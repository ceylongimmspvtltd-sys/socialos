"""OrchestratorAgent — the Master Controller.

Builds and runs the multi-agent graph:

    trend_hunt -> niche_strategy -> multimodal_creator -> brand_safety -> stage_govern

Persists outputs, safety report, status transitions and scheduled posts.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.agents.brand_safety import BrandSafetyGatekeeper
from app.agents.graph import END, START, Graph
from app.agents.multimodal_creator import MultiModalCreatorAgent
from app.agents.niche_strategy import NicheStrategyAgent
from app.agents.state import PipelineState, TrendRef
from app.core.context import get_context
from app.db.models import (AuditLog, BrandKit, Campaign, ContentItem, Workspace)
from app.scheduler.governance import stage_and_govern
from app.trends.hunter import top_trends, translate_to_niche

log = logging.getLogger("socialos.orchestrator")


def build_payloads(outputs: dict, demographic: dict) -> dict[str, dict]:
    """Map creator outputs -> connector-ready publish payloads per platform."""
    payloads: dict[str, dict] = {}
    utm_dest = demographic.get("destination_url", "")

    yt = outputs.get("youtube")
    if yt:
        payloads["youtube"] = {
            "title": yt["seo_title"], "body": yt["description"], "link": utm_dest,
            "hashtags": [f"#{t}" for t in yt["tags"]], "first_comment": yt["pinned_comment"],
            "media_urls": [], "platform_payload": {"category_id": yt["category_id"],
                                                   "is_short": False},
        }
    ig = outputs.get("instagram")
    if ig:
        payloads["instagram"] = {
            "title": "", "body": ig["caption"], "link": utm_dest,
            "media_urls": [], "hashtags": ig["first_comment_hashtags"].split(),
            "first_comment": ig["first_comment_hashtags"],
            "platform_payload": {"media_type": "REELS", "location_id": None},
        }
    fb = outputs.get("facebook")
    if fb:
        payloads["facebook"] = {
            "title": "", "body": fb["post_copy"], "link": fb["link"], "media_urls": [],
            "hashtags": fb["hashtags"].split(), "first_comment": "",
            "platform_payload": {"cta_button": fb["cta_button"],
                                 "geo_targeting": fb["geo_targeting"],
                                 "scheduled_publish_time": None},
        }
    tk = outputs.get("tiktok")
    if tk:
        payloads["tiktok"] = {
            "title": tk["script_30s"]["hook"], "body": tk["caption"], "link": utm_dest,
            "media_urls": [], "hashtags": [], "first_comment": "",
            "platform_payload": {"allow_duet": tk["allow_duet"], "allow_stitch": tk["allow_stitch"],
                                 "cover_ts_ms": tk["cover_ts_ms"], "is_short": True},
        }
    pin = outputs.get("pinterest")
    if pin:
        payloads["pinterest"] = {
            "title": pin["pin_title"], "body": pin["pin_description"], "link": pin["destination_url"],
            "media_urls": [], "hashtags": [], "first_comment": "",
            "platform_payload": {"board_id": pin.get("board_hint", ""), "alt_text": pin["alt_text"]},
        }
    rd = outputs.get("reddit")
    if rd:
        payloads["reddit"] = {
            "title": rd["title"], "body": rd["markdown_body"], "link": rd.get("comment_cta", ""),
            "media_urls": [], "hashtags": [], "first_comment": rd.get("comment_cta", ""),
            "platform_payload": {"subreddit": rd["subreddit"], "kind": "self",
                                 "value_first": rd["value_first"], "allow_links": rd["allow_links"],
                                 "flair": rd["flair_hint"]},
        }
    tg = outputs.get("telegram")
    if tg:
        btn = (tg.get("buttons") or [[{"text": "Open", "url": utm_dest}]])[0]
        payloads["telegram"] = {
            "title": "", "body": tg["message_md"], "link": btn[0].get("url", utm_dest),
            "media_urls": tg.get("media_group", []), "hashtags": [], "first_comment": "",
            "platform_payload": {"chat_id": demographic.get("telegram_channel", "@main"),
                                 "buttons": btn, "method": tg["method"], "silent": tg["silent"],
                                 "pin": tg["pin"]},
        }
    return payloads


class TrendHuntNode:
    """Trend Hunter agent: fetch signals, score, niche-translate, attach refs."""

    name = "trend_hunt"

    async def __call__(self, state: PipelineState | dict) -> dict:
        s = state if isinstance(state, PipelineState) else PipelineState(**state)
        refs: list[TrendRef] = []
        try:
            for t in await top_trends(s.niche, limit=3):
                refs.append(TrendRef(name=t.name, source=t.source, phase=t.phase,
                                     angle=translate_to_niche(t, s.niche)))
        except Exception as e:  # noqa: BLE001 — trends are enrichment, never blocking
            log.warning("trend hunt degraded: %s", e)
        out = s.model_dump()
        out["trends"] = [r.model_dump() for r in refs]
        return out


class StageGovernNode:
    """Post-safety node: persist + stage + apply governance tier."""

    name = "stage_govern"

    def __init__(self, db: Session):
        self.db = db

    async def __call__(self, state: PipelineState | dict) -> dict:
        s = state if isinstance(state, PipelineState) else PipelineState(**state)
        item = self.db.get(ContentItem, s.content_item_id)
        if item is None:
            out = s.model_dump()
            out["errors"].append("content item vanished during pipeline")
            out["status"] = "FAILED"
            return out

        item.outputs_json = s.outputs
        item.safety_report = s.safety_report
        item.strategy_json = s.strategy
        item.trends_used = [getattr(t, "name", None) or t.get("name") for t in s.trends]
        item.status = s.status  # GENERATED | FLAGGED
        self.db.commit()

        region = (s.target_demographic.get("region") or "GLOBAL")
        result: dict = {"mode": "manual", "staged": 0, "queued": 0, "approval_token": None}
        if s.status == "GENERATED":
            payloads = build_payloads(s.outputs, s.target_demographic)
            result = stage_and_govern(self.db, item, payloads, region=region)

        self.db.add(AuditLog(
            tenant_id=(get_context().get("tenant_id") or item.workspace_id),
            actor="orchestrator", action="pipeline.completed",
            entity_type="content_item", entity_id=item.id,
            detail={"safety": s.safety_report.get("passed"), "governance": result},
        ))
        self.db.commit()

        out = s.model_dump()
        out["governance"] = result
        out["status"] = item.status
        return out


def build_graph(db: Session) -> Graph:
    g = Graph()
    g.add_node("trend_hunt", TrendHuntNode())
    g.add_node("niche_strategy", NicheStrategyAgent())
    g.add_node("multimodal_creator", MultiModalCreatorAgent())
    g.add_node("brand_safety", lambda s: BrandSafetyGatekeeper(_brand_kit_of(db, s))(s))
    g.add_node("stage_govern", StageGovernNode(db))
    g.set_entry_point("trend_hunt")
    g.add_edge("trend_hunt", "niche_strategy")
    g.add_edge("niche_strategy", "multimodal_creator")
    g.add_edge("multimodal_creator", "brand_safety")
    g.add_conditional_edges(
        "brand_safety",
        router=lambda s: "stage" if s.get("status") != "FLAGGED" else "halt",
        mapping={"stage": "stage_govern", "halt": END},
    )
    g.add_edge("stage_govern", END)
    return g


def _brand_kit_of(db: Session, state) -> dict | None:
    s = state if isinstance(state, PipelineState) else PipelineState(**state)
    kit = db.query(BrandKit).join(Workspace, BrandKit.workspace_id == Workspace.id) \
        .filter(Workspace.id == s.workspace_id).first()
    if kit is None:
        return None
    return {"banned_words": kit.banned_words, "required_disclaimers": kit.required_disclaimers,
            "negative_prompt_constraints": kit.negative_prompt_constraints}


async def run_pipeline(db: Session, content_item) -> dict:
    """Entry point: execute the full agent graph for a content item (id or ORM object)."""
    item = content_item if hasattr(content_item, "master_prompt") else db.get(ContentItem, content_item)
    if item is None:
        raise ValueError(f"content item {content_item} not found")
    campaign = db.get(Campaign, item.campaign_id)

    state = PipelineState(
        content_item_id=item.id, campaign_id=item.campaign_id, workspace_id=item.workspace_id,
        tenant_id=_tenant_of(db, item), niche=item.niche, master_prompt=item.master_prompt,
        title=item.title, source_asset_url=item.source_asset_url,
        target_platforms=item.target_platforms or [],
        target_demographic=(campaign.target_demographic if campaign else {}) or {},
        language=item.language, governance_mode=(campaign.governance_mode if campaign else "supervised"),
    )

    compiled = build_graph(db).compile()
    final = await compiled.ainvoke(state.model_dump())

    item = db.get(ContentItem, item.id)
    item.status = final.get("status", item.status)
    db.commit()
    return final


def _tenant_of(db: Session, item: ContentItem) -> str:
    ws = db.get(Workspace, item.workspace_id)
    return ws.tenant_id if ws else ""
