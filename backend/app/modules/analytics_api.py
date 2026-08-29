"""Unified analytics: metric sync + dashboard + UTM audit."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.normalizer import dashboard, upsert_analytics
from app.connectors import build_connector, get_workspace_account
from app.db.base import get_db
from app.db.models import PostAnalytics, ScheduledPost, Tenant
from app.modules.dep import audit, resolve_tenant
from app.analytics.normalizer import upsert_analytics
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.post("/sync")
async def sync(workspace_id: str | None = None, tenant: Tenant = Depends(resolve_tenant),
               db: Session = Depends(get_db)):
    """Pull platform metrics for published posts (mock connectors -> simulated telemetry)
    and recompute normalized metrics + PPI."""
    q = (db.query(ScheduledPost)
         .filter(ScheduledPost.tenant_id == tenant.id, ScheduledPost.publish_status == "PUBLISHED"))
    if workspace_id:
        q = q.filter(ScheduledPost.payload_json.isnot(None))
    synced = 0
    for post in q.all():
        if workspace_id and post.content_item.workspace_id != workspace_id:
            continue
        account = get_workspace_account(db, post.content_item.workspace_id, post.platform)
        connector = build_connector(post.platform, account)
        raw = await connector.fetch_analytics(post.external_post_id or post.id)
        upsert_analytics(db, post, raw)
        synced += 1
    audit(db, tenant.id, "analytics.sync", detail={"synced": synced})
    return {"synced": synced}


@router.get("/dashboard")
def unified_dashboard(tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    return dashboard(db, tenant.id)


@router.get("/posts")
def per_post_metrics(tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    rows = (db.query(ScheduledPost, PostAnalytics)
            .join(PostAnalytics, PostAnalytics.scheduled_post_id == ScheduledPost.id)
            .filter(ScheduledPost.tenant_id == tenant.id).all())
    return [{"platform": p.platform, "post_id": p.id, "impressions": a.impressions,
             "engagements": a.engagements, "er": a.engagement_rate, "ppi": a.ppi,
             "raw": a.raw_metrics} for p, a in rows]
