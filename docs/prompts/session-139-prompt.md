# Session 139: Mega Fix Sprint — Triage UX + Data + Performance + Refactor

## Context
Session 138 generated 13 feedback items. User is away — work autonomously until done.
See `docs/session_context/session-139-context.md` for full research from 5 parallel agents.
**Codex CLI audit is MANDATORY after each track** (HD-030).

## Phase 0: Setup
```bash
echo "139" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```

## Track A: Missing Crops Data Fix (worktree — independent)
**Goal**: Identify and fix faces with missing crop files on R2.

1. Write `scripts/audit_missing_crops.py`:
   - Load embeddings.npy — every entry has face_id + bbox
   - For each face_id, check if crop exists on R2 (HEAD request to R2_PUBLIC_URL/crops/{face_id}.jpg)
   - Report: total faces, faces with crops, faces missing crops, breakdown by collection
2. Write `scripts/regenerate_missing_crops.py`:
   - For each missing crop: read source photo from R2, extract face using bbox from embeddings, save crop
   - Upload generated crops to R2 via boto3
   - Update photo_faces in Supabase if needed
   - Dry-run mode first, then execute
3. Run audit, present findings, then regenerate
4. Tests for both scripts

## Track B: Focus Mode UX Fixes (worktree — independent of Track A)
**Goal**: Fix merge advance, bulk merge, and "Edit in Admin" deep link.

### B1: Verify/fix merge auto-advance in focus mode
- The merge endpoint already has from_focus support (lines 2338-2361 in identity_routes.py)
- Test by writing an integration test that POSTs a merge with from_focus=true and verifies the response contains a new focus card
- If the response is correct, the issue may be HTMX client-side — check hx_target on the merge button

### B2: Add from_focus support to bulk-merge endpoint
- Current `/api/identity/{id}/bulk-merge` returns only a toast
- Add `from_focus: bool = False` parameter
- When from_focus=true: return `get_next_focus_card()` + OOB toast (same pattern as single merge)
- Update bulk merge button in neighbor_card to pass from_focus parameter

### B3: Fix "Edit in Admin" deep link (FB-014)
- Problem: `#identity-{id}` anchor fails when card isn't in the first 150 loaded
- Solution: Change "Edit in Admin" to link to focus mode for that specific identity:
  `/{prefix}/?section={section}&view=focus&current={identity_id}`
- This loads the identity directly in focus mode — no need for it to be in the DOM
- Also add a fallback: if the identity IS in the DOM, scroll to it; if not, navigate to focus

### B4: Write tests for all fixes

## Track C: Triage Workflow — PRD + Quick Implementation
**Goal**: Separate "confirm" from "identify", add filters.

### C1: Write PRD `docs/prds/057_triage_workflow_redesign.md`
- Confirm = "this cluster is a real person" (can be unnamed)
- Identify = "this person is [name]" (naming action)
- Google/Apple Photos precedent: unnamed clusters are valid
- New filters on People page: "All" / "Named" / "Needs Name"
- No schema change needed — derive is_named from name field

### C2: Implement People page filter
- Add a filter dropdown/tabs above the people grid: "All Confirmed" / "Named" / "Needs Identification"
- Filter logic: `_is_real_name(identity.get("name"))` for named vs unnamed
- The People page sidebar count should show both (e.g., "41 People (28 named)")

### C3: Add direct-load endpoint for focus mode
- New route: `/?section={section}&view=focus&current={identity_id}`
- If `current` parameter is provided, load THAT specific identity in focus mode instead of the first in the queue
- This makes "Edit in Admin" work for any identity regardless of pagination

## Track D: Refactor Phase 2 Completion (sequential — touches main.py)
**Goal**: Extract identity_card + identity_card_expanded → main.py ≤ 9,000 lines.

### D1: Extract shared utility functions to a new `app/utils_identity.py` or to cards.py
- `_sequential_display_name` (~25 lines)
- `get_best_face_id` (~40 lines) — needs _photo_registry_cache via lazy import
- `resolve_face_image_url` (~50 lines)
- `get_photo_id_for_face` (~8 lines)
- `get_face_quality` (~15 lines)

### D2: Extract identity_card_expanded (~272 lines)
- Uses lazy import pattern for remaining main.py dependencies
- `_proposal_banner`, `_get_identities_with_proposals` accessed via `import app.main as _m`

### D3: Extract identity_card (~566 lines)
- Highest risk — 18+ dependencies, many through lazy imports
- Extract only if D1 and D2 succeed cleanly

### After each extraction: `make test-fast`, commit atomically

## Track E: Performance Quick Wins (can parallel with Track B/C)
**Goal**: 3 targeted performance fixes.

### E1: Dict lookup for _global_identity_info (2-line fix)
In `app/perf_cache.py`, replace O(N²) linear scan with dict:
```python
# In _rebuild_global_matrix():
_global_identity_info_by_id = {item[0]: item for item in _global_identity_info}

# In get_all_neighbors():
info = _global_identity_info_by_id.get(iid)  # was: for item in _global_identity_info: if item[0] == iid
```

### E2: Precompute best_face_id cache
Add `_best_face_cache: dict[str, str | None] = {}` — populated lazily in `get_best_face_id()`, invalidated in `save_registry()`.

### E3: Optimize sort key (skip quality scoring for browse mode)
In browse mode, sort by date or name instead of quality score. Quality scoring should only run for focus mode's top-10.

## Dual-Audit Protocol (MANDATORY)
After EACH track completion:
1. `codex exec --full-auto "Audit [changed files]. P0/P1/P2/P3."`
2. Review findings, fix P0/P1
3. Save to `docs/session_context/session-139-codex-audit.md`

## Session End Checklist
- [ ] Track A: Missing crops audited + fixed
- [ ] Track B: Merge advance, bulk merge, deep link all fixed
- [ ] Track C: PRD written, people filter implemented, direct-load works
- [ ] Track D: identity_card_expanded + identity_card extracted (or documented why deferred)
- [ ] Track E: 3 performance fixes shipped
- [ ] All Codex audits saved with provenance
- [ ] `make test-fast` passes
- [ ] Assessment + session log + CHANGELOG + ROADMAP + BACKLOG updated
- [ ] `git push origin main` + deploy verified
- [ ] Browser verify all affected pages
