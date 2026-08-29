"""Dynamic UTM generator — structured attribution links for every channel."""
from __future__ import annotations

from urllib.parse import urlencode


def build_utm_link(base_url: str, source: str, medium: str = "social", campaign: str = "",
                   content: str = "") -> str:
    if not base_url:
        base_url = "https://example.com"
    params = {
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": campaign or "always-on",
        "utm_content": content or f"{source}-{medium}",
    }
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}{urlencode(params)}"
