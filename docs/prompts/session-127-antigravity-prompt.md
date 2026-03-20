# Session 127 Antigravity — Browse & Estimate Visual Polish

You are making CSS/template improvements to a heritage photo archive app (Rhodesli). The app uses FastHTML + HTMX + Tailwind CSS with a dark theme (slate-900 background, indigo/amber accents).

## CRITICAL: Branch First
```bash
git checkout -b session-127/antigravity-polish
```
**YOU MUST BE ON THIS BRANCH BEFORE ANY EDITS.** Session 126 Antigravity committed to main — that was wrong. Verify with `git branch --show-current`.

## YOUR FILES (only modify these)
- `app/browse_routes.py` — people grid, photo grid, browse pages
- `app/estimate_routes.py` — date estimator tool

## DO NOT TOUCH
- `app/main.py`, `app/person_routes.py`, `app/page_routes.py`, `app/cluster_review_routes.py`, `app/identity_routes.py` — owned by Claude Code
- `core/` — frozen
- `data/` — frozen, never modify
- `tests/` — don't touch existing tests
- Never use `--no-verify` on commits
- Never remove `_check_admin` calls or change route paths

## DESIGN LANGUAGE
- **Colors**: indigo-600 (primary), amber-500 (CTA/highlight), emerald-500 (confirmed/success), slate-700/800 (cards/borders)
- **Typography**: `font-serif` for headings, `font-sans` for body. Editorial museum feel.
- **Shapes**: `rounded-2xl` for avatars, `rounded-lg` for cards, `rounded-xl` for panels
- **Transitions**: `transition-all duration-300` on interactive elements
- **Active states**: `active:scale-95` on buttons for tactile feedback
- **Hover**: `hover:scale-[1.02] hover:shadow-lg` on cards

## DELIVERABLES

### 1. People Grid Cards (PRIORITY 1)
The people grid (`/people`) cards should feel more interactive:
- Card hover: subtle scale + shadow + border highlight
- Face crop: gentle zoom on hover (`group-hover:scale-105`)
- Name text: slightly brighter on hover
- Photo count: use `tabular-nums` for consistent alignment

### 2. Estimate Tool Polish (PRIORITY 2)
The `/tools/estimate` page should feel more premium:
- Form inputs: consistent `rounded-lg` with `focus:ring-indigo-400`
- Result card: add subtle entrance animation (fade-in or slide-up)
- Upload dropzone: more prominent dashed border, hover state
- Stats/confidence: `tabular-nums`, slight glow on high confidence

### 3. Photo Grid Enhancement (PRIORITY 3)
The `/photos` browse page:
- Photo cards: hover overlay with subtle gradient + photo title
- Masonry-like appearance via `columns-2 sm:columns-3 md:columns-4` if applicable
- Loading skeleton shimmer while photos load

## CONSTRAINTS
- CSS and HTML template changes ONLY — no Python logic changes
- All changes must work with existing HTMX swap patterns
- Dark theme only (no light mode)
- Test by reading the rendered HTML — don't run the app

## COMMIT
```bash
git checkout -b session-127/antigravity-polish  # MUST DO FIRST
# make changes
git add app/browse_routes.py app/estimate_routes.py
git commit -m "[antigravity] style(ux): session 127 — browse grid + estimate polish"
```

Write your audit findings to `docs/session_context/session-127-antigravity-audit.md` before implementing.
