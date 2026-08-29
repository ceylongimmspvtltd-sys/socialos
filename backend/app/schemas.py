"""Pydantic request/response schemas for the public API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.consts import GOVERNANCE_MODES, NICHES, PLATFORMS


# ---------------- workspaces & brand kits ----------------
class WorkspaceOut(BaseModel):
    id: str
    name: str
    industry_niche: str
    settings: dict = {}
    brand_kit_id: str | None = None


class BrandKitIn(BaseModel):
    colors_json: dict = {}
    fonts_json: dict = {}
    tone_embeddings: dict = {}
    banned_words: list[str] = []
    required_disclaimers: list[str] = []
    negative_prompt_constraints: list[str] = []
    logo_urls: dict = {}


# ---------------- campaigns & pipeline ----------------
class CampaignIn(BaseModel):
    workspace_id: str
    name: str
    objective: str = "awareness"
    niche: Literal[*NICHES] = "hospitality"  # type: ignore[valid-type]
    master_prompt: str
    title: str = ""
    source_asset_url: str = ""
    target_platforms: list[Literal[*PLATFORMS]] = []  # type: ignore[valid-type]  # empty -> niche defaults
    target_demographic: dict = {}
    governance_mode: Literal[*GOVERNANCE_MODES] = "supervised"  # type: ignore[valid-type]
    budget: float = 0.0
    language: str = "en"
    run_now: bool = True


class CampaignOut(BaseModel):
    id: str
    workspace_id: str
    name: str
    objective: str
    governance_mode: str
    status: str
    target_demographic: dict = {}
    content_item_ids: list[str] = []


class ContentOut(BaseModel):
    id: str
    campaign_id: str
    workspace_id: str
    niche: str
    title: str
    status: str
    outputs_json: dict = {}
    safety_report: dict = {}
    strategy_json: dict = {}
    trends_used: list = []
    platforms: list[str] = []
    scheduled_posts: list[dict] = []
    governance: dict = {}
    created_at: datetime | None = None


# ---------------- scheduling ----------------
class RescheduleIn(BaseModel):
    scheduled_at: datetime


class CalendarEntry(BaseModel):
    id: str
    platform: str
    scheduled_at: datetime
    publish_status: str
    title: str = ""
    niche: str = ""
    content_item_id: str = ""
    external_post_id: str = ""


# ---------------- portal ----------------
class PortalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    feedback: str = ""


# ---------------- assets / trends ----------------
class AssetIn(BaseModel):
    workspace_id: str
    filename: str
    source_url: str = ""
    kind: Literal["image", "video", "doc"] = "image"
    mime: str = ""
    size_bytes: int = 0


class TranslateIn(BaseModel):
    trend_name: str
    source: str = "tiktok"
    niche: Literal[*NICHES] = "hospitality"  # type: ignore[valid-type]


class OAuthStartOut(BaseModel):
    authorize_url: str
    state: str
    pkce: bool
    note: str = ""
