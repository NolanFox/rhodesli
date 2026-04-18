# Session 153 — Skip UX Investigation

**Date:** 2026-04-18
**Trigger:** Admin accidentally clicked the orange "skip" icon on Person 2510
(`c39e8284-871d-4a1d-88ae-888793f4b151`), flipping it INBOX → SKIPPED. State
reverted manually; backup at `backups/session-153/person-2510-before-20260418T220659Z.json`.
**Constraint:** READ-ONLY investigation, no commits.

---

## 1. Button Identification

There are **TWO** skip surfaces on a face overlay in the photo viewer. The user
likely clicked the *first* (the small amber circle).

### A. Inline Quick-Action Skip Pill (the culprit)
- **File:** `app/page_routes.py:3967-3983`
- **Icon:** `\u23f8` (⏸ "Double Vertical Bar" / pause-shaped)
- **Style:** `w-6 h-6 rounded-full bg-amber-500 hover:bg-amber-400` — **24×24 px**,
  amber circle, white pause glyph. Below WCAG 44×44 touch-target minimum.
- **Container:** `quick-actions absolute bottom-1 left-1/2 -translate-x-1/2 flex gap-1
  opacity-0 group-hover:opacity-100` — sits inside the face bounding box, appears
  on hover/touch, between Confirm (✓ green) and Reject (✗ red).
- **Tooltip:** `title="Ignore / Skip"` (only shows on desktop hover; useless on mobile).
- **POSTs to:** `/api/face/quick-action?identity_id=...&action=skip&photo_id=...`
- **Visible for:** admin AND state ∈ {INBOX, PROPOSED} (not SKIPPED).
- **No `hx_confirm`. No `data-undo-*` hooks.** Mis-click is silent and irreversible
  from the same surface.

### B. "Ignore Stranger →" Button (sequential mode tag dropdown)
- **File:** `app/page_routes.py:3920-3934`
- **Style:** amber text pill with border, only in sequential mode
  (`seq_mode and face_identity_id`).
- **Tooltip:** "Mark this face as background noise or defer it for later review".
- Clearly labeled, lower mis-click risk.

The user's screenshot shows both, but the small amber ⏸ pill (A) is the
overlapping click target with the face itself.

---

## 2. Server-Side Skip — What Changes?

### Route: `/api/face/quick-action` (`app/identity_routes.py:1678-1784`)
1. Auth check (`_check_admin`).
2. `registry.skip_identity(identity_id, user_source="quick_action")`.
3. `save_registry(registry, changed_ids={identity_id})`.
4. `_log_audit("skip", entity_id=..., old_value={state, name}, new_value={state:SKIPPED})`.
5. Re-renders the photo view + success toast: "Ignored for now. You can still
   rediscover it later."

### `core/registry.skip_identity()` (`core/registry.py:1027-1070`)
Mutations on the identity dict ONLY:
- `state` → `SKIPPED`
- `version_id` += 1
- `updated_at` → now
- Appends a `SKIP` event to history (with `previous_state` metadata)

**No mutations to:** `anchor_ids`, `candidate_ids`, `negative_ids`, `photo_faces`,
embeddings, GEDCOM links, any cross-table joins. Faces are untouched.

### Side effects via `save_registry()` (`app/main.py:1719+`)
- Supabase upsert (state column changes for that one identity)
- JSON backup write (background thread)
- Cache invalidations: `_face_identity_lookup_cache`, `_best_face_cache`,
  `neighbors_cache` (per identity), `perf_cache global matrix`,
  `cluster_review_caches`, `_community_identity_ids_cache`.
- No notifications, no emails, no derived-table writes, no audit_log row beyond
  the `_log_audit("skip", …)` row above.

### Reversibility — FULLY REVERSIBLE
- `core/registry.reset_identity()` (`core/registry.py:1072-1120`) explicitly accepts
  `SKIPPED` as a source state and transitions to INBOX, bumping `version_id`,
  appending a `RESET` event. No data loss. Both forward and reverse are
  audit-trail visible.

---

## 3. Undo UI — DOES NOT EXIST FOR SKIPPED

### What exists
- `/api/identity/{id}/restore` (`app/identity_routes.py:4515-4635`) calls
  `reset_identity()`, which the registry layer DOES allow for SKIPPED…
  **but the route handler explicitly blocks it:** line 4558:
  `if old_state not in ("REJECTED", "CONTESTED"):` → 400 error.
