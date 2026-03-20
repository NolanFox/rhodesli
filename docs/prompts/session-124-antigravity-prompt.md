# Antigravity Design Audit — Rhodesli Heritage Photo Archive

## Context
Rhodesli is a heritage photo archive for the Jewish Community of Rhodes. It uses ML face recognition to help community members identify people in historical photos. The core user loop is: Find face → Share → Community member recognizes → Responds → Admin merges.

**Stack:** FastHTML + HTMX + Tailwind CSS (CDN runtime). No React. Dark theme (slate-900 background).
**Users:** ~2000 Facebook group members, 1 admin (Nolan), occasional contributors.
**Live site:** https://rhodesli.nolanandrewfox.com

## Your Task
Review the codebase and produce actionable UX/design improvements. Focus on these files:

1. `app/page_routes.py` — Landing page, photo pages, browse views
2. `app/main.py` — Sidebar, navigation, shared components, CSS
3. `app/cluster_review_routes.py` — Speed-run triage UI
4. `app/person_routes.py` — Person detail pages
5. `app/compare_routes.py` — Face comparison tool

## Key Problems to Solve

### 1. Mobile Experience (HIGHEST PRIORITY)
Most users arrive from Facebook mobile links. Check:
- Viewport meta tag configuration
- Touch target sizes (minimum 44px)
- Text readability (minimum 16px body text)
- Horizontal overflow issues
- Navigation usability on small screens
- Photo grid responsiveness

### 2. Landing Page Visitor Journey
First-time visitors see photos but don't know what to do. We just added CTA buttons. Evaluate:
- Is the value proposition clear within 3 seconds?
- Are CTAs prominent enough?
- Does the page feel like a heritage archive or a tech demo?
- Suggested hero section / above-the-fold content

### 3. Speed-Run Triage Visual Hierarchy
Admin reviews 472 face matches. The current UI is dense. Evaluate:
- Face thumbnail size vs metadata ratio
- Action button prominence and spacing
- Enrichment panel layout (merge search → name → GEDCOM)
- Progress indicators
- Keyboard shortcut discoverability

### 4. Person Page Information Architecture
Person pages show: name, status, photos, metadata, admin tools, similar identities.
- Is the most important info (photos, identity status) above the fold?
- Are admin tools cluttering the public view?
- How should photo grids scale (5 photos vs 160 photos)?

### 5. Emotional Design
This is a HERITAGE archive, not a tech product. Families are discovering lost relatives.
- Color palette: is the dark theme appropriate for heritage content?
- Typography: does it convey dignity and history?
- Imagery: are photos displayed with respect and prominence?
- Microinteractions: do confirmations/merges feel meaningful?

## Output Format
Save your findings to `docs/session_context/session-124-antigravity-ux-audit.md` with:

```markdown
# Antigravity UX Audit — Session 124

## Priority 1: [Title] (File: [path], Line: [N])
**Problem:** [description]
**Fix:** [specific code change with Tailwind classes]
**Impact:** [what improves]

## Priority 2: [Title] ...
...
```

List at least 10 findings, ranked by impact. Include specific Tailwind CSS class suggestions and HTML structure changes where possible. Reference exact file paths and line numbers.

## Design References
- Google Photos: clean grid, prominent face crops, minimal chrome
- FamilySearch: warm tones, heritage feel, generous whitespace
- Apple Photos: person page with face collage, clean metadata
- MyHeritage: family tree integration, historical photo colorization feel
