# Session 93 Prompt: Close All Deferrals

Source: User request in conversation (2026-03-08)
Predecessor: Session 92 (docs/assessments/session-92-assessment.md)

## Goal
Tackle ALL deferred items from Session 92. Session is not done until every item is handled.

## Deferred Items to Close

### 1. DATA-007: Postgres Migration for Core Tables
- Create identities + photos + photo_faces tables in Supabase
- Backfill all data from JSON files (894 identities, 295 photos, 981 faces)
- Verify DATA_SOURCE=postgres locally
- Flip DATA_SOURCE=postgres on Railway
- Verify app loads correctly from Postgres

### 2. Verify Sentry Dashboard
- Confirm SENTRY_DSN is set on Railway
- Verify error events are appearing in Sentry dashboard
- If no errors, trigger a test error and verify it appears

### 3. Verify PostHog Dashboard
- Confirm POSTHOG_API_KEY is set on Railway
- Verify events are appearing (face_compare_requested, photo_uploaded, help_identify_submitted, admin_identity_confirmed)
- Check client-side JS snippet is loading

### 4. Verify Resend Email Delivery
- Confirm RESEND_API_KEY is set on Railway
- Check Resend dashboard for delivery logs
- If no deliveries, trigger a test notification and verify

### 5. Leon's Batch Re-analyze
- Run batch GEDCOM re-analysis on all eligible photos
- Verify results are being stored correctly
- Cost cap the batch run

## Acceptance Criteria
- [ ] All 3 core tables exist in Supabase with correct data counts
- [ ] DATA_SOURCE=postgres works on Railway (health endpoint confirms)
- [ ] Sentry dashboard shows events
- [ ] PostHog dashboard shows events
- [ ] Resend shows email delivery
- [ ] Batch re-analyze completed or cost-capped
- [ ] All tests pass
- [ ] Assessment written with evidence
