# Session 128 Context — Security Hardening + Accessibility + Dead Code

**Predecessor:** [Session 127 Context](session-127-context.md)
**Assessment:** [Session 127 Assessment](../assessments/session-127-assessment.md)
**Audit:** [Session 127 Codex Audit](session-127-codex-audit.md)

## Goal

Harden security posture from Session 127 audit findings, ship accessibility quick wins, clean dead code, and fix remaining audit gaps. This is a "clean the house" session — no new features, just making existing code safer, more accessible, and leaner.

## Why Now

Session 127 ran a comprehensive security + accessibility audit that found 26 issues:
- 2 P0 security (1 fixed: path traversal. 1 noted: session secret default)
- 4 P1 security (CSRF, rate limiting, unguarded endpoint, duplicate routes)
- 4 P2 security (exec_sql, filename sanitization, token default, error leakage)
- 9 accessibility gaps
- 8 dead code items

The P0 path traversal was fixed in Session 127. Everything else is open.

## Carryover from Session 127

### Must Do (Security)
1. **CSRF protection** (SEC-127-001) — SameSite=Strict cookies as immediate mitigation. Full CSRF middleware is overkill for this app (no cross-origin embedding scenario). Add Origin header check on state-changing POST routes as belt-and-suspenders.
2. **Rate limiting on public uploads** (SEC-127-002) — 6 public upload endpoints. IP-based rate limit: 20 uploads/hour per IP. Use simple in-memory dict with TTL.
3. **ML_SERVICE_TOKEN default** — Fail loudly if ML_SERVICE_URL is set but token is `"dev-token"`.
4. **Duplicate routes** — Remove 3 duplicate route definitions (reject-match, correct-date, face-alignment in page_routes.py/browse_routes.py).

### Must Do (Accessibility)
5. **Skip-to-content link** (A11Y-005) — 15 min, high a11y value
6. **`<main>` landmark** (A11Y-009) — 30 min, screen reader structure
7. **Alt text on crop images** (A11Y-001) — ~18 images, batch fix
8. **Icon-only button aria-labels** (A11Y-002) — top 50 most-used buttons

### Should Do (Dead Code)
9. **Remove `compare_v2_routes.py`** — entire file is 501 stubs
10. **Move `app/audit_notes.md` + `app/ui_spec.md`** to docs/
11. **Remove duplicate `sys.path` insertion** in main.py
12. **Verify CONTRIBUTOR_EMAILS wiring** or document deprecation

### Should Do (Session 127 Gaps)
13. **Top bar label alignment** — "TO REVIEW" vs "PROPOSALS" text should match sidebar
14. **Harness rule codification** — new `.claude/rules/session-defaults.md` written, needs HD entry

## Technical Notes

### CSRF Approach (Recommended)
Full CSRF token middleware adds complexity and breaks HTMX patterns. Instead:
1. Set `SameSite=Strict` on session cookies (prevents cross-origin cookie sending)
2. Add `_check_origin(request)` helper that validates Origin/Referer header matches our domain
3. Wire it into the top 10 most dangerous POST routes (merge, confirm, reject, upload-approve)
This blocks 99% of CSRF without a token system.

### Rate Limiting Approach (Recommended)
Simple in-memory rate limiter — no Redis needed at our scale:
```python
# app/rate_limit.py
from collections import defaultdict
import time

_requests = defaultdict(list)  # IP -> [timestamps]

def check_rate_limit(ip: str, max_per_hour: int = 20) -> bool:
    now = time.time()
    _requests[ip] = [t for t in _requests[ip] if now - t < 3600]
    if len(_requests[ip]) >= max_per_hour:
        return False
    _requests[ip].append(now)
    return True
```

### Parallelization Plan
- **Track A** (worktree): Security — CSRF + rate limiting + token validation + duplicate routes
- **Track B** (worktree): Accessibility — skip-to-content, `<main>`, alt text, aria-labels
- **Track C** (worktree): Dead code cleanup — remove stubs, move docs, sys.path
- **Track D** (main after merge): Top bar label fix, harness docs, codex audit

Tracks A, B, C touch completely different files — fully parallelizable.

## Breadcrumbs
- Session 127 audit: `docs/session_context/session-127-codex-audit.md`
- Session 127 assessment: `docs/assessments/session-127-assessment.md`
- BACKLOG items: SEC-127-001 through SEC-127-003, DEAD-127-001
- Harness rule: `.claude/rules/session-defaults.md` (new Session 127)
- Lessons: `tasks/lessons.md`
