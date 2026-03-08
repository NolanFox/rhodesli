# Session 93-hotfix Assessment

## Shipped
- [x] Fix: Merged 69 orphaned root-level reanalyzed entries into `photos` section of `data/photo_locations.json` — Evidence: JSON now has 268 entries under `photos`, 0 root-level orphans
- [x] Fix: `sync_photo_location()` and `sync_photo_locations_batch()` column names corrected (`latitude`→`lat`, `longitude`→`lng`, `place`→`location_name`) + `on_conflict="photo_id"` — Evidence: 69 entries synced to Supabase, 0 mismatches verified
- [x] Fix: Test updated to match new column names — Evidence: 3717 tests pass, 566 ML tests pass
- [x] Documentation: AD-212, Lessons 104-105, CHANGELOG v0.96.1

## Root Cause
Session 93's batch GEDCOM reanalysis script wrote results to the root level of `photo_locations.json` instead of inside the `"photos"` key. The migration to Supabase and the app's `_load_photo_locations()` both read only from `data.get("photos", {})`, so the 69 reanalyzed entries were invisible to all consumers.

## Why Session 93's Assessment Didn't Catch This
This is a **harness failure**. Session 93's self-assessment rated the batch reanalysis as PASS, but:
1. No production browser verification of the reanalyzed locations was performed
2. The session verified the JSON file "had data" but didn't verify the data was readable by the app
3. The Feature Reality Contract (FRC) check was superficial — "data exists" ≠ "data is in the right place"
4. The Supabase sync function had wrong column names since it was first written — the mock-only tests couldn't catch this because mocks don't validate column names

## Systemic Issues Exposed
1. **No structural validation for JSON data files** — There's no test that `photo_locations.json` has only `version`, `description`, `photos` at root level. Orphaned keys are invisible.
2. **Mock-only tests for DB sync are insufficient** — Column name mismatches (`latitude` vs `lat`) pass all mock tests but fail on real Supabase. Need at least one integration test or schema comment.
3. **Batch scripts lack read-back verification** — The batch script should have loaded the file back using `_load_photo_locations()` and verified the affected entries were visible.
4. **Session 93 self-assessment violated Lesson 97** — "PASS without visual verification is theater." The reanalyzed locations were never checked in a browser.

## Red Flags
- [HIGH] `data/annotations.json` had uncommitted production user data locally — restored via `git checkout`. This file keeps showing up as dirty. Need to investigate why it keeps getting modified locally.
- [MEDIUM] The `sync_photo_locations_batch` function had wrong column names since it was written — never caught because the migration used a different code path (`migrate_complete.py` used direct SQL, not the sync function).
- [MEDIUM] Session 93's self-assessment did not catch this regression despite FRC being a mandatory check.

## Prevention (Lessons 104-105)
1. Batch scripts must write to the EXACT key path consumers read from
2. After batch writes, read back with the SAME function the app uses
3. Supabase sync functions need schema validation (not just mock tests)
4. Add structural validation test for all JSON data files

## Next Session Should Verify
1. After deploy: confirm https://rhodesli.nolanandrewfox.com/photo/746dd11e5b4d86a1 shows Asheville
2. Check a few other reanalyzed photos show correct locations
3. Investigate `data/annotations.json` appearing dirty — what's modifying it locally?
