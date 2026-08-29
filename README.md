# ⚡ C Tech SocialOS — Multi-Niche Autonomous AI Social Media Marketing & Publishing Platform

> Centralized strategy, trend forecasting, audience intelligence, automated scheduling and
> multi-platform distribution for **5 business verticals × 7 social networks**, with
> 3-tier publishing governance and a closed-loop analytics feedback engine.
>
> Built to the approved PRD (C Tech — IT & Digital Marketing Operations, v1.0, Aug 2026).

| | |
|---|---|
| **Verticals** | Hospitality · Travel Agencies (EU feeder markets) · Salons & Spas · Production Companies · E-Commerce |
| **Channels** | YouTube · Instagram · Facebook · TikTok · Pinterest · Reddit · Telegram |
| **Backend** | Python 3.13 · FastAPI · SQLAlchemy 2 (PostgreSQL + RLS / SQLite demo) |
| **Agents** | LangGraph-style multi-agent graph (drop-in swap to `langgraph`) |
| **Queue** | Durable DB-backed worker + in-proc broker; Redis sorted-set transport for scale-out |
| **Security** | AES-256-GCM token vault · OAuth 2.0 + PKCE · tenant Row-Level Security · audit log |

---

## 1. Quick start (demo mode — zero external credentials)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000  (docs at /docs)
```

Demo mode boots a seeded Sri Lankan multi-brand agency: **5 workspaces, 5 campaigns, 22+
scheduled posts, published history with analytics, and one live client-portal approval**.

- Landing dashboard: `http://localhost:8000/`
- Swagger UI: `http://localhost:8000/docs`
- Auth header: `X-API-Key: demo-key`
- LLM: deterministic template engine by default — set `SOCIALOS_LLM_PROVIDER=openai` +
  `SOCIALOS_OPENAI_API_KEY` (any OpenAI-compatible endpoint) to enrich copy generation.
- Connectors run in **mock mode** (`SOCIALOS_MOCK_CONNECTORS=true`) — real OAuth apps/
  tokens flip them to live publishing.

Run the test suite (39 tests): `cd backend && pytest -q`

## 2. Production stack

> 🆓 **Easiest free hosting (GitHub + Render, no credit card):** see **`docs/DEPLOY.md`** —
> a `render.yaml` blueprint is included; push to GitHub → Render Blueprint → live URL.

```bash
cp .env.example .env                    # fill OAuth app credentials + vault key
docker compose up -d                    # postgres (+pgvector) + redis + api + adminer
docker compose exec api python -m app.db.migrate   # or: psql "$DATABASE_URL" -f app/db/migrations/0001_init.sql
```

`app/db/migrations/0001_init.sql` contains the full PostgreSQL schema: pgvector for brand
voice embeddings, **Row-Level Security policies keyed off `app.current_tenant`**, a unified
performance view, and indexes for the scheduler hot path.

## 3. Architecture

```
                                  ┌──────────────────────────────────────────┐
   Brief / Asset ──►  POST /api/campaigns                     │  ORCHESTRATOR (master controller)        │
                                  │                                          │
   TikTok CC ─┐                    │   ┌────────┐  ┌───────────┐  ┌────────────────────┐  ┌───────────────┐ │
   YT Trend ──┤   TREND HUNTER ───►│   │ trend_ │─►│ niche_    │─►│ multimodal_creator │─►│ brand_safety  │ │
   Reddit ────┤   velocity/sat.   │   │ hunt   │  │ strategy  │  │  7 platform outputs │  │ two-pass gate │ │
   Google RSS ┘   niche translate │   └────────┘  └───────────┘  └────────────────────┘  └───────┬───────┘ │
                                  │       ▲            ▲ EU feeder-market engine               │pass     │
                                  │       └── snapshots / live RSS+JSON ingest                  ▼ FLAGGED │
                                  │                                              ┌───────────────┐   │
   OAuth2+PKCE vault ─────────────┼─────────────────────────────────────────────►│ governance    │◄──┘
                                  │                                              │ 3-tier:       │
                                  │                                              │ autonomous /  │
                                  │   ┌──────────┐   ┌──────────────┐            │ supervised /  │
   Client portal ◄── token ───────┼──►│ queue    │◄──│ scheduled_   │◄───────────│ client portal │
   (approve/reject)               │   │ + DLQ    │   │ posts (RLS)  │            └───────────────┘
                                  │   └────┬─────┘   └──────────────┘
                                  │        ▼  retry/backoff/token refresh
                                  │   7 PUBLISHING ADAPTERS  ──► YouTube · IG · FB · TikTok · Pinterest · Reddit · Telegram
                                  │        ▼
                                  │   analytics normalizer ─► ER + PPI ─► scheduling weight feedback loop
                                  └──────────────────────────────────────────┘
```

### Repo layout

