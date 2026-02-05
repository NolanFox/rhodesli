# Master Task: Fix Auth System — Public Access + Role-Based Permissions

**Session**: 2026-02-05
**Status**: COMPLETE

## Phase 1: Rewrite auth module
- [x] Replace Supabase SDK with direct httpx calls
- [x] Add User dataclass with is_admin flag
- [x] Add ADMIN_EMAILS environment variable support
- [x] Add get_current_user(), validate_invite_code()

## Phase 2: Remove blanket auth, add granular protection
- [x] Remove Beforeware that blocked all routes
- [x] Add _check_admin() guard to 13 admin-only POST routes
- [x] Add _check_login() guard to upload POST route
- [x] Auth checks pass through when auth is disabled

## Phase 3: Update UI for permission-aware rendering
- [x] review_action_buttons: hidden for non-admins
- [x] name_display: edit button hidden for non-admins
- [x] face_card: detach button hidden for non-admins
- [x] identity_card_expanded: action buttons hidden for non-admins
- [x] sidebar: login/logout state, conditional upload button
- [x] Thread is_admin through render pipeline

## Phase 4: Dependencies and config
- [x] Replace supabase SDK with httpx in requirements.txt
- [x] Add ADMIN_EMAILS to .env.example

## Phase 5: Verification
- [x] Syntax check passes
- [x] All imports work
- [x] Tests: 318 passing, 7 pre-existing failures (no new failures)
- [x] Committed: da6bc61

## USER ACTION REQUIRED (Railway deployment)
- [ ] Add `ADMIN_EMAILS=NolanFox@gmail.com` to Railway env vars
- [ ] Disable "Confirm email" in Supabase Auth settings if signup fails
- [ ] Deploy (auto-deploys on `git push origin main`)
- [ ] Test public access: visit site without logging in
- [ ] Test admin access: login with admin email, verify action buttons appear
