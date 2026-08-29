-- ============================================================================
-- C Tech SocialOS — Migration 0001: core schema, pgvector, Row-Level Security
-- Apply with: psql "$DATABASE_URL" -f migrations/0001_init.sql
-- (Bootstrap: run once as superuser; app roles then connect as socialos_app.)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;      -- brand voice embeddings (pgvector)

-- ---------------------------------------------------------------- tenants
CREATE TABLE IF NOT EXISTS tenants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(200) NOT NULL,
    plan          VARCHAR(50)  NOT NULL DEFAULT 'pro',
    api_key_hash  VARCHAR(64)  UNIQUE NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workspaces (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name           VARCHAR(200) NOT NULL,
    industry_niche VARCHAR(50)  NOT NULL,
    settings       JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_workspaces_tenant ON workspaces(tenant_id);

CREATE TABLE IF NOT EXISTS brand_kits (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id               UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
    colors_json                JSONB NOT NULL DEFAULT '{}',
    fonts_json                 JSONB NOT NULL DEFAULT '{}',
    tone_embeddings            JSONB NOT NULL DEFAULT '{}',   -- named dims (formality, wit, luxury...)
    banned_words               JSONB NOT NULL DEFAULT '[]',
    required_disclaimers       JSONB NOT NULL DEFAULT '[]',
    negative_prompt_constraints JSONB NOT NULL DEFAULT '[]',
    logo_urls                  JSONB NOT NULL DEFAULT '{}',
    voice_vector               VECTOR(1536),                  -- brand voice embedding (optional)
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS assets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kind         VARCHAR(20) NOT NULL DEFAULT 'image',
    source_url   TEXT NOT NULL DEFAULT '',
    storage_key  TEXT NOT NULL DEFAULT '',
    filename     VARCHAR(300) NOT NULL DEFAULT '',
    mime         VARCHAR(100) NOT NULL DEFAULT '',
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    auto_tags    JSONB NOT NULL DEFAULT '[]',
    renditions   JSONB NOT NULL DEFAULT '{}',
    meta         JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_assets_workspace ON assets(workspace_id);

-- ---------------------------------------------------------------- social accounts
CREATE TABLE IF NOT EXISTS social_accounts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    platform          VARCHAR(20) NOT NULL,
    account_id        VARCHAR(200) NOT NULL,
    display_name      VARCHAR(200) NOT NULL DEFAULT '',
    access_token_enc  TEXT NOT NULL DEFAULT '',      -- AES-256-GCM ciphertext
    refresh_token_enc TEXT NOT NULL DEFAULT '',
    token_expires_at  TIMESTAMPTZ,
    scopes            JSONB NOT NULL DEFAULT '[]',
    meta              JSONB NOT NULL DEFAULT '{}',
    status            VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_social_accounts_ws ON social_accounts(workspace_id, platform);

-- ---------------------------------------------------------------- campaigns & content
CREATE TABLE IF NOT EXISTS campaigns (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name               VARCHAR(300) NOT NULL,
    objective          VARCHAR(300) NOT NULL DEFAULT 'awareness',
    target_demographic JSONB NOT NULL DEFAULT '{}',
    governance_mode    VARCHAR(20) NOT NULL DEFAULT 'supervised',
    start_date         TIMESTAMPTZ,
    end_date           TIMESTAMPTZ,
    budget             DOUBLE PRECISION NOT NULL DEFAULT 0,
    status             VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_campaigns_ws ON campaigns(workspace_id);

CREATE TABLE IF NOT EXISTS content_items (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id       UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    workspace_id      UUID NOT NULL,
    niche             VARCHAR(30) NOT NULL,
    title             VARCHAR(300) NOT NULL DEFAULT '',
    master_prompt     TEXT NOT NULL DEFAULT '',
    source_asset_url  TEXT NOT NULL DEFAULT '',
    target_platforms  JSONB NOT NULL DEFAULT '[]',
    language          VARCHAR(10) NOT NULL DEFAULT 'en',
    status            VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    outputs_json      JSONB NOT NULL DEFAULT '{}',
    safety_report     JSONB NOT NULL DEFAULT '{}',
    strategy_json     JSONB NOT NULL DEFAULT '{}',
    trends_used       JSONB NOT NULL DEFAULT '[]',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_content_campaign ON content_items(campaign_id);
CREATE INDEX IF NOT EXISTS ix_content_status ON content_items(status);

CREATE TABLE IF NOT EXISTS scheduled_posts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    content_item_id  UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    platform         VARCHAR(20) NOT NULL,
    payload_json     JSONB NOT NULL DEFAULT '{}',
    scheduled_at     TIMESTAMPTZ NOT NULL,
    published_at     TIMESTAMPTZ,
    publish_status   VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    attempts         INTEGER NOT NULL DEFAULT 0,
    external_post_id VARCHAR(300) NOT NULL DEFAULT '',
    error_log        TEXT NOT NULL DEFAULT '',
    utm_link         TEXT NOT NULL DEFAULT '',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_scheduled_due ON scheduled_posts(publish_status, scheduled_at);

CREATE TABLE IF NOT EXISTS post_analytics (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheduled_post_id  UUID NOT NULL UNIQUE REFERENCES scheduled_posts(id) ON DELETE CASCADE,
    impressions        INTEGER NOT NULL DEFAULT 0,
    reach              INTEGER NOT NULL DEFAULT 0,
    engagements        INTEGER NOT NULL DEFAULT 0,
    clicks             INTEGER NOT NULL DEFAULT 0,
    shares             INTEGER NOT NULL DEFAULT 0,
    video_views        INTEGER NOT NULL DEFAULT 0,
    raw_metrics        JSONB NOT NULL DEFAULT '{}',
    engagement_rate    DOUBLE PRECISION NOT NULL DEFAULT 0,
    ppi                DOUBLE PRECISION NOT NULL DEFAULT 0,
    last_synced_at     TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS client_approvals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_item_id UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    token           VARCHAR(64) UNIQUE NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    client_feedback TEXT NOT NULL DEFAULT '',
    decided_at      TIMESTAMPTZ,
    expires_at      DOUBLE PRECISION NOT NULL DEFAULT 0,
    viewed          BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_approvals_item ON client_approvals(content_item_id);

-- ---------------------------------------------------------------- intelligence & audit
CREATE TABLE IF NOT EXISTS trend_signals (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source           VARCHAR(30) NOT NULL,
    name             VARCHAR(300) NOT NULL,
    url              TEXT NOT NULL DEFAULT '',
    volume           INTEGER NOT NULL DEFAULT 0,
    prev_volume      INTEGER NOT NULL DEFAULT 0,
    velocity         DOUBLE PRECISION NOT NULL DEFAULT 0,
    saturation_index DOUBLE PRECISION NOT NULL DEFAULT 0,
    phase            VARCHAR(20) NOT NULL DEFAULT 'emerging',
    region           VARCHAR(20) NOT NULL DEFAULT 'GLOBAL',
    niche            VARCHAR(30) NOT NULL DEFAULT '',
    meta             JSONB NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_trends_phase ON trend_signals(phase, niche);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,
    actor       VARCHAR(100) NOT NULL DEFAULT 'system',
    action      VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50)  NOT NULL DEFAULT '',
    entity_id   VARCHAR(64)  NOT NULL DEFAULT '',
    detail      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_tenant ON audit_logs(tenant_id, created_at);

-- ============================================================================
-- ROW-LEVEL SECURITY: every tenant-scoped table is filtered by app.current_tenant,
-- set per-transaction by the API layer (db/base.py::set_tenant_guc).
-- ============================================================================
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'workspaces','brand_kits','assets','social_accounts','campaigns',
        'content_items','scheduled_posts','post_analytics','client_approvals',
        'trend_signals','audit_logs'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format($f$
            CREATE POLICY tenant_isolation ON %I
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
            )
        $f$, t);
    END LOOP;
END $$;

-- Child tables without a direct tenant_id column: policies via parent join.
DROP POLICY IF EXISTS tenant_isolation ON brand_kits;
CREATE POLICY bk_ws ON brand_kits USING (
    workspace_id IN (SELECT id FROM workspaces)
) WITH CHECK (workspace_id IN (SELECT id FROM workspaces));

DROP POLICY IF EXISTS tenant_isolation ON assets;
CREATE POLICY a_ws ON assets USING (
    workspace_id IN (SELECT id FROM workspaces)
) WITH CHECK (workspace_id IN (SELECT id FROM workspaces));

DROP POLICY IF EXISTS tenant_isolation ON social_accounts;
CREATE POLICY sa_ws ON social_accounts USING (
    workspace_id IN (SELECT id FROM workspaces)
) WITH CHECK (workspace_id IN (SELECT id FROM workspaces));

DROP POLICY IF EXISTS tenant_isolation ON campaigns;
CREATE POLICY c_ws ON campaigns USING (
    workspace_id IN (SELECT id FROM workspaces)
) WITH CHECK (workspace_id IN (SELECT id FROM workspaces));

DROP POLICY IF EXISTS tenant_isolation ON content_items;
CREATE POLICY ci_camp ON content_items USING (
    campaign_id IN (SELECT id FROM campaigns)
) WITH CHECK (campaign_id IN (SELECT id FROM campaigns));

DROP POLICY IF EXISTS tenant_isolation ON scheduled_posts;
CREATE POLICY sp_ci ON scheduled_posts USING (
    content_item_id IN (SELECT id FROM content_items)
) WITH CHECK (content_item_id IN (SELECT id FROM content_items));

DROP POLICY IF EXISTS tenant_isolation ON post_analytics;
CREATE POLICY pa_sp ON post_analytics USING (
    scheduled_post_id IN (SELECT id FROM scheduled_posts)
) WITH CHECK (scheduled_post_id IN (SELECT id FROM scheduled_posts));

DROP POLICY IF EXISTS tenant_isolation ON client_approvals;
CREATE POLICY ca_ci ON client_approvals USING (
    content_item_id IN (SELECT id FROM content_items)
) WITH CHECK (content_item_id IN (SELECT id FROM content_items));

-- ============================================================================
-- Views: unified analytics rollup (dashboard)
-- ============================================================================
CREATE OR REPLACE VIEW v_unified_performance AS
SELECT sp.id AS scheduled_post_id,
       sp.tenant_id,
       sp.platform,
       ci.niche,
       pa.impressions, pa.reach, pa.engagements, pa.clicks, pa.shares, pa.video_views,
       pa.engagement_rate, pa.ppi,
       sp.published_at
FROM scheduled_posts sp
JOIN content_items ci ON ci.id = sp.content_item_id
LEFT JOIN post_analytics pa ON pa.scheduled_post_id = sp.id
WHERE sp.publish_status = 'PUBLISHED';
