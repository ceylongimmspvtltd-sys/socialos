"""3-Tier Publishing Governance (PRD §6.2).

autonomous  : safety-passed content is staged AND queued immediately.
supervised  : content stops at STAGED until internal approval.
client_portal: a tokenized approval link is issued; one-click approve/reject.
"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.core.context import get_context
from app.core.security import generate_portal_token, portal_token_expiry
from app.db.models import Campaign, ClientApproval, ContentItem, ScheduledPost
from app.scheduler.windows import next_optimal_slot


def stage_and_govern(db: Session, item: ContentItem, payloads: dict[str, dict],
                     region: str = "GLOBAL") -> dict:
    """Create scheduled_posts (STAGED) and apply the campaign's governance tier.

    Returns {"mode": ..., "queued": n, "approval_token": str|None}
    """
    from app.db.models import Workspace

    campaign = db.get(Campaign, item.campaign_id)
    mode = (campaign.governance_mode if campaign else "supervised") or "supervised"
    ctx = get_context()
    ws = db.get(Workspace, item.workspace_id)
    tenant_id = ctx.get("tenant_id") or (ws.tenant_id if ws else item.workspace_id)

    posts: list[ScheduledPost] = []
    for i, (platform, payload) in enumerate(payloads.items()):
        slot = next_optimal_slot(platform, item.niche, region, index=i)
        post = ScheduledPost(
            tenant_id=tenant_id,
            content_item_id=item.id,
            platform=platform,
            payload_json=payload,
            scheduled_at=slot,
            publish_status="PENDING",
            utm_link=payload.get("link", ""),
        )
        posts.append(post)
        db.add(post)

    approval_token: str | None = None
    if mode == "autonomous":
        for p in posts:
            p.publish_status = "QUEUED"
        item.status = "QUEUED"
    elif mode == "supervised":
        item.status = "STAGED"
    elif mode == "client_portal":
        item.status = "STAGED"
        token = generate_portal_token()
        db.add(ClientApproval(content_item_id=item.id, token=token, status="pending",
                              expires_at=portal_token_expiry()))
        approval_token = token
    else:
        raise ValueError(f"unknown governance mode '{mode}'")

    db.commit()
    return {"mode": mode, "staged": len(posts), "queued": sum(p.publish_status == "QUEUED" for p in posts),
            "approval_token": approval_token}


def internal_approve(db: Session, item: ContentItem) -> int:
    """Supervised-mode: internal team moves STAGED -> QUEUED."""
    if item.status not in ("STAGED", "FLAGGED", "GENERATED"):
        raise ValueError(f"cannot approve from status {item.status}")
    queued = 0
    for p in item.scheduled_posts:
        if p.publish_status in ("PENDING",):
            p.publish_status = "QUEUED"
            queued += 1
    item.status = "QUEUED"
    db.commit()
    return queued


def client_decide(db: Session, approval: ClientApproval, decision: str, feedback: str = "") -> str:
    """Client-portal decision: approve -> queue; reject -> terminal REJECTED."""
    if approval.status != "pending":
        raise ValueError(f"approval already {approval.status}")
    if time.time() > approval.expires_at:
        approval.status = "expired"
        db.commit()
        raise PermissionError("approval link expired")
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved|rejected")

    item = db.get(ContentItem, approval.content_item_id)
    approval.status, approval.client_feedback = decision, feedback
    approval.decided_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    if decision == "approved":
        return f"queued:{internal_approve(db, item)}"
    item.status = "REJECTED"
    db.commit()
    return "rejected"