```
backend/
├── app/
│   ├── core/          config · AES-256-GCM vault · PKCE · tenant context · consts
│   ├── db/            models (9 core tables + DAM/trends/audit) · migrations/0001_init.sql (PG + RLS) · seed
│   ├── connectors/    base (OAuth2/PKCE, 429 backoff, mock/live) + 7 adapters + token-bucket limiter
│   ├── agents/        graph engine · orchestrator · niche strategy · multimodal creator ·
│   │                  brand safety · niches (5 vertical profiles) · eu_demographics
│   ├── trends/        trend hunter (velocity/saturation/phase + niche translation)
│   ├── scheduler/     optimal windows · 3-tier governance · queue (+Redis) · worker (retry/DLQ)
│   ├── analytics/     metric normalization · engagement rate · PPI · dashboard
│   ├── modules/       FastAPI routers (workspaces, campaigns, scheduling, portal, connectors, trends, analytics)
│   └── main.py        app factory + lifespan (auto-seed, background worker)
└── tests/             vault · connectors · pipeline E2E · governance/portal · trends/analytics
```

## 4. The 3-tier governance flow

| Tier | Behaviour | Demo command |
|---|---|---|
| **Autonomous** | Safety-passed content stages **and queues** instantly | seeded *Glow Studio* campaign |
| **Supervised** | Stops at `STAGED` until internal approval | `POST /api/content/{id}/approve` |
| **Client portal** | Tokenized link; client approves/rejects with feedback | `GET /portal/{token}` → `POST /portal/{token}/decision` |

## 5. API tour (see `/docs` for all)

```bash
H='X-API-Key: demo-key'; B=http://localhost:8000

curl -H "$H" $B/api/workspaces                                   # 5 vertical workspaces
curl -H "$H" "$B/api/trends?niche=travel"                        # scored trends + niche angles
curl -H "$H" "$B/api/trends/eu-demographics?market=DACH"         # feeder-market brief
curl -H "$H" "$B/api/schedule?platform=tiktok"                   # calendar feed
curl -H "$H" "$B/api/schedule/optimal?niche=travel&region=DACH"  # smart windows
curl -X POST -H "$H" $B/api/schedule/worker/tick                 # force-publish due posts
curl -X POST -H "$H" "$B/api/analytics/sync"                     # pull metrics → PPI
curl -H "$H" $B/api/analytics/dashboard                          # unified rollup + weights

# full lifecycle: 1 brief → 7 platform-native outputs → staged → published
curl -X POST -H "$H" -H 'Content-Type: application/json' $B/api/campaigns -d @- <<'JSON'
{"workspace_id":"<id>","name":"Test","niche":"hospitality","governance_mode":"autonomous",
 "master_prompt":"Promote lagoon suites to EU couples","target_demographic":{"region":"EU","market":"UK"}}
JSON
```

## 6. Platform integration guardrails implemented

- **YouTube** — resumable chunked upload session, Shorts detection, thumbnail set, pinned first comment.
- **Instagram** — media container → publish flow, carousels (10), Reels, auto-first-comment hashtags.
- **Facebook** — Pages API, CTA action buttons, geo gating, native scheduled publishing.
- **TikTok** — Content Posting API `PULL_FROM_URL`, commercial-music-library compliance, duet/stitch toggles.
- **Pinterest** — v5 pins (image/video), board sections, rich-pin meta, visual-SEO alt text.
- **Reddit** — subreddit validation, **karma gating**, flair, ≥280-char value-first body, no raw promo URLs (anti-shadowban).
- **Telegram** — MarkdownV2 escaping, inline keyboards, media groups, silent + pinned broadcasts.

Rate limiting: per-platform token buckets sized to documented quotas; HTTP 429 triggers
exponential backoff; exhausted jobs route to the dead-letter queue with audit trail.

## 7. GDPR posture

Audience intelligence processes **aggregated public trend volumes only** — no individual
tracking, no unauthorized PII (the brand-safety gate also blocks emails/phones in public
copy). Tokens are encrypted at rest (AES-256-GCM, HKDF-derived master key). Tenant data
isolation is double-enforced: ORM scoping + PostgreSQL RLS.

## 8. Status vs PRD roadmap

| Phase | Scope | Status here |
|---|---|---|
| 1 | Multi-tenant workspaces, brand kits, DAM, core integrations, niche pipelines, calendar + review mode | ✅ backend complete (drag-drop UI frontend next) |
| 2 | Pinterest/Reddit/Telegram, trend hunter, EU demographic engine, normalized analytics + UTM | ✅ backend complete |
| 3 | Fully autonomous publishing w/ circuit breakers, self-healing schedule, multilingual, community inbox | 🔶 autonomous mode + PPI feedback loop done; multilingual DE/FR/ES/IT generation + inbox pending |

**Next steps:** Next.js dashboard (React 19 + FullCalendar drag-drop calendar), BullMQ
worker parity, real FFmpeg renditions on S3/R2, LangGraph/temporal swap-in, webhook listeners.
