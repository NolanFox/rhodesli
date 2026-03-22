# Session 132 — Merge Chain Audit

**Date:** 2026-03-22
**Type:** READ-ONLY audit of Supabase `identities` table merge chains
**Script:** `scripts/audit_merge_chains.py`

## Summary

| Metric | Count |
|--------|-------|
| Total identities | 3,545 |
| Active (non-merged) | 1,649 |
| Merged (merged_into set) | 1,896 |
| Multi-hop chains (>1 hop) | 556 |
| Circular chains | 0 |
| Intermediate merge targets (themselves merged) | 152 |
| Dangling references (target doesn't exist) | 691 |
| Unique dangling targets | 106 |
| Merged identities still holding faces | 1,858 |

## Key Findings

### 1. No Circular Chains (GOOD)
No circular merge references found. Every chain terminates.

### 2. Multi-Hop Chains (556 identities)
556 identities have merge chains with >1 hop (e.g., A -> B -> C instead of A -> C).
Deepest chains are 3 hops. Example:
- `0069f2be` -> `add3a974` -> `4f97e48e` (Person 3380) -> `85546ebf` (Albert Fox, CONFIRMED)

**152 intermediate merge targets** are the root cause: identities that are themselves merge targets but have their own `merged_into` set. Flattening these 152 would fix all 556 multi-hop chains.

### 3. Dangling References (691 identities — CRITICAL)
691 identities have `merged_into` pointing to identity IDs that don't exist in Supabase.
These resolve to only **106 unique missing targets**:

| Missing Target ID | Identities Pointing Here |
|-------------------|-------------------------|
| `9b686cf1-b1ad-...` | 219 |
| `5981a409-0572-...` | 138 |
| `a71d7a56-8044-...` | 108 |
| `26fe72fa-3271-...` | 34 |
| `ef7470fd-9f34-...` | 19 |
| `b38316a5-6e3c-...` | 17 |
| (100 more with <10 each) | 156 |

**Hypothesis:** These are likely identities from the pre-Supabase era (JSON-only) that were never migrated, or were deleted during data cleanup sessions. The top 3 missing targets account for 465 of 691 dangling references (67%).

### 4. Merged Identities Still Holding Faces (1,858 — CRITICAL)
1,858 of 1,896 merged identities still have `anchor_ids` and/or `candidate_ids`. These faces should have been transferred to the merge target but were not. This is the same orphaning pattern documented in Lesson 154 (Session 131).

**This means nearly ALL merged identities still hold their faces.** The faces are effectively invisible — they belong to identities marked as merged, so they don't appear in any active identity's face list.

### 5. Top Merge Targets

| Identity | Name | State | Merges Absorbed |
|----------|------|-------|-----------------|
| `429cf1b6` | Charles Fox | CONFIRMED | 292 |
| `9b686cf1` | ? | MISSING | 219 |
| `85546ebf` | Albert Fox | CONFIRMED | 216 |
| `65207728` | Esther Burd Fox | CONFIRMED | 146 |
| `5981a409` | ? | MISSING | 138 |
| `a71d7a56` | ? | MISSING | 108 |
| `ae0b181b` | Roland Fox | CONFIRMED | 94 |
| `26fe72fa` | ? | MISSING | 34 |
| `e889a985` | Leona Fox Smilg | CONFIRMED | 34 |
| `6a1657f4` | Rose | CONFIRMED | 22 |

## Recommended Fixes (Priority Order)

### P1: Flatten Multi-Hop Chains (556 chains, 152 intermediates)
Update `merged_into` on 556 identities to point directly to the final non-merged target.
This is a safe, non-destructive operation — it doesn't change who is merged, just shortens the chain.

**Impact:** Merge resolution will skip unnecessary lookups. Currently any code following merge chains must traverse 2-3 hops.

### P1: Investigate Dangling References (691 identities, 106 missing targets)
Before fixing, investigate:
1. Do these targets exist in `identities.json` (legacy JSON)? If so, they need Supabase migration.
2. Were they deliberately deleted? If so, the 691 sources need new targets or un-merging.
3. The top 3 missing targets (465 references) should be investigated first.

### P1: Face Transfer for Merged Identities (1,858 identities)
This is the Session 131 orphan pattern at massive scale. 1,858 merged identities still hold faces.
The `merge_identities()` function should transfer all face IDs to the target identity.

**Caution:** The 691 dangling references mean we cannot blindly transfer faces for those —
their targets don't exist. Must resolve dangling references first.

## Relationship to Session 131

Session 131 fixed 175 orphaned faces across 18 identities and added post-merge verification.
This audit reveals the problem is much larger: 1,858 merged identities with retained faces.
The Session 131 fix prevents NEW orphaning but doesn't repair historical damage.

## Next Steps

1. Run the audit script again after any fix to verify improvement
2. Cross-reference dangling targets with `identities.json` backup
3. Determine if faces on dangling-target merges should be un-merged or re-targeted
