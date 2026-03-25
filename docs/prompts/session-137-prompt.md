# Session 137: Overnight Parallel Work — Refactor + Tests + Design

## Context
Supabase is down (egress exceeded). All work in this session is Supabase-independent.
Session runs overnight with 4 parallel worktree agents. DO NOT STOP UNTIL DONE.

## Session Setup
```bash
echo "137" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
echo "1" > .claude/parallel_session_active  # Block main commits
source venv/bin/activate
make test-fast  # Baseline
```

## Track 1: main.py Refactor Phase 1 (BIGGEST TASK — DO NOT QUIT EARLY)
**Branch:** `session-137/refactor-main-components`
**Worktree isolation required.**

Extract ~56 UI component functions (~5,500 lines) from `app/main.py` to `app/components/`.

### Modules to create (in order):

1. **`app/components/__init__.py`** — Re-exports for backward compatibility
2. **`app/components/cards.py`** — `identity_card()`, `identity_card_expanded()`, `neighbor_card()`, `_search_result_card()`, and related card components
3. **`app/components/badges.py`** — `_confidence_tier_badge()`, `_cross_community_badge()`, `_era_badge()`, `_state_badge()`, `_promotion_badge()`, `_progressive_refinement_badge()`, and all badge/tag components
4. **`app/components/nav.py`** — `sidebar()`, `_build_triage_bar()`, `_public_nav_links()`, `og_tags()`, `share_button()`, `neighbors_sidebar()`
5. **`app/components/photo.py`** — `_build_ai_analysis_section()`, `_build_face_alignment_section()`, `render_photos_section()`, `_photo_card()`, and photo rendering functions
6. **`app/components/forms.py`** — Form helpers, datalists, input components
7. **`app/components/modals.py`** — Modal dialog components
8. **`app/components/layouts.py`** — `_404_handler()`, page shell, CSS/JS head elements

### Pattern for each module:
1. Create the target file with necessary imports
2. Copy functions from main.py to new file
3. In main.py, replace function body with: `from app.components.X import function_name` (re-export)
4. Run `make test-fast` — fix any import issues
5. Commit: `refactor: extract [module] from main.py to app/components/`
6. Move to next module

### Critical rules:
- Keep re-exports in main.py so `_main_mod.function()` calls in route files still work
- Import `_main_mod` references within component files should use function parameters instead
- If a component function needs `load_registry()` or similar, pass it as a parameter or import from main
- DO NOT refactor route files to import from components — that's Phase 2. Just re-export.
- Run tests after EVERY module extraction. Fix breakage before proceeding.

### Success criteria:
- `wc -l app/main.py` ≤ 6,500 lines
- `make test-fast` passes (3746+ tests)
- `ls app/components/*.py | wc -l` = 8 files
- No circular imports: `python -c "import app.components"`

## Track 2: Fix Flaky xdist Tests
**Branch:** `session-137/fix-flaky-tests`
**Worktree isolation required.**

### Root cause
`reset_registry_cache()` in `tests/conftest.py` only resets 3 caches. Tests depend on
10+ module-level caches in main.py. Parallel xdist workers share process state.

### Fix
1. In `tests/conftest.py`, expand `reset_registry_cache()` to also reset:
   ```python
   import app.main as _m
   _m._raw_embeddings_cache = None
   _m._face_data_cache = None
   _m._photo_registry_cache = None
   _m._photo_cache = {}
   _m._face_to_photo_cache = {}
   _m._crop_files_cache = None
   _m._discovery_cache = {}
   _m._skipped_neighbor_cache = {}
   _m._proposals_cache = None
   _m._proposals_cache_ts = 0.0
   ```
2. In `test_discoveries.py`: change `scope="class"` fixtures to `scope="function"`
3. In `test_skipped_focus.py`: update `_render_path()` to reset all caches
4. Run `make test-fast` 3 times to verify no flaky failures
5. Run `pytest tests/ -x -q -p no:xdist` to verify sequential mode also passes

### Success criteria:
- 3 consecutive `make test-fast` runs with 0 failures
- Sequential run also passes

## Track 3: ML Test Coverage Gaps
**Branch:** `session-137/ml-test-gaps`
**Worktree isolation required.**

### Create test files for untested modules:

1. **`rhodesli_ml/tests/test_multi_pass.py`**
   - Read `rhodesli_ml/multi_pass.py` (128 lines)
   - Test multi-pass refinement workflow
   - Test edge cases (empty input, API failure, single pass vs multi)
   - Mock Gemini API calls

2. **`rhodesli_ml/tests/test_nl_query.py`**
   - Read `rhodesli_ml/nl_query.py` (259 lines)
   - Test rule-based parser (name queries, date ranges, location filters)
   - Test SQL generation
   - Test edge cases (empty query, special characters, injection attempts)

3. **`rhodesli_ml/tests/test_prompt_manifest.py`**
   - Read `rhodesli_ml/prompt_manifest.py` (105 lines)
   - Test prompt registration, version tracking, lineage

### Success criteria:
- `pytest rhodesli_ml/tests/ -x -q` passes (590+ tests including new)
- Each new test file has ≥ 5 test cases

## Track 4: TOOLS-005 Design Work (lowest priority)
**Branch:** `session-137/tools-005-design`
**Worktree isolation required.**

1. Read `docs/prds/055_estimate_v2.md` and `app/estimate_routes.py`
2. Write test skeletons (marked `@pytest.mark.xfail`):
   - `tests/test_estimate_v2_text_hints.py`
   - `tests/test_estimate_v2_gedcom_paste.py`
   - `tests/test_estimate_v2_geography_retry.py`
3. Update PRD with implementation anchors found in codebase

## Merge Order (after all tracks complete)
1. Track 3 (ML tests — independent, no conflicts)
2. Track 4 (TOOLS-005 — independent, new files only)
3. Track 2 (Flaky tests — touches conftest.py)
4. Track 1 (Refactor — touches main.py, largest diff)

Use `./scripts/merge.sh` for each merge. Run `make test-fast` after each.

## Session End Checklist
- [ ] All 4 tracks merged to main
- [ ] `make test-fast` passes on final merged state
- [ ] `pytest rhodesli_ml/tests/ -x -q` passes
- [ ] `wc -l app/main.py` shows reduction
- [ ] Assessment written
- [ ] CHANGELOG updated
- [ ] ROADMAP updated
- [ ] Commit + push
