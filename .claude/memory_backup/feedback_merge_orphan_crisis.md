---
name: Merge orphan crisis — data integrity failure #10
description: Merge operations orphan faces — 175 faces lost across 18 identities. Post-merge verification + audit tests added. NEVER declare data fix done without browser verification of the specific affected page.
type: feedback
---

Merge operations can orphan faces: faces stay in merged source (hidden from UI) but aren't in target.
175 faces across 18 identities were orphaned. Esther Burd Fox lost 8 faces from a tagged photo.

**Why:** The in-memory merge transfers faces correctly, but if the save path fails silently or if faces were
orphaned before the fix was applied, the source gets `merged_into` (hidden) while its faces remain invisible.
This was declared "FIXED" in Session 129 without actually verifying the photo page rendered the correct names.

**How to apply:**
1. Post-merge verification added to `core/registry.py merge_identities()` — force-adds orphaned faces
2. `tests/test_merge_face_transfer.py` — 6 structural tests (simple, swap, chain, orphan detection)
3. `tests/test_merge_orphan_audit.py` — production Supabase data audit
4. **CRITICAL**: NEVER claim a data fix is "done" without loading the ACTUAL affected page in the browser
   and verifying the face shows the correct name. "Tests pass" is not verification. "Supabase query shows
   correct data" is not verification. Only the rendered photo page with correct face labels is verification.
5. This is the 10th data integrity occurrence (Lessons 56→69→78→85→141→144→147→150→153→154)
