# PRD-025: Compare — Functional Rebuild

**Status:** IN PROGRESS
**Priority:** P0 — Community member blocked
**Session:** 85
**Date:** 2026-03-03
**Supersedes:** PRD-016 (Compare Faces Redesign)
**Origin:** Claude Benatar feedback (2026-03-02) — "See if you can find a match with this picture"

## Problem Statement

Compare is broken for the primary use case: a community member has a family photo and
wants to check if a specific known person (Isaac Cohen) is in it. The current
implementation fails in three critical ways:

1. **Photos don't persist**: Uploads go to a separate `uploads/compare/` silo, never
   appearing in the Photos section. Identities are never created for detected faces.
2. **No way to compare against a specific person**: The upload flow compares against ALL
   archive faces, producing a confusing "20 matches found" list of "Unlikely match"
   entries. No way to say "compare against Isaac Cohen specifically."
3. **Result page lacks context**: No uploaded photo visible, no face overlays, no way to
   tell which face was compared, no context about how the score ranks against existing matches.

## Use Cases

### UC-1: "Is [Person X] in this photo?" (PRIMARY — Mode B)
User has a family photo and a hypothesis about who's in it.
1. Upload photo → faces detected, photo persists to archive
2. Search for "Isaac Cohen" → select him
3. See per-face match scores against Isaac Cohen
4. See context: how these scores compare to Isaac Cohen's existing top matches
5. Share interactive comparison link with community member

### UC-2: "Who is in this photo?" (Mode B — General)
User has a photo, no hypothesis.
1. Upload photo → faces detected, photo persists to archive
2. Each face compared against all archive faces
3. Top matches shown per face with confidence tiers

### UC-3: "Compare two people in the archive" (Mode A)
User wants to compare two known people.
1. Search for Person A → select
2. Search for Person B → select
3. See side-by-side comparison with match score

### UC-4: "Are the same people in both photos?" (Mode C)
User has two photos.
1. Upload Photo A → persists, faces detected
2. Upload Photo B → persists, faces detected
3. Cross-comparison: every face in A scored against every face in B
4. Results ranked by match strength

## User Flows

### Flow 1: Upload vs. Specific Person (UC-1 — Isaac Cohen Test Case)

```
/compare
  ├─ [Upload a Photo] ← drag/drop or file picker
  │   └─ Photo uploads → SSE progress → faces detected
  │      └─ Photo saved to archive (same pipeline as Upload page)
  │      └─ 5 INBOX identities created (one per face)
  │      └─ Face crops generated + stored
  │
  ├─ [Results] ← initial results showing top archive matches per face
  │   └─ Uploaded photo shown with face bounding box overlays
  │   └─ Face selector: click any face to see its matches
  │   └─ Top 5 archive matches per selected face
  │
  ├─ [Compare against specific person] ← search box
  │   └─ Type "Isaac Cohen" → autocomplete → select
  │   └─ Isaac Cohen's crop shown as reference
  │   └─ ALL 5 faces scored against Isaac Cohen
  │   └─ Context: "Isaac Cohen's closest archive match is at distance 1.22 (Low)"
  │   └─ Scores sorted: best match first
  │   └─ Color-coded: green (Strong), amber (Possible), gray (Unlikely)
  │
  └─ [Share] ← generates shareable URL
      └─ /compare/result/{id} shows:
         ├─ Uploaded photo with face overlays
         ├─ Isaac Cohen's crop as reference
         ├─ Per-face score table
         ├─ Context about score quality
         ├─ "Do you recognize anyone?" response form
         └─ OG tags with side-by-side face image
```

### Flow 2: Upload vs. All Archive (UC-2)

Same as Flow 1 but skip the "Compare against specific person" step.
Initial results show top archive matches per face.

## Acceptance Criteria

### Foundation (Phase 2)
- [ ] Compare upload uses same pipeline as Upload page
- [ ] Photo saved to `raw_photos/` (not `uploads/compare/`)
- [ ] Photo appears in Photos section
- [ ] Face crops generated and stored in standard location
- [ ] INBOX identity created for each detected face
- [ ] Embeddings stored in embeddings cache

### Person-Specific Compare (Phase 3)
- [ ] After upload, user can search for a specific person by name
- [ ] Per-face match scores shown against selected person
- [ ] Context shows the person's existing top archive match distances
- [ ] Scores sorted by match strength (best first)
- [ ] Color-coded confidence tiers (green/amber/gray)
- [ ] Visual confidence bar alongside percentage

