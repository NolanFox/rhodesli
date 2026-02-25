# GEDCOM Admin UI — Build Results

## What was built

### AD-164: GEDCOM Admin UI — Version Management via Web

Enhanced the existing `/admin/gedcom` page with Supabase-backed version management:

1. **Version Info Panel** — Shows current GEDCOM version number, individual/family counts, import date, and notes. Queries from `gedcom_versions` table via Supabase.

2. **Versioned Upload with Diff Preview** — Upload a .ged file, the system parses it and computes a diff against the current database (N added, N modified, N removed, N unchanged). Shows a diff summary with Apply/Cancel buttons. Follows the Gatekeeper pattern: no data changes until admin explicitly clicks "Apply".

3. **Version History Table** — Lists all past imports with version numbers, dates, source files, and change count badges (+added, ~modified, -removed, =unchanged).

4. **Re-Enrichment Queue Counter** — Shows count of pending photos needing re-processing from `gedcom_enrichment_queue` table. Displayed in the version info panel with amber/green color coding.

5. **Apply/Cancel Endpoints** — `/admin/gedcom/apply` commits the previewed import (runs both versioned Supabase import and legacy matching pipeline). `/admin/gedcom/cancel` discards the preview and cleans up the temp file.

## Files changed

| File | Change |
|------|--------|
| `app/main.py` | Enhanced `/admin/gedcom` route with version info, version history, enrichment queue. Added `/admin/gedcom/apply` and `/admin/gedcom/cancel` routes. Added `_load_gedcom_versions()` and `_load_gedcom_enrichment_queue_count()` helpers. |
| `docs/ml/ALGORITHMIC_DECISIONS.md` | Added AD-164 entry documenting the design rationale. |
| `tests/test_gedcom_admin.py` | New test file with 25 tests covering auth, page load, upload, apply/cancel, helper functions, and navigation. |
| `RESULTS.md` | This file. |

## Tests

- **25 new tests** in `tests/test_gedcom_admin.py`
  - 8 auth tests (anon, non-admin blocked from all routes)
  - 7 page load tests (version info, history, enrichment queue, upload form, nav bar)
  - 1 upload test (no-file error)
  - 2 apply/cancel tests (cancel clears preview, apply with no preview errors)
  - 6 helper function tests (Supabase success, failure, no-config cases)
  - 1 navigation test (GEDCOM link in admin nav)

- **All 78 GEDCOM-related tests pass** (25 new + 33 existing routes + 20 versioning)

## Navigation

GEDCOM was already wired into the admin navigation bar at `/admin/gedcom`. The link appears in:
- Admin sidebar nav (mobile + desktop)
- `_admin_nav_bar()` component shared across all admin pages

## Design decisions

- **Why enhance existing page**: The `/admin/gedcom` page already handled GEDCOM matching. Adding version management to the same page keeps related functionality together rather than fragmenting it.
- **Why diff-before-apply**: Follows the Gatekeeper pattern (AD-163). No data changes happen until the admin reviews the diff summary and explicitly clicks "Apply". This prevents accidental imports.
- **Why dual pipeline**: The apply step runs both the versioned Supabase import (for version tracking) AND the legacy matching pipeline (for identity matching). This maintains backward compatibility.
- **Graceful degradation**: If Supabase is not configured, the page still loads and shows the legacy matching UI. Version panels show "no versions" instead of errors.
