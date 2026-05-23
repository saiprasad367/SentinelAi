"""
SentinelAI — Core Configuration
All settings loaded from environment variables via pydantic-settings.
No hardcoded values anywhere.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "SentinelAI"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── Supabase ─────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = ""
    sync_database_url: str = ""

    # ── OpenRouter AI ────────────────────────────────────────────────────────
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "anthropic/claude-3-haiku"
    openrouter_fast_model: str = "openai/gpt-4o-mini"
    openrouter_strong_model: str = "anthropic/claude-3-5-sonnet"

    # ── HuggingFace Embeddings ───────────────────────────────────────────────
    hf_embedding_model: str = "BAAI/bge-small-en-v1.5"
    hf_device: str = "cpu"

    # ── Scheduler Intervals ──────────────────────────────────────────────────
    prediction_scan_interval_minutes: int = 5
    health_check_interval_seconds: int = 30
    analytics_aggregation_interval_minutes: int = 15

    # ── Business Impact ──────────────────────────────────────────────────────
    revenue_per_minute_usd: float = 1500.0
    critical_user_threshold: int = 10000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()


settings = get_settings()
