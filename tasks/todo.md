# Task: UX & Auth Polish — Pre-Launch Fixes

**Session**: 2026-02-05 (session 4)
**Status**: COMPLETE

## Issues Fixed
- [x] Issue 1: Password recovery flow — added redirect_to, PKCE code exchange
- [x] Issue 2: Email button legibility — inline styles on all email template buttons
- [x] Issue 3: Remove Facebook button — provider allow-list in auth.py
- [x] Issue 4: Google button styling — official 4-color G logo, white background
- [x] Issue 5: Unauthenticated action flow — login modal, 401 instead of 303
- [x] Issue 6: Error hash handling — global JS toast for otp_expired, access_denied

## Additional Improvements
- [x] Styled confirmation dialog replacing native browser confirm()
- [x] Email template update script (scripts/update_email_templates.sh)
- [x] htmx:beforeSwap global handler for 401 interception
- [x] htmx:confirm global handler for styled confirmations
- [x] Recovery token redirect (wrong page → /reset-password)

## Pending (requires SUPABASE_ACCESS_TOKEN)
- [ ] Push email templates to Supabase via Management API
- [ ] Update sender name to "Rhodesli"
- [ ] Verify email button rendering in inbox

## Verification
- [ ] Visual: Google button has 4-color G logo on /login
- [ ] Visual: No Facebook button on /login
- [ ] Manual: Password reset email → /reset-password (not /)
- [ ] Manual: Click Merge in incognito → login modal appears, card intact
- [ ] Manual: Click Merge when logged in → styled confirm dialog
- [ ] Manual: Navigate to /#error=access_denied&error_code=otp_expired → toast
- [ ] Manual: Trigger test email → verify white button text
