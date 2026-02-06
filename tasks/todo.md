# Task: Email Templates + Verification + Testing Harness

**Session**: 2026-02-05 (session 5)
**Status**: COMPLETE

## Phase 1: Email Templates
- [x] Push email templates with inline styles to Supabase
- [x] Update email subjects (all 4 templates)
- [x] Attempt sender name update (requires custom SMTP — not possible with built-in mailer)
- [x] Trigger test recovery email

## Phase 2: Test User + Verification
- [ ] Create test user (rhodesli.testuser@gmail.com) — deferred (needs live site verification)
- [ ] Run automated production checks — deferred (local tests prioritized)

## Phase 3: Regression Test Suite
- [x] Created `tests/conftest.py` — shared fixtures for auth states
- [x] Created `tests/test_auth.py` — 23 tests for login, signup, forgot/reset password, OAuth, logout
- [x] Created `tests/test_permissions.py` — 19 tests for permission matrix (public/admin/user routes)
- [x] Created `tests/test_ui_elements.py` — 17 tests for OAuth buttons, scripts, modals, branding
- [x] All 59 new tests passing
- [x] No regressions in existing tests (9 pre-existing failures in old test files)

## Phase 4: Harness Updates
- [x] Added "Testing Requirements" section to CLAUDE.md
- [x] Added lessons 14-18 to tasks/lessons.md
- [x] Updated tasks/todo.md

## Ongoing
- [ ] Maintain test coverage for all auth/permission/UI changes
- [ ] Fix 9 pre-existing test failures in test_app.py, test_inbox_contract.py, test_photo_serving_integration.py
