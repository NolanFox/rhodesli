# Session 140 Assessment

**Date:** 2026-03-26
**Version:** v0.99.51
**Status:** IN PROGRESS — auth fix deployed, comprehensive audit running

## Shipped

- [x] **P0 Auth Fix**: Re-exported 7 auth functions from app.auth in main.py's import block. OAuth, login, signup, and password reset were ALL broken since Session 90b.
- [x] **Root Cause Identified**: Session 90b extracted auth_routes.py from main.py but removed the auth function imports. auth_routes.py continued referencing them via `_main_mod` (app.main), causing AttributeError. Tests didn't catch this because they use `create=True` in patches which auto-creates missing attributes.

## Red Flags

- **CRITICAL**: Auth was broken for ~20 sessions (~3 weeks). No user could log in via OAuth, email, or sign up. This went undetected because:
  1. Admin was already logged in (session cookie persisted)
  2. Tests patched at `_main_mod.X` with `create=True` which silently creates the attribute
  3. No integration test that actually exercises the full OAuth flow end-to-end
- **Lesson needed**: Tests with `create=True` on mock patches are dangerous — they mask missing attributes

## AI Tool Usage

- **Tool**: Codex CLI v0.115.0 (gpt-5.4)
- **Task**: Critical audit of all Sessions 138-140 changes — broken _main_mod references, merge artifacts, security
- **Status**: Running

## Next Actions

1. Verify OAuth login works on production
2. Review Codex audit findings
3. Add lesson about `create=True` mock patches
4. Add integration test for auth flow
