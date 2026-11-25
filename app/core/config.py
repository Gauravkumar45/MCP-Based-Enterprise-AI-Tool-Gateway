"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "super-secret-jwt-key-change-me-in-production-min-32-chars"


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
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ISSUER: str = "mcp-enterprise-tool-gateway"
    JWT_AUDIENCE: str = "mcp-enterprise-tool-gateway"

    # Authentication hardening
    # Demo shortcuts (username aliases like "bob" and relaxed demo passwords) are for local
    # demos only. They are rejected at startup when APP_ENV=production.
    AUTH_DEMO_SHORTCUTS: bool = False
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_WINDOW_SECONDS: int = 300

    # HTTP security
    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:8501", "http://localhost:3000"]
    )
    SECURITY_HEADERS_ENABLED: bool = True

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

    def production_config_errors(self) -> list[str]:
        """Return a list of insecure settings that must not be used in production."""
        errors: list[str] = []
        if self.APP_ENV != "production":
            return errors
        if self.JWT_SECRET == DEFAULT_JWT_SECRET or len(self.JWT_SECRET) < 32:
            errors.append("JWT_SECRET must be overridden with a random value of at least 32 chars")
        if self.JWT_ALGORITHM.lower() == "none":
            errors.append("JWT_ALGORITHM must not be 'none'")
        if self.AUTH_DEMO_SHORTCUTS:
            errors.append("AUTH_DEMO_SHORTCUTS must be disabled in production")
        if "*" in self.CORS_ALLOWED_ORIGINS:
            errors.append("CORS_ALLOWED_ORIGINS must list explicit origins, not '*'")
        if self.DEBUG:
            errors.append("DEBUG must be disabled in production")
        return errors

    def validate_for_environment(self) -> None:
        """Fail fast when the configuration is unsafe for the current environment."""
        errors = self.production_config_errors()
        if errors:
            raise RuntimeError("Insecure production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
