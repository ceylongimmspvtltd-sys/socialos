"""Trend intelligence + EU demographic endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.eu_demographics import market_brief, SCHOOL_HOLIDAYS, seasonal_intent
from app.core.config import settings
from app.db.base import get_db
from app.db.models import Tenant, TrendSignal
from app.modules.dep import resolve_tenant
from app.trends.hunter import top_trends, translate_to_niche
from app.schemas import TranslateIn

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("")
async def trends(niche: str = "travel", limit: int = 8, persist: bool = False,
                 tenant: Tenant = Depends(resolve_tenant), db: Session = Depends(get_db)):
    try:
        scored = (await top_trends(niche, limit=limit))
    except KeyError as e:
        from fastapi import HTTPException

        raise HTTPException(422, str(e))
    out = []
    for t in scored:
        if persist:
            db.add(TrendSignal(source=t.source, name=t.name, url=t.url, volume=t.volume,
                               prev_volume=t.prev_volume, velocity=t.velocity,
                               saturation_index=t.saturation_index, phase=t.phase, niche=niche))
        out.append({"source": t.source, "name": t.name, "phase": t.phase, "velocity": t.velocity,
                    "saturation_index": t.saturation_index, "volume": t.volume,
                    "niche_angle": translate_to_niche(t, niche)})
    if persist:
        db.commit()
    return {"niche": niche, "mode": "live" if settings.trends_live_fetch else "snapshot",
            "gdpr": "aggregated public signals only — no PII", "trends": out}


@router.post("/translate")
def translate(payload: TranslateIn, tenant: Tenant = Depends(resolve_tenant)):
    from app.trends.hunter import Trend

    t = Trend(source=payload.source, name=payload.trend_name, volume=1000, prev_volume=700)
    t.classify()
    return {"trend": payload.trend_name, "phase": t.phase, "velocity": t.velocity,
            "angle": translate_to_niche(t, payload.niche)}


@router.get("/eu-demographics")
def eu_demographics(market: str = "DACH", tenant: Tenant = Depends(resolve_tenant)):
    month = datetime.now(timezone.utc).month
    return {
        "market_brief": market_brief(market, month),
        "seasonal_intent_now": seasonal_intent(month),
        "school_holidays": {k: v for k, v in SCHOOL_HOLIDAYS.items() if k == market.upper()} or SCHOOL_HOLIDAYS,
        "markets_available": ["UK", "DACH", "FR", "NORDICS", "BENELUX"],
        "gdpr_note": "Zero individual tracking; macro keyword volumes + anonymized aggregates only.",
    }
