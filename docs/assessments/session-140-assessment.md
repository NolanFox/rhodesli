# Session 140 Assessment

**Date:** 2026-03-26/27
**Version:** v0.99.51
**Status:** COMPLETE

## Shipped

- [x] **P0 Auth Fix**: Re-exported 7 auth functions from app.auth in main.py. OAuth, login, signup, password reset all restored.
- [x] **OAuth Redirect Fix**: Changed from fetch() + client JS redirect to form POST → 303 server redirect. Session cookie now travels with the redirect response.
- [x] **Root Page Nav**: Shows "Go to Archive" when logged in, "Sign In" when not.
- [x] **Login Redirect**: Already-logged-in users clicking "Sign In" redirect to `/c/rhodes/` not `/`.
- [x] **Codex Critical Audit**: All 180 `_main_mod` refs verified across 10 route files. No merge conflicts. No auth bypass. No data safety issues.

## Root Cause Analysis

### Auth Functions Missing (P0)
- **When**: Session 90b (commit b541381, 2026-03-06)
- **What**: Extracted auth_routes.py from main.py, removed 7 auth function imports
- **Why undetected**: Tests patch `_main_mod.X` with `create=True` which auto-creates missing attrs
- **Impact**: ALL auth operations broken for ~20 sessions (~3 weeks)
- **Fix**: Re-export functions in main.py import block

### OAuth Cookie Race (P1)
- **What**: fetch() API sets session cookie via XHR response header, but `window.location.href` redirect fires before browser commits the cookie
- **Why**: fetch() handles cookies asynchronously; the redirect is synchronous
- **Fix**: Use form POST → 303 redirect (same pattern as email/password login)

## Lessons Added

### Lesson 157: Tests with `create=True` mask missing attributes
Mock patches with `create=True` silently create attributes that don't exist on the target module. A test can pass even when the real code would raise `AttributeError`. Avoid `create=True` on critical path patches. Add structural tests that verify all `_main_mod.X` references resolve.

### Lesson 158: Never use fetch() + client redirect for auth
Session cookies set by XHR responses may not be committed before a JS redirect fires. Always use form POST → server 303 redirect for auth flows. The cookie travels with the redirect response, guaranteeing it's set before the target page loads.

## AI Tool Usage

- **Tool**: Codex CLI v0.115.0 (gpt-5.4)
- **Agent type**: Independent (fresh context)
- **Task**: Critical audit — broken _main_mod refs, merge conflicts, security, data safety
- **Findings**: P0 none, P1 none, P2 none, P3 one (audit script writes file unconditionally)
- **Verification**: Ran auth, workspace signup, and community routing tests
- **Value**: STRONG — confirmed the fix was complete, no other broken refs

## Harness Compliance

- [x] Assessment file exists
- [x] Session log exists
- [x] CHANGELOG updated (v0.99.51)
- [x] Codex audit with provenance
- [x] Tests pass (3780)
- [x] Deployed and verified (user confirmed OAuth works)
- [x] `git log origin/main..HEAD` clean

## Next Session Should Verify

1. Structural test for _main_mod references (prevent recurrence)
2. OAuth flow in incognito from multiple entry points (root, community, person page)
