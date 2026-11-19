# AI-Powered Website Link Analysis API

A FastAPI application that analyzes a website URL using an LLM and returns structured business, competitor, SEO, search query, and target audience insights.

## Features

- **Competitor Analysis** – Identifies competitors and compares strengths, weaknesses, and market opportunities
- **Target Search Queries** – Generates 5 platform-specific search queries (Google, Facebook, Instagram, LinkedIn, X)
- **SEO Improvements** – Recommends keywords, title, meta description, and supporting content ideas
- **Top 5 Services** – Extracts the most important services from the website
- **Target Audience** – Identifies primary/secondary audiences, industries, and customer profiles
- **SSRF Protection** – Blocks requests to localhost, private IPs, and internal network addresses
- **Graceful Error Handling** – Handles inaccessible websites, timeouts, and invalid URLs

---

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI |
| Server | Uvicorn |
| Validation | Pydantic v2 |
| HTTP Client | HTTPX (async) |
| HTML Parsing | BeautifulSoup4 + lxml |
| LLM | Google Gemini 2.5 Flash |
| Config | python-dotenv + pydantic-settings |
| Testing | pytest |

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- A [Google Gemini API key](https://aistudio.google.com/app/apikey) (free tier available)

### 1. Clone the repository

```bash
git clone https://github.com/vanshxbansal/ai-link-analysis.git
cd ai-link-analysis
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

The API will be available at `http://localhost:4000`  
API documentation: `http://localhost:4000/docs`

---

## API Usage

### Endpoint

```
POST /link-analysis
```

### Request

```bash
curl -X POST http://localhost:4000/link-analysis \
  -H "Content-Type: application/json" \
  -d '{"url": "https://stripe.com"}'
```

### Sample Response

```json
{
  "success": true,
  "website": "https://stripe.com",
  "brand": {
    "name": "Stripe",
    "category": "Financial Technology (FinTech)",
    "summary": "Stripe is a global payments infrastructure platform that enables businesses of all sizes to accept payments online and in-person, manage subscriptions, and build financial products."
  },
  "analysis": {
    "competitor_analysis": {
      "brand_overview": "Stripe provides developer-focused payment processing APIs and financial tools trusted by millions of businesses worldwide.",
      "main_products_services": [
        "Payment Processing",
        "Billing & Subscriptions",
        "Connect (marketplace payments)",
        "Radar (fraud detection)",
        "Issuing (card creation)"
      ],
      "competitive_advantages": [
        "Best-in-class developer documentation",
        "Comprehensive API ecosystem",
        "Global currency and payment method support"
      ],
      "competitors": [
        {
          "name": "PayPal",
          "overview": "Established digital payments platform with broad consumer recognition",
          "strengths": ["High consumer trust", "Wide merchant adoption"],
          "weaknesses": ["Less developer-friendly", "Higher fees for small businesses"]
        },
        {
          "name": "Braintree",
          "overview": "PayPal-owned payment gateway targeting developers",
          "strengths": ["Competitive pricing", "Good developer tools"],
          "weaknesses": ["Less innovation than Stripe", "Limited advanced features"]
        },
        {
          "name": "Square",
          "overview": "POS and payment platform focused on small businesses",
          "strengths": ["Strong in-person payments", "Easy setup"],
          "weaknesses": ["Limited international support", "Less suited for complex integrations"]
        }
      ],
      "opportunities": [
        "Expand into emerging markets with local payment methods",
        "Grow the financial services ecosystem beyond payments"
      ]
    },
    "target_search_queries": [
      {
        "query": "best payment gateway for startups",
        "platforms": ["Google"],
        "intent": "Service Discovery",
        "business_relevance": "Directly targets Stripe's core customer segment",
        "target_audience": "Startup founders and CTOs"
      },
      {
        "query": "online payment processing for small business",
        "platforms": ["Facebook"],
        "intent": "Business Discovery",
        "business_relevance": "High volume SMB search term",
        "target_audience": "Small business owners"
      },
      {
        "query": "accept payments on website",
        "platforms": ["Instagram"],
        "intent": "How-to Search",
        "business_relevance": "Top-of-funnel awareness for new businesses",
        "target_audience": "New entrepreneurs and creators"
      },
      {
        "query": "stripe payment integration for saas",
        "platforms": ["LinkedIn"],
        "intent": "B2B Technical Search",
        "business_relevance": "High-intent B2B developer and CTO audience",
        "target_audience": "SaaS developers and product managers"
      },
      {
        "query": "stripe vs paypal developer experience",
        "platforms": ["X"],
        "intent": "Comparison / Research",
        "business_relevance": "Captures switching intent from competitors",
        "target_audience": "Developers and technical decision-makers"
      }
    ],
    "seo_improvements": {
      "primary_keyword": "online payment processing",
      "secondary_keywords": ["payment gateway", "accept credit cards online", "subscription billing"],
      "long_tail_keywords": [
        "best payment gateway for e-commerce startups",
        "how to integrate stripe payment in website",
        "stripe recurring billing for saas"
      ],
      "recommended_title": "Stripe | Online Payment Processing for Businesses",
      "meta_description": "Accept payments online with Stripe. Fast, secure payment processing with developer-friendly APIs for businesses of all sizes.",
      "supporting_content": [
        "Blog: How to Choose the Right Payment Gateway for Your Startup",
        "FAQ: What are Stripe's transaction fees?",
        "Landing page: Stripe for SaaS Businesses",
        "Landing page: Stripe for E-commerce",
        "Article: Stripe vs PayPal – A Developer's Comparison",
        "Guide: Setting Up Subscription Billing with Stripe"
      ]
    },
    "top_services": [
      {
        "service_name": "Payment Processing",
        "description": "Accept cards, wallets, and local payment methods globally",
        "target_industry": "All industries",
        "target_customer": "Businesses needing to accept online payments",
        "main_benefit": "Fast, reliable global payment acceptance"
      },
      {
        "service_name": "Stripe Billing",
        "description": "Subscription and recurring revenue management",
        "target_industry": "SaaS, Media, Services",
        "target_customer": "Businesses with subscription revenue models",
        "main_benefit": "Automate billing and reduce churn"
      },
      {
        "service_name": "Stripe Connect",
        "description": "Payments infrastructure for platforms and marketplaces",
        "target_industry": "Marketplaces, Platforms",
        "target_customer": "Platform builders and marketplace operators",
        "main_benefit": "Split payments and onboard sellers at scale"
      },
      {
        "service_name": "Stripe Radar",
        "description": "Machine learning-powered fraud detection",
        "target_industry": "E-commerce, FinTech",
        "target_customer": "Businesses with high-volume transactions",
        "main_benefit": "Reduce fraud while approving more legitimate payments"
      },
      {
        "service_name": "Stripe Issuing",
        "description": "Create and manage physical and virtual cards",
        "target_industry": "FinTech, Enterprise",
        "target_customer": "Businesses building card programs",
        "main_benefit": "Launch card products without banking infrastructure"
      }
    ],
    "target_audience": {
      "primary_audience": ["Software developers and engineers", "SaaS founders and CTOs"],
      "secondary_audience": ["E-commerce business owners", "Marketplace operators"],
      "industries": ["Technology", "E-commerce", "FinTech", "SaaS", "Marketplaces"],
      "business_types": ["Startups", "SMBs", "Enterprise", "Platforms"],
      "customer_profiles": ["Developer-led companies", "High-growth startups", "Global enterprise businesses"],
      "geographical_focus": "Global",
      "customer_needs": ["Reliable payment acceptance", "Developer-friendly APIs", "Global currency support"],
      "potential_interests": ["API integrations", "Financial automation", "Subscription management"],
      "recommended_segments": [
        "SaaS founders aged 25-45 building B2B products",
        "E-commerce operators with 100+ monthly transactions",
        "Platform builders in gig economy and marketplaces"
      ]
    }
  }
}
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## LLM Platform Research & Recommendation

### A. LLM Comparison Table

| Criteria | Google Gemini 2.5 Flash | OpenAI GPT-4o Mini | Anthropic Claude 3 Haiku |
|---|---|---|---|
| **Provider** | Google DeepMind | OpenAI | Anthropic |
| **Model** | gemini-2.5-flash | gpt-4o-mini | claude-3-haiku-20240307 |
| **Input Cost** | $0.075 / 1M tokens | $0.15 / 1M tokens | $0.25 / 1M tokens |
| **Output Cost** | $0.30 / 1M tokens | $0.60 / 1M tokens | $1.25 / 1M tokens |
| **Context Window** | 1,000,000 tokens | 128,000 tokens | 200,000 tokens |
| **Response Speed** | ~2–4 seconds | ~3–6 seconds | ~3–5 seconds |
| **JSON Support** | Native (response_mime_type) | Yes (response_format) | Yes (tool use) |
| **Website Content Accuracy** | Excellent | Very Good | Very Good |
| **Recommendation** | **Best choice** | Good fallback | Higher cost |

> Pricing based on publicly available provider documentation (Nov 2024). Response times are estimates based on typical API latency for ~2,000-token outputs.

### B. Final LLM Recommendation

| Field | Details |
|---|---|
| **Recommended Provider** | Google (Gemini) |
| **Recommended Model** | `gemini-2.5-flash` |
| **Estimated Input Tokens** | ~3,000–5,000 tokens per analysis |
| **Estimated Output Tokens** | ~1,500–2,500 tokens per analysis |
| **Estimated Cost per Analysis** | ~$0.001–$0.002 USD |
| **Expected Response Time** | 3–6 seconds |
| **Fallback Model** | OpenAI `gpt-4o-mini` |

**Why Gemini 2.5 Flash:**
- **Lowest cost** among capable models (~2x cheaper than GPT-4o Mini for this use case)
- **Largest context window** (1M tokens) handles full website content without truncation
- **Native JSON output** via `response_mime_type="application/json"` eliminates parsing errors
- **Fast inference** with minimal latency for structured generation tasks
- **Generous free tier** via Google AI Studio for development and testing

### C. Cost Optimization Strategies Applied

1. **Content trimming** – HTML is stripped of scripts, styles, navigation, and footers before sending to the LLM
2. **Text truncation** – Main content is capped at 8,000 characters in the LLM prompt; full extraction is capped at 50,000 characters
3. **Heading extraction** – Only the top 20 headings are passed instead of full DOM
4. **Single-call analysis** – All 5 sections are generated in one LLM call instead of 5 separate calls (saves ~80% on API costs)
5. **Low temperature** – Temperature set to 0.3 to reduce token wastage from verbose outputs
6. **Prompt optimization** – Prompt is structured to enforce concise, structured JSON output

---

## Project Structure

```
ai-link-analysis/
├── app/
│   ├── main.py                    # FastAPI app and routes
│   ├── config.py                  # Settings via pydantic-settings
│   ├── schemas.py                 # Pydantic request/response models
│   ├── services/
│   │   ├── website_extractor.py   # Fetches and parses website HTML
│   │   ├── llm_service.py         # Gemini LLM integration
│   │   ├── analysis_service.py    # Orchestrates full analysis pipeline
│   │   └── competitor_service.py  # Competitor post-processing utilities
│   └── utils/
│       └── validators.py          # URL validation + SSRF protection
├── tests/
│   └── test_link_analysis.py      # Unit and integration tests
├── .env.example                   # Environment variable template
├── requirements.txt
└── README.md
```

---

## Security

- All URLs are validated before making outbound requests
- SSRF protection blocks requests to `localhost`, `127.0.0.1`, `169.254.x.x`, and all RFC-1918 private IP ranges
- API keys are loaded from environment variables and never committed to the repository
- Input URLs are sanitized and normalized before processing

---

## Error Handling

| Scenario | HTTP Status | Response |
|---|---|---|
| Invalid or missing URL | 400 | `{"success": false, "error": "..."}` |
| Private/localhost URL | 400 | `{"success": false, "error": "Access not allowed"}` |
| Website timeout | 400 | Timeout message |
| Website returns 4xx/5xx | 400 | HTTP status message |
| LLM API key not configured | 400 | Config error message |
| Unexpected server error | 500 | Generic error message |
