# Session 82d — Archaeology Summary

## Key Findings

### Card Hierarchy (evolved sessions 74-81)
1. **`identity_card_compact()`** (line 7026) — browse grids, shows ONE face, Confirm/Reject/Skip actions
2. **`identity_card()`** (line 7203) — confirmed/skipped sections, hero face + pills + collapsible admin
3. **`identity_card_expanded()`** (line 3691) — focus mode, full context + neighbors sidebar
4. **`face_card()`** (line 6476) — individual face crop, ONLY inside identity_card() admin tools

### Two "Find Similar" Paths
1. **Full page**: "Similar" pill -> `/people/{id}/similar` (standalone page)
2. **HTMX inline**: Overflow menu "Find Similar" -> `/api/identity/{id}/neighbors`

### No Expansion Panels Exist
Zero results for "expansion-panel". Collapsible elements use `<Details>/<Summary>`.

### Shared `face_card()` Is Underused
Only called in 3 of 14+ face rendering locations. Rest are inline bespoke code.

## Bugs Found (by Bug Inventory Agent)

| Bug | Severity | Description |
|-----|----------|-------------|
| 1 | P0 | `/api/photos/more` uses wrong key (`face_ids` vs `faces`) — lazy-loaded photos show 0 faces |
| 2 | P1 | Person page admin buttons (Edit/Find Similar/View Admin) all go to same URL |
| 3 | P1 | Photos/Faces toggle is full page navigation, not HTMX partial swap |
| 4 | P1 | Focus mode main photo click highlights wrong face (loop variable leak) |
| 5 | P2 | Find Similar on browse cards navigates away instead of inline expansion |
| 6 | P2 | People page shows face count labeled as "photos" |
| 7 | P2 | Sidebar JS duplicated 12 times |
