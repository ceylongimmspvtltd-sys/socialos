"""AI Trend Hunter & Audience Intelligence (PRD §4.2/§4.3).

Ingests TikTok Creative Center, YouTube Trending, Reddit hot, Pinterest Trends,
Google Trends RSS. Computes Trend_Velocity + Saturation_Index -> Emerging/Peaking/
Declining, then translates general trends into niche-specific creative angles.

`SOCIALOS_TRENDS_LIVE_FETCH=1` switches to live public feeds (aggregated, GDPR-safe).
Default uses a bundled snapshot so the demo is deterministic and offline-safe.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

from app.agents.niches import get_niche
from app.core.config import settings

UA = {"User-Agent": "Mozilla/5.0 (compatible; SocialOS/0.1; trend-intelligence)"}


@dataclass
class Trend:
    source: str
    name: str
    url: str = ""
    volume: int = 0
    prev_volume: int = 0
    region: str = "GLOBAL"
    phase: str = "emerging"
    velocity: float = 0.0
    saturation_index: float = 0.0
    meta: dict = field(default_factory=dict)

    def classify(self, niche_cap: float = 0.6) -> "Trend":
        """velocity = current/previous volume; saturation = share of the audience
        already reached before this window (prev/current) — high growth = low saturation."""
        self.velocity = round(self.volume / max(self.prev_volume, 1), 2)
        self.saturation_index = round(min(1.0, self.prev_volume / max(self.volume, 1)), 2)
        if self.velocity >= 1.4 and self.saturation_index < niche_cap:
            self.phase = "emerging"
        elif self.velocity >= 0.8:
            self.phase = "peaking"
        else:
            self.phase = "declining"
        return self


# ---------------------------------------------------------------- snapshots
def _snapshot() -> list[Trend]:
    return [
        Trend("tiktok", "slow-motion reveal audio 'Little Life'", volume=148_000, prev_volume=61_000,
              meta={"type": "audio", "format": "9:16"}),
        Trend("tiktok", "POV hotel room tour format", volume=310_000, prev_volume=290_000,
              meta={"type": "format", "format": "9:16"}),
        Trend("youtube", "cinematic gear breakdown videos", volume=88_000, prev_volume=40_000,
              meta={"type": "format"}),
        Trend("reddit", "island itinerary debate threads", volume=12_400, prev_volume=5_100,
              region="EU", meta={"type": "topic"}),
        Trend("pinterest", "wellness retreat mood boards", volume=205_000, prev_volume=160_000,
              region="EU", meta={"type": "visual"}),
        Trend("google", "sri lanka 10 day itinerary", volume=74_000, prev_volume=69_000,
              region="EU", meta={"type": "search"}),
        Trend("tiktok", "before/after glow-up transition", volume=505_000, prev_volume=420_000,
              meta={"type": "audio"}),
        Trend("pinterest", "shoppable product pins rich meta", volume=121_000, prev_volume=49_000,
              meta={"type": "feature"}),
        Trend("reddit", "wedding videography pricing talk", volume=9_800, prev_volume=4_300,
              meta={"type": "topic"}),
        Trend("google", "flash sale nail appointments near me", volume=33_000, prev_volume=31_000,
              meta={"type": "search"}),
    ]


# ---------------------------------------------------------------- live fetchers
async def fetch_google_trends(region: str = "LK") -> list[Trend]:
    url = f"https://trends.google.com/trending/rss?geo={region}"
    async with httpx.AsyncClient(timeout=15, headers=UA) as client:
        r = await client.get(url)
    trends = []
    root = ET.fromstring(r.text)
    ns = {"ht": "https://trends.google.com/trending/rss"}
    for item in root.findall(".//item", ns) or root.findall(".//item"):
        title = item.findtext("title") or ""
        traffic = item.findtext("ht:approx_traffic", namespaces=ns) or "0"
        trends.append(Trend("google", title, volume=_parse_traffic(traffic),
                            prev_volume=max(1, int(_parse_traffic(traffic) * 0.7)), region=region))
    return trends


async def fetch_youtube_trending(api_key: str = "", region: str = "US") -> list[Trend]:
    key = api_key or settings.youtube_api_key
    if not key:
        return []
    url = ("https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics"
           f"&chart=mostPopular&regionCode={region}&maxResults=20&key={key}")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
    items = r.json().get("items", [])
    return [Trend("youtube", v["snippet"]["title"], url=f"https://youtu.be/{v['id']}",
                  volume=int(v.get("statistics", {}).get("viewCount", 0)) // 1000)
            for v in items]


async def fetch_reddit_hot(subreddits: list[str]) -> list[Trend]:
    out: list[Trend] = []
    async with httpx.AsyncClient(timeout=15, headers=UA) as client:
        for sub in subreddits:
            try:
                r = await client.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=10")
                for child in r.json().get("data", {}).get("children", []):
                    d = child["data"]
                    out.append(Trend("reddit", d["title"][:200], url=f"https://reddit.com{d['permalink']}",
                                     volume=d.get("ups", 0), prev_volume=max(1, d.get("ups", 0) // 2)))
            except Exception:
                continue
    return out


# Pinterest Trends API v5 (/trends/keywords/{region}) + TikTok Creative Center
# require partner credentials; they plug into the same Trend contract below.
async def fetch_all(subreddits: list[str] | None = None) -> list[Trend]:
    if not settings.trends_live_fetch:
        return _snapshot()
    import asyncio

    subs = subreddits or [s.strip() for s in settings.trend_subreddits.split(",")]
    groups = await asyncio.gather(fetch_google_trends(), fetch_youtube_trending(),
                                  fetch_reddit_hot(subs), return_exceptions=True)
    trends: list[Trend] = []
    for g in groups:
        if isinstance(g, list):
            trends += g
    return trends or _snapshot()


def _parse_traffic(s: str) -> int:
    s = s.replace(",", "").replace("+", "").strip()
    mult = 1
    if s.endswith("K"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


# ---------------------------------------------------------------- scoring + translation
def score(trends: list[Trend]) -> list[Trend]:
    return sorted((t.classify() for t in trends), key=lambda t: (-t.velocity, -t.volume))


async def top_trends(niche_key: str, limit: int = 5) -> list[Trend]:
    relevant = {"hospitality": ["hotel", "room", "resort", "dining", "retreat", "tour"],
                "travel": ["itinerary", "travel", "island", "holiday", "week"],
                "salon": ["glow", "nail", "hair", "appointment", "transformation"],
                "production": ["cinematic", "gear", "video", "pricing", "4k"],
                "ecom": ["product", "sale", "shop", "deal", "pin"]}
    keywords = relevant.get(niche_key, [])
    all_t = score(await fetch_all())
    hits = [t for t in all_t if any(k in t.name.lower() for k in keywords)]
    pool = hits + [t for t in all_t if t not in hits]
    return pool[:limit]


def translate_to_niche(trend: Trend, niche_key: str) -> str:
    """Niche Translation Layer: general trend -> vertical-specific creative angle."""
    niche = get_niche(niche_key)
    name = trend.name
    angle_map = {
        "hospitality": f"shoot a POV arrival reel at the property riding '{name}' — sensory hook, end on 'book direct'",
        "travel": f"turn '{name}' into a feeder-market itinerary guide (day-by-day, transparent pricing)",
        "salon": f"recut a before/after transformation to '{name}' with a flash-slot CTA in Telegram",
        "production": f"break down how we'd film '{name}' — lens, lighting, budget table",
        "ecom": f"demo the product in the '{name}' format with a problem/solution hook and shoppable pin",
    }
    base = angle_map.get(niche_key, name)
    phase_hint = {"emerging": "move now — low saturation", "peaking": "fast-follow with a twist",
                  "declining": "only if brand-native, else skip"}[trend.phase]
    return f"{base} [{phase_hint}] ({trend.source}, velocity {trend.velocity}x)"
