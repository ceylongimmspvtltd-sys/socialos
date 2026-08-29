"""Niche profiles: verified prompt chains, tone policies, content pillars, conversion
formulas, hashtag banks, disclaimers and channel priorities per vertical (PRD §2)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NicheProfile:
    key: str
    name: str
    objective: str
    core_channels: list[str]
    pillars: list[str]                      # content pillars
    tone: dict                              # tone vector dims 0..1
    hook_patterns: list[str]                # {topic} placeholders
    cta_bank: list[str]
    hashtag_bank: list[str]
    disclaimers: list[str]
    visual_style: str                       # visual prompt style for image gen
    optimal_hours_utc: dict[str, list[int]] # platform -> posting hours (UTC)
    reddit_subs: list[str]
    benchmarks_er: dict[str, float]         # engagement-rate benchmarks per platform
    season_notes: str = ""
    prompt_chain: str = ""                  # master system prompt for the strategy agent


HOSPITALITY = NicheProfile(
    key="hospitality", name="Hospitality (Hotels • Resorts • Dining • Venues)",
    objective="Direct room/table & event bookings; ambiance showcase",
    core_channels=["instagram", "facebook", "tiktok", "pinterest"],
    pillars=["Experiential property reels", "Culinary showcases", "Local attraction guides", "Guest UGC amplification", "Event venue features"],
    tone={"warm": 0.9, "luxurious": 0.6, "experiential": 0.9, "formal": 0.3, "witty": 0.3, "technical": 0.1},
    hook_patterns=[
        "POV: you wake up to this view at {topic}",
        "The {topic} experience nobody told you about",
        "3 reasons guests keep coming back for {topic}",
        "Rate this {topic} setup 1–10 👇",
    ],
    cta_bank=["Book your stay — link in bio", "Reserve a table tonight", "Plan your event with us — DM 'VENUE'"],
    hashtag_bank=["#luxurytravel", "#resortlife", "#foodieheaven", "#destinationwedding", "#hiddengem", "#travelgram", "#finedining"],
    disclaimers=["Rates & availability subject to season. Images representative of property experience."],
    visual_style="golden-hour resort photography, shallow depth of field, cinematic color grade, natural textures",
    optimal_hours_utc={"instagram": [11, 17], "facebook": [12, 18], "tiktok": [15, 21], "pinterest": [14, 20], "youtube": [16], "reddit": [9], "telegram": [10, 19]},
    reddit_subs=["travel", "food", "Hotels"],
    benchmarks_er={"instagram": 0.048, "facebook": 0.032, "tiktok": 0.075, "pinterest": 0.012},
    season_notes="Peak interest Nov–Mar (EU winter escape); wedding season inquiries Jan–Apr.",
    prompt_chain=(
        "You are a hospitality marketing strategist for hotels, resorts, dining and event venues. "
        "Lead with sensory experience and place. Convert scenery into booked rooms and tables. "
        "Always pair visuals with a concrete booking action."
    ),
)

TRAVEL = NicheProfile(
    key="travel", name="Travel Agencies (Inbound/Outbound, EU feeder markets)",
    objective="Itinerary sales, package inquiries, seasonal bookings",
    core_channels=["pinterest", "youtube", "instagram", "reddit", "facebook"],
    pillars=["Visual trip guides", "Itinerary transparency", "Seasonal booking windows", "Cultural deep-dives", "Safety & logistics Q&A"],
    tone={"warm": 0.7, "luxurious": 0.4, "experiential": 0.9, "formal": 0.5, "witty": 0.2, "technical": 0.4},
    hook_patterns=[
        "The exact {topic} itinerary for your {market} summer",
        "{market} travellers: 7 days in {topic}, fully mapped",
        "What {market} families ask us about {topic} (and the honest answers)",
        "Sun, culture, value: {topic} beyond the brochures",
    ],
    cta_bank=["Get the full itinerary — free PDF", "Check seasonal packages", "Ask us anything about {market} travel to {topic}"],
    hashtag_bank=["#travelagency", "#wanderlust", "#itinerary", "#familytravel", "#europetravel", "#traveltips", "#bucketlist"],
    disclaimers=["Package inclusions vary by season. Flight taxes not included unless stated."],
    visual_style="documentary travel photography, wide establishing vistas, authentic local moments, map overlays",
    optimal_hours_utc={"pinterest": [13, 20], "youtube": [16], "instagram": [11, 18], "reddit": [8, 14], "facebook": [12], "tiktok": [17], "telegram": [9]},
    reddit_subs=["travel", "solotravel", "TripHacks", "TravelHacks"],
    benchmarks_er={"pinterest": 0.011, "youtube": 0.035, "instagram": 0.042, "reddit": 0.05, "facebook": 0.028},
    season_notes="Jan–Mar EU summer-holiday planning surge; Sep–Oct autumn wellness escapes; school-holiday windows.",
    prompt_chain=(
        "You are a travel-agency growth strategist specialized in European feeder markets "
        "(UK, DACH, France, Nordics, Benelux). Translate seasonal intent into itinerary sales. "
        "DACH wants structure, safety and transparent pricing; France wants culinary and cultural "
        "authenticity; UK wants value and family practicality; Nordics want nature and design."
    ),
)

SALON = NicheProfile(
    key="salon", name="Salons & Spas (Hair • Nails • Aesthetics)",
    objective="Local appointments, recurring clients, filling cancelled slots",
    core_channels=["instagram", "tiktok", "facebook", "telegram"],
    pillars=["Before/after transformations", "Trend showcases", "Flash slot alerts", "Care & technique education", "Team personality"],
    tone={"warm": 0.8, "luxurious": 0.5, "experiential": 0.6, "formal": 0.2, "witty": 0.6, "technical": 0.4},
    hook_patterns=[
        "She said 'do whatever you think is best' — {topic} result 😱",
        "Cancelled 4pm slot tomorrow — first to DM gets {topic}",
        "{topic} trend is exploding right now. Here's our take",
        "3 hair mistakes making your {topic} look cheap",
    ],
    cta_bank=["DM to book", "Claim the flash slot — link in bio", "Save this for your next appointment"],
    hashtag_bank=["#hairstylist", "#nailart", "#beforeandafter", "#salonlife", "#hairtransformation", "#spa", "#glowup"],
    disclaimers=["Results vary by hair/skin type. Patch test required 48h before colour services."],
    visual_style="crisp clinical-bright beauty photography, mirror reveals, macro texture detail, trending-audio cuts",
    optimal_hours_utc={"instagram": [10, 16, 20], "tiktok": [13, 19, 22], "facebook": [11], "telegram": [10, 18]},
    reddit_subs=["HaircareScience", "Hairstylist", "SkincareAddiction"],
    benchmarks_er={"instagram": 0.055, "tiktok": 0.085, "facebook": 0.036, "telegram": 0.18},
    season_notes="Wedding/prom season Mar–Jul; year-end party season Nov–Dec; trend waves follow TikTok audio.",
    prompt_chain=(
        "You are a local salon & spa marketing specialist. Hyper-local, transformation-led, "
        "trend-reactive. Convert attention into booked chairs and filled cancellation slots fast — "
        "Telegram flash alerts are for urgency, IG/TikTok are for aspiration."
    ),
)

PRODUCTION = NicheProfile(
    key="production", name="Production Companies (Cinematography • Showreels • Gear)",
    objective="B2B client acquisition, creative visibility, gear authority",
    core_channels=["youtube", "reddit", "instagram", "pinterest"],
    pillars=["4K showreels", "BTS cinematography", "Lighting & gear breakdowns", "Client case studies", "Community craft discussion"],
    tone={"warm": 0.3, "luxurious": 0.4, "experiential": 0.5, "formal": 0.5, "witty": 0.3, "technical": 0.95},
    hook_patterns=[
        "We shot {topic} on a budget — here's the full breakdown",
        "One light, one lens: {topic} cinematography explained",
        "BTS of our latest {topic} commercial shoot",
        "Stop doing {topic} like this. Do this instead",
    ],
    cta_bank=["Full breakdown on the channel — subscribe", "Book a shoot: hello@studio", "Save this lighting diagram"],
    hashtag_bank=["#cinematography", "#filmmaking", "#bts", "#showreel", "#gear", "#4k", "#videoproduction"],
    disclaimers=["Gear featured may be sponsored; opinions remain independent."],
    visual_style="anamorphic film-look frames, moody key lighting, V-log color science, technical overlay graphics",
    optimal_hours_utc={"youtube": [15], "reddit": [10, 15], "instagram": [17], "pinterest": [14]},
    reddit_subs=["videography", "cinematography", "filmmakers", "cams"],
    benchmarks_er={"youtube": 0.038, "reddit": 0.06, "instagram": 0.04, "pinterest": 0.009},
    season_notes="Corporate budget cycles Q1/Q4; wedding-season showreel demand Nov–Feb.",
    prompt_chain=(
        "You are a B2B content strategist for production companies. Speak to directors of "
        "photography, agency producers and brand managers. Technical credibility first, "
        "creative flex second, always end with a capability proof point."
    ),
)

ECOM = NicheProfile(
    key="ecom", name="Online Sales / E-Commerce (DTC • Dropshipping • Shoppable)",
    objective="Direct product sales, lower CAC, catalog conversions",
    core_channels=["tiktok", "pinterest", "instagram", "facebook", "reddit"],
    pillars=["Problem/solution hooks", "Product demo reels", "UGC-style reviews", "Shoppable rich pins", "Community answers"],
    tone={"warm": 0.5, "luxurious": 0.2, "experiential": 0.5, "formal": 0.2, "witty": 0.8, "technical": 0.2},
    hook_patterns=[
        "I was today years old when I learned {topic} does this",
        "POV: your {topic} problem finally solved for under $30",
        "Why is nobody talking about this {topic}?!",
        "Adding to cart in 3… 2… 1… #${topic}",
    ],
    cta_bank=["Link in bio before it sells out", "Shop the pin", "Get yours — 20% today only"],
    hashtag_bank=["#tiktokmademebuyit", "#amazonfinds", "#dropshipping", "#shopsmall", "#dtc", "#productreview"],
    disclaimers=["Prices incl. VAT where applicable. Returns per store policy. Results not guaranteed."],
    visual_style="clean e-comm product staging, motion-first demos, bold captions, bright gradient backgrounds",
    optimal_hours_utc={"tiktok": [12, 18, 21], "pinterest": [14, 21], "instagram": [11, 19], "facebook": [13], "reddit": [10]},
    reddit_subs=["dropship", "ecommerce", "BuyItForLife"],
    benchmarks_er={"tiktok": 0.09, "pinterest": 0.013, "instagram": 0.045, "facebook": 0.03, "reddit": 0.04},
    season_notes="Q4 gifting surge; Jan 'new year' angle; payday weekends 25th–1st.",
    prompt_chain=(
        "You are a DTC e-commerce growth copywriter. Hooks in the first 1.5 seconds, social proof, "
        "objection handling, then a hard CTA. Native to the platform — never ad-speak in organic posts."
    ),
)

NICHES: dict[str, NicheProfile] = {p.key: p for p in (HOSPITALITY, TRAVEL, SALON, PRODUCTION, ECOM)}


def get_niche(key: str) -> NicheProfile:
    if key not in NICHES:
        raise KeyError(f"unknown niche '{key}' — valid: {list(NICHES)}")
    return NICHES[key]
