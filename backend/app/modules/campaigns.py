"""Campaigns + the multi-agent content pipeline + governance actions."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_pipeline
from app.db.base import get_db
from app.db.models import Campaign, ContentItem, ScheduledPost, Tenant, Workspace
from app.modules.dep import audit, resolve_tenant, scoped_ws
from app.scheduler.governance import internal_approve
from app.schemas import CampaignIn, CampaignOut, ContentOut

router = APIRouter(prefix="/api", tags=["campaigns"])


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
async def create_campaign(payload: CampaignIn, background: BackgroundTasks,
                          tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    ws = scoped_ws(db, tenant, payload.workspace_id)
    if ws.industry_niche != payload.niche:
        raise HTTPException(422, f"workspace niche is '{ws.industry_niche}', campaign says '{payload.niche}'")
    campaign = Campaign(workspace_id=ws.id, name=payload.name, objective=payload.objective,
                        target_demographic=payload.target_demographic,
                        governance_mode=payload.governance_mode, budget=payload.budget)
    db.add(campaign)
    db.flush()
    item = ContentItem(campaign_id=campaign.id, workspace_id=ws.id, niche=payload.niche,
                       title=payload.title or payload.name, master_prompt=payload.master_prompt,
                       source_asset_url=payload.source_asset_url,
                       target_platforms=payload.target_platforms, language=payload.language,
                       status="GENERATING")
    db.add(item)
    db.commit()
    audit(db, tenant.id, "campaign.created", "campaign", campaign.id, {"item": item.id})
    if payload.run_now:
        background.add_task(_safe_pipeline, item.id)
    return CampaignOut(id=campaign.id, workspace_id=ws.id, name=campaign.name,
                       objective=campaign.objective, governance_mode=campaign.governance_mode,
                       status=campaign.status, target_demographic=campaign.target_demographic,
                       content_item_ids=[item.id])


def _safe_pipeline(item_id: str) -> None:
    import asyncio

    from app.db.base import SessionLocal

    db = SessionLocal()
    try:
        asyncio.run(run_pipeline(db, item_id))
    except Exception as e:  # noqa: BLE001
        item = db.get(ContentItem, item_id)
        if item:
            item.status = "FAILED"
            db.commit()
        raise RuntimeWarning(f"pipeline failed: {e}")
    finally:
        db.close()


@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(workspace_id: str | None = None, tenant: Tenant = Depends(resolve_tenant),
                   db: Session = Depends(get_db)):
    q = db.query(Campaign).join(Workspace, Campaign.workspace_id == Workspace.id) \
        .filter(Workspace.tenant_id == tenant.id)
    if workspace_id:
        q = q.filter(Campaign.workspace_id == workspace_id)
    out = []
    for c in q.all():
        out.append(CampaignOut(id=c.id, workspace_id=c.workspace_id, name=c.name,
                               objective=c.objective, governance_mode=c.governance_mode,
                               status=c.status, target_demographic=c.target_demographic,
                               content_item_ids=[i.id for i in c.content_items]))
    return out


@router.get("/content/{item_id}", response_model=ContentOut)
def get_content(item_id: str, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    item = _scoped_item(db, tenant, item_id)
    posts = [{"id": p.id, "platform": p.platform, "scheduled_at": p.scheduled_at.isoformat(),
              "publish_status": p.publish_status, "external_post_id": p.external_post_id}
             for p in item.scheduled_posts]
    approval = next((a for a in item.approvals if a.status == "pending"), None)
    return ContentOut(id=item.id, campaign_id=item.campaign_id, workspace_id=item.workspace_id,
                      niche=item.niche, title=item.title, status=item.status,
                      outputs_json=item.outputs_json or {}, safety_report=item.safety_report or {},
                      strategy_json=item.strategy_json or {}, trends_used=item.trends_used or [],
                      platforms=list((item.outputs_json or {}).keys()), scheduled_posts=posts,
                      governance={"approval_token": approval.token if approval else None,
                                  "awaiting": approval is not None},
                      created_at=item.created_at)


@router.post("/content/{item_id}/run")
async def run_content(item_id: str, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    item = _scoped_item(db, tenant, item_id)
    item.status = "GENERATING"
    db.commit()
    final = await run_pipeline(db, item.id)
    return {"id": item.id, "status": final.get("status"), "platforms": list(final.get("outputs", {})),
            "safety": final.get("safety_report", {}).get("passed"), "governance": final.get("governance", {})}


@router.post("/content/{item_id}/approve")
def approve_content(item_id: str, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    item = _scoped_item(db, tenant, item_id)
    try:
        queued = internal_approve(db, item)
    except ValueError as e:
        raise HTTPException(409, str(e))
    audit(db, tenant.id, "content.approved_internal", "content_item", item.id, {"queued": queued})
    return {"id": item.id, "status": item.status, "queued": queued}


def _scoped_item(db: Session, tenant: Tenant, item_id: str) -> ContentItem:
    item = db.query(ContentItem).join(Workspace, ContentItem.workspace_id == Workspace.id) \
        .filter(ContentItem.id == item_id, Workspace.tenant_id == tenant.id).first()
    if item is None:
        raise HTTPException(404, "content item not found")
    return item
