"""Trend scoring, niche translation, EU demographics, metric normalization + PPI."""
import pytest

from app.agents.eu_demographics import market_brief, seasonal_intent, localize_hook
from app.analytics.normalizer import engagement_rate, normalize, ppi, dashboard
from app.trends.hunter import Trend, score, top_trends, translate_to_niche


def _t(name, vol, prev):
    return Trend("tiktok", name, volume=vol, prev_volume=prev)


def test_trend_classification():
    t = score([_t("emerging sound", 100_000, 20_000), _t("peaking format", 100_000, 90_000),
               _t("old meme", 50_000, 90_000)])
    phases = [x.phase for x in t]
    assert "emerging" in phases and "peaking" in phases and "declining" in phases


def test_velocity_and_saturation():
    t = _t("x", 120_000, 60_000).classify()
    assert t.velocity == 2.0
    assert 0.0 <= t.saturation_index <= 1.0


def test_niche_translation():
    angle = translate_to_niche(_t("POV room tour", 50_000, 20_000), "hospitality")
    assert "property" in angle.lower() or "reel" in angle.lower()
    assert "move now" in angle  # emerging-phase hint


async def test_top_trends_relevance():
    trends = await top_trends("salon", limit=3)
    assert len(trends) == 3
    assert all(isinstance(t.velocity, float) for t in trends)


def test_eu_market_brief_dach():
    b = market_brief("DACH", month=2)
    assert "structured" in " ".join(b["tone_rules"]) or b["priorities"][0] == "day-by-day itinerary"
    assert b["seasonal_intent"] == "summer_holiday_planning_surge"


def test_eu_seasonal_autumn():
    assert seasonal_intent(9)["intent"] == "autumn_wellness_escapes"


def test_localize_hook_dach():
    assert localize_hook("Island escape", "DACH", 2).startswith("Plan it properly:")


def test_metric_normalization_reddit():
    unified = normalize({"upvotes": 400, "comments": 50, "impressions": 8000})
    assert unified["engagements"] == 450
    assert 0 < engagement_rate(unified) < 1


def test_ppi_benchmark_relative():
    m = normalize({"impressions": 10000, "likes": 500, "comments": 50, "shares": 50})
    p = ppi(m, "hospitality", "instagram")  # bench 0.048; ER=0.06 -> ~125
    assert 80 <= p <= 200
    m_low = normalize({"impressions": 10000, "likes": 100, "comments": 10})
    assert ppi(m_low, "hospitality", "instagram") < 50


def test_utm_link():
    from app.utils.utm import build_utm_link

    link = build_utm_link("https://x.y/p", "pinterest", "organic", "c1", "rich-pin")
    assert "utm_source=pinterest" in link and "utm_campaign=c1" in link and "utm_content=rich-pin" in link
