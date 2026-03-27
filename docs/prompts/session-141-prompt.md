# Session 141: Fix Sprint + Refactor + Hardening

## Context
7 outstanding items from Sessions 138-140. User is away — work autonomously.
See `docs/session_context/session-141-context.md` for full research and dependency maps.
**Codex CLI audit MANDATORY after each track** (HD-030).
**User approved all actions.** Proceed without asking for permissions.

## Phase 0: Setup
```bash
echo "141" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline (~3780 tests)
```

## Track A: Structural Test + FB-002 Toast Link (worktree)
**Goal**: Prevent auth-style regressions + show merged identity link.

### A1: Structural test for _main_mod references (Lesson 157)
Write `tests/test_main_mod_references.py`:
```python
def test_all_main_mod_references_resolve():
    """Every _main_mod.X reference in route files must exist in app.main."""
    import app.main as m
    import re, os
    route_files = [f for f in os.listdir('app') if f.endswith('_routes.py')]
    missing = []
    for fname in route_files:
        with open(f'app/{fname}') as fh:
            refs = set(re.findall(r'_main_mod\.(\w+)', fh.read()))
        for ref in refs:
            if not hasattr(m, ref):
                missing.append(f'{fname}: _main_mod.{ref}')
    assert not missing, f"Broken _main_mod references: {missing}"
```
Also add a test that warns about `create=True` in mock patches.

### A2: FB-002 — Link to merged identity in toast
In identity_routes.py merge handler (~line 2338), after merge succeeds:
- Build a link to the surviving identity: `<a href="/person/{actual_target_id}">View {name}</a>`
- Include it in the merge toast message
- The toast already uses OOB swap — just add the link HTML

### A3: Tests for both

## Track B: FB-007 Hero Face Picker (worktree)
**Goal**: Let admin choose which face is the "hero" thumbnail.

### B1: Add `primary_face_id` field
- In `core/registry.py`, add `primary_face_id` to identity schema
- `get_best_face_id()` in main.py: check `identity.get("primary_face_id")` first
- If set and valid (face exists in anchor_ids/candidate_ids), use it
- Fall back to quality-based selection if not set

### B2: UI — "Set as Primary" button on face cards
- In `app/components/cards.py` face_card(), add a small star/pin icon button (admin only)
- POST to `/api/identity/{id}/set-primary-face/{face_id}`
- Handler in identity_routes.py: sets primary_face_id, saves, returns updated card

### B3: Supabase column
- Add `primary_face_id` to shadow_write_identities if not already present
- Check if column exists, add migration note if needed

### B4: Tests

## Track C: Performance Quick Wins (worktree)
**Goal**: heapq sort + parallel cold start.

### C1: heapq.nsmallest for focus mode sort
In app/main.py `render_to_review_section()`:
- Current: `sorted(to_review, key=_focus_sort_key)[:10]` — sorts ALL items
- Fix: `heapq.nsmallest(10, to_review, key=_focus_sort_key)` — only finds top 10
- Import heapq at top of file

### C2: Parallel cold start Supabase fetches
In app/main.py `_prewarm_caches()`:
- Current: sequential Supabase queries (registry, photo_registry, sync data)
- Fix: use `concurrent.futures.ThreadPoolExecutor` to parallelize
- Measure before/after with timing logs

### C3: Tests + benchmarks

## Track D: REFACTOR-001 Phase 3 (sequential — after A/B/C merge)
**Goal**: Extract identity_card + identity_card_expanded, main.py ≤ 9,000.

### D1: Extract shared utility functions
- `_sequential_display_name` (~25 lines) — pure utility
- `_proposal_banner`, `_proposal_badge_inline` (~65 lines) — UI builders

### D2: Extract identity_card_expanded (~272 lines)
- Fewer external callers (2 in main.py only)
- Uses lazy `import app.main as _m` for cache-dependent functions

### D3: Extract identity_card (~566 lines) + identity_card_compact
- 10 call sites in identity_routes.py (all via `_main_mod.identity_card`)
- Re-export in main.py for backward compat

### After each extraction: `make test-fast`, commit atomically

## Track E: FB-003 PRD Analysis (worktree — docs only)
**Goal**: Define when merge→auto-confirm is safe.

Write analysis in `docs/prds/058_merge_auto_confirm.md`:
- **Safe cases**: merging INTO a CONFIRMED identity (target is already confirmed)
- **Unsafe cases**: merging two INBOX/PROPOSED identities (neither validated)
- **Proposed rule**: auto-confirm ONLY when the surviving identity is already CONFIRMED
- **Implementation**: in merge handler, if `target.state == "CONFIRMED"`, skip the confirm step (it's already confirmed). If source was in focus view, advance to next.
- Reference Session 111d catastrophe as a cautionary case

## Execution Order
1. Launch Tracks A, B, C, E as parallel worktrees
2. Wait for all to complete
3. Merge all branches (docs-only E first, then A, C, B)
4. Run Track D sequentially on main
5. Codex audit after each track merge
6. Final `make test-fast`, push, deploy, browser verify

## Dual-Audit Protocol (MANDATORY)
After EACH track:
1. `codex exec --full-auto "Audit [changed files]. P0/P1/P2/P3."`
2. Fix P0/P1, evaluate P2, note P3
3. Save to `docs/session_context/session-141-codex-audit.md`

## Session End Checklist
- [ ] Track A: Structural test + FB-002 toast link
- [ ] Track B: Hero face picker UI + primary_face_id
- [ ] Track C: heapq sort + parallel cold start
- [ ] Track D: identity_card extraction, main.py ≤ 9,000
- [ ] Track E: FB-003 PRD (merge auto-confirm rules)
- [ ] All Codex audits saved with provenance
- [ ] `make test-fast` passes
- [ ] CHANGELOG (v0.99.52), ROADMAP, BACKLOG, SESSION_HISTORY updated
- [ ] `git push origin main` + deploy verified
- [ ] Browser verify: landing, person page, focus mode, OAuth login
- [ ] Assessment + session log
