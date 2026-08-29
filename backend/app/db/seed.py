"""Demo seed — a Sri Lankan multi-brand agency operating all 5 verticals,
with EU feeder-market targeting for travel. Runs the full agent pipeline so the
dashboard, calendar, governance and analytics are populated end-to-end."""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents.orchestrator import run_pipeline
from app.core.security import hash_api_key
from app.db.models import (BrandKit, Campaign, ContentItem, ScheduledPost, Tenant, Workspace)
from app.scheduler.governance import internal_approve

log = logging.getLogger("socialos.seed")

DEMO_API_KEY = "demo-key"


def run_coro_sync(coro):
    """Run a coroutine from synchronous code — safe both outside AND inside a
    running event loop (FastAPI lifespan). In the latter case the coroutine runs
    on a private loop in a private thread, because run_until_complete() cannot
    nest inside uvicorn's loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: dict = {}

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            box["v"] = loop.run_until_complete(coro)
        except BaseException as exc:  # noqa: BLE001 — re-raised on caller thread
            box["e"] = exc
        finally:
            loop.close()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()
    if "e" in box:
        raise box["e"]
    return box.get("v")


def seed_if_empty(db: Session) -> bool:
    if db.query(Tenant).count() > 0:
        return False
    seed(db)
    return True


def seed(db: Session) -> dict:
    tenant = Tenant(name="C Tech Digital — Demo Agency", plan="enterprise",
                    api_key_hash=hash_api_key(DEMO_API_KEY))
    db.add(tenant)
    db.flush()

    spaces = [
        ("hospitality", "Coral Bay Resort — Negombo",
         {"colors_json": {"primary": "#0E4D64", "secondary": "#F2A65A", "accent": "#FFF3E2"},
          "fonts_json": {"heading": "Playfair Display", "body": "Inter", "hierarchy": "H1 48/56, H2 32/40"},
          "tone_embeddings": {"warm": 0.9, "luxurious": 0.6, "experiential": 0.95},
          "banned_words": ["cheap", "discount spam"],
          "required_disclaimers": ["Rates subject to seasonal availability."],
          "logo_urls": {"light": "s3://dam/coralbay/light.svg", "dark": "s3://dam/coralbay/dark.svg",
                        "mono": "s3://dam/coralbay/mono.svg"}},
         "Summer Escape Campaign — EU winter market",
         "Promote the lagoon-view suites + seafood dining experience to European couples escaping winter. Golden hour reels, chef tables, airport-proximity angle.",
         {"region": "EU", "market": "UK", "destination_url": "https://coralbay.lk/summer",
          "location": "Negombo, Sri Lanka"}, "supervised", ["instagram", "facebook", "tiktok", "pinterest"]),
        ("travel", "Serendib Voyages — EU Inbound Specialists",
         {"colors_json": {"primary": "#123D5B", "secondary": "#4ECDC4", "accent": "#FFD166"},
          "fonts_json": {"heading": "DM Serif Display", "body": "Source Sans 3"},
          "tone_embeddings": {"experiential": 0.9, "formal": 0.5, "technical": 0.4},
          "banned_words": ["cheapest"],
          "required_disclaimers": ["Package inclusions vary by season."],
          "logo_urls": {"light": "s3://dam/serendib/light.svg", "dark": "s3://dam/serendib/dark.svg"}},
         "DACH 10-Day Culture & Coast Itinerary",
         "Launch the 10-day Sri Lanka culture + coast itinerary for German-speaking families: structured day-by-day plan, safety and pricing transparency, autumn wellness add-on.",
         {"region": "EU", "market": "DACH", "destination_url": "https://serendibvoyages.lk/dach-10day",
          "subreddit": "travel"}, "client_portal", ["pinterest", "youtube", "instagram", "reddit", "facebook"]),
        ("salon", "Glow Studio — Colombo",
         {"colors_json": {"primary": "#2D1B4E", "secondary": "#FF6EC7", "accent": "#FFE1FF"},
          "fonts_json": {"heading": "Poppins", "body": "Nunito"},
          "tone_embeddings": {"witty": 0.7, "warm": 0.8},
          "banned_words": ["surgery", "medical-grade"],
          "required_disclaimers": ["Patch test required 48h before colour services."],
          "logo_urls": {"light": "s3://dam/glow/light.svg"}},
         "Keratin Glow-Up Week",
         "Before/after keratin transformations trending audio; fill cancelled afternoon slots with Telegram flash alerts; balayage trend showcase.",
         {"region": "LK", "destination_url": "https://glowstudio.lk/book",
          "telegram_channel": "@glowstudio_alerts"}, "autonomous", ["instagram", "tiktok", "facebook", "telegram"]),
        ("production", "Ceylon Frames — Film & Commercials",
         {"colors_json": {"primary": "#101418", "secondary": "#E50914", "accent": "#8A8F98"},
          "fonts_json": {"heading": "Bebas Neue", "body": "Roboto Mono"},
          "tone_embeddings": {"technical": 0.95, "formal": 0.5},
          "banned_words": ["cheap gear"],
          "required_disclaimers": [],
          "logo_urls": {"mono": "s3://dam/ceylonframes/mono.svg"}},
         "Monsoon Wedding Film Showreel",
         "4K monsoon wedding showreel + BTS lighting breakdown for B2B agency producers; YouTube long-form + Reddit craft discussion.",
         {"region": "GLOBAL", "destination_url": "https://ceylonframes.lk/showreel",
          "subreddit": "videography"}, "supervised", ["youtube", "reddit", "instagram", "pinterest"]),
        ("ecom", "Island Kart — Curated LK Finds",
         {"colors_json": {"primary": "#0F9D58", "secondary": "#4285F4", "accent": "#FBBC05"},
          "fonts_json": {"heading": "Montserrat", "body": "Open Sans"},
          "tone_embeddings": {"witty": 0.8, "warm": 0.5},
          "banned_words": ["guaranteed results"],
          "required_disclaimers": ["Prices incl. VAT where applicable."],
          "logo_urls": {"light": "s3://dam/islandkart/light.svg"}},
         "Ceylon Cinnamon Launch",
         "Launch Ceylon cinnamon gift packs with problem/solution hooks, shoppable Pinterest rich pins and TikTok demo reels.",
         {"region": "GLOBAL", "destination_url": "https://islandkart.lk/cinnamon",
          "subreddit": "ecommerce"}, "supervised", ["tiktok", "pinterest", "instagram", "facebook", "reddit"]),
    ]

    created = {"workspaces": [], "campaigns": [], "content_items": []}
    for niche, name, kit, camp_name, brief, demo, gov, platforms in spaces:
        ws = Workspace(tenant_id=tenant.id, name=name, industry_niche=niche,
                       settings={"timezone": "Asia/Colombo", "governance_default": gov})
        db.add(ws)
        db.flush()
        db.add(BrandKit(workspace_id=ws.id, **kit))
        campaign = Campaign(workspace_id=ws.id, name=camp_name, objective="conversions",
                            target_demographic=demo, governance_mode=gov,
                            start_date=datetime.now(timezone.utc),
                            end_date=datetime.now(timezone.utc) + timedelta(days=30),
                            budget=2500)
        db.add(campaign)
        db.flush()
        item = ContentItem(campaign_id=campaign.id, workspace_id=ws.id, niche=niche,
                           title=camp_name, master_prompt=brief, target_platforms=platforms)
        db.add(item)
        db.commit()
        created["workspaces"].append(name)
        created["campaigns"].append(camp_name)

        # run the full agent graph (loop-safe: works inside uvicorn's lifespan too)
        try:
            run_coro_sync(run_pipeline(db, item.id))
        except Exception:  # noqa: BLE001 — demo must never hard-fail
            log.exception("pipeline failed for %s", camp_name)
            db.rollback()
        created["content_items"].append(item.id)

    _publish_history(db)
    db.commit()
    return created


def _publish_history(db: Session) -> None:
    """Approve supervised items; backdate + publish due posts for live analytics demo.
    Client-portal items intentionally stay STAGED with a pending tokenized approval."""
    from app.db.models import Campaign

    for item in db.query(ContentItem).all():
        campaign = db.get(Campaign, item.campaign_id)
        if item.status == "STAGED" and campaign.governance_mode == "supervised":
            try:
                internal_approve(db, item)
            except ValueError:
                db.rollback()
    now = datetime.now(timezone.utc)
    for post in db.query(ScheduledPost).filter(ScheduledPost.publish_status == "QUEUED").all():
        post.scheduled_at = now - timedelta(minutes=5)
    db.commit()
    try:
        run_coro_sync(_sync_all(db))
    except Exception:  # noqa: BLE001
        log.exception("demo publish failed")


async def _sync_all(db: Session) -> None:
    from app.analytics.normalizer import upsert_analytics
    from app.connectors import build_connector, get_workspace_account
    from app.scheduler.worker import publish_due

    await publish_due(db)
    for post in db.query(ScheduledPost).filter(ScheduledPost.publish_status == "PUBLISHED").all():
        account = get_workspace_account(db, post.content_item.workspace_id, post.platform)
        connector = build_connector(post.platform, account)
        raw = await connector.fetch_analytics(post.external_post_id or post.id)
        upsert_analytics(db, post, raw)
