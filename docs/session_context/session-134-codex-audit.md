# Session 134 — Security Audit Report

**Tool:** Claude subagent (in lieu of Codex CLI)
**Strategy:** HD-028 — fresh audit, no prior context
**Date:** 2026-03-22

## Target Files
- `app/nl_query_executor.py` — NL query executor
- `app/auth_routes.py` — Signup wiring
- `app/tools_routes.py` — /tools/search route

## Findings Summary

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| 1 | `.or_()` filter injection (latent) | P1 | BACKLOG — fix before Gemini parser |
| 2 | ILIKE wildcard not escaped | P2 | BACKLOG |
| 3 | No rate limit on search | P2 | **FIXED** — 60/hr per IP |
| 4 | No CSRF on search POST | P3 | BACKLOG |
| 5 | Open redirect via `//` in `next` | P2 | **FIXED** — blocked `//` prefix |
| 6 | No rate limit on login/signup | P2 | **FIXED** — 10/hr login, 5/hr signup |
| 7 | Invite code timing side-channel | P3 | BACKLOG |
| 8 | XSS (framework-mitigated) | P3 | BACKLOG (informational) |
| 9 | Personal archive creation not atomic | P3 | BACKLOG |
| 10 | No input length limit on search | P3 | **FIXED** — 500 char cap |

## Value Assessment
- **Rating:** STRONG
- **Rationale:** Finding 5 (open redirect) was a real phishing risk we would have missed. Rate limiting gaps (3, 6) were systematically identified across all public POST routes.
- **Would we have found this ourselves?** The open redirect: unlikely (subtle `//` edge case). The rate limiting: maybe eventually but not comprehensively.

## BACKLOG Items Created
- SEC-001: `.or_()` PostgREST filter injection sanitization (P1, fix before TOOLS-004 Phase 2)
- SEC-002: ILIKE wildcard escaping in person search (P2)
- SEC-003: CSRF check on /tools/search POST (P3)
- SEC-004: Invite code timing (P3)
