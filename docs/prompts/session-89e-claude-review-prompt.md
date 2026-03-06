# Session 89e Claude Review + Closeout Prompt

Start from the current local state of Session 89e and treat this as a critical review, verification, and completion pass over GPT 5.4's work.

## Mission

1. Verify what was actually accomplished in Session 89e.
2. Critically evaluate the quality of the work, including where GPT 5.4 did well and where it struggled.
3. Check for any bugs, regressions, missing deliverables, or gaps between the original 89e prompt and what was actually completed.
4. Fix any remaining issues you find.
5. If local work is solid, deploy the appropriate code safely, then verify in Claude Chrome on the live site.

Do not be polite or generous in the review. Be technically exact.

## Read First

1. `docs/prompts/session-89e-prompt.md`
2. `docs/session_context/session-89e-context.md`
3. `docs/session_logs/session-89e-log.md`
4. `docs/assessments/session-89e-assessment.md`
5. `docs/sessions/SESSION_089e.md`
6. `tasks/lessons.md`
7. `tasks/todo.md`

Set `.claude/current_session.txt` to `89e` if needed.

## What GPT 5.4 Believes It Completed

### Local code changes

- `app/main.py`
  - Fixed the Benatar/R2 repair helper path so `_upload_new_files_to_r2()` checks the real Railway volume upload/staging directories.
  - Added GEDCOM retry/backoff and failure caching.
  - Added request-scoped face→identity lookup caching for photo-heavy pages.
  - Added startup cache prewarm for photo-grid related caches.
  - Expanded photo provenance display to support archive entry dates.
- `app/face_alignment.py`
  - Added in-memory TTL caching for bulk `face_gemini_alignments` loads.
  - Added write-through cache updates on alignment save.
- `app/supabase_data.py`
  - Added explicit PostgREST timeout configuration.
- `scripts/backfill_upload_dates.py`
  - New dry-run/backup-first script for archive-wide upload-date backfill.
- `scripts/cleanup_isolated_photo.py`
  - New dry-run/backup-first cleanup script for isolated duplicate/test photo residue.
- `scripts/check_data_integrity.py`
  - Updated for current identity-state reality.

### Tests added/updated

- Added:
  - `tests/test_backfill_upload_dates.py`
  - `tests/test_cleanup_isolated_photo.py`
  - `tests/test_identity_lookup_cache.py`
  - `tests/test_r2_upload_helper.py`
- Updated many app tests, especially stateful route-render tests:
  - `tests/test_public_person_page.py`
  - `tests/test_public_photo_viewer.py`
  - `tests/test_search.py`
  - `tests/test_session_82e_features.py`
  - `tests/test_skipped_focus.py`
  - several others listed in `git status`

### Data/documentation work

- Created/updated:
  - `docs/session_logs/session-89e-log.md`
  - `docs/assessments/session-89e-assessment.md`
  - `docs/sessions/SESSION_089e.md`
- Synced production-derived local data and performed one backup-first cleanup of known Session 65c residue. Review the session log carefully before trusting that.

## What GPT 5.4 Believes Is Still Outstanding

1. Final clean `pytest tests/ -x -q` pass was not yet achieved at handoff time.
2. No commits had been made until the user explicitly demanded one.
3. No deploy had been made from this session.
4. No live-site verification had yet been completed for:
   - Benatar repair after the local fix
   - Leon's Restaurant face analysis
   - live sort verification
   - live performance verification
5. Upload-date backfill script was written but not yet safely executed and verified end-to-end.

## Where GPT 5.4 Struggled

Be explicit in your assessment of these points:

1. It spent far too much time in late-suite test stabilization, especially `tests/test_skipped_focus.py`.
2. It failed commit-after-act discipline.
3. It was too slow to generalize the skipped-focus test instability pattern.
4. It did produce substantial real code and docs, but the closure discipline was weak.

## What To Verify Technically

### Local verification

1. Inspect the exact diffs and determine whether the Benatar path fix is correct.
2. Verify the performance fixes are coherent and not placebo.
3. Check whether the backfill script is safe and correct.
4. Run the necessary tests.
   - If app suite still has a tail failure, identify whether it is a real product bug or a brittle test.
   - Fix it properly.
5. Review all documentation artifacts for accuracy, not just existence.

### Production-safe verification

If local state is sound:

1. Make commits in bounded conventional format.
2. Deploy code safely without blindly pushing synced local data.
3. Use Claude Chrome to verify:
   - Benatar image recovery on the live photo page
   - Leon's Restaurant face analysis
   - `/photos` sort modes
   - site performance

## Comparison Task: GPT 5.4 vs Claude Code

I want an honest comparison, not a diplomatic one.

Assess:

1. What GPT 5.4 handled well in Session 89e.
2. What GPT 5.4 handled poorly.
3. Whether there were parts of this session Claude Code likely would have struggled with too.
4. Whether the main problem was model capability, execution discipline, or repo/test-suite characteristics.
5. Whether GPT 5.4 found/fixed anything materially useful that Claude had not already done.

## Required Outputs

1. A critical review of Session 89e.
2. A concrete list of remaining gaps, if any.
3. Fixes for those gaps if they exist.
4. Verification evidence from local tests and Claude Chrome.
5. A direct comparison between GPT 5.4 and Claude Code on this session.

Do not assume GPT 5.4's session log is correct. Audit it against the code, test results, and the live site.
