# Frontend — Next.js Dashboard (Phase 1 delivery: planned scaffold)

Stack (per PRD): **Next.js 15 · React 19 · TypeScript · Tailwind CSS · Shadcn UI · FullCalendar.io**

## Screens (build order)

1. **Workspace switcher + Brand Kit studio** — palette/typography editors, tone sliders
   (persisted as tone vectors), banned-word list, logo set (light/dark/mono).
2. **Campaign Creator** — master brief input, niche + demographic picker (EU feeder markets),
   governance tier selector; shows live agent-graph progress (`trend_hunt → niche_strategy →
   multimodal_creator → brand_safety`).
3. **Content Review** — per-platform previews (7 tabs), safety report chips, approve/regenerate.
4. **Drag-and-drop Calendar** — FullCalendar timeline wired to:
   `GET /api/schedule`, `PATCH /api/schedule/{id}` (drop = reschedule), color = publish_status.
5. **Client Portal page** — `/portal/{token}` branded approve/reject with feedback.
6. **Unified Analytics** — cross-network rollup, PPI leaderboard, feedback-loop weights,
   UTM click-through table.

All data comes from the running FastAPI backend (`http://localhost:8000`, `X-API-Key`
header). No external asset dependencies in the portal preview path.

> Status: backend API is live and complete for all screens above; scaffold the app in a
> follow-up session with `npx create-next-app@latest frontend --ts --tailwind --app`.
