# Lessons Learned

**READ THIS FILE AT THE START OF EVERY SESSION.**

## Session 2026-02-05: R2 Migration Failures

### Lesson 1: Test ALL code paths, not just the obvious one
- **Mistake**: Fixed image URLs for image_* identities but missed inbox_* identities
- **Rule**: When fixing URL generation, grep for ALL places that generate URLs and test each one
- **Prevention**: Before declaring done, list every code path and verify each

### Lesson 2: Regressions require before/after comparison
- **Mistake**: Face box overlays broke during dimension fix -- indentation error caused only 1 box instead of N
- **Rule**: Before committing, compare behavior for ALL affected features
- **Prevention**: Write down what worked before, verify it still works after

### Lesson 3: "It compiles" is not "it works"
- **Mistake**: Declared success when crops loaded, but didn't test Photo Context modal
- **Rule**: Test every UI state, not just the first one you see
- **Prevention**: Create explicit checklist of ALL UI states before starting

### Lesson 4: Staff engineer approval test
- **Question**: "Would a staff engineer at a top company approve this PR?"
- **If no**: Stop and fix before continuing
- **If unsure**: Probably no -- investigate further

### Lesson 5: 2026-02-05 - Indentation bugs when wrapping code in conditionals
- **Mistake**: When wrapping a `for` loop body inside `if has_dimensions:`, only the first few lines of the loop body were re-indented. The rest stayed at the outer level, causing them to run once after the loop instead of per-iteration.
- **Rule**: When adding a new conditional wrapper around existing code, verify EVERY line in the block got re-indented. Check the last line of the block specifically.
- **Prevention**: After any indentation change, read the full block end-to-end and confirm the closing lines are at the correct depth.

### Lesson 6: Auth should be additive, not restrictive by default
- **Mistake**: Protected entire site with Beforeware login requirement — visitors couldn't view anything
- **Rule**: Start with public access, add protection only to specific routes that need it
- **Prevention**: List all routes and explicitly decide: public, login-required, or admin-only

### Lesson 7: Auth guards must respect "auth disabled" mode
- **Mistake**: Adding `_check_admin(sess)` to POST routes broke tests because auth wasn't configured but the check still rejected requests (no user in session)
- **Rule**: When auth is disabled (`is_auth_enabled() == False`), ALL permission checks must pass through
- **Prevention**: First line of every auth check: `if not is_auth_enabled(): return None`

### Lesson 8: Supabase Management API can automate "manual" config
- **Mistake**: Initially declared email templates and OAuth provider setup as "USER ACTION REQUIRED" / manual steps
- **Rule**: Before marking any task as manual, check: (1) CLI tool? (2) Management API? (3) curl-able?
- **Prevention**: The Supabase Management API at `https://api.supabase.com/v1/projects/{ref}/config/auth` can update email templates, enable OAuth providers, and change auth settings. Use a personal access token (from Dashboard → Account → Access Tokens).
- **API fields**: `mailer_templates_confirmation_content`, `mailer_templates_recovery_content`, `mailer_subjects_*`, `external_google_enabled`, `external_google_client_id`, `external_google_secret`

### Lesson 9: Supabase has TWO types of API keys — use the right one
- **Mistake**: Railway had `sb_publishable_...` (new-style publishable key) set as `SUPABASE_ANON_KEY`, but Supabase Auth API requires the legacy JWT key (`eyJ...`)
- **Rule**: The Supabase Auth REST API (`/auth/v1/*`) requires the legacy JWT anon key. The new `sb_publishable_*` keys are for the Supabase client SDK.
- **Prevention**: Get correct keys via Management API: `GET /v1/projects/{ref}/api-keys` — use the key where `type: "legacy"` and `name: "anon"`

### Lesson 10: Facebook OAuth requires Business Verification for production
- **Mistake**: Planned Facebook OAuth as a simple credential-swap step
- **Rule**: Facebook/Meta requires Business Verification + App Review even for basic "Login with Facebook", making it impractical for small/invite-only projects
- **Prevention**: For small projects, stick with Google OAuth + email/password. Only add Facebook if the user base justifies the weeks-long verification process.
