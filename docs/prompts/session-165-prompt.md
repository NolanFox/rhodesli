# Session 165 Prompt — Person-Scoped Photo Navigation + Shareable Person Gallery

**Context (READ FIRST):** [docs/session_context/session-165-context.md](../session_context/session-165-context.md)
**Predecessor:** Session 164 (GEDCOM redesign — site is LIVE; DB 244 MB; Supabase on Pro).
**Mode:** UX bug fix + small feature. **Effort:** Opus xhigh. Think carefully, step-by-step for the
navigation logic; this is a shared-link experience real community members hit.

---

## Mission
A shared person link's photo viewer cycles through the **whole collection** instead of just that
**person's photos**. Fix the navigation to stay scoped to the person, and add a clean, dedicated
**shareable person-photo gallery** so "share photos of Harry Fox" is unambiguous. This is the known
**FB-004** (Session 135, P1, BACKLOG) and an instance of **Lesson 63** (preserve filters across all
navigation paths).

## Exact repro (verify the fix against THIS)
1. Incognito → `https://rhodesli.nolanandrewfox.com/c/fox-family/person/d74cb556-6d44-4288-ade3-1cc8fa2b45a6` (Harry Fox).
2. Click **Photos** → `/c/fox-family/photo/a58504ab20bbb741?identity_id=d74cb556-…&sort_by=date_asc`
   ("VIEWING Harry Fox in this photo" — correct).
3. Click right → currently lands on `/c/fox-family/photo/24c06d3f876d34a5?identity_id=…` where Harry is
   NOT tagged ("NEEDS REVIEW" banner). **After the fix:** right/left cycle ONLY Harry's tagged photos.

## Phase 0 — Orient
- Read the context file + this prompt. `echo 165 > .claude/current_session.txt`; `make test-fast` baseline.
- Read `app/page_routes.py` `_ordered_identity_photo_ids` (~3513), `photo_view_content` scoped-nav block
  (~3611-3620) and the SECOND prev/next block (~11390); the wrappers `app/photo_routes.py:356` (`/photo/{id}`)
  and `:393` (`/photo/{id}/partial`); and `_main_mod.public_photo_page` / `photo_view_content` in `app/main.py`.
- Confirm the root cause: the scoped block is guarded by `not prev_id and not next_id`, so collection-based
  prev/next passed by the entry point / arrows bypass it (context §"Root cause"). Verify by reading, not assuming.

## Phase 1 — Fix person-scoped prev/next (the core bug) — write tests FIRST
- When `identity_id` is present, `_ordered_identity_photo_ids(registry, identity_id, sort_by)` is
  **authoritative**: ALWAYS recompute prev/next from it and OVERRIDE any incoming collection
  prev_id/next_id. Remove/restructure the `not prev_id and not next_id` bypass for the identity case.
- "X of Y" = position within the person's set. **Clamp at ends** (disable arrow at first/last; do NOT
  wrap into the collection). When NO `identity_id`, keep existing collection navigation unchanged (regression).
- Every prev/next href (full page + HTMX partial) must carry `identity_id` + `sort_by` + the freshly
  identity-scoped neighbor IDs, so repeated arrow clicks stay scoped.
- Unify the two prev/next computations (the ~3613 block and the ~11390 block) onto `_ordered_identity_photo_ids`
  so full-page and partial agree. Confirm `_ordered_identity_photo_ids` returns exactly the person-gallery
  set (the photos the person "Photos" tab shows — confirm a58504ab + Harry's other photos are all present;
  decide + document confirmed/anchor-only vs including candidates).
- Tests (`tests/`): (a) with identity_id, prev/next come only from the identity's ordered set; (b) incoming
  collection prev/next are overridden when identity_id present; (c) ends clamp (no wrap); (d) href carries
  identity_id+sort_by; (e) partial route scopes identically to full page; (f) regression: no identity_id →
  collection nav unchanged. Mock registry/photo data; no live Supabase. `make test-fast` green.

## Phase 2 — Dedicated shareable person-photo gallery (mini-PRD first)
- Write a short PRD `docs/prds/065_person_photo_gallery.md` (problem, user flow, acceptance criteria,
  data model = none/reuse, out-of-scope). Keep it small.
- Add a clean public route, e.g. `GET /c/<community>/person/{id}/photos` — a gallery of the person's
  confirmed photos whose viewer prev/next stays in-set (reuses Phase 1). Title/OG tags = "Photos of <Name>".
- Wire the person page **Share** button to offer/point at this person-photo link (so the shared link is
  unambiguous). Don't break the existing person-page share. Tests for the route + share wiring.

## Phase 3 — Public-appropriate messaging
- The "not currently tagged / NEEDS REVIEW" banner is admin language. For anonymous (non-admin) viewers,
  show gentle public wording or suppress the review framing (admins still see the review banner). With
  Phase 1 fixed, public viewers shouldn't reach the off-person state via arrows, but a raw deep link still
  can — handle it gracefully. Test both admin and anonymous branches.

## Phase 4 — Verify (browser, READ-ONLY on production)
- Reproduce the exact flow incognito-equivalent: Harry Fox person → Photos → left/right cycles ONLY Harry's
  photos; "X of Y" correct; ends clamp; every shown photo has Harry tagged; no NEEDS REVIEW to public.
- Verify the dedicated `/person/{id}/photos` share link + Share button.
- Screenshots → `docs/screenshots/session-165/`. (Browser automation READ-ONLY — Lesson 149.)

## Phase 5 — Dual-audit (Codex) per phase, then closeout
- Codex CLI audit (`codex exec "<prompt>" </dev/null`, gpt-5.5/xhigh; verify pin fresh) of the nav fix +
  new route + messaging. Fix P0/P1. Save `docs/session_context/session-165-codex-audit.md` with provenance.
- Closeout: assessment, CHANGELOG (version bump), ROADMAP + SESSION_HISTORY, BACKLOG (close **FB-004**;
  add DD-NNN for the person-scoped-share decision), lessons if any, memory backup, `git push origin main`,
  verify health 200, `git log origin/main..HEAD` empty, `/session-review`.

## Acceptance criteria (all must pass)
- [ ] With `identity_id`, photo prev/next cycle ONLY that person's photos (full page + HTMX partial); ends clamp.
- [ ] Incoming collection prev/next are overridden when identity_id is present; hrefs carry identity_id+sort_by.
- [ ] No `identity_id` → collection navigation unchanged (regression test passes).
- [ ] Dedicated shareable `/c/<community>/person/{id}/photos` gallery exists; Share button points to it.
- [ ] Anonymous viewers never see admin "NEEDS REVIEW" language; admins still do.
- [ ] Exact Harry Fox repro verified in production browser (READ-ONLY) + screenshots.
- [ ] Codex audit logged; P0/P1 resolved. Both test suites green. FB-004 closed.

## Rules
- Browser automation READ-ONLY on production (Lesson 149). NEVER click action buttons.
- `/clear` between phases; commit atomically; every change gets tests (happy + failure + regression).
- This touches a shared monolith (`app/page_routes.py` / `app/main.py`) — sequential, not parallel worktrees.
