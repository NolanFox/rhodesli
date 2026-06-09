# Session 163 Context — Supabase Restore + Site Recovery (UNPLANNED)

**Predecessor:** [session-162-context.md](session-162-context.md) (Disk IO Budget Remediation)
**Date:** 2026-06-08
**Type:** Unplanned emergency recovery (like 158e, 162). Triggered by user report + email
alerts that "parts of the site are down."
**Mode:** interactive

> NOTE: This session DISPLACES the originally-planned Session 163 (RHODES-WIKI-004:
> dossier auto-update + first wiki/ narrative pages). That work is re-numbered to a
> future session. See ROADMAP "Rhodes Wiki Integration."

## Symptom
Production `rhodesli.nolanandrewfox.com` loads but shows **0 people, 0 new matches,
0 help-identify, "0 of 0 identified"** while Photos still shows 1127. The app shell,
sidebar, version (v0.99.82), and admin login all render fine.

## Root Cause (confirmed)
`/health` returned:
```
"supabase":"error:[Errno -2] Name or service not known"
```
DNS NXDOMAIN on `db.fvynibivlphxwfowzkjl.supabase.co`. Supabase Management API
(`GET /v1/projects/fvynibivlphxwfowzkjl`) returned `"status": "INACTIVE"`.

**The Supabase project was PAUSED** — free-tier auto-pause after ~7 days of
inactivity (project had been on Pro for a month per memory `project_supabase_egress.md`,
then reverted to free and went idle). A paused project's DB hostname stops resolving,
so the app's startup sync + background registry refresh (DATA_SOURCE=postgres) all fail
silently (logged `registry_swr_refresh_error`), and the app serves stale/empty
community-scoped state.

## Why the UI showed 0 people but health showed 1824 identities
- In-memory registry had 1824 identities cached (loaded before the pause) via the
  600s stale-while-revalidate cache (`app/main.py:load_registry`).
- Background refresh kept failing (Supabase unreachable) → stale cache served.
- Community-scoped People count reads `identity_communities` via Supabase; that
  query failed/cached-empty (300s `_community_cache`) → People = 0.

## Fix Applied (partial — see REAL BLOCKER below)
1. Restored project via Management API: `POST /v1/projects/{ref}/restore` (HTTP 200).
2. Polled to `ACTIVE_HEALTHY` + DNS resolves.

## REAL BLOCKER — DB size quota (discovered after restore)
After unpausing, `/health` returned a NEW error:
```
error 402: Service for this project is restricted due to the following violations:
exceed_db_size_quota. The project owner must upgrade their plan or remove spend
caps to restore service.
```
The project reverted from Pro → **Free tier (500 MB DB limit)**, but the database
is **1,309 MB** (per ROADMAP, post-Session-162). Free tier can NEVER hold this DB.
This is the true cause of the outage; the "pause" was the free-tier inactivity
auto-pause on top of it.

**Correction to memory `project_supabase_egress.md`:** that note assumed downgrade
to free was safe based on EGRESS reductions. It conflated egress (bandwidth) with
DB SIZE. A 1.3 GB database structurally cannot fit the free tier's 500 MB cap.

### Resolution options (USER DECISION — billing/data)
- **A. Upgrade to Pro (~$25/mo, 8 GB DB)** — instant, no data loss, what it was before.
  RECOMMENDED. Restore service via dashboard billing or Management API upgrade.
- **B. Shrink DB < 500 MB to stay free** — must drop ~810+ MB. The GEDCOM tables
  (43k individuals / 13k families, power relationship+family pages) are the bulk.
  Lossy, large effort, and writes may be blocked while restricted (402) — likely
  need to upgrade temporarily to even run the cleanup. Not recommended.
- **C. Remove spend caps + payment method** — usage-based; for DB size ≈ Pro anyway.

Org: "Nolan Fox Projects" (`pkkbvxtoywxxfwyajikj`). Project ref `fvynibivlphxwfowzkjl`.

## Key Facts / Gotchas
- **Railway CLI not authenticated** this session (`railway status` → Unauthorized);
  Railway MCP failed (-32000). Restart-based instant recovery needs `railway login`.
- **SUPABASE_ACCESS_TOKEN** (sbp_...) IS present in `.env` — Management API works
  (Lesson 189 satisfied).
- Self-heal is automatic but slow (cache TTL). Deterministic recovery = Railway redeploy.

## Prevention candidates (BACKLOG)
- **OPS: paused-project monitor** — a scheduled health-check (cron) that pings
  `/health` and alerts if `supabase` != ok, OR pings Supabase Management API for
  `status != ACTIVE_HEALTHY`. Free-tier pause is silent until the site breaks.
- **OPS: keep-alive** — a tiny scheduled query (e.g., weekly cron hitting a cheap
  endpoint) prevents free-tier auto-pause entirely. Or stay on Pro.
- **App UX**: when `/health` supabase != ok, render an admin banner instead of a
  silent "0 people" (which looks like data loss, not an outage).

## Deferred
- RHODES-WIKI-004 (original Session 163 scope) → future session.
