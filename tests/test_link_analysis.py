import asyncio
import copy
import json
from functools import partial
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.exceptions import InvalidURLError, LLMConfigError, LLMServiceError
from app.main import app
from app.schemas import Competitor, LLMOutput, SearchQuery, Service
from app.services import analysis_service, llm_service, website_extractor
from app.services.competitor_service import clean_competitors, finalize_competitor_analysis
from app.utils import validators
from app.utils.validators import is_private_ip, normalize_url, validate_url

client = TestClient(app)
PUBLIC_IP = ["93.184.215.14"]


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """Resolve every hostname to a public IP so tests never depend on real DNS."""
    monkeypatch.setattr(validators, "resolve_host", lambda host: PUBLIC_IP)
    analysis_service.cache.clear()
    yield


# ---------------------------------------------------------------- validators


def test_validate_url_valid():
    assert validate_url("https://example.com") == (True, "")


def test_validate_url_without_scheme_is_accepted():
    assert validate_url("example.com")[0] is True


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/api",
        "http://127.0.0.1",
        "http://192.168.1.1/admin",
        "http://10.0.0.5",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0",
        "http://100.64.0.1",
        "http://metadata.google.internal",
        "http://printer.local",
    ],
)
def test_validate_url_blocks_internal_targets(url):
    valid, msg = validate_url(url)
    assert valid is False
    assert "not allowed" in msg.lower()


def test_validate_url_blocks_domain_resolving_to_private_ip(monkeypatch):
    monkeypatch.setattr(validators, "resolve_host", lambda host: ["93.184.215.14", "10.1.2.3"])
    valid, msg = validate_url("https://rebind.example.com")
    assert valid is False
    assert "private" in msg.lower()


@pytest.mark.parametrize(
    "url,fragment",
    [
        ("ftp://example.com", "http"),
        ("", "required"),
        ("https://user:pass@example.com", "credentials"),
        ("https://example.com:22", "port"),
        ("https://intranet", "fully qualified"),
    ],
)
def test_validate_url_rejects_invalid(url, fragment):
    valid, msg = validate_url(url)
    assert valid is False
    assert fragment in msg.lower()


def test_is_private_ip():
    assert is_private_ip("172.16.5.4")
    assert is_private_ip("fd00::1")
    assert not is_private_ip("8.8.8.8")


def test_normalize_url():
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("http://example.com") == "http://example.com"
    assert normalize_url("  https://example.com ") == "https://example.com"


# ---------------------------------------------------------------- schemas / parsing


def test_platform_names_are_normalized():
    q = SearchQuery(query="x", platforms=["twitter", "Google Search", "TikTok", "linkedin"])
    assert q.platforms == ["X", "Google", "LinkedIn"]


def test_service_source_label_is_normalized():
    assert Service(service_name="a", source="Inferred recommendation").source == "inferred"
    assert Service(service_name="a", source="website").source == "website_content"


def test_extract_json_handles_code_fences_and_noise():
    assert llm_service._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm_service._extract_json('Here you go: {"a": 2} thanks') == {"a": 2}


def test_validate_rejects_incomplete_output():
    with pytest.raises(ValueError):
        llm_service._validate({"brand": {"name": "X"}, "analysis": {}})


# ---------------------------------------------------------------- competitor service


def test_clean_competitors_dedupes_removes_brand_and_labels():
    comps = [
        Competitor(name="Acme"),
        Competitor(name="Rival"),
        Competitor(name="rival"),
        Competitor(name="Other", source="trust me"),
    ]
    result = clean_competitors(comps, brand_name="acme")
    assert [c.name for c in result] == ["Rival", "Other"]
    assert all("AI-generated" in c.source for c in result)


# ---------------------------------------------------------------- website extraction

SAMPLE_HTML = """
<html lang="en"><head>
  <title>Acme Web Studio | Websites for Small Businesses</title>
  <meta name="description" content="Acme builds fast websites for small businesses.">
  <meta property="og:site_name" content="Acme Web Studio">
  <script type="application/ld+json">{"@type": "Organization", "name": "Acme Web Studio", "areaServed": "Austin, TX"}</script>
  <script>var tracking = 1;</script>
</head><body>
  <nav><a href="/services">Services</a><a href="/about">About Us</a><a href="/blog/post-1">Blog</a></nav>
  <main>
    <h1>Websites that grow your business</h1>
    <p>We design and develop websites for local businesses.</p>
    <p>We design and develop websites for local businesses.</p>
    <h2>E-commerce development</h2><p>Shopify and WooCommerce stores.</p>
  </main>
  <footer>Copyright 2026</footer>
</body></html>
"""


