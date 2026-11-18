from app.services.website_extractor import extract_website_content, build_content_summary
from app.services.llm_service import run_llm_analysis
from app.schemas import (
    AnalysisResponse, BrandInfo, Analysis,
    CompetitorAnalysis, Competitor, SearchQuery,
    SEOImprovements, Service, TargetAudience,
)
from app.config import get_settings


def _parse_competitor(c: dict) -> Competitor:
    return Competitor(
        name=c.get("name", "Unknown"),
        overview=c.get("overview", ""),
        strengths=c.get("strengths", []),
        weaknesses=c.get("weaknesses", []),
    )


def _parse_response(url: str, raw: dict) -> AnalysisResponse:
    brand_data = raw.get("brand", {})
    brand = BrandInfo(
        name=brand_data.get("name", "Unknown"),
        category=brand_data.get("category", "Unknown"),
        summary=brand_data.get("summary", ""),
    )

    analysis_data = raw.get("analysis", {})

    # Competitor analysis
    ca_data = analysis_data.get("competitor_analysis", {})
    competitor_analysis = CompetitorAnalysis(
        brand_overview=ca_data.get("brand_overview", ""),
        main_products_services=ca_data.get("main_products_services", []),
        competitive_advantages=ca_data.get("competitive_advantages", []),
        competitors=[_parse_competitor(c) for c in ca_data.get("competitors", [])],
        opportunities=ca_data.get("opportunities", []),
    )

    # Search queries
    queries = []
    for q in analysis_data.get("target_search_queries", []):
        queries.append(SearchQuery(
            query=q.get("query", ""),
            platforms=q.get("platforms", []),
            intent=q.get("intent", ""),
            business_relevance=q.get("business_relevance", ""),
            target_audience=q.get("target_audience", ""),
        ))

    # SEO
    seo_data = analysis_data.get("seo_improvements", {})
    seo = SEOImprovements(
        primary_keyword=seo_data.get("primary_keyword", ""),
        secondary_keywords=seo_data.get("secondary_keywords", []),
        long_tail_keywords=seo_data.get("long_tail_keywords", []),
        recommended_title=seo_data.get("recommended_title", ""),
        meta_description=seo_data.get("meta_description", ""),
        supporting_content=seo_data.get("supporting_content", []),
    )

    # Services
    services = []
    for s in analysis_data.get("top_services", []):
        services.append(Service(
            service_name=s.get("service_name", ""),
            description=s.get("description", ""),
            target_industry=s.get("target_industry", ""),
            target_customer=s.get("target_customer", ""),
            main_benefit=s.get("main_benefit", ""),
        ))

    # Audience
    aud_data = analysis_data.get("target_audience", {})
    audience = TargetAudience(
        primary_audience=aud_data.get("primary_audience", []),
        secondary_audience=aud_data.get("secondary_audience", []),
        industries=aud_data.get("industries", []),
        business_types=aud_data.get("business_types", []),
        customer_profiles=aud_data.get("customer_profiles", []),
        geographical_focus=aud_data.get("geographical_focus"),
        customer_needs=aud_data.get("customer_needs", []),
        potential_interests=aud_data.get("potential_interests", []),
        recommended_segments=aud_data.get("recommended_segments", []),
    )

    return AnalysisResponse(
        success=True,
        website=url,
        brand=brand,
        analysis=Analysis(
            competitor_analysis=competitor_analysis,
            target_search_queries=queries,
            seo_improvements=seo,
            top_services=services,
            target_audience=audience,
        ),
    )


async def run_full_analysis(url: str) -> AnalysisResponse:
    settings = get_settings()

    # 1. Extract website content
    content = await extract_website_content(
        url,
        timeout=settings.request_timeout,
        max_length=settings.max_content_length,
    )

    # 2. Build a compact summary for the LLM
    summary = build_content_summary(content)

    # 3. Run LLM analysis
    raw_result = await run_llm_analysis(summary)

    # 4. Parse and validate
    return _parse_response(url, raw_result)
