"""Centralised, validated runtime configuration.

All settings are loaded from environment variables (12-factor) and validated
once at startup. Secrets are *never* logged. The `Settings` object is
constructed lazily and cached so tests can override individual values via
environment variables before the first call to `get_settings()`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    app_env: str = Field(default="dev")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8080)
    log_level: str = Field(default="info")
    allowed_origins: str = Field(default="http://localhost:8080")

    # Google AI / Gemini
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-2.0-flash")

    # Maps
    google_maps_api_key: str = Field(default="")

    # YouTube
    youtube_api_key: str = Field(default="")

    # Translate / GCP
    google_cloud_project: str = Field(default="")
    translate_location: str = Field(default="global")

    # Calendar
    default_timezone: str = Field(default="Asia/Kolkata")

    # Rate limiting
    rate_limit_per_minute: int = Field(default=30, ge=1, le=600)

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, v: str) -> str:
        v = v.lower()
        if v not in {"debug", "info", "warning", "error", "critical"}:
            return "info"
        return v

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached `Settings` instance."""
    return Settings()
