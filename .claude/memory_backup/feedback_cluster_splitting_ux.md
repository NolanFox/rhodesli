---
name: Cluster splitting UX is missing (P1)
description: No way to break up a contaminated cluster in the app. Siblings get grouped together and unmerging is painful. This was a core motivation for building the platform (Google Photos pain point).
type: feedback
---

There is no UX to split a cluster in the app. You can detach individual faces but there's no "split cluster" operation that moves a subset of faces to a new or existing identity.

**Why:** Sibling resemblance causes clusters to contain faces of multiple people (e.g., Person 4063 contains both Albert and Harry Fox faces). Accidental merges during triage compound this. Google Photos has the same problem and it was one of Nolan's motivations for building Rhodesli.

**How to apply:**
- This needs a PRD (workflow change, multiple edge cases)
- Core operation: select faces within a cluster → "Move to new identity" or "Move to [existing identity]"
- Must preserve audit trail (who split, why, which faces moved)
- Should show side-by-side comparison before confirming split
- Related: BACKLOG UX-130, UX-131
- Context: Person 4063 investigation (`docs/session_context/investigation-4063-harry-fox.md`)

**Implementation difficulty when done programmatically (2026-03-18):**
1. Supabase anchor_ids update worked immediately (verified via direct query)
2. Production app showed STALE data for 10+ minutes despite 120s TTL cache
3. Root cause: direct Supabase writes bypass the app's cache invalidation. The app only invalidates when writes go through its own save_registry() path.
4. Fix required: deploy restart (new process loads fresh from Supabase)
5. **This means the in-app split feature MUST use the app's own write path** (save_registry → invalidate cache), not direct Supabase manipulation
6. Linked to Lesson 150 (three-source data split-brain) and Session 111 speed-run caching issues
7. BACKLOG: need `/api/admin/cache/invalidate` endpoint for forced cache refresh without deploy
8. **CRITICAL: `identity_overrides` table silently overwrites `identities` table.** `load_from_postgres()` first loads from `identities`, then applies `identity_overrides` on top (lines 1914-1919 in registry.py). Any direct write to `identities` is INVISIBLE if an override row exists. Must update BOTH tables. This is a data integrity trap — the override layer was designed for startup sync but creates a shadow write problem for any programmatic identity mutation.
9. Root cause of the Person 4063 split not taking effect: override row had old 3-anchor data, overwriting the corrected 2-anchor data in identities table. Took ~30 min to diagnose.
