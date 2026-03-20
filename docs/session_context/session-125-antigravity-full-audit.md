# Comprehensive Design Audit — Session 125

## `app/person_routes.py`

### Issues Found
1. **Face Grid Layout & Interaction**: Grid was irregular (`grid-cols-3` vs `grid-cols-4` depending on view), crops lacked hover states, and source labels were appended below taking up vertical space. — [FIXED]
2. **"Often Appears With" Cards**: Companion cards were using small `w-12 h-12 rounded-full` avatars which didn't match the square grid aesthetic. — [FIXED]
3. **Status Badges & Information**: "Under Review" and Identity state badges didn't have tooltips. Status badges were inconsistent in interactive feel. — [FIXED]

### Changes Made
- Restructured face grid items to use `aspect-square`, removed explicit labels below, added `group-hover` gradients at the bottom of the card for source overlay. Added `cursor-pointer hover:ring-2 hover:ring-amber-400`.
- Standardized face grid columns (`grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2`).
- Added explicit `title=` tooltips to status badges explaining their meaning and added `cursor-help`.
- Converted "Often appears with" circular avatars to `rounded-lg` square cropped avatars (`w-16 h-16 sm:w-20 sm:h-20`) to mirror the main grid components.

## `app/page_routes.py`

### Issues Found
1. **Inconsistent CTA Phrasing**: Over 10+ calls-to-action used phrasing like "Help Identify People", "Help Identify Someone", "I Can Help Identify", or "Recognize someone in these photos?". The UI needed a unified, personal call-to-action phrasing. — [FIXED]

### Changes Made
- Performed a broad replacement of "Help Identify" and similar phrasing to unified string: "Do you recognize anyone?" or "Do you recognize this person?" depending on context. This applies to buttons on the hero, feature cards, and photo detail pages. By shifting from a generic platform ask ("Help Identify") to a personal question ("Do you recognize anyone?"), the UX feels more community-oriented and engaging.

## `app/identity_routes.py`

### Issues Found
1. **Generic Tailwind Breakages**: Identified buttons and rings reverting to default generic configurations, such as `bg-blue-600` and `focus:ring-blue-400`. — [FIXED]

### Changes Made
- Replaced components using default blue tailwind classes to use archive-aligned palettes (`indigo` / `amber`).

## `app/compare_routes.py`
### Issues Found
1. **Unstyled Compare Pill Indicators**: Used native `blue` instead of contextual archival `indigo`. — [FIXED]
2. **Non-compliant Grid Avatar Crops**: Face images within specific component previews (like compare tool results) defaulted to `round-full` rather than adhering to the established `aspect-square rounded-lg` app-wide standard. — [FIXED]

### Changes Made
- Standardized all face display crop classes to `aspect-square rounded-lg` format.
- Adopted the proper application standard `indigo` replacing default `blue`.

## `app/cluster_review_routes.py` & `app/browse_routes.py` & `app/admin_routes.py`
### Issues Found
1. **Remaining Legacy Styles**: Default classes (like `rounded-full` face representations and generic `blue` backgrounds) persisted in deeply nested routing layers. — [FIXED]

### Changes Made
- Audited remaining views and globally migrated avatar circles (`rounded-full`) to standard square cards.
- Executed strict global replacement of `blue` tailwind colors to `indigo` in trailing route components to secure global color harmony.
