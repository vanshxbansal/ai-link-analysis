"""Fetches a website and extracts clean, LLM-ready business content."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.exceptions import (
    InsufficientContentError,
    InvalidURLError,
    WebsiteFetchError,
    WebsiteTimeoutError,
)
from app.utils.validators import validate_url

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REMOVE_TAGS = ["script", "style", "noscript", "iframe", "svg", "canvas", "form", "template", "img", "video", "audio"]
BOILERPLATE_TAGS = ["header", "footer", "nav", "aside"]
MAX_REDIRECTS = 5

# Internal pages that usually describe the business best
KEY_PAGE_PATTERNS = re.compile(
    r"\b(about|about-us|company|services|service|solutions|products|product|what-we-do|features|pricing)\b",
    re.IGNORECASE,
)


@dataclass
class PageContent:
    url: str
    title: str = ""
    text: str = ""


@dataclass
class ExtractedContent:
    url: str
    title: str
    meta_description: str
    headings: List[str]
    main_text: str
    links: List[str]
    keywords: List[str]
    site_name: str = ""
    language: str = ""
    nav_items: List[str] = field(default_factory=list)
    structured_data: List[str] = field(default_factory=list)
    extra_pages: List[PageContent] = field(default_factory=list)

    @property
    def pages_analyzed(self) -> int:
        return 1 + len(self.extra_pages)


def _clean_text(text: str) -> str:
    """Collapse whitespace, drop tiny fragments and duplicate lines."""
    seen = set()
    cleaned = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) <= 2:
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)
    return "\n".join(cleaned)


async def _fetch_html(client: httpx.AsyncClient, url: str, max_bytes: int) -> Tuple[str, str]:
    """
    Fetch HTML while following redirects manually so that every hop is
    re-validated against the SSRF rules. Returns (final_url, html).
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        ok, err = await asyncio.to_thread(validate_url, current)
        if not ok:
            raise InvalidURLError(f"Blocked URL ({current}): {err}")

        try:
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise WebsiteFetchError("Redirect without a Location header")
                    current = urljoin(current, location)
                    continue

                if response.status_code >= 400:
                    raise WebsiteFetchError(
                        f"Website returned HTTP {response.status_code}. "
                        "The page may be restricted, missing or blocking automated access."
                    )

                content_type = response.headers.get("content-type", "").lower()
                if content_type and "html" not in content_type and "xml" not in content_type:
                    raise WebsiteFetchError(
                        f"URL does not point to an HTML page (content-type: {content_type.split(';')[0]})"
                    )

                chunks = []
                size = 0
                async for chunk in response.aiter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= max_bytes:
                        break
                raw = b"".join(chunks)
                encoding = response.encoding or "utf-8"
                return str(response.url), raw.decode(encoding, errors="replace")

        except httpx.TimeoutException:
            raise WebsiteTimeoutError(f"Request to {current} timed out. The website may be slow or unreachable.")
        except httpx.RequestError as e:
            raise WebsiteFetchError(f"Could not reach the website: {e.__class__.__name__}")

    raise WebsiteFetchError("Too many redirects")


def _extract_structured_data(soup: BeautifulSoup) -> List[str]:
    """Pull useful fields out of JSON-LD (Organization, Product, Service...)."""
    results = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            parts = []
            for key in ("@type", "name", "description", "slogan", "areaServed", "address"):
                value = item.get(key)
                if isinstance(value, (str, int)):
                    parts.append(f"{key}: {value}")
                elif isinstance(value, dict):
                    flat = ", ".join(str(v) for v in value.values() if isinstance(v, (str, int)))
                    if flat:
                        parts.append(f"{key}: {flat}")
            if len(parts) > 1:
                results.append("; ".join(parts)[:400])
    return results[:5]


def _meta(soup: BeautifulSoup, **attrs) -> str:
    tag = soup.find("meta", attrs=attrs)
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def _body_text(soup: BeautifulSoup, max_length: int) -> str:
    container = soup.find("main") or soup.find("body") or soup
    text = _clean_text(container.get_text(separator="\n"))
    return text[:max_length]


def _find_key_pages(soup: BeautifulSoup, base_url: str, limit: int) -> List[str]:
    base_host = urlparse(base_url).hostname
    found = []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0].rstrip("/")
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or parsed.hostname != base_host:
            continue
        if href.rstrip("/") == base_url.rstrip("/") or href in found:
            continue
        path_and_text = f"{parsed.path} {a.get_text(' ', strip=True)}"
        if KEY_PAGE_PATTERNS.search(path_and_text) and parsed.path.count("/") <= 2:
            found.append(href)
        if len(found) >= limit:
            break
    return found


