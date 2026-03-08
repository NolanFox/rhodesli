# Session 92 Act 2 — Full Gap Closure Workplan

## CRITICAL STATE
- Branch: main
- Last commit: f66edff — fix(gemini): unwrap array response
- Deploy: BUILDING on Railway
- Tests: 2515 pass (app), ML not yet run

## BUG FIX IN PROGRESS
- **Asheville photo** (3192877a90a174e9): Gemini returns JSON array `[{...}]` instead of `{...}`.
  Code called `.get()` on list → `'list' has no attribute 'get'` → silent failure.
  Fixed: unwrap array before accessing dict keys. Also has display name fix + cache invalidation fix.
  **STATUS**: Fix pushed, deploy building. Need to re-trigger reanalyze after deploy.

## FULL GAP LIST (ALL MUST BE CLOSED)

### Priority 1: Asheville Verification
- [ ] Wait for deploy (commit f66edff)
- [ ] Navigate to /photo/3192877a90a174e9
- [ ] Click "Re-analyze Photo"
- [ ] Verify "Asheville, North Carolina" shows as headline
- [ ] If still failing, check Railway logs for error

### Priority 2: Create Supabase Tables for Full Migration
Need to create 9+ tables via direct Postgres connection (REST API can't create tables):
- date_labels, photo_locations, person_comments, discovery_log
- audit_log, pending_uploads, comparison_results, birth_year_estimates, corrections_log
- PLUS: sentry_events, posthog_events, contributor_suggestions, upload_tracking
- **Method**: Use psycopg2 with DATABASE_URL from Railway env vars
- SQL is ready in scripts/migrate_all_to_supabase.py

### Priority 3: Run Full Data Migration
- [ ] Run scripts/migrate_all_to_supabase.py after tables exist
- [ ] Verify row counts match source data

### Priority 4: DATA_SOURCE=postgres Implementation
- [ ] Full implementation — not just tables, but read paths
- [ ] All load_* functions need postgres fallback
- [ ] Test with DATA_SOURCE=postgres locally
- [ ] Set on Railway and verify

### Priority 5: Email Notifications (OPS-001 + PRD-028)
- [ ] Wire Resend with RESEND_API_KEY (already set on Railway)
- [ ] Custom SMTP sender for branded emails
- [ ] Notification triggers → actual email delivery
- [ ] Confirm→notification E2E test

### Priority 6: Additional Supabase Tables
- [ ] sentry_events — error tracking storage
- [ ] posthog_events — analytics event storage
- [ ] contributor_suggestions — user-submitted identifications
- [ ] upload_tracking — photo upload metadata
- [ ] railway_logs — log archival (7-day retention concern)

### Priority 7: Code Quality
- [ ] main.py <5K target (currently 9.4K)
- [ ] Fix e2e test_admin_review_queue_sorted
- [ ] Test speed optimization

### Priority 8: Remaining Features
- [ ] Leon's face alignment
- [ ] Timeline integration for life_events
- [ ] Rename re-analyze buttons for clarity
  - "Re-analyze Photo" → "Re-estimate Date & Location" (Gemini visual analysis)
  - "Re-run Analysis" → "Re-describe Faces" (face coordinate bridging)

## SUPABASE CONNECTION INFO
- Project: fvynibivlphxwfowzkjl
- Need DATABASE_URL for direct Postgres (psycopg2)
- Can get from Railway env vars or Supabase dashboard

## KEY FILES
- app/estimate_routes.py — Gemini reanalyze (fixed array unwrap)
- scripts/migrate_all_to_supabase.py — Migration script (588 lines)
- app/supabase_data.py — Supabase sync functions
- app/page_routes.py — Photo locations cache