### Result Page (Phase 4)
- [ ] Uploaded photo visible with face bounding box overlays
- [ ] Selected reference person shown prominently
- [ ] Per-face match scores clearly displayed
- [ ] Multi-face selector (click different faces to see their matches)
- [ ] Admin sees raw distance scores
- [ ] Shareable URL works without authentication
- [ ] OG tags render with face images
- [ ] Mobile responsive at 375px

### Isaac Cohen Test Case (End-to-End)
- [ ] Upload 5-person family photo from `~/Downloads/claude_rhodesli_feedback/`
- [ ] 5 faces detected
- [ ] Photo appears in Photos section
- [ ] Search "Isaac Cohen" → select → per-face scores shown
- [ ] Context: Isaac Cohen's closest archive match is ~1.22
- [ ] Shareable link shows full interactive comparison
- [ ] Share link works in incognito (no auth required)

## Data Model

### Unified Upload (replaces _save_compare_upload)
Uses same data path as Upload page:
- `photo_index.json` entry (or Supabase photos table)
- `raw_photos/{filename}` on R2
- `crops/{identity_id}_0.jpg` on R2
- Identity entries in identities.json / Supabase

### Comparison Results (extends existing)
```json
{
  "results": {
    "<result_id>": {
      "result_id": "abc123def456",
      "created_at": "2026-03-03T...",
      "query_type": "upload_vs_person|upload_vs_all|archive_vs_archive",
      "photo_id": "...",
      "photo_url": "...",
      "faces": [
        {
          "face_id": "...",
          "identity_id": "...",
          "bbox": [x1, y1, x2, y2],
          "crop_url": "..."
        }
      ],
      "reference_person": {
        "identity_id": "...",
        "name": "Isaac Cohen",
        "crop_url": "...",
        "existing_top_matches": [
          {"name": "Unidentified Person 090", "distance": 1.22}
        ]
      },
      "comparisons": [
        {
          "face_idx": 0,
          "face_id": "...",
          "distance": 1.15,
          "confidence_pct": 42,
          "tier": "POSSIBLE MATCH"
        }
      ],
      "responses": []
    }
  }
}
```

## UX Design Notes

### Confidence Visualization (from UX research)
- **Dual encoding**: Colored bar + percentage + text label
- **Tiers**: 85%+ green "Very likely", 70-84% amber "Strong match", 50-69% blue "Possible", <50% gray "Unlikely"
- **Context line**: "Isaac Cohen's closest existing match is 1.22 (Low). Your best face scores 1.15."
- **Admin-only**: Raw distance shown in parentheses for admin users

### Result Page Layout
```
┌─────────────────────────────────────────┐
│ Face Comparison Result                   │
│ 5 faces compared against Isaac Cohen     │
├─────────────────────────────────────────┤
│ ┌─────────┐  ┌─────────┐               │
│ │ Uploaded │  │  Isaac   │  Reference   │
│ │  Photo   │  │  Cohen   │  Person      │
│ │ (faces   │  │  (crop)  │              │
│ │ overlaid)│  │          │              │
│ └─────────┘  └─────────┘               │
├─────────────────────────────────────────┤
│ Face 1: ██████████░░░░ 42% Possible     │
│ Face 2: ████░░░░░░░░░░ 22% Unlikely     │
│ Face 3: █████████████░ 58% Possible     │ ← Best match
│ Face 4: ██░░░░░░░░░░░░ 12% Unlikely     │
│ Face 5: ████████░░░░░░ 36% Unlikely     │
├─────────────────────────────────────────┤
│ Context: Isaac Cohen's closest archive   │
│ match is Unidentified Person 090 at      │
│ distance 1.22 (Low confidence).          │
│ Your best match (Face 3) scores 1.08.    │
├─────────────────────────────────────────┤
│ [Share with someone who might know]      │
│                                          │
│ Do you recognize anyone?                 │
│ [textarea] [Submit Response]             │
└─────────────────────────────────────────┘
```

## Out of Scope

- Feature-level similarity breakdown (eyes, nose, jawline)
- Composite OG image generation (nice to have, not required for v1)
- Mode A (Archive vs. Archive) — mostly works via Find Similar already
- Mode C (Upload vs. Upload) — `/compare/pair` exists, polish later
- Before/after slider overlay (better for photo restoration, not identity)
- Visual clue tagging (Civil War Photo Sleuth pattern — future)
- Real-time GPU inference on Railway (AD-187 defers this)

## Priority Order

1. Unified upload pipeline (foundation — nothing works without this)
2. Compare against specific person + search (the Claude Benatar use case)
3. Interactive result page with face overlays + context
4. Shareable result URL
5. Mobile responsive verification