async def _fetch_extra_page(client: httpx.AsyncClient, url: str, max_bytes: int) -> Optional[PageContent]:
    try:
        final_url, html = await _fetch_html(client, url, max_bytes)
    except Exception as e:  # best effort: extra pages must never break the analysis
        logger.info("Skipping extra page %s: %s", url, e)
        return None
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(REMOVE_TAGS + BOILERPLATE_TAGS):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    return PageContent(url=final_url, title=title, text=_body_text(soup, 4000))


async def extract_website_content(
    url: str,
    timeout: int = 20,
    max_length: int = 50000,
    max_bytes: int = 3_000_000,
    max_extra_pages: int = 2,
) -> ExtractedContent:
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout, headers=HEADERS) as client:
        final_url, html = await _fetch_html(client, url, max_bytes)
        soup = BeautifulSoup(html, "lxml")

        structured_data = _extract_structured_data(soup)

        title = soup.title.get_text(strip=True) if soup.title else ""
        meta_description = _meta(soup, name="description") or _meta(soup, property="og:description")
        site_name = _meta(soup, property="og:site_name")
        keywords_raw = _meta(soup, name="keywords")
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()][:20]
        html_tag = soup.find("html")
        language = (html_tag.get("lang") or "") if html_tag else ""

        # Navigation labels are a strong hint about products/services
        nav_items = []
        for nav in soup.find_all("nav"):
            for a in nav.find_all("a"):
                label = a.get_text(" ", strip=True)
                if 2 < len(label) < 40 and label not in nav_items:
                    nav_items.append(label)
        nav_items = nav_items[:30]

        key_pages = _find_key_pages(soup, final_url, max_extra_pages) if max_extra_pages > 0 else []

        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(final_url, a["href"])
            if href.startswith("http") and href not in links:
                links.append(href)
            if len(links) >= 50:
                break

        for tag in soup(REMOVE_TAGS + BOILERPLATE_TAGS):
            tag.decompose()

        headings = []
        for tag in soup.find_all(["h1", "h2", "h3"]):
            text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
            if text and text not in headings:
                headings.append(text)

        main_text = _body_text(soup, max_length)

        extra_pages = []
        if key_pages:
            results = await asyncio.gather(*[_fetch_extra_page(client, p, max_bytes) for p in key_pages])
            extra_pages = [r for r in results if r and r.text]

    if not (title or meta_description or main_text or extra_pages):
        raise InsufficientContentError(
            "The website returned no readable content. It may rely entirely on JavaScript rendering."
        )

    return ExtractedContent(
        url=final_url,
        title=title,
        meta_description=meta_description,
        headings=headings[:30],
        main_text=main_text,
        links=links,
        keywords=keywords,
        site_name=site_name,
        language=language,
        nav_items=nav_items,
        structured_data=structured_data,
        extra_pages=extra_pages,
    )


def build_content_summary(content: ExtractedContent, max_chars: int = 12000) -> str:
    """Build a compact, token-efficient text summary to send to the LLM."""
    parts = [f"Website URL: {content.url}", f"Page Title: {content.title}"]

    if content.site_name:
        parts.append(f"Site Name: {content.site_name}")
    if content.language:
        parts.append(f"Language: {content.language}")
    if content.meta_description:
        parts.append(f"Meta Description: {content.meta_description}")
    if content.keywords:
        parts.append(f"Meta Keywords: {', '.join(content.keywords)}")
    if content.structured_data:
        parts.append("Structured Data:\n" + "\n".join(f"  - {s}" for s in content.structured_data))
    if content.nav_items:
        parts.append(f"Navigation: {' | '.join(content.nav_items)}")
    if content.headings:
        parts.append("Page Headings:\n" + "\n".join(f"  - {h}" for h in content.headings[:25]))

    header = "\n\n".join(parts)
    budget = max(max_chars - len(header), 2000)

    # Give the homepage ~65% of the remaining budget, split the rest across key pages
    extra_budget = int(budget * 0.35) if content.extra_pages else 0
    body = [f"Homepage Content:\n{content.main_text[: budget - extra_budget]}"]
    if content.extra_pages:
        per_page = extra_budget // len(content.extra_pages)
        for page in content.extra_pages:
            body.append(f"Page ({page.url}) - {page.title}:\n{page.text[:per_page]}")

    return header + "\n\n" + "\n\n".join(body)
