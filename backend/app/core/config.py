"""Application configuration (12-factor, env-driven)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOCIALOS_", env_file=".env", extra="ignore")

    # --- Identity ---
    app_name: str = "C Tech SocialOS"
    app_version: str = "0.1.0"

    # --- Data layer ---
    # Demo runs on SQLite; production uses Postgres (see docker-compose.yml + migrations).
    database_url: str = "sqlite:///./socialos.db"

    # --- Security ---
    # 32-byte key, hex or base64. If empty in dev, a key is generated and cached in .vault_key.
    vault_master_key: str = ""
    api_keys_csv: str = "demo-key"  # comma separated: "key1:tenant_id,key2:tenant_id" or bare keys
    portal_token_ttl_hours: int = 72

    # --- Connectors ---
    # When true (or when no real OAuth token exists) publishing runs against deterministic mocks.
    mock_connectors: bool = True
    http_timeout: float = 20.0

    # OAuth app credentials per platform (set per environment)
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    instagram_client_id: str = ""
    instagram_client_secret: str = ""
    facebook_client_id: str = ""
    facebook_client_secret: str = ""
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    pinterest_client_id: str = ""
    pinterest_client_secret: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    telegram_bot_token: str = ""

    # --- LLM ---
    llm_provider: str = "template"  # "template" (deterministic, offline) | "openai" (any OpenAI-compatible API)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # --- Queue ---
    queue_backend: str = "inproc"  # "inproc" | "redis"
    redis_url: str = "redis://localhost:6379/0"
    worker_poll_seconds: float = 2.0
    worker_enabled: bool = True

    # --- Trend hunter ---
    trends_live_fetch: bool = False  # demo default: bundled snapshot data (GDPR-safe aggregates)
    youtube_api_key: str = ""
    trend_subreddits: str = "travel,hairstyist,SkincareAddiction,videography,dropship"

    # --- Demo ---
    auto_seed: bool = True

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgres")


def _dev_vault_key() -> str:
    """Deterministic dev fallback key so the demo always boots. PRODUCTION: set SOCIALOS_VAULT_MASTER_KEY."""
    path = Path(".vault_key")
    if path.exists():
        return path.read_text().strip()
    import secrets

    key = secrets.token_hex(32)
    path.write_text(key)
    path.chmod(0o600)
    return key


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.vault_master_key = resolve_vault_key(s)
    return s


def resolve_vault_key(s: "Settings") -> str:
    """Vault key precedence: SOCIALOS_VAULT_MASTER_KEY > unprefixed VAULT_MASTER_KEY
    alias > dev fallback key (never used in production)."""
    if s.vault_master_key.strip():
        return s.vault_master_key.strip()
    alias = os.environ.get("VAULT_MASTER_KEY", "").strip()
    if alias:
        return alias
    return _dev_vault_key()


settings = get_settings()
