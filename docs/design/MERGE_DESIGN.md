# Merge System Design Doc

**Status:** Draft
**Date:** 2026-02-05
**Author:** Design review session
**Related ADRs:** ADR-004 (Identity Registry)
**Related Invariants:** Conservation of Mass (CLAUDE.md), Reversible Merges (CLAUDE.md)

---

## 1. Current Behavior Analysis

### 1.1 Data Model

An identity has this shape (from `core/registry.py`, line 103):

```python
{
    "identity_id": "uuid",
    "name": "string | null",           # Human-readable name, or null for unnamed
    "state": "INBOX | PROPOSED | CONFIRMED | CONTESTED | REJECTED | SKIPPED",
    "anchor_ids": ["face_id", ...],    # Confirmed faces (participate in fusion math)
    "candidate_ids": ["face_id", ...], # Suggested matches (not yet confirmed)
    "negative_ids": ["face_id", ...],  # Explicitly rejected faces/identities
    "version_id": 1,
    "created_at": "ISO8601",
    "updated_at": "ISO8601",
    "provenance": {"job_id": ..., "source": ...},
    "merged_into": "target_identity_id"  # Only present on absorbed identities
}
```

The global history is an append-only event log (separate from the identity dict):

```python
{
    "event_id": "uuid",
    "timestamp": "ISO8601",
    "identity_id": "uuid",       # Which identity this event belongs to
    "action": "merge",
    "face_ids": [],
    "user_source": "web | manual_search",
    "confidence_weight": 1.0,
    "previous_version_id": int,
    "metadata": {
        "source_identity_id": "uuid",
        "faces_merged": int
    }
}
```

### 1.2 Merge Mechanics (What Happens Today)

**File:** `core/registry.py`, `merge_identities()` method (line 234-355)

When `merge_identities(source_id, target_id, ...)` is called:

1. **Validation** (non-negotiable): `validate_merge()` checks co-occurrence. If any face of the source appears in the same photo as any face of the target, the merge is blocked. This is a hard safety invariant.

2. **Already-merged check**: If `source.get("merged_into")` is set, merge is rejected with `"already_merged"`.

3. **Face transfer**: ALL faces are moved from source to target:
   - Source `anchor_ids` are appended to target `anchor_ids` (deduped)
   - Source `candidate_ids` are appended to target `candidate_ids` (deduped)
   - Source `negative_ids` are appended to target `negative_ids` (deduped)

4. **Source soft-delete**: The source identity gets `merged_into = target_id` and an updated timestamp. It is NOT deleted from the registry dict, but is filtered out of `list_identities()` by default (line 207-208).

5. **Target version bump**: `target.version_id` is incremented and timestamp updated.

6. **Event recorded**: A MERGE event is appended to the global history with `identity_id = target_id` and metadata containing `source_identity_id`.

### 1.3 Which Identity's Name Is Kept?

**The target identity's name is kept. The source identity's name is ignored.**

The merge function (line 234-355) does not touch the `name` field at all. It only moves face lists and sets `merged_into` on the source. Whatever name the target had before the merge, it keeps. Whatever name the source had, it is preserved on the soft-deleted source record but is invisible to the UI (since merged identities are filtered from all listings).

### 1.4 Which Identity's Faces Are Kept?

Both. Source faces are appended to the target's face lists. The source retains its face lists in the soft-deleted record but they are effectively unused.

### 1.5 Is Anything Deleted?

No hard deletes. The source identity is soft-deleted via the `merged_into` field. It remains in `_identities` and can be retrieved with `include_merged=True` on `list_identities()`.

### 1.6 What Is the Undo Mechanism?

**There is no functional undo for merges.**

The `undo()` method (line 1001-1088) handles PROMOTE, REJECT, and STATE_CHANGE events. It has no handler for MERGE events. If the `undo()` function encounters a MERGE event as the most recent action, it would:
- Record the event as "undone"
- Bump the version
- But NOT actually reverse the merge (faces stay on target, source stays soft-deleted)

The UX Principles doc (`docs/canonical/UX_PRINCIPLES.md`, line 11) states: "Merges can be undone via detach." This means the intended recovery path is manual: an admin would need to individually detach each face that was merged in, which is tedious and error-prone for multi-face merges.

