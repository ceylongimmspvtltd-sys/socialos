"""Timezone-aware smart scheduler — optimal posting windows per platform,
demographic region and niche (PRD §6.2)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.agents.niches import get_niche

# Audience-region prime time (local time, 24h) — demographic attention windows
# informed by EU feeder-market behaviour and APAC local patterns.
REGION_TZ = {"UK": "Europe/London", "DACH": "Europe/Berlin", "FR": "Europe/Paris",
             "NORDICS": "Europe/Stockholm", "BENELUX": "Europe/Brussels",
             "EU": "Europe/Berlin", "GLOBAL": "UTC", "LK": "Asia/Colombo"}

PLATFORM_OFFSET_HOURS = {
    # platform -> hours relative to daily prime-time block (spread across the day)
    "youtube": [0, 8], "instagram": [0, 6], "facebook": [1, 7], "tiktok": [2, 8],
    "pinterest": [3, 9], "reddit": [4, 10], "telegram": [5, 11],
}


def next_optimal_slot(platform: str, niche: str, region: str = "GLOBAL",
                      after: datetime | None = None, index: int = 0) -> datetime:
    """Next optimal UTC datetime for a post on `platform` for this demographic."""
    niche_profile = get_niche(niche)
    hours = niche_profile.optimal_hours_utc.get(platform, [10, 18])
    tz = ZoneInfo(REGION_TZ.get((region or "GLOBAL").upper(), "UTC"))

    now_utc = (after or datetime.now(timezone.utc)).astimezone(timezone.utc)
    offset_hours = PLATFORM_OFFSET_HOURS.get(platform, [0])[index % len(PLATFORM_OFFSET_HOURS.get(platform, [0]))]
    target_local_hour = (hours[index % len(hours)] + offset_hours // 12) % 24

    local_now = now_utc.astimezone(tz)
    candidate = local_now.replace(hour=target_local_hour, minute={0: 15, 1: 45}[index % 2],
                                  second=0, microsecond=0)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    # stagger multiple platforms same day
    candidate += timedelta(minutes=(index * 23) % 47)
    return candidate.astimezone(timezone.utc)


def plan_week(niche: str, platforms: list[str], region: str = "GLOBAL") -> list[dict]:
    """Seven-day posting plan across platforms."""
    plan: list[dict] = []
    now = datetime.now(timezone.utc)
    for day in range(7):
        for i, platform in enumerate(platforms):
            slot = next_optimal_slot(platform, niche, region, after=now + timedelta(days=day),
                                     index=(i + day) % 2)
            plan.append({"platform": platform, "scheduled_at": slot.isoformat(),
                         "day": slot.strftime("%A")})
    plan.sort(key=lambda p: p["scheduled_at"])
    return plan