- "Restore" button on the person page (`app/person_routes.py:1565-1575`):
  only renders when `state in ("REJECTED", "CONTESTED")`.
- "Restore" button on identity card (`app/components/identity_cards.py:813-822`):
  same — only `REJECTED`/`CONTESTED`.
- Z-key keyboard undo (`app/page_routes.py:3068-3139`): only wired to skip
  actions inside *Skipped Focus mode*, not face-overlay quick actions. Pushes
  to `_undoStack` only when the clicked element has `data-undo-type` — the
  inline ⏸ button does NOT.

### What is missing
A SKIPPED person's `/person/{id}` page shows Confirm + Reject buttons
(`app/person_routes.py:1522, 1546`) but NO Skip and NO Restore. The user can
only "undo" by Confirming (which is wrong — implies identification) or by
Rejecting (which is worse — sends to a different terminal state).

There is NO admin-visible UI path to flip SKIPPED → INBOX without a
backend script or the `/api/admin/force-state/{id}/INBOX` route (which has
no UI surface either).

---

## 4. Proposed UX Changes

**P0 — Add Restore for SKIPPED (matches existing REJECTED pattern)**
1. `app/identity_routes.py:4558` — extend allowed states:
   `if old_state not in ("REJECTED", "CONTESTED", "SKIPPED"):`
2. `app/person_routes.py:1554` — render the Restore button branch when
   `state == "SKIPPED"` too. Use amber accent to mirror SKIPPED pill.
3. `app/components/identity_cards.py:813` — add `"SKIPPED"` to the tuple.

**P0 — Make the inline quick-action Skip pill harder to mis-click**
- Increase `w-6 h-6` (24px) to at least `w-9 h-9` (36px) — still <44px
  ideal but reduces collision with face-click area. Or:
- Move the quick-actions row from `absolute bottom-1 inside face box` to
  *outside* the face bbox (e.g. `-bottom-7`) so face-click and skip-click
  are physically separated.
- Add `hx_confirm="Skip this person? You can restore from their profile page."`
  on the Skip pill only (Confirm/Reject can stay frictionless because
  Reject already has Restore and Confirm has the explicit toast).

**P1 — Wire the existing Z-undo into face-overlay quick actions**
- Add `data-undo-type="skip"`, `data-undo-identity={identity_id}`,
  `data-undo-url=/api/identity/{id}/restore` to the inline Skip button at
  `app/page_routes.py:3969`.
- Update the toast at `app/identity_routes.py:1779` to include an inline
  "Undo (Z)" link when `action == "skip"`.

**P1 — Replace the ambiguous ⏸ glyph**
- ⏸ reads as "pause/playback" not "defer review". Use 💤 or text "Skip"
  inside the pill (slightly larger pill required). Tooltip alone is invisible
  on mobile.

**P2 — De-emphasize Skip in sequential mode**
- The "Ignore Stranger →" button (3920) is the *intended* defer surface for
  sequential mode. The duplicate inline ⏸ pill (3967) in the same modal
  creates two skip paths with different copy. Hide the inline pill when
  `seq_mode == True` to leave only the labeled button.

---

## 5. Data Safety Assessment

**No hidden side effects.** Skip is a single-column state flip on one identity
row. Faces, embeddings, photo joins, GEDCOM links, and all derived tables are
untouched. Forward and reverse both write a history event and an audit_log row,
so any accidental flip is fully traceable and reversible by `reset_identity()`.

The only "loss" from accidental skip is that the identity drops out of
proposals/inbox surfaces and stops appearing in cluster review until manually
restored — invisible-but-not-destroyed. The Person 2510 incident was
recoverable because the user noticed within minutes; a quieter mis-click
could go undetected for weeks.

---

## Summary

The amber ⏸ skip pill is a 24px touch target glued to the face-click target
with no confirm, no inline undo, and no compensating UI to reverse the action
— the only "Restore" surface in the codebase explicitly excludes the SKIPPED
state. The fix is small (≈20 LoC across 3 files): allow Restore from SKIPPED,
enlarge/relocate the pill, and wire it into the existing Z-undo stack.
