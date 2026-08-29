"""Connector foundation: OAuth2+PKCE helpers, token refresh, mock/live dispatch,
rate-limit-aware HTTP with 429 exponential backoff, and normalized results."""
from __future__ import annotations

import abc
import asyncio
import random
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings
from app.connectors.rate_limiter import registry as rate_registry


class ConnectorError(Exception):
    pass


class TokenExpired(ConnectorError):
    pass


class RateLimited(ConnectorError):
    """HTTP 429 surfaced so the queue worker can back off and retry."""


@dataclass
class TokenBundle:
    access_token: str = ""
    refresh_token: str = ""
    expires_in: int | None = None
    scopes: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class PublishRequest:
    body: str = ""                      # caption / message / description
    title: str = ""                     # youtube/pinterest/reddit title
    link: str = ""                      # destination URL
    media_urls: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    first_comment: str = ""
    platform_payload: dict = field(default_factory=dict)  # adapter-specific extras


@dataclass
class PublishResult:
    ok: bool
    external_id: str = ""
    url: str = ""
    raw: dict = field(default_factory=dict)
    error: str = ""


class SocialConnector(abc.ABC):
    """One decoupled adapter per social network. Live mode speaks the real API;
    mock mode produces deterministic results so the whole platform is testable offline."""

    platform: str = "base"
    auth_url: str = ""
    token_url: str = ""
    default_scopes: list[str] = []

    def __init__(self, account: dict | None = None, client_id: str = "", client_secret: str = "",
                 mock: bool | None = None):
        self.account = account or {}
        self.client_id = client_id
        self.client_secret = client_secret
        self.mock = settings.mock_connectors if mock is None else mock

    # ---------------- OAuth 2.0 (+PKCE) ----------------
    def pkce_required(self) -> bool:
        return False

    def authorize_url(self, state: str, redirect_uri: str, code_challenge: str | None = None,
                      extra: dict | None = None) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
        }
        if self.default_scopes:
            sep = "+" if "google" in self.auth_url or "tiktok" in self.auth_url else ","
            params["scope"] = sep.join(self.default_scopes) if sep == "+" else " ".join(self.default_scopes)
        if self.pkce_required() and code_challenge:
            params.update({"code_challenge": code_challenge, "code_challenge_method": "S256"})
        params.update(extra or {})
        return httpx.URL(self.auth_url, params=params).__str__()

    async def exchange_code(self, code: str, redirect_uri: str, code_verifier: str | None = None) -> TokenBundle:
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}
        if self.pkce_required() and code_verifier:
            data["code_verifier"] = code_verifier
        return await self._token_request(data)

    async def refresh(self, refresh_token: str) -> TokenBundle:
        return await self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )

    async def _token_request(self, data: dict) -> TokenBundle:
        data = dict(data)
        data.setdefault("client_id", self.client_id)
        if self.client_secret:
            data.setdefault("client_secret", self.client_secret)
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            r = await client.post(self.token_url, data=data)
            if r.status_code != 200:
                raise ConnectorError(f"{self.platform} token error {r.status_code}: {r.text[:300]}")
            payload = r.json()
        return TokenBundle(
            access_token=payload.get("access_token", ""),
            refresh_token=payload.get("refresh_token", ""),
            expires_in=payload.get("expires_in"),
            scopes=payload.get("scope", "").replace("+", " ").split(),
            raw=payload,
        )

    # ---------------- HTTP with rate-limit discipline ----------------
    async def api(self, method: str, url: str, account_key: str = "default", **kwargs) -> httpx.Response:
        bucket = rate_registry.bucket(self.platform, account_key)
        await asyncio.to_thread(bucket.acquire)
        backoff = 1.0
        for attempt in range(4):
            async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
                r = await client.request(method, url, **kwargs)
            if r.status_code == 429:
                if attempt == 3:
                    raise RateLimited(f"{self.platform} 429 after retries: {url}")
                retry_after = float(r.headers.get("retry-after", backoff))
                await asyncio.sleep(min(retry_after, backoff * 2))
                backoff *= 2
                continue
            return r
        raise ConnectorError("unreachable")

    def bearer(self) -> dict:
        token = self.account.get("access_token", "")
        if not token:
            raise TokenExpired(f"{self.platform}: no access token (connect the account first)")
        return {"Authorization": f"Bearer {token}"}

    def requires_live_token(self) -> None:
        if self.mock:
            return
        if not self.account.get("access_token"):
            raise TokenExpired(f"{self.platform}: no access token")

    # ---------------- contract ----------------
    async def publish(self, req: PublishRequest) -> PublishResult:
        if self.mock:
            return self._publish_mock(req)
        self.requires_live_token()
        return await self._publish_live(req)

    async def fetch_analytics(self, external_id: str) -> dict[str, int]:
        if self.mock:
            return self._analytics_mock(external_id)
        return await self._fetch_analytics_live(external_id)

    # ---------------- override per adapter ----------------
    @abc.abstractmethod
    def _publish_mock(self, req: PublishRequest) -> PublishResult: ...

    @abc.abstractmethod
    async def _publish_live(self, req: PublishRequest) -> PublishResult: ...

    async def _fetch_analytics_live(self, external_id: str) -> dict[str, int]:
        return {}

    # ---------------- deterministic analytics simulation ----------------
    def _analytics_mock(self, external_id: str) -> dict[str, int]:
        rng = random.Random(f"{self.platform}:{external_id}")
        base = {"youtube": 4200, "instagram": 5800, "facebook": 2600, "tiktok": 9500,
                "pinterest": 3100, "reddit": 1800, "telegram": 1200}[self.platform]
        impressions = rng.randint(base, base * 4)
        reach = int(impressions * rng.uniform(0.55, 0.9))
        likes = int(impressions * rng.uniform(0.02, 0.09))
        comments = int(likes * rng.uniform(0.03, 0.15))
        shares = int(likes * rng.uniform(0.05, 0.3))
        saves = int(likes * rng.uniform(0.1, 0.4))
        views = int(impressions * rng.uniform(0.4, 0.95)) if self.platform != "pinterest" else 0
        clicks = int(impressions * rng.uniform(0.01, 0.06))
        native = {"impressions": impressions, "reach": reach, "likes": likes, "comments": comments,
                  "shares": shares, "saves": saves, "video_views": views, "clicks": clicks}
        native.update(self._native_metric_names(native))
        return native

    def _native_metric_names(self, unified: dict) -> dict:
        """Platform-native aliases preserved for the raw_metrics audit trail."""
        aliases = {
            "youtube": {"views": unified.get("video_views", 0), "upvotes": unified.get("likes", 0)},
            "reddit": {"upvotes": unified.get("likes", 0), "upvote_ratio": 0.95},
            "pinterest": {"saves": unified.get("saves", 0), "impressions": unified["impressions"]},
            "telegram": {"views": unified["impressions"], "forwards": unified.get("shares", 0)},
        }
        return aliases.get(self.platform, {})
