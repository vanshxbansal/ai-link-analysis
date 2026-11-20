"""Orchestrates extraction -> LLM analysis -> validation -> response."""

import logging
import time
from collections import OrderedDict
from typing import Optional, Tuple

from app.config import get_settings
from app.schemas import ALLOWED_PLATFORMS, AnalysisMeta, AnalysisResponse
from app.services import llm_service, website_extractor
from app.services.competitor_service import finalize_competitor_analysis

logger = logging.getLogger(__name__)


class TTLCache:
    """Small in-memory LRU cache with expiry, to avoid paying twice for the same URL."""

    def __init__(self, ttl_seconds: int, max_entries: int):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: "OrderedDict[str, Tuple[float, AnalysisResponse]]" = OrderedDict()

    def get(self, key: str) -> Optional[AnalysisResponse]:
        item = self._store.get(key)
        if not item:
            return None
        stored_at, value = item
        if time.time() - stored_at > self.ttl:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: AnalysisResponse) -> None:
        self._store[key] = (time.time(), value)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


_settings = get_settings()
cache = TTLCache(_settings.cache_ttl_seconds, _settings.cache_max_entries)


def _cache_key(url: str) -> str:
    return url.strip().lower().rstrip("/")


def _postprocess(result: llm_service.LLMResult):
    """Apply business rules the LLM may not have followed exactly."""
    output = result.data
    analysis = output.analysis

    competitor_analysis = finalize_competitor_analysis(
        analysis.competitor_analysis, output.brand.name, output.brand.target_market
    )
    if not competitor_analysis.main_category:
        competitor_analysis = competitor_analysis.model_copy(update={"main_category": output.brand.category})

    # Keep 5 queries with at least one valid platform; make sure every platform is represented
    queries = [q for q in analysis.target_search_queries if q.query and q.platforms][:5]
    covered = {p for q in queries for p in q.platforms}
    missing = [p for p in ALLOWED_PLATFORMS if p not in covered]
    for q in queries:
        if not missing:
            break
        if len(q.platforms) < 3:
            q.platforms.append(missing.pop(0))

    services = [s for s in analysis.top_services if s.service_name][:5]

    return output.brand, analysis.model_copy(
        update={
            "competitor_analysis": competitor_analysis,
            "target_search_queries": queries,
            "top_services": services,
        }
    )


async def run_full_analysis(url: str, use_cache: bool = True) -> AnalysisResponse:
    settings = get_settings()
    started = time.perf_counter()
    key = _cache_key(url)

    if use_cache:
        cached = cache.get(key)
        if cached:
            logger.info("Cache hit for %s", url)
            meta = cached.meta.model_copy(update={"cached": True}) if cached.meta else None
            return cached.model_copy(update={"meta": meta})

    # 1-5. Fetch, extract, clean
    content = await website_extractor.extract_website_content(
        url,
        timeout=settings.request_timeout,
        max_length=settings.max_content_length,
        max_bytes=settings.max_html_bytes,
        max_extra_pages=settings.max_extra_pages,
    )
    summary = website_extractor.build_content_summary(content, settings.max_llm_content_chars)
    logger.info(
        "Extracted %s: pages=%d chars_sent=%d (homepage text=%d chars)",
        content.url, content.pages_analyzed, len(summary), len(content.main_text),
    )

    # 6-8. LLM analysis + validation
    result = await llm_service.run_llm_analysis(summary)
    brand, analysis = _postprocess(result)

    # Feed the real on-page title/meta into the SEO section for comparison
    seo = analysis.seo_improvements.model_copy(
        update={"current_title": content.title, "current_meta_description": content.meta_description}
    )
    analysis = analysis.model_copy(update={"seo_improvements": seo})

    response = AnalysisResponse(
        success=True,
        website=url,
        brand=brand,
        analysis=analysis,
        meta=AnalysisMeta(
            provider=result.provider,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            llm_latency_ms=result.latency_ms,
            total_latency_ms=int((time.perf_counter() - started) * 1000),
            pages_analyzed=content.pages_analyzed,
            content_chars_sent=len(summary),
            cached=False,
        ),
    )
    cache.set(key, response)
    return response
