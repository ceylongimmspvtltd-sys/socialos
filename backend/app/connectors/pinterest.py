"""Pinterest API v5 adapter — Pin creation (standard/video/rich), board & section
assignment, destination URL, visual SEO alt-text."""
from __future__ import annotations

from app.connectors.base import PublishRequest, PublishResult, SocialConnector

API = "https://api.pinterest.com/v5"


class PinterestAdapter(SocialConnector):
    platform = "pinterest"
    auth_url = "https://www.pinterest.com/oauth/"
    token_url = "https://api.pinterest.com/v5/oauth/token"
    default_scopes = ["boards:read", "pins:read", "pins:write", "user_accounts:read"]

    def _pin_body(self, req: PublishRequest) -> dict:
        p = req.platform_payload
        media = req.media_urls[0] if req.media_urls else ""
        body: dict = {
            "board_id": p.get("board_id", ""),
            "title": req.title[:100],
            "description": req.body[:500],
            "alt_text": (p.get("alt_text") or req.title)[:500],  # visual SEO
            "link": req.link or None,
        }
        if media.endswith(".mp4"):
            body["media_source"] = {"source_type": "video_url", "media_url": media}
        else:
            body["media_source"] = {"source_type": "image_url", "url": media}
        if p.get("section"):  # board section assignment
            body["board_section_id"] = p["section"]
        return body

    def _publish_mock(self, req: PublishRequest) -> PublishResult:
        return PublishResult(
            ok=True,
            external_id=f"pin_{abs(hash((req.title, req.body))) % 10**12}",
            url="https://pinterest.com/pin/mock",
            raw={"board_id": req.platform_payload.get("board_id", ""),
                 "rich_pin": bool(req.link), "aspect": "2:3"},
        )

    async def _publish_live(self, req: PublishRequest) -> PublishResult:
        r = await self.api("POST", f"{API}/pins",
                           headers={**self.bearer(), "Content-Type": "application/json"},
                           json={k: v for k, v in self._pin_body(req).items() if v})
        if r.status_code >= 400:
            return PublishResult(ok=False, error=f"{r.status_code}: {r.text[:300]}")
        data = r.json()
        return PublishResult(ok=True, external_id=data.get("id", ""),
                             url=f"https://www.pinterest.com/pin/{data.get('id', '')}/", raw=data)

    async def _fetch_analytics_live(self, external_id: str) -> dict:
        r = await self.api("GET", f"{API}/pins/{external_id}/analytics",
                           params={"start_date": "2026-01-01", "end_date": "2026-12-31",
                                   "metric_types": "IMPRESSION,OUTBOUND_CLICK,SAVE,REPIN"})
        d = r.json().get("data", {}).get("metrics", {})
        return {"impressions": d.get("IMPRESSION", 0), "clicks": d.get("OUTBOUND_CLICK", 0),
                "saves": d.get("SAVE", 0), "shares": d.get("REPIN", 0)}