### 1.7 What Happens to Embeddings?

Nothing. Embeddings are immutable (stored in `data/embeddings.npy`). The merge only affects the identity metadata layer that references face IDs. The PFE vectors are never modified. This is an explicit design invariant from ADR-004.

### 1.8 Merge Direction: Source and Target

The merge direction is explicit in the API: `POST /api/identity/{target_id}/merge/{source_id}`

- **target_id**: The identity that survives (absorbs faces, keeps its name)
- **source_id**: The identity that is absorbed (gets `merged_into` set, filtered from listings)

### 1.9 How the UI Triggers a Merge

There are two merge entry points in the UI:

#### A. Find Similar (Neighbor Cards)

**File:** `app/main.py`, `neighbor_card()` (line 2051-2105)

When a user clicks "Find Similar" on identity card X, the system computes nearest neighbors via `core/neighbors.py:find_nearest_neighbors()`. Each neighbor card has a "Merge" button:

```
hx_post=f"/api/identity/{target_identity_id}/merge/{neighbor_id}"
```

Here, `target_identity_id` is the identity the user is currently viewing (the one they clicked "Find Similar" on), and `neighbor_id` is the similar identity found by the algorithm.

**Critical insight:** In Focus Mode, the user reviews INBOX items (often unnamed "Unidentified Person" identities). When they click "Find Similar" on an unnamed identity and find a named CONFIRMED identity as a neighbor, clicking "Merge" makes the unnamed identity the TARGET and the named identity the SOURCE. The named identity gets absorbed into the unnamed one, losing the name.

#### B. Manual Search

**File:** `app/main.py`, `search_result_card()` (line 2107-2156)

The manual search panel (available within the neighbors sidebar) lets the user search identities by name. Search results show a "Merge" button:

```
hx_post=f"/api/identity/{target_identity_id}/merge/{result_id}?source=manual_search"
```

Same direction problem: the currently-viewed identity is always the target.

#### C. Browse Mode

**File:** `app/main.py`, `identity_card()` (line ~2240-2420)

Browse mode identity cards also have a "Find Similar" button that loads the same neighbors sidebar. The same merge direction applies: the card being viewed is always the target.

### 1.10 What Data Fields Are Affected by Merge?

| Field | Target | Source |
|-------|--------|--------|
| `name` | Unchanged | Unchanged (preserved on soft-deleted record) |
| `state` | Unchanged | Unchanged |
| `anchor_ids` | Source anchors appended | Unchanged |
| `candidate_ids` | Source candidates appended | Unchanged |
| `negative_ids` | Source negatives appended | Unchanged |
| `version_id` | Incremented by 1 | Unchanged |
| `updated_at` | Set to now | Set to now |
| `merged_into` | Not set | Set to `target_id` |

---

## 2. Problems with Current Behavior

### 2.1 Named Data Overwritten When Merging From Focus Mode

This is the primary bug motivating this design. The UI always makes the currently-viewed identity the merge target. In Focus Mode, users review INBOX items which are typically unnamed. When they find a named CONFIRMED neighbor and click "Merge":

- The unnamed INBOX identity becomes the target (survives)
- The named CONFIRMED identity becomes the source (absorbed, soft-deleted)
- Result: the name is lost, the faces end up under an unnamed identity

This makes Focus Mode nearly useless for its intended purpose (processing the inbox by associating unnamed faces with known identities).

### 2.2 No Functional Merge Undo

Despite the UX Principles document stating "Merges can be undone via detach," there is no automated undo-merge operation. The `undo()` function does not handle MERGE events. An admin would need to:

1. Know which faces were added by the merge
2. Manually detach each one
3. Hope the detached faces end up in the right new identity

This is fragile and error-prone, especially for merges that transferred many faces.

The merge confirmation dialog says "This cannot be undone" (line 2099, 2158), which is honest but violates the Reversible Merges forensic invariant from CLAUDE.md.

### 2.3 Merge Direction Is Implicit and Context-Dependent

The merge direction is determined entirely by which card the user is viewing, not by any property of the identities themselves. There is no intelligence about which identity "should" be the target based on:
- Which has a name vs. unnamed
- Which has more faces (more evidence)
- Which has a higher state (CONFIRMED vs. INBOX)
- Which was human-curated vs. auto-generated

