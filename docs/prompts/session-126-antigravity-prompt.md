# Session 126 Antigravity — Delight & Visual Polish

You are making CSS/template improvements to a heritage photo archive app (Rhodesli). The app uses FastHTML + HTMX + Tailwind CSS with a dark theme (slate-900 background, indigo/amber accents).

## YOUR FILES (only modify these)
- `app/page_routes.py` — landing page, collections, timeline, about
- `app/person_routes.py` — individual person pages, face gallery, photo grid

## DO NOT TOUCH
- `app/main.py`, `app/cluster_review_routes.py`, `app/browse_routes.py`, `app/identity_routes.py` — owned by Claude Code
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

## DELIVERABLES

### 1. Person Page Face Gallery (PRIORITY 1)
The face gallery on person pages (showing all photos of a person) should feel like a curated exhibit:
- Masonry-style or responsive grid layout for face photos
- Subtle hover effect: slight scale + shadow + photo metadata overlay
- Click to expand in a lightbox-style modal
- Photos sorted by quality/date with best photo prominent

### 2. Micro-Interactions (PRIORITY 2)
Add CSS transitions that make the app feel alive:
- Card hover: `transform scale-[1.02]` with `shadow-lg` transition
- Badge hover: gentle glow effect via `ring-2 ring-indigo-400/50`
- Button press: `active:scale-95` for tactile feedback
- Skeleton shimmer animation for loading states (use `@keyframes shimmer`)

### 3. Empty States (PRIORITY 3)
When sections have no content, show something better than blank:
- Collections page with no collections: "No collections yet" with a subtle illustration-style border pattern
- Timeline with no dates: "Timeline builds as dates are discovered" with a dotted timeline graphic (CSS only)

### 4. Typography Refinement (PRIORITY 4)
- Section headings: larger, more editorial (`text-3xl font-serif tracking-tight`)
- Stat numbers: `tabular-nums` for consistent width
- Photo captions: `text-sm italic text-slate-400`

## CONSTRAINTS
- CSS and HTML template changes ONLY — no Python logic changes
- All changes must work with existing HTMX swap patterns
- Dark theme only (no light mode)
- Test by reading the rendered HTML — don't run the app
- Commit to branch `session-126/antigravity-delight`

## COMMIT
```
git checkout -b session-126/antigravity-delight
# make changes
git add app/page_routes.py app/person_routes.py
git commit -m "[antigravity] style(ux): session 126 — delight pass (gallery, transitions, empty states)"
```

Write your audit findings to `docs/session_context/session-126-antigravity-delight-audit.md` before implementing.
