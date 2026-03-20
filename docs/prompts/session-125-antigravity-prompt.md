# Antigravity Comprehensive Design Audit + Implementation — Session 125

## Context
Rhodesli is a heritage photo archive for the Jewish Community of Rhodes. It uses ML face recognition to help community members identify people in historical photos. FastHTML + HTMX + Tailwind CSS (CDN runtime). Dark theme (slate-900 background). ~2000 Facebook group members, 1 admin.

**Stack:** FastHTML (Python → HTML), HTMX for interactions, Tailwind CSS via CDN. No React. No build step.
**Live site:** https://rhodesli.nolanandrewfox.com

## ABSOLUTE CONSTRAINTS — READ THESE FIRST

1. **DO NOT touch `data/` files** — these are production data. Not even for testing. Not even to read.
2. **DO NOT use `--no-verify`** on any git commit.
3. **DO NOT modify**: `core/*`, `data/*`, `scripts/*`, `rhodesli_ml/*`
4. **DO NOT change database queries, Supabase calls, or data loading logic.** If a function loads data from Supabase, do not change the query. You may change how the RESULT is displayed.
5. **DO NOT change route paths** (the URL patterns). You may change what the route RETURNS.
6. **DO NOT change authentication or permission logic.** `_check_admin()` calls must remain.
7. **Set `DATA_SOURCE=json`** when running tests: `export DATA_SOURCE=json`
8. **Branch**: `git checkout -b session-125/antigravity-ux`
9. **Test before commit**: `source venv/bin/activate && export DATA_SOURCE=json && pytest tests/ -x -q --ignore=tests/e2e/ -n auto`
10. **Single commit** when done. Do NOT push to main.

## What You CAN Change
- CSS classes (Tailwind)
- HTML structure and element hierarchy
- Text content and labels
- HTML attributes (title, aria-label, data-*, placeholder)
- Element ordering within a container
- Adding new HTML elements for visual purposes (badges, tooltips, dividers)
- Hover states, transitions, animations via Tailwind
- Responsive breakpoints (sm:, md:, lg:)

## Your Mission

You are doing a **comprehensive design audit and implementation** across the ENTIRE app. For every route file, review the visual output and implement improvements. The goal: make this look like a polished, modern heritage archive — not a developer tool or AI demo.

### Design Principles
1. **Heritage dignity** — This is a Holocaust-era community archive. Warm, respectful, not clinical.
2. **Consistency** — Every face card looks the same everywhere. Every badge looks the same. Every action button follows the same pattern.
3. **Modern & smooth** — Transitions, hover states, proper spacing. Look at Google Photos, FamilySearch, Apple Photos for inspiration. Adapt their patterns to our dark theme.
4. **Mobile-first** — Most users arrive from Facebook on phones. Touch targets ≥44px. No horizontal overflow.
5. **Information hierarchy** — Most important info is biggest and first. Metadata is secondary. Admin tools are tucked away.

---

## PRIORITY 1: Face Card Grid Redesign (person_routes.py)

**This is the #1 complaint.** The current face gallery on person pages is terrible:
- Tiny crops that are hard to see
- Quality labels ("Good quality") waste space and look ugly
- Clicking a face does nothing useful
- No way to compare faces side-by-side
- Looks like a debug output, not a photo gallery

**What good looks like:** Google Photos "People" view — clean grid of face crops, click one and it expands inline showing the source photo with the face highlighted, smooth transitions.

**Your implementation (in `app/person_routes.py`):**

1. **Face grid**: Use `grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2` with `aspect-square` crops. Remove quality labels from the grid view — they add no value for the user.

2. **Face crop styling**: Each crop should be `rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-amber-400 transition-all`. Clean border, no text below individual crops. The face itself should be the hero.

3. **Source labels**: If source/collection info is shown, make it a subtle overlay at the bottom of the crop (gradient fade, small text), not a separate element below.

4. **Pagination**: The "1-8 of 80" pagination at bottom — if it exists, style it properly with consistent button styling.

