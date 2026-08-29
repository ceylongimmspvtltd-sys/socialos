"""SQLAlchemy models — full schema blueprint (tenants, workspaces, brand_kits, social_accounts,
campaigns, content_items, scheduled_posts, post_analytics, client_approvals) + supporting tables
(assets/DAM, trend_signals, audit_logs)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.context import new_id
from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- tenants
class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    plan: Mapped[str] = mapped_column(String(50), default="pro")  # trial|pro|enterprise
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    industry_niche: Mapped[str] = mapped_column(String(50))  # hospitality|travel|salon|production|ecom
    settings: Mapped[dict] = mapped_column(JSON, default=dict)  # timezone, governance default, locales...

    tenant: Mapped[Tenant] = relationship(back_populates="workspaces")
    brand_kit: Mapped["BrandKit | None"] = relationship(back_populates="workspace", uselist=False)
    social_accounts: Mapped[list["SocialAccount"]] = relationship(back_populates="workspace")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="workspace")


class BrandKit(Base, TimestampMixin):
    __tablename__ = "brand_kits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True)
    colors_json: Mapped[dict] = mapped_column(JSON, default=dict)   # primary/secondary/accent hex
    fonts_json: Mapped[dict] = mapped_column(JSON, default=dict)    # heading/body/weights/hierarchy
    tone_embeddings: Mapped[dict] = mapped_column(JSON, default=dict)  # named tone vector dims
    banned_words: Mapped[list] = mapped_column(JSON, default=list)
    required_disclaimers: Mapped[list] = mapped_column(JSON, default=list)
    negative_prompt_constraints: Mapped[list] = mapped_column(JSON, default=list)
    logo_urls: Mapped[dict] = mapped_column(JSON, default=dict)     # light/dark/monochrome

    workspace: Mapped[Workspace] = relationship(back_populates="brand_kit")


class Asset(Base, TimestampMixin):
    """Digital Asset Manager entry: auto-tags + aspect-ratio renditions."""
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="image")  # image|video|doc
    source_url: Mapped[str] = mapped_column(Text, default="")
    storage_key: Mapped[str] = mapped_column(Text, default="")
    filename: Mapped[str] = mapped_column(String(300), default="")
    mime: Mapped[str] = mapped_column(String(100), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    auto_tags: Mapped[list] = mapped_column(JSON, default=list)
    renditions: Mapped[dict] = mapped_column(JSON, default=dict)  # {"16:9": url, "9:16": url, "1:1": url, "4:5": url}
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class SocialAccount(Base, TimestampMixin):
    __tablename__ = "social_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    account_id: Mapped[str] = mapped_column(String(200))       # platform-side handle/page id
    display_name: Mapped[str] = mapped_column(String(200), default="")
    access_token_enc: Mapped[str] = mapped_column(Text, default="")
    refresh_token_enc: Mapped[str] = mapped_column(Text, default="")
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)     # karma, page tokens, board map...
    status: Mapped[str] = mapped_column(String(20), default="pending")

    workspace: Mapped[Workspace] = relationship(back_populates="social_accounts")


# ---------------------------------------------------------------- campaigns & content
class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    objective: Mapped[str] = mapped_column(String(300), default="awareness")
    target_demographic: Mapped[dict] = mapped_column(JSON, default=dict)  # region, age, feeder market...
    governance_mode: Mapped[str] = mapped_column(String(20), default="supervised")
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    budget: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="active")

    content_items: Mapped[list["ContentItem"]] = relationship(back_populates="campaign")
    workspace: Mapped[Workspace] = relationship(back_populates="campaigns")


class ContentItem(Base, TimestampMixin):
    __tablename__ = "content_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    niche: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300), default="")
    master_prompt: Mapped[str] = mapped_column(Text, default="")
    source_asset_url: Mapped[str] = mapped_column(Text, default="")
    target_platforms: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    outputs_json: Mapped[dict] = mapped_column(JSON, default=dict)  # platform -> platform-specific payload
    safety_report: Mapped[dict] = mapped_column(JSON, default=dict)
    strategy_json: Mapped[dict] = mapped_column(JSON, default=dict)  # niche strategy agent output
    trends_used: Mapped[list] = mapped_column(JSON, default=list)

    campaign: Mapped[Campaign] = relationship(back_populates="content_items")
    scheduled_posts: Mapped[list["ScheduledPost"]] = relationship(back_populates="content_item")
    approvals: Mapped[list["ClientApproval"]] = relationship(back_populates="content_item")


class ScheduledPost(Base, TimestampMixin):
    __tablename__ = "scheduled_posts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    external_post_id: Mapped[str] = mapped_column(String(300), default="")
    error_log: Mapped[Text] = mapped_column(Text, default="")
    utm_link: Mapped[str] = mapped_column(Text, default="")

    content_item: Mapped[ContentItem] = relationship(back_populates="scheduled_posts")
    analytics: Mapped["PostAnalytics | None"] = relationship(back_populates="scheduled_post", uselist=False)


class PostAnalytics(Base, TimestampMixin):
    __tablename__ = "post_analytics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scheduled_post_id: Mapped[str] = mapped_column(ForeignKey("scheduled_posts.id", ondelete="CASCADE"), unique=True)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    engagements: Mapped[int] = mapped_column(Integer, default=0)  # unified likes+comments+shares+saves
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    video_views: Mapped[int] = mapped_column(Integer, default=0)
    raw_metrics: Mapped[dict] = mapped_column(JSON, default=dict)  # platform-native names preserved
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    ppi: Mapped[float] = mapped_column(Float, default=0.0)        # Post Performance Index (0-100+)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scheduled_post: Mapped[ScheduledPost] = relationship(back_populates="analytics")


class ClientApproval(Base, TimestampMixin):
    __tablename__ = "client_approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    client_feedback: Mapped[Text] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[float] = mapped_column(Float, default=0.0)  # epoch seconds
    viewed: Mapped[bool] = mapped_column(Boolean, default=False)

    content_item: Mapped[ContentItem] = relationship(back_populates="approvals")


# ---------------------------------------------------------------- intelligence & audit
class TrendSignal(Base, TimestampMixin):
    __tablename__ = "trend_signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(30), index=True)  # tiktok|youtube|reddit|pinterest|google
    name: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text, default="")
    volume: Mapped[int] = mapped_column(Integer, default=0)
    prev_volume: Mapped[int] = mapped_column(Integer, default=0)
    velocity: Mapped[float] = mapped_column(Float, default=0.0)
    saturation_index: Mapped[float] = mapped_column(Float, default=0.0)
    phase: Mapped[str] = mapped_column(String(20), default="emerging", index=True)
    region: Mapped[str] = mapped_column(String(20), default="GLOBAL")
    niche: Mapped[str] = mapped_column(String(30), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(100), default="system")
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


Index("ix_scheduled_due", ScheduledPost.publish_status, ScheduledPost.scheduled_at)
