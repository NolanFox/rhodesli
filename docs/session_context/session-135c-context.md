# Session 135c Context — Override Preview + Compare Active Side + UX Analysis

**Date:** 2026-03-23
**Predecessor:** [Session 135b Assessment](../assessments/session-135b-assessment.md)

## Origin

Three items deferred from Session 135b:
1. **FB-008 (P1)**: Override button in neighbor_card shows only a browser `confirm()` dialog. User cannot see WHICH photo has the co-occurrence or verify the face detections before committing to an override merge.
2. **FB-009 (P2)**: Compare Faces modal has two panels (target vs neighbor) but no visual indicator for which side is "active" — i.e., which side's photos the arrows will cycle.
3. **Speed-Run vs Focus UX overlap**: User reports these two triage surfaces blur together. Need design clarity on distinct purposes.

## Research Findings (from Session 135 exploration)

### FB-008: Co-Occurrence Override
- Override button: `app/main.py:9631-9656` (neighbor_card function)
- Uses `hx_confirm` which triggers browser's native confirm dialog
- `find_shared_photo_filename()` already exists to find the shared photo
- Co-occurrence data enrichment: `app/identity_routes.py:616-627`
- Face overlay rendering pattern exists in `compare_routes.py` (`_compare_photo_with_overlays`)
- PRD-048 exists but covers only the override reason selection, not the preview

### FB-009: Compare Active Side
- Compare modal skeleton: `app/main.py:10958-10993`
- Compare content (two panels): `app/compare_routes.py:5901-5937`
- Per-side arrow navigation helper: `app/compare_routes.py:5708-5751`
- Currently amber for target name, indigo for neighbor — but no panel-level indicator
- No keyboard navigation in compare modal (only in photo-modal)

### Speed-Run vs Focus Mode
- Speed-Run: `app/cluster_review_routes.py:847-870` — multi-face cluster triage
- Focus Mode: `app/main.py:7312-7501` — individual identity deep-dive with photo context
- Key difference: Speed-Run asks "Is this cluster correct?" vs Focus asks "Who is this person?"
- They serve genuinely different intents and should remain separate

## Parallelization Analysis

FB-008 touches `app/main.py` + `app/identity_routes.py`.
FB-009 touches `app/compare_routes.py`.
**Zero file overlap** → parallel worktrees are safe.

DD-018 is docs-only (orchestrator).

## Known Gaps & Risks
- FB-008 preview panel needs careful HTMX target management (Lesson 39: event delegation)
- Compare modal hyperscript may conflict with existing event handlers
- Face overlay rendering may need photo dimensions (cached in photo_index)
- Browser verification is READ-ONLY on production (Lesson 149)

## Cross-Feature Implications
- Override preview reuses face overlay from compare_routes — if compare_routes changes in Track B, overlay pattern still works (Track B only adds classes/attributes, doesn't change overlay rendering)
- DD-018 recommendations (sidebar rename) deferred to future session to avoid scope creep
