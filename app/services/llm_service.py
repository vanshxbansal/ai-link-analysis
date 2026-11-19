import json
import re
import httpx
from app.config import get_settings

GEMINI_REST_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-flash-lite-latest:generateContent"
)

ANALYSIS_PROMPT = """You are an expert business analyst and SEO specialist. Analyze the following website content and return a comprehensive JSON analysis.

WEBSITE CONTENT:
{content}

Return ONLY valid JSON with this exact structure (no markdown, no explanation):

{{
  "brand": {{
    "name": "Brand name extracted from the website",
    "category": "Main business category",
    "summary": "2-3 sentence business overview"
  }},
  "analysis": {{
    "competitor_analysis": {{
      "brand_overview": "Detailed overview of this brand",
      "main_products_services": ["service1", "service2", "service3"],
      "competitive_advantages": ["advantage1", "advantage2"],
      "competitors": [
        {{
          "name": "Competitor name",
          "overview": "Brief competitor overview",
          "strengths": ["strength1", "strength2"],
          "weaknesses": ["weakness1", "weakness2"]
        }}
      ],
      "opportunities": ["opportunity1", "opportunity2"]
    }},
    "target_search_queries": [
      {{
        "query": "search query text",
        "platforms": ["Google", "LinkedIn"],
        "intent": "Service Discovery",
        "business_relevance": "Why this query matters for the business",
        "target_audience": "Who would search this"
      }}
    ],
    "seo_improvements": {{
      "primary_keyword": "main keyword",
      "secondary_keywords": ["keyword2", "keyword3"],
      "long_tail_keywords": ["long tail keyword 1", "long tail keyword 2"],
      "recommended_title": "Optimized SEO title under 60 characters",
      "meta_description": "Optimized meta description under 160 characters",
      "supporting_content": ["Blog topic 1", "FAQ page suggestion", "Landing page idea"]
    }},
    "top_services": [
      {{
        "service_name": "Service name",
        "description": "Short description of the service",
        "target_industry": "Relevant industry",
        "target_customer": "Type of customer",
        "main_benefit": "Primary benefit for customers"
      }}
    ],
    "target_audience": {{
      "primary_audience": ["Primary audience segment 1", "Primary audience segment 2"],
      "secondary_audience": ["Secondary audience segment 1"],
      "industries": ["Industry 1", "Industry 2"],
      "business_types": ["Small businesses", "Enterprises"],
      "customer_profiles": ["Profile 1", "Profile 2"],
      "geographical_focus": "Location if identifiable, else null",
      "customer_needs": ["Need 1", "Need 2"],
      "potential_interests": ["Interest 1", "Interest 2"],
      "recommended_segments": ["Segment 1 for marketing", "Segment 2 for marketing"]
    }}
  }}
}}

Rules:
- Include exactly 3-5 real competitors based on the business type
- Include exactly 5 target_search_queries covering Google, Facebook, Instagram, LinkedIn, X
- Include exactly 5 top_services
- Base everything strictly on the website content provided
- Do not invent search volumes or ranking data
- Competitor info should be clearly labeled as AI-generated suggestions
- Return only valid JSON, nothing else
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()
    return json.loads(text)


async def analyze_with_gemini(content_summary: str) -> dict:
    settings = get_settings()

    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    prompt = ANALYSIS_PROMPT.format(content=content_summary)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            GEMINI_REST_URL,
            params={"key": settings.gemini_api_key},
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return _extract_json(raw_text)


async def run_llm_analysis(content_summary: str) -> dict:
    return await analyze_with_gemini(content_summary)
