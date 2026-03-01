# Session 81C Analysis — Tree + UX Fixes

## Issue 1: Moise's Tree Shows Only 2 Nodes (Should Show ~16)

### Root Cause: Truncated identity IDs in gedcom_matches.json

`gedcom_matches.json` has truncated identity IDs for some entries:
- `fd43c9dd` should be `fd43c9dd-8558-4305-8bda-90c3f320daac` (Boulissa Pizanti Capeluto)
- `2cf08b25` should be `2cf08b25-075c-41a8-a20d-d03686aafd06` (Victoria Cukran Capeluto)

When `_build_tree_adjacency()` builds xref_to_uuid from gedcom_face_links, it uses these SHORT IDs.
The `resolve()` function then maps `@I132127402466@` → `fd43c9dd` (truncated).
But `_build_tree_person_lookup()` stores identities with FULL UUIDs.
So when building nodes, `lookup.get('fd43c9dd')` returns None — the person is "invisible."

Additionally, `@I132127402446@` (Nissim Capeluto, Moise's mother/father) is NOT in gedcom_matches at all.

### Fix Required (app/main.py: _build_tree_adjacency)

The `_build_tree_adjacency` function at line 18900 should also use the identity registry to find
GEDCOM xref mappings, not just `_load_gedcom_face_links()`. Specifically:
1. Build xref_to_uuid from gedcom_matches.json (which has the confirmed links)
2. Use FULL identity IDs (fix the truncated ones in gedcom_matches.json)
3. For unresolved xrefs, fall through to GEDCOM individual lookup

Alternative simpler fix: make `_build_tree_adjacency` also build xref_to_uuid from
`gedcom_matches.json` directly (not just Supabase gedcom_face_links).

### Data to Fix: gedcom_matches.json

Fix truncated IDs:
- `fd43c9dd` → `fd43c9dd-8558-4305-8bda-90c3f320daac`
- `2cf08b25` → `2cf08b25-075c-41a8-a20d-d03686aafd06`

### Verification

After fix, the tree API for photo fb6a846971b30f4b should return ~16 nodes including:
- All 9 photo people (Moise, Vida, Anita, Victor, Victoria, Nace, Big Leon, Laura, Selma)
- Boulissa Pizanti (parent of Moise + Big Leon)
- Victoria Cukran (Moise's wife)
- Other connecting GEDCOM individuals
- Betty Capeluto (Moise's daughter) via expansion

## Issue 2: Photo Cycling Arrows Too Small

In `app/static/js/family-tree.js`:
- Arrow circle radius: 14px (28px diameter) — BELOW 44px WCAG minimum
- Need to increase to r=22 (44px diameter)
- Lines ~838-872 in family-tree.js

## Issue 3: Time Slider Issues

The slider uses temporal distribution across lifespan, progressing left→right.
Need Chrome verification that:
- Oldest photos on left, newest on right
- Sliding all the way left and right works correctly
- Photos actually change when sliding

## Issue 4: Expand/Collapse for Tree Branches

The expand/collapse feature exists (pill buttons with Parents/Children/Siblings).
Need Chrome verification that it works for toggling branches on/off.

## People in Photo fb6a846971b30f4b

| UUID | Name |
|------|------|
| 925904af... | Moise Capeluto |
| 843aaa8e... | Vida Capeluto |
| 1547d786... | Anita Capeluto Franco |
| 7cba61d1... | Victor Capelluto |
| 964f4c07... | Victoria Capuano Capeluto |
| 9e5f05cf... | Nace Capeluto |
| b6d9ea5b... | Big Leon Capeluto |
| 35b997f8... | Laura Franco Capelluto |
| cca5f7ff... | Selma Capeluto |

## Family Relationships

- Big Leon + Victoria Capuano = parents of Nace, Selma, Anita, Betty
- Moise = Big Leon's BROTHER (shared parents: @I132127402446@ and Boulissa/fd43c9dd)
- Moise's wife = Victoria Cukran (2cf08b25)
- Moise's daughter = Betty Capeluto (c9bd1c83)
- Vida = another sibling of Moise/Big Leon
- Victor = another sibling
- Laura = spouse of one of the siblings
