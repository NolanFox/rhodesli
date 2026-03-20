# Session 126 UX Consistency Audit

## Audit Scope
All route files in app/ that render HTML.

## Findings Fixed This Session

### P1: Color System — blue→indigo sweep
- **tools_routes.py**: 3 blue→indigo (nav active/inactive)
- **auth_routes.py**: 45 gray→slate (full auth page palette)
- **main.py**: 31 blue→indigo (buttons, badges, focus rings, confidence tiers)
- **discoveries_routes.py**: ~13 blue→indigo (confidence tiers, badges)
- **cluster_review_routes.py**: ~6 blue→indigo (badges, focus)
- **upload_routes.py**: ~6 blue→indigo (progress bars, borders)
- **identity_routes.py**: 1 focus:ring-blue→indigo
- **person_routes.py**: ~4 blue→indigo (badges, focus)

### P1: Auth Design System
- All `rounded` inputs → `rounded-lg` (13 instances)

## Findings Deferred to BACKLOG

### P2: Touch Targets
- cluster_review_routes badges `py-0.5` (16px) — should be `py-1`
- engagement_routes pagination `px-2 py-1` (28px)

### P2: Accessibility
- SVG icons in tools_routes, main.py, discoveries_routes lack aria-labels
- ~141 aria instances found vs ~1500+ interactive elements (~9% coverage)

### P3: Component Patterns
- Button padding inconsistency (`px-2 py-1` vs `px-3 py-1.5`)
- Mixed hover colors in discoveries_routes (standardize to indigo-300)
