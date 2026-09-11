"""
aurelius.settings
=================
Application configuration management using pydantic-settings.

How it works:
  pydantic-settings reads values from:
  1. Environment variables (highest priority)
  2. A .env file (if present)
  3. Default values defined in the model

  Values are validated at startup. If a required field is missing,
  pydantic-settings raises a clear ValidationError before the server starts,
  preventing silent misconfiguration.

Usage:
  from aurelius.settings import get_settings
  settings = get_settings()

Caching:
  get_settings() is decorated with @lru_cache, so settings are loaded once
  and reused. In tests, call get_settings.cache_clear() to reset.

Security:
  - Never log settings.dict() — it may contain API keys.
  - API keys must never appear in source code.
  - The .env file is listed in .gitignore and must not be committed.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    AURELIUS application settings.

    All configuration comes from environment variables or the .env file.
    The field names here must match the variable names in .env.example.
    """

    model_config = SettingsConfigDict(
        # Read from .env file at project root (one level up from backend/).
        # If .env does not exist, fall back to environment variables only.
        env_file="../.env",
        env_file_encoding="utf-8",
        # Do not raise an error if the .env file does not exist.
        # The developer may be setting env vars directly (e.g., in CI).
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------

    aurelius_env: str = Field(
        default="development",
        description="Runtime environment: 'development' | 'production'.",
    )

    aurelius_log_level: str = Field(
        default="INFO",
        description="Python logging level: DEBUG | INFO | WARNING | ERROR | CRITICAL.",
    )

    # -------------------------------------------------------------------------
    # API
    # -------------------------------------------------------------------------

    api_host: str = Field(
        default="127.0.0.1",
        description="Host to bind the Uvicorn server to.",
    )

    api_port: int = Field(
        default=8000,
        description="Port for the Uvicorn server.",
    )

    # Allowed CORS origins. In development, allow the Vite dev server.
    # In production, restrict to the actual deployed frontend domain.
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="List of allowed CORS origins.",
    )

    # -------------------------------------------------------------------------
    # Data Provider API Keys
    # These are optional at Milestone 0/1 (yfinance requires no key).
    # They will be used in later milestones (FMP from M6, AV from M1+).
    # The fields are here to document the expected environment variables.
    # -------------------------------------------------------------------------

    fmp_api_key: str | None = Field(
        default=None,
        description=(
            "Financial Modeling Prep API key. "
            "Required from Milestone 6 (Financial Statements). "
            "Free tier: 250 requests/day. Get one at financialmodelingprep.com."
        ),
    )

    alpha_vantage_api_key: str | None = Field(
        default=None,
        description=(
            "Alpha Vantage API key. "
            "Optional provider for historical price data. "
            "Free tier: 25 requests/day. Get one at alphavantage.co."
        ),
    )

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------

    database_url: str = Field(
        default="sqlite+aiosqlite:///./aurelius.db",
        description=(
            "SQLAlchemy async database URL. "
            "Development default: SQLite via aiosqlite. "
            "Production path: postgresql+asyncpg://user:password@host/dbname. "
            "IMPORTANT: SQLite → PostgreSQL migration requires explicit schema "
            "and query compatibility testing before production use."
        ),
    )

    @property
    def is_development(self) -> bool:
        return self.aurelius_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.aurelius_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached Settings instance.

    The settings are loaded once at first call and cached via lru_cache.
    This is the preferred way to access settings throughout the application.

    In tests:
        from aurelius.settings import get_settings
        get_settings.cache_clear()
        # Then monkeypatch environment variables before calling get_settings()
    """
    return Settings()
