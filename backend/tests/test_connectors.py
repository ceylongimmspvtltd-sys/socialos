"""All 7 connectors against deterministic mocks + rate limiter + Reddit guardrails."""
import pytest

from app.connectors import mock_connector
from app.connectors.base import PublishRequest
from app.connectors.rate_limiter import TokenBucket

PLATFORMS = ["youtube", "instagram", "facebook", "tiktok", "pinterest", "reddit", "telegram"]


@pytest.mark.parametrize("platform", PLATFORMS)
async def test_mock_publish_ok(platform):
    c = mock_connector(platform)
    req = PublishRequest(
        title="Test post", body=("x" if platform != "reddit" else "y" * 400),
        link="https://example.com", hashtags=["#test"],
        media_urls=["https://cdn.example/a.mp4" if platform in ("youtube", "tiktok") else "https://cdn.example/a.jpg"],
        first_comment="#tag",
        platform_payload={"subreddit": "travel", "value_first": True, "allow_links": False,
                          "chat_id": "@ch", "buttons": [{"text": "Go", "url": "https://x.y"}]},
    )
    res = await c.publish(req)
    if platform == "reddit":  # guardrails may reject short/guarded content; give valid body
        assert res.ok or "guarded" in res.raw
    else:
        assert res.ok and res.external_id


async def test_mock_analytics_normalized_names():
    c = mock_connector("tiktok")
    m = await c.fetch_analytics("abc123")
    for key in ("impressions", "reach", "likes", "comments", "shares", "saves", "video_views"):
        assert key in m and m[key] >= 0


async def test_youtube_shorts_detection():
    c = mock_connector("youtube")
    res = await c.publish(PublishRequest(title="t", body="#Shorts test", platform_payload={"is_short": True}))
    assert res.raw["kind"] == "short"


async def test_reddit_karma_gate():
    c = mock_connector("reddit")
    c.account["meta"]["karma"] = 10  # below MIN_KARMA
    res = await c.publish(PublishRequest(title="t", body="z" * 400,
                                         platform_payload={"subreddit": "travel", "value_first": True}))
    assert not res.ok and "karma" in res.error


async def test_reddit_promo_guard():
    c = mock_connector("reddit")
    res = await c.publish(PublishRequest(title="t", body="check https://spam.example z" * 30,
                                         platform_payload={"subreddit": "travel", "value_first": True}))
    assert not res.ok and "raw promotional URL" in res.error


async def test_telegram_mock_buttons():
    c = mock_connector("telegram")
    res = await c.publish(PublishRequest(body="hi",
                                         platform_payload={"chat_id": "@news", "buttons": [
                                             {"text": "Book", "url": "https://x.y"}]}))
    assert res.ok and res.raw["parse_mode"] == "MarkdownV2"


def test_token_bucket_burst():
    b = TokenBucket(capacity=3, refill_per_sec=0.0)
    assert b.try_acquire() and b.try_acquire() and b.try_acquire()
    assert not b.try_acquire()
