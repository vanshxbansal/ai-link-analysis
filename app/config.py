from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM providers
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    llm_timeout: int = 90
    llm_temperature: float = 0.3

    # Website extraction
    request_timeout: int = 20
    max_content_length: int = 50000
    max_html_bytes: int = 3_000_000
    max_llm_content_chars: int = 12000
    max_extra_pages: int = 2

    # Caching
    cache_ttl_seconds: int = 3600
    cache_max_entries: int = 256

    app_env: str = "development"
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
