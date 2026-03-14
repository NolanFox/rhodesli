# Session 101 Context — Fox Triage P1 Fixes + Performance + Triage Sprint

**Predecessor:** `docs/session_context/session-100-master-status.md` (Session 100 complete as of 100g)
**Feedback source:** `docs/feedback/2026-03-14-fox-triage-feedback.md` (19 items, FB-100-119)
**Current state:** v0.99.3, 4276 tests, 941 photos, 3412 identities, 3 Fox Family confirmed (Charles Fox 68 faces, Esther Burd Fox 12, Roland Fox 31)

## What Happened

Nolan did a 20-minute Fox Family triage session using speed-run mode. He successfully confirmed and merged 3 people and linked 2 to GEDCOM. The core workflow WORKS but has significant friction:

1. **Enrichment flow order is backwards** — name input shows first, but merge should be first (if it's an existing person, the name comes from the merge target)
2. **Merge from speed-run is unclear** — clicked Merge, jumped to next card, no confirmation
3. **No GEDCOM linking from speed-run** — had to leave to person page
4. **Performance is very slow** — merge, similar, rename all take multiple seconds
5. **"Under Review" badge on CONFIRMED identities** — public page contradicts admin state
6. **Cross-community badges missing on suggestions** — Big Leon from Rhodes, no indicator
7. **Speed-run links go to public page** — should stay in admin context

## Key Architectural Insight: Performance

The performance issue (FB-105) is likely the most impactful fix. Every action (merge, similar, rename) reloads the full identity registry from JSON. With 1174 Fox Family identities + 3412 total, this is ~4500 identities parsed on every operation. The Supabase egress issue (OD-011) compounds this — TTL cache reloads pull full tables.

Candidate fixes:
- **Registry TTL cache** already exists (30s→120s in egress fix). Verify it's actually being used.
- **Merge should not reload full registry** — it already has the registry in memory
- **Similar endpoint** may be doing full embedding scan — check if it uses the precomputed neighbors
- **Rename** should be a single identity update, not full save+reload

## Cross-Community Badge Gap

The enrichment panel suggests Big Leon Capeluto (Rhodes) alongside Fox Family matches. This is architecturally correct (cross-community matching) but visually indistinguishable. The badge system from Session 96d (COMMUNITY-014) exists on discovery cards but was never added to:
- Speed-run enrichment suggestions
- Similar identities panel
- Person page match results

## Enrichment Panel Flow Redesign

Current order: Name input → Merge search → (nothing else)
Correct order: Merge search → Name input (pre-filled from merge target if merged) → GEDCOM link

This is a reorder of existing components plus adding GEDCOM search (which already works on the person page — just needs to be embedded in the enrichment panel).

## Performance Profiling Targets

1. `save_registry()` — how long does atomic JSON write take for 3412 identities?
2. `_get_neighbors()` / similar endpoint — is it doing full pairwise comparison or using precomputed?
3. Registry cache — is the TTL cache actually being hit, or is every request a full reload?
4. Supabase shadow writes — are background threads backing up?

## Files Likely Modified

- `app/cluster_review_routes.py` — enrichment panel reorder, GEDCOM link, merge confirmation
- `app/main.py` — performance profiling, cache behavior, "Under Review" badge logic
- `app/page_routes.py` — public person page status badge
- `core/registry.py` — merge performance
- `tests/test_cluster_review_routes.py` — new tests for reordered flow

## Known Risks

- **Data regression** — merges modify identities.json. Every merge must go through `save_registry()` with Supabase shadow write. Test merge paths thoroughly.
- **Test speed** — full suite is ~150s. Use targeted tests during development, full suite before commits.
- **Cache invalidation** — performance improvements that add caching can cause stale data. Every cache must invalidate on mutation.
