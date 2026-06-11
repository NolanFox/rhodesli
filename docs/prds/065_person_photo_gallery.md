# PRD-065 — Shareable Person-Photo Gallery

**Status:** Shipped (Session 165) · **Owner:** Nolan · **Size:** small (reuses existing gallery + viewer)
**Related:** FB-004, Lesson 63, DD (person-scoped share), Session 165 nav fix (canonical photo IDs).

## Problem
When you share a person link (`/c/<community>/person/<id>`) so the community can say
"here are photos of Harry Fox," the recipient lands on a page whose primary framing is the person
record (faces, identify CTAs, similar people). The phrase the sharer means — *photos of this person* —
isn't an unambiguous, dedicated destination. Compounding this, the in-photo viewer's prev/next used to
walk the whole collection (FB-004), so a shared link could drift off-person entirely.

## User flow
1. A community member opens a person page and taps **Share**.
2. The shared link is `/c/<community>/person/<id>/photos` — a clean "Photos of <Name>" gallery.
3. The recipient opens it: a grid of the person's photos, OG preview titled **"Photos of <Name>"**.
4. Tapping a photo opens the viewer; prev/next stay **in that person's set** (Session 165 fix), with a
   correct "X of Y" within the person's photos and clamped ends (no wrap into the collection).

## Acceptance criteria
- [x] `GET /c/<community>/person/<id>/photos` returns 200 and renders the person's photo gallery (view=photos).
- [x] OG/Twitter title + page `<title>` read **"Photos of <Name>"**; og:url points to the `/photos` path.
- [x] The person page **Share** button targets the `/person/<id>/photos` link (unambiguous share).
- [x] Merged identities redirect to the canonical person's `/photos` (no dead links).
- [x] Viewer prev/next stay in the person's set (reuses the Session 165 canonical-ID nav fix).
- [x] No auth required (public, like the person page).

## Data model
None. Reuses `identities` + photo registry + the existing `public_person_page` gallery renderer and the
`/photo/{id}?identity_id=…&sort_by=…` viewer.

## Out of scope
- New gallery layout / new viewer (reuse existing).
- Curated/ordered "best of" selection — order follows the existing gallery sort.
- Per-photo privacy controls.
