"""
Application configuration.

Settings are read from environment variables (or a .env file) using
pydantic-settings.  Every value has a safe fallback for local development;
production deployments must override at least DATABASE_URL and JWT_SECRET_KEY
via environment variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration object.

    Field values are populated in this priority order:
      1. Real environment variables.
      2. Values in the .env file at the project root.
      3. The defaults defined here (safe for local dev only).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/kaamwala"

    # JWT — secret must be a long, random string in production.
    # Algorithm HS256 is symmetric; all signing and verification happen server-side.
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # App
    APP_NAME: str = "KaamWala API"
    APP_VERSION: str = "0.1.0"
    # DEBUG enables SQLAlchemy query logging; never enable in production.
    DEBUG: bool = False


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    @lru_cache ensures the .env file is read only once per process,
    which matters for performance under uvicorn with multiple workers.
    """
    return Settings()


# Module-level singleton used throughout the application via direct import.
settings = get_settings()
