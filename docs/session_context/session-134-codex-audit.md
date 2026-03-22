# Session 134 — Security + Performance Audit Report

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
- SEC-002: ILIKE wildcard escaping in person search (P2) — FIXED in session
- SEC-003: CSRF check on /tools/search POST (P3)
- SEC-004: Invite code timing (P3)

---

## Performance Audit

**Tool:** Claude subagent
**Target files:** `app/main.py`, `app/page_routes.py`, `app/perf_cache.py`
**Strategy:** Push back on items already fixed in Sessions 111f-125

### Performance Findings

| # | Finding | Severity | Disposition |
|---|---------|----------|-------------|
| P1 | `list_identities()` copies all dicts, called 12-15x per request | P2 | BACKLOG — add state-indexed cache or count_by_state() |
| P2 | `_compute_discoveries()` frozenset cache key + 3 list_identities calls | P3 | BACKLOG |
| P3 | `save_registry()` deepcopy for JSON backup | P2 | **FIXED** — json.dumps instead (-20-50ms) |
| P4 | `/health` reads photo_index.json from disk | P3 | BACKLOG |
| P5 | `_compute_landing_stats()` 5+ list_identities calls | P2 | BACKLOG — cache with 30s TTL |
| P6 | `/photos` computes confirmed_count for all 971 photos, displays 24 | P2 | BACKLOG |
| P7 | Sidebar counts duplicate list_identities calls | P2 | BACKLOG |
| P8 | perf_cache loads communities on every community-scoped call | P3 | BACKLOG |

### Performance Measurements (Production, 2026-03-22)
| Page | Time | Target | Status |
|------|------|--------|--------|
| Tree | 440ms | <3s | PASS |
| Landing | 827ms | — | OK |
| People grid | 856ms | — | OK |
| Compare | 257ms | — | OK |
| Estimate | 357ms | — | OK |
| 404 | 496ms | — | OK |

### Performance Value Assessment
- **Rating:** MODERATE
- **Rationale:** Dominant theme (list_identities N copies) is real but structural — fixing requires IdentityRegistry refactor. The deepcopy fix (P3) was the only actionable item.
- **Would we have found this ourselves?** Yes, eventually. The list_identities pattern is a classic N+1 variant.
