"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    APP_ENV: Literal["development", "staging", "production", "testing"] = "development"
    APP_NAME: str = "MCP-Enterprise-Tool-Gateway"
    APP_PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mcp_gateway"
    DATABASE_READONLY_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mcp_gateway"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT Authentication
    JWT_SECRET: str = "super-secret-jwt-key-change-me-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # LLM Settings
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # MCP Protocol Settings
    MCP_SERVER_NAME: str = "enterprise-tool-gateway"
    MCP_SERVER_VERSION: str = "1.0.0"
    DEFAULT_TOOL_TIMEOUT_SECONDS: int = 10
    MAX_TOOL_TIMEOUT_SECONDS: int = 60
    MAX_QUERY_LIMIT: int = 1000


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
