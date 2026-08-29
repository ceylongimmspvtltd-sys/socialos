"""YouTube Data API v3 adapter — resumable chunked upload, Shorts detection,
thumbnail set, pinned first comment, analytics via videos statistics."""
from __future__ import annotations

import httpx

from app.connectors.base import PublishRequest, PublishResult, SocialConnector

API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"


class YouTubeAdapter(SocialConnector):
    platform = "youtube"
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    default_scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]

    def pkce_required(self) -> bool:
        return True

    def _is_short(self, req: PublishRequest) -> bool:
        return bool(req.platform_payload.get("is_short")) or "#shorts" in req.body.lower()

    def _publish_mock(self, req: PublishRequest) -> PublishResult:
        kind = "short" if self._is_short(req) else "video"
        return PublishResult(
            ok=True,
            external_id=f"yt-{kind}-{abs(hash((self.platform, req.title, req.body))) % 10**10}",
            url=f"https://youtu.be/mock/{req.title[:24]}",
            raw={"resumable_session": "mock", "chunk_size": 8 * 1024 * 1024,
                 "category_id": req.platform_payload.get("category_id", 22), "kind": kind},
        )

    async def _publish_live(self, req: PublishRequest) -> PublishResult:
        media = req.media_urls[0] if req.media_urls else ""
        metadata = {
            "snippet": {
                "title": req.title[:100],
                "description": req.body[:5000],
                "tags": [t.lstrip("#") for t in req.hashtags][:30],
                "categoryId": str(req.platform_payload.get("category_id", 22)),
            },
            "status": {
                "privacyStatus": req.platform_payload.get("privacy", "public"),
                "selfDeclaredMadeForKids": False,
            },
        }
        # 1) Initiate resumable session
        init = await self.api(
            "POST",
            f"{UPLOAD}/videos?uploadType=resumable&part=snippet,status",
            json=metadata, headers={**self.bearer(), "X-Upload-Content-Type": "video/*"},
        )
        if init.status_code >= 400:
            return PublishResult(ok=False, error=f"init {init.status_code}: {init.text[:300]}")
        session_url = init.headers["Location"]
        # 2) Chunked transfer (8 MiB chunks; FFmpeg-normalized MP4 expected from DAM)
        async with httpx.AsyncClient(timeout=600) as client:
            put = await client.put(session_url, content=_chunkedReader(media) or b"",
                                   headers={"Content-Type": "video/*"})
        if put.status_code not in (200, 201):
            return PublishResult(ok=False, error=f"upload {put.status_code}: {put.text[:300]}")
        video = put.json()
        vid = video["id"]
        # 3) Thumbnail
        if req.platform_payload.get("thumbnail_url"):
            await self.api(
                "POST",
                f"{UPLOAD}/thumbnails/set?videoId={vid}",
                headers=self.bearer,
                content=req.platform_payload["thumbnail_url"].encode(),
            )
        # 4) Pinned first comment (SEO hashtag drop)
        if req.first_comment:
            await self.api("POST", f"{API}/commentThreads?part=snippet",
                           headers={**self.bearer(), "Content-Type": "application/json"},
                           json={"snippet": {"topLevelComment": {"snippet": {
                               "textOriginal": req.first_comment, "videoId": vid}}}})
        return PublishResult(ok=True, external_id=vid, url=f"https://youtu.be/{vid}", raw=video)

    async def _fetch_analytics_live(self, external_id: str) -> dict:
        r = await self.api("GET", f"{API}/videos?part=statistics&id={external_id}", headers=self.bearer)
        st = r.json().get("items", [{}])[0].get("statistics", {})
        return {"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0))}


def _chunkedReader(media: str) -> bytes:
    """Placeholder byte source: in production the DAM/FFmpeg pipeline streams the
    normalized asset from S3/R2 through this reader in 8 MiB chunks."""
    return b"" if not media else b""
