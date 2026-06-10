---
name: supabase-egress-crisis-and-fix
description: "Free plan has THREE separate limits (egress 5GB, disk-IO budget, DB-size 500MB). Egress fixed via TTLs/selective cols (Session 136). DB-SIZE is a DIFFERENT limit — see Session 163 / Lesson 200."
metadata: 
  node_type: memory
  type: project
  originSessionId: faf91da9-a91d-4602-bf27-137ec810da8e
---

## CORRECTION (Session 163, 2026-06-09) — READ THIS FIRST
Supabase Free tier has THREE INDEPENDENT limits that fail differently. Do NOT conflate them:
- **Egress (5 GB/mo)** — bandwidth. Fixed below (Session 136).
- **Disk-IO budget** — read throughput. Fixed Session 162 (Lesson 198).
- **DB SIZE (500 MB)** — storage. Tripped in Session 163 (the project had reverted Pro→Free
  and the DB was 1.3 GB). The site went down with `402 exceed_db_size_quota`.
The earlier assumption that egress/TTL reductions made it safe to "downgrade to Free" was
WRONG — it ignored DB SIZE. A 1.3 GB DB can never fit Free's 500 MB regardless of egress.
Session 163 cleaned the DB to 423 MB (dropped vestigial gedcom_events/records + 731,942
superseded relationship rows; all archived to R2). PRD-064 / Session 164 finishes the
redesign (Option B-plus: current-state-only tables + history in R2). See Lesson 200 +
Lesson 199 (non-atomic imports were the bloat root cause). [[feedback_platform_reliability]]

## Original (egress) note — Session 136, still valid for the egress limit

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
