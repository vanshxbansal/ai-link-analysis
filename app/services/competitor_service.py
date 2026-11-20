"""Post-processing for competitor analysis returned by the LLM."""

from typing import List

from app.schemas import ComparisonRow, Competitor, CompetitorAnalysis

AI_SOURCE_LABEL = "AI-generated suggestion (based on model knowledge; verify before use)"


def clean_competitors(competitors: List[Competitor], brand_name: str, limit: int = 5) -> List[Competitor]:
    """Remove duplicates and the brand itself, and label every entry as AI-generated."""
    brand_key = (brand_name or "").strip().lower()
    seen = set()
    result = []
    for c in competitors:
        key = c.name.strip().lower()
        if not key or key in ("unknown", brand_key) or key in seen:
            continue
        seen.add(key)
        result.append(c.model_copy(update={"source": AI_SOURCE_LABEL}))
    return result[:limit]


def summarize_competitor_gaps(competitors: List[Competitor]) -> List[str]:
    """Unique weaknesses/gaps across all competitors (market gaps the brand can exploit)."""
    gaps = []
    seen = set()
    for c in competitors:
        for w in c.weaknesses:
            key = w.lower().strip()
            if key and key not in seen:
                seen.add(key)
                gaps.append(f"{c.name}: {w}")
    return gaps


def build_comparison_table(analysis: CompetitorAnalysis, target_market: str) -> List[ComparisonRow]:
    """Build a Brand-vs-Competitor table if the LLM did not return a usable one."""
    comps = analysis.competitors
    main_service = analysis.main_products_services[0] if analysis.main_products_services else ""
    strength = analysis.competitive_advantages[0] if analysis.competitive_advantages else ""
    opportunity = analysis.opportunities[0] if analysis.opportunities else ""
    return [
        ComparisonRow(aspect="Brand Name", your_brand=analysis.brand_name, competitors={c.name: c.name for c in comps}),
        ComparisonRow(aspect="Main Service", your_brand=main_service, competitors={c.name: c.main_service for c in comps}),
        ComparisonRow(aspect="Target Market", your_brand=target_market, competitors={c.name: c.target_market for c in comps}),
        ComparisonRow(
            aspect="Key Strength",
            your_brand=strength,
            competitors={c.name: (c.strengths[0] if c.strengths else "") for c in comps},
        ),
        ComparisonRow(
            aspect="Weakness / Gap",
            your_brand="",
            competitors={c.name: (c.weaknesses[0] if c.weaknesses else "") for c in comps},
        ),
        ComparisonRow(aspect="Opportunity", your_brand=opportunity, competitors={}),
    ]


def finalize_competitor_analysis(analysis: CompetitorAnalysis, brand_name: str, target_market: str) -> CompetitorAnalysis:
    competitors = clean_competitors(analysis.competitors, brand_name)
    updated = analysis.model_copy(
        update={
            "brand_name": analysis.brand_name or brand_name,
            "competitors": competitors,
            "competitor_gaps": summarize_competitor_gaps(competitors),
        }
    )
    names = {c.name for c in competitors}
    table_ok = any(set(row.competitors) & names for row in updated.comparison_table)
    if competitors and not table_ok:
        updated = updated.model_copy(update={"comparison_table": build_comparison_table(updated, target_market)})
    return updated
