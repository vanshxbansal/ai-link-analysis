"""Application-level exceptions mapped to clean JSON error responses."""


class AppError(Exception):
    status_code = 500
    error = "Internal server error"

    def __init__(self, detail: str = ""):
        super().__init__(detail or self.error)
        self.detail = detail or self.error


class InvalidURLError(AppError):
    status_code = 400
    error = "Invalid URL"


class WebsiteFetchError(AppError):
    status_code = 502
    error = "Website could not be fetched"


class WebsiteTimeoutError(AppError):
    status_code = 504
    error = "Website request timed out"


class InsufficientContentError(AppError):
    status_code = 422
    error = "Not enough website content to analyze"


class LLMConfigError(AppError):
    status_code = 503
    error = "LLM provider is not configured"


class LLMServiceError(AppError):
    status_code = 502
    error = "LLM analysis failed"
