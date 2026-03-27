# Session 141 Codex Audit

**Auditor**: Codex CLI v0.115.0 (gpt-5.4)
**Agent type**: Independent (fresh context)
**Phase**: All tracks (A, B, C, D, E) — post-merge audit
**Date**: 2026-03-26
**Tokens used**: 356,582

## Findings

### P0 (Critical) — None

### P1 (High)
1. **primary_face_id not wired through render paths** — `get_best_face_id()` only honors the override when callers pass `identity=`, but `identity_card_expanded` (line 182), `identity_card` (line 624), `cards.py` (line 228), and `_build_face_cards_for_entries` (line 400) all call it WITHOUT the identity dict. The hero face picker feature is cosmetically complete but functionally inert in production renders. Tests cover the isolated helper but not the rendering integration.
   - **Action**: BACKLOG — wire `identity=identity` into all card rendering call sites. This is a follow-up task, not a regression (quality-based selection still works as before).

### P2 (Medium)
1. **Hero-face button loses community scoping** — `_build_face_cards_for_entries()` doesn't accept/forward `nav_prefix`, so the star button POSTs to `/api/identity/.../set-primary-face/...` instead of `/c/<slug>/api/...` on community-scoped pages. Tests never cover `nav_prefix`.
   - **Action**: BACKLOG — add nav_prefix to _build_face_cards_for_entries.

2. **CSRF guard patches are inert** — Hero face picker tests patch `app.auth._check_origin` but `identity_routes.py` binds `_check_origin` directly at import time (line 20). After import, the route's reference is already bound. Tests pass only because missing Origin/Referer headers are allowed by default.
   - **Action**: BACKLOG — fix test patches to target `app.identity_routes._check_origin`.

3. **Circular import: `import app.identity_routes` fails standalone** — identity_routes imports app.main, which imports identity_routes. The test masks this by importing app.main first. Not a runtime issue (FastHTML loads main.py first) but blocks future standalone module testing.
   - **Action**: NOTE — pre-existing architectural issue, not Session 141 regression.

### P3 (Informational)
1. **create=True guard non-enforcing** — Uses `pytest.skip()` instead of `assert False`. Converts masked-regression signal into a skipped test. Shows `1 skipped` instead of surfacing the 17 create=True patches.
   - **Action**: NOTE — intentional design (flagging, not blocking). Could be promoted to a warning.

2. **Starlette deprecated startup hook** — `startup_event` at line 1007 uses deprecated `@app.on_event("startup")`. Not a bug today but a future upgrade risk.
   - **Action**: NOTE — pre-existing, not Session 141.

## Claude Review of Codex Findings

| Finding | Codex Assessment | Claude Assessment | Action |
|---------|-----------------|-------------------|--------|
| P1 #1: primary_face_id not wired | Correct | **AGREE** — Feature ships green but is inert. Honest assessment: the hero face picker doesn't actually change what users see. | BACKLOG |
| P2 #1: Community scoping | Correct | **AGREE** — nav_prefix gap in _build_face_cards_for_entries | BACKLOG |
| P2 #2: CSRF patch inert | Correct | **AGREE** — Tests are testing nothing for the security guard | BACKLOG (fix next session) |
| P2 #3: Circular import | Correct | **AGREE but REJECT as Session 141 issue** — pre-existing architecture | NOTE |
| P3 #1: create=True non-enforcing | Correct | **AGREE** — intentional for now, could be stricter | NOTE |
| P3 #2: Deprecated startup hook | Correct | **AGREE** — not Session 141 | NOTE |

## Value Assessment
- **Codex**: STRONG — P1 finding (hero face picker inert) is exactly the kind of "ships green, doesn't work" bug that unit tests can't catch. P2 CSRF patch finding is a real security test gap. Worth the 356K tokens.
- **Would we have found this ourselves?** P1: my self-audit noted it but called it P2. Codex correctly elevated it. P2 CSRF: NO — I would not have caught that the patches are inert.
