# W4 — Scoping / Stale-Reads / Cached-Failure / Silent-Writes / Request-ML / _main_mod Audit

**Auditor**: Claude (Fable 5), read-only sweep, 2026-07-02.
**Scope**: defect classes (a) community scoping, (b) stale-JSON in postgres mode, (c) cached
failure states, (d) silent Supabase write failures, (e) request-path heavy ML (AD-110),
(f) `_main_mod` coupling. Method: grep-driven + code-path reading (Lesson 38).

**Counts**: Verified — a:3, b:1, c:2, d:1, e:0, f:0. Risk — a:1, b:2, c:1, f:1. (V1 and V4
are dual-class a+c / b+d; counted once per primary class.)

---

## Verified defects

### V1 — `/collections` + `/collection/{slug}` are completely community-unscoped (class a)
- **Files**: `app/browse_routes.py:1647-1744` (`/collections`), `:1747+` (`/collection/{slug}`),
  helper `_get_collections_data()` at `app/browse_routes.py:167-199` (duplicated at
  `app/identity_routes.py:553-585`).
- **Proof**: `_get_collections_data()` takes NO community argument and iterates every photo in
  the registry (`photos = photo_reg.list_photos()`), grouping by `photo.get("collection")`.
  The `/collections` route (`browse_routes.py:1651-1654`) reads `community_slug` from
  `request.state` — but uses it ONLY for `nav_prefix`; the card loop at `:1658` renders every
  collection. `/collection/{slug}` (`:1754`) likewise renders every photo of any collection.
- **Failure scenario**: `/c/fox-family/collections` shows the Rhodes Capeluto collections (and
  vice versa) with preview thumbnails; the detail page exposes every photo of another
  community's collection. Nav from a community archive leaks the whole cross-community photo
  corpus. Also the OG copy at `:1706` is hardcoded "Rhodes-Capeluto family archive" on every
  community (same class Session 168 G1/G2 fixed for landing/help).
- **Why tests miss it**: `tests/test_community_prefix_audit.py` only greps for hardcoded
  `href=` PATTERNS — it cannot detect a data-scoping gap. No test asserts collection data is
  filtered by `_get_community_photo_ids` (compare COMMUNITY-001, which fixed "photos section"
  but never listed collections).

### V2 — Hardcoded root links inside `app/components/` escape the prefix-audit test (class a)
- **Files**: `app/components/photo_analysis.py:939` (`href=f"/person/{identity_id}"` in AI
  face-alignment cards) and `:528` (`href=f"/photos?tag={quote(t)}"` tag pills).
- **Proof**: `_build_ai_analysis_section(photo_id, is_admin)` /
  `_build_face_alignment_section(photo_id, is_admin)` have NO nav_prefix parameter (defs at
  `photo_analysis.py:109`, `:802`). They are rendered inside the community-prefixed photo
  viewer (`app/page_routes.py:4563-4565`) and the HTMX partial (`app/photo_routes.py:61`, `:318`).
