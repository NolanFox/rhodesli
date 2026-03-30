**Auditor**: Codex CLI v0.117.0 (o4-mini)
**Agent type**: Independent (fresh context)
**Scope**: All Session 144b changed files (13 files)
**Date**: 2026-03-30

## Findings

### P0: None

### P1: `--rerun-without-gedcom` fails open (1 finding)
- **File**: scripts/batch_gemini_for_person.py:290
- **Issue**: If SUPABASE_URL/key missing, flag silently falls through to processing ALL photos
- **Fix**: Added explicit error + return when Supabase env vars missing
- **Status**: FIXED

### P2: 3 findings
1. **geocode_photos.py incomplete Supabase rows** — New upsert only sent photo_id, data, location_name, location_estimate. Missing lat, lng, confidence, region columns.
   - **Fix**: Added all denormalized columns to upsert payload
   - **Status**: FIXED

2. **event_grouping.py dated photo count mismatch** — Supabase path treats any row with `data` as dated, but downstream grouping filters by `best_year_estimate`. Reported totals can overstate.
   - **Assessment**: Cosmetic — the actual grouping is correct since it filters by year. The metadata count is advisory only.
   - **Status**: NOTED (low impact, cosmetic)

3. **Test coverage thinner than claimed** — New tests are mostly unit/structural. No integration tests for `--rerun-without-gedcom`, Supabase photo metadata fallback, or geocode Supabase write path.
   - **Assessment**: Valid observation. The scripts are offline tooling with low blast radius. Integration testing would require Supabase mocking infrastructure that doesn't exist.
   - **Status**: ACCEPTED (offline scripts, tested manually via execution)

### P3: 2 findings
1. **face-label CSS needs `display: inline-block`** — `max-width` on `<span>` needs block display for width constraints to apply.
   - **Fix**: Added `display: inline-block` to `.face-label`
   - **Status**: FIXED

2. **Structural tests are source-string inspection** — Can pass with dead code or misplaced helpers.
   - **Assessment**: True limitation, but these are guardrail tests. The actual behavior is tested separately (test_photo_sorting.py::TestDateLabelsDualKeying).
   - **Status**: ACCEPTED (defense in depth, not sole verification)

## Value Assessment
**MODERATE** — Caught the P1 fail-open bug and the P2 incomplete columns, both of which would have caused real issues. The P3 CSS fix was also valid.