def _mock_client_factory(handler):
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    return factory


def test_extract_website_content_parses_and_cleans(monkeypatch):
    def handler(request):
        if request.url.path == "/services":
            return httpx.Response(200, html="<html><title>Services</title><body><p>SEO and hosting plans.</p></body></html>")
        if request.url.path == "/about":
            return httpx.Response(404)
        return httpx.Response(200, html=SAMPLE_HTML)

    monkeypatch.setattr(website_extractor.httpx, "AsyncClient", _mock_client_factory(handler))
    content = asyncio.run(website_extractor.extract_website_content("https://acme.example.com"))

    assert content.title.startswith("Acme Web Studio")
    assert content.meta_description == "Acme builds fast websites for small businesses."
    assert content.site_name == "Acme Web Studio"
    assert "Websites that grow your business" in content.headings
    assert content.main_text.count("We design and develop websites") == 1  # de-duplicated
    assert "tracking" not in content.main_text and "Copyright" not in content.main_text
    assert any("Austin" in s for s in content.structured_data)
    assert "Services" in content.nav_items
    assert [p.title for p in content.extra_pages] == ["Services"]  # 404 page skipped gracefully

    summary = website_extractor.build_content_summary(content)
    assert "SEO and hosting plans" in summary and "Meta Description" in summary


def test_redirect_to_internal_address_is_blocked(monkeypatch):
    def handler(request):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    monkeypatch.setattr(website_extractor.httpx, "AsyncClient", _mock_client_factory(handler))
    with pytest.raises(InvalidURLError):
        asyncio.run(website_extractor.extract_website_content("https://evil.example.com"))


def test_non_html_content_is_rejected(monkeypatch):
    handler = lambda request: httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})  # noqa
    monkeypatch.setattr(website_extractor.httpx, "AsyncClient", _mock_client_factory(handler))
    response = client.post("/link-analysis", json={"url": "https://example.com/file.pdf"})
    assert response.status_code == 502
    assert response.json()["success"] is False


# ---------------------------------------------------------------- LLM provider chain

MOCK_LLM_RESPONSE = {
    "brand": {
        "name": "Example Corp",
        "category": "Technology Services",
        "summary": "A technology company providing digital solutions.",
        "target_market": "Small businesses",
    },
    "analysis": {
        "competitor_analysis": {
            "brand_overview": "Example Corp is a web agency.",
            "main_products_services": ["Web Development", "Mobile Apps"],
            "competitive_advantages": ["Affordable pricing"],
            "competitors": [
                {"name": "TechRival Inc", "overview": "x", "main_service": "Web", "target_market": "Enterprise",
                 "strengths": ["Established brand"], "weaknesses": ["Higher cost"]},
                {"name": "DevCo", "overview": "y", "strengths": ["Large team"], "weaknesses": ["Slow delivery"]},
                {"name": "Example Corp", "overview": "self", "strengths": [], "weaknesses": []},
                {"name": "BuildSoft", "overview": "z", "strengths": ["Niche"], "weaknesses": ["Limited offerings"]},
            ],
            "opportunities": ["Invest in SEO"],
        },
        "target_search_queries": [
            {"query": "best web agency for startups", "platforms": ["Google"], "intent": "Service Discovery"},
            {"query": "web design near me", "platforms": ["Google Search"], "intent": "Local"},
            {"query": "website design ideas", "platforms": ["instagram"], "intent": "Inspiration"},
            {"query": "hire web developer", "platforms": ["LinkedIn"], "intent": "B2B"},
            {"query": "affordable web dev", "platforms": ["Twitter"], "intent": "Discovery"},
        ],
        "seo_improvements": {
            "primary_keyword": "web development company",
            "secondary_keywords": ["web design"],
            "recommended_title": "Example Corp | Web Development Company",
            "meta_description": "Example Corp builds websites.",
            "supporting_content": ["FAQ page"],
        },
        "top_services": [
            {"service_name": f"Service {i}", "description": "d", "source": "website_content" if i < 4 else "inferred"}
            for i in range(5)
        ],
        "target_audience": {
            "primary_audience": ["Startups"],
            "audience_segments": [{"audience": "Audience 1", "business_type": "Startups", "requirement": "Website"}],
        },
    },
}


