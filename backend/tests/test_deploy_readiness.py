"""Deployment readiness contract — GitHub → Render Blueprint flow.

These tests assert the deployment-critical invariants so a bad edit fails CI
instead of failing on Render: blueprint fields, Dockerfile boot logic, env keys,
secret hygiene, gitignore coverage and Postgres URL normalization.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # repo root (socialos/)
BACKEND = ROOT / "backend"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- render.yaml
def test_render_blueprint_spec_fields():
    y = _read(ROOT / "render.yaml")
    assert "type: web" in y
    assert "runtime: docker" in y
    assert "rootDir: backend" in y          # build context = backend/
    assert "plan: free" in y
    assert "healthCheckPath: /health" in y  # Render health checker (no auth)
    assert "autoDeploy: true" in y
    # dockerfilePath intentionally omitted -> Render default ./Dockerfile under rootDir


def test_render_blueprint_env_defaults():
    y = _read(ROOT / "render.yaml")
    for var in ("SOCIALOS_AUTO_SEED", "SOCIALOS_MOCK_CONNECTORS",
                "SOCIALOS_WORKER_ENABLED", "SOCIALOS_LLM_PROVIDER"):
        assert re.search(rf"- key: {var}\s*\n\s*value: \"\w+\"", y), f"{var} envVar missing/malformed"


# ---------------------------------------------------------------- Dockerfile
def test_dockerfile_production_shape():
    d = _read(BACKEND / "Dockerfile")
    assert d.startswith("FROM python:3.13")            # pinned major.minor
    assert "pip install --no-cache-dir -r requirements.txt" in d
    assert "USER socialos" in d and "adduser" in d     # non-root runtime user
    assert "PYTHONUNBUFFERED=1" in d                   # log streaming on Render
    assert "--host 0.0.0.0" in d                       # bind all interfaces
    assert "${PORT:-8000}" in d                        # Render $PORT injection
    assert "WORKDIR /srv" in d


def test_dockerignore_blocks_secrets_and_state():
    di = _read(BACKEND / ".dockerignore")
    for pattern in (".env", ".vault_key", "*.db", "__pycache__/", ".pytest_cache/"):
        assert pattern in di, f".dockerignore missing {pattern}"
    assert "!.env.example" in di                       # template stays buildable-visible


# ---------------------------------------------------------------- env template
def test_env_example_documents_all_required_keys():
    env = _read(ROOT / ".env.example")
    required = [
        "SOCIALOS_DATABASE_URL",
        "SOCIALOS_VAULT_MASTER_KEY",
        "SOCIALOS_MOCK_CONNECTORS",
        "SOCIALOS_LLM_PROVIDER",
        "SOCIALOS_OPENAI_API_KEY",
        "SOCIALOS_QUEUE_BACKEND",
        "SOCIALOS_REDIS_URL",
        "SOCIALOS_TELEGRAM_BOT_TOKEN",
        "SOCIALOS_YOUTUBE_CLIENT_ID",
        "SOCIALOS_INSTAGRAM_CLIENT_ID",
        "SOCIALOS_FACEBOOK_CLIENT_ID",
        "SOCIALOS_TIKTOK_CLIENT_KEY",
        "SOCIALOS_PINTEREST_CLIENT_ID",
        "SOCIALOS_REDDIT_CLIENT_ID",
    ]
    missing = [k for k in required if f"{k}=" not in env]
    assert not missing, f".env.example missing: {missing}"
    assert "VAULT_MASTER_KEY" in env                    # unprefixed alias documented
    # template must never ship real values
    assert not re.search(r"=(sk-[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{30,}|xox[baprs]-)", env)


# ---------------------------------------------------------------- secret hygiene
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),          # OpenAI-style keys
    re.compile(r"AIza[A-Za-z0-9_\-]{30,}"),      # Google API keys
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),     # Slack tokens
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),         # GitHub PATs
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def _git_files() -> list[Path] | None:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, timeout=15, check=True).stdout
        return [ROOT / f for f in out.splitlines() if f.strip()]
    except Exception:
        return None  # not a git checkout (e.g. zip run) — skip, file-level checks still apply


def test_no_secrets_in_tracked_files():
    files = _git_files()
    if files is None:
        files = [p for p in BACKEND.rglob("*.py")]
    hits = []
    for f in files:
        if not f.is_file() or f.suffix in {".zip", ".db", ".png", ".jpg"}:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                hits.append(f"{f.name}: {m.group(0)[:12]}…")
    assert not hits, f"possible hardcoded secrets: {hits}"


def test_sensitive_paths_not_tracked():
    files = _git_files()
    if files is None:
        return  # skip when git metadata is absent
    names = {str(f.relative_to(ROOT)) for f in files}
    for forbidden in (".env", ".vault_key", "socialos.db"):
        assert forbidden not in names, f"{forbidden} must not be committed"


# ---------------------------------------------------------------- .gitignore
def test_gitignore_covers_local_artifacts():
    gi = _read(ROOT / ".gitignore")
    for pattern in (".venv/", "venv/", "__pycache__/", "*.db", ".sqlite3".lstrip("."), ".env", ".vault_key", ".pytest_cache/"):
        assert pattern in gi, f".gitignore missing {pattern}"
    assert "!.env.example" in gi


# ---------------------------------------------------------------- runtime behaviour
def test_postgres_url_normalization():
    from app.db.base import normalize_db_url

    assert normalize_db_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert normalize_db_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert normalize_db_url("postgresql+psycopg://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"  # idempotent
    assert normalize_db_url("sqlite:///./demo.db") == "sqlite:///./demo.db"


def test_vault_master_key_alias_precedence(monkeypatch):
    from app.core.config import Settings, resolve_vault_key

    # 1) unprefixed alias honoured when prefixed var is empty
    monkeypatch.setenv("VAULT_MASTER_KEY", "ab" * 32)
    assert resolve_vault_key(Settings(vault_master_key="")) == "ab" * 32
    # 2) explicit SOCIALOS_VAULT_MASTER_KEY wins over the alias
    assert resolve_vault_key(Settings(vault_master_key="cd" * 32)) == "cd" * 32


def test_health_contract_is_authfree_and_fast():
    """/health must answer 200 without any API key (Render health checker)."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:   # runs lifespan (seed+worker) like a cold boot
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        # landing + docs reachable without auth as well
        assert client.get("/").status_code == 200
        assert client.get("/docs").status_code == 200
        # API surface enforces the key
        assert client.get("/api/workspaces").status_code == 401
