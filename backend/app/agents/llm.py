"""LLM provider layer.

- `template` (default): fully deterministic, offline, zero-cost — the agents carry
  rich vertical prompt-chains as templates and always succeed.
- `openai`: any OpenAI-compatible endpoint (OpenAI, Azure, vLLM, Ollama...). When the
  call fails, agents transparently fall back to templates so publishing never blocks.
"""
from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.core.config import settings

log = logging.getLogger("socialos.llm")


class LLMClient(Protocol):
    async def complete(self, system: str, user: str, max_tokens: int = 1600) -> str: ...


class TemplateLLM:
    """Deterministic no-op client — agents detect this and use their template paths."""

    is_template = True

    async def complete(self, system: str, user: str, max_tokens: int = 1600) -> str:
        return ""


class OpenAICompatClient:
    is_template = False

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key, self.base_url, self.model = api_key, base_url, model

    async def complete(self, system: str, user: str, max_tokens: int = 1600) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
                      "max_tokens": max_tokens, "temperature": 0.7},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]


def get_llm() -> LLMClient:
    if settings.llm_provider == "openai" and settings.openai_api_key:
        return OpenAICompatClient(settings.openai_api_key, settings.openai_base_url, settings.openai_model)
    return TemplateLLM()


async def llm_or(llm: LLMClient, system: str, user: str, fallback: str) -> str:
    """Try the LLM; on any failure fall back to the deterministic template output."""
    if getattr(llm, "is_template", True):
        return fallback
    try:
        out = await llm.complete(system, user)
        return out.strip() if out and out.strip() else fallback
    except Exception as e:  # noqa: BLE001 — resilience by design
        log.warning("LLM call failed (%s); using deterministic fallback", e)
        return fallback
