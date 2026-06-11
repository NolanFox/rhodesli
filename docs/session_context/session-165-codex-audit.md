# Session 165 — Codex Audit of the PROMPT (pre-session)

**Auditor**: Codex CLI v0.139.0 (gpt-5.5, xhigh) · **Agent**: Independent (read prompt + context +
`app/page_routes.py` + `app/photo_routes.py` + identity routes + tests) · **Date**: 2026-06-10
**Value**: **STRONG** — caught that the proposed fix would break existing contracts + a regression test,
and that the real fix surface includes client-side JS, not just server prev/next.

## Root-cause check
Confirmed: `photo_view_content` (`app/page_routes.py` ~3611-3620) computes identity-scoped prev/next only
under `if … not prev_id and not next_id …`, so collection neighbors passed upstream bypass it. BUT the
fix is NOT simply "override incoming prev/next" (see P0/P1).

## Findings (incorporate into the prompt)
- **P0 — "Override incoming prev/next" breaks existing contracts.** A regression test
  `test_explicit_nav_overrides_identity` explicitly asserts explicit prev/next WIN over identity context.
  Globally making `identity_id` authoritative would break it AND three callers that depend on explicit
  nav. The correct fix preserves "explicit nav wins" generally, and instead ensures the **identity-context
  flow emits identity-scoped neighbors in the first place** (the entry point / arrow hrefs must carry the
  identity-scoped prev/next, not collection neighbors). Distinguish "legitimate explicit nav (compare/seq)"
  from "collection neighbors leaking into the identity flow."
- **P1 — Missed callers.** `photo_view_content` is called directly by **three routes in
  `app/identity_routes.py`**, plus the **compare modal** path (`from_compare=1`, explicit prev/next) and
  **seq-mode**. Any change to prev/next precedence must keep compare-modal nav, seq-mode, and those three
  callers working. The prompt only listed `photo_routes.py` wrappers.
- **P1 — Client-side surface.** FB-004 was **partially fixed in commit `c2d7f787`** (Session ~135):
  "Lightbox: prioritize data-nav-url (identity-scoped) over photoNavTo (global grid) in click delegation."
  So the arrows' target is chosen in **JS click delegation** between an identity-scoped `data-nav-url` and a
  global `photoNavTo`. The shared-link `/photo/` page arrows in THIS flow likely still resolve to the global
  grid nav. The fix must check/repair the client-side delegation + ensure the server emits the identity-scoped
  `data-nav-url` for the shared-person flow — not only server prev/next.
- **P2 — Verify `_ordered_identity_photo_ids` membership** (anchor/confirmed set) actually contains the
  repro photos; and confirm the second prev/next block (~11390) is reconciled without regressing its callers.

## Resolution → prompt revised
The prompt's Phase 0/1 are revised (see `session-165-prompt.md` "Codex prompt-audit corrections"):
preserve the explicit-nav-wins contract + `test_explicit_nav_overrides_identity`; fix the identity-context
ENTRY POINT + arrow hrefs (server `data-nav-url`) AND the client-side click delegation; enumerate + keep
green the compare/seq/identity_routes callers. Nothing rejected.

---

# Session 165 — Codex POST-EXECUTION Audit (implementation)

**Auditor**: Codex CLI v0.139.0 (gpt-5.5, xhigh) · **Agent**: Independent (fresh context) · **Date**: 2026-06-10
**Scope**: implementation diff — `app/main.py` (`canonical_photo_id`), `app/page_routes.py`
(`_ordered_identity_photo_ids`, `photo_view_content`, `public_photo_page` nav + banner),
`app/person_routes.py` (`GET /person/{id}/photos`), nav + gallery-route tests.
**Invocation**: `codex exec "<prompt>" </dev/null`
**Value**: **STRONG** — caught a residual FB-004 leak path (off-person deep links) + a reflected-XSS sink.

## Findings (no P0; 2 P1, 2 actionable P2, 1 P3) — ALL fixed before push

- **P1-1 — Person context falls back to whole-collection nav** (`public_photo_page:11424`). Off-person deep
  link with `identity_id` present still hit the collection fallback (the `pZ` fixture rendered "Photo 4 of 4").
  **Fix**: guard fallback with `not identity_id`. Regression: `test_off_person_deep_link_does_not_leak_collection_nav`.
- **P1-2 — Reflected XSS via `identity_id`** in the inline keyboard/touch nav `<script>` (`~12195`). Raw
  f-string interpolation into JS string literals. **Fix**: `urlencode` the query + `quote()` photo IDs +
  `json.dumps` the URLs into JS vars. Regression: `test_keyboard_nav_script_escapes_identity_id` (payload
  renders url-encoded `%22%29%3B…`, inert in every `<script>`).
- **P2-3 — Resolver not consistently canonicalized** (`_ordered_identity_photo_ids:3540`). `_face_to_photo_cache`
  can hold raw `inbox_*` IDs. **Fix**: `canonical_photo_id()` every resolved pid in the primary loop, not only fallback.
- **P2-4 — Anonymous gallery exposes admin review language** (`person_routes.py:~492/542/551`). "Needs review" /
  "Conflicting face assignment" rendered unconditionally on the public `/person/{id}/photos`. **Fix**: gate all
  three on `(context_conflict and is_admin)`. Tests: `test_anonymous_gallery_hides_review_language` +
  `test_admin_gallery_shows_review_language_when_conflicted`.
- **P3-5 — Boundary test gaps** → added full-page first/last clamp (no-wrap), off-person leak guard,
  XSS-escaping assertion, admin/anonymous gallery matrix.

## Disposition
P1×2 fixed; P2×2 fixed (on-mission for Phase 1 robustness + Phase 3 public messaging); P3 addressed.
No data-modifying authz bypass (new route is public GET by design, matches `/person/{id}`).
`make test-fast` 4339 passed (+6 regression tests), 0 regressions, post-fix.
