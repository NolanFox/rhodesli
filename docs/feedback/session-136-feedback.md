# Session 136 Feedback

Interactive triage session — pivoted to Supabase egress crisis.

### FB-001: Supabase Egress Quota Exceeded — Community Filtering Failed Open
- **Severity:** P0
- **Context:** User opened app, saw Fox Family identities on Rhodes community page. 1519 "New Matches" showing cross-community data. Supabase returned 402 (egress quota exceeded), causing `_get_community_identity_ids()` to return `None` for Rhodes (fail-open).
- **Root cause:** Rhodes had special-case fail-open logic (return None instead of empty set) when Supabase was unavailable. Combined with 13.79 GB / 5.5 GB egress overage.
- **Fix:** FIXED — community filtering now fails closed for ALL communities including Rhodes.

### FB-002: Supabase Egress Budget — TTLs Too Aggressive
- **Severity:** P1
- **Context:** 120s TTL caches doing full `SELECT *` reloads 24/7. SWR background refresh triggered by bot/crawler traffic even when admin is not using the app. Estimated ~14 GB/month.
- **Root cause:** TTLs designed for multi-admin freshness that doesn't exist. Single admin, writes invalidate cache immediately. SWR fires on every stale request including bots.
- **Fix:** FIXED — TTLs bumped 120s→600s, selective columns on identities/photos, SWR bot guard (5 min activity window).

### FB-003: User Frustration — AI Subscriptions Wasted During Downtime
- **Severity:** P1 (user experience)
- **Context:** User paying for Claude Code subscriptions but can't do interactive triage for ~12 days until Supabase quota resets April 5. App is non-functional.
- **Options explored:** Pro upgrade ($25/mo), new Supabase org (migration), JSON fallback (rejected — too many past data integrity issues), Convex (rejected — full rewrite).
- **Decision:** Codex to review migration plan. User will upgrade to Pro tomorrow if migration isn't viable.

### FB-004: Egress Issue Should Have Been Caught Earlier
- **Severity:** P2 (process)
- **Context:** User correctly noted that OD-011 (Session 100e) identified the egress problem but only bumped TTLs from 30s to 120s. The decision document listed selective columns and longer TTLs as future optimizations (EGRESS-001/002/003) but they were never implemented. This is the second quota violation.
- **Root cause:** "Good enough" fix that didn't address the structural problem. BACKLOG items created but never prioritized.
- **Lesson:** When a quota/budget issue is identified, fix it fully — don't create BACKLOG items for the actual solution.
