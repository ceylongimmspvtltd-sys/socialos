"""Cross-network metric normalization + Post Performance Index (PPI) closed loop.

Unifies platform-native metrics into one schema, computes engagement rate and a
benchmark-relative PPI which the scheduler feeds back as format weights.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.niches import get_niche
from app.db.models import PostAnalytics, ScheduledPost

# platform-native -> unified
UNIFIED_KEYS = ("impressions", "reach", "likes", "comments", "shares", "saves",
                "video_views", "clicks", "upvotes", "forwards", "views")


def normalize(raw: dict) -> dict:
    """Map platform-native names into the unified schema."""
    u = {
        "impressions": raw.get("impressions", 0),
        "reach": raw.get("reach", 0) or int(raw.get("impressions", 0) * 0.7),
        "engagements": (raw.get("likes", 0) + raw.get("comments", 0) + raw.get("shares", 0)
                        + raw.get("saves", 0) + raw.get("upvotes", 0) + raw.get("forwards", 0)),
        "clicks": raw.get("clicks", 0) or raw.get("outbound_clicks", 0),
        "shares": raw.get("shares", 0) + raw.get("forwards", 0) + raw.get("repins", 0),
        "video_views": raw.get("video_views", 0) or raw.get("views", 0),
    }
    return {k: int(v or 0) for k, v in u.items()}


def engagement_rate(m: dict) -> float:
    denom = m.get("impressions") or m.get("reach") or 1
    return round(m.get("engagements", 0) / max(denom, 1), 4)


def ppi(m: dict, niche: str, platform: str) -> float:
    """Post Performance Index: ER vs niche/platform benchmark, indexed to 100."""
    bench = get_niche(niche).benchmarks_er.get(platform, 0.04)
    if bench <= 0:
        return 0.0
    raw = (engagement_rate(m) / bench) * 100
    # light view-velocity boost for video platforms
    if m.get("video_views", 0) > 0 and platform in ("youtube", "tiktok", "instagram"):
        raw *= 1.05
    return round(min(raw, 500.0), 1)


def upsert_analytics(db: Session, post: ScheduledPost, raw: dict) -> PostAnalytics:
    item = post.content_item
    unified = normalize(raw)
    row = post.analytics or PostAnalytics(scheduled_post_id=post.id)
    for k in ("impressions", "reach", "engagements", "clicks", "shares", "video_views"):
        setattr(row, k, unified[k])
    row.raw_metrics = raw
    row.engagement_rate = engagement_rate(unified)
    row.ppi = ppi(unified, item.niche if item else "hospitality", post.platform)
    from datetime import datetime, timezone

    row.last_synced_at = datetime.now(timezone.utc)
    if row.id:
        db.merge(row)
    else:
        db.add(row)
    db.commit()
    return row


def dashboard(db: Session, tenant_id: str) -> dict:
    """Unified cross-network rollup for the analytics dashboard."""
    rows = (db.query(ScheduledPost, PostAnalytics)
              .join(PostAnalytics, PostAnalytics.scheduled_post_id == ScheduledPost.id)
              .filter(ScheduledPost.tenant_id == tenant_id)
              .all())
    by_platform: dict[str, dict] = {}
    top: list[dict] = []
    for post, an in rows:
        b = by_platform.setdefault(post.platform, {"posts": 0, "impressions": 0, "reach": 0,
                                                   "engagements": 0, "clicks": 0, "shares": 0,
                                                   "video_views": 0, "ppi_sum": 0.0})
        b["posts"] += 1
        for k in ("impressions", "reach", "engagements", "clicks", "shares", "video_views"):
            b[k] += getattr(an, k)
        b["ppi_sum"] += an.ppi
        top.append({"post_id": post.id, "platform": post.platform, "title": post.payload_json.get("title", "")[:80],
                    "ppi": an.ppi, "er": an.engagement_rate, "impressions": an.impressions})
    for p, b in by_platform.items():
        b["avg_ppi"] = round(b.pop("ppi_sum") / max(b["posts"], 1), 1)
        b["er"] = round(b["engagements"] / max(b["impressions"], 1), 4)
    return {
        "totals": {k: sum(b[k] for b in by_platform.values())
                   for k in ("posts", "impressions", "reach", "engagements", "clicks", "shares", "video_views")},
        "by_platform": by_platform,
        "top_posts": sorted(top, key=lambda t: -t["ppi"])[:10],
        "feedback_loop": _format_weights(by_platform),
    }


def _format_weights(by_platform: dict) -> dict:
    """Closed loop: platforms over-indexing on PPI get higher scheduling weight."""
    avg = (sum(b["avg_ppi"] for b in by_platform.values()) / len(by_platform)) if by_platform else 0
    return {p: round(min(2.0, b["avg_ppi"] / avg), 2) if avg else 1.0
            for p, b in by_platform.items()}
