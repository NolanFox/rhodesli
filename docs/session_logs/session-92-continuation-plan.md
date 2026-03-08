# Session 92 Continuation — Full Gap Closure Plan

## CRITICAL STATE (saved for context recovery)
- Branch: main
- Last commit: 01c29c9 — fix(estimate): cache invalidation bug + clean location display names
- Railway: Hobby plan active, deploys working
- Tests: 3680 pass (app), 566 pass (ML)

## IMMEDIATE: Push + Deploy + Verify Asheville (commit 01c29c9)
1. `git push origin main`
2. Wait for deploy to succeed
3. Navigate to /photo/3192877a90a174e9
4. Click "Re-analyze Photo" button
5. Verify "Asheville, North Carolina" shows as headline
6. If not: debug Gemini response in Railway logs

## GAP INVENTORY (from screenshots + session log)
| # | Gap | Status | Action |
|---|-----|--------|--------|
| G1 | Leon's → Asheville display | FIX COMMITTED | Push + re-analyze + verify |
| G2 | SENTRY_DSN + POSTHOG_API_KEY on Railway | NEEDS CHECK | Verify via Railway CLI |
| G3 | DATA_SOURCE=postgres | NOT DONE | Full implementation needed |
| G4 | OPS-001: Custom SMTP | CODE READY | Wire Resend with custom domain |
| G5 | Test speed <30s | PARTIAL | Currently ~260s, profile + optimize |
| G6 | Email notifications | NOT DONE | Wire Resend to notification triggers |
| G7 | Confirm→notification E2E | NOT VERIFIED | Browser verify after deploy |
| G8 | main.py <5K target | AT 9.4K | Extract UI components |
| G9 | e2e test_admin_review_queue_sorted | FAILING | Fix the test |
| G10 | Leon's face alignment | DEFERRED | Run alignment |
| G11 | Timeline integration for events | DEFERRED | Wire life_events to timeline |
| G12 | pgvector migration | FUTURE | Enable extension, migrate embeddings |
| G13 | Full Supabase migration | SCRIPT READY | Run migrate_all_to_supabase.py |
| G14 | Railway log archival to Supabase | NEW (user req) | 7-day retention → Supabase table |
| G15 | Two re-analyze buttons UX | INVESTIGATED | Different purposes, rename for clarity |
| G16 | Supabase tables for Sentry/PostHog/uploads/suggestions | NEW (user req) | Design + create |

## WORK ORDER (prioritized)
1. Push + deploy + verify Asheville (G1)
2. Set Railway env vars if missing (G2)
3. Run Supabase migration script (G13)
4. Full Supabase data migration — all JSON → Postgres (G3, G16)
5. Railway log archival design (G14)
6. Remaining gaps (G4-G12)

## TWO BUTTONS ANSWER (for user)
- "Re-analyze Photo" = date + location + scene estimation (Gemini visual analysis)
- "Re-run Analysis" = face coordinate bridging (maps face boxes to identity descriptions)
- NOT redundant — orthogonal operations on different data
- UX: should rename for clarity (e.g., "Re-estimate Date & Location" vs "Re-describe Faces")

## KEY CODE LOCATIONS
- Reanalyze endpoint: app/estimate_routes.py:1137
- Face alignment endpoint: app/photo_routes.py:312
- Location display: app/main.py:1860-1920
- Cache invalidation fix: app/estimate_routes.py:1296,1334
- Geocode display name: app/estimate_routes.py:1385-1430
- Migration script: scripts/migrate_all_to_supabase.py
- Supabase sync functions: app/supabase_data.py
