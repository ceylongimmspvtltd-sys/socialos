"""European Travel Demographic Engine (PRD §4.3).

GDPR posture: operates ONLY on aggregated public trend volumes and anonymized
seasonality calendars — zero individual user tracking, zero PII storage.
"""
from __future__ import annotations

# --- Feeder market profiles ---------------------------------------------------
FEEDER_MARKETS: dict[str, dict] = {
    "UK": {
        "name": "United Kingdom",
        "tone_rules": ["value-forward", "family-practical", "wry humour lands"],
        "priorities": ["price transparency", "school-holiday timing", "direct flights"],
        "copy_style": "Short, punchy, value-led. 'Two weeks of sun for the price of one in Spain.'",
        "peak_window": "Jan–Mar (summer booking surge), Jul–Aug (late deals)",
    },
    "DACH": {
        "name": "Germany • Austria • Switzerland",
        "tone_rules": ["structured itineraries", "safety reassurance", "no hype"],
        "priorities": ["day-by-day itinerary", "health/medical standards", "transparent pricing", "punctual logistics"],
        "copy_style": "Structured, precise, factual. Bullet itineraries, explicit costs, insurance notes.",
        "peak_window": "Jan–Feb (early-bird), May–Jun (late bookings)",
    },
    "FR": {
        "name": "France",
        "tone_rules": ["culinary & cultural depth", "heritage storytelling", "eloquent"],
        "priorities": ["gastronomy", "authentic craft", "cultural sites", "art de vivre"],
        "copy_style": "Evocative and cultural. 'Entre jungle sauvage et tables d'hôtes — le Sri Lanka des connaisseurs.'",
        "peak_window": "Jan–Mar, with Apr–Jun long-weekend planning",
    },
    "NORDICS": {
        "name": "Sweden • Norway • Denmark • Finland • Iceland",
        "tone_rules": ["nature-first", "design & minimalism", "sustainability proof"],
        "priorities": ["wildlife & landscape", "eco certification", "digital detox value"],
        "copy_style": "Calm, nature-led, understated. Sustainability facts over adjectives.",
        "peak_window": "Jan–Mar (escape the dark), Sep (autumn wellness)",
    },
    "BENELUX": {
        "name": "Netherlands • Belgium • Luxembourg",
        "tone_rules": ["pragmatic", "cycle-and-explore framing", "direct"],
        "priorities": ["compact itineraries", "active travel options", "good value seasonality"],
        "copy_style": "Practical and compact. Clear route logic, honest cost framing.",
        "peak_window": "Jan–Apr bookings; Oct half-term",
    },
}

# --- Seasonal intent windows (month -> intent signal) --------------------------
SEASONAL_INTENT = {
    (1, 2, 3): {"intent": "summer_holiday_planning_surge", "weight": 1.0,
                "angles": ["early-bird pricing", "guaranteed sunshine", "school-holiday availability"]},
    (4, 5, 6): {"intent": "late_deals_and_city_breaks", "weight": 0.8,
                "angles": ["shoulder-season value", "fewer crowds", "festival calendars"]},
    (7, 8): {"intent": "in_trip_realtime_and_autumn_lookahead", "weight": 0.6,
             "angles": ["live from destination", "autumn wellness pre-launch"]},
    (9, 10): {"intent": "autumn_wellness_escapes", "weight": 0.85,
              "angles": ["ayurveda & spa retreats", "digital detox", "monsoon-green landscapes"]},
    (11, 12): {"intent": "winter_sun_and_gift_vouchers", "weight": 0.9,
               "angles": ["escape the winter", "gift an experience", "festive departures"]},
}

# Simplified European school-holiday windows (aggregated public calendars)
SCHOOL_HOLIDAYS = {
    "UK": [(7, 1, 8, 31), (12, 20, 1, 5)],           # (from_m, from_d, to_m, to_d) approx
    "DACH": [(6, 25, 8, 5), (12, 22, 1, 6)],
    "FR": [(7, 6, 9, 1), (10, 18, 11, 3), (12, 20, 1, 6)],
    "NORDICS": [(6, 8, 8, 12)],
    "BENELUX": [(7, 15, 8, 25), (10, 26, 11, 2)],
}


def seasonal_intent(month: int) -> dict:
    for months, data in SEASONAL_INTENT.items():
        if month in months:
            return data
    return {"intent": "steady_state", "weight": 0.5, "angles": ["year-round value"]}


def market_brief(market_key: str, month: int) -> dict:
    """Full localization brief for the NicheStrategy agent."""
    market = FEEDER_MARKETS.get(market_key.upper(), FEEDER_MARKETS["UK"])
    season = seasonal_intent(month)
    return {
        "market": market_key.upper(),
        "market_name": market["name"],
        "tone_rules": market["tone_rules"],
        "priorities": market["priorities"],
        "copy_style": market["copy_style"],
        "peak_window": market["peak_window"],
        "seasonal_intent": season["intent"],
        "seasonal_weight": season["weight"],
        "recommended_angles": season["angles"],
        "gdpr_note": "Aggregated public signals only; no personal data processed.",
    }


def localize_hook(hook: str, market_key: str, month: int) -> str:
    """Adapt a generated hook to a feeder market's cultural nuance."""
    brief = market_brief(market_key, month)
    prefix = {
        "DACH": "Plan it properly: ",
        "FR": "L'authenticité: ",
        "NORDICS": "Slow travel: ",
        "BENELUX": "Compact & smart: ",
    }.get(market_key.upper(), "")
    return f"{prefix}{hook}" if brief["seasonal_weight"] >= 0.6 else hook


def is_school_holiday(month: int, market_key: str = "UK") -> bool:
    return any(f <= month <= t for (f, _, t, _) in SCHOOL_HOLIDAYS.get(market_key.upper(), []))