### 2.4 No Conflict Resolution for Two-Named Merges

If both identities have names, the merge silently keeps the target's name and discards the source's name. There is no UI for the admin to choose which name to keep, or to know that a name was lost.

### 2.5 Source State Is Not Considered

Merging a CONFIRMED identity (high trust) into an INBOX identity (low trust) does not elevate the target's state. The target remains INBOX even though it now contains confirmed data.

### 2.6 Merge History Not Stored on Identity

The MERGE event is recorded in the global history log, but the identity record itself has no `merge_history` field. To reconstruct what happened, you must scan the entire event log. There is no quick way to answer "what was merged into this identity and when?"

---

## 3. Proposed Non-Destructive Merge System

### 3.1 Core Principles

1. **Never delete data**: Merges must be reversible. Source identities are preserved (soft-delete via `merged_into` is already correct).
2. **Named data always wins over unnamed**: When one identity has a name and the other does not, the named identity must be the target regardless of UI context.
3. **Conflicts surfaced, not auto-resolved**: When both identities have names, the admin must explicitly choose.
4. **Metadata merges additively**: Negative evidence, face lists, and provenance are combined, never discarded.
5. **State promotion**: If the source has a higher-trust state than the target, the target should be promoted.

### 3.2 Merge Direction Logic

The merge endpoint should implement smart direction resolution. The UI can still send `target_id` and `source_id` based on context, but the backend may swap them based on heuristics:

#### Rule 1: Named wins over unnamed
If one identity has a name and the other does not, the named identity becomes the target regardless of what the UI sent.

```
CONFIRMED "Morris Mazal" + INBOX (unnamed) -> Target: "Morris Mazal"
```

#### Rule 2: Higher state wins
If names are equal (both null, or resolved via conflict UI), the identity with the higher-trust state becomes the target.

State priority: CONFIRMED > PROPOSED > INBOX > SKIPPED

```
CONFIRMED (unnamed) + INBOX (unnamed) -> Target: CONFIRMED identity
```

#### Rule 3: More faces wins (tiebreaker)
If state is equal and both are unnamed, the identity with more faces (more evidence) becomes the target.

#### Rule 4: Two-named conflict requires resolution
If both identities have names, the merge cannot proceed without explicit name resolution from the admin. The endpoint returns a conflict response that triggers a resolution UI.

### 3.3 Data Model Changes

Add a `merge_history` field to the identity schema:

```python
{
    "identity_id": "person_042",
    "name": "Morris Mazal",
    "state": "CONFIRMED",
    "anchor_ids": ["face_001", "face_002", "face_003"],
    "candidate_ids": [],
    "negative_ids": [],
    "version_id": 5,
    "created_at": "2026-01-15T10:00:00Z",
    "updated_at": "2026-02-05T22:00:00Z",
    "provenance": {...},
    "merge_history": [
        {
            "merge_event_id": "uuid",
            "timestamp": "2026-02-05T22:00:00Z",
            "action": "merged_in",
            "source_id": "person_214",
            "source_name": null,
            "source_state": "INBOX",
            "faces_added": {
                "anchors": ["face_003"],
                "candidates": [],
                "negatives": []
            },
            "direction_auto_corrected": true,
            "merged_by": "admin@example.com"
        }
    ]
}
```

Key fields in each merge history entry:
- **`merge_event_id`**: Links to the global history event for cross-reference
- **`source_id`**: The identity that was absorbed
- **`source_name`**: Preserved for audit (even if null)
- **`source_state`**: Preserved for audit
- **`faces_added`**: Exact list of faces that came from the source, split by type (anchors, candidates, negatives) for precise undo
- **`direction_auto_corrected`**: Boolean flag indicating whether the backend swapped the UI's intended direction (important for transparency/debugging)
- **`merged_by`**: User who authorized the merge

### 3.4 Undo Mechanism

#### Storage
The `merge_history` on each identity contains all information needed to reverse a merge.

#### "Undo Last Merge" Button
Each identity page should show an "Undo Last Merge" button when `merge_history` is non-empty. Clicking it:

