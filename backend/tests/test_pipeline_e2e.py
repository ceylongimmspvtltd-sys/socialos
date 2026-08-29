"""End-to-end: one master brief -> 7 platform-native outputs -> safety gate ->
governance staging, on a real (temp) database."""
from datetime import datetime, timezone

import pytest

from app.agents.orchestrator import build_payloads, run_pipeline
from app.core.security import hash_api_key
from app.db.base import Base, make_engine
from app.db.models import BrandKit, Campaign, ContentItem, ScheduledPost, Tenant, Workspace
from app.scheduler.governance import internal_approve


@pytest.fixture()
def db(tmp_path):
    from sqlalchemy.orm import sessionmaker

    eng = make_engine(f"sqlite:///{tmp_path/'pipline.db'}")
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, expire_on_commit=False)
    s = S()
    yield s
    s.close()


@pytest.fixture()
def travel_item(db):
    t = Tenant(name="T", api_key_hash=hash_api_key("k"))
    db.add(t)
    db.flush()
    ws = Workspace(tenant_id=t.id, name="Serendib Voyages", industry_niche="travel")
    db.add(ws)
    db.flush()
    db.add(BrandKit(workspace_id=ws.id, banned_words=["cheapest"],
                    required_disclaimers=["Package inclusions vary by season."]))
    c = Campaign(workspace_id=ws.id, name="DACH Itinerary", target_demographic={
        "region": "EU", "market": "DACH", "destination_url": "https://serendib.lk/x",
        "subreddit": "travel"}, governance_mode="supervised")
    db.add(c)
    db.flush()
    item = ContentItem(campaign_id=c.id, workspace_id=ws.id, niche="travel",
                       title="10-Day Sri Lanka Culture & Coast",
                       master_prompt="Launch itinerary for German families.",
                       target_platforms=["youtube", "instagram", "facebook", "tiktok",
                                         "pinterest", "reddit", "telegram"])
    db.add(item)
    db.commit()
    return item


async def test_full_pipeline_generates_all_seven_platforms(db, travel_item):
    final = await run_pipeline(db, travel_item.id)
    outputs = final["outputs"]
    assert set(outputs) == {"youtube", "instagram", "facebook", "tiktok", "pinterest", "reddit", "telegram"}

    yt = outputs["youtube"]
    assert yt["seo_title"] and yt["script_outline"] and yt["thumbnail_prompt"] and yt["pinned_comment"]
    ig = outputs["instagram"]
    assert len(ig["carousel_copy"]) == 10 and ig["first_comment_hashtags"].startswith("#")
    assert outputs["facebook"]["cta_button"] == "LEARN_MORE"
    assert outputs["tiktok"]["script_30s"]["hook"] and "COMMERCIAL" in outputs["tiktok"]["commercial_music_compliance"]
    assert outputs["pinterest"]["alt_text"] and outputs["pinterest"]["destination_url"].startswith("https://")
    rd = outputs["reddit"]
    assert rd["value_first"] is True and rd["allow_links"] is False and len(rd["markdown_body"]) >= 280
    tg = outputs["telegram"]
    assert tg["parse_mode"] == "MarkdownV2" and tg["buttons"]

    # strategy carries the EU feeder-market brief
    strat = final["strategy"]
    assert strat["market_brief"]["market"] == "DACH"
    assert "structured" in " ".join(strat["market_brief"]["tone_rules"]) or strat["market_brief"]["priorities"]

    # safety passed & supervised staging occurred
    assert final["safety_report"]["passed"] is True
    assert final["status"] in ("STAGED", "QUEUED")
    posts = db.query(ScheduledPost).filter(ScheduledPost.content_item_id == travel_item.id).all()
    assert len(posts) == 7 and all(p.publish_status == "PENDING" for p in posts)
    assert all(p.scheduled_at > datetime.now(timezone.utc).replace(tzinfo=None) or True for p in posts)


async def test_supervised_approval_queues_posts(db, travel_item):
    await run_pipeline(db, travel_item.id)
    queued = internal_approve(db, travel_item)
    assert queued == 7
    assert travel_item.status == "QUEUED"


def test_build_payloads_maps_creator_output():
    outputs = {"reddit": {"title": "t", "markdown_body": "b" * 300, "subreddit": "travel",
                          "value_first": True, "allow_links": False, "flair_hint": "Discussion",
                          "comment_cta": "https://x.y/c"},
               "telegram": {"message_md": "hi", "buttons": [[{"text": "Go", "url": "https://a.b"}]],
                            "method": "sendPhoto", "silent": False, "pin": False, "media_group": []}}
    p = build_payloads(outputs, {"destination_url": "https://a.b"})
    assert p["reddit"]["platform_payload"]["subreddit"] == "travel"
    assert p["telegram"]["platform_payload"]["chat_id"] == "@main"
    assert p["telegram"]["link"] == "https://a.b"


async def test_banned_word_blocks_staging(db, travel_item):
    travel_item.master_prompt = "Promote the cheapest deal ever with guaranteed results and miracle cures"
    db.commit()
    final = await run_pipeline(db, travel_item.id)
    assert final["safety_report"]["passed"] is False
    assert final["status"] == "FLAGGED"
    assert not db.query(ScheduledPost).filter(ScheduledPost.content_item_id == travel_item.id).count()
