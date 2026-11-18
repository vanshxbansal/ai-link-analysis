from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx

from app.schemas import AnalysisRequest, AnalysisResponse, ErrorResponse
from app.services.analysis_service import run_full_analysis
from app.utils.validators import validate_url, normalize_url

app = FastAPI(
    title="AI-Powered Website Link Analysis API",
    description=(
        "Analyzes a website URL and generates business, competitor, SEO, "
        "search query, and target audience insights using an LLM."
    ),
    version="1.0.0",
)


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Link Analysis API is running. Visit /docs for API documentation."}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post(
    "/link-analysis",
    response_model=AnalysisResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid URL or inaccessible website"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Analyze a website URL",
    description=(
        "Accepts a website URL, extracts its content, and uses an LLM to generate "
        "5 analysis sections: competitor analysis, search queries, SEO improvements, "
        "top services, and target audience identification."
    ),
)
async def link_analysis(request: AnalysisRequest):
    url = normalize_url(request.url.strip())

    # Validate URL and check for SSRF
    is_valid, error_msg = validate_url(url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        result = await run_full_analysis(url)
        return result

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=400,
            detail=f"Request to {url} timed out. The website may be too slow or unreachable.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Website returned HTTP {e.response.status_code}. The page may not be accessible.",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not reach the website: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": "Validation error", "detail": str(exc)},
    )
