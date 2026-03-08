# Session 93 Log
Started: 2026-03-08
Prompt: Close all Session 92 deferrals

## Phase Checklist
- [x] Phase 1: DATA-007 — Create core tables in Supabase
- [x] Phase 2: DATA-007 — Backfill identities + photos + photo_faces
- [x] Phase 3: DATA-007 — Verify DATA_SOURCE=postgres locally
- [x] Phase 4: DATA-007 — Flip on Railway
- [x] Phase 5: Verify Sentry dashboard
- [x] Phase 6: Verify PostHog dashboard
- [x] Phase 7: Verify Resend email delivery
- [x] Phase 8: Leon's batch re-analyze all photos
- [x] Phase 9: Supplementary data migration (date_labels, photo_locations, birth_year_estimates)
- [x] Phase 10: GEDCOM reanalysis results analysis

## Progress

### Act 1: DATA-007 — Core Tables Migration
- Migration script written: scripts/migrate_core_tables.py
- Direct psycopg2 connection blocked (DNS from local) — used Supabase SQL Editor via Chrome
- Tables created: identities, photos, photo_faces (3 tables + 4 indexes)
- Data backfilled via Supabase REST API: 894 identities, 295 photos, 981 faces
- Null name fix: identity 224495e8 (CONTESTED state) had name=null, defaulted to "Unknown (224495e8)"
- CHECK constraint broadened to include CONTESTED and REJECTED states
- DATA_SOURCE=postgres flipped on Railway
- Deploy logs confirmed: "IdentityRegistry loaded from Postgres (894 identities)"

### Act 2: Supplementary Data Migration
- date_labels, photo_locations, birth_year_estimates tables had `full_data` JSONB column
- Load functions expected `data` column — column name mismatch from Session 92's migrate_complete.py
- Fixed via SQL ALTER TABLE + UPDATE in Supabase SQL Editor
- Verified: 271 date_labels, 268 photo_locations, 32 birth_year_estimates loaded correctly

### Act 3: Observability Verification
- **Sentry**: 5 real issues in dashboard. NameError `photo_url` (4 events) — verified import is present, likely from pre-deploy. APIError invalid UUID "confirmed-1" (3 events) — bad external requests.
- **PostHog**: Page view events flowing. 4 server-side events configured.
- **Resend**: 1 email delivered successfully. RESEND_API_KEY confirmed set.

### Act 4: Batch GEDCOM Re-analyze
- Dry run: 72 GEDCOM-eligible photos, 51 GEDCOM identity links, $2.66 estimated cost
- Batch executed: `python scripts/reprocess_with_gedcom.py --batch --max-cost 3.00`
- Runtime: ~79 minutes (12:36 PM to ~1:55 PM)
- Results: 67/72 photos reanalyzed successfully, 5 failed (content safety/image loading)
- Model: gemini-3.1-pro-preview
- Updated: data/date_labels.json (67 entries with reanalyzed_at), data/photo_locations.json
- Analysis report: docs/ml/GEDCOM_REANALYSIS_REPORT.md

### Act 5: Tests
- App tests: 3717 passed, 4 skipped (281s)
- ML tests: 566 passed (42s)
- 1 e2e test failure (pre-existing, chromium discovery layer sort)
