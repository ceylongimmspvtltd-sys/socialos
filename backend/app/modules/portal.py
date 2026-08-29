"""Client approval portal — secure tokenized links, one-click approve/reject (tier 3)."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import ClientApproval, ContentItem
from app.modules.dep import audit
from app.scheduler.governance import client_decide
from app.schemas import PortalDecision

router = APIRouter(tags=["client-portal"])


def _load(db: Session, token: str) -> ClientApproval:
    approval = db.query(ClientApproval).filter(ClientApproval.token == token).first()
    if approval is None:
        raise HTTPException(404, "invalid portal link")
    if approval.status == "pending" and time.time() > approval.expires_at:
        approval.status = "expired"
        db.commit()
    return approval


@router.get("/portal/{token}")
def portal_view(token: str, db: Session = Depends(get_db)):
    approval = _load(db, token)
    if not approval.viewed and approval.status == "pending":
        approval.viewed = True
        db.commit()
    item = db.get(ContentItem, approval.content_item_id)
    outputs = item.outputs_json or {}
    preview = {}
    for platform, payload in outputs.items():
        texty = {k: v for k, v in payload.items() if isinstance(v, (str, int, float))}
        preview[platform] = texty
    return {
        "approval": {"status": approval.status, "expires_at": approval.expires_at},
        "campaign": {"title": item.title, "niche": item.niche},
        "safety": item.safety_report or {},
        "content_preview": preview,
        "actions": ["POST /portal/{token}/decision"] if approval.status == "pending" else [],
    }


@router.post("/portal/{token}/decision")
def portal_decide(token: str, payload: PortalDecision, db: Session = Depends(get_db)):
    approval = _load(db, token)
    try:
        outcome = client_decide(db, approval, payload.decision, payload.feedback)
    except (ValueError, PermissionError) as e:
        raise HTTPException(409, str(e))
    item = db.get(ContentItem, approval.content_item_id)
    audit(db, item.workspace_id, f"portal.{payload.decision}", "content_item", item.id,
          {"feedback": payload.feedback[:500]})
    return {"token": token, "decision": payload.decision, "outcome": outcome,
            "content_status": item.status}
