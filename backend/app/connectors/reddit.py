"""Reddit adapter — OAuth2 script/app: subreddit validation, karma gating,
flair selection, value-first text/link submission with anti-spam guards."""
from __future__ import annotations

import re

from app.connectors.base import ConnectorError, PublishRequest, PublishResult, SocialConnector

API = "https://oauth.reddit.com"
UA = "socialos/0.1 (by /c_tech_ops)"


class RedditAdapter(SocialConnector):
    platform = "reddit"
    auth_url = "https://www.reddit.com/api/v1/authorize"
    token_url = "https://www.reddit.com/api/v1/access_token"
    default_scopes = ["identity", "submit", "read", "flair", "modflair"]

    MIN_KARMA = 50  # PRD: karma gating verification before submission
    PROMO_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

    def _guard(self, req: PublishRequest) -> list[str]:
        """Anti-spam / anti-shadowban guardrails (PRD risk table)."""
        violations = []
        karma = self.account.get("meta", {}).get("karma", 10_000)
        if karma < self.MIN_KARMA:
            violations.append(f"karma {karma} < {self.MIN_KARMA}")
        p = req.platform_payload
        if p.get("subreddit", "").startswith("u/"):
            violations.append("user profile posting disabled")
        if len(req.body) < 280:
            violations.append("body too short for value-first standard (>=280 chars)")
        if not p.get("value_first"):
            violations.append("flagged promotional: value_first=False")
        if self.PROMO_URL_RE.search(req.body) and not p.get("allow_links"):
            violations.append("raw promotional URL in body — use comments instead")
        return violations

    def _publish_mock(self, req: PublishRequest) -> PublishResult:
        violations = self._guard(req)
        if violations:
            return PublishResult(ok=False, error="; ".join(violations), raw={"guarded": True})
        return PublishResult(
            ok=True,
            external_id=f"t3_{abs(hash((req.title, req.body))) % 10**8}",
            url=f"https://reddit.com/r/{req.platform_payload.get('subreddit', 'test')}/comments/mock",
            raw={"kind": req.platform_payload.get("kind", "self"), "flair": req.platform_payload.get("flair", "")},
        )

    async def _publish_live(self, req: PublishRequest) -> PublishResult:
        violations = self._guard(req)
        if violations:
            return PublishResult(ok=False, error="; ".join(violations))
        p = req.platform_payload
        # subreddit validation
        about = await self.api("GET", f"{API}/r/{p['subreddit']}/about", headers={**self.bearer(), "User-Agent": UA})
        if about.status_code != 200:
            return PublishResult(ok=False, error=f"subreddit invalid: {p['subreddit']}")
        data: dict = {
            "sr": p["subreddit"], "api_type": "json", "title": req.title[:300],
            "kind": p.get("kind", "self"), "resubmit": "true", "ad": False,
        }
        if data["kind"] == "self":
            data["text"] = req.body
        else:
            data["url"] = req.link or (req.media_urls[0] if req.media_urls else "")
        if p.get("flair_id"):
            data.update({"flair_id": p["flair_id"], "flair_text": p.get("flair", "")})
        r = await self.api("POST", f"{API}/api/submit", headers={**self.bearer(), "User-Agent": UA}, data=data)
        j = r.json()
        if j.get("json", {}).get("errors"):
            return PublishResult(ok=False, error=str(j["json"]["errors"]))
        post = j["json"]["data"]
        return PublishResult(ok=True, external_id=post["id"], url=post["url"], raw=j)

    async def _fetch_analytics_live(self, external_id: str) -> dict:
        r = await self.api("GET", f"{API}/api/info", params={"id": external_id},
                           headers={**self.bearer(), "User-Agent": UA})
        child = r.json().get("data", {}).get("children", [{}])[0].get("data", {})
        return {"impressions": child.get("view_count", 0) or 0, "likes": child.get("ups", 0),
                "upvotes": child.get("ups", 0), "comments": child.get("num_comments", 0),
                "upvote_ratio": child.get("upvote_ratio", 0)}
