# AI-Powered Website Link Analysis API

A FastAPI service that takes a website URL, extracts and cleans its content (homepage plus key About/Services/Products pages), and uses an LLM to produce a structured JSON analysis with five sections:

1. **Competitor vs Your Brand**: brand overview, category, products/services, 3-5 competitors with strengths/weaknesses, competitive advantages, market gaps, positioning opportunities, and a Brand-vs-Competitor comparison table
2. **Top 5 Target Search Queries**: one query per platform (Google, Facebook, Instagram, LinkedIn, X), each with intent, business relevance and target audience
3. **SEO Improvements**: primary/secondary/long-tail/business keywords, a rewritten SEO title and meta description (shown next to the current ones), technical notes, and supporting content ideas
4. **Top 5 Services**: name, description, target industry, target customer, main benefit, and whether each one was **stated on the website** or **inferred**
5. **Target Audience**: primary/secondary audiences, industries, business types, customer profiles, geography, needs, challenges, interests, and recommended marketing segments

---

## Contents

- [Tech stack](#tech-stack)
- [How it works](#how-it-works)
- [Setup and running locally](#setup-and-running-locally)
- [API usage](#api-usage)
- [Error handling](#error-handling)
- [Testing](#testing)
- [LLM platform research and recommendation](#llm-platform-research-and-recommendation)
- [Deployment](#deployment)
- [Security](#security)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)

---

## Tech stack

| Component | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Validation | Pydantic v2, pydantic-settings |
| HTTP client | HTTPX (async, streaming, manual redirect handling) |
| HTML parsing | BeautifulSoup4 + lxml |
| LLM | Google Gemini `gemini-3.1-flash-lite` (primary), `gemini-3.5-flash-lite` (fallback), optional OpenAI fallback |
| Tests | pytest (39 tests, fully offline) |

---

## How it works

```
POST /link-analysis {"url": ...}
        │
        ▼
1. Validate URL ── scheme, port, credentials, DNS → every resolved IP must be public (SSRF)
        │
        ▼
2. Fetch HTML ── redirects followed manually, each hop re-validated; 3 MB cap; HTML-only
        │
        ▼
3. Extract ── title, meta, og:site_name, JSON-LD (Organization/Service), nav labels,
              H1-H3, main text (scripts/styles/header/footer/nav removed, lines de-duplicated)
        │
        ├── + up to 2 key internal pages (about / services / products / pricing) fetched in parallel
        ▼
4. Build compact prompt ── ~12k chars (~3.2k tokens) with a fixed budget per page
        │
        ▼
5. LLM (single call, JSON schema-constrained output)
   gemini-3.1-flash-lite ─(retry on 429/5xx/invalid JSON)→ gemini-3.5-flash-lite ─→ OpenAI (optional)
        │
        ▼
6. Validate with Pydantic + post-process
   (dedupe competitors, remove the brand itself, label as AI-generated, enforce 5 queries
    covering all 5 platforms, normalise platform names, add current title/meta for comparison)
        │
        ▼
7. Cache (in-memory TTL, 1 h) → JSON response with `meta` (model, tokens, cost, latency)
```

---

## Setup and running locally

**Requirements:** Python 3.9+ and a Google Gemini API key ([Google AI Studio](https://aistudio.google.com/app/apikey)).

```bash
git clone https://github.com/vanshxbansal/ai-link-analysis.git
cd ai-link-analysis

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # then set GEMINI_API_KEY in .env

uvicorn app.main:app --host 0.0.0.0 --port 4000
```

- API: `http://localhost:4000/link-analysis`
- Interactive docs (Swagger): `http://localhost:4000/docs`
- Health check: `http://localhost:4000/health`

### Configuration (`.env`)

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | (none) | Required for the default provider |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` | Primary model |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.5-flash-lite` | Used when the primary model fails or is overloaded |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | empty / `gpt-5.4-mini` | Optional last-resort fallback provider |
| `REQUEST_TIMEOUT` | `20` | Website fetch timeout (s) |
| `MAX_LLM_CONTENT_CHARS` | `12000` | Content budget sent to the LLM |
| `MAX_EXTRA_PAGES` | `2` | Extra internal pages to read (0 disables) |
| `CACHE_TTL_SECONDS` | `3600` | How long an analysis is reused |

---

## API usage

### Request

```bash
curl -X POST http://localhost:4000/link-analysis \
  -H "Content-Type: application/json" \
  -d '{"url": "https://stripe.com"}'
```

Add `?refresh=true` to bypass the cache.

### Response (real output, shortened)

Full, unedited responses captured from local runs:
[docs/sample_response_stripe.json](docs/sample_response_stripe.json) and [docs/sample_response_shopify.json](docs/sample_response_shopify.json).

```json
{
  "success": true,
  "website": "https://stripe.com",
  "brand": {
    "name": "Stripe",
    "category": "Financial Infrastructure and Payment Processing",
    "summary": "Stripe provides a comprehensive suite of financial tools and APIs that enable businesses of all sizes to accept payments, manage billing, and handle money movement globally. The platform offers flexible, scalable infrastructure designed to support both online and in-person commerce, including advanced fraud protection and revenue management.",
    "target_market": "Global businesses ranging from startups to large enterprises, including SaaS, e-commerce, and platform-based companies."
  },
  "analysis": {
    "competitor_analysis": {
      "brand_name": "Stripe",
      "brand_overview": "A leading financial technology company providing payment processing software and application programming interfaces for e-commerce websites and mobile applications.",
      "main_category": "Payment Service Provider (PSP)",
      "main_products_services": [
        "Online Payment Processing",
        "Stripe Billing",
        "Stripe Connect",
        "Stripe Terminal",
        "Stripe Radar (Fraud Protection)"
      ],
      "competitive_advantages": [
        "High developer-centricity with robust APIs",
        "Global reach with 135+ currencies",
        "High platform reliability (99.999% uptime)",
        "Integrated ecosystem for billing, tax, and risk"
      ],
      "competitors": [
        {
          "name": "PayPal",
          "website": "paypal.com",
          "overview": "A global leader in online payment systems and digital wallets.",
          "main_service": "Consumer and merchant payment processing",
          "target_market": "Mass market consumers and SMEs",
          "strengths": [
            "High brand recognition",
            "Strong consumer trust"
          ],
          "weaknesses": [
            "Higher fees for some merchants",
            "Less developer-friendly"
          ],
          "source": "AI-generated suggestion (based on model knowledge; verify before use)"
        },
        {
          "name": "Adyen",
          "website": "adyen.com",
          "overview": "A global payment platform providing end-to-end infrastructure for large enterprises.",
          "main_service": "Enterprise payment processing",
          "target_market": "Large global enterprises",
          "strengths": [
            "Unified platform",
            "Strong enterprise focus"
          ],
          "weaknesses": [
            "Higher barrier to entry for small businesses"
          ],
          "source": "AI-generated suggestion (based on model knowledge; verify before use)"
        },
        "... (more competitors)"
      ],
      "competitor_gaps": [
        "PayPal: Higher fees for some merchants",
        "PayPal: Less developer-friendly",
        "..."
      ],
      "opportunities": [
        "Expand deeper into emerging market local payment methods",
        "Enhance AI-driven financial advisory tools for SMBs",
        "Strengthen presence in the creator economy sector"
      ],
      "comparison_table": [
        {
          "aspect": "Brand Name",
          "your_brand": "Stripe",
          "competitors": {
            "PayPal": "PayPal",
            "Adyen": "Adyen",
            "Razorpay": "Razorpay"
          }
        },
        {
          "aspect": "Main Service",
          "your_brand": "Online Payment Processing",
          "competitors": {
            "PayPal": "Consumer and merchant payment processing",
            "Adyen": "Enterprise payment processing",
            "Razorpay": "Payment gateway and financial services"
          }
        },
        "..."
      ],
      "disclaimer": "Competitors are identified by the LLM from the website's category and its general market knowledge. They are AI-generated suggestions and should be verified."
    },
    "target_search_queries": [
      {
        "query": "best payment gateway for online business",
        "platforms": [
          "Google"
        ],
        "intent": "Commercial investigation",
        "business_relevance": "High",
        "target_audience": "Business owners"
      },
      {
        "query": "how to accept international payments on my website",
        "platforms": [
          "Facebook"
        ],
        "intent": "Informational",
        "business_relevance": "High",
        "target_audience": "E-commerce entrepreneurs"
      },
      {
        "query": "modern payment solutions for startups",
        "platforms": [
          "Instagram"
        ],
        "intent": "Brand awareness",
        "business_relevance": "Medium",
        "target_audience": "Startup founders"
      },
      {
        "query": "enterprise payment infrastructure for global scale",
        "platforms": [
          "LinkedIn"
        ],
        "intent": "Commercial",
        "business_relevance": "High",
        "target_audience": "CTOs and CFOs"
      },
      {
        "query": "Stripe vs competitors for recurring billing",
        "platforms": [
          "X"
        ],
        "intent": "Comparison",
        "business_relevance": "High",
        "target_audience": "Developers and Product Managers"
      }
    ],
    "seo_improvements": {
      "current_title": "Stripe | Financial Infrastructure to Grow Your Revenue",
      "current_meta_description": "Stripe is a financial services platform that helps all types of businesses accept payments, build flexible billing models and manage money movement.",
      "primary_keyword": "financial infrastructure",
      "secondary_keywords": [
        "payment processing",
        "online billing",
        "global payments"
      ],
      "long_tail_keywords": [
        "how to accept payments online",
        "payment gateway for startups"
      ],
      "business_keywords": [
        "revenue growth",
        "payment optimization"
      ],
      "recommended_title": "Stripe: Global Financial Infrastructure for Online Payments",
      "title_rationale": "Added 'Global' and 'Online Payments' to improve search relevance while maintaining brand identity.",
      "meta_description": "Scale your business with Stripe's financial infrastructure. Accept global payments, manage recurring billing, and optimize revenue with our developer-friendly tools.",
      "supporting_content": [
        "Service landing page: Global Payment Processing",
        "FAQ: How to integrate Stripe APIs",
        "Blog: Scaling your revenue with AI",
        "Location page: Stripe India Payment Solutions"
      ],
      "technical_notes": [
        "The current meta description is descriptive but lacks a strong call to action.",
        "Headings are well-structured but could benefit from more keyword-rich H2 tags.",
        "Ensure all images have descriptive alt text for accessibility and SEO."
      ],
      "note": "No search volume data is included; keywords are recommendations, not measured rankings."
    },
    "top_services": [
      {
        "service_name": "Online Payment Processing",
        "description": "Accept payments globally via 125+ payment methods.",
        "target_industry": "E-commerce",
        "target_customer": "Online merchants",
        "main_benefit": "Increased conversion rates",
        "source": "website_content"
      },
      {
        "service_name": "Stripe Billing",
        "description": "Flexible subscription and recurring billing management.",
        "target_industry": "SaaS",
        "target_customer": "Subscription-based businesses",
        "main_benefit": "Automated revenue collection",
        "source": "website_content"
      },
      "... (5 total)"
    ],
    "target_audience": {
      "primary_audience": [
        "Software Developers",
        "Startup Founders",
        "E-commerce Business Owners"
      ],
      "secondary_audience": [
        "CFOs",
        "Product Managers",
        "Platform Operators"
      ],
      "industries": [
        "SaaS",
        "E-commerce",
        "Marketplaces",
        "Fintech"
      ],
      "business_types": [
        "SMBs",
        "Enterprises",
        "Startups"
      ],
      "customer_profiles": [
        "Tech-savvy decision makers",
        "Growth-focused entrepreneurs"
      ],
      "geographical_focus": "Global",
      "customer_needs": [
        "Reliable payment processing",
        "Easy API integration",
        "Fraud prevention"
      ],
      "customer_challenges": [
        "High operational overhead",
        "Complex global regulations"
      ],
      "potential_interests": [
        "Digital transformation",
        "AI in commerce"
      ],
      "recommended_segments": [
        "High-growth SaaS",
        "Global Marketplaces"
      ],
      "audience_segments": [
        {
          "audience": "Developers",
          "business_type": "Tech Companies",
          "requirement": "Clean, well-documented APIs"
        },
        {
          "audience": "Founders",
          "business_type": "Startups",
          "requirement": "Fast incorporation and payment setup"
        }
      ]
    }
  },
  "meta": {
    "provider": "gemini",
    "model": "gemini-3.1-flash-lite",
    "input_tokens": 3809,
    "output_tokens": 2155,
    "estimated_cost_usd": 0.004185,
    "llm_latency_ms": 9663,
    "total_latency_ms": 12195,
    "pages_analyzed": 3,
    "content_chars_sent": 12158,
    "cached": false
  }
}
```

### Logs from a local run

From [docs/sample_server.log](docs/sample_server.log):

```
INFO  analysis_service - Extracted https://stripe.com/in: pages=3 chars_sent=12158 (homepage text=8562 chars)
INFO  llm_service - LLM ok provider=gemini model=gemini-3.1-flash-lite attempt=1 latency_ms=9663 input_tokens=3809 output_tokens=2155
INFO  app - POST /link-analysis 200 12218ms
INFO  analysis_service - Extracted https://www.shopify.com/in: pages=2 chars_sent=8267 (homepage text=3067 chars)
INFO  llm_service - LLM ok provider=gemini model=gemini-3.1-flash-lite attempt=1 latency_ms=7661 input_tokens=3222 output_tokens=2552
INFO  app - POST /link-analysis 200 8212ms
INFO  analysis_service - Cache hit for https://stripe.com
INFO  app - POST /link-analysis 200 7ms
WARNING app - POST /link-analysis -> 400 Invalid URL: Access to this host is not allowed
WARNING app - POST /link-analysis -> 400 Invalid URL: Access to private or internal network addresses is not allowed
WARNING app - POST /link-analysis -> 502 Website could not be fetched: Website returned HTTP 404. ...
```

Fallback chain in action (from an earlier run, when the primary was overloaded):

```
WARNING llm_service - LLM invalid output model=gemini-3.5-flash-lite attempt=1: Expecting property name enclosed in double quotes ...
WARNING llm_service - LLM retryable error model=gemini-3.5-flash-lite attempt=2: HTTP 503
INFO    llm_service - LLM ok provider=gemini model=gemini-3.1-flash-lite attempt=1 latency_ms=8682 input_tokens=3809 output_tokens=2233
INFO    app - POST /link-analysis 200 27384ms
```

The malformed-JSON failure above led to adding Gemini's `responseJsonSchema` (constrained decoding). Since then, every benchmark run has returned valid JSON.

---

## Error handling

Every error uses the same JSON shape: `{"success": false, "error": "...", "detail": "..."}`. Captured examples are in [docs/error_examples.md](docs/error_examples.md).

| Scenario | HTTP | `error` |
|---|---|---|
| Missing / malformed body | 422 | `Validation error` |
| Invalid URL, unsupported scheme, non-standard port, credentials in URL | 400 | `Invalid URL` |
| localhost, private/link-local/CGNAT IPs, cloud metadata, `.internal`/`.local` hosts, domains resolving to private IPs | 400 | `Invalid URL` |
| Unresolvable domain | 400 | `Invalid URL` |
| Redirect to a blocked address | 400 | `Invalid URL` |
| Website returns 4xx/5xx, is not HTML, or refuses the connection | 502 | `Website could not be fetched` |
| Website timeout | 504 | `Website request timed out` |
| Page has no readable content (e.g. JS-only shell) | 422 | `Not enough website content to analyze` |
| No LLM API key configured | 503 | `LLM provider is not configured` |
| All LLM models/providers failed | 502 | `LLM analysis failed` |
| Anything unexpected | 500 | `Internal server error` (no stack trace is leaked) |

---

## Testing

```bash
pytest -v
```

39 tests that run fully offline (DNS, websites and LLM are mocked):

- SSRF: localhost, RFC-1918, link-local/metadata, IPv6 loopback, IPv4-mapped IPv6, CGNAT, `.local`/`.internal`, DNS-rebinding style domains, redirects to internal IPs
- Extraction: script/footer removal, line de-duplication, JSON-LD, nav labels, extra pages, graceful skip of a 404 sub-page, non-HTML rejection
- LLM: JSON extraction from fenced/noisy output, incomplete-output rejection, model fallback chain, missing key
- API: structured 400/422/503 errors, full success path covering all five sections, competitor labelling, platform coverage, caching and `refresh=true`

Live benchmark against real websites: `python -m scripts.benchmark --models gemini-3.1-flash-lite gemini-3.5-flash-lite`

---

## LLM platform research and recommendation

> **Measured vs estimated.** Rows marked **measured** come from `scripts/benchmark.py` running this exact prompt on 4 real websites (stripe.com, shopify.com, mailchimp.com, notion.com) on 2026-11-21. Raw data is in [docs/benchmark_results.json](docs/benchmark_results.json). Everything else is **estimated** from provider documentation. No accuracy benchmark claims are made beyond what was tested here.
>
> **Pricing** is the standard paid tier in USD per 1M tokens, taken from provider pricing pages and pricing trackers in November 2026. Prices change often, so check the provider's page before relying on them.

### A. LLM platform comparison

| Criteria | Gemini 3.1 Flash-Lite | Gemini 3.5 Flash-Lite | Gemini 3.8 Flash | OpenAI GPT-5.4 mini | OpenAI GPT-5.4 nano | Anthropic Claude Haiku 5.5 |
|---|---|---|---|---|---|---|
| **Provider** | Google | Google | Google | OpenAI | OpenAI | Anthropic |
| **API cost (in / out)** | $0.25 / $1.50 | $0.30 / $2.50 | $0.75 / $3.75 (intro until 2026-12-31, then $1.50 / $7.50) | $0.75 / $4.50 | $0.20 / $1.25 | $0.10 / $0.50 (prompts ≤100k tokens) |
| **Response time** | **8.2 s avg (measured)** | **7.9 s avg (measured)** | Not measurable: 429/503 overload on all 4 runs | ~6-12 s (estimate) | ~4-8 s (estimate) | ~5-10 s (estimate) |
| **Cost per analysis** | **$0.0044 (measured)** | **$0.0077 (measured)** | ~$0.012 (estimate) | ~$0.014 (estimate) | ~$0.0037 (estimate) | ~$0.0015 (estimate) |
| **Output quality on this task** | 4/4 schema-complete; grounded services; 3 competitors per site (measured) | 4/4 schema-complete; slightly longer, richer text (measured) | Not tested | Not tested | Not tested (nano models are weaker on market knowledge) | Not tested |
| **Context window** | 1M | 1M | 1M | 400k | 400k | 200k |
| **JSON support** | JSON schema (constrained) | JSON schema (constrained) | JSON schema (constrained) | Structured Outputs / JSON mode | Structured Outputs / JSON mode | Tool use / structured outputs |
| **Availability notes** | Shutdown announced for 2027-05-07 | Current generation | Capacity-limited during testing | Implemented as optional fallback | | No key available for testing |
| **Suitability** | **Recommended primary** | **Recommended fallback / successor** | Too expensive and unreliable for this workload right now | Good cross-provider fallback | Budget option | Promising on price; worth benchmarking |

The estimated costs use the measured average token usage for this prompt: about 3,200 input and 2,400 output tokens.

### B. Best model selection

| Requirement | How the choice satisfies it |
|---|---|
| Accuracy on website content | Both Flash-Lite models returned all five sections on 4 of 4 sites, with services that match each site's real products (e.g. Stripe Billing, Radar, Connect, Issuing). This was checked by reading the outputs, not by a formal accuracy benchmark. |
| Fast response | ~8 s LLM time, ~8-12 s end to end including fetching 2-3 pages (measured). Repeat requests are served from cache in under 10 ms. |
| Low cost | $0.0044 per analysis measured, i.e. ~230 analyses per $1 |
| Reliable JSON | `responseJsonSchema` constrained decoding, then Pydantic validation, retry, and model fallback. 8 of 8 benchmark runs were valid. |
| Competitor and SEO insight | Named competitors are real and category-appropriate (Stripe → PayPal, Adyen, Razorpay for the India-localised site; Shopify → WooCommerce, Wix eCommerce, BigCommerce). SEO output rewrites the current title/meta instead of copying it. |
| Large content | 1M-token context, but the app sends a trimmed ~3.2k-token summary on purpose (see C) |

### C. Cost optimization (implemented)

1. **HTML cleaning before the LLM**: scripts, styles, SVG, forms, header/footer/nav/aside are removed. Only text, headings, meta, JSON-LD and nav labels are kept.
2. **De-duplication**: repeated lines (menus, CTAs, carousels) are dropped.
3. **Fixed content budget**: 12k characters (~3.2k tokens). The homepage gets ~65% and key sub-pages share the rest. A raw homepage is often 50k-500k characters.
4. **Targeted extra pages**: at most 2 sub-pages, chosen by URL/link text (about, services, products, pricing), instead of crawling.
5. **One LLM call for all five sections**: about 5x cheaper than one call per section, because the website content (the largest part of the prompt) is sent only once.
6. **Cheapest adequate model first**: Flash-Lite as primary. The pricier model runs only on failure.
7. **Schema-constrained output**: avoids paying again for malformed JSON.
8. **Caching**: an in-memory TTL cache (1 h) means repeat analyses of the same URL cost $0. Use Redis in a multi-instance deployment.
9. **Low temperature (0.3) and concise-output instructions** keep output tokens down (output tokens cost 6-8x more than input).
10. **Further options, not yet enabled**: Batch API (~50% off) for bulk or offline analysis, and context caching of the fixed system prompt.

### D. Final LLM recommendation

| Item | Recommendation |
|---|---|
| **Provider** | Google Gemini API |
| **Model** | `gemini-3.1-flash-lite` |
| **Estimated input tokens** | ~3,200 per analysis (measured range 2,300-3,800) |
| **Estimated output tokens** | ~2,400 per analysis (measured range 2,150-2,550) |
| **Cost per analysis** | ~$0.0044 (measured average); ~$4.40 per 1,000 analyses |
| **Response time** | ~8 s LLM / ~8-12 s end to end (measured); <10 ms when cached |
| **Fallback** | `gemini-3.5-flash-lite` (same provider, ~$0.0077, measured), then OpenAI `gpt-5.4-mini` for provider-level outages |
| **Why** | It was the cheapest model that passed every benchmark run on the first attempt, it has native schema-constrained JSON and a 1M context window, and its output quality matched 3.5 Flash-Lite at ~43% lower cost. |
| **Balancing accuracy, speed and cost** | Clean and trim content first, run a single schema-constrained call on a lite model, validate with Pydantic, and escalate to a stronger or alternative model only on failure. Cache results, and use the Batch API for non-interactive bulk jobs. |
| **Migration note** | Google has announced that `gemini-3.1-flash-lite` will shut down on 2027-05-07. Switching is a one-line change (`GEMINI_MODEL=gemini-3.5-flash-lite`), and that model already passes the same benchmark. |

---

## Deployment

The repository includes a `Dockerfile`, `render.yaml` (Render blueprint) and a `Procfile` (Railway / Heroku-style platforms).

**Render (free tier):**

1. Push the repository to GitHub.
2. In Render, choose **New → Blueprint** and select the repository. `render.yaml` is detected automatically.
3. Set the `GEMINI_API_KEY` environment variable when prompted.
4. After the deploy finishes:
   - API: `https://<your-service>.onrender.com/link-analysis`
   - Docs: `https://<your-service>.onrender.com/docs`

**Docker anywhere:**

```bash
docker build -t ai-link-analysis .
docker run -p 4000:4000 -e GEMINI_API_KEY=your_key ai-link-analysis
```

| Requirement | URL |
|---|---|
| Live Demo | `https://<your-deployment>` |
| API Endpoint | `https://<your-deployment>/link-analysis` |
| API Documentation | `https://<your-deployment>/docs` |

---

## Security

- **SSRF protection**:
  - Only http/https on ports 80/443/8080/8443, with no credentials in the URL.
  - Hostnames are resolved and **every** returned IPv4/IPv6 address must be globally routable. IPv4-mapped IPv6 addresses are unwrapped before checking.
  - Redirects are followed manually, at most 5, and **each hop is re-validated**, so a public URL cannot redirect into the internal network.
- Download size is capped at 3 MB and non-HTML responses are rejected.
- Website text is passed to the LLM as clearly delimited, untrusted data, and the model is told to ignore instructions inside it (prompt-injection mitigation).
- API keys come only from environment variables. `.env` is git-ignored, and the Gemini key is sent in a header (`x-goog-api-key`) rather than the URL, so it never appears in logs.
- Error responses never include stack traces or upstream request details.

---

## Project structure

```
ai-link-analysis/
├── app/
│   ├── main.py                    # FastAPI app, routes, error handlers, request logging
│   ├── config.py                  # Settings from environment (.env)
│   ├── exceptions.py              # Typed errors → HTTP status + JSON error body
│   ├── schemas.py                 # Pydantic request / response / LLM output models
│   ├── services/
│   │   ├── website_extractor.py   # Safe fetching, cleaning, key-page discovery, prompt content
│   │   ├── llm_service.py         # Prompt, Gemini/OpenAI calls, retries, fallback, cost tracking
│   │   ├── analysis_service.py    # Pipeline orchestration, post-processing, TTL cache
│   │   └── competitor_service.py  # Competitor cleaning, labelling, gaps, comparison table
│   └── utils/
│       └── validators.py          # URL validation + SSRF protection
├── scripts/
│   └── benchmark.py               # Live model benchmark (latency, tokens, cost, completeness)
├── tests/
│   └── test_link_analysis.py      # 39 offline tests
├── docs/                          # Sample responses, logs, error examples, benchmark data
├── Dockerfile, render.yaml, Procfile
├── .env.example
├── requirements.txt
└── README.md
```

---

## Known limitations

- **Competitors come from the model's general knowledge**, not live web research, and every entry is labelled `AI-generated suggestion`. Adding a search API (e.g. SerpAPI or Bing) would allow sourced verification.
- **No search volumes** are returned on purpose. Adding them would require a real data source such as Google Ads Keyword Planner or Semrush.
- **JavaScript-rendered sites** (empty HTML shells) produce little content. These return a 422, or a thin analysis based only on meta tags. A headless browser (e.g. Playwright) would fix this, at a cost in speed.
- **Geo-redirects**: some sites redirect to a regional version (e.g. `stripe.com` → `stripe.com/in` from India), and the analysis reflects that version.
- **The cache is per-process.** Use Redis when running several instances.
