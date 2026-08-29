"""Regression: cold-start seeding inside a RUNNING event loop (uvicorn lifespan).

A previous bug ran loop.run_until_complete() nested inside uvicorn's loop,
which raised 'Cannot run the event loop while another loop is running' and left
fresh Render deploys unseeded. These tests pin the fix.
"""
import asyncio

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, make_engine
from app.db.models import ContentItem, ScheduledPost, Tenant
from app.db.seed import run_coro_sync, seed


@pytest.fixture()
def db(tmp_path):
    eng = make_engine(f"sqlite:///{tmp_path / 'coldstart.db'}")
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, expire_on_commit=False)
    session = S()
    yield session
    session.close()


async def test_seed_inside_running_event_loop(db):
    """Exact lifespan context: seed() called while an event loop is running."""
    seed(db)  # must not raise 'Cannot run the event loop while another loop is running'

    assert db.query(Tenant).count() == 1
    items = db.query(ContentItem).all()
    assert len(items) == 5
    assert all(i.status in ("PUBLISHED", "STAGED") for i in items), \
        [i.title for i in items if i.status not in ("PUBLISHED", "STAGED")]
    assert db.query(ScheduledPost).count() >= 15
    published = db.query(ScheduledPost).filter_by(publish_status="PUBLISHED").count()
    assert published >= 10
    # client-portal item must remain staged with a pending approval
    staged = [i for i in items if i.status == "STAGED"]
    assert len(staged) == 1 and staged[0].approvals


async def test_run_coro_sync_both_contexts():
    async def val():
        await asyncio.sleep(0)
        return 42

    # inside a running loop (this test) — private loop/thread path
    assert run_coro_sync(val()) == 42

    # outside any loop — plain asyncio.run path
    def _sync_call():
        return run_coro_sync(val())

    assert await asyncio.to_thread(_sync_call) == 42


async def test_run_coro_sync_propagates_exceptions():
    async def boom():
        raise ValueError("seed-coroutine-failure")

    with pytest.raises(ValueError, match="seed-coroutine-failure"):
        run_coro_sync(boom())
