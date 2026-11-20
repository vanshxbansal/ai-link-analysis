from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

ALLOWED_PLATFORMS = ["Google", "Facebook", "Instagram", "LinkedIn", "X"]

_PLATFORM_ALIASES = {
    "google": "Google",
    "google search": "Google",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "linkedin": "LinkedIn",
    "x": "X",
    "twitter": "X",
    "x (twitter)": "X",
    "twitter (x)": "X",
    "x/twitter": "X",
}


class _Lenient(BaseModel):
    """Base model that tolerates extra keys returned by the LLM."""

    model_config = {"extra": "ignore"}


# ---------- Request ----------


class AnalysisRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, description="Public website URL to analyze")

    model_config = {"json_schema_extra": {"example": {"url": "https://example.com"}}}


# ---------- Section 0: Brand ----------


class BrandInfo(_Lenient):
    name: str = "Unknown"
    category: str = "Unknown"
    summary: str = ""
    target_market: str = ""


# ---------- Section 1: Competitor analysis ----------


class Competitor(_Lenient):
    name: str = "Unknown"
    website: Optional[str] = None
    overview: str = ""
    main_service: str = ""
    target_market: str = ""
    strengths: List[str] = []
    weaknesses: List[str] = []
    source: str = "AI-generated suggestion (based on model knowledge; verify before use)"


class ComparisonRow(_Lenient):
    aspect: str
    your_brand: str = ""
    competitors: dict = {}


class CompetitorAnalysis(_Lenient):
    brand_name: str = ""
    brand_overview: str = ""
    main_category: str = ""
    main_products_services: List[str] = []
    competitive_advantages: List[str] = []
    competitors: List[Competitor] = []
    competitor_gaps: List[str] = []
    opportunities: List[str] = []
    comparison_table: List[ComparisonRow] = []
    disclaimer: str = (
        "Competitors are identified by the LLM from the website's category and its general "
        "market knowledge. They are AI-generated suggestions and should be verified."
    )


# ---------- Section 2: Search queries ----------


class SearchQuery(_Lenient):
    query: str
    platforms: List[str] = []
    intent: str = ""
    business_relevance: str = ""
    target_audience: str = ""

    @field_validator("platforms", mode="before")
    @classmethod
    def normalize_platforms(cls, value):
        if isinstance(value, str):
            value = [value]
        out = []
        for p in value or []:
            name = _PLATFORM_ALIASES.get(str(p).strip().lower())
            if name and name not in out:
                out.append(name)
        return out


# ---------- Section 3: SEO ----------


class SEOImprovements(_Lenient):
    current_title: str = ""
    current_meta_description: str = ""
    primary_keyword: str = ""
    secondary_keywords: List[str] = []
    long_tail_keywords: List[str] = []
    business_keywords: List[str] = []
    recommended_title: str = ""
    title_rationale: str = ""
    meta_description: str = ""
    supporting_content: List[str] = []
    technical_notes: List[str] = []
    note: str = "No search volume data is included; keywords are recommendations, not measured rankings."


# ---------- Section 4: Services ----------


class Service(_Lenient):
    service_name: str
    description: str = ""
    target_industry: str = ""
    target_customer: str = ""
    main_benefit: str = ""
    source: Literal["website_content", "inferred"] = "website_content"

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value):
        return "inferred" if str(value or "").strip().lower().startswith("infer") else "website_content"


# ---------- Section 5: Audience ----------


class AudienceSegment(_Lenient):
    audience: str
    business_type: str = ""
    requirement: str = ""


class TargetAudience(_Lenient):
    primary_audience: List[str] = []
    secondary_audience: List[str] = []
    industries: List[str] = []
    business_types: List[str] = []
    customer_profiles: List[str] = []
    geographical_focus: Optional[str] = None
    customer_needs: List[str] = []
    customer_challenges: List[str] = []
    potential_interests: List[str] = []
    recommended_segments: List[str] = []
    audience_segments: List[AudienceSegment] = []


# ---------- Envelope ----------


class Analysis(_Lenient):
    competitor_analysis: CompetitorAnalysis = CompetitorAnalysis()
    target_search_queries: List[SearchQuery] = []
    seo_improvements: SEOImprovements = SEOImprovements()
    top_services: List[Service] = []
    target_audience: TargetAudience = TargetAudience()


class LLMOutput(_Lenient):
    """Shape the LLM is asked to return; validated before building the API response."""

    brand: BrandInfo = BrandInfo()
    analysis: Analysis = Analysis()


class AnalysisMeta(BaseModel):
    provider: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    llm_latency_ms: int
    total_latency_ms: int
    pages_analyzed: int
    content_chars_sent: int
    cached: bool = False


class AnalysisResponse(BaseModel):
    success: bool = True
    website: str
    brand: BrandInfo
    analysis: Analysis
    meta: Optional[AnalysisMeta] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
