# Task: Complete Auth System — Standard Login Experience

**Session**: 2026-02-05 (sessions 2+3)
**Status**: COMPLETE

## Password Recovery
- [x] Add send_password_reset() to auth.py
- [x] Add update_password() to auth.py
- [x] Add GET/POST /forgot-password routes
- [x] Add GET/POST /reset-password routes
- [x] Add "Forgot password?" link to login page
- [x] Syntax check passes
- [x] Tests: 320 passing, 8 pre-existing failures (no new failures)

## OAuth / Social Login
- [x] Add get_oauth_url() to auth.py
- [x] Add get_user_from_token() to auth.py
- [x] Add GET /auth/callback route (client-side token extraction)
- [x] Add POST /auth/session route (token → session)
- [x] Add Google/Facebook buttons to login page (conditionally shown)

## Email Templates (via Management API)
- [x] Created docs/design/EMAIL_TEMPLATES.md with dark theme templates
- [x] Updated confirmation subject: "Welcome to Rhodesli!"
- [x] Updated recovery subject: "Reset your Rhodesli password"
- [x] Updated magic link subject: "Your Rhodesli login link"
- [x] Updated invite subject: "You're invited to Rhodesli!"
- [x] All 4 template bodies updated with dark theme HTML

## Supabase Configuration (via Management API)
- [x] Site URL set: `https://rhodesli.nolanandrewfox.com`
- [x] Redirect URLs set: `https://rhodesli.nolanandrewfox.com/**`
- [x] Google OAuth enabled with client credentials
- [x] Fixed SUPABASE_ANON_KEY on Railway (was publishable key, needs JWT key)

## Railway
- [x] Set SITE_URL=https://rhodesli.nolanandrewfox.com
- [x] Fixed SUPABASE_ANON_KEY to use legacy JWT key
- [x] Pushed to trigger redeploy

## Facebook OAuth
- [x] DEFERRED — requires Meta Business Verification + App Review, impractical for invite-only MVP

## Verification
- [x] Test password reset email sent to NolanFox@gmail.com
- [ ] Confirm dark theme email arrived (USER)
- [ ] Verify Google login button on live site (after deploy)
- [ ] End-to-end: forgot password → email → reset → login
