# W8 — Quick-Wins Queue (ranked patch plans — NO implementation)

For the **gated Phase 2 sprint** the orchestrator runs under full test gates + independent audit.
Nothing here is implemented, committed, or pushed. Each item: user impact, exact files, why it's
**outside the exclusion list**, acceptance tests, rollback, and provenance
(**new / already-logged / stale / synthesis** — no repackaging of existing BACKLOG items as new).

Ranked by (confidence × impact ÷ effort). All are small, reversible, test-gateable diffs.

## QW-1 — Photos grid fails OPEN on Supabase blip (cross-community data leak) — **synthesis (W4 S-V3)**
- **Impact:** High. During any Supabase flake, `/c/<slug>/photos` renders the **full multi-community
  corpus** (the identity path already fails closed; the photos path does not). This is the project's
  #1 bug class (cross-community leak, Lesson 151) live in code.
- **Files:** `app/browse_routes.py:290-293`, `:685-687` (mirror the fail-closed pattern at
  `app/main.py:968-980`).
- **Outside exclusions?** Yes — `browse_routes.py` is an ordinary route module (not global head/
  schema/frozen/`.claude`).
- **Acceptance tests:** new test simulates `load_photos_for_community → None` and asserts `/photos`
  + `/api/photos/more` render an **empty/errored** grid for a non-default community, not everything;
  existing prefix-audit tests stay green.
- **Rollback:** single-function revert; behavior is pure additive guard.
- **Provenance:** synthesis (not in BACKLOG as a verified leak; W4 confirms it).

## QW-2 — Two unthrottled public auth endpoints — **synthesis (W4 A-VD1/A-VD2)**
- **Impact:** High/Med. `POST /login/modal` hits the same credential verifier as `/login` with **no
  rate limit** (bypasses brute-force protection); `POST /forgot-password` can email-bomb a victim /
  burn the Supabase auth-email quota (ties to Free-tier fragility, Lesson 200).
- **Files:** `app/auth_routes.py:214` (`/login/modal`), `:432` (`/forgot-password`) — add
  `check_rate_limit(client_ip, ...)` mirroring `:149`/`:302`; both handlers need a `request` param.
- **Outside exclusions?** Yes — route module.
- **Acceptance tests:** route-level tests asserting the 11th `/login/modal` and 6th
  `/forgot-password` from one IP within the window are throttled; parity with `/login`/`/signup`.
- **Rollback:** remove the two guard lines.
- **Provenance:** synthesis (verified defects, not verbatim in BACKLOG).

## QW-3 — `get_community_by_slug` caches `None` → whole archive 404s for 5 min — **synthesis (W4 S-V5)**
- **Impact:** Med-High. One 500ms Supabase blip takes an entire `/c/<slug>/` archive offline for up
  to 300s (Lesson 151 anti-pattern; the team fixed the twin case at `main.py:914` but missed this one).
- **Files:** `app/supabase_data.py:1620-1639` — in the `except` branch, do **not** write
  `_community_cache[slug] = None`; return `None` without caching (retry next request).
- **Outside exclusions?** Yes — data-access module (not schema/migration; no DB writes).
- **Acceptance tests:** middleware test distinguishing "slug genuinely missing" (may cache) from
  "Supabase raised" (must NOT cache) → second request after a transient error resolves the community.
- **Rollback:** one-line revert.
- **Provenance:** synthesis.

## QW-4 — Rewrite the two `@`-imported architecture docs (JSON-canonical → Postgres-canonical) — **already-logged direction, new execution (W1 #5 / W3 stale-doc)**
- **Impact:** Med-High (compounding). `docs/architecture/DATA_MODEL.md` + `OVERVIEW.md` are
  `@`-imported by CLAUDE.md, so **every session loads a false "no relational database" architecture**
  that contradicts the "Postgres is source of truth" invariant three paragraphs above — the exact
  posture behind the deploy-overwrite lessons (56/69/78/141). Also refresh `PERMISSIONS.md` (upload
  is no longer admin-only).
- **Files:** `docs/architecture/DATA_MODEL.md`, `OVERVIEW.md`, `PERMISSIONS.md`. **Note:** these are
  docs OUTSIDE `docs/fable-eval/` → **excluded for THIS eval run**, but they are the orchestrator's
  to edit in Phase 2. Listed here because it's the single highest-leverage low-risk doc fix.
- **Acceptance tests:** none code; the doc-size-enforcement test (≤300 lines) must still pass; add a
  breadcrumb to AD-232/PRD-051.
- **Rollback:** git revert of doc commit.
- **Provenance:** already-logged as a health finding; execution is new. **Not for this run** — Phase 2.

## QW-5 — Add a favicon (kills a 404 on every page) — **new (W2 V2-10)**
- **Impact:** Low but universal + polish. `/favicon.ico` 404s on every page (console error);
  undermines the browser-tab + share-preview polish the project has invested in.
- **Files:** add a static `favicon.ico`/`favicon.svg` + a route or static mount (check how
  `app/static/` is served); one `<link rel="icon">` in the head builder.
- **Outside exclusions?** The head/layout is global — **touches the global head → route it as a
  User Decision / Phase-2 item**, not a same-run quick win. Flagged honestly.
- **Acceptance tests:** `GET /favicon.ico` returns 200; head contains the icon link.
- **Rollback:** remove the asset + link.
- **Provenance:** new.

## Explicitly NOT quick wins (need their own scoped work — do not smuggle in)
- **Public "Dismissed" badge leak** (W2 V2-1), **"Needs Name (0)" vs "131 awaiting"** reconciliation
  (V2-3), **archive "0 PEOPLE"** (V2-2/V2-5): each needs a product decision + multi-surface changes.
- **Nav low-contrast** (V2-6): global head/CSS — User Decision.
- **W3 VD-1/VD-2/R-2** (write-failure visibility + batch atomicity): correct but larger than a quick
  win; belongs in the data-integrity Phase-2 track with structural tests.
- **DETROIT-PROMOTE-167** (W6): NOT-READY, design + paid eval — not a quick win.

## Handoff note
QW-1, QW-2, QW-3 are the three highest-confidence, smallest-diff, highest-safety wins and all three
are **cross-community-leak or auth-hardening** — exactly the class where a silent regression is most
costly, so they belong FIRST in a gated sprint with the `route-safety-audit` + `split-brain-data-audit`
skills loaded and an independent audit before push.
