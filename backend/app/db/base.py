"""Database engine/session management.

Demo: SQLite (zero-config). Production: PostgreSQL — apply db/migrations/*.sql, which also
enables pgvector and Row-Level Security policies keyed off `app.current_tenant`.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def normalize_db_url(url: str) -> str:
    """Normalize Render/Heroku-style Postgres URLs to the SQLAlchemy psycopg3 dialect.
    Accepts: postgres://, postgresql://, postgresql+psycopg:// (idempotent)."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def make_engine(url: str | None = None):
    url = normalize_db_url(url or settings.database_url)
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_tenant_guc(db: Session, tenant_id: str) -> None:
    """Set the PostgreSQL session GUC consumed by RLS policies. No-op on SQLite
    (tenant scoping is enforced at the ORM/repository layer there)."""
    if settings.is_postgres:
        db.execute(text("SELECT set_config('app.current_tenant', :t, false)"), {"t": tenant_id})


def init_db() -> None:
    """Create tables (demo/bootstrap). Production: prefer versioned SQL migrations."""
    from app.db import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)


@event.listens_for(engine, "connect")
def _sqlite_fk_pragma(dbapi_conn, _record):
    if engine.url.drivername.startswith("sqlite"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
