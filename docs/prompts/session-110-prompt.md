# Session 110 — James Fields UX Bug Sprint

## Context
@docs/session_context/session-110-context.md

## Pre-Requisites
- Read ALL feedback bugs FB-016 through FB-024 in the context file
- Read `app/main.py` — `neighbor_card()`, `_similar_identities_panel()`, merge handlers
- Read `app/identity_routes.py` — confirm handler, merge handler
- Read `core/registry.py` — `merge_identities()` with override param
- Test case: Person 28fa8bfa-4270-4b60-b549-5f7b8515410d (James Henry Jimmy Fields, CONFIRMED)

## Phase 0: Orient + Reproduce (10 min)

1. Verify 109b deploy live
2. Navigate to James Fields person page in browser
3. Reproduce FB-019 (individual merge button fail) and FB-021 (override fail)
4. Capture the network requests to understand what's happening

## Phase 1: Fix P0 Bugs — Merge + Override (30 min)

### FB-019: Individual Merge button silently fails
1. Find the `hx_post` URL for the individual merge button in `neighbor_card()`
2. Trace the endpoint handler — is it returning an error?
3. Check if the HTMX swap target exists in the DOM
4. Fix and verify with browser

### FB-021: Override button does nothing
1. Find the Override button handler (Session 108b, PRD-048)
2. It shows a tooltip but doesn't trigger merge
3. Add a confirmation dialog: "These faces appear in the same photo. Are you sure they're the same person?"
4. On confirm, call merge endpoint with `override_co_occurrence=true`
5. Fix and verify with browser

Tests:
- Test: Individual merge button returns success response
- Test: Override button triggers merge with co-occurrence override
- Test: Override merge respects confirmation (not auto-merge)

## Phase 2: Fix P1 UX Bugs (30 min)

### FB-017: Confirm creates duplicate card + stale buttons
1. Check the confirm endpoint's HTMX return — what element is being swapped?
2. Fix the swap target so the old card is replaced, not appended
3. Remove Confirm/Skip/Reject buttons from the returned card (identity is now CONFIRMED)
4. Verify INBOX badge is replaced with CONFIRMED badge

### FB-018: Find Similar broken after Confirm
1. After confirm, the page state is stale (identity was INBOX, now CONFIRMED)
2. Find Similar may be looking up the identity by state
3. Fix: after confirm swap, ensure the Find Similar button targets the correct identity state
4. Or: force a panel refresh after confirm

### FB-020: Merge closes Similar panel
1. The merge handler likely returns a response that replaces the entire panel
2. Instead: after merge, re-render the Similar Identities panel with the merged face removed
3. Use `hx_swap="outerHTML"` on the specific face card, or re-fetch the panel
4. This is the highest-impact UX fix — turns 60s workflow into 15s

### FB-016 + FB-023 + FB-024: Slowness
1. Add HTMX loading indicators (`hx-indicator`) to Rename, Confirm, Find Similar, Merge buttons
2. Show spinner or "Loading..." text while waiting for response
3. For rename: add `hx-indicator` class to the button
4. For confirm: same
5. For GEDCOM: same
6. This doesn't fix the underlying speed but prevents "is it broken?" perception

Tests:
- Test: Confirm returns card without action buttons
- Test: Merge response re-renders panel (not closes it)
- Test: Loading indicators present on slow-action buttons

## Phase 3: Browser Verify (15 min)

Walk through the EXACT James Fields workflow:
1. Go to a Similar Identities panel with co-occurrence blocked faces
2. Click individual Merge → verify it works
3. Click Override → verify confirmation dialog → verify merge
4. Verify panel stays open after merge
5. Verify loading indicators on slow actions
6. Screenshot each step

## Phase 4: Harness Outputs (10 min)

1. Assessment: docs/assessments/session-110-assessment.md
2. Session log
3. Update BACKLOG with any remaining items
4. Update ROADMAP, CHANGELOG
5. Verify all breadcrumbs

## Verification Checklist

- [ ] Individual merge button works on person page
- [ ] Override button shows confirmation then merges
- [ ] Confirm doesn't create duplicate card
- [ ] Find Similar works after confirm (no page refresh needed)
- [ ] Similar panel stays open after merge
- [ ] Loading indicators on rename, confirm, merge, GEDCOM
- [ ] All tests pass
- [ ] CI green
- [ ] git log origin/main..HEAD is empty

## Reference: James Fields Test Identities

| Identity | Distance | Status | Notes |
|----------|----------|--------|-------|
| 28fa8bfa | (source) | CONFIRMED | James Henry Jimmy Fields |
| 1c8c316f | 0.84 | Co-occurrence blocked | Same collage photo |
| 3474 | 0.87 | Co-occurrence blocked | Same collage photo |
| 5e3de5c5 | 0.91 | Co-occurrence blocked | Same collage photo |
| 3347 | 1.01 | Mergeable | Different photo |
| 3895 | 1.13 | Mergeable | Review — may not be James Fields |
| 0cb65795 | 1.16 | Mergeable | Review — baby photo |
| 3650 | 1.20 | Mergeable | James Fields at piano |
| 558 | 1.14 | Cross-community | Jewish Community of Rhodes |