1. Reads the most recent entry in `merge_history`
2. Removes the `faces_added.anchors` from target's `anchor_ids`
3. Removes the `faces_added.candidates` from target's `candidate_ids`
4. Removes the `faces_added.negatives` from target's `negative_ids`
5. Retrieves the source identity (by `source_id`)
6. Clears `source.merged_into`
7. Restores the source's original face lists (they are still intact because the source was soft-deleted, not modified)
8. Removes the entry from `merge_history`
9. Records an UNDO_MERGE event in the global history

#### Why Source Face Lists Are Intact
The current code appends source faces to the target but does NOT clear them from the source (line 305-315: it only appends to target, never removes from source). Combined with the `merged_into` soft-delete, the source's face lists are preserved. This means undo can use the source's own data as the authoritative record rather than relying solely on `merge_history`.

This is a fortunate consequence of the current implementation and should be explicitly preserved as an invariant.

#### Undo Constraints
- Only the most recent merge can be undone (stack order) unless we implement full merge chain reversal
- If the target was subsequently merged into another identity, undo is blocked (chain dependency)
- If individual faces from the merge were subsequently detached, undo should handle partial state (only undo what remains)

### 3.5 Conflict Resolution UI

When merging two named identities (Rule 4), the API returns a 409 Conflict with a payload indicating name conflict:

```json
{
    "status": "name_conflict",
    "identity_a": {"id": "...", "name": "Morris Mazal", "face_count": 5},
    "identity_b": {"id": "...", "name": "Maurice Mazal", "face_count": 2}
}
```

The UI renders a modal with:
- Side-by-side thumbnails of both identities
- Radio buttons: Keep "Morris Mazal" / Keep "Maurice Mazal" / Enter custom name
- "Merge" button that re-sends the request with `resolved_name` parameter
- "Cancel" button

### 3.6 State Promotion on Merge

When faces from a CONFIRMED identity are merged into a lower-state identity, the target should be promoted:

| Target State | Source State | Result |
|-------------|-------------|---------|
| INBOX | CONFIRMED | Target becomes CONFIRMED |
| INBOX | PROPOSED | Target becomes PROPOSED |
| PROPOSED | CONFIRMED | Target becomes CONFIRMED |
| CONFIRMED | INBOX | Target stays CONFIRMED |
| CONFIRMED | PROPOSED | Target stays CONFIRMED |

Rule: `target.state = max(target.state, source.state)` by trust ordering.

This ensures that merging a named CONFIRMED identity's faces into a target does not demote the trust level.

---

## 4. Migration Plan

### 4.1 Schema Migration

Add empty `merge_history: []` to all existing identities. This is additive and non-destructive.

```python
# scripts/migrate_merge_history.py (with --dry-run)
for identity in registry._identities.values():
    if "merge_history" not in identity:
        identity["merge_history"] = []
```

### 4.2 Backward Compatibility

- All existing code that reads identities will ignore the new `merge_history` field (dict access by key)
- The `list_identities()` filter on `merged_into` is unchanged
- Existing merged identities remain soft-deleted
- No existing data is deleted or modified

### 4.3 Retroactive History

For identities that were previously merged, we can optionally reconstruct `merge_history` from the global event log:

```python
for event in registry._history:
    if event["action"] == "merge":
        target_id = event["identity_id"]
        source_id = event["metadata"]["source_identity_id"]
        # Reconstruct merge_history entry from event data
```

This is optional because the source identities still retain their face lists (per section 3.4), so even without history entries, we have the data needed for audit.

---

## 5. API Design

### 5.1 Merge Endpoint (Enhanced)

```
POST /api/identity/{target_id}/merge/{source_id}
```

Query parameters:
- `source`: Origin of merge request (`"web"` or `"manual_search"`) [existing]
- `resolved_name`: Name to use when both identities have names [new]

Response codes:
- **200**: Merge successful (returns updated target card + OOB removal of source) [existing behavior]
- **409 (name_conflict)**: Both identities have names, need resolution [new]
- **409 (co_occurrence)**: Identities share a photo [existing]
- **409 (already_merged)**: Source already absorbed [existing]
- **404**: Identity not found [existing]
- **401/403**: Not admin [existing]

