import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.utils.validators import validate_url, normalize_url

client = TestClient(app)


# --- Validator tests ---

def test_validate_url_valid():
    valid, msg = validate_url("https://example.com")
    assert valid is True
    assert msg == ""


def test_validate_url_localhost_blocked():
    valid, msg = validate_url("http://localhost/api")
    assert valid is False
    assert "not allowed" in msg.lower()


def test_validate_url_private_ip_blocked():
    valid, msg = validate_url("http://192.168.1.1/admin")
    assert valid is False


def test_validate_url_no_scheme():
    valid, msg = validate_url("ftp://example.com")
    assert valid is False


def test_validate_url_empty():
    valid, msg = validate_url("")
    assert valid is False


def test_normalize_url_adds_https():
    assert normalize_url("example.com") == "https://example.com"


def test_normalize_url_keeps_http():
    assert normalize_url("http://example.com") == "http://example.com"


# --- API endpoint tests ---

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_link_analysis_missing_url():
    response = client.post("/link-analysis", json={})
    assert response.status_code == 422


def test_link_analysis_localhost_blocked():
    response = client.post("/link-analysis", json={"url": "http://localhost:8080"})
    assert response.status_code == 400


def test_link_analysis_private_ip_blocked():
    response = client.post("/link-analysis", json={"url": "http://192.168.0.1"})
    assert response.status_code == 400


MOCK_LLM_RESPONSE = {
    "brand": {
        "name": "Example Corp",
        "category": "Technology Services",
        "summary": "A technology company providing digital solutions."
    },
    "analysis": {
        "competitor_analysis": {
            "brand_overview": "Example Corp is a leading tech firm.",
            "main_products_services": ["Web Development", "Mobile Apps"],
            "competitive_advantages": ["Affordable pricing", "Fast delivery"],
            "competitors": [
                {
                    "name": "TechRival Inc",
                    "overview": "A competing tech firm.",
                    "strengths": ["Established brand"],
                    "weaknesses": ["Higher cost"]
                },
                {
                    "name": "DevCo",
                    "overview": "Another tech competitor.",
                    "strengths": ["Large team"],
                    "weaknesses": ["Slow delivery"]
                },
                {
                    "name": "BuildSoft",
                    "overview": "Software development house.",
                    "strengths": ["Specialization"],
                    "weaknesses": ["Limited offerings"]
                }
            ],
            "opportunities": ["Expand to new markets", "Invest in SEO"]
        },
        "target_search_queries": [
            {
                "query": "best tech company for startups",
                "platforms": ["Google"],
                "intent": "Service Discovery",
                "business_relevance": "High relevance for new clients",
                "target_audience": "Startup founders"
            },
            {
                "query": "web development services near me",
                "platforms": ["Google", "Facebook"],
                "intent": "Local Search",
                "business_relevance": "Local client acquisition",
                "target_audience": "Local businesses"
            },
            {
                "query": "affordable mobile app development",
                "platforms": ["Instagram"],
                "intent": "Cost Discovery",
                "business_relevance": "Budget-conscious clients",
                "target_audience": "SMBs"
            },
            {
                "query": "hire web developer for startup",
                "platforms": ["LinkedIn"],
                "intent": "B2B Search",
                "business_relevance": "B2B lead generation",
                "target_audience": "CTOs and product managers"
            },
            {
                "query": "top software development company",
                "platforms": ["X"],
                "intent": "Brand Discovery",
                "business_relevance": "Brand awareness",
                "target_audience": "Tech enthusiasts"
            }
        ],
        "seo_improvements": {
            "primary_keyword": "technology services company",
            "secondary_keywords": ["web development", "mobile apps"],
            "long_tail_keywords": ["affordable web development for startups"],
            "recommended_title": "Example Corp | Technology Services for Startups",
            "meta_description": "Example Corp provides affordable web and mobile solutions for businesses.",
            "supporting_content": ["Blog: Top 10 Web Dev Tips", "FAQ page", "Service landing pages"]
        },
        "top_services": [
            {
                "service_name": "Web Development",
                "description": "Full-stack web development.",
                "target_industry": "All industries",
                "target_customer": "Businesses needing online presence",
                "main_benefit": "Professional online presence"
            },
            {
                "service_name": "Mobile App Development",
                "description": "iOS and Android apps.",
                "target_industry": "Retail and services",
                "target_customer": "Businesses needing mobile apps",
                "main_benefit": "Reach mobile users"
            },
            {
                "service_name": "SEO Services",
                "description": "Search engine optimization.",
                "target_industry": "E-commerce",
                "target_customer": "Businesses wanting more traffic",
                "main_benefit": "Higher search rankings"
            },
            {
                "service_name": "UI/UX Design",
                "description": "User interface and experience design.",
                "target_industry": "SaaS",
                "target_customer": "Startups",
                "main_benefit": "Better user engagement"
            },
            {
                "service_name": "Cloud Solutions",
                "description": "Cloud infrastructure and hosting.",
                "target_industry": "Technology",
                "target_customer": "Growing businesses",
                "main_benefit": "Scalability and reliability"
            }
        ],
        "target_audience": {
            "primary_audience": ["Startups", "SMBs"],
            "secondary_audience": ["Enterprise companies"],
            "industries": ["Technology", "Retail"],
            "business_types": ["Startups", "Small businesses"],
            "customer_profiles": ["Tech-savvy founders", "Non-technical business owners"],
            "geographical_focus": "Global",
            "customer_needs": ["Digital presence", "Cost-effective solutions"],
            "potential_interests": ["Digital transformation", "Growth hacking"],
            "recommended_segments": ["Startup founders aged 25-45", "SMB owners in tech sector"]
        }
    }
}


@patch("app.services.llm_service.analyze_with_gemini")
@patch("app.services.website_extractor.extract_website_content")
def test_link_analysis_success(mock_extract, mock_llm):
    from app.services.website_extractor import ExtractedContent

    mock_extract.return_value = ExtractedContent(
        url="https://example.com",
        title="Example Corp",
        meta_description="A tech company",
        headings=["Web Development", "About Us"],
        main_text="We build websites and mobile apps.",
        links=[],
        keywords=["web development"],
    )
    mock_llm.return_value = MOCK_LLM_RESPONSE

    response = client.post("/link-analysis", json={"url": "https://example.com"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["brand"]["name"] == "Example Corp"
    assert len(data["analysis"]["top_services"]) == 5
    assert len(data["analysis"]["target_search_queries"]) == 5
    assert "competitor_analysis" in data["analysis"]
    assert "seo_improvements" in data["analysis"]
    assert "target_audience" in data["analysis"]
