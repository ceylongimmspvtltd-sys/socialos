"""Facebook adapter — Meta Pages API: feed posts, video, CTA action buttons,
geo gating params, scheduled publish timestamps."""
from __future__ import annotations

from app.connectors.base import PublishRequest, PublishResult, SocialConnector

GRAPH = "https://graph.facebook.com/v21.0"


class FacebookAdapter(SocialConnector):
    platform = "facebook"
    auth_url = "https://www.facebook.com/v21.0/dialog/oauth"
    token_url = "https://graph.facebook.com/v21.0/oauth/access_token"
    default_scopes = ["pages_manage_posts", "pages_read_engagement", "pages_show_list"]

    def _publish_mock(self, req: PublishRequest) -> PublishResult:
        return PublishResult(
            ok=True,
            external_id=f"fb_{abs(hash((req.body, req.link))) % 10**12}_0000",
            url="https://facebook.com/mock/posts/1",
            raw={"cta_button": req.platform_payload.get("cta_button", ""),
                 "geo_targeting": req.platform_payload.get("geo_targeting", {}),
                 "scheduled": bool(req.platform_payload.get("scheduled_publish_time"))},
        )

    async def _publish_live(self, req: PublishRequest) -> PublishResult:
        page_id = self.account.get("account_id", "")
        token = self.account.get("access_token", "")
        p = req.platform_payload
        params: dict = {"message": req.body, "access_token": token}
        if req.link:
            params["link"] = req.link
        if p.get("cta_button") and req.link:  # 'Book Now' / 'Shop Now' action button
            params["call_to_action"] = (
                f'{{"type":"{p["cta_button"]}","value":{{"link":"{req.link}"}}}}'
            )
        if p.get("geo_targeting"):  # geographic audience gating
            params["targeting"] = str({"geo_locations": {"countries": p["geo_targeting"].get("countries", [])}})
        if p.get("scheduled_publish_time"):  # unix ts — native scheduled page publishing
            params["scheduled_publish_time"] = p["scheduled_publish_time"]
            params["published"] = "false"

        endpoint = f"{GRAPH}/{page_id}/feed"
        if req.media_urls and req.media_urls[0].endswith(".mp4"):
            endpoint = f"{GRAPH}/{page_id}/videos"
            params["file_url"] = req.media_urls[0]
            params["description"] = params.pop("message")
        elif req.media_urls:
            params["attached_media"] = str([{"media_fbid": m} for m in req.platform_payload.get("media_fbids", [])])

        r = await self.api("POST", endpoint, params=params)
        if r.status_code >= 400:
            return PublishResult(ok=False, error=f"{r.status_code}: {r.text[:300]}")
        post_id = r.json().get("id", "")
        return PublishResult(ok=True, external_id=post_id,
                             url=f"https://facebook.com/{post_id.replace('_', '/posts/')}", raw=r.json())

    async def _fetch_analytics_live(self, external_id: str) -> dict:
        r = await self.api("GET", f"{GRAPH}/{external_id}",
                           params={"fields": "impressions,post_impressions,reach,likes.summary(true),"
                                             "comments.summary(true),shares,clicks"})
        d = r.json()
        return {"impressions": d.get("impressions", {}).get("summary", {}).get("total_count", 0)
                or d.get("post_impressions", 0),
                "reach": d.get("reach", {}).get("summary", {}).get("total_count", 0),
                "likes": len(d.get("likes", {}).get("data", [])),
                "comments": d.get("comments", {}).get("summary", {}).get("total_count", 0),
                "shares": d.get("shares", {}).get("count", 0)}
