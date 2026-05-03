"""Centralized config — loads from env, validates with pydantic."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    supervisor_model: str = "claude-opus-4-7"
    worker_model: str = "claude-sonnet-4-6"
    judge_model: str = "claude-opus-4-7"
    embedding_model: str = "text-embedding-005"

    provider_mode: str = "mock"

    sendgrid_api_key: str = ""
    notify_from_email: str = "concierge@tableau.app"

    demo_fixture_replay: bool = True
    tick_interval_seconds: int = 120

    api_base_url: str = "http://localhost:8000"
    internal_tick_token: str = "dev-token"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://us.cloud.langfuse.com"

    daily_cost_cap: float = 5.00


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
