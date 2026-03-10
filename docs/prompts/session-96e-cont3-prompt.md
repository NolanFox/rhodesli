# Session 96e-cont3 — Browser Verify + Remaining UX Fixes

**Context:** `docs/session_context/session-96e-feedback.md`, `docs/assessments/session-96e-cont2-assessment.md`
**Previous commits:** `800d4ac` (complete-linkage grouping + UI fixes), `b63e166` (session docs)
**Priority:** P0 — Must browser-verify all fixes, then complete remaining UX work

---

## What Was Fixed in cont2 (NEEDS BROWSER VERIFICATION)

1. **Complete-linkage grouping** — Max cluster now 44 faces (was 252 garbage). 582 merges, 294 groups.
2. **Sort control community prefix** — Sort links include `/c/{slug}/` via `nav_prefix` param in `_sort_control()` (main.py:5531).
3. **Name truncation** — "Person NNNN" instead of "Unidentified Person ..." on cards (main.py:8942).
4. **Upload Review Grouped Identities** — New section showing multi-face clusters (cluster_review_routes.py).
5. **Proposals filtered to < 1.05** — 17 proposals (was 2115).

## Act 1: Browser Verify All Fixes (Claude Chrome)

Navigate to production and verify each fix:

1. `/c/fox-family/?section=to_review&view=browse` — Cards show "Person NNNN" not truncated
2. `/c/fox-family/?section=to_review&view=browse&sort_by=faces` — Stays on Fox Family (not Rhodes). Largest cluster ~44 faces.
3. `/c/fox-family/?section=to_review&view=browse` — Click "Similar" on any cluster. Should NOT show "Dist: 0.00" entries (or if still present, investigate).
4. `/c/fox-family/admin/upload-review` — Shows "Grouped Identities" section with clusters. Shows "Proposal Matches" (not "Cluster Review"). Shows GEDCOM Triage.
5. `/c/fox-family/?section=to_review&view=match` — Match view works, shows face comparison.

Save screenshots to `docs/screenshots/session-96e-cont3/`.

## Act 2: Fix Remaining Issues

### FIX 1: Match view — Up Next carousel + ordering by strongest matches
- **File:** `app/main.py` — search for `view_mode == "match"` in `render_to_review_section()`
- Match view should order identities by strongest proposal match (lowest distance first)
- Add Up Next carousel below the match comparison (same pattern as focus view)
- Face cards in match view must be consistent with browse view

### FIX 2: Duplicate face detections (Dist: 0.00, "Seen together in 1 photo")
- **Root cause:** Face detection pipeline detected same face twice in some photos, creating separate identities with near-identical embeddings
- **Investigation:** Run this to find duplicates:
  ```python
  # Find identity pairs with distance 0.00 that share a photo
  # These are duplicate face detections, not real matches
  ```
- **Fix options:**
  a. Dedup at identity level: merge identities that share a photo AND have distance < 0.1
  b. Filter from Similar Identities display: don't show neighbors with Dist < 0.1 AND co-occurrence
  c. Dedup at embeddings level: remove duplicate bbox detections from same photo
- Option (b) is fastest fix for UI. Option (c) is the proper fix.

### FIX 3: Face card consistency across views
- Focus, Browse, Match, Upload Review should all use consistent card components
- Currently Upload Review uses custom `_face_match_card()` while main app uses `identity_card()`
- At minimum: ensure all views show name (not truncated), face count, community badge

## Act 3: Session Wrap
1. Update assessment with browser verification results
2. Update CHANGELOG, ROADMAP
3. Final `make test-fast` + commit

## Key Files
- `app/main.py` — `render_to_review_section()` (line ~5273), `_sort_control()` (5531), `identity_card()` (8678), `neighbors_sidebar()` (8363)
- `app/cluster_review_routes.py` — Upload Review page
- `app/identity_routes.py` — `/api/identity/{id}/neighbors` endpoint (line 269)
- `core/neighbors.py` — `find_nearest_neighbors()` (line 44)
- `docs/session_context/session-96e-feedback.md` — All user P0 feedback

## Verification Checklist
- [ ] Browse view: "Person NNNN" visible (not truncated)
- [ ] Sort links: stay on `/c/fox-family/` (not redirect to Rhodes)
- [ ] Clusters: max ~44 faces, not 252
- [ ] Upload Review: Grouped Identities section visible
- [ ] Upload Review: Proposals filtered (17 not 2115)
- [ ] Similar Identities: no Dist 0.00 entries (or filtered)
- [ ] Match view: Up Next carousel present
- [ ] Match view: ordered by strongest match
- [ ] All tests pass
