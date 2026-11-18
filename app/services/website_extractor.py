import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REMOVE_TAGS = ["script", "style", "noscript", "iframe", "svg", "img", "header", "footer", "nav"]


@dataclass
class ExtractedContent:
    url: str
    title: str
    meta_description: str
    headings: list[str]
    main_text: str
    links: list[str]
    keywords: list[str]


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    cleaned = [line for line in lines if line and len(line) > 2]
    return "\n".join(cleaned)


async def extract_website_content(url: str, timeout: int = 30, max_length: int = 50000) -> ExtractedContent:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers=HEADERS,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    soup = BeautifulSoup(html, "lxml")

    for tag in soup(REMOVE_TAGS):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_description = meta_tag["content"].strip()

    # Also check og:description
    if not meta_description:
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            meta_description = og_desc["content"].strip()

    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.get_text(strip=True)
        if text:
            headings.append(text)

    keywords = []
    kw_tag = soup.find("meta", attrs={"name": "keywords"})
    if kw_tag and kw_tag.get("content"):
        keywords = [k.strip() for k in kw_tag["content"].split(",")]

    body = soup.find("body")
    main_text = ""
    if body:
        raw_text = body.get_text(separator="\n")
        main_text = _clean_text(raw_text)

    # Truncate to avoid huge LLM inputs
    if len(main_text) > max_length:
        main_text = main_text[:max_length]

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and len(links) < 50:
            links.append(href)

    return ExtractedContent(
        url=url,
        title=title,
        meta_description=meta_description,
        headings=headings[:30],
        main_text=main_text,
        links=links,
        keywords=keywords,
    )


def build_content_summary(content: ExtractedContent) -> str:
    """Build a compact text summary to send to the LLM."""
    parts = [
        f"Website URL: {content.url}",
        f"Page Title: {content.title}",
    ]

    if content.meta_description:
        parts.append(f"Meta Description: {content.meta_description}")

    if content.keywords:
        parts.append(f"Keywords: {', '.join(content.keywords[:20])}")

    if content.headings:
        parts.append("Page Headings:\n" + "\n".join(f"  - {h}" for h in content.headings[:20]))

    parts.append(f"\nMain Content:\n{content.main_text[:8000]}")

    return "\n\n".join(parts)
