"""Pipeline state shared by every agent in the content graph."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TrendRef(BaseModel):
    name: str = ""
    source: str = ""
    phase: str = "emerging"
    angle: str = ""  # niche-translated creative angle


class PipelineState(BaseModel):
    # inputs
    content_item_id: str = ""
    campaign_id: str = ""
    workspace_id: str = ""
    tenant_id: str = ""
    niche: str = "hospitality"
    master_prompt: str = ""
    title: str = ""
    source_asset_url: str = ""
    target_platforms: list[str] = Field(default_factory=list)
    target_demographic: dict = Field(default_factory=dict)  # e.g. {"region": "DACH", "market": "EU-summer"}
    language: str = "en"
    governance_mode: str = "supervised"

    # enrichments
    trends: list[TrendRef] = Field(default_factory=list)
    strategy: dict[str, Any] = Field(default_factory=dict)  # NicheStrategyAgent output

    # outputs
    outputs: dict[str, Any] = Field(default_factory=dict)  # platform -> payload
    safety_report: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    # bookkeeping
    status: str = "GENERATING"
    trace: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
