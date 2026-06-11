# Session 165 Context — Person-Scoped Photo Navigation + Shareable Person Gallery

**Predecessor:** [session-164-context.md](session-164-context.md) (GEDCOM redesign — site is LIVE again).
**Type:** UX bug fix + small feature (SDD: Part B needs a mini-PRD). **Date planned:** 2026-06-10.
**Reported by:** Nolan (live, incognito shared-link test). **Prior docs:** this is a known issue —
**FB-004 (Session 135): "Photo lightbox arrows cycle through all photos, not cluster photos" (P1, BACKLOG)**
and **Lesson 63 (Filters must be preserved across all navigation paths)**.

## The bug (reproduced by user)
1. Open a shared person link in incognito: `https://rhodesli.nolanandrewfox.com/c/fox-family/person/d74cb556-6d44-4288-ade3-1cc8fa2b45a6` (Harry Fox).
2. Click **Photos** → lands on a photo with `?identity_id=d74cb556-…&sort_by=date_asc`
   (e.g. `/c/fox-family/photo/a58504ab20bbb741?identity_id=…&sort_by=date_asc`) — correctly shows
   "VIEWING Harry Fox in this photo."
3. Click the **left/right arrows** → navigation cycles through the WHOLE collection
   ("Charles Fox Dayton Ohio Collection"), NOT just Harry Fox's tagged photos. Next lands on
   `/c/fox-family/photo/24c06d3f876d34a5?identity_id=…` where Harry is NOT tagged → a public viewer
   sees the admin-flavored "Harry Fox is not currently tagged on this photo / NEEDS REVIEW" banner.

For someone handed a shared link, this is confusing — they expect "photos of Harry Fox," not the
whole collection.

## Root cause (located — `app/page_routes.py`)
- `_ordered_identity_photo_ids(registry, identity_id, sort_by)` (line ~3513) is the correct ordered
  builder of an identity's photo set (the same set the person "Photos" gallery shows).
- `photo_view_content` computes identity-scoped prev/next at **lines ~3611-3620**, BUT inside a guard:
  `if context_identity_id and context_photo_ids and not prev_id and not next_id and photo_id in context_photo_ids:`
  → **the scoped computation is bypassed whenever `prev_id`/`next_id` are already passed in.** The entry
  point and the arrow hrefs pass COLLECTION-based neighbors, so the scoped block never runs and the
  arrows walk the collection. Each HTMX partial click re-propagates collection prev/next, so it never
  recovers.
- A SECOND, inconsistent prev/next block exists at **line ~11390** (`identity_photo_ids = sorted(...)`,
  not via `_ordered_identity_photo_ids`) — unify these.
- Routes: full page `/photo/{photo_id}` → `_main_mod.public_photo_page`; HTMX partial
  `/photo/{photo_id}/partial` → `_main_mod.photo_view_content` (both in `app/page_routes.py` /
  `app/main.py`; thin wrappers in `app/photo_routes.py:356,393`). Both must scope correctly.

## Design (think through — three parts)
**A. Make `identity_id` authoritative for prev/next (the core fix).** When `identity_id` is present,
ALWAYS compute prev/next from `_ordered_identity_photo_ids` (honoring `sort_by`), overriding any
incoming collection prev/next. Arrow hrefs must always carry `identity_id` + `sort_by` + the
freshly-scoped neighbors. "X of Y" reflects position within the person's set. Clamp at ends (disable
arrow at first/last) rather than wrap into the collection. Fix BOTH the full-page and partial paths;
unify the 3613 + 11390 blocks. Verify `_ordered_identity_photo_ids` includes exactly the person-gallery
photos (confirm a58504ab + the person's other photos are all in it; decide confirmed/anchor-only).

**B. Dedicated shareable person-photo gallery (the user's suggestion).** A clean public URL —
e.g. `/c/<community>/person/<id>/photos` — that IS the "photos of Harry Fox" share target: a gallery
of the person's confirmed photos whose viewer prev/next stays in-set (reuses A). The person page's
**Share** button should surface/point to this link. Mini-PRD required (SDD): problem, user flow,
acceptance criteria, out-of-scope. Keep it small — reuse the existing gallery + viewer.

**C. Public-appropriate messaging.** With A fixed, a public viewer navigating within the set won't
hit the off-person state. But if an off-person photo is reached via a raw deep link, the
"not currently tagged / NEEDS REVIEW" banner is ADMIN language — show gentle public wording (or hide
the review framing) for anonymous viewers.

## Acceptance / verification (must reproduce the exact user flow)
- Incognito: Harry Fox shared link → Photos → left/right cycles ONLY Harry's photos; "X of Y" is the
  person count; ends clamp; every photo shown has Harry tagged. No "NEEDS REVIEW" to public.
- Browser-verify on production (READ-ONLY) with the exact URLs above + screenshots →
  `docs/screenshots/session-165/`.
- Tests: prev/next scoping (full + partial), href propagation of identity_id+sort_by, ends clamp,
  the dedicated gallery route, public-messaging branch. Regression: collection nav still works when
  NO identity_id.

## Breadcrumbs
- Close FB-004 (BACKLOG) + cite Lesson 63. New DD-NNN for the person-scoped-share decision.
- Related prior: session-129 FB (identity_id back-link reflects navigation source), session-135 FB-004.
