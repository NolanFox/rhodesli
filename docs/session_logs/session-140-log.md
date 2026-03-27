# Session 140 Log — P0 Auth Fix + Comprehensive Audit

**Started:** 2026-03-26
**Mode:** Implementation (emergency fix)
**Prompt:** User reported OAuth broken

## Phase Checklist
- [x] Investigate OAuth failure
- [x] Identify root cause (missing auth function imports since Session 90b)
- [x] Fix: re-export 7 auth functions in main.py
- [x] Tests: 3780 pass
- [x] Deploy: SUCCESS (commit 5114d2a)
- [x] Codex audit: all 180 _main_mod references verified correct, zero merge conflicts
- [x] Own audit: Python script verified all _main_mod.X references resolve

## Timeline

### Investigation (01:30 UTC)
- User reported "You broke OAuth. I can't sign in."
- Checked deploy logs: `AttributeError: module '__main__' has no attribute 'get_user_from_token'`
- Traced to auth_routes.py calling `_main_mod.get_user_from_token()` where `_main_mod` = `app.main`
- `get_user_from_token` defined in `app/auth.py` but NOT imported in `app/main.py`

### Root Cause Analysis (01:35 UTC)
- Session 90b (commit b541381) extracted auth_routes.py from main.py
- That commit removed imports: signup_with_supabase, validate_invite_code, send_password_reset, update_password, get_user_from_token, exchange_code_for_session
- auth_routes.py continued using `_main_mod.X` for ALL of them → AttributeError
- Tests didn't catch it: patches use `create=True` which auto-creates missing attributes
- ALL auth operations (OAuth, email login, signup, password reset) broken for ~20 sessions

### Fix (01:40 UTC)
- First attempt: import auth functions directly in auth_routes.py → broke tests (patches target `_main_mod.X`)
- Final fix: re-export all 7 auth functions from app.auth in main.py's import block
- auth_routes.py continues using `_main_mod.X` pattern (compatible with existing test patches)
- 3780 tests pass

### Verification (01:47 UTC)
- Deploy SUCCESS on Railway
- Login page returns 200
- No auth errors in deploy logs
- Codex CLI audit: all 180 _main_mod references verified across 8 route files
- Python script audit: confirms all references resolve

## Lesson
**Lesson 157**: Tests with `create=True` on mock patches silently mask missing attributes. The `create=True` parameter creates the attribute if it doesn't exist, which means a test can pass even when the actual code would raise AttributeError. Avoid `create=True` on critical path patches, or add a structural test that verifies all `_main_mod.X` references resolve without mocking.
