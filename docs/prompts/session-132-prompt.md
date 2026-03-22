# Session 132 — Data Integrity Hardening

## Predecessor
Session 131 (v0.99.41). See `docs/session_logs/session-131-log.md` and `docs/assessments/session-131-assessment.md`.

## What Happened in Session 131
- **P0 Crisis**: 175 faces orphaned across 18 identities from merge operations. Esther Burd Fox lost 8 faces from a tagged photo. This was declared "fixed" in Sessions 129/130 without actually verifying the specific photo page. Three sessions passed with the bug still present.
- **Immediate fix deployed**: Post-merge verification in `merge_identities()`, 8 structural tests, data repair of 112 faces across 18 identities. Browser-verified on production.
- **Deep investigation revealed 7 additional vulnerabilities** in the merge/cache/write pipeline (documented in session log).
- **Lesson 154**: 10th data integrity occurrence. NEVER declare a data fix done without browser-verifying the SPECIFIC affected page.

## Session 132 Objectives
Fix ALL identified merge pipeline vulnerabilities. Run comprehensive data integrity audit. Browser-verify specific affected pages. Have Codex audit every phase.

## Phase 0: Session Init (~5 min)
```bash
echo "132" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```
Create `docs/session_logs/session-132-log.md`. Clean stale worktrees (`git worktree list`, remove any `.claude/worktrees/agent-*`). Prune old branches.

## Phase 1: Deep Data Integrity Audit (~20 min)

Three parallel audit tracks:

### Track A: Transitive Merge Chain Audit
Query ALL identities with `merged_into` set. Follow chains to any depth (A->B->C->D). Report and repair:
- Chains >1 hop (which break face lookup via `get_identity_for_face`)
- Circular chains (infinite loop risk)
- Flatten: make all point to final non-merged target

### Track B: Face-Identity Coverage Audit
For every CONFIRMED identity:
- Verify all `anchor_ids` exist in `photo_faces` table
- Verify all `anchor_ids` map to a valid photo
For every face in `photo_faces`:
- Verify it maps to exactly one non-merged identity
Report orphaned faces (no identity) and ghost faces (identity refs non-existent face).

### Track C: Browser Verification of 18 Repaired Identities
Navigate to person page for each of the 18 identities repaired in Session 131. Verify face counts. For Esther Burd Fox, verify Dayton Ohio photo (`/c/fox-family/photo/10a7d40eb3bf94f7`) shows her tagged. Screenshot evidence.

**The 18 repaired identities (from Session 131 continuation):**
- Esther Burd Fox (65207728) — 120 anchors
- Unidentified Person 3048, 2814, 2923, 3467, 2586, 3050, 3028, 2795, 3557, 3178, 3443
- Netanel Menashe, Selma Capeluto
- Unidentified Person 2820, 3819, 3466, 4063, 3779

**Codex audit**: Run on audit script and findings.

## Phase 2: Batch Shadow Write Race Condition Fix (~30 min, CRITICAL)

**Problem**: `shadow_write_identities_batch()` at `app/supabase_data.py:838` uses raw `upsert()` with no version check. Concurrent writes with stale data can overwrite merge results.

**Fix**: Add optimistic concurrency control:
1. Before upsert, fetch current `version_id` for each identity in the batch from Supabase
2. Skip any row where Supabase `version_id >= incoming version_id`
3. Log warning when stale write is skipped
4. Test: simulate race condition, verify merge wins

**Key file**: `app/supabase_data.py` line 767-846

**Codex audit**: Run on the race condition fix.

## Phase 3: Merge Safety Improvements (~25 min, parallelizable via worktrees)

### 3A: Cache Invalidation After Merge
In `save_registry()` (`app/main.py:1584`), add community cache invalidation. Currently `_community_identity_ids_cache` is not cleared when identities change via merge.

### 3B: Merged Identity Redirect
When `/person/<id>` receives a merged identity (has `merged_into` set), 301 redirect to the merged-into target. Check `app/person_routes.py` for the handler. Add test.

### 3C: Startup Merge Orphan Check
Add to `_startup_parity_check()` in `app/main.py:1039`: detect faces in merged identities not in their target. Auto-repair like existing orphan face check. Log results.

**Codex audit**: Run on all three fixes.

## Phase 4: Fix Test Failures (~15 min)
- Fix `test_cross_batch` if failing
- Fix flaky `test_upload_result_has_share_cta` (ordering issue)
- Run full suite, ensure 0 failures (excluding e2e)
- Run ML tests

## Phase 5: UX Quick Wins (~30 min, parallelizable via worktrees)
From Session 131 backlog analysis:
- People grid photo count performance fix
- UX-089: Hide "Unknown" fields on person pages
- UX-073: Enter key submit on name forms
- FB-005: Face cards clickable to person page

## Phase 6: Full Codex Audit (~10 min, background)
Comprehensive audit of ALL code changes from Sessions 131-132:
- Post-merge verification, batch write race fix, cache invalidation, merge redirect, startup check
- Test coverage gaps
- Any remaining data integrity vulnerabilities

## Phase 7: Deploy + Verify + Close (~15 min)
1. Run full test suite
2. `git push origin main`
3. Verify deploy health
4. Browser verify: Landing, People, Photos, Compare, Estimate, Person page, **Esther Burd photo specifically**
5. Complete: assessment, changelog (v0.99.42), roadmap, session_history
6. `git log origin/main..HEAD` must be empty
7. Run /session-review skill

## Critical Constraints
- **NEVER declare a data fix done without browser-verifying the SPECIFIC affected page**
- Follow harness: commit after every sub-task, /clear between phases
- Parallelize independent tracks with worktree subagents
- Browser automation is READ-ONLY on production
- Every change gets tests
- Codex audit after each major phase
- This is the 10th data integrity occurrence. There MUST NOT be an 11th.

## Key Files
- `core/registry.py` — merge_identities() with post-merge verification (line 496)
- `app/main.py` — save_registry (1584), _build_caches (4474), _startup_parity_check (1039)
- `app/supabase_data.py` — shadow_write_identities_batch (767) — CRITICAL race condition
- `tests/test_merge_face_transfer.py` — 8 structural tests
- `tests/test_merge_orphan_audit.py` — production Supabase audit
- `scripts/data_integrity_audit.py` — comprehensive audit script
- `docs/session_context/session-131-merge-failure-investigation.md` — investigation report
- `docs/session_context/session-131-codex-audit.md` — Codex findings
- `.claude/plans/abstract-plotting-sedgewick.md` — detailed implementation plan

## Reference Documents
- Lesson 154: `tasks/lessons/data-lessons.md`
- Previous data integrity lessons: 56, 69, 78, 85, 141, 144, 147, 150, 153
- Session 131 assessment: `docs/assessments/session-131-assessment.md`
