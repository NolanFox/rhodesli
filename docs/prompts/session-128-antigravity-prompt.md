# Session 128 Antigravity — Person Page + Cluster Review Visual Polish

You are making CSS/template improvements to a heritage photo archive app (Rhodesli). The app uses FastHTML + HTMX + Tailwind CSS with a dark theme (slate-900 background, indigo/amber accents).

## CRITICAL: Branch First
```bash
git checkout -b session-128/antigravity-polish
```
**YOU MUST BE ON THIS BRANCH BEFORE ANY EDITS.** Verify with `git branch --show-current`. DO NOT commit to main.

## YOUR FILES (only modify these)
- `app/person_routes.py` — individual person detail pages
- `app/cluster_review_routes.py` — admin speed-run / cluster review UI

## DO NOT TOUCH
- `app/main.py`, `app/browse_routes.py`, `app/estimate_routes.py`, `app/page_routes.py`, `app/identity_routes.py` — owned by Claude Code
- `core/` — frozen
- `data/` — frozen, never modify
- `tests/` — don't touch existing tests
- Never use `--no-verify` on commits
- Never remove `_check_admin` calls or change route paths
- Never change Supabase queries or auth guards
- Never change Python logic — CSS and HTML template ONLY

## DESIGN LANGUAGE
- **Colors**: indigo-600 (primary), amber-500 (CTA/highlight), emerald-500 (confirmed/success), slate-700/800 (cards/borders)
- **Typography**: `font-serif` for headings, `font-sans` for body. Editorial museum feel.
- **Shapes**: `rounded-2xl` for avatars, `rounded-lg` for cards, `rounded-xl` for panels
- **Transitions**: `transition-all duration-300` on interactive elements
- **Active states**: `active:scale-95` on buttons for tactile feedback
- **Hover**: `hover:scale-[1.02] hover:shadow-lg` on cards
- **Focus**: `focus:ring-2 focus:ring-indigo-400 focus:outline-none` on interactive elements

## DELIVERABLES

### 1. Person Page Polish (PRIORITY 1) — `app/person_routes.py`
The `/person/{id}` page should feel like a museum exhibit card:
- Face crop: larger display with subtle shadow + `rounded-2xl`
- Life details (Born/Died/From): cleaner typography, `tabular-nums` for years
- Photo appearances section: card hover with scale + shadow
- "Can you help?" CTA (already added Session 127): ensure it has warm styling, maybe a soft gradient background
- Annotation section: improve spacing, add subtle dividers
- "Similar Identities" panel: face crop zoom on hover, distance badges aligned

### 2. Speed-Run / Cluster Review Polish (PRIORITY 2) — `app/cluster_review_routes.py`
The admin review UI should feel snappy and professional:
- Current identity card: more prominent, clear visual hierarchy
- Action buttons (Confirm/Skip/Reject): larger touch targets with `active:scale-95` feedback
- "Up Next" queue: thumbnail hover with gentle zoom
- Keyboard shortcut indicators: subtle styling, not competing with actions
- Status badges: consistent pill style with `rounded-full`
- Match suggestions: face crops with hover zoom, distance as colored badge

### 3. Shared Patterns
- Ensure `transition-all duration-200` on ALL buttons in both files
- All face crops: `rounded-2xl object-cover`
- All cards: `hover:shadow-lg hover:border-slate-600`
- All badges: `rounded-full px-2 py-0.5 text-xs font-medium`

## WHAT WORKED IN PREVIOUS SESSIONS
- Session 125: blue→indigo sweep, rounded-2xl avatars, aspect-square — clean, consistent
- Session 126: lightbox on person pages — good UX addition
- What works: CSS-only changes, hover effects, typography, spacing, rounded corners
- What doesn't work: changing Python logic, modifying data files, touching auth

## CONSTRAINTS
- CSS and HTML template changes ONLY — no Python logic changes
- All changes must work with existing HTMX swap patterns
- Dark theme only (no light mode)
- Test by reading the rendered HTML — don't run the app
- Keep all existing functionality working — if in doubt, don't change it

## COMMIT
```bash
git checkout -b session-128/antigravity-polish  # MUST DO FIRST
# make changes
git add app/person_routes.py app/cluster_review_routes.py
git commit -m "[antigravity] style(ux): session 128 — person page + cluster review polish"
```