def test_llm_chain_falls_back_to_next_model(monkeypatch):
    calls = []

    async def failing(client, model, content):
        calls.append(model)
        raise llm_service._RetryableError("HTTP 503")

    async def working(client, model, content):
        calls.append(model)
        return json.dumps(MOCK_LLM_RESPONSE), 1000, 500

    monkeypatch.setattr(llm_service, "_providers", lambda: [("gemini", "primary", failing), ("gemini", "gemini-3.5-flash-lite", working)])
    monkeypatch.setattr(llm_service.asyncio, "sleep", AsyncMock())

    result = asyncio.run(llm_service.run_llm_analysis("content"))
    assert calls == ["primary", "primary", "gemini-3.5-flash-lite"]
    assert result.model == "gemini-3.5-flash-lite"
    assert result.estimated_cost_usd == pytest.approx((1000 * 0.30 + 500 * 2.50) / 1e6)


def test_llm_chain_raises_when_all_fail(monkeypatch):
    async def bad_json(client, model, content):
        return "not json", 1, 1

    monkeypatch.setattr(llm_service, "_providers", lambda: [("gemini", "m", bad_json)])
    with pytest.raises(LLMServiceError):
        asyncio.run(llm_service.run_llm_analysis("content"))


def test_llm_without_api_key(monkeypatch):
    monkeypatch.setattr(llm_service, "_providers", lambda: [])
    with pytest.raises(LLMConfigError):
        asyncio.run(llm_service.run_llm_analysis("content"))


# ---------------------------------------------------------------- API


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_url_returns_structured_422():
    response = client.post("/link-analysis", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False and body["error"] == "Validation error"


@pytest.mark.parametrize("url", ["http://localhost:8080", "http://192.168.0.1", "ftp://example.com"])
def test_blocked_urls_return_structured_400(url):
    response = client.post("/link-analysis", json={"url": url})
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_llm_not_configured_returns_503(monkeypatch):
    monkeypatch.setattr(website_extractor, "extract_website_content", AsyncMock(return_value=_sample_content()))
    monkeypatch.setattr(llm_service, "_providers", lambda: [])
    response = client.post("/link-analysis", json={"url": "https://example.com"})
    assert response.status_code == 503
    assert response.json()["success"] is False


def _sample_content():
    return website_extractor.ExtractedContent(
        url="https://example.com",
        title="Example Corp",
        meta_description="A tech company",
        headings=["Web Development"],
        main_text="We build websites and mobile apps.",
        links=[],
        keywords=[],
    )


def test_link_analysis_success_and_cache(monkeypatch):
    extract = AsyncMock(return_value=_sample_content())
    llm = AsyncMock(
        return_value=llm_service.LLMResult(
            LLMOutput.model_validate(copy.deepcopy(MOCK_LLM_RESPONSE)), "gemini", "gemini-3.5-flash-lite", 3000, 2500, 8000
        )
    )
    monkeypatch.setattr(website_extractor, "extract_website_content", extract)
    monkeypatch.setattr(llm_service, "run_llm_analysis", llm)

    response = client.post("/link-analysis", json={"url": "example.com"})
    assert response.status_code == 200
    data = response.json()
    analysis = data["analysis"]

    assert data["success"] is True
    assert data["website"] == "https://example.com"
    assert data["brand"]["name"] == "Example Corp"

    # Section 1: brand itself removed from competitors, all labelled, table built
    competitors = analysis["competitor_analysis"]["competitors"]
    assert [c["name"] for c in competitors] == ["TechRival Inc", "DevCo", "BuildSoft"]
    assert all("AI-generated" in c["source"] for c in competitors)
    assert analysis["competitor_analysis"]["comparison_table"]
    assert analysis["competitor_analysis"]["competitor_gaps"]

    # Section 2: 5 queries and every platform covered after normalisation/post-processing
    queries = analysis["target_search_queries"]
    assert len(queries) == 5
    assert {p for q in queries for p in q["platforms"]} == {"Google", "Facebook", "Instagram", "LinkedIn", "X"}

    # Section 3: current on-page SEO is reported next to recommendations
    assert analysis["seo_improvements"]["current_title"] == "Example Corp"

    # Section 4: inferred services are labelled
    assert len(analysis["top_services"]) == 5
    assert analysis["top_services"][4]["source"] == "inferred"

    # Section 5
    assert analysis["target_audience"]["audience_segments"][0]["business_type"] == "Startups"

    assert data["meta"]["estimated_cost_usd"] == pytest.approx((3000 * 0.30 + 2500 * 2.50) / 1e6)
    assert data["meta"]["cached"] is False

    # Second call is served from cache without new LLM usage
    again = client.post("/link-analysis", json={"url": "https://example.com/"})
    assert again.json()["meta"]["cached"] is True
    assert llm.await_count == 1

    # refresh=true bypasses the cache
    client.post("/link-analysis?refresh=true", json={"url": "https://example.com"})
    assert llm.await_count == 2
