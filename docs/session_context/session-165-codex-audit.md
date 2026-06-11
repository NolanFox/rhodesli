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
