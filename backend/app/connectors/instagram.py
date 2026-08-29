"""Instagram adapter — Meta Graph API (Instagram Content API): media containers,
Reels/carousel publish flow, auto-first-comment, location & collaborator tags."""
from __future__ import annotations

from app.connectors.base import PublishRequest, PublishResult, SocialConnector

GRAPH = "https://graph.facebook.com/v21.0"


class InstagramAdapter(SocialConnector):
    platform = "instagram"
    auth_url = "https://www.facebook.com/v21.0/dialog/oauth"
    token_url = "https://graph.facebook.com/v21.0/oauth/access_token"
    default_scopes = ["instagram_basic", "instagram_content_publish", "pages_show_list"]

    def _container_spec(self, req: PublishRequest) -> dict:
        """Build the IG media-container spec (dict sent to /{ig-user-id}/media)."""
        p = req.platform_payload
        media = req.media_urls[0] if req.media_urls else ""
        is_video = media.endswith(".mp4") or p.get("media_type") == "REELS"
        media_type = p.get("media_type") or ("REELS" if is_video else "IMAGE")
        spec: dict = {"media_type": media_type, "caption": req.body[:2200]}
        if is_video:
            spec["video_url"] = media
            spec["share_to_feed"] = True
        else:
            spec["image_url"] = media
        if media_type == "CAROUSEL":
            # Children created separately as is_carousel_item containers.
            spec["children_media_urls"] = req.media_urls[:10]
        if p.get("location_id"):
            spec["location_id"] = p["location_id"]
        if p.get("collaborators"):
            spec["collaborators"] = p["collaborators"]
        return spec

    def _publish_mock(self, req: PublishRequest) -> PublishResult:
        spec = self._container_spec(req)
        return PublishResult(
            ok=True,
            external_id=f"ig_{spec['media_type'].lower()}_{abs(hash((req.body, req.title))) % 10**12}",
            url="https://www.instagram.com/p/mock",
            raw={"container_id": "17900000000000000", "media_type": spec["media_type"],
                 "first_comment": req.first_comment[:80]},
        )

    async def _publish_live(self, req: PublishRequest) -> PublishResult:
        ig_user = self.account.get("account_id", "")
        token = self.account.get("access_token", "")
        spec = self._container_spec(req)
        children_urls = spec.pop("children_media_urls", [])

        if spec["media_type"] == "CAROUSEL":  # 1) child containers
            child_ids = []
            for url in children_urls:
                item = {"is_carousel_item": True, "image_url": url}
                if url.endswith(".mp4"):
                    item = {"is_carousel_item": True, "video_url": url}
                r = await self.api("POST", f"{GRAPH}/{ig_user}/media",
                                   params={**item, "access_token": token})
                if r.status_code >= 400:
                    return PublishResult(ok=False, error=f"child container: {r.text[:300]}")
                child_ids.append(r.json()["id"])
            spec["children"] = ",".join(child_ids)
            spec.pop("image_url", None)

        # 2) root container -> 3) publish
        create = await self.api("POST", f"{GRAPH}/{ig_user}/media",
                                params={**spec, "access_token": token})
        if create.status_code >= 400:
            return PublishResult(ok=False, error=f"container {create.status_code}: {create.text[:300]}")
        creation_id = create.json()["id"]
        pub = await self.api("POST", f"{GRAPH}/{ig_user}/media_publish",
                             params={"creation_id": creation_id, "access_token": token})
        if pub.status_code >= 400:
            return PublishResult(ok=False, error=f"publish {pub.status_code}: {pub.text[:300]}")
        media_id = pub.json()["id"]
        if req.first_comment:  # auto-first-comment hashtag drop
            await self.api("POST", f"{GRAPH}/{media_id}/comments",
                           params={"message": req.first_comment, "access_token": token})
        return PublishResult(ok=True, external_id=media_id, url=f"https://www.instagram.com/p/{media_id}", raw=pub.json())

    async def _fetch_analytics_live(self, external_id: str) -> dict:
        r = await self.api("GET", f"{GRAPH}/{external_id}",
                           params={"fields": "impressions,reach,like_count,comments_count,saved,shares"})
        d = r.json()
        return {"impressions": d.get("impressions", 0), "reach": d.get("reach", 0),
                "likes": d.get("like_count", 0), "comments": d.get("comments_count", 0),
                "saves": d.get("saved", 0), "shares": d.get("shares", 0)}
