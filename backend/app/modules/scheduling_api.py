"""Calendar / scheduling / worker control endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.niches import get_niche
from app.db.base import get_db
from app.db.models import ContentItem, ScheduledPost, Tenant
from app.modules.dep import audit, resolve_tenant
from app.scheduler.queue import get_queue
from app.scheduler.worker import publish_due
from app.schemas import CalendarEntry, RescheduleIn

router = APIRouter(prefix="/api/schedule", tags=["scheduling"])


@router.get("", response_model=list[CalendarEntry])
def calendar(from_: datetime | None = None, to: datetime | None = None,
             platform: str | None = None, tenant: Tenant = Depends(resolve_tenant),
             db: Session = Depends(get_db)):
    q = (db.query(ScheduledPost)
         .filter(ScheduledPost.tenant_id == tenant.id)
         .join(ContentItem, ScheduledPost.content_item_id == ContentItem.id))
    if from_:
        q = q.filter(ScheduledPost.scheduled_at >= from_)
    if to:
        q = q.filter(ScheduledPost.scheduled_at <= to)
    if platform:
        q = q.filter(ScheduledPost.platform == platform)
    return [CalendarEntry(id=p.id, platform=p.platform, scheduled_at=p.scheduled_at,
                          publish_status=p.publish_status,
                          title=(p.payload_json or {}).get("title", "") or p.content_item.title,
                          niche=p.content_item.niche, content_item_id=p.content_item_id,
                          external_post_id=p.external_post_id)
            for p in q.order_by(ScheduledPost.scheduled_at).limit(500)]


@router.patch("/{post_id}")
def reschedule(post_id: str, payload: RescheduleIn, tenant: Tenant = Depends(resolve_tenant),
               db: Session = Depends(get_db)):
    post = db.query(ScheduledPost).filter(ScheduledPost.id == post_id,
                                          ScheduledPost.tenant_id == tenant.id).first()
    if post is None:
        raise HTTPException(404, "scheduled post not found")
    if post.publish_status == "PUBLISHED":
        raise HTTPException(409, "cannot reschedule a published post")
    post.scheduled_at = payload.scheduled_at
    db.commit()
    audit(db, tenant.id, "post.rescheduled", "scheduled_post", post_id,
          {"scheduled_at": payload.scheduled_at.isoformat()})
    return {"id": post.id, "scheduled_at": post.scheduled_at.isoformat(), "status": post.publish_status}


@router.get("/optimal")
def optimal_windows(niche: str, region: str = "GLOBAL", platforms: str | None = None):
    from app.scheduler.windows import plan_week

    try:
        plist = [p.strip() for p in platforms.split(",")] if platforms else get_niche(niche).core_channels
        return {"niche": niche, "region": region, "week_plan": plan_week(niche, plist, region)}
    except KeyError as e:
        raise HTTPException(422, str(e))


@router.post("/worker/tick")
async def worker_tick(tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    """Force-process due posts now (the background worker also does this continuously)."""
    results = await publish_due(db)
    return {"processed": len(results), "results": results}


@router.get("/dlq")
def dead_letter_queue(tenant: Tenant = Depends(resolve_tenant)):
    q = get_queue()
    return {"dead_letters": getattr(q, "dlq", None) or "see redis stream socialos:dlq (redis backend)"}


@router.get("/week-preview")
def week_preview(niche: str = "travel", region: str = "DACH"):
    from app.scheduler.windows import plan_week

    return plan_week(niche, get_niche(niche).core_channels, region)
