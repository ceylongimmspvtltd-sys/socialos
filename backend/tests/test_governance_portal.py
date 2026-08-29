"""3-tier governance + tokenized client portal + retry/DLQ worker behaviour."""
import time

import pytest

from app.agents.orchestrator import run_pipeline
from app.core.security import hash_api_key, portal_token_expiry
from app.db.base import Base, make_engine
from app.db.models import Campaign, ClientApproval, ContentItem, ScheduledPost, Tenant, Workspace
from app.scheduler.governance import client_decide, internal_approve, stage_and_govern
from app.scheduler.worker import publish_due


@pytest.fixture()
def db(tmp_path):
    from sqlalchemy.orm import sessionmaker

    eng = make_engine(f"sqlite:///{tmp_path/'gov.db'}")
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, expire_on_commit=False)
    yield S()
    # engine disposed implicitly


def _mk_item(db, gov_mode, niche="salon"):
    t = Tenant(name="T", api_key_hash=hash_api_key("k"))
    db.add(t)
    db.flush()
    ws = Workspace(tenant_id=t.id, name=f"WS-{niche}", industry_niche=niche)
    db.add(ws)
    db.flush()
    c = Campaign(workspace_id=ws.id, name="C", governance_mode=gov_mode,
                 target_demographic={"region": "LK", "destination_url": "https://x.y"})
    db.add(c)
    db.flush()
    item = ContentItem(campaign_id=c.id, workspace_id=ws.id, niche=niche, title="t",
                       master_prompt="brief", target_platforms=["instagram", "telegram"])
    db.add(item)
    db.commit()
    return item


async def test_autonomous_mode_queues_immediately(db):
    item = _mk_item(db, "autonomous")
    final = await run_pipeline(db, item.id)
    assert final["governance"]["mode"] == "autonomous"
    assert final["governance"]["queued"] == 2
    assert item.status == "QUEUED"


async def test_client_portal_flow(db):
    item = _mk_item(db, "client_portal", niche="travel")
    final = await run_pipeline(db, item.id)
    token = final["governance"]["approval_token"]
    assert token
    approval = db.query(ClientApproval).filter(ClientApproval.token == token).first()
    assert approval.status == "pending"

    outcome = client_decide(db, approval, "approved", "Looks great, ship it")
    assert outcome.startswith("queued:")
    assert item.status == "QUEUED"
    assert approval.client_feedback == "Looks great, ship it"


async def test_client_portal_rejection(db):
    item = _mk_item(db, "client_portal", niche="ecom")
    final = await run_pipeline(db, item.id)
    token = final["governance"]["approval_token"]
    approval = db.query(ClientApproval).filter(ClientApproval.token == token).first()
    outcome = client_decide(db, approval, "rejected", "Too salesy for our brand")
    assert outcome == "rejected"
    assert item.status == "REJECTED"


def test_expired_portal_token(db):
    item = _mk_item(db, "client_portal", niche="hospitality")
    approval = ClientApproval(content_item_id=item.id, token="tok", expires_at=time.time() - 10)
    db.add(approval)
    db.commit()
    with pytest.raises(PermissionError):
        client_decide(db, approval, "approved")


async def test_worker_publishes_due_posts(db):
    item = _mk_item(db, "autonomous")
    await run_pipeline(db, item.id)
    from datetime import datetime, timedelta

    for p in db.query(ScheduledPost).filter(ScheduledPost.content_item_id == item.id).all():
        p.scheduled_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    results = await publish_due(db)
    assert len(results) == 2
    assert all(r["status"] == "PUBLISHED" for r in results)
    assert item.status == "PUBLISHED"


async def test_worker_retries_guarded_reddit_until_dead(db):
    item = _mk_item(db, "autonomous", niche="production")
    item.target_platforms = ["reddit"]
    db.commit()
    # reddit guard will fail: value_first payload present, but force a failing payload
    await run_pipeline(db, item.id)
    post = db.query(ScheduledPost).filter(ScheduledPost.content_item_id == item.id).first()
    assert post is not None
    if post and post.platform == "reddit":
        post.publish_status = "QUEUED"
        post.payload_json["platform_payload"]["value_first"] = False  # force guard violation
        db.commit()
        from datetime import datetime, timedelta

        post.scheduled_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
        for _ in range(4):
            await publish_due(db)
        db.refresh(post)
        assert post.publish_status in ("FAILED", "DEAD") and post.attempts >= 1
