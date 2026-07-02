---
name: route-safety-audit
description: >
  Checklist + audit protocol for FastHTML/HTMX route safety in rhodesli: auth guards, CSRF
  origin checks, rate limits, community-scoping (/c/<slug>/ prefix + data filtering), and
  HTMX-specific auth semantics. Load BEFORE adding/modifying any route (especially POST/write
  routes), changing auth helpers, or touching community filtering/middleware. Also the playbook
  for periodic route-security sweeps. DO NOT USE FOR: pure ML pipeline work, batch scripts with
  no HTTP surface, or docs work.
---

# Route Safety Audit — auth, CSRF, scoping, HTMX

## Why this skill exists (the scar tissue)
Permission regressions are this project's most dangerous UI bugs (Lesson 15). Session 111 found
80+ community-prefix gaps across 11 route files; Session 96 leaked cross-community data because
a failed scoping lookup was cached as `None` = "no filtering" (Lesson 151); Session 140 found
ALL auth operations broken since Session 90b because re-exports were dropped in a refactor.
HTMX changes the rules: a 303 redirect on an auth failure silently swaps the login page INTO the
target element (Lesson 11).

## Triggers — WHEN to load
- Adding or modifying ANY route, especially POST/PUT/DELETE handlers
- Refactoring route modules (extraction from `app/main.py`/`app/page_routes.py`)
- Touching `app/auth.py`, CommunityMiddleware, or community-scoped queries
- A session prompt asks for a security/scoping sweep
WHEN NOT: ML pipeline code, scripts without HTTP surface, styling-only changes.

## Required reading
1. `docs/architecture/PERMISSIONS.md` — the permission matrix (binary: public vs admin)
2. `tasks/lessons/auth-lessons.md` — Lessons 6, 7, 11, 15, 19, 22
3. `tasks/lessons.md` — Lessons 109, 112, 113, 151 (community scoping)
4. `app/auth.py` — `_check_admin`, `_check_login`, `_check_origin` (line ~245), `is_auth_enabled`
5. `tests/test_permissions.py`, `tests/test_route_permissions.py`, `tests/test_community_prefix_audit.py`

## The write-route checklist (every POST/PUT/DELETE handler)
1. **Auth guard first.** Default NEW data-modifying routes to `_check_admin(sess)`; downgrade to
   `_check_login` only when a moderation queue/guardrail exists (Lessons 19/22). Intentionally
   public write surfaces (help-identify, tool uploads) need rate limiting + input size caps instead.
2. **CSRF: `_check_origin(request)`** on every state-changing route (Session 128 pattern;
   cookies are SameSite=Strict but origin-check is the enforced layer).
3. **Auth-disabled passthrough.** Guards must return `None` when `is_auth_enabled()` is False,
   or every test breaks (Lesson 7). Never bypass by checking env vars directly in handlers.
4. **HTMX auth semantics: return 401, never 303.** HTMX follows redirects silently and swaps
   login-page HTML into the target element. The client `htmx:beforeSwap` handler shows the login
   modal on 401 (Lesson 11).
5. **Community scoping.** HTMX-generated URLs must carry the `/c/<slug>/` prefix (middleware
   skips `/api/`, creating a dual-path problem — Lesson 109). Data queries must filter by the
   community's identity/photo set; cross-community reads are allowed only where designed
   (compare/matching, Lesson 108 — never filter confirmed_list by community there).
6. **Fail closed.** If a community-scope lookup fails, return an EMPTY set for non-default
   communities. Never cache `None`/failure states that mean "skip filtering" (Lesson 151).
7. **Canonical mutation path.** Use canonical save functions + write an `app/audit.py` audit_log
   row for identity mutations. No direct `.save()` in handlers (Lesson 48).

## Verification gates (before commit)
1. `pytest tests/test_permissions.py tests/test_route_permissions.py -q` — the route×auth matrix
   (anonymous / user / admin) covers your new/changed routes; if not, ADD matrix rows.
2. `pytest tests/test_community_prefix_audit.py -q` — prefix regression guard.
3. Grep gate on your diff: every new `@rt(...POST...)` handler body contains an auth or origin
   guard within its first ~15 lines, or a written justification comment for why it is public.
4. HTMX gate: no `RedirectResponse` returned from an auth guard on an HTMX endpoint.
5. For refactors/extractions: verify re-exports — grep each moved symbol for external importers
   (`grep -rn "from app.main import" app/ tests/`); Session 140's total auth outage came from 7
   dropped re-exports surviving 50 sessions of local-green tests.

## Sweep mode (periodic audit)
Enumerate write routes: `grep -n 'methods=\[\|@rt(' app/*routes*.py app/main.py | grep -iv get`.
For each, record: guard present? origin check? rate limit (public only)? community filter?
Report unguarded routes as findings with file:line; distinguish "verified missing" (you read the
handler) from "risk" (pattern-match only). Check `app/onboarding_routes.py`-style feature-flagged
routes actually gate the WRITE handlers, not just the page render.

## Anti-patterns (hard NOs)
- Adding a POST route with no guard "because it's internal/admin-page-only" — the URL is public.
- Returning 303 from auth guards on HTMX endpoints.
- Caching scope-lookup failures; failing open on non-default communities.
- Testing only the happy path — the matrix is route × {anonymous, user, admin} (Lesson 15).
- Assuming middleware handles `/api/` prefixes — it skips them by design (Lesson 109).
- Browser-clicking data-mutating buttons on production to "test" a route (Lesson 149 — READ-ONLY).
