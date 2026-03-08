# Session 92 Gap Closure Sprint — Full Plan

## PRIORITY 1: Leon's Restaurant → Asheville (USER BLOCKING)
- Code deployed: sibling GEDCOM context + visible_text extraction + prompt strengthening
- Photo 3192877a90a174e9 needs RE-ANALYSIS in production browser
- Click "Re-analyze" button on https://rhodesli.nolanandrewfox.com/photo/3192877a90a174e9
- If still not Asheville: debug the actual prompt Gemini receives, fix, redeploy, re-analyze again
- DO NOT STOP until Asheville appears on that page

## PRIORITY 2: Merge Supabase Migration (from worktree)
- Worktree branch: worktree-agent-abff88ab
- Path: /Users/nolanfox/rhodesli/.claude/worktrees/agent-abff88ab
- Contains: scripts/migrate_all_to_supabase.py, supabase_data.py updates, route dual-write wiring, tests
- Merge to main, run tests, push

## PRIORITY 3: Create Supabase Tables + Run Migration
- 9 new tables: date_labels, photo_locations, person_comments, discovery_log, audit_log, pending_uploads, comparison_results, birth_year_estimates, corrections_log
- Run migration script to backfill all JSON data
- Verify data in Supabase

## PRIORITY 4: Remaining Gaps (from screenshots)
| # | Gap | Action |
|---|-----|--------|
| G1 | SENTRY_DSN + POSTHOG_API_KEY | Check Railway vars via CLI |
| G2 | DATA_SOURCE=postgres | Enable on Railway after migration completes |
| G3 | OPS-001 Custom SMTP | Wire Resend with custom domain |
| G4 | Test speed <30s | Profile and optimize slow tests |
| G5 | Email notifications | Wire Resend to notification triggers |
| G6 | Confirm→notification E2E | Browser verify after deploy |
| G7 | main.py <5K | Extract more routes |
| G8 | e2e test_admin_review_queue_sorted | Fix test |
| G9 | Leon's face alignment | Run alignment on Leon's photo |
| G10 | Timeline integration | Wire life_events to timeline |
| G11 | pgvector migration | Enable pgvector extension, migrate embeddings |

## PRIORITY 5: Harness Rules to Prevent Future Gaps
- Add rule: "SKIPPED is not an acceptable status — everything must be DONE or have a BLOCKER with a fix plan"
- Add rule: "Re-analysis must happen after prompt changes — code deploy alone doesn't update cached results"

## BLOCKER: Railway Trial Expired
- Railway trial expired — site is DOWN
- All recent deploys show REMOVED
- `railway deployment redeploy --yes` returns "Your trial has expired"
- Nolan must select a paid plan at https://railway.app
- Once plan is active, deploy will auto-trigger from latest git push (ffe38af)

## Current State
- Branch: main
- Last push: ffe38af (Supabase migration merged)
- All code is committed and pushed to GitHub
- Railway DOWN (trial expired)
- Tests: 86 new tests pass (54 migration + 32 session92), ML 566 pass
- Worktree cleaned up (merged)

## Commits pushed but not yet deployed:
- `0eeefd1` — fix(gedcom): sibling residence/occupation events (AD-210)
- `ffe38af` — feat(data): comprehensive Supabase migration

## After Railway is back online:
1. Navigate to /photo/3192877a90a174e9
2. Click "Re-analyze" button
3. Verify Asheville appears
4. Run migration script: `python scripts/migrate_all_to_supabase.py`
5. Set DATA_SOURCE=postgres on Railway
6. Set SENTRY_DSN + POSTHOG_API_KEY on Railway
