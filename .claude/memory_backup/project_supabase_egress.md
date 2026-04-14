---
name: Supabase egress crisis and fix
description: Free plan exceeded 13.79GB/5.5GB March 2026. Service restricted until April 5. TTLs bumped 120s→600s, selective columns, SWR bot guard. Estimated post-fix 3GB/mo.
type: project
---

Supabase restricted project on 2026-03-23 — 13.79 GB of 5.5 GB quota consumed.
Service unavailable until quota resets April 5, 2026 (not April 13 grace period as previously thought).
Dashboard access still works, API calls blocked.

**Root cause:** 120s TTL SWR caches fire 24/7 from Railway. Bot/crawler traffic triggers stale-while-revalidate
background refreshes even with no admin activity. `SELECT *` on identities/photos fetches unused columns.
At ~1.4 MB per refresh cycle × 30/hr × 24/7 = ~30 GB/month theoretical max.

**Fix (Session 136, OD-012):**
1. TTLs 120s → 600s on ALL caches (5x reduction in refresh frequency)
2. Selective columns on identities + photos queries (12 cols each instead of `*`)
3. SWR bot guard: skip refresh if no real user page load in last 5 minutes
4. Community filtering fail-closed for ALL communities (was fail-open for Rhodes)

**Estimated post-fix egress: ~3 GB/month** — within free tier.

**Why:** The 120s TTL was designed for multi-admin freshness that doesn't exist. Single admin
writes invalidate cache immediately. The only scenario where TTL matters is external DB edits.

**How to apply:**
- EGRESS-003 (selective columns) is DONE
- Monitor after April 5 deploy — if still over quota, upgrade to Pro ($25/mo)
- Rule: `.claude/rules/egress-budget.md`
- Decision: OD-012 in docs/ops/OPS_DECISIONS.md
