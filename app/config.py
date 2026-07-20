"""Centralized application settings, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM — NVIDIA NIM (OpenAI-compatible)
    nvidia_api_key: str = ""
    nvidia_model: str = "openai/gpt-oss-120b"
    nvidia_fallback_model: str = "meta/llama-3.1-70b-instruct"

    # Database (asyncpg DSN for tools; psycopg DSN for checkpointer — same URL)
    database_url: str = "postgresql://ops:ops@localhost:5432/ops"
    db_pool_min: int = 2
    db_pool_max: int = 10
    # psycopg pool for the LangGraph Postgres checkpointer
    checkpoint_pool_min: int = 1
    checkpoint_pool_max: int = 5

    # Redis / async queue
    redis_url: str = "redis://localhost:6379"
    job_ttl: int = 3600        # seconds to keep job results in Redis
    job_timeout: int = 300     # max seconds a single agent turn may run (allow multi-step)

    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    # Comma-separated valid API keys for machine-to-machine callers
    api_keys: str = "dev-key-change-me"

    # Agent
    max_steps: int = 6
    # Hard backstop: must comfortably exceed max_steps * 4 (node executions per step)
    recursion_limit: int = 60
    # How many recent messages the plan node sees (older ones → summarized)
    history_window: int = 20

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Memory
    episodic_recall_k: int = 3    # past episodes to inject at plan time
    long_term_recall_k: int = 5   # user facts to inject at plan time

    # Observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    otel_endpoint: str = ""       # e.g. http://localhost:4318/v1/traces; blank = no-op
    otel_service_name: str = "operations-assistant"

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def otel_enabled(self) -> bool:
        return bool(self.otel_endpoint)

    @property
    def llm_configured(self) -> bool:
        return bool(self.nvidia_api_key)

    # psycopg conninfo string (same host/db, different driver notation)
    @property
    def checkpoint_conninfo(self) -> str:
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
