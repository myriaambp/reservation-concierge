"""Centralized config — loads from env, validates with pydantic."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""  # only used if LLM_PROVIDER=anthropic
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    # Defaults run on Vertex AI Gemini, billed against GCP credits.
    # Gemini 2.5 Flash is the workhorse — its thinking budget is light enough
    # not to starve tool-use output, and it's ~10× cheaper than 2.5 Pro.
    supervisor_model: str = "gemini-2.5-flash"
    worker_model: str = "gemini-2.5-flash"
    judge_model: str = "gemini-2.5-flash"
    embedding_model: str = "text-embedding-005"

    provider_mode: str = "mock"
    # Memory backend: "local" (JSON file, default for dev) or "firestore"
    # (production). Local mode skips Firestore entirely so dev works without
    # enabling the Cloud Firestore API.
    memory_backend: str = "local"

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
