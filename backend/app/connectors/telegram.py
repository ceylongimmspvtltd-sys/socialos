"""Telegram Bot API adapter — sendPhoto/sendVideo/sendMediaGroup/sendMessage with
MarkdownV2, inline keyboard CTAs, silent mode, pinned broadcast alerts."""
from __future__ import annotations

import re

from app.connectors.base import PublishRequest, PublishResult, SocialConnector


def mdv2_escape(text: str) -> str:
    """Escape MarkdownV2 reserved characters outside entities (conservative escape)."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", text)


class TelegramAdapter(SocialConnector):
    platform = "telegram"
    auth_url = ""   # bots authenticate with a bot token, not OAuth user flow
    token_url = ""
    default_scopes = []

    def _api(self) -> str:
        return f"https://api.telegram.org/bot{self.account.get('access_token', '')}"

    def _publish_mock(self, req: PublishRequest) -> PublishResult:
        return PublishResult(
            ok=True,
            external_id=f"tg_msg_{abs(hash((req.body, req.link))) % 10**10}",
            url=f"https://t.me/{req.platform_payload.get('chat_id', '@channel')}/1",
            raw={"parse_mode": "MarkdownV2", "method": req.platform_payload.get("method", "sendMessage"),
                 "buttons": req.platform_payload.get("buttons", [])},
        )

    def _keyboard(self, req: PublishRequest) -> dict | None:
        buttons = req.platform_payload.get("buttons", [])
        if not buttons:
            return None
        return {"inline_keyboard": [[{"text": b["text"], "url": b["url"]} for b in row]
                                    for row in (buttons if isinstance(buttons[0], list) else [buttons])]}

    async def _publish_live(self, req: PublishRequest) -> PublishResult:
        p = req.platform_payload
        chat = p.get("chat_id", "")
        media = req.media_urls or []
        keyboard = self._keyboard(req)
        common: dict = {"chat_id": chat, "parse_mode": "MarkdownV2"}
        if keyboard:
            common["reply_markup"] = str(keyboard).replace("'", '"')
        if p.get("silent"):
            common["disable_notification"] = "true"

        method, params = "sendMessage", {**common, "text": mdv2_escape(req.body)[:4096]}
        if len(media) > 1:  # media album
            method = "sendMediaGroup"
            group = []
            for i, m in enumerate(media[:10]):
                item = {"type": "video" if m.endswith(".mp4") else "photo", "media": m}
                if i == 0:
                    item["caption"] = mdv2_escape(req.body)[:1024]
                    item["parse_mode"] = "MarkdownV2"
                group.append(item)
            params = {"chat_id": chat, "media": str(group).replace("'", '"').replace("None", "null")}
            if p.get("silent"):
                params["disable_notification"] = "true"
        elif media:
            is_video = media[0].endswith(".mp4")
            method = "sendVideo" if is_video else "sendPhoto"
            media_field = "video" if is_video else "photo"
            params = {**common, media_field: media[0],
                      "caption": mdv2_escape(req.body)[:1024]}

        r = await self.api("POST", f"{self._api()}/{method}", data=params)
        if r.status_code >= 400:
            return PublishResult(ok=False, error=f"{r.status_code}: {r.text[:300]}")
        msg = r.json()
        if p.get("pin"):
            await self.api("POST", f"{self._api()}/pinChatMessage",
                           data={"chat_id": chat, "message_id": msg["result"]["message_id"], "disable_notification": "true"})
        return PublishResult(ok=True, external_id=str(msg["result"]["message_id"]),
                             raw={"ok": True, "method": method})

    async def _fetch_analytics_live(self, external_id: str) -> dict:
        # Telegram has limited insights via Bot API; views come from channel post forwards.
        return {"impressions": 0, "forwards": 0}
