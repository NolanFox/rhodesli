# VERDICT: SHIP-WITH-FIXES

Independent audit of `git diff 92bdeeb6..HEAD -- app/ tests/`.

## Findings

### P2 — `/photos` fail-closed still emits global corpus metadata

`app/browse_routes.py:268-277` computes global decade/tag counts and optional global search results before the scope-failure guard runs at `app/browse_routes.py:304-307`. Even when the photo grid correctly stays empty, those counts are rendered at `app/browse_routes.py:449-455` and `app/browse_routes.py:465-483`.

I verified the route behavior with a simulated `/c/fox-family/photos` scope failure: no photo card, collection, or lazy sentinel leaked, but patched global `1950s (1)` and `secret tag (1)` filter pills still rendered. That is a smaller leak than the original full-corpus photo leak, but it is not fully fail-closed.

Fix: compute `_scope_failed = _community_scope_failed(...)` immediately after `community_photo_ids` is loaded. If true, skip `_get_decade_counts()`, `_get_tag_counts()`, and `_search_photos()`, force `decade_counts = {}`, `tag_counts = {}`, `photos = []`, `collections = []`, and render no lazy sentinel. Add a route-level regression asserting a scope-failed community page contains no cards, no sentinel, and no global decade/tag labels.

### P2 — non-Rhodes community lookup can still cache `None` when client acquisition fails

`app/supabase_data.py:1630-1637` no longer caches `None` on query exceptions, which fixes the tested transient `execute()` failure path. However `app/supabase_data.py:1609-1618` still caches `None` for every non-Rhodes slug whenever `get_supabase_client()` returns `None`. Because `get_supabase_client()` also returns `None` after client initialization exceptions (`app/supabase_data.py:69-72`), a configured production process with a transient client-init failure can still mark a real non-Rhodes archive as missing for the 300s cache TTL.

Fix: in the `if not sb:` branch, preserve the Rhodes default path, but only cache non-Rhodes `None` when Supabase is genuinely unconfigured. If `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are present but no client is available, return `None` without writing `_community_cache[slug]`. Add a regression for configured env + unavailable client asserting the slug is not cached.

### P3 — QW-1 tests cover the helper but not the serving routes

`tests/test_community_scope_failclosed.py:28-37` proves `_community_scope_failed()` distinguishes Supabase-present from Supabase-absent, but it does not exercise `/photos` or `/c/{slug}/api/photos/more`. The important security property is route output: no cards, no global metadata, and no next-page loop.

Fix: add integration tests with a prefixed community request, patched `load_photos_for_community()` returning `None`, patched `get_supabase_client()` returning an object, and a multi-community `_photo_cache`. Assert `/c/{slug}/photos` omits foreign filenames and omits `photos-lazy-sentinel`; assert `/c/{slug}/api/photos/more` returns an empty body.

## Checks Passed

- QW-1 distinguishes empty set from `None`: `app/browse_routes.py:46-47` treats any non-`None` scope, including `set()`, as normal filtering, so a real zero-photo community renders empty without entering the scope-failure branch.
- QW-1 pagination state is not half-built: with `_scope_failed`, `/photos` has `len(photos) == 0`, `total_pages == 0`, and no sentinel; `/api/photos/more` returns `""` at `app/browse_routes.py:754-755`.
- QW-2 rate-limit checks run before credential/email work: `/login/modal` checks before `login_with_supabase()` at `app/auth_routes.py:217-223`; `/forgot-password` checks before `send_password_reset()` at `app/auth_routes.py:444-448`.
- QW-2 throttled forgot-password avoids enumeration: the response remains HTTP 200 with the same generic message at `app/auth_routes.py:441-459`, and the reset email is not sent when the limiter denies the request.
- QW-3 genuine not-found caching remains intact at `app/supabase_data.py:1627-1629`; the changed query-exception path no longer writes `_community_cache[slug]`.

## Verification

- Ran `git diff 92bdeeb6..HEAD -- app/ tests/`.
- Confirmed live route registration resolves `/photos` and `/api/photos/more` to `app.browse_routes`.
- Ran targeted tests:
  `pytest tests/test_rate_limit.py::TestRateLimitedEndpoints::test_login_modal_blocks_11th_attempt tests/test_rate_limit.py::TestRateLimitedEndpoints::test_forgot_password_blocks_reset_send_on_6th_attempt tests/test_community_scope_failclosed.py tests/test_auth.py::TestCommunityCacheErrors -q`
  Result: `7 passed`.
