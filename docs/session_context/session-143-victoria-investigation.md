# Session 143 Track D: Victoria Capeluto "Conflicting Face Assignment" Investigation

**Date:** 2026-03-27
**Investigator:** Claude Opus 4.6 subagent (Track D)

## Summary

Victoria Capeluto's person page reportedly shows "Needs review" / "Conflicting face assignment" badges. Investigation found **no active data conflicts** in the Supabase source of truth. The likely root cause is either (a) a stale embeddings cache with different bbox data than Supabase, or (b) the report was based on a different page view (photo viewer context, not person page).

## Findings

### 1. Victoria's Identity Data

There are **two** Victoria identities, both CONFIRMED:

| Field | Victoria Capuano Capeluto | Victoria Cukran Capeluto |
|-------|--------------------------|--------------------------|
| ID | `964f4c07-e9e5-43e2-933c-7fd8bfd234b8` | `2cf08b25-075c-41a8-a20d-d03686aafd06` |
| State | CONFIRMED | CONFIRMED |
| anchor_ids | 7 | 10 |
| candidate_ids | 8 | 7 |
| negative_ids | 1 | 2 |
| Shared photos | 4 photos shared between them |

**Observation:** Both Victorias have significant `candidate_ids` lists. However, candidate_ids alone do NOT trigger the badge.

### 2. Badge Trigger Logic

The "Conflicting face assignment" / "Needs review" badges are rendered in two places:

**Person page** (`app/person_routes.py`, `_photo_context_conflict()`):
- Returns `True` if the identity's face state is "REJECTED" or "CONTESTED" (neither Victoria is)
- Returns `True` if the person's face bbox overlaps (IoU >= 0.8) with another identity's face in the same photo

**Photo viewer** (`app/page_routes.py`):
- Uses IoU >= 0.85 threshold for bbox conflict detection
- Shows "Needs review" only for unidentified/unconfirmed faces with bbox conflicts
- Identified faces with bbox conflicts show their name but with a "Conflicting face assignments" tooltip

**Key detail:** `get_identity_for_face()` looks up faces in BOTH `anchor_ids` AND `candidate_ids`. If two identities both claim faces in the same photo, and those bboxes overlap, the badge triggers.

### 3. No Actual Conflicts Found

- **Multi-claimed faces:** 0 out of 1,768 non-merged identities (checked with full pagination)
- **Bbox overlaps in Victoria's photos:** 0 (checked all 15 photos for Victoria Capuano, all 17 for Victoria Cukran)
- **Shared photos between Victorias:** 4 photos, but their faces are in completely different positions

### 4. CONFIRMED Identities with candidate_ids (Systemic Finding)

**23 CONFIRMED identities still have candidate_ids**, meaning faces that were ML-proposed but never explicitly confirmed or rejected by admin. These include major identities:

| Identity | Anchors | Candidates |
|----------|---------|------------|
| Big Leon Capeluto | 13 | 12 |
| Esther Burd Fox | 143 | 1 |
| Roland Fox | 57 | 31 |
| Victoria Capuano Capeluto | 7 | 8 |
| Victoria Cukran Capeluto (linked to `2cf08b25`) | 10 | 7 |
| Vida Capeluto | 0 | 15 |
| Moise Capeluto | 11 | 7 |
| Betty Capeluto | 5 | 7 |
| Victor Capelluto | 1 | 7 |
| (and 14 more) | | |

**This is not a bug per se**, but these candidate faces are in limbo: they show on the person page (because `get_identity_for_face` includes candidates), but they haven't been explicitly confirmed. Some identities like Vida Capeluto have 0 anchors and 15 candidates -- meaning ALL their faces are unconfirmed.

### 5. Possible Explanations for the Reported Badge

1. **Embeddings-based photo cache has different bboxes:** The `_photo_cache` is built from `embeddings.npy`, not from Supabase `photo_faces`. If the embeddings file has slightly different bbox coordinates (e.g., from a different detection run), the IoU calculation could yield different results than what Supabase shows.

2. **The badge was observed in the PHOTO VIEWER, not the person page:** The photo viewer (`page_routes.py`) has its own conflict detection at IoU >= 0.85, and shows "Needs review" for unidentified faces with overlaps. If someone viewed a photo containing Victoria alongside an unidentified overlapping face, they might see the badge in that context.

3. **Transient state:** A previous session may have created a temporary conflict that was since resolved. The report may be outdated.

## Recommendations

### Immediate (no code changes needed)
1. **Verify on production:** Navigate to Victoria Capuano Capeluto's person page and check if the badge is currently showing. If not, the issue may have been resolved by a previous session's data repair.

### Short-term UI improvement
2. **Consider promoting candidates to anchors for CONFIRMED identities:** The 23 CONFIRMED identities with candidate_ids represent a data hygiene issue. When an admin confirms an identity, all its candidate_ids should ideally be promoted to anchor_ids (or presented for explicit accept/reject). This is a workflow gap, not a bug.

### Medium-term
3. **Add a "Confirm all candidates" button** on the person page for CONFIRMED identities that still have candidates. This would let the admin batch-accept ML proposals that are clearly correct.
4. **Distinguish candidate vs anchor faces visually** on the person page -- e.g., a subtle "Proposed" badge on candidate faces so admin knows they haven't been explicitly confirmed.

## Files Referenced
- `app/person_routes.py:119-152` -- `_photo_context_conflict()` function
- `app/page_routes.py:11390-11424` -- Photo viewer bbox conflict detection
- `app/main.py:4277-4297` -- `get_identity_for_face()` includes both anchor and candidate faces
- `app/main.py:4130-4183` -- `load_embeddings_for_photos()` builds photo cache from embeddings
