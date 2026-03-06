# Session 89e Log
Started: 2026-03-05
Prompt: docs/prompts/session-89e-prompt.md

## Phase Checklist
- [x] Act 1: Orient + recover context
  - Read session 89e prompt/context, lessons, and todo
  - Confirmed `89e` in `.claude/current_session.txt`
  - Verified Benatar photo recovery required production-only investigation
  - Identified two hot paths causing repeated Supabase traffic: face alignments and GEDCOM loaders
- [x] Act 2: Performance fix (local code)
  - Added in-memory TTL caching for bulk `face_gemini_alignments` loads
  - Added write-through cache update on face-alignment save
  - Added GEDCOM retry/backoff and success/failure caching
  - Added configurable Supabase PostgREST timeout guard
- [ ] Act 3: Upload date backfill
- [ ] Act 4: Leon's Restaurant face analysis
- [ ] Act 5: Sort + production verification
- [ ] Act 6: Assessment + docs

## Working Notes
- Benatar recovery requires production-only verification via sync token / Supabase / Railway state.
- Face alignment slowdown comes from `load_alignments()` bulk-loading `face_gemini_alignments` on repeated photo requests.
- GEDCOM loaders cache successes but not failures, so transient Supabase errors are retried on every request.
- Photo-grid rendering was also paying a repeated face→identity lookup cost; a request-scoped lookup cache in `app/main.py` cut that repeated scan path.
- Cold `/?section=photos` E2E failures were reduced by prewarming the photo-grid caches during startup.

## Production Evidence

### Benatar Repair Attempt
- Photo page: `/photo/inbox_0c57277a_0_unknown`
- Repair endpoint called with sync token on 2026-03-05 for job `0c57277a`
- Production response:
  - `Found uploads dir: /app/storage/data/uploads/0c57277a`
  - `Copied unknown.jpg to raw_photos/`
  - `R2 upload completed`
  - `Caches invalidated`
- Follow-up verification still showed public R2 `404`s for:
  - `raw_photos/unknown.jpg`
  - `crops/inbox_a4c3a5701b51.jpg`
- Root cause found locally in `_upload_new_files_to_r2()`: it checked the wrong uploads path (`data_dir.parent / "uploads" / job_id`) instead of the real Railway volume path (`data_dir / "uploads" / job_id`).
- Local fix now checks both legacy and real upload/staging paths and can fall back to the canonical `raw_photos/...` entry if the job directory is gone.

### Data-Safety Cleanup Performed
- Synced production data down locally first, with timestamped backups:
  - `data/identities.bak.1772742039`
  - `data/photo_index.bak.1772742039`
  - `data/annotations.bak.1772742039`
- Integrity checker drift fixed: `REJECTED` is a valid identity state and should not fail integrity checks.
- Real contamination found from Session 65c test residue:
  - duplicate photo record `inbox_beae1035_0_albert_angel_499725590_10171877447865346_8151957301761971413_n`
  - metadata: `source='Test Session 65c'`, `collection='Test Upload'`
- Wrote `scripts/cleanup_isolated_photo.py` for reviewable, backup-first cleanup of isolated photo records.
- Dry-run safety checks for the `beae1035` record confirmed:
  - no identity references
  - no identity-history references
  - no annotation references
  - no local crop file for the orphan face
  - same raw asset retained by `inbox_community-batch-20260214_104_albert_angel_499725590_10171877447865346_8151957301761971413_n`
- Execute-mode cleanup backup created at:
  - `data/cleanup_backups/isolated_photo_inbox_beae1035_0_albert_angel_499725590_10171877447865346_8151957301761971413_n_20260305_205106`
- Orphan face soft-tracked in ignored local file:
  - `data/orphaned_face_ids.json` now includes `inbox_2b4b9d142998`

### Test Stabilization After Production Sync
- Fixed empty neighbors-sidebar state so browse expansion panels retain a close button even when an identity has no neighbors.
- Updated stale browse-card share test to match the current contract: identity cards share `/person/{identity_id}`, not `/photo/{photo_id}`.
- Hardened `_get_best_match_pair()` to skip stale proposal IDs instead of raising `KeyError`.
- Updated brittle photo-viewer person-link tests to assert the real contract (person links are present for identified people) rather than binding to one exact fixture identity selected through a different cache path.
- Stabilized several late full-suite route tests by moving state-sensitive HTML assertions onto isolated subprocess renders (`test_public_person_page.py`, `test_public_photo_viewer.py`, `test_search.py`, `test_session_82e_features.py`, `test_skipped_focus.py`).

## Verification Notes

- `rhodesli_ml/tests/` passed locally: `551 passed`.
- App suite repeatedly reduced to a single late failure in `tests/test_skipped_focus.py`; the stabilization work focused on making the assertions match the route's active-focus vs empty-state contract rather than assuming one specific data state.

## Process Lessons To Capture

- What worked:
  - Root-cause-first debugging on the Benatar incident found a concrete path bug quickly once production evidence was available.
  - Performance work targeted real hot paths instead of speculative optimization.
  - Dry-run and backup-first scripts kept local data work reviewable.
- What did not work:
  - Integration-test tail stabilization consumed too much session time.
  - Commit-after-act discipline was missed.
  - The skipped-focus regression pattern should have been generalized earlier, not fixed one assertion at a time.

## Handoff State

- `rhodesli_ml/tests/` is green locally: `551 passed`.
- `tests/` has been repeatedly reduced to one late `tests/test_skipped_focus.py` tail; the latest full pass in flight at wrap-up time is the final app-suite confirmation.
- No commit or push has been made yet.
- Assessment artifact exists: `docs/assessments/session-89e-assessment.md`
- Session summary exists: `docs/sessions/SESSION_089e.md`

## Next Actions For Claude Review

1. Check the result of the in-flight `pytest tests/ -x -q` run and, if needed, finish the last skipped-focus stabilization.
2. Commit the verified local work in bounded conventional commits.
3. Review the Benatar recovery notes, then do the production-safe code-only deploy and rerun the authenticated repair.
4. Verify Leon's Restaurant face analysis, live sort behavior, and live performance.
