# Task: Complete Auth System — Standard Login Experience

**Session**: 2026-02-05 (session 2)
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

## Email Templates
- [x] Created docs/design/EMAIL_TEMPLATES.md with dark theme templates

## USER ACTION REQUIRED

### Supabase Configuration
- [ ] Set Site URL: Authentication → URL Configuration → `https://rhodesli.nolanandrewfox.com`
- [ ] Set Redirect URLs: `https://rhodesli.nolanandrewfox.com/**`
- [ ] Customize email templates: Authentication → Email Templates (copy from docs/design/EMAIL_TEMPLATES.md)

### Google OAuth (optional)
- [ ] Create OAuth Client at https://console.cloud.google.com/apis/credentials
- [ ] Redirect URI: `https://fvynibivlphxwfowzkjl.supabase.co/auth/v1/callback`
- [ ] Enable in Supabase → Authentication → Providers → Google

### Facebook OAuth (optional)
- [ ] Create App at https://developers.facebook.com/apps
- [ ] Redirect URI: `https://fvynibivlphxwfowzkjl.supabase.co/auth/v1/callback`
- [ ] Enable in Supabase → Authentication → Providers → Facebook

### Railway
- [ ] Add `SITE_URL=https://rhodesli.nolanandrewfox.com` environment variable