- **Failure scenario**: on `/c/fox-family/photo/<id>`, clicking an AI tag jumps to root
  `/photos?tag=…` (Rhodes-scoped grid) and a face identity link jumps to root `/person/<id>` —
  exiting the community context (Lesson 109's exact whack-a-mole).
- **Why tests miss it**: the audit test globs `ROUTE_FILES_DIR.glob("*_routes.py")` —
  `app/components/` and `app/main.py` are never scanned. (Related low-priority sibling: the
  404 handler at `app/main.py:1539/:1545` links root `/photos` `/people`; defensible since a
  404 has no community context, but it drops users of a community archive into Rhodes.)

### V3 — Photos grid fails OPEN on transient Supabase failure; identities fail closed (class a+c)
- **Files**: `app/browse_routes.py:246` + `:290-293` (`/photos`), `:654` + `:685-687`
  (`/api/photos/more`); contrast `app/main.py:968-980`.
- **Proof**: `_get_community_photo_ids()` returns `None` on Supabase load failure
  (`app/main.py:913-917`, deliberately un-cached per Lesson 151, "caller decides whether to
  fail-open or fail-closed"). The identity-side caller fails CLOSED
  (`app/main.py:968-980` returns `set()` with a warning). But the photos grid does
  `if community_photo_ids is not None:` before filtering (`browse_routes.py:290`) — when
  `None`, NO filter is applied and every community's photos render.
- **Failure scenario**: during a Supabase blip (the exact Session 136 scenario), each request
  to `/c/fox-family/photos` renders the full multi-community photo corpus. Session 136's claim
  "community filtering fails closed when Supabase down" is true only for the identity path.
- **Why tests miss it**: `tests/` has fail-closed tests for `_get_community_identity_ids`
  (157b "community helpers fail-close"); no test simulates `load_photos_for_community → None`
  and asserts the `/photos` route renders an empty/errored grid rather than everything.

### V4 — Person comments: JSON-only read path in postgres mode + swallowed write failure (class b, d)
- **Files**: `app/engagement_routes.py:760-775` (`_load_person_comments`), `:778-794`
  (`_save_person_comments`); write route `app/person_routes.py:2311-2331`; renderer
  `app/person_routes.py:164`.
- **Proof (b)**: `_load_person_comments()` has NO `DATA_SOURCE == "postgres"` branch — it reads
  only `data_path/"person_comments.json"` and memoizes forever (`if _person_comments_cache is
  not None: return`). Meanwhile the write route dual-writes (JSON + `sync_person_comment` to
  Supabase, `person_routes.py:2327-2329`). Supabase rows are never read back — an AD-232
  survivor: Supabase is written as "source of truth" that nothing consumes; the UI's truth is
  the Railway volume JSON. Contrast `_load_annotations` (`engagement_routes.py:530-545`),
  which was properly converted.
- **Proof (d)**: `_save_person_comments` catches `except Exception:` and only `os.unlink`s the
  temp file — the original exception is NOT re-raised and no log is emitted
  (`engagement_routes.py:790-794`; contrast `_save_annotations` which re-raises at `:577-580`).
  The comment route then renders the success list from the in-memory dict — a visitor's
  comment can be silently lost on volume I/O failure while the page shows it posted (it
  survives only in Supabase, which per (b) is never read).
- **Why tests miss it**: comment tests exercise the happy path against local JSON; no test
  runs with `DATA_SOURCE=postgres` + empty volume and asserts Supabase comments render, and no
  test makes the JSON write raise and asserts an error surfaces.

### V5 — `get_community_by_slug` caches `None` on transient Supabase errors → whole community 404s for 5 min (class c)
- **Files**: `app/supabase_data.py:1620-1639` (except branch), TTL at `:1563` (300s);
  consumer `app/main.py:796-806` (CommunityMiddleware).
- **Proof**: in the `except _SUPABASE_ERRORS` branch, for any non-rhodes slug the function does
  `_community_cache[slug] = None; _community_cache_ts = now; return None`. The middleware then
  returns a hard 404 ("Community not found") for every `/c/<slug>/...` request
  (`main.py:800-806`) until the TTL expires. This is the literal Lesson 151 anti-pattern
  ("never cache failure states") — the direction here is fail-closed (availability outage, not
  a leak), but one 500ms Supabase blip takes a whole community archive offline for up to 300s
  and poisons `request.state.community` for every downstream scoping helper.
- **Why tests miss it**: community middleware tests cover slug-not-in-DB → 404; none distinguish
  "slug missing" (cache OK) from "Supabase raised" (must NOT cache). The `_get_community_photo_ids`
  fix (main.py:914 comment) shows the team knows the rule — this second cache was missed.

---

## Risk findings

### R1 — `_get_collections_data` JSON fallback serves stale volume photo_index in postgres mode (class b)
- **Files**: `app/identity_routes.py:559-570`, duplicate `app/browse_routes.py:173-184`.
- **Missing evidence**: fallback fires only `if not photos` after `photo_reg.list_photos()`.
  Whether a Supabase outage yields an EMPTY registry (triggering the fallback → stale JSON) vs
  a raised exception depends on `load_photo_registry()`'s failure mode, which I did not trace
  end-to-end. If it can return empty, this is the Lesson 133/144 fallback-masking pattern.
- **Settling test**: postgres mode + mock `load_photo_registry().list_photos() → []` + a
  populated `data/photo_index.json`; assert `/collections` does NOT render JSON-derived
  collections (should render empty), and assert only ONE implementation exists (the
  browse_routes/identity_routes duplication itself is drift waiting to happen).

### R2 — Empty-default caching on Supabase read failure blanks content for the full TTL (class c)
- **Files**: `app/engagement_routes.py:540-545` (annotations, 600s TTL at `:509`);
  `app/relationship_routes.py:83-87` (gedcom_matches) and `:147-151` (relationship graph, 300s).
- On transient failure these cache `default` (empty) and serve it for the TTL — annotations,
  GEDCOM matches, and relationship panels silently vanish. Not a scoping/security boundary
  (unlike Lesson 151's case), so risk-tier: data disappears, no leak. AD-232 mandates no JSON
  fallback but doesn't require caching the failure; a shorter negative-TTL (or no caching of
  the failure result, matching `_get_community_photo_ids`) settles it.
- **Settling test**: mock one failing then one succeeding Supabase read within TTL; assert the
  second request returns data (currently it returns the cached empty default).

### R3 — Shared `_community_ids_cache_ts` lets scoping sets stay stale far past TTL (class a, staleness)
- **Files**: `app/main.py:880` (single global ts), `:901-902`/`:937-938` (photo cache),
  `:963-964`/`:1020-1021` (identity cache).
- One timestamp is shared by BOTH caches and ALL communities, refreshed on every miss-write.
  Under steady multi-community traffic, community B's entry written long ago passes
  `now - ts < TTL and community_id in cache` indefinitely (ts keeps refreshing via A's writes).
  Newly uploaded photos / newly tagged identities can stay invisible in scoped views well past
  the 600s TTL. Staleness of a scoping boundary, not a leak (sets only grow).
- **Settling test**: populate community A, advance mock clock 599s, populate B (refreshing ts),
  advance repeatedly; assert A's entry is refetched after its own 600s.

### R4 — Lesson 173: unpaginated `.select().execute()` on gedcom_matches / relationships (class b-adjacent)
- **Files**: `app/relationship_routes.py:75` (`gedcom_matches`), `:139` (`relationships`).
- Supabase REST defaults to 1000-row pages; both loaders take `resp.data` with no `.range()`
  loop (contrast `load_annotations_from_supabase`, `supabase_data.py:1493`, and
  `load_photos_for_community`, `:1652-1665`, which paginate). GEDCOM matches ≈282 today, so
  latent — silent truncation the day either table crosses 1000 rows (the exact Lesson 173
  failure). Settling test: structural grep-test asserting every `sb.table(...).select` in
  request-path loaders either paginates or documents a hard row-count bound.

### R5 — `test_main_mod_references.py` doesn't cover `app/components/` or `app/perf_cache.py` (class f)
- **Files**: `tests/test_main_mod_references.py:20` (globs `*_routes.py` only); `_main_mod`
  users outside that glob: `app/perf_cache.py`, `app/components/{__init__,photo_analysis,modals,nav}.py`.
- I ran an AST sweep of every `_main_mod.<attr>` across app/ against `app/main.py` definitions:
  **all 222 distinct attrs currently resolve** (the only misses were false positives `app`
  — tuple-unpacked `fast_app()` — and `function_name` in a docstring). So no live defect; the
  Session 140-class breakage (Lesson 157) is simply unguarded for components/perf_cache.
- **Settling fix**: change the test's file list to "every .py under app/ containing `_main_mod.`".

---

## Class (e) — request-path ML: no verified defect
Public upload endpoints DO run face detection in the web worker
(`app/compare_routes.py:3129`, `:4277`; `app/estimate_routes.py:1205`;
`app/match_facecompare_routes.py:1410`; `app/page_routes.py:9876+` SSE flow), and production
ships `insightface==0.7.3` (`requirements.txt:18`, models pre-baked in `Dockerfile:30-39`), so
`has_insightface` guards pass in prod. However this is the sanctioned AD-114 lightweight
hybrid path (`extract_faces_hybrid`, buffalo_sc ~500M FLOPs) with rate limiting, and AD-229
explicitly deferred local-ML removal (TOOLS-002 Phase 5); AD-110's "heavy ML" ban targets the
archive/enrichment pipeline. Residual risk only: buffalo_sc→buffalo_l silent-fallback latency
(AD-120 instrumentation is the guard). `/health`'s in-request `import insightface`
(`page_routes.py:326-327`) is an availability probe — first-hit import cost only.

---

## Coverage appendix
- **Swept fully (grep + targeted reads)**: `app/main.py` (middleware, community scoping,
  404 handler, caches), `app/browse_routes.py`, `app/engagement_routes.py`,
  `app/person_routes.py` (comments, community detect), `app/relationship_routes.py` (loaders),
  `app/supabase_data.py` (community fns, loaders, sync stubs), `app/components/photo_analysis.py`,
  `app/event_routes.py` (write helpers), `app/audit.py`, `app/temporal_routes.py`,
  `tests/test_community_prefix_audit.py`, `tests/test_main_mod_references.py`.
- **Swept partially (grep + spot reads)**: `app/page_routes.py` (health, landing, photo viewer,
  SSE compare — 13k lines, not read end-to-end), `app/identity_routes.py` (except/pass sites,
  collections dup, neighbors filter), `app/compare_routes.py` (upload endpoints),
  `app/estimate_routes.py`, `app/match_facecompare_routes.py`, `app/photo_routes.py` (callers).
- **Grep-only**: `app/admin_routes.py`, `app/cluster_review_routes.py`,
  `app/discoveries_routes.py`, `app/upload_routes.py`, `app/tools_routes.py`,
  `app/sync_routes.py`, `app/notification_routes.py`, `app/onboarding_routes.py`,
  `app/components/{nav,modals,badges,cards}.py`.
- **Not swept**: `app/gedcom_*`, `app/rhodes_inbox.py`, `app/nl_query_executor.py`,
  `app/face_alignment.py`, `core/` (beyond ML-import grep), `rhodesli_ml/`.
