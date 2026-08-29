"""Central constants: platforms, niches, and all lifecycle status enums."""

PLATFORMS = ["youtube", "instagram", "facebook", "tiktok", "pinterest", "reddit", "telegram"]

# --- Niches (business verticals) ---
NICHES = ["hospitality", "travel", "salon", "production", "ecom"]

# --- Content item lifecycle ---
# DRAFT -> GENERATING -> GENERATED -> (FLAGGED | STAGED) -> APPROVED -> QUEUED -> PUBLISHING -> PUBLISHED | FAILED
CONTENT_STATUS = [
    "DRAFT", "GENERATING", "GENERATED", "FLAGGED", "STAGED",
    "APPROVED", "QUEUED", "PUBLISHING", "PUBLISHED", "FAILED", "REJECTED",
]

# --- Scheduled post lifecycle ---
POST_STATUS = ["PENDING", "QUEUED", "RETRYING", "PUBLISHING", "PUBLISHED", "FAILED", "DEAD"]

# --- Governance tiers ---
GOVERNANCE_MODES = ["autonomous", "supervised", "client_portal"]

# --- Social account status ---
ACCOUNT_STATUS = ["pending", "connected", "expired", "revoked", "error"]

# --- Client approval status ---
APPROVAL_STATUS = ["pending", "approved", "rejected", "expired"]

# --- Trend lifecycle classification ---
TREND_PHASES = ["emerging", "peaking", "declining"]

# --- Approval-eligible terminal states per governance tier ---
GOV_AUTO_ADVANCE = {"autonomous"}
GOV_REQUIRE_INTERNAL = {"supervised"}
GOV_REQUIRE_CLIENT = {"client_portal"}

MAX_PUBLISH_ATTEMPTS = 3
