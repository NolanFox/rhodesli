# W4 — Code-Quality + Bug-Recall Sweep (route monoliths, no edits)

**Synthesis of** `subagents/w4-auth-csrf.md` + `subagents/w4-scoping-reads.md` (full file:line proof
there). Read-only. Defect classes: auth/CSRF, community-scoping leaks, stale-JSON in postgres mode,
cached-failure states, silent Supabase writes, request-path ML, `_main_mod` coupling.

**Health baseline (credit first):** ~110 admin write routes correctly `_check_admin`-gate; SameSite=Strict
cookies cover all cookie-authed CSRF; sync routes token-gated; `/create-archive` flag+auth+throttle+caps
is well-built; request-path ML is the sanctioned AD-114 lightweight path, not an AD-110 violation
(**class e: 0 defects**); all 222 `_main_mod` attrs currently resolve (**class f: 0 live defects**).

## VERIFIED DEFECTS (airtight code-path proof) — 6

| ID | Class | File:line | Route | Failure | Why tests miss |
|----|-------|-----------|-------|---------|----------------|
| A-VD1 | auth (rate-limit) | `app/auth_routes.py:214` | `POST /login/modal` | Sibling of `/login` (10/hr) calls the **same** credential verifier with **no throttle** → unlimited credential-stuffing bypasses brute-force protection | `test_rate_limit.py` unit-tests the function, asserts nothing about which routes wire it |
| A-VD2 | auth (rate-limit) | `app/auth_routes.py:432` | `POST /forgot-password` | No throttle on reset-email send → email-bomb a victim / burn Supabase auth-email quota (ties to Free-tier fragility, Lesson 200) | No test exercises `/forgot-password`; "always success" design hides abuse |
| S-V1 | scoping (a) | `app/browse_routes.py:1647-1744`, `:167-199` | `/collections`, `/collection/{slug}` | `_get_collections_data()` takes no community arg → `/c/fox-family/collections` shows Rhodes collections + exposes every photo of another community's collection; OG copy hardcoded "Rhodes-Capeluto" | `test_community_prefix_audit.py` greps `href=` patterns only — can't see a data-scoping gap |
| S-V2 | scoping (a) | `app/components/photo_analysis.py:939,528` | community photo viewer | AI face-card link → root `/person/{id}`; tag pill → root `/photos?tag=` → exits community context (Lesson 109 whack-a-mole). **Confirmed live** on `/c/rhodes/people` DOM (W2 V2-4) | audit test globs `*_routes.py` only; `app/components/` never scanned |
| S-V3 | scoping+cache (a+c) | `app/browse_routes.py:290-293`, `:685-687` vs `app/main.py:968-980` | `/photos`, `/api/photos/more` | Photos grid fails **OPEN** on Supabase blip (`if community_photo_ids is not None`) → renders full multi-community corpus. Identity path fails closed; photos path does not (Session 136's fail-closed claim only half-true) | no test simulates `load_photos_for_community → None` asserting empty grid |
| S-V4 | stale-read+silent-write (b+d) | `app/engagement_routes.py:760-794`; `app/person_routes.py:2311-2331` | person comments | `_load_person_comments` has no postgres branch → reads volume JSON only + memoizes forever; write dual-writes Supabase but it's never read back (AD-232 survivor). Write `except:` unlinks temp, no re-raise/log → comment silently lost while page shows it posted | comment tests hit local-JSON happy path; none run postgres-mode + failing write |
| S-V5 | cached-failure (c) | `app/supabase_data.py:1620-1639`, TTL `:1563`; `app/main.py:796-806` | CommunityMiddleware | `get_community_by_slug` caches `None` on transient error → whole `/c/<slug>/` archive hard-404s for up to 300s from one 500ms blip (Lesson 151 anti-pattern, fail-closed direction = availability outage) | middleware tests cover slug-missing → 404; none distinguish "raised" (must not cache) |

## RISK FINDINGS (credible, not reproduced — missing evidence + settling test) — 7

| ID | Class | File:line | Risk | Missing evidence / settling test |
|----|-------|-----------|------|----------------------------------|
| A-RF1 | public-write caps | `app/engagement_routes.py:1052,1193` | `/api/annotations/submit` + `guest-submit` have **no rate limit AND no length cap** (only `.strip()`) → unauthenticated storage-exhaustion DoS; admin-approval renders bloat | No live exploit / upstream body-cap measured (Railway/CF may blunt). XSS likely mitigated by FT auto-escape but every render site needs a targeted pass |
| A-RF2 | auth throttle | `app/auth_routes.py:557,676,702` | `/reset-password`, `/auth/session`, `/auth/exchange-code` unthrottled — but each needs a valid high-entropy secret → no takeover, only Supabase-API amplification | No confirmed abuse yielding takeover; defense-in-depth only |
| S-R1 | stale-JSON (b) | `app/identity_routes.py:559-570`, `browse_routes.py:173-184` | `_get_collections_data` JSON fallback fires `if not photos` → if a Supabase outage yields an EMPTY registry, serves stale volume `photo_index.json` (Lesson 133/144 masking) | Whether `load_photo_registry()` returns empty vs raises not traced. Test: postgres + mock `list_photos()→[]` + populated JSON; assert empty render. Also dedupe the two copies |
| S-R2 | cached-failure (c) | `app/engagement_routes.py:540-545`; `app/relationship_routes.py:83-87,147-151` | Empty-default cached on Supabase failure for full TTL → annotations/GEDCOM-matches/relationship panels silently vanish (data loss, no leak) | Test: mock fail-then-succeed within TTL; assert 2nd request returns data (currently returns cached empty) |
| S-R3 | scoping staleness (a) | `app/main.py:880,901-902,963-964` | Single shared `_community_ids_cache_ts` for both caches + all communities, refreshed on every miss → community B's set can stay stale far past 600s TTL → new photos/tags invisible in scoped views | Test: populate A, advance 599s, populate B (refresh ts), repeat; assert A refetched after its own 600s |
| S-R4 | pagination (b-adjacent, Lesson 173) | `app/relationship_routes.py:75,139` | `gedcom_matches` + `relationships` loaders use `.select().execute()` with no `.range()` loop → silent truncation the day either crosses 1000 rows (matches ≈282 today = latent) | Structural grep-test: every request-path `.select` paginates or documents a row-count bound |
| S-R5 | `_main_mod` guard gap (f) | `tests/test_main_mod_references.py:20` | Test globs `*_routes.py` only; `app/perf_cache.py` + `app/components/*` unguarded for Session-140-class breakage (Lesson 157). AST sweep confirms **no live defect today** | Fix: change test file-list to "every .py under app/ containing `_main_mod.`" |

## Highest-leverage fixes (ranked)
1. **S-V3** (photos grid fail-open) + **S-V1** (collections unscoped) — active cross-community
   **data leaks**, the project's most-repeated bug class. Both bypass the prefix-audit test by design.
2. **A-VD1 + A-VD2** — two unthrottled public auth endpoints; small diffs, real abuse surface.
3. **S-V4** — silent comment loss + AD-232 survivor (Supabase written, never read).
4. **A-RF1** — public annotation writes uncapped; storage-DoS on an anonymous endpoint.

## Coverage appendix
- **Fully swept:** `auth_routes`, `engagement_routes`, `sync_routes`, `onboarding_routes`,
  `admin_rhodes_inbox_routes`, `browse_routes`, `person_routes`, `relationship_routes` (loaders),
  `supabase_data` (community fns), `components/photo_analysis.py`, `main.py` middleware/caches/404,
  `test_community_prefix_audit.py`, `test_main_mod_references.py`.
- **Partially swept (grep + spot reads):** `page_routes.py` (13k lines, not end-to-end),
  `identity_routes`, `compare_routes`, `estimate_routes`, `match_facecompare_routes`, `photo_routes`,
  `admin_routes`, `cluster_review_routes`, `discoveries_routes`.
- **NOT swept:** stored-XSS render-site pass for annotation `value`/`reason`; IDOR / cross-community
  authorization (admin of A writing to B — different threat class); `gedcom_*`, `rhodes_inbox.py`,
  `nl_query_executor.py`, `core/` beyond ML-import grep, `rhodesli_ml/`.