Changes from current behavior:
1. Backend checks both identities' names and states
2. If auto-correction is needed (unnamed target + named source), backend swaps direction silently
3. If both are named, returns 409 with `name_conflict` status and identity details
4. Merge records `merge_history` entry on target
5. Target state is promoted if source had higher state

### 5.2 Undo Merge Endpoint (New)

```
POST /api/identity/{identity_id}/undo-merge
```

Response codes:
- **200**: Undo successful (returns updated target card + toast)
- **409**: Cannot undo (no merge history, or chain dependency)
- **404**: Identity not found
- **401/403**: Not admin

Process:
1. Read the last entry in `identity.merge_history`
2. Validate undo is possible (source still exists, no chain dependencies)
3. Remove merged faces from target
4. Clear `merged_into` on source
5. Remove the `merge_history` entry
6. Record UNDO_MERGE event in global history
7. Return updated target card

### 5.3 Differences from Current Endpoints

| Aspect | Current | Proposed |
|--------|---------|----------|
| Direction | UI-determined, never corrected | Backend auto-corrects based on name/state |
| Name conflict | Silently keeps target name | Returns 409, requires explicit resolution |
| Undo | Not supported (no handler in `undo()`) | Dedicated endpoint with full reversal |
| State promotion | Not performed | Target promoted to max(target, source) state |
| merge_history | Not stored on identity | Stored per-merge with full detail |
| Confirmation text | "This cannot be undone" | "This can be undone from the identity page" |

---

## 6. Test Plan

### 6.1 Direction Auto-Correction Tests

1. **Merge unnamed into named**: INBOX unnamed is viewed, CONFIRMED "Morris Mazal" is neighbor. Click merge. Assert: "Morris Mazal" is the surviving identity (direction auto-corrected), unnamed identity has `merged_into` set.

2. **Merge named into unnamed (no correction needed)**: CONFIRMED "Morris Mazal" is viewed, INBOX unnamed is neighbor. Click merge. Assert: "Morris Mazal" is still the target, unnamed absorbed. No auto-correction flag.

3. **Merge two unnamed (more faces wins)**: INBOX with 3 faces is viewed, INBOX with 1 face is neighbor. Assert: identity with 3 faces is target.

4. **Merge two unnamed (equal faces)**: Both INBOX with 1 face. Assert: the original target_id from the UI is kept (no correction).

### 6.2 Name Conflict Tests

5. **Merge two named identities**: CONFIRMED "Morris Mazal" + CONFIRMED "Maurice Mazal". Assert: returns 409 name_conflict with both identities' details.

6. **Resolve name conflict**: Re-send merge with `resolved_name="Morris Mazal"`. Assert: merge succeeds, target has resolved name.

7. **Resolve with custom name**: Re-send with `resolved_name="Morris (Maurice) Mazal"`. Assert: merge succeeds with custom name.

### 6.3 Undo Tests

8. **Undo single merge**: Merge A into B. Undo on B. Assert: A is restored (no `merged_into`), A's faces removed from B, B's `merge_history` is empty.

9. **Undo preserves original faces**: B had face_001 before merge, A added face_002. After undo, B has only face_001, A has only face_002.

10. **Undo restores source name**: A was named "Morris Mazal" before being merged as source. After undo, A is restored with name intact.

11. **Undo blocked when chain exists**: A merged into B, then B merged into C. Undo on C should work (reverses B merge). But undo on B should be blocked (B is soft-deleted, cannot undo while merged_into C).

12. **Undo with partial detach**: A merged 3 faces into B. Admin then detached 1 of those faces. Undo should handle gracefully (only remove 2 remaining faces from B, not crash looking for the 3rd).

### 6.4 State Promotion Tests

13. **CONFIRMED source into INBOX target**: After merge (with auto-correction making CONFIRMED the target), the surviving identity is CONFIRMED.

14. **INBOX source into CONFIRMED target**: Target stays CONFIRMED.

15. **PROPOSED source into INBOX target**: Target becomes PROPOSED.

### 6.5 merge_history Tests

16. **merge_history populated on merge**: After merging A into B, B.merge_history has one entry with correct source_id, faces_added, timestamp.

