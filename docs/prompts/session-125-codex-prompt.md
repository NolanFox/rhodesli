# Codex Performance + UX Fixes — Session 125

You are fixing 5 contained bugs/performance issues. Each fix is in a SEPARATE file. Do them one at a time.

## ABSOLUTE CONSTRAINTS

1. **ONLY modify these files**: `app/perf_cache.py`, `app/browse_routes.py`, `app/identity_routes.py`
2. **DO NOT modify**: `app/main.py`, `app/cluster_review_routes.py`, `app/page_routes.py`, `app/person_routes.py`, `app/compare_routes.py`, `core/*`, `data/*`
3. **DO NOT use `--no-verify`** — if pre-commit hooks fail, fix the issue.
4. **DO NOT modify any file in `data/`** — these are production data files.
5. **Set `DATA_SOURCE=json`** when running tests.
6. **Branch name**: `session-125/codex-fixes`
7. **Create branch first**: `git checkout -b session-125/codex-fixes`
8. **Create a single test file**: `tests/test_session_125_codex.py`
9. **Run tests before committing**: `source venv/bin/activate && export DATA_SOURCE=json && pytest tests/test_session_125_codex.py -x -q`
10. **Single commit** with all fixes when done.

## Fix 1: PERF #8 — perf_cache Redundant Registry Reload
**File:** `app/perf_cache.py`
**Problem:** After `_rebuild_matrix()` loads the registry to build the confirmed identity matrix, `get_confirmed_distances()` (around line 136) calls `load_registry()` AGAIN to look up identity names/metadata. This is redundant — the matrix rebuild already accessed the registry.
**Fix:** During `_rebuild_matrix()`, also cache a `_confirmed_metadata` dict mapping `identity_id → {name, face_count, best_face_id}`. Then `get_confirmed_distances()` reads from `_confirmed_metadata` instead of calling `load_registry()` again.
**Test:** Verify `_confirmed_metadata` is populated after rebuild. Verify `get_confirmed_distances` doesn't need a fresh `load_registry()` call.

## Fix 2: UX-114 — Collection Dropdown Fragility
**File:** `app/browse_routes.py`
**Problem:** Collection filter dropdown uses `onfocus="this.select()"` which is fragile with keyboard navigation.
**Fix:** Remove the `onfocus` handler. Use a proper `placeholder` attribute on the select/input instead. Search for `onfocus` in `browse_routes.py` and replace with a clean pattern.
**Test:** Verify no `onfocus="this.select()"` remains in browse_routes.py.

## Fix 3: FB-157 — Identity Cards Missing Clickable Links
**File:** `app/browse_routes.py`
**Problem:** Identity cards in manual search results have no clickable link to the person page.
**Fix:** Find identity card rendering in browse_routes.py. Wrap the thumbnail and name in an `A()` tag linking to `f"{nav_prefix}/person/{identity_id}"`. Make sure `nav_prefix` is available (check how other routes in the file get it).
**Test:** Verify identity card HTML contains an `href` to `/person/`.

## Fix 4: FB-158 — Manual Search Missing Distance Score
**File:** `app/browse_routes.py`
**Problem:** When browsing similar identities, no distance/confidence score is shown (unlike the similar panel which shows "83% match").
**Fix:** If distance data is available in the search results, render a confidence badge. Use the same `_confidence_badge()` pattern from cluster_review_routes (or create a simple inline version). If distance data is NOT available in browse results, skip this fix and note why.
**Test:** If implemented, verify confidence badge renders in search results.

## Fix 5: FB-163 — Community Badge on Tag Search Results
**File:** `app/identity_routes.py`
**Problem:** Tag search results show identities from all communities without any community indicator.
**Fix:** Find the tag search result rendering. Add a community badge (small colored pill) showing which community the identity belongs to. Use `_main_mod._get_identity_community()` or similar to look up the community.
**Test:** Verify community badge renders in tag search results.

## Output

When all fixes are done and tests pass:
```bash
git add app/perf_cache.py app/browse_routes.py app/identity_routes.py tests/test_session_125_codex.py
git commit -m "perf+fix: session 125 codex — PERF #8, UX-114, FB-157, FB-158, FB-163"
```

DO NOT push to main. Leave on the `session-125/codex-fixes` branch.

---

## Part 2: Design Audit Review (after fixes above)

After completing the 5 fixes, do a design/UX audit of the codebase. Read through the route files and write your findings to `docs/session_context/session-125-codex-design-audit.md`.

For each route file, evaluate:
1. **Visual consistency** — Do face cards, badges, buttons look the same across different views?
2. **Information hierarchy** — Is the most important info (photos, names) prominent? Is metadata secondary?
3. **Mobile usability** — Are touch targets large enough? Any horizontal overflow risks?
4. **Dead ends** — Can users always navigate forward/backward? Any orphan pages?
5. **Admin vs public** — Is it clear what's admin-only? Are admin tools cluttering public views?

Files to review:
- `app/page_routes.py` (landing, browse, about)
- `app/person_routes.py` (person detail, face gallery)
- `app/compare_routes.py` (face compare tool)
- `app/cluster_review_routes.py` (speed-run triage)
- `app/admin_routes.py` (admin dashboard)
- `app/browse_routes.py` (browse/search)

Output format for each file:
```markdown
## [filename]
### Good
- [what works well]
### Issues (ranked by impact)
1. [P1] [issue] — suggested fix: [specific CSS/HTML change]
2. [P2] [issue] — suggested fix: [specific change]
### Consistency gaps
- [element X in this file doesn't match element X in other_file.py]
```

Add this audit file to your commit:
```bash
git add docs/session_context/session-125-codex-design-audit.md
git commit --amend --no-edit
```
