# Session 136: Supabase Migration Research

## Problem
Supabase free tier (5.5 GB egress/month) exceeded at 13.79 GB. Service restricted until April 5, 2026.
App is non-functional (API calls return 402).

## Root Cause Analysis
- 120s TTL SWR caches fire 24/7 from Railway, even from bot/crawler traffic
- `SELECT *` on identities (~1853 rows) and photos (~971 rows) fetches unused columns
- At ~1.4 MB per refresh cycle x 30/hr x 24/7 = ~30 GB/month theoretical max
- Actual usage: ~14 GB/month with typical admin activity

## Fixes Applied (Session 136)
1. Community filtering fails closed for ALL communities (security fix)
2. TTLs bumped 120s → 600s on all caches
3. Selective columns on identities (12 cols) and photos (12 cols)
4. SWR bot guard: skip refresh if no user page load in 5 minutes
5. Estimated post-fix egress: ~3 GB/month

## Migration Options Explored

### Option A: Upgrade to Pro ($25/mo)
- Immediate fix, zero risk
- 250 GB egress (will never hit)
- Can downgrade after verifying post-fix egress is under 5.5 GB

### Option B: New Supabase Org
- Fresh 5.5 GB quota immediately
- ~39 tables + 8 views to migrate
- ~25-60 MB total data
- Effort: 3-4 hours estimated
- Risk: Schema reconstruction from 25+ incremental migrations
- Mitigation: pg_dump from existing project (dashboard still works)
- Auth: Google OAuth reconfiguration needed
- Env vars: 4 to update on Railway

### Option C: JSON Fallback (REJECTED)
- Would reintroduce all data integrity issues (10+ incidents)
- No community filtering (photo_communities/identity_communities only in Supabase)
- Half the app's features disabled

### Option D: Convex (REJECTED)
- Full rewrite of data layer (~1800 lines in supabase_data.py)
- Not a stopgap, strategic decision
- Multiple sessions of work

## Supabase Tables (Full Inventory)
See agent research output for complete list of 39 tables, 8 views, 5 triggers,
1 RPC function, and pg_trgm extension.

## Decision
Codex CLI to independently review migration plan and assess risk. User will
upgrade to Pro tomorrow if migration isn't viable.

## Breadcrumbs
- OD-012: docs/ops/OPS_DECISIONS.md
- Egress rule: .claude/rules/egress-budget.md
- BACKLOG: EGRESS-001 (ETag), EGRESS-002 (incremental sync), EGRESS-003 (DONE)
