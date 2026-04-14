---
name: Codex Audit Mandate
description: User wants Codex-style security audit as standard practice for every session with code changes
type: feedback
---

User explicitly requested that Codex-style security auditing should be a mandatory rule for sessions with code changes, similar to Session 118 (HD-028).

**Why:** Session 118 found real security issues (upload community override) via Codex audit. User sees value in cross-AI code review for security scopes.

**How to apply:** Every session with code changes should include a security audit phase. Review changed files for auth guards, injection, XSS, input validation, and OWASP top 10. Document findings. Fix P0/P1 immediately, P2+ to BACKLOG.
