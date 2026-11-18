from pydantic import BaseModel, HttpUrl
from typing import Optional


class AnalysisRequest(BaseModel):
    url: str

    model_config = {"json_schema_extra": {"example": {"url": "https://example.com"}}}


class BrandInfo(BaseModel):
    name: str
    category: str
    summary: str


class Competitor(BaseModel):
    name: str
    overview: str
    strengths: list[str]
    weaknesses: list[str]


class CompetitorAnalysis(BaseModel):
    brand_overview: str
    main_products_services: list[str]
    competitive_advantages: list[str]
    competitors: list[Competitor]
    opportunities: list[str]


class SearchQuery(BaseModel):
    query: str
    platforms: list[str]
    intent: str
    business_relevance: str
    target_audience: str


class SEOImprovements(BaseModel):
    primary_keyword: str
    secondary_keywords: list[str]
    long_tail_keywords: list[str]
    recommended_title: str
    meta_description: str
    supporting_content: list[str]


class Service(BaseModel):
    service_name: str
    description: str
    target_industry: str
    target_customer: str
    main_benefit: str


class TargetAudience(BaseModel):
    primary_audience: list[str]
    secondary_audience: list[str]
    industries: list[str]
    business_types: list[str]
    customer_profiles: list[str]
    geographical_focus: Optional[str] = None
    customer_needs: list[str]
    potential_interests: list[str]
    recommended_segments: list[str]


class Analysis(BaseModel):
    competitor_analysis: CompetitorAnalysis
    target_search_queries: list[SearchQuery]
    seo_improvements: SEOImprovements
    top_services: list[Service]
    target_audience: TargetAudience


class AnalysisResponse(BaseModel):
    success: bool
    website: str
    brand: BrandInfo
    analysis: Analysis


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
