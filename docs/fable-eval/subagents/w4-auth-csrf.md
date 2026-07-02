# W4 — Auth / CSRF Sweep of POST Routes & Public Write Surfaces

**Auditor**: Claude (Fable 5) read-only subagent · fresh context
**Scope**: All write routes (`def post|put|delete`) across `app/*.py`; guard presence in handler body; CSRF/rate-limit/token gates
**Date**: 2026-07-02
**Method**: AST-style enumeration of every `@rt(...)` / `@app.post(...)` decorated write handler (script), then per-handler read of the first ~60 body lines for `_check_admin` / `_check_login` / `_check_contributor` / `_check_origin` / `_check_sync_token` / `check_rate_limit`. 132 write handlers enumerated.

---

## Summary of the healthy majority (not itemized below)

- **~110 admin write routes** correctly call `_check_admin(sess)` as their first guard (identity, cluster-review, discoveries, events, relationships, photo metadata, gedcom admin, communities, ml-review, approvals, pending). Auth-matrix is intact for the admin surface.
- **CSRF**: `same_site="Strict"` is set on the session cookie (`app/main.py:270`) — this is the primary CSRF defense and it covers **every** cookie-authed route. `_check_origin` (Session 128) is layered on ~13 of the highest-impact mutation routes as defense-in-depth. Admin routes lacking `_check_origin` are **not** a CSRF hole given SameSite=Strict + the fact that all state-changing calls are HTMX `fetch()` (not navigations). Not itemized as findings.
- **Sync/machine routes** (`app/sync_routes.py` — `/api/sync/staged/clear`, `/mark-processed`, `/repair-upload`, `/push`) are all gated by `_check_sync_token(request)` (Bearer token vs `SYNC_API_TOKEN`, returns 503 if unconfigured, 401 on mismatch). Token validation is correct; path-traversal guards present in `staged/clear`. My classifier flagged these "UNGUARDED" only because the guard name wasn't in the keyword list — **false positives, verified safe.**
- **`/api/identity/{target}/suggest-merge/{source}`** — gated by `_check_contributor` (login+role). Safe (classifier false positive).
- **`/create-archive`** (`app/onboarding_routes.py:309`) — correctly gated: feature-flag `_self_service_enabled()` FIRST (default OFF via `SELF_SERVICE_ARCHIVE_ENABLED`), then auth gate, then IP throttle (10/hr), then length caps (`MAX_NAME_LEN`/`MAX_DESCRIPTION_LEN`/`MAX_CONTACT_LEN`) + email regex. The flag genuinely gates the WRITE. Well-built; no finding.
- **`/api/notifications/create`** — `_check_admin` gated (classifier initially confusing; verified admin-only). Safe.

---

## Verified defect

### VD-1 — `/login/modal` has NO rate limit; its sibling `/login` does
- **File**: `app/auth_routes.py:214`
- **Route**: `POST /login/modal` (public, unauthenticated by design)
- **Guard status**: none. `/login` (line 145) throttles `check_rate_limit(client_ip, max_per_hour=10)`; `/signup` (line 302) throttles at 5/hr. `/login/modal` calls the **same** credential verifier with **no throttle**:
  ```python
  @rt("/login/modal")
  async def post(email: str, password: str, sess):
      """Handle login from the modal context. Returns error text or HX-Refresh on success."""
      user, error = await _main_mod.login_with_supabase(email, password)   # ← no check_rate_limit
      if error:
          return error
      sess["auth"] = user
      return Response("", headers={"HX-Refresh": "true"})
  ```
- **Failure scenario**: An attacker performs unlimited password guesses / credential-stuffing against `/login/modal` (identical Supabase auth path as `/login`), completely bypassing the 10/hr brute-force protection that exists on `/login`. `grep -n 'rate_limit' app/auth_routes.py` confirms only lines 149 and 302 call the limiter.
- **Why tests miss it**: `tests/test_rate_limit.py` unit-tests the `check_rate_limit()` function in isolation and asserts nothing about which routes are wired to it. There is no route-level test asserting `/login/modal` is throttled, so the parallel unthrottled login endpoint is invisible.
- **Fix**: add the same `check_rate_limit(client_ip, max_per_hour=10)` guard (needs `request` param, currently absent from the signature) at the top of the handler.

### VD-2 — `/forgot-password` triggers reset emails with NO rate limit
- **File**: `app/auth_routes.py:432`
- **Route**: `POST /forgot-password` (public)
- **Guard status**: none. Handler calls the email-sending path unconditionally:
  ```python
  @rt("/forgot-password")
  async def post(email: str, sess):
      """Handle forgot password form."""
      success, error = await _main_mod.send_password_reset(email)   # ← no throttle, no request param
      # Always show success message to avoid email enumeration
  ```
- **Failure scenario**: Unbounded, unauthenticated triggering of Supabase password-reset emails. An attacker scripts thousands of `POST /forgot-password` with a victim's address (email bombing) or many addresses (burning the Supabase auth email quota → legitimate reset/OTP emails start failing; ties into the Free-tier fragility documented in Lessons 200). Enumeration is correctly mitigated (constant success message) but **volume** is not.
- **Why tests miss it**: no test exercises `/forgot-password` at all; `test_rate_limit.py` never references it. The "always success" design masks the abuse (no error surface to alert on).
- **Fix**: IP throttle (e.g. 5/hr) keyed on `client_ip` before `send_password_reset`; the handler must accept `request` to read `client.host`.

