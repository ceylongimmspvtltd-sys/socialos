"""Token-bucket rate limiting per platform (guards HTTP 429s before they happen)."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    capacity: float
    refill_per_sec: float
    tokens: float = field(default_factory=lambda: 0.0)
    last_refill: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if self.tokens == 0.0:
            self.tokens = self.capacity

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = max(0.0, now - self.last_refill)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.last_refill = now

    def try_acquire(self, n: float = 1.0) -> bool:
        with self.lock:
            self._refill()
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False

    def acquire(self, n: float = 1.0, timeout: float = 30.0) -> None:
        """Block until a token is available or timeout (then raise)."""
        deadline = time.monotonic() + timeout
        while not self.try_acquire(n):
            if time.monotonic() > deadline:
                raise TimeoutError("rate-limit bucket exhausted")
            time.sleep(min(0.25, 1.0 / max(self.refill_per_sec, 0.1)))


class RateLimiterRegistry:
    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def bucket(self, platform: str, account_id: str = "default") -> TokenBucket:
        key = f"{platform}:{account_id}"
        with self._lock:
            if key not in self._buckets:
                # Conservative defaults; tuned per platform documented limits.
                capacity, refill = RATE_PROFILES.get(platform, (10, 0.5))
                self._buckets[key] = TokenBucket(capacity=capacity, refill_per_sec=refill)
            return self._buckets[key]


# (capacity, refill tokens/sec) — aligned with documented platform quotas.
RATE_PROFILES: dict[str, tuple[float, float]] = {
    "youtube":    (6,   6 / 60),     # ~6 uploads quota units/sec budget
    "instagram":  (25,  25 / 3600),  # 25 posts / 24h (app cap), metered
    "facebook":   (30,  30 / 3600),
    "tiktok":     (15,  15 / 3600),  # direct post audit quota
    "pinterest":  (40,  40 / 3600),  # write limit 1000s/day, metered
    "reddit":     (10,  10 / 600),   # ~10 posts/10min guidance
    "telegram":   (20,  20 / 60),    # ~20 msgs/min per chat
}

registry = RateLimiterRegistry()
