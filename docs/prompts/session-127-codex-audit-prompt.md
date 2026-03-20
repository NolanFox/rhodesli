# Session 127 Codex Audit — Security + Accessibility + Dead Code

Audit the Rhodesli codebase for:

1. **Security**: auth guard gaps on POST routes, input sanitization, SQL injection via Supabase RPC, CSRF
2. **Accessibility**: missing aria-labels, focus traps, keyboard-only navigation blockers, color contrast below WCAG AA
3. **Dead code**: unused routes, orphaned imports, stale feature flags

Read all files in `app/`. Write findings to `docs/session_context/session-127-codex-audit.md`.

**Do NOT modify any code.**
