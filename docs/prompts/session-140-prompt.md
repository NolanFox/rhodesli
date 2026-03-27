# Session 140: P0 Auth Fix + OAuth Redirect (Emergency)

**Type:** Emergency / Interactive (no pre-written prompt — user-reported P0)
**Date:** 2026-03-27
**Predecessor:** Session 139 (v0.99.50)
**Context:** `docs/session_context/session-140-context.md`

## Trigger

User reported: "You broke OAuth. I can't sign in." All auth operations (OAuth, login, signup, password reset) broken since Session 90b (~20 sessions, ~3 weeks undetected).

## Goals

1. **Diagnose and fix auth breakage** — identify root cause of OAuth/login failure
2. **Fix OAuth redirect flow** — ensure post-login redirect works reliably (no cookie race)
3. **Root page nav** — show correct state for logged-in vs anonymous users
4. **Codex critical audit** — verify all _main_mod references are intact across route files
5. **Lessons** — document create=True masking (157) and fetch cookie race (158)

## Acceptance Criteria

- OAuth login works end-to-end (user-confirmed)
- Post-login redirects to community page, not platform root
- Root page shows "Go to Archive" when logged in
- All 180 _main_mod refs verified clean
- 3780 app tests pass

## Backfill Note

This prompt was backfilled from session log and assessment (Session 142 harness audit). Session 140 was reactive — the user reported a P0 during an interactive session, so no prompt was written in advance.
