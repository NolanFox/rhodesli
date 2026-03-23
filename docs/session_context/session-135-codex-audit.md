# Session 135 — Independent Code Quality & Security Audit of Session 134

**Tool:** Claude Opus 4.6 (independent audit agent)
**Strategy:** Fresh review of all Session 134 diffs, no prior context from Session 134
**Date:** 2026-03-22

## Scope
All files changed between commits `c80d7a8` (Session 133 end) and `8deea62` (Session 134 end).

---

## Findings

### Finding 1: `_sanitize_postgrest_value` allows single quotes — potential SQL fragment injection
- **Severity:** P2
- **File:** `app/nl_query_executor.py:24`
- **Description:** The regex `[^a-zA-Z0-9 '\-]` preserves single quotes. While PostgREST parameterizes queries server-side, allowing `'` in `.or_()` filter strings could interact with PostgREST's own string literal parsing (`source.ilike.%O'Brien%`). The `.or_()` filter syntax uses `.` as a delimiter and PostgREST may interpret unbalanced quotes. This is LOW risk in practice because PostgREST rejects malformed filters with a 400 error rather than executing them, but it merits investigation.
- **Recommended fix:** Escape or strip single quotes from PostgREST filter strings. Use `_escape_ilike` on values within `.or_()` strings too, or switch to `.ilike()` chaining (which is parameterized) instead of `.or_()` with inline filter strings.

### Finding 2: Location/photo_type filters silently dropped on temporal queries
- **Severity:** P3
- **File:** `app/nl_query_executor.py:188`
- **Description:** When a temporal filter is present (`decade`, `year`, etc.), location and photo_type filters are silently ignored. A query like "wedding photos from the 1940s" would only filter by decade, not by "wedding." The comment acknowledges this ("skip gracefully") but no user feedback is given. Users will get unexpected results.
- **Recommended fix:** Either (a) apply location/photo_type as post-fetch Python filters on the temporal results, or (b) include a message in the response noting that combined temporal+location filters are not yet supported.

### Finding 3: `/login/modal` endpoint lacks rate limiting
- **Severity:** P2
- **File:** `app/auth_routes.py:188-195`
- **Description:** Session 134 added rate limiting to POST `/login` (10/hr) and POST `/signup` (5/hr), but POST `/login/modal` (the HTMX modal login) has no rate limiting. An attacker could brute-force credentials through this endpoint, bypassing the rate limit on the main login form.
- **Recommended fix:** Add the same `check_rate_limit(client_ip, max_per_hour=10)` check to `/login/modal`. The endpoint needs to accept `request=None` to extract the IP.

### Finding 4: `/forgot-password` endpoint lacks rate limiting
- **Severity:** P2
- **File:** `app/auth_routes.py:406-428`
- **Description:** POST `/forgot-password` sends password reset emails but has no rate limit. An attacker could trigger thousands of Supabase password reset emails, causing email delivery costs and potential abuse. The anti-enumeration message is good, but rate limiting is still needed.
- **Recommended fix:** Add `check_rate_limit(client_ip, max_per_hour=5)` to `/forgot-password` POST.

### Finding 5: `save_registry` JSON serialization accesses `registry._identities` without snapshot
- **Severity:** P3
- **File:** `app/main.py:1700-1704`
- **Description:** The old code used `deepcopy` to snapshot the registry before the background write. The new code serializes with `json.dumps` synchronously, which avoids the thread-safety issue for the write. However, `json.dumps` iterates over `registry._identities` — if another ASGI request modifies the dict during serialization (e.g., dict resizing from a concurrent confirm), `json.dumps` could raise `RuntimeError: dictionary changed size during iteration`. In practice, Python's GIL makes this unlikely in a single-worker uvicorn setup, but it's not guaranteed safe in multi-worker or async contexts.
- **Recommended fix:** This is acceptable given the current single-worker deployment and the fact that this is a non-critical backup path. Document the assumption. If moving to multi-worker, revisit.

### Finding 6: `dense_faces_layout` variable is now dead code
- **Severity:** P3
- **File:** `app/page_routes.py:11412`
- **Description:** `dense_faces_layout = len(face_info_list) >= 7` is defined but no longer used after the grid layout change. The old CSS classes `.person-strip` and `.person-grid` (lines 11846-11858) are also dead code.
- **Recommended fix:** Remove `dense_faces_layout` assignment and the `.person-strip` / `.person-grid` CSS rules.

### Finding 7: Rate limit tests only test the `check_rate_limit` function, not the route integration
- **Severity:** P3
- **File:** `tests/test_auth.py:182-211`
- **Description:** The rate limit tests in `TestSecurityAuditFixes` call `check_rate_limit()` directly, verifying the rate limiter works. But no test verifies that `/login` POST actually returns 429 when rate-limited, or that `/tools/search` returns the rate-limit div. The fixture `reset_rate_limits` in conftest.py resets limits between tests, which is correct, but integration coverage is missing.
- **Recommended fix:** Add at least one integration test that hits the actual route endpoint 11+ times and asserts the 429 response.

### Finding 8: `_escape_ilike` does not escape backslash
- **Severity:** P3
- **File:** `app/nl_query_executor.py:33`
- **Description:** The `_escape_ilike` function escapes `%` and `_` but not `\` (backslash). In PostgreSQL ILIKE, backslash is the escape character. A search term containing `\` could interfere with the escape sequences. For example, searching for `test\` would produce `%test\%` where `\%` is interpreted as a literal `%` by Postgres, breaking the ILIKE pattern.
- **Recommended fix:** Add `value.replace("\\", "\\\\")` as the first replacement in `_escape_ilike`.

### Finding 9: Pre-existing — `_query_gedcom_search_candidates` has incomplete PostgREST sanitization
- **Severity:** P2 (pre-existing, not Session 134)
- **File:** `app/relationship_routes.py:944`
- **Description:** The GEDCOM search function only escapes commas (`term.replace(",", r"\,")`) in user-supplied search terms before passing them to `.or_()` filter strings. Dots and parens are NOT escaped, which could alter PostgREST filter logic. This is the same class of vulnerability as Session 134's Finding 1 but in a different file. Session 134 added `_sanitize_postgrest_value` only to `nl_query_executor.py`.
- **Recommended fix:** Apply `_sanitize_postgrest_value` (or equivalent) to GEDCOM search terms. Move the sanitization function to a shared utility module.

### Finding 10: Responsive grid may display poorly for 1-2 face photos
- **Severity:** P3 (UX, not security)
- **File:** `app/page_routes.py:12620-12622`
- **Description:** All photos now use `grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3`, replacing the previous conditional layout (strip for <7 faces, grid for 7+). Photos with 1-2 faces will show cards in a sparse grid with significant empty space. This is a deliberate UX change (FB-009) but may not look optimal for portrait photos with a single face.
- **Recommended fix:** Consider `grid grid-cols-1 sm:grid-cols-2` for photos with fewer than 4 faces, or `flex flex-wrap` for more natural wrapping.

---

## Summary

| # | Finding | Severity | Category | New/Pre-existing |
|---|---------|----------|----------|------------------|
| 1 | Single quotes in PostgREST sanitizer | P2 | Security | New (S134) |
| 2 | Location/type filters dropped on temporal queries | P3 | Correctness | New (S134) |
| 3 | `/login/modal` lacks rate limiting | P2 | Security | Pre-existing, gap in S134 fix |
| 4 | `/forgot-password` lacks rate limiting | P2 | Security | Pre-existing, gap in S134 fix |
| 5 | `json.dumps` on live dict (theoretical race) | P3 | Thread safety | New (S134) |
| 6 | Dead code: `dense_faces_layout` + old CSS | P3 | Code quality | New (S134) |
| 7 | Rate limit tests are unit-only, no integration | P3 | Test coverage | New (S134) |
| 8 | `_escape_ilike` misses backslash | P3 | Security | New (S134) |
| 9 | GEDCOM search has same `.or_()` injection risk | P2 | Security (pre-existing) | Pre-existing |
| 10 | Sparse grid for 1-2 face photos | P3 | UX | New (S134) |

## Overall Code Quality Assessment

**Session 134 changes are SOLID.** The security fixes (open redirect, rate limiting, PostgREST sanitization, ILIKE escaping) are well-implemented. The `save_registry` optimization is correct and avoids the thread-safety pitfalls of the old approach. Test coverage for the new sanitization functions is thorough.

**Key gaps:** Rate limiting was applied inconsistently — main login/signup got it but modal login and forgot-password were missed. The PostgREST sanitization was applied to `nl_query_executor.py` but the same vulnerability exists in `relationship_routes.py` (pre-existing). The `_escape_ilike` function is missing backslash escaping.

**Recommendations for immediate action (P2):**
1. Add rate limiting to `/login/modal` and `/forgot-password`
2. Backslash-escape in `_escape_ilike`
3. Apply PostgREST sanitization to GEDCOM search (pre-existing)

**No P0 findings.** No data loss, corruption, or critical security risks identified.
