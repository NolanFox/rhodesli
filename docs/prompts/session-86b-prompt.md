# Session 86b Prompt: Route Extraction + Deferred UX Fixes

## Context
Session 86 shipped UX-037/039, face labels, connected navigation, MLS evaluation, and Gemini completion.
It deferred the monolith split (only app/utils.py extracted) and all compare/estimate UX fixes because
the routes stayed in app/main.py. This session completes that work.

**Predecessor**: Session 86 (v0.89.0, commit 19455af)
**Version target**: v0.89.0 → v0.90.0

## Scope — Three Workstreams

### WS1: Extract Compare + Estimate Routes from main.py
### WS2: Fix Remaining UX Bugs (UX-038, UX-053, UX-056, UX-057)
### WS3: Browser-Verify Session 86 Deferred Items + New Work

## Pre-Session Verification (Act 0)
Before doing ANY new work, verify Session 86's shipped features in the browser with Claude Chrome
(admin is logged in). These were only curl-verified last session:

1. Navigate to any /person/ page for a CONFIRMED identity → verify action bar (Timeline, Map, Tree, Connections, Compare)
2. Click a Merge button on the neighbor sidebar → verify hx_confirm dialog appears with both identity names
3. Navigate to /person/ page as admin → verify inline admin controls (rename, confirm/skip/reject, merge search)
4. Navigate to any /photo/ page → verify face overlay labels visible for confirmed faces
5. Open an incognito window (or check as non-admin) → face overlays should still be visible

Save screenshots to docs/screenshots/session-86b/. If ANY of these fail, fix them BEFORE proceeding.

## Execution Plan

### Act 1: Route Extraction (compare + estimate)

**Goal**: Extract ~10,000 lines from app/main.py into app/compare_routes.py and app/estimate_routes.py.

**Architecture**:
- Cache variables (`_photo_cache`, `_face_data_cache`, `_face_to_photo_cache`, `_comparison_results_cache`,
  `_date_labels_cache`, `_birth_year_cache`) STAY in app/main.py
- Cache-building functions (`_build_caches()`, `get_face_data()`, `load_registry()`, `get_crop_files()`,
  `_load_date_labels()`, `_get_birth_year()`) STAY in app/main.py
- Route modules import from app.main — one-way dependency, no circular imports
- app/main.py imports route modules at END of file: `from app import compare_routes, estimate_routes`
- The `rt` decorator and `app` object are passed to route modules or imported from main

**Extraction order** (each step: move code, update imports, run tests, commit):

1. **app/compare_routes.py** — Move all `/compare/*` and `/api/compare/*` routes (lines 16295-25956).
   Include helper functions: `_compare_result_card()`, `_compare_results_grid()`, `_queue_compare_upload_for_review()`,
   `_save_compare_upload()`, `_build_compare_results_view()`, `_compare_photo_with_overlays()`,
   `_save_comparison_result()`, `_generate_result_id()`, `_resolve_crop_url()`.
   Also move: `_comparison_results_cache` variable and its load function.

2. **app/estimate_routes.py** — Move `/estimate` and `/api/estimate/*` routes (lines 21427-21940).
   Include helpers: `_call_gemini_date_estimate()`.

**Critical invariant**: `make test-fast` must pass after EACH extraction step. If tests break,
fix imports before proceeding. Common issues:
- Tests importing helpers from `app.main` that moved to route modules → update test imports
- Route registration order changing → FastHTML is order-sensitive for overlapping paths
- Mock patches targeting `app.main._xxx` that need to target `app.compare_routes._xxx`

**Commit**: `refactor(app): extract compare + estimate routes from main.py`

### Act 2: Fix UX-038 — Merged Identity Validation

**Current state**: GET /person/{id} redirects to canonical identity (line 11259-11261), but POST operations
(confirm, reject, skip, merge, discovery/confirm) silently succeed on merged-away identities.

**Fix**:
1. Create a helper function in app/main.py:
   ```python
   def _check_merged_identity(identity_id: str, registry) -> tuple[bool, str | None]:
       """Returns (is_merged, canonical_id) — use to guard POST identity operations."""
       identity = registry.get_identity(identity_id)
       if identity and identity.get("merged_into"):
           return True, identity["merged_into"]
       return False, None
   ```

2. Add this check to ALL POST routes that accept an identity_id parameter:
   - `/api/discovery/confirm`
   - `/api/identity/{identity_id}/skip`
   - `/api/identity/{identity_id}/reject-match/{neighbor_id}`
   - `/api/identity/{target_id}/merge/{source_id}`
   - `/api/identity/{identity_id}/rename`
   - `/api/identity/{identity_id}/confirm-state`
   - Any other POST route that modifies an identity

3. When merged, return an HTMX response that redirects to the canonical identity:
   ```python
   if is_merged:
       return HttpHeader("HX-Redirect", f"/person/{canonical_id}")
   ```

