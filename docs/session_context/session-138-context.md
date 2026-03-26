# Session 138 Context — Refactor Phase 2 + Cleanup + Harness

**Predecessor:** Session 137 (v0.99.48) — Parallel refactor + tests + design
**Date:** 2026-03-25

## What Session 137 Delivered
- 7 `app/components/` modules: badges, forms, layouts, modals, nav, toasts, __init__
- 1,127 lines extracted from main.py (11,765 → 10,638)
- 68 new ML tests (658 total), 13 xfail TOOLS-005 skeletons
- Flaky xdist cache reset expansion (30+ caches)
- Codex CLI audit: 0 P0, 2 P1 (both fixed), 5 P2 (3 fixed, 2 deferred)

## What Session 137 Did NOT Do
- **cards.py**: `identity_card` (line 9647), `identity_card_expanded` (line 5748), `neighbor_card` (line 8884), `face_card` (line 8696), `match_info_bar` (line 8822), `lane_section` (line 10303) — all tightly coupled to main.py state
- **photo.py**: `_build_ai_analysis_section` (line 2975, ~436 lines), `_build_face_alignment_section` (line 3493, ~219 lines) — largest single functions, worktree persistence issues
- **Also not extracted**: `_cross_community_badge` (line 814, ~51 lines), `_build_triage_bar` (line 3792, ~58 lines), `neighbors_sidebar` (line 9291)
- main.py target was ≤6,500 lines — achieved 10,638 (4,138 lines over target)

## Phase 2 Strategy: Parameter Injection Pattern
Functions that reference main.py globals need their dependencies injected as parameters:
```python
# Instead of:
def identity_card(identity, crop_files, ...):
    photo_id = get_photo_id_for_face(...)  # main.py global

# Extract as:
def identity_card(identity, crop_files, *, get_photo_id_for_face=None, ...):
    if get_photo_id_for_face is None:
        from app.main import get_photo_id_for_face
    ...
```
This avoids circular imports while allowing test injection.

## Key Dependencies to Map
| Function | main.py globals used |
|---|---|
| identity_card | get_crop_url, resolve_face_image_url, get_best_face_id, _cross_community_badge |
| neighbor_card | match_info_bar, _confidence_tier_label, get_crop_url |
| face_card | resolve_face_image_url, get_face_quality |
| _build_ai_analysis_section | _evidence_card (already extracted), _detective_evidence_section (already extracted) |
| _build_face_alignment_section | get_photo_url, _photo_cache |

## xpassed Tests Finding
The 2 xpassed tests only appear under xdist parallelization (cache bleed from other tests). When run alone, all 15 are xfail. Not a real feature implementation — it's a test isolation artifact. No fix needed beyond documentation.

## Harness Improvements Needed
Per user feedback in Session 137:
1. AI tool audit must track **model** and **agent type** (independent vs resume) — DONE in ai-tool-audit.md
2. Codex CLI (not Claude subagent) for audits — ensures independent review
3. Provenance tracking is mandatory in all audit artifacts

## Supabase Status
Egress exceeded, grace period until 2026-04-13. All work must be Supabase-independent until restored or upgraded to Pro ($25/mo).

## Cross-references
- BACKLOG: REFACTOR-001 (in progress, Phase 2)
- PRD: docs/prds/056_mainpy_refactoring.md
- AD: None needed (mechanical refactor, no algorithmic decisions)
- Lessons: 88 (monolithic app prevents parallel worktrees)
