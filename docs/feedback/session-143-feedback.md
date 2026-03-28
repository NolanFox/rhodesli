# Session 143 Feedback

## FB-001: Face card names show doubled/overlapping text on photo pages
- **Severity:** P0
- **Context:** User navigated to photo page (e.g., Victoria Capuano Capeluto photo). Face cards in "People in this photo" section show names rendered twice, overlapping — "Victoria**Capuano C**apeluto". Clicking the card does correctly navigate to person page.
- **Screenshot:** User-provided zoomed screenshot showing doubled text on Victoria's face card
- **Root cause:** Nested `<a>` tags — `name_el` was an `<a>` link to person page, AND the entire card was wrapped in another `<a>` to the same URL. Browsers flatten nested links, rendering both text nodes offset.
- **Fix:** FIXED in session. When card itself is a link, name_el and see_all_link use plain text instead of `<a>` tags.
- **Commit:** 982370fa

## FB-002: Face boxes on photo pages render incorrectly with overlapping text
- **Severity:** P1
- **Context:** User reported from Session 142 screenshots. On group photos (e.g., Fox Family), face overlay name labels overlap with adjacent face boxes when faces are close together. Labels positioned at `-bottom-5` collide with boxes below. Also labels near photo edges get clipped.
- **Root cause:** CSS positioning — name labels use `absolute -bottom-5` which overlaps with adjacent face boxes. No collision avoidance or edge detection.
- **Fix:** IN PROGRESS — UX review agent investigating. Needs CSS changes to handle edge cases.

## FB-003: Harness should mandate Chrome browser verification mid-session
- **Severity:** P1 (process)
- **Context:** User pointed out that Chrome verification should be mandated by the harness, not just at session end. The harness says "Browser verify" at session end but doesn't enforce it after UI changes mid-session.
- **Fix:** Needs harness rule update — add browser verification after any commit that touches app/main.py, app/*_routes.py, or static/

## FB-004: /ux-review skill should run on every Chrome screenshot automatically
- **Severity:** P1 (process)
- **Context:** User reminded that the /ux-review skill exists and should be used on every screenshot taken during a session. The harness mentions it in session-defaults.md but Claude didn't invoke it.
- **Fix:** Needs stronger harness enforcement — mandate /ux-review invocation after screenshots

## FB-005: Parallelize more aggressively
- **Severity:** P2 (process)
- **Context:** User wants maximum parallelization via agents. Should use as many agents as needed for independent tasks.
- **Fix:** Acknowledged — launching parallel agents for all independent work

## FB-006: Data safety is paramount — never lose data
- **Severity:** P0 (principle)
- **Context:** User explicitly stated: "we need to be resilient enough so that we never ever lose data" and "make sure in doing this week you don't do anything destructive to the data." All changes must be additive, reversible, and data-safe.
- **Fix:** All Session 143 changes are read-path only (no data mutations). JSON files preserved as backup.

## FB-007: Gemini API still on free tier (250/day) — Tier 1 NOT active
- **Severity:** P1 (blocker for Phase 5)
- **Context:** Batch script hit 429 RESOURCE_EXHAUSTED with `limit: 250, model: gemini-3.1-pro`. Despite context claiming Tier 1 (1,500/day), actual quota is 250/day. Retry in ~20h.
- **Root cause:** Billing may not be enabled at https://aistudio.google.com/apikey
- **Fix:** User needs to verify billing status. Once Tier 1 confirmed, batch can retry.
- **BACKLOG:** BATCH-005
