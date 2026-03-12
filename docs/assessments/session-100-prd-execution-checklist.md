# Session 100 PRD Execution Checklist

**Date:** 2026-03-12  
**Author:** Codex

## Purpose
Prevent another scope-collapse failure where the emergency hotfix slice is
mistaken for the full Session 100 outcome.

This checklist is the execution companion to
[PRD-040](/Users/nolanfox/rhodesli/docs/prds/040_multi_community_bootstrap_and_face_cards.md).
Session 100 is not done until every item below is either:
- shipped
- explicitly deferred in writing
- or blocked with a repo-grounded reason

## No-Drop Rules
1. No acceptance item may disappear due to agent handoff.
2. Antigravity-owned design critique work becomes Codex-owned if Antigravity is
   unavailable.
3. “Hotfix complete” does not equal “session complete.”
4. Any item discovered through live Fox Family usage must be logged against this
   checklist, not treated as ad hoc feedback.

## Acceptance Matrix

### A. Community Context
- `/` must not silently force users into Rhodes.
- Community-prefixed routes must preserve archive context across person, photo,
  identify, tree, and similar flows.
- Admin links must not kick Fox Family users back into Rhodes.
- Community-specific pages must use generic/fallback copy instead of Rhodes-only
  assumptions.

### B. Admin vs Public Separation
- Public identify/share pages remain share-safe and archive-correct.
- Admin person/photo/similar flows keep admin affordances visible.
- “Edit in Admin” and similar return paths must land in the correct archive and
  section.

### C. Fast Tagging Workflow
- Person -> Photos -> Photo -> next/prev preserves person context.
- Dense multi-face photos use a grid-capable expanded state.
- The speed loop is discoverable from the real working path, not only from a
  hidden branch.
- “Ignore stranger” / skip behavior remains fast and reversible.
- Mobile photo navigation supports touch gestures where the desktop path uses
  left/right navigation.

### D. Similar / Merge Workflow
- “Find Similar” is visually discoverable from the admin person page.
- Full-page similar view preserves community context.
- Full-page similar view allows merge/reject actions for admins.
- Similar-view links back to profile/workstation are archive-correct.

### E. Multi-Community Bootstrap
- A second archive can be created and browsed without leaking Rhodes context.
- Community chooser/root-entry path is understandable to a first-time visitor.
- Community landing includes a visible contribution/help path.

### F. Quality / Trust / Audit
- Changes stay FastHTML + HTMX.
- No shared-helper leakage into unrelated routes without tests.
- Attribution stays explicit: user vs Codex vs Antigravity vs collaborative.
- Before merge, run the required test gates and capture browser evidence.

## Current Session 100 Reality Check
- **Completed:** Fox Family perf recovery, speed-loop mechanics, denser public
  photo multi-face handling, person-context photo navigation, standalone speed
  loop discoverability, full-page similar/community/admin fixes in progress.
- **Not yet complete:** neutral root/platform entry, full multi-community
  bootstrap hardening, contribution-shell work, final harmonization of repeated
  face-card/admin/public surfaces.

## Decision
Use this checklist as the completion bar for the remaining Session 100 work.
