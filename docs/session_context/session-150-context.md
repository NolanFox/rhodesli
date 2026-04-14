# Session 150 Context — Mobile + Quick Wins + Tool Foundations

## Predecessor
- Session 148d: Codex fixes, Gemini response_schema, Supabase migration, deploy
- Session 149: Investigation infrastructure (table, helpers, preset, endpoint, 79 tests)
- Session 147: PRD-059 Phase 4 identity inference — 18 suggestions, never browser-verified

## Item 1: Mobile Usability (adoption blocker)

### Current State
- Viewport meta present (`app/main.py:271`)
- Tailwind CDN JIT (not precompiled) — 200-800ms first-paint penalty on mobile
- Hamburger nav works at 375px (verified Session 82f)
- Custom CSS: `overflow-x: hidden; max-width: 100vw` on body, `.focus-card-mobile-stack` media query at 640px

### Known Bugs
- **UX-134** (BACKLOG:693): Landing page horizontal overflow at 375px — scrollWidth=780, clientWidth=375. Test `test_mobile_landing_page[chromium]` fails.
- **UX-123** (BACKLOG:524): Face labels overlap when 12+ faces on mobile
- **UX-075** (BACKLOG:308): Face card click targets below 44px WCAG minimum
- **FA-003** (BACKLOG:530): Face description cards overlap on small screens
- **COMPARE-001** (BACKLOG:468): Compare flow not mobile-optimized
- **QA-005-007** (BACKLOG:703): Mobile viewport tests pending

### Mobile-Relevant Route Files (UI-facing)
- `app/page_routes.py` — landing, about
- `app/browse_routes.py` — photo grid
- `app/person_routes.py` — person detail
- `app/photo_routes.py` — photo detail
- `app/compare_routes.py` — compare tool
- `app/estimate_routes.py` — date estimator
- `app/identity_routes.py` — identity cards, suggestions

### Strategy
Focus on the pages people actually share in family group chats:
1. Landing page (first impression)
2. Person page (shared when someone is identified)
3. Photo page (shared when a photo is interesting)
4. Compare modal (used during identification)

Don't touch admin-only pages — admin uses desktop.

## Item 2: TOOLS-005 Estimate v2

### Current State
- PRD: `docs/prds/055_estimate_v2.md` (Draft, Session 133)
- 15 xfail test skeletons across 3 files:
  - `tests/test_estimate_v2_text_hints.py` — 4 xfail
  - `tests/test_estimate_v2_gedcom_paste.py` — 5 xfail
  - `tests/test_estimate_v2_geography_retry.py` — 6 xfail
- Current route: `app/estimate_routes.py:35` (GET /tools/estimate) — photo-only upload
- Upload handler: `app/estimate_routes.py:682` (POST /api/estimate/upload)

### Deliverables (from PRD)
- Flow 1: GEDCOM paste textarea → enriched Gemini prompt
- Flow 2: Free-text hints field → appended to prompt
- Flow 3: Geography retry button → re-run with user location, side-by-side comparison
- New DB columns: `user_context`, `retry_parent_id` on `gemini_api_calls`
- New endpoint: `POST /api/estimate/retry`

### Note
Flow 2 (text hints) is the smallest and most impactful — adds one textarea. Ship this first.

## Item 3: TOOLS-006 Self-Service Archive

### Current State
- BACKLOG entry only (BACKLOG:407), Priority P2
- No dedicated PRD — references `docs/prds/035_multi_community_platform.md`
- WORKSPACE-001 done: `create_personal_archive()` in `app/supabase_data.py:1659`, called during signup in `app/auth_routes.py:381`
- Remaining WORKSPACE work: redirect to personal archive after signup, upload-to-personal-archive

### What This Session Can Do
- Write the PRD (prerequisite for implementation)
- Design the "Create Your Archive" user flow
- Define the data model changes needed

## Item 4: Browser-Verify PRD-059 Phase 4

### Current State
- 18 identity suggestions in Supabase, all PENDING
- Evidence panel UI built (Session 147) with signal bars, accept/reject/needmore buttons
- identity_routes.py: suggestions panel at ~line 870
- Accept via merge route, reject via `/api/skipped/{id}/reject-suggestion`
- NEVER browser-verified on production

### Verification Plan
- Navigate to person pages that have suggestions
- Screenshot the evidence panel
- Verify admin-only visibility
- Check accept/reject buttons render correctly

## Item 5: Batch Event Context on Fader Photos

### Current State
- 147 Fader photos in Supabase (community UUID: `1a2c23d6-fc5e-4d0e-b020-1721579485bf`)
- Endpoint `POST /api/admin/analyze-event-context/{photo_id}` now uses response_schema (Session 148d)
- Gemini returns event_context + relationship_inference with schema enforcement
- No batch variant — need to call endpoint individually per photo

### Strategy
- Write a batch script that queries Fader photo_ids from Supabase
- Calls the Gemini API directly (not via HTTP endpoint) for each photo
- Stores results in a new `event_context_analysis` table or as JSONB on existing tables
- Rate limit: ~15 calls/minute to stay within Gemini quota
- Cost estimate: 147 photos * ~$0.01/call = ~$1.50

## Item 6: ENV-001 Dev/Staging/Prod Separation

### Current State
- `app/main.py:170-179`: Sentry init checks `SENTRY_DSN` env var
- `SENTRY_ENVIRONMENT` defaults to `"production"` if unset
- No `.env.example` entry for SENTRY_ENVIRONMENT
- No dev/staging guard — local development sends to production Sentry
- Breadcrumbs in `app/supabase_data.py:613,672`

### Fix (minimal)
1. Add `SENTRY_ENVIRONMENT=development` to `.env`
2. Add `SENTRY_ENVIRONMENT` to `.env.example`
3. Guard: don't initialize Sentry when `SENTRY_ENVIRONMENT=development`
4. Or: set `traces_sample_rate=0` in development

## Parallelization Analysis

### Independent tracks (can use worktrees):
- **Track A**: Mobile CSS fixes (page_routes, browse_routes, person_routes, photo_routes — NOT main.py)
- **Track B**: TOOLS-005 Flow 2 text hints (estimate_routes.py only)
- **Track C**: ENV-001 fix (main.py:170-179, .env, .env.example)
- **Track D**: PRD writing for TOOLS-006

### Sequential (same agent):
- Browser verification (needs Chrome plugin)
- Batch Fader event context (needs Gemini API key, rate limiting)

### File conflicts:
- main.py: ENV-001 (lines 170-179) — small, isolated change
- estimate_routes.py: TOOLS-005 only
- Route files for mobile: spread across multiple files, no overlap with above

## Deferred
- Fader identification work (Anna/David Josowitz, Nellie confirmation) — deferred until more photos arrive from another family branch that may have Sarah Fox Fader photos
