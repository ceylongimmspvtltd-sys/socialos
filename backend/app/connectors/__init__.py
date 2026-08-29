"""Connector registry — resolves the right adapter for a platform and hydrates it
with the decrypted account credentials."""
from __future__ import annotations

from typing import Type

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import vault
from app.connectors.base import SocialConnector
from app.connectors.facebook import FacebookAdapter
from app.connectors.instagram import InstagramAdapter
from app.connectors.pinterest import PinterestAdapter
from app.connectors.reddit import RedditAdapter
from app.connectors.telegram import TelegramAdapter
from app.connectors.tiktok import TikTokAdapter
from app.connectors.youtube import YouTubeAdapter

ADAPTERS: dict[str, Type[SocialConnector]] = {
    "youtube": YouTubeAdapter,
    "instagram": InstagramAdapter,
    "facebook": FacebookAdapter,
    "tiktok": TikTokAdapter,
    "pinterest": PinterestAdapter,
    "reddit": RedditAdapter,
    "telegram": TelegramAdapter,
}


def adapter_class(platform: str) -> Type[SocialConnector]:
    if platform not in ADAPTERS:
        raise KeyError(f"no adapter registered for platform '{platform}'")
    return ADAPTERS[platform]


def client_credentials(platform: str) -> tuple[str, str]:
    return {
        "youtube": (settings.youtube_client_id, settings.youtube_client_secret),
        "instagram": (settings.instagram_client_id, settings.instagram_client_secret),
        "facebook": (settings.facebook_client_id, settings.facebook_client_secret),
        "tiktok": (settings.tiktok_client_key, settings.tiktok_client_secret),
        "pinterest": (settings.pinterest_client_id, settings.pinterest_client_secret),
        "reddit": (settings.reddit_client_id, settings.reddit_client_secret),
        "telegram": (settings.telegram_bot_token, ""),
    }.get(platform, ("", ""))


def build_connector(platform: str, account_row) -> SocialConnector:
    """Hydrate an adapter from a SocialAccount DB row (decrypting the token vault)."""
    cls = adapter_class(platform)
    account: dict = {
        "account_id": account_row.account_id,
        "meta": account_row.meta or {},
    }
    if account_row.access_token_enc:
        account["access_token"] = vault.decrypt(account_row.access_token_enc)
    if account_row.refresh_token_enc:
        account["refresh_token"] = vault.decrypt(account_row.refresh_token_enc)
    if platform == "telegram" and not account.get("access_token"):
        account["access_token"] = settings.telegram_bot_token or "mock-bot-token"
    cid, secret = client_credentials(platform)
    return cls(account=account, client_id=cid, client_secret=secret, mock=settings.mock_connectors)


def mock_connector(platform: str) -> SocialConnector:
    cls = adapter_class(platform)
    cid, secret = client_credentials(platform)
    return cls(account={"account_id": "mock", "meta": {"karma": 5000}}, client_id=cid,
               client_secret=secret, mock=True)


def get_workspace_account(db: Session, workspace_id: str, platform: str):
    from app.db.models import SocialAccount

    row = (db.query(SocialAccount)
             .filter(SocialAccount.workspace_id == workspace_id, SocialAccount.platform == platform)
             .first())
    if row is None:  # auto-provision a simulated account so the demo pipeline flows
        row = SocialAccount(workspace_id=workspace_id, platform=platform, account_id=f"mock_{platform}",
                            display_name=f"Mock {platform.title()}", status="connected", meta={})
        db.add(row)
        db.commit()
    return row
