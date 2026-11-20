"""
Benchmark LLM models on real websites: latency, token usage, cost and output validity.

Usage:
    python -m scripts.benchmark --models gemini-3.5-flash-lite gemini-3.8-flash --urls https://stripe.com
Results are printed as a Markdown table and saved to docs/benchmark_results.json.
"""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

from app.config import get_settings
from app.services import llm_service
from app.services.website_extractor import build_content_summary, extract_website_content

DEFAULT_URLS = [
    "https://stripe.com",
    "https://www.shopify.com",
    "https://mailchimp.com",
    "https://www.notion.com",
]


async def benchmark(models, urls):
    settings = get_settings()
    summaries = {}
    for url in urls:
        content = await extract_website_content(url, max_extra_pages=settings.max_extra_pages)
        summaries[url] = build_content_summary(content, settings.max_llm_content_chars)

    rows = []
    for model in models:
        call = llm_service._call_openai if model.startswith("gpt") else llm_service._call_gemini
        for url, summary in summaries.items():
            entry = {"model": model, "url": url}
            try:
                async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
                    for attempt in range(1, 4):  # retry provider overload (429/503) like the API does
                        started = time.perf_counter()
                        try:
                            text, in_tok, out_tok = await call(client, model, summary)
                            break
                        except llm_service._RetryableError:
                            if attempt == 3:
                                raise
                            await asyncio.sleep(2 * attempt)
                    entry["attempts"] = attempt
                output = llm_service._validate(llm_service._extract_json(text))
                a = output.analysis
                platforms = {p for q in a.target_search_queries for p in q.platforms}
                result = llm_service.LLMResult(output, "", model, in_tok, out_tok, 0)
                entry.update(
                    ok=True,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cost_usd=result.estimated_cost_usd,
                    competitors=len(a.competitor_analysis.competitors),
                    queries=len(a.target_search_queries),
                    platforms_covered=len(platforms),
                    services=len(a.top_services),
                    brand=output.brand.name,
                )
            except Exception as e:
                entry.update(ok=False, error=f"{e.__class__.__name__}: {str(e)[:150]}")
            print(json.dumps(entry))
            rows.append(entry)
    return rows


def summarize(rows):
    print("\n| Model | Runs OK | Avg latency (s) | Avg input tok | Avg output tok | Avg cost (USD) | Schema complete* |")
    print("|---|---|---|---|---|---|---|")
    for model in dict.fromkeys(r["model"] for r in rows):
        mr = [r for r in rows if r["model"] == model]
        ok = [r for r in mr if r.get("ok")]
        if not ok:
            print(f"| {model} | 0/{len(mr)} | - | - | - | - | - |")
            continue
        complete = sum(
            1 for r in ok if r["competitors"] >= 3 and r["queries"] == 5 and r["services"] == 5 and r["platforms_covered"] == 5
        )
        avg = lambda k: statistics.mean(r[k] for r in ok if r.get(k) is not None)  # noqa: E731
        print(
            f"| {model} | {len(ok)}/{len(mr)} | {avg('latency_ms') / 1000:.1f} | {avg('input_tokens'):.0f} | "
            f"{avg('output_tokens'):.0f} | {avg('cost_usd'):.4f} | {complete}/{len(ok)} |"
        )
    print("\n*3+ competitors, exactly 5 queries covering all 5 platforms, exactly 5 services (before post-processing).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=[get_settings().gemini_model])
    parser.add_argument("--urls", nargs="+", default=DEFAULT_URLS)
    args = parser.parse_args()

    results = asyncio.run(benchmark(args.models, args.urls))
    out = Path("docs/benchmark_results.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    summarize(results)