5. **Admin metadata** (quality scores, face IDs): Hide behind a "Show details" toggle or remove entirely from the grid. Admin can see this in other views.

---

## PRIORITY 2: App-Wide Component Consistency

Read EVERY route file listed below. For each, identify and fix inconsistencies.

### Files to audit (read the FULL file, not just first 800 lines):

**`app/page_routes.py`** — Landing pages, photo browse, about page
- Landing page hero: is the typography consistent with heritage feel?
- Photo grid cards: consistent border radius, hover state, spacing
- About page: does it have proper navbar? Consistent with other pages?
- CTA phrasing: unify all calls-to-action ("Do you recognize anyone?" everywhere)

**`app/person_routes.py`** — Person detail pages
- Face gallery (PRIORITY 1 above)
- Person header: name, status badge, metadata layout
- "Often appears with" section: consistent card styling with main grid
- Similar identities panel: consistent with face cards
- Status badges: CONFIRMED (green), PROPOSED (amber), INBOX (slate) — add tooltips everywhere

**`app/identity_routes.py`** — Identity management, tagging
- Tag search results: add community badges
- Name editing: consistent input styling
- Merge/split UI: clear action hierarchy

**`app/compare_routes.py`** — Face comparison tool
- Upload area: consistent with other upload surfaces
- Results grid: match cards should look like face cards elsewhere
- Confidence badges: same style as speed-run confidence

**`app/admin_routes.py`** — Admin dashboard, approvals
- Approval cards: consistent layout, face thumbnails visible
- Audit trail: clean table or card layout
- Action buttons: consistent with speed-run buttons

**`app/cluster_review_routes.py`** — Speed-run triage
- Already has kbd shortcuts and good button styling
- Check: are the proposal cards consistent with identity cards on person pages?
- Check: enrichment panel layout — is merge search discoverable?

**`app/browse_routes.py`** — Browse/search views
- Identity card styling: consistent face crop + name + metadata
- Search results: clean, scannable layout

### Consistency Checklist (apply to ALL files):

| Element | Standard | Where to check |
|---------|----------|---------------|
| Face crop | `rounded-lg aspect-square object-cover` | person_routes, browse, cluster_review, compare |
| Status badge | Green=CONFIRMED, Amber=PROPOSED, Slate=INBOX, with tooltip | person_routes, browse, admin |
| Community badge | Small pill with community name | identity_routes, browse, compare |
| Action button (primary) | `px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-lg font-medium transition-colors` | ALL admin surfaces |
| Action button (danger) | `px-4 py-2.5 bg-red-600 hover:bg-red-500 rounded-lg font-medium transition-colors` | ALL admin surfaces |
| Card container | `bg-slate-800/60 border border-slate-700 rounded-xl p-4` | ALL card-like elements |
| Hover on clickable | `hover:ring-2 hover:ring-amber-400/50 transition-all` | face crops, cards |
| Touch target | Minimum `py-2.5 px-4` on mobile | ALL buttons |

---

## PRIORITY 3: External Tools Consistency

The standalone tools (/tools/compare, /tools/estimate) should feel like the same app but with a "tools" identity — slightly different header, but same components.

Check:
- Does the compare tool upload area match the admin upload area?
- Do result cards match the person page face cards?
- Is there consistent navigation back to the main archive?

---

## Output

### Save your audit findings AND changes to:
`docs/session_context/session-125-antigravity-full-audit.md`

Format for each route file:
```markdown
## [filename]

### Issues Found
1. [Issue]: [description] — [FIXED / NEEDS LOGIC CHANGE / DEFERRED]

### Changes Made
- Line NNN: [what changed and why]
```

### Save a summary to:
`docs/session_context/session-125-antigravity-results.md`

### Commit:
```bash
git add -A  # Only because you're on a branch, not main
git commit -m "feat(ux): session 125 antigravity — comprehensive design audit + implementation

- Face card grid redesign on person pages
- Component consistency across all route files
- Status badge tooltips, community badges, CTA unification
- Touch target compliance, hover states, transitions"
```

**DO NOT push to main.** Leave on `session-125/antigravity-ux` branch.
