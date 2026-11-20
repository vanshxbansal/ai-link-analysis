import asyncio
import logging
import time

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.exceptions import AppError, InvalidURLError
from app.schemas import AnalysisRequest, AnalysisResponse, ErrorResponse
from app.services.analysis_service import run_full_analysis
from app.utils.validators import normalize_url, validate_url

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI(
    title="AI-Powered Website Link Analysis API",
    description=(
        "Analyzes a website URL and generates business, competitor, SEO, "
        "search query, and target audience insights using an LLM."
    ),
    version="1.1.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


def _error(status_code: int, error: str, detail: str = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error, detail=detail).model_dump(),
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning("%s %s -> %d %s: %s", request.method, request.url.path, exc.status_code, exc.error, exc.detail)
    return _error(exc.status_code, exc.error, exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    messages = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
    return _error(422, "Validation error", messages)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, str(exc.detail))


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return _error(500, "Internal server error", "Analysis failed due to an unexpected error.")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info(
        "%s %s %d %.0fms",
        request.method, request.url.path, response.status_code, (time.perf_counter() - started) * 1000,
    )
    return response


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Link Analysis API is running. Visit /docs for API documentation."}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": bool(settings.gemini_api_key or settings.openai_api_key),
        "model": settings.gemini_model if settings.gemini_api_key else settings.openai_model,
    }


@app.post(
    "/link-analysis",
    response_model=AnalysisResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid URL or blocked (private/internal) address"},
        422: {"model": ErrorResponse, "description": "Validation error or website has no readable content"},
        502: {"model": ErrorResponse, "description": "Website inaccessible or LLM provider failure"},
        503: {"model": ErrorResponse, "description": "LLM provider not configured"},
        504: {"model": ErrorResponse, "description": "Website request timed out"},
    },
    summary="Analyze a website URL",
    description=(
        "Accepts a website URL, extracts its content (homepage plus key About/Services pages), "
        "and uses an LLM to generate 5 analysis sections: competitor analysis, target search queries, "
        "SEO improvements, top services, and target audience."
    ),
)
async def link_analysis(
    request: AnalysisRequest,
    refresh: bool = Query(False, description="Bypass the cache and re-run the analysis"),
):
    url = normalize_url(request.url)

    is_valid, error_msg = await asyncio.to_thread(validate_url, url)
    if not is_valid:
        raise InvalidURLError(error_msg)

    return await run_full_analysis(url, use_cache=not refresh)
