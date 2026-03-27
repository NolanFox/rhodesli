# Session 140 Log — P0 Auth Fix + OAuth Redirect

**Started:** 2026-03-26
**Mode:** Emergency fix → iterative debugging with user
**Prompt:** User reported "You broke OAuth. I can't sign in."

## Phase Checklist
- [x] Investigate OAuth failure
- [x] Root cause: missing auth function imports since Session 90b
- [x] Fix 1: Re-export 7 auth functions in main.py
- [x] Deploy + verify: auth/session returns 200
- [x] Fix 2: Post-OAuth redirect to /c/rhodes/ instead of /
- [x] Fix 3: Root page shows "Go to Archive" when logged in
- [x] Fix 4: Form POST replaces fetch() for reliable cookie setting
- [x] Codex critical audit: all 180 _main_mod refs clean
- [x] User confirmed OAuth works end-to-end

## Timeline

### 01:30 UTC — Investigation
- Deploy logs: `AttributeError: module '__main__' has no attribute 'get_user_from_token'`
- Traced to Session 90b (commit b541381): auth_routes extraction removed imports
- ALL auth operations broken: OAuth, email login, signup, password reset

### 01:40 UTC — Fix 1: Re-export auth functions
- Added 7 imports to main.py's `from app.auth import` block
- First attempt (direct import in auth_routes.py) broke tests — patches target `_main_mod.X`
- Final: re-export in main.py, auth_routes continues using `_main_mod.X`
- Commit 5114d2a, deployed, auth/session returns 200

### 02:00 UTC — User reports redirect issue
- Auth works but redirects to `/` (platform root) instead of community page
- Root page shows "Sign In" even when logged in — confusing

### 02:05 UTC — Fix 2: OAuth redirect
- Changed post-login redirect from `/` to `/c/rhodes/`
- Used sessionStorage to save return URL — unreliable in incognito
- Commit 83391c8

### 02:10 UTC — User reports still broken
- sessionStorage cleared by cross-origin OAuth redirect
- Switched to server-side session (`sess["login_return_to"]`)
- Root page nav shows "Go to Archive" when authenticated
- Commit 9f49702

### 02:15 UTC — User reports need to refresh
- fetch() + `window.location.href` race condition: cookie not committed before redirect
- Replaced with form POST → 303 server redirect
- Cookie travels WITH the redirect response — guaranteed to be set
- Commit b1243be

### 02:20 UTC — User confirms working
- OAuth flow works end-to-end in incognito
- Redirects to archive page with session intact
- No manual refresh needed

## Codex Audit (01:50 UTC)
- **Auditor**: Codex CLI v0.115.0 (gpt-5.4)
- **Scope**: All route files, _main_mod references, merge conflicts, security
- **Result**: P0 none, all 180 refs clean, no merge conflicts, no auth bypass
- Ran test suites: auth, workspace signup, community routing — all pass

## Commits
| Hash | Description |
|------|-------------|
| 5114d2a | fix(auth): P0 — re-export auth functions |
| 4869d89 | docs: session 140 assessment + CHANGELOG v0.99.51 |
| 4e1f6a9 | docs: session 140 log |
| 83391c8 | fix(auth): post-OAuth redirect to community page |
| 9f49702 | fix(auth): server-side redirect + root page nav |
| b1243be | fix(auth): form POST instead of fetch for session |
