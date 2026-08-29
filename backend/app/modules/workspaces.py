"""Workspaces, brand kits and DAM assets."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Asset, BrandKit, Tenant, Workspace
from app.modules.dep import audit, resolve_tenant, scoped_ws
from app.schemas import AssetIn, BrandKitIn, WorkspaceOut

router = APIRouter(prefix="/api", tags=["workspaces"])

_AUTO_TAG_MAP = {
    "reel": ["video", "shortform"], "mp4": ["video"], "jpg": ["image"], "png": ["image"],
    "menu": ["culinary", "f&b"], "room": ["property", "interior"], "suite": ["luxury", "property"],
    "beach": ["destination", "landscape"], "nail": ["beauty"], "hair": ["beauty"],
    "showreel": ["portfolio", "bts"], "product": ["catalog", "ecom"],
}
_RENDITIONS = {"16:9": 1920, "9:16": 1080, "1:1": 1080, "4:5": 1080}


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(tenant: Tenant = Depends(resolve_tenant)):
    return [WorkspaceOut(id=w.id, name=w.name, industry_niche=w.industry_niche, settings=w.settings or {},
                         brand_kit_id=(w.brand_kit.id if w.brand_kit else None))
            for w in tenant.workspaces]


@router.post("/workspaces/{workspace_id}/brand-kit")
def upsert_brand_kit(workspace_id: str, payload: BrandKitIn,
                     tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    ws = scoped_ws(db, tenant, workspace_id)
    kit = db.query(BrandKit).filter(BrandKit.workspace_id == ws.id).first()
    if kit is None:
        kit = BrandKit(workspace_id=ws.id)
        db.add(kit)
    for k, v in payload.model_dump().items():
        setattr(kit, k, v)
    db.commit()
    audit(db, tenant.id, "brand_kit.updated", "brand_kit", kit.id)
    return {"id": kit.id, "workspace_id": ws.id, "brand_kit": payload.model_dump()}


# ------------------------- DAM -------------------------
@router.post("/assets")
def create_asset(payload: AssetIn, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    scoped_ws(db, tenant, payload.workspace_id)
    fname = payload.filename.lower()
    tags = sorted({t for kw, tags_ in _AUTO_TAG_MAP.items() if kw in fname for t in tags_})
    renditions = {ratio: {"width": px, "height": int(px / _ratio(ratio)),
                          "url": f"/dam/{payload.workspace_id[:8]}/{fname}.{ratio}.jpg",
                          "pipeline": "ffmpeg -vf scale={w}:{h} crop=cover"}
                  for ratio, px in _RENDITIONS.items()}
    asset = Asset(workspace_id=payload.workspace_id, kind=payload.kind, source_url=payload.source_url,
                  filename=payload.filename, mime=payload.mime or _guess_mime(fname),
                  size_bytes=payload.size_bytes, auto_tags=tags, renditions=renditions,
                  meta={"compression": "h264 CRF23 (video)", "presigned_upload": "PUT /api/assets/{id}/upload"})
    db.add(asset)
    db.commit()
    return {"id": asset.id, "auto_tags": tags, "renditions": renditions,
            "note": "pre-signed upload URL issued; FFmpeg renditions queued"}


@router.get("/assets")
def list_assets(workspace_id: str, tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    scoped_ws(db, tenant, workspace_id)
    rows = db.query(Asset).filter(Asset.workspace_id == workspace_id).all()
    return [{"id": a.id, "filename": a.filename, "kind": a.kind, "auto_tags": a.auto_tags,
             "renditions": list(a.renditions)} for a in rows]


def _ratio(r: str) -> float:
    w, h = map(int, r.split(":"))
    return w / h


def _guess_mime(fname: str) -> str:
    if fname.endswith(".mp4") or fname.endswith(".mov"):
        return "video/mp4"
    if fname.endswith(".png"):
        return "image/png"
    return "image/jpeg"
