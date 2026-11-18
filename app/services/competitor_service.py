"""
Helper utilities for competitor-related processing.
Competitors are identified by the LLM based on website content.
This module provides supplementary utilities for post-processing.
"""

from app.schemas import Competitor


def label_ai_competitors(competitors: list[Competitor]) -> list[dict]:
    """Add an AI-generated label to each competitor entry."""
    result = []
    for c in competitors:
        entry = c.model_dump()
        entry["source"] = "AI-generated suggestion based on business category"
        result.append(entry)
    return result


def summarize_competitor_gaps(competitors: list[Competitor]) -> list[str]:
    """Extract unique weaknesses/gaps across all competitors."""
    gaps = []
    seen = set()
    for c in competitors:
        for w in c.weaknesses:
            key = w.lower().strip()
            if key not in seen:
                seen.add(key)
                gaps.append(w)
    return gaps
