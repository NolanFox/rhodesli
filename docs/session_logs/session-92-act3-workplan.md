# Session 92 Act 3 — Complete Gap Closure (Continuation)

## CRITICAL STATE
- Branch: main
- Previous context ran out — this is a continuation
- Railway Hobby Plan active (7-day log retention)
- Supabase tables: ALL 15+ created successfully (40 total tables)
- Migration: psycopg2 script exists at scripts/migrate_data_psycopg2.py (untracked, 685 lines)

## ROOT CAUSE: ASHEVILLE LOCATION BUG
**Photo**: 3192877a90a174e9 (Leon's Restaurant)
**Problem**: Page shows old vague Gemini text instead of "Asheville, North Carolina"
**Root cause**: photo_locations.json entry stored under INBOX ID (`inbox_staged-20260210-182610_5_757557421.130308`)
but page looks up by SHA256 ID (`3192877a90a174e9`). The dual-key fallback in `_load_photo_locations()`
(page_routes.py:6522-6535) should map inbox→SHA256 via PhotoRegistry, but may be failing silently
due to the broad `except Exception: pass` at line 6534.

**Fix approach**:
1. Make _load_photo_locations() more robust — log errors instead of swallowing
2. Verify the dual-key mapping works for this specific photo
3. Also: improve the GEDCOM context sent to Gemini for this photo
4. Deploy and verify on production

## FULL GAP LIST — ALL MUST BE CLOSED

### 1. Asheville Location Fix (HIGHEST PRIORITY)
- [ ] Fix photo_locations.json dual-key mapping
- [ ] Improve GEDCOM context for Victor/Victoria/Leon (user wants full family info)
- [ ] Test locally
- [ ] Deploy to Railway
- [ ] Browser verify on production

### 2. Full Data Migration to Supabase
- [ ] Review scripts/migrate_data_psycopg2.py (background agent output)
- [ ] Run migration with --dry-run first
- [ ] Run real migration
- [ ] Verify row counts match source data
- [ ] All tables populated: date_labels, photo_locations, person_comments, discovery_log, audit_log, pending_uploads, comparison_results, birth_year_estimates, corrections_log

### 3. DATA_SOURCE=postgres Implementation
- [ ] All load_* functions need postgres read path
- [ ] Test with DATA_SOURCE=postgres locally
- [ ] Set on Railway and verify
- [ ] Fallback to JSON if Postgres unavailable

### 4. Email Notifications (OPS-001 + PRD-028)
- [ ] Wire Resend with RESEND_API_KEY
- [ ] Custom SMTP sender for branded emails
- [ ] Notification triggers → actual email delivery
- [ ] Confirm→notification E2E test

### 5. Railway Log Archival
- [ ] Railway Hobby plan has 7-day log retention
- [ ] Design log archival to Supabase (railway_logs table already exists)
- [ ] Implement log forwarding or periodic sync

### 6. SENTRY_DSN + POSTHOG_API_KEY
- [ ] Set environment variables on Railway
- [ ] Verify Sentry captures errors
- [ ] Verify PostHog tracks events

### 7. Code Quality
- [ ] Fix e2e test_admin_review_queue_sorted
- [ ] Test speed optimization (43s → <30s target)

### 8. Two Buttons Investigation (ANSWERED)
- "Re-analyze Photo" = Gemini date/location/scene analysis (estimate_routes.py:1137)
- "Re-run Analysis" = face coordinate bridging for descriptions (photo_routes.py:312)
- Different purposes, both needed. Consider renaming for clarity.

### 9. Gemini Prompting Strategy
- User wants ALL GEDCOM info for Victor, Victoria, and direct relations
- "Gemini should see Victor is with the wife of his brother Leon around 1938 or 1940
  in front of a restaurant called Leon's when Leon and Victoria lived in Asheville
  and Victor came to the US via SF twice"
- Need to verify GEDCOM context builder includes full family info

## KEY FILES
- app/estimate_routes.py — Gemini reanalyze + location write
- app/page_routes.py:6505 — _load_photo_locations() with dual-key
- app/main.py:1860 — Location headline display
- scripts/migrate_data_psycopg2.py — New psycopg2 migration (untracked)
- scripts/create_supabase_tables.py — Table creation (done)
- rhodesli_ml/gedcom_context.py — GEDCOM context builder

## SUPABASE CONNECTION
- Project: fvynibivlphxwfowzkjl
- Password has @ symbol — use individual params, NOT DATABASE_URL
- Tables: 40 total (15 new from this session)