4. Tests: merged identity POST → gets HX-Redirect header, not 200

**Commit**: `fix(identity): UX-038 — POST operations on merged identities redirect to canonical`

### Act 3: Fix UX-053/056/057 — Estimate Upload Polish

**These are in app/estimate_routes.py after extraction.**

**UX-053 — No photo preview in estimate upload results**:
- The `/api/estimate/upload` handler returns text-only results
- Fix: Include the uploaded photo as an `<img>` in the response HTML
- The photo should be saved temporarily and served via a temp URL

**UX-056 — No CTAs after estimate upload**:
- After showing the date estimate result, add action buttons:
  - "Try Another Photo" → resets the form
  - "Share Estimate" → copy link / Web Share API
  - "View Similar Photos" → link to /photos filtered by estimated decade

**UX-057 — File input doesn't reset**:
- After successful upload and result display, reset the file input
- Use HTMX afterSwap event or hyperscript: `_on htmx:afterSwap from #estimate-upload-result reset() the closest <form/>`

**Note**: UX-045/046 (compare loading + auto-scroll) were found to be ALREADY FIXED in the research phase.
The compare workspace has `show:` in its hx_swap. Verify this in browser during Act 5 — if it's not working,
fix it then.

**Commit**: `fix(estimate): UX-053/056/057 — photo preview, CTAs, and form reset on upload`

### Act 4: Tests

Write tests for ALL new/changed behavior:
- Route extraction: existing tests still pass (this is the main gate)
- UX-038: POST to merged identity returns HX-Redirect
- UX-038: POST to non-merged identity works normally
- UX-053: Estimate upload response contains `<img>` tag
- UX-056: Estimate upload response contains "Try Another" and "Share" CTAs
- UX-057: Estimate upload response triggers form reset (check for hyperscript/HTMX directive)

Run BOTH test suites:
```bash
source venv/bin/activate && pytest tests/ -x -q
source venv/bin/activate && pytest rhodesli_ml/tests/ -x -q
```

**Commit**: `test: session 86b — merged identity redirect, estimate upload polish`

### Act 5: Browser Verification with Claude Chrome

Navigate through the full user journey for every change. Admin is logged in.

**Compare verification**:
1. Go to /compare → upload a photo → verify loading spinner appears
2. After results load → verify page auto-scrolls to results
3. Try the "Compare with a person" flow → search works, results display

**Estimate verification**:
4. Go to /estimate → upload a photo → verify loading spinner
5. After result loads → verify uploaded photo preview visible
6. Verify "Try Another Photo" and share CTAs present
7. Click "Try Another Photo" → file input should be cleared

**Merged identity verification (UX-038)**:
8. Find a merged identity (search for one, or check identities.json for `merged_into`)
9. Try to access /person/{merged_id} → should redirect to canonical
10. Via browser console or direct fetch: POST to an identity endpoint with merged ID → should get HX-Redirect

**Session 86 re-verification**:
11. /person/ page action bar present
12. Merge confirmation dialog appears
13. Admin controls on person page
14. Face overlay labels on photo page

Save ALL screenshots to docs/screenshots/session-86b/.

### Act 6: Assessment + Final Docs

- Write docs/assessments/session-86b-assessment.md
- Write docs/sessions/SESSION_086b.md
- Update SESSION_LOG.md, ROADMAP.md, CHANGELOG.md, BACKLOG.md
- Mark UX-038, UX-053, UX-056, UX-057 as FIXED in BACKLOG.md and UX_ISSUE_TRACKER.md
- Update BACKLOG.md header (version, test count)
- Update SESSION_HISTORY.md with session 86b entry

## Key Files

| File | Purpose | Modified By |
|------|---------|-------------|
| app/main.py (35812 lines) | Source — routes extracted OUT | Act 1 |
| app/compare_routes.py (NEW) | Compare routes (~9600 lines) | Act 1 |
| app/estimate_routes.py (NEW) | Estimate routes (~500 lines) | Act 1, Act 3 |
| app/main.py | UX-038 merged identity guard | Act 2 |
| tests/ | New + updated tests | Act 4 |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Import breakage after extraction | Run `make test-fast` after EACH file move. Fix imports immediately. |
| Test mocks targeting old paths | Search for `patch("app.main._compare` etc. and update to new module |
| Route registration order | FastHTML registers routes in import order. Import route modules at end of main.py |
| Cache access from extracted modules | Caches stay in main.py as globals. Route modules import them. One-way dependency. |
| HTMX endpoint paths change | They don't — only Python module paths change, not URL paths |
| Flaky xdist tests | Pre-existing, not introduced by this session. Document if seen. |

## Constraints
- `core/neighbors.py` is FROZEN — do not modify
- No ML model changes — this is pure web/UX work
- Budget: $0 API cost (no Gemini calls needed)
- Commit after EVERY act
- /clear between acts
- Run BOTH test suites before every commit
