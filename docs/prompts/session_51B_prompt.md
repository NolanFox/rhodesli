# Session 51B: Production Bug Fixes — Manual Testing Failures

## Session Identity
- **Previous session:** Session 51 (Quick-Identify, v0.51.0)
- **Goal:** Fix bugs found during manual production testing. Multiple features claimed as "shipped" are not working for real users.
- **Time budget:** ~30 min
- **Priority:** P0 — public-facing features are broken

## Bugs
1. **BUG 1 (P0):** Compare Upload — "Photo saved!" but no comparison results
2. **BUG 2 (P0/Auth):** "Name These Faces" button missing on photo page
3. **BUG 3 (P1):** Compare/Estimate tab duplication
4. **BUG 4 (P0):** Supabase inactivity — 0 requests, pause imminent
5. **BUG 5 (P2):** No email notifications (known missing, just audit)

## Verification Standard
FUNCTIONAL verification — simulate real user flows, check response CONTENT not just status codes.

## Phases
- Phase 0: Orient + Diagnose
- Phase 1: Fix Compare Upload Pipeline
- Phase 2: Verify "Name These Faces"
- Phase 3: Remove Estimate Tab from Compare
- Phase 4: Supabase Keepalive + Auth Warning
- Phase 5: Email Notification Audit
- Phase 6: Verification Gate
- Phase 7: Docs + Push
