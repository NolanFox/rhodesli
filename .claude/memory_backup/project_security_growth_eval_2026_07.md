---
name: project_security_growth_eval_2026_07
description: 2026-07-05 security+growth eval — no breach; concierge-pilot roadmap; open user actions
metadata: 
  node_type: memory
  type: project
  originSessionId: 39796b3a-3698-4e97-9452-2c6c1a0136ff
---

**2026-07-05 session** (triggered by 51 anonymous "Compare Upload" pending entries the owner feared
were a breach). Full artifacts: `docs/fable-eval/2026-07-05-security-growth/` (read `INDEX.md` first).
Multi-model: Opus orchestrate+verify · Codex gpt-5.5 security audit + eval draft + brief audit-gate ·
Fable live-site architect/evaluator (read-only). Evaluation only — no code/data/prod mutation.

**Security = RESOLVED. No breach, no browser-reachable key exposure.** The 51 = the public
`/tools/compare` tool working as designed (anonymous upload → `pending_uploads` as `unknown`).

**OPEN USER ACTIONS (not yet done — surface these next session):**
1. **Rotate `ML_SERVICE_TOKEN`** on Railway — a real value is committed in
   `docs/session_logs/session-116-log.md` (internal ML service only, repo-read-access; not web-facing).
2. Reject the 51 pending Compare-Upload entries (currently one-at-a-time; no batch-reject exists).

**NEW verified P0 (Fable caught by loading the live site; both code drafts missed it):** cross-community
leak — `/c/rhodes/tree` renders the global/Fox GEDCOM. `/api/tree/data` (`app/page_routes.py:10950`)
uses community only for nav prefix, not data scoping. Lesson-151 class. Map/Timeline/Connect likely same.

**SUPERSEDED 2026-07-13** ([[project_research_desk_pivot]]): the GROWTH_ROADMAP is deprioritized —
owner redirected to the Research Desk program. Phase A P0s (tree leak, token rotation, ephemeral
compare) became session-171 Rider R; the concierge pilot waits until the owner uses the desk daily.
Original plan (kept for the record): `GROWTH_ROADMAP.md` — community-AWARE but not safe
multi-TENANT; concierge pilot, not broad self-service; gate is global-admin `_check_admin`
(`app/main.py:1972`). Phases A→B→C→D.
Related: [[project_upload_testing_reminder]] [[feedback_platform_reliability]].
