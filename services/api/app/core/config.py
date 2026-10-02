"""
Application configuration via Pydantic Settings.
All values are driven by environment variables (or .env file).
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_NAME: str = "LumaVaani"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ──────────────────────────────────────────────────────────────────
    API_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("API_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # ── AI Gateway (Gemini) ───────────────────────────────────────────────────
    AI_DEFAULT_PROVIDER: Literal["gemini", "openai", "anthropic"] = "gemini"
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    # Gemini — primary AI provider
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"          # fast + cost-effective for front-desk
    GEMINI_TEMPERATURE: float = 0.4                  # lower = more deterministic for clinical
    GEMINI_MAX_OUTPUT_TOKENS: int = 1024

    # Conversation engine settings
    AI_SAFETY_ENABLED: bool = True                   # run safety layer on all AI I/O
    AI_MAX_TOOL_ITERATIONS: int = 6                  # max tool-calling rounds per turn
    AI_MAX_CONVERSATION_TURNS: int = 50              # max messages per conversation session
    AI_TOOL_TIMEOUT_SECONDS: float = 10.0            # per-tool execution timeout

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()
