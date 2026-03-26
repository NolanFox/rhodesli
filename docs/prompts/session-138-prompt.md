# Session 138: Refactor Phase 2 + Worktree Cleanup + Harness Polish

## Context
Supabase still down (egress exceeded). All work is Supabase-independent.
See `docs/session_context/session-138-context.md` for full background.
Codex CLI audit of Session 137 pending — incorporate findings at session start.

## Session Setup
```bash
echo "138" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline (~3748 tests)
```

## Track 1: REFACTOR-001 Phase 2 — cards.py + photo.py
**Sequential (touches main.py). No worktree isolation.**

### 1a. Extract `app/components/cards.py`

Target functions (in extraction order — simplest first):
1. `match_info_bar()` (line 8822, ~60 lines) — depends on `_confidence_tier_label` (already in badges.py)
2. `face_card()` (line 8696, ~120 lines) — depends on `resolve_face_image_url`, `get_face_quality`
3. `neighbor_card()` (line 8884, ~160 lines) — depends on `match_info_bar`, `get_crop_url`
4. `identity_card()` (line 9647, ~250 lines) — depends on `get_best_face_id`, `_cross_community_badge`, `resolve_face_image_url`
5. `identity_card_expanded()` (line 5748, ~300 lines) — largest card, most dependencies
6. `lane_section()` (line 10303, ~50 lines) — depends on `identity_card`

**Pattern**: Use lazy imports inside function body for main.py dependencies:
```python
def face_card(face_id, ...):
    import app.main as _m
    url = _m.resolve_face_image_url(face_id)
    ...
```

After each function extraction:
1. Replace body in main.py with import re-export
2. Run `make test-fast`
3. Commit: `refactor: extract [function] to app/components/cards.py`

### 1b. Extract `app/components/photo.py`

Target functions:
1. `_build_face_alignment_section()` (line 3493, ~219 lines)
2. `_build_ai_analysis_section()` (line 2975, ~436 lines) — uses `_evidence_card` and `_detective_evidence_section` (already in layouts.py)

These are the largest single functions. Use lazy imports for `get_photo_url`, `_photo_cache`.

### 1c. Extract remaining badges/nav
1. `_cross_community_badge()` (line 814, ~51 lines) → badges.py
2. `_build_triage_bar()` (line 3792, ~58 lines) → nav.py
3. `neighbors_sidebar()` (line 9291, ~15 lines) → nav.py

### Success criteria:
- `wc -l app/main.py` ≤ 8,500 lines (Phase 2 target — realistic reduction of ~2,100 lines)
- `make test-fast` passes
- `python -c "import app.components"` succeeds
- No circular imports at module level (lazy imports inside functions are OK)
- Each extraction committed atomically

## Track 2: Worktree Cleanup
**Quick — do first.**

Verify Session 137 worktree branches are deleted (done in Session 137 closure):
```bash
git branch | grep session-137  # Should be empty
git worktree list  # Should only show main
ls .claude/worktrees/  # Should be empty or not exist
```

If any remain, clean up. Also remove any stale worktree directories from previous sessions.

## Track 3: Harness Polish
**Quick — do after Track 2.**

1. Update `docs/session_context/session-137-codex-audit.md` with Codex CLI findings (replace Claude subagent findings with independent Codex CLI results). Keep both for comparison.
2. Update `docs/assessments/session-137-assessment.md` AI Tools section with provenance per updated `ai-tool-audit.md` rule.
3. Commit harness rule update (`ai-tool-audit.md` model/agent tracking).

## Codex CLI Audit
Run Codex CLI (`codex exec --full-auto`) on Track 1 after all extractions:
```
codex exec --full-auto "Audit app/components/cards.py and app/components/photo.py for security, code quality, and correct lazy imports. Check that all re-exports in main.py work. P0/P1/P2/P3 report."
```
Save to `docs/session_context/session-138-codex-audit.md` with provenance header.

## Session End Checklist
- [ ] All tracks complete
- [ ] `make test-fast` passes
- [ ] `wc -l app/main.py` shows further reduction
- [ ] Assessment written with AI Tools section (provenance tracking)
- [ ] Codex CLI audit saved with provenance header
- [ ] CHANGELOG updated (v0.99.49)
- [ ] ROADMAP updated (REFACTOR-001 Phase 2 status)
- [ ] BACKLOG updated
- [ ] SESSION_HISTORY updated
- [ ] Commit (push blocked until Supabase restored)