---

## Risk finding

### RF-1 — Public annotation writes have NO rate limit AND NO input length cap
- **Files**: `app/engagement_routes.py:1052` (`/api/annotations/submit`) and `:1193` (`/api/annotations/guest-submit`)
- **Routes**: intentionally-public community-contribution write surfaces (anonymous users allowed → `status="pending_unverified"`).
- **Guard status (correct expectation for public writes = rate limit + input caps)**: **both missing.**
  - `app/engagement_routes.py` does **not** import `check_rate_limit` (`grep` shows no reference); CommunityMiddleware skips `/api/` paths, so nothing throttles these.
  - `value` and `reason` are stored with only `.strip()` — **no length cap** anywhere before `_save_annotations()`:
    ```python
    "value": value.strip(),
    "reason": reason.strip() if reason else "",
    ```
    (guest-submit writes the record with zero size validation; submit only rejects *empty* values.)
- **Failure scenario**: An unauthenticated client scripts unbounded `POST /api/annotations/guest-submit` with megabyte-scale `value` strings → the annotations JSON store grows without limit (storage-exhaustion / DoS; also inflates every admin-approval page render and the Postgres annotation load at `:536`). No credential or token needed.
- **Evidence gap (why this is a Risk, not a Verified defect)**: I did not confirm a *live* exploit or a hard upstream body-size limit. Starlette/uvicorn impose no default form-field size cap, and I found no app-level cap, but I did not measure the practical ceiling (proxy/CDN limits at Railway/Cloudflare could blunt the largest payloads). The DoS is credible on the code path; the exact blast radius is unverified.
- **XSS sub-note**: rendered via FastHTML FT elements which auto-escape, so stored-XSS is *likely* mitigated — but `value`/`reason` flow into admin approval UI and `my-contributions`; a targeted review of every render site (esp. any `NotStr`/`Safe`/`to_xml` raw path) is warranted and out of this sweep's scope.
- **Why tests miss it**: `test_annotations.py` / `test_guest_annotations.py` assert functional happy-path submission, not size limits or throughput. No test asserts a cap on `value` length or a per-IP submission ceiling.
- **Fix**: add `check_rate_limit` (needs `request`) to both handlers + a `MAX_ANNOTATION_LEN` cap on `value`/`reason` (return 400 when exceeded), mirroring the caps already in `onboarding_routes.py`.

### RF-2 — Token-consuming auth endpoints unthrottled (lower severity)
- **Files/routes**: `app/auth_routes.py:557` (`POST /reset-password`), `:676` (`POST /auth/session`), `:702` (`POST /auth/exchange-code`).
- **Guard status**: no rate limit. Each, however, requires a **valid secret** to do anything: `reset-password` needs a valid `access_token`; `auth/session` needs a valid Supabase `access_token`; `exchange-code` needs a valid PKCE `code`. Invalid inputs fail fast without side effects.
- **Failure scenario**: brute-forcing these is low-value (the secrets are high-entropy Supabase tokens). Residual risk is amplification of Supabase auth-API calls (each `auth/session`/`exchange-code` hits Supabase). Worth a modest IP throttle for parity, but not an exploitable auth bypass.
- **Evidence gap**: no confirmed abuse path that yields account takeover; classified Risk purely as missing defense-in-depth throttling.
- **Why tests miss it**: same as above — no route-level throttle assertions.

---

## Coverage appendix

**Fully swept** (every write handler read for guards):
- `app/auth_routes.py` — all 7 POST routes.
- `app/engagement_routes.py` — all 7 POST routes (propose-match/accept/reject admin-guarded; 4 annotation routes analyzed).
- `app/sync_routes.py` — all 7 write routes (token validation confirmed at `:23`).
- `app/onboarding_routes.py` — `/create-archive` flag+auth+throttle+caps confirmed.
- `app/admin_rhodes_inbox_routes.py` — prod-404 gate (`is_rhodes_wiki_available()`) + `_check_admin` + `_check_origin` on both write routes confirmed.
- `app/notification_routes.py`, `app/compare_routes.py` (12 write routes: upload/select & pair/match are compute-only, no persistent mutation; facecompare/select saves a result unauthenticated but no user-data mutation), `app/estimate_routes.py`, `app/tools_routes.py` (`/tools/search` has `_check_origin`+rate_limit).

**Partially swept** (guard confirmed present via first-N-lines classifier; full body logic NOT deep-read):
- `app/identity_routes.py`, `app/cluster_review_routes.py`, `app/admin_routes.py`, `app/relationship_routes.py`, `app/photo_routes.py`, `app/page_routes.py`, `app/discoveries_routes.py`, `app/event_routes.py`, `app/person_routes.py`, `app/match_facecompare_routes.py` — all show `_check_admin`/`_check_login`/`_check_contributor` as first guard; I did not audit downstream community-scoping or IDOR (e.g. does `_check_admin` also bound the write to the caller's community? — out of scope for this auth/CSRF sweep).

**NOT swept**:
- Stored-XSS render-site review for annotation `value`/`reason` (flagged in RF-1; needs a dedicated output-encoding pass).
- IDOR / cross-community authorization (an admin of community A writing to community B) — different threat class; not part of the auth-presence mandate.
- `app/main.py` global routes (no `def post` write handlers found there; upload stream lives in `page_routes.py:9826`, rate-limited).
- WebSocket / SSE surfaces (none found among write routes).
