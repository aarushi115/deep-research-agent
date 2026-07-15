"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings.

    All values can be overridden via environment variables or a `.env` file
    in the project root. See `.env.example` for the full list.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_temperature: float = Field(default=0.2, alias="GROQ_TEMPERATURE")

    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    max_llm_retries: int = Field(default=3, alias="MAX_LLM_RETRIES")
    max_research_retries: int = Field(default=2, alias="MAX_RESEARCH_RETRIES")
    max_search_results: int = Field(default=5, alias="MAX_SEARCH_RESULTS")

    default_hitl_enabled: bool = Field(default=True, alias="DEFAULT_HITL_ENABLED")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()
