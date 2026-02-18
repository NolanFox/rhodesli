# Auth & Permissions Lessons

Lessons about authentication, OAuth, Supabase, and permission models.
See also: `docs/architecture/PERMISSIONS.md`

---

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
- **Prevention**: The Supabase Management API at `https://api.supabase.com/v1/projects/{ref}/config/auth` can update email templates, enable OAuth providers, and change auth settings. Use a personal access token (from Dashboard -> Account -> Access Tokens).
- **API fields**: `mailer_templates_confirmation_content`, `mailer_templates_recovery_content`, `mailer_subjects_*`, `external_google_enabled`, `external_google_client_id`, `external_google_secret`

### Lesson 9: Supabase has TWO types of API keys — use the right one
- **Mistake**: Railway had `sb_publishable_...` (new-style publishable key) set as `SUPABASE_ANON_KEY`, but Supabase Auth API requires the legacy JWT key (`eyJ...`)
- **Rule**: The Supabase Auth REST API (`/auth/v1/*`) requires the legacy JWT anon key. The new `sb_publishable_*` keys are for the Supabase client SDK.
- **Prevention**: Get correct keys via Management API: `GET /v1/projects/{ref}/api-keys` — use the key where `type: "legacy"` and `name: "anon"`

### Lesson 10: Facebook OAuth requires Business Verification for production
- **Mistake**: Planned Facebook OAuth as a simple credential-swap step
- **Rule**: Facebook/Meta requires Business Verification + App Review even for basic "Login with Facebook", making it impractical for small/invite-only projects
- **Prevention**: For small projects, stick with Google OAuth + email/password. Only add Facebook if the user base justifies the weeks-long verification process.

### Lesson 11: HTMX silently follows 3xx redirects — use 401 + beforeSwap for auth
- **Mistake**: `_check_admin()` returned `RedirectResponse("/login", 303)`. HTMX followed the redirect transparently, fetched the full login page HTML, and swapped it into the target element (replacing the identity card).
- **Rule**: For HTMX-triggered auth failures, return 401 (not 303). Use a global `htmx:beforeSwap` handler to intercept 401 and show a login modal.
- **Prevention**: Never use RedirectResponse for auth guards that protect HTMX POST endpoints. Use `Response("", status_code=401)` and handle it client-side.

### Lesson 13: Supabase recovery email redirects to Site URL by default
- **Mistake**: Password reset email link redirected to `/#access_token=...` (the Site URL) instead of `/reset-password#access_token=...`.
- **Rule**: Pass `redirect_to` in the options when calling `/auth/v1/recover` to control where the user lands.
- **Prevention**: Always specify `"redirect_to": f"{site_url}/reset-password"` in the recovery request body.

### Lesson 15: Permission regressions are the most dangerous bugs
- **Mistake**: Changing `_check_admin` to return 303 (redirect) instead of 401 broke HTMX inline actions silently — the page appeared to work but swapped in full login page HTML.
- **Rule**: Always test the full matrix of routes x auth levels (anonymous, user, admin).
- **Prevention**: `tests/test_permissions.py` has matrix tests for all admin routes. Run them after any auth change.

### Lesson 18: Supabase sender name requires custom SMTP
- **Mistake**: Tried to set `smtp_sender_name` via Management API, but it only works when custom SMTP is configured.
- **Rule**: Supabase's built-in mailer uses a fixed sender name. Custom sender requires configuring custom SMTP (Resend, SendGrid, etc.).
- **Prevention**: Check if custom SMTP is configured before trying to change sender-related fields.

### Lesson 19: Default to admin-only for new data-modifying features
- **Mistake**: `POST /upload` used `_check_login` (any user), but had no file size limits, rate limiting, or moderation queue. Any logged-in user could fill disk with uploads.
- **Rule**: Default to admin-only for new data-modifying features. Loosen permissions only when moderation/guardrails are in place.
- **Prevention**: When adding a new POST route that writes data, use `_check_admin` first. Add a `# TODO: Revert to _check_login when <guardrail> is built` comment. Only downgrade to `_check_login` after implementing the guardrail.

### Lesson 22: Upload permissions should be admin-only until moderation exists
- **Mistake**: Originally had `_check_login` on upload, which was too permissive without rate limiting or moderation.
- **Rule**: Default new data-modifying routes to `_check_admin`. Only downgrade to `_check_login` when the moderation queue (pending uploads) is implemented.
- **Prevention**: The pending upload queue (Phase 3) is the guardrail that allows reverting to `_check_login`.
