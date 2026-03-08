# Session 93 Context

Predecessor: [Session 92 Assessment](../assessments/session-92-assessment.md)

## Background
Session 92 shipped v0.95.0 with 4,283 tests passing. Several items were deferred:
- DATA-007: Core tables (identities, photos, photo_faces) didn't exist in Supabase
- Sentry/PostHog/Resend dashboard verification not done
- Leon's batch re-analyze not triggered

## Technical Context

### DATA-007 Architecture
- `DATA_SOURCE` env var controls json vs postgres mode (app/main.py:151)
- `IdentityRegistry.load_from_postgres()` already implemented (core/registry.py:1570)
- `PhotoRegistry.load_from_postgres()` already implemented (core/photo_registry.py:342)
- `save_registry()` and `save_photo_registry()` already have postgres write paths
- SQL schemas exist: scripts/sql/001_photos_table.sql, 002_identities_table.sql, 003_photo_faces_table.sql
- Tables do NOT exist in Supabase yet — that's the blocker
- Local psycopg2 can't resolve db.*.supabase.co — must use Supabase SQL Editor or REST API

### Observability Stack
- Sentry: initialized conditionally on SENTRY_DSN (app/main.py:101-117)
- PostHog: 4 server-side events + client-side JS (app/main.py:119-176)
- Resend: email via HTTP POST (app/notification_routes.py:94-122)
- All 3 env vars set on Railway per Session 92

### Batch Re-analyze
- Script: scripts/reprocess_with_gedcom.py
- Endpoint: /api/photo/{photo_id}/reanalyze (admin-only)
- GEDCOM context builder: rhodesli_ml/gedcom_context.py
- Leon's fix (AD-210) already verified in production

## Migration Script
Created: scripts/migrate_core_tables.py
- Uses psycopg2 for direct Postgres connection (needs DNS workaround)
- Alternative: use Supabase REST API via chrome SQL editor for DDL, then REST for data

## Risk Assessment
- **DATA-007**: Medium risk — need to verify read paths work correctly before flipping
- **Observability**: Low risk — just dashboard verification
- **Batch re-analyze**: Low risk — script exists, cost-capped

## Deferred to Future Sessions
- Schema additions for longitudinal tracking: `previous_date_estimate`, `gedcom_token_count` on `gemini_api_calls` — See AD-211, GEDCOM_REANALYSIS_REPORT.md Section 7
- Multi-GEDCOM architecture — See docs/session_context/session-93-user-feedback.md
- 5 failed photos investigation (content safety blocks) — See GEDCOM_REANALYSIS_REPORT.md Section 6
- Dockerfile missing `rhodesli_ml/recalibration_hooks.py` — pre-existing gap

## Post-Session Planning
- Next session should verify Railway DATA_SOURCE=postgres is still healthy
- Schema additions are the highest-priority follow-up (enables future longitudinal analysis)
- Multi-GEDCOM is the highest-ROI architectural investment per user feedback