17. **merge_history records direction correction**: When auto-corrected, `direction_auto_corrected` is True.

18. **merge_history cleared on undo**: After undo, the corresponding entry is removed from merge_history.

### 6.6 Regression Tests

19. **Existing CONFIRMED identities unaffected**: Run migration, verify all existing identities have `merge_history: []` and all other fields unchanged.

20. **Co-occurrence block still works**: Merge blocked when faces share a photo (existing invariant preserved).

21. **Already-merged block still works**: Cannot merge an already-absorbed identity (existing behavior preserved).

22. **Merged identities still excluded from search**: `search_identities()` still filters out `merged_into` identities.

23. **Merged identities still excluded from list**: `list_identities()` with default `include_merged=False` still works.

### 6.7 Permission Tests

24. **Merge requires admin**: Non-admin gets 401/403.
25. **Undo-merge requires admin**: Non-admin gets 401/403.

### 6.8 UI Content Tests

26. **Undo button visible when merge_history non-empty**: Identity page shows "Undo Last Merge" button.
27. **Undo button hidden when merge_history empty**: No button on identities without merges.
28. **Confirmation text updated**: "This cannot be undone" replaced with "This can be undone from the identity page."
29. **Name conflict modal renders**: When 409 name_conflict returned, modal shows both names and resolution options.

---

## Appendix A: Code References

| File | Line(s) | What |
|------|---------|------|
| `core/registry.py` | 234-355 | `merge_identities()` method |
| `core/registry.py` | 1328-1373 | `validate_merge()` function |
| `core/registry.py` | 650-738 | `detach_face()` method (current "manual undo") |
| `core/registry.py` | 1001-1088 | `undo()` method (no MERGE handler) |
| `core/registry.py` | 189-213 | `list_identities()` with `include_merged` filter |
| `core/registry.py` | 1250-1325 | `search_identities()` with merged filter |
| `core/neighbors.py` | 44-98 | `find_nearest_neighbors()` |
| `app/main.py` | 2051-2105 | `neighbor_card()` UI with merge button |
| `app/main.py` | 2107-2156 | `search_result_card()` UI with merge button |
| `app/main.py` | 3427-3499 | `POST /merge` route handler |
| `app/main.py` | 1152-1309 | `identity_card_expanded()` (Focus Mode) |
| `tests/test_safety.py` | 304-390 | Existing merge tests |
| `tests/test_registry.py` | 757-797 | Search excludes merged identities test |

## Appendix B: Forensic Invariants Checklist

This design must respect all forensic invariants from CLAUDE.md:

| Invariant | Status |
|-----------|--------|
| Immutable Embeddings | Respected: merge only touches identity metadata, never PFE vectors |
| Reversible Merges | Addressed: `merge_history` + undo endpoint provides full reversal |
| No Silent Math | Respected: `core/neighbors.py` algorithmic logic is not modified |
| Conservation of Mass | Respected: no face is ever deleted, only moved between identities |
| Human Authority | Enhanced: named/confirmed data (human decisions) takes priority in auto-correction |

## Appendix C: Open Questions

1. **Should auto-correction be transparent?** When the backend swaps merge direction, should the UI show a toast like "Direction auto-corrected: named identity kept as target"? Or should it be silent?

2. **Undo depth**: Should we support undoing multiple merges in sequence (full stack), or only the most recent? Stack undo is more complex but more useful for "oops I merged the wrong 3 things."

3. **Variance explosion guardrail**: ADR-004 (line 112-121) specifies a variance explosion check before merges. This is not currently implemented in the code. Should it be added as part of this work?

4. **Event log vs. merge_history redundancy**: The merge is recorded both in the global event log and the proposed `merge_history` field. Is the duplication acceptable, or should `merge_history` be the sole record? The global event log is append-only by design (ADR-004), so both serve different purposes: event log for audit, merge_history for operational undo.

5. **Focus Mode flow after auto-correction**: If the unnamed INBOX identity is absorbed (becomes source) due to auto-correction, what should Focus Mode show next? The named target's updated card, or the next INBOX item? Showing the named target would be confusing ("I was reviewing inbox, now I'm looking at a confirmed person"). Showing the next inbox item is more natural but the user might want to verify the merge result.
