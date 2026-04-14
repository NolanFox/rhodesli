---
name: Collage/same-photo merge override needed
description: Current "seen together in 1 photo" block prevents merging faces from collages, photos-of-photos, and photos-on-walls. Need an override with enough friction to be intentional but not painful.
type: feedback
---

The co-occurrence block ("Seen together in 1 photo" → Blocked button) creates false positives for:
- Collage photos (multiple sub-photos assembled into one image)
- Photos of photo albums (person appears in foreground + in a framed photo)
- Photos with pictures on the wall
- Before/after composite images

**Why:** Session 108 — Nolan noticed Person 1c8c316f (65% match), Person 5e3de5c5 (59%), Person 1646d93d (56%) were all BLOCKED due to "Seen together in 1 photo" but they were actually the same person in different sub-photos of a collage. The block prevented legitimate merges.

**User's design guidance:**
- Default should still be BLOCK (correct for siblings standing together)
- Override must be intentional — enough friction not to do it accidentally
- "Same photo" warning must remain prominent even when override is available
- Should work like a confirmation step, not a toggle

**How to apply:** When implementing the override, design for the collage use case. The UX should surface the warning, require explicit acknowledgment ("I understand these faces are from the same photo — this is a collage/composite"), and log the override for audit. This needs a PRD — don't implement without proper UX design.

**BACKLOG:** MERGE-001 in docs/BACKLOG.md
