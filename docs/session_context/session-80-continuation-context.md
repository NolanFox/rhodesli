# Session 80 Continuation Context

## What Was Done
- Acts 0-7 of session 80 completed across multiple context windows
- v0.82.0 deployed with tree overhaul, face card redesign, GEDCOM fixes

## Critical Files Modified
- `app/main.py`: identity_card() photo-dominant redesign (DD-005), Find Similar full-page route, review_action_buttons de-emphasis, tree node best-face selection
- `app/static/js/family-tree.js`: Gender silhouettes, timeline crossfade animations, card entrance/line draw-in animations, expand pulse
- `data/relationships.json`: Replaced 1000 wrong xref-based rels with 1221 correct GEDCOM-sourced rels from Fox/Capeluto tree
- `data/gedcom_matches.json`: Added Matilda Capouano + Hanula Mosafir (35 total matches)

## Key Commits (in order)
- d64a5fb: Photo-dominant cards + tree gender silhouettes
- 1bac4eb: Timeline slider + fluid card animations (worktree)
- 67ce57d: Merge tree JS animations
- 3a93561: Collapsible admin, full-page similar, de-emphasize reset
- e1f5216: GEDCOM relationships + best-face selection + card UX

## REMAINING TASKS — Parallelizable by File

### Track A: family-tree.js (independent — can use worktree)
1. **Per-person photo cycling**: Click arrows on tree node to flip through that person's faces. `all_faces` array is already in node data. Reset to slider-appropriate photo when timeline scrubs.
2. **Expand/collapse from ANY node**: Currently only focal person can expand. Need expand arrows on every node that has hidden connections. Like Ancestry: start at Roland, expand to Betty's parents, expand to Abraham's parents.
3. **Multiple spouse support**: Currently only first spouse shown. Need to handle cases like GEDCOM families with remarriages.
4. **Relationship visualization**: Research suggests: thicker lines for direct parent-child, labels like "father"/"mother" on hover, generation bands (alternating subtle background stripes), pedigree collapse indicators.
5. **Text readability**: Increase font sizes for names (currently ~11px at normal zoom). Birth-death years need higher contrast. Consider: white text with subtle text-shadow for readability over dark background.

### Track B: app/main.py — Find Similar + Share (independent — can use worktree)
6. **Verify Find Similar page**: Navigate to /people/{id}/similar in production, confirm hero + grid renders correctly with real neighbor data.
7. **Share button restoration**: The Web Share API button was added as an overlay on hero section but full share_button() function may need to be wired properly. Check share_button() at line ~6204.
8. **Multi-face gallery**: For identities with many photos, show 2-3 stacked face thumbnails on the card with expand-on-click.

### Track C: Data fixes (can run in parallel)
9. **Match remaining 25 identities to GEDCOM**: Many are clear matches (Boulissa Pizanti, Victoria Cukran, etc.) — look up xrefs in GEDCOM file at ~/Downloads/Fox_Capeluto_Fogel_Waldorf Family Tree.ged
10. **Fix Supabase GEDCOM face links**: Matilda (a2889099) is linked to wrong GEDCOM record (Mathi Capelluto @I132423679471@ instead of Matilda Cap Capelouto @I132127360994@). Need to update via Supabase API.

### Track D: Documentation
11. DD-005 entry in DESIGN_DECISIONS.md
12. AD updates for GEDCOM relationship import decision
13. Session assessment

## GEDCOM File Location
`~/Downloads/Fox_Capeluto_Fogel_Waldorf Family Tree.ged` — 21,809 individuals, 6,680 families

## Review CSV
`~/Downloads/gedcom_match_review.csv` — Session 49B human-verified matches with corrected Ancestry IDs

## Architecture Notes
- Tree API: /api/tree/data, /api/tree/expand, /api/tree/search
- Tree renders via D3.js in family-tree.js
- GEDCOM individuals come from Supabase `current_gedcom_individuals` view
- GEDCOM face links come from Supabase `gedcom_face_links` table
- Relationships.json has both UUID-based rels (manual) and xref-based rels (from GEDCOM)
- _build_tree_adjacency() resolves xrefs→UUIDs using _load_gedcom_face_links()
- _build_tree_person_lookup() builds lookup from confirmed identities + GEDCOM individuals
- _make_tree_node() constructs each node with avatar, faces, rels, expansion flags

## User's Standard
"This should be even better than Ancestry but have at least all the functionality."
Animations must be fluid and modern. Names/dates must be readable. Best practices across the app.
