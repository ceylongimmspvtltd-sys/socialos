"""FastAPI application factory — C Tech SocialOS."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import settings
from app.db.base import SessionLocal, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("socialos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema creation — safe on every cold start (SQLite demo or PostgreSQL prod).
    try:
        init_db()
    except Exception:  # noqa: BLE001 — never block the health check on schema issues
        log.exception("init_db failed (continuing startup; /health stays reachable)")

    # Demo data seeding — non-fatal: a seeding bug must never take the service down.
    if settings.auto_seed:
        try:
            from app.db.seed import seed_if_empty

            with SessionLocal() as db:
                seeded = seed_if_empty(db)
                log.info("auto-seed: %s", "created demo org" if seeded else "already populated")
        except Exception:  # noqa: BLE001
            log.exception("auto-seed failed (service continues unseeded)")

    # Background publish worker.
    worker_task = None
    if settings.worker_enabled:
        try:
            from app.scheduler.worker import worker_loop

            worker_task = asyncio.create_task(worker_loop(SessionLocal))
            log.info("publish worker started (poll %.1fs)", settings.worker_poll_seconds)
        except Exception:  # noqa: BLE001
            log.exception("worker failed to start")
    yield
    if worker_task:
        worker_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        description=(
            "Autonomous multi-niche AI social media marketing & publishing platform.\n\n"
            "**Auth:** `X-API-Key: demo-key` (demo tenant) · **Demo mode:** connectors publish to "
            "deterministic mocks until real OAuth credentials are configured."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    from app.modules import analytics_api, campaigns, connectors_api, portal, root, scheduling_api, trends_api, workspaces

    app.include_router(root.router)
    app.include_router(workspaces.router)
    app.include_router(campaigns.router)
    app.include_router(scheduling_api.router)
    app.include_router(portal.router)
    app.include_router(connectors_api.router)
    app.include_router(trends_api.router)
    app.include_router(analytics_api.router)
    return app


app = create_app()
