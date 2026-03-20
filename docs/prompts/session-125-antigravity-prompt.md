# Antigravity UX Quick Wins — Session 125

## Context
Rhodesli is a heritage photo archive for the Jewish Community of Rhodes. FastHTML + HTMX + Tailwind CSS (CDN runtime). Dark theme (slate-900 background).

## ABSOLUTE CONSTRAINTS — READ BEFORE DOING ANYTHING

1. **ONLY modify these files**: `app/page_routes.py`, `app/person_routes.py`
2. **DO NOT modify**: `app/main.py`, `app/cluster_review_routes.py`, `app/browse_routes.py`, `app/identity_routes.py`, `app/admin_routes.py`, `app/compare_routes.py`, `core/*`, `data/*`, `tests/e2e/*`
3. **NO logic changes** — CSS classes, text content, HTML attributes ONLY. Do not change conditionals, function signatures, data queries, or route handlers.
4. **NO `--no-verify`** — if hooks fail, fix the issue or skip the commit.
5. **DO NOT touch `data/` files** — these are production data. Not even for testing.
6. **Set `DATA_SOURCE=json`** when running tests: `export DATA_SOURCE=json`
7. **Branch name**: Work on a branch called `session-125/antigravity-ux`
8. **Create branch first**: `git checkout -b session-125/antigravity-ux`
9. **Tests**: Create `tests/test_session_125_antigravity.py` with assertions for your changes
10. **Run tests before committing**: `source venv/bin/activate && export DATA_SOURCE=json && pytest tests/test_session_125_antigravity.py -x -q`

## Your Tasks (3 items)

### Task 1: UX-081 — About Page Navbar Consistency
**File:** `app/page_routes.py`
**Problem:** The about page may be missing navigation elements present on other pages (Tools link, community links).
**What to do:**
1. Find the about page route (search for `/about` or `def about`)
2. Compare its navbar/header structure to the landing page
3. If missing nav elements, add them to match the standard pattern
4. If already consistent, document that it's fine — do nothing

### Task 2: UX-106 — Inconsistent CTA Phrasing
**File:** `app/page_routes.py`
**Problem:** Some contribution CTAs say "Do you know this person?" while others say "Can you help identify?". The language should be unified.
**What to do:**
1. `grep -n "Do you know\|Can you help\|Know this person\|help identify" app/page_routes.py`
2. Pick ONE phrasing (prefer: "Do you recognize anyone?") and update all instances
3. Also check `app/person_routes.py` for the same inconsistency
4. Only change TEXT content — do not alter any Python logic, conditionals, or function calls

### Task 3: UX-107 — "Identified" Badge Missing Tooltip
**File:** `app/person_routes.py`
**Problem:** The green "Identified" badge on person pages has no tooltip explaining what it means.
**What to do:**
1. Find the "Identified" or "CONFIRMED" badge element (search for `Identified` or `CONFIRMED` in badge context)
2. Add a `title` attribute: `title="This person has been confirmed by an admin"`
3. Also check for "Proposed" and "Inbox" badges — add appropriate tooltips
4. Only change HTML attributes — do not alter logic

## Output Format

Save a summary of what you changed to `docs/session_context/session-125-antigravity-results.md`:
```markdown
# Antigravity Results — Session 125

## Changes Made
- [x/skip] UX-081: [what you did or why you skipped]
- [x/skip] UX-106: [what you did]
- [x/skip] UX-107: [what you did]

## Files Modified
- app/page_routes.py: [lines changed]
- app/person_routes.py: [lines changed]
```

Commit your changes:
```bash
git add app/page_routes.py app/person_routes.py tests/test_session_125_antigravity.py docs/session_context/session-125-antigravity-results.md
git commit -m "feat(ux): session 125 antigravity — UX-081, UX-106, UX-107 quick wins"
```

DO NOT push to main. Leave on the `session-125/antigravity-ux` branch. Claude Code will merge after review.
