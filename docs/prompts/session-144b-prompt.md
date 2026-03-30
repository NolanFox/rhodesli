# Session 144b: Bug Fixes + Batch Completion + Temporal Co-Occurrence Foundation

## Context
Session 144 delivered GEDCOM import, context enrichment, 218/279 batch photos, and identity investigation.
See `docs/session_context/session-144b-context.md` for full predecessor context.

## Phase 0: Bug Fixes (PARALLEL — all independent)

### 0a: FB-007 Person Page Sort by Estimated Date (P1)
- **Bug**: "Sort: Earliest First" on person page doesn't sort by Gemini estimate
- **File**: `app/page_routes.py` — search for sort logic near photo gallery
- **Likely cause**: date_labels not loaded or `best_year_estimate` not used as sort key
- **Steps**:
  1. Trace the sort dropdown handler — what field does "Earliest First" sort by?
  2. Verify date_labels are loaded from Supabase for the person's photos
  3. If sorting by upload_date instead of best_year_estimate, fix the sort key
  4. Test: Albert Fox (199 photos spanning 1910s-1980s) should show 1910s photos first
  5. Add test for sort ordering
- **Browser verify**: Albert's person page with "Earliest First" selected

### 0b: 0% Display Bug for Family Resemblance (P1)
- **Bug**: Person 3772 showed "0% match" to Albert Fox when calibrator gives 27-32%
- **Codex finding**: The 0% doesn't match any current scorer. Likely stale/alternate display path.
- **Note**: Person 3772 is now merged into Albert, so this specific case is gone. But the bug affects other family resemblance matches.
- **Steps**:
  1. Search for confidence display formatting in identity_routes.py, page_routes.py, main.py
  2. Find where "0% match" badge is generated — check if it truncates/floors values
  3. Check if the "Manual Search" merge results use a different scorer than "Find Similar"
  4. Fix: ensure calibrated confidence is displayed consistently across all surfaces
  5. Test: verify a 27% confidence displays as "27% match" not "0% match"

### 0c: Person 3481 Multi-Claimed Faces (Data Repair)
- **Bug**: 3 faces from penny arcade strip are claimed by Persons 3481, 3485, and 3486
- **All 3 faces should belong ONLY to Person 3481**
- **Steps**:
  1. Query Supabase for anchor_ids of Persons 3481, 3485, 3486
  2. Identify the 3 face IDs (`inbox_0f38fc4ed157`, `inbox_a9836b90601f`, `inbox_ecd034168ebc`)
  3. Remove these face IDs from 3485 and 3486's anchor_ids
  4. Verify 3481 has all 3 and 3485/3486 have none (or are empty/merged)
  5. Snapshot before, verify after

## Phase 1: Batch Completion (SEQUENTIAL — after Phase 0)

### 1a: Run Remaining 61 Photos
- 279 total Albert+Esther photos - 218 processed = 61 remaining
- Budget: ~$3.36 at $0.055/photo
- Command:
  ```bash
  python scripts/batch_gemini_for_person.py \
    --identity "85546ebf-75b9-4971-a9d4-b2ce2271bc19" \
    --identity "65207728-9ee6-48c1-be68-a2da23354caf" \
    --skip-existing --max-cost 4.00
  ```
- **Verify first result**: `gedcom_context_sent: True`, spouse timeline in context
- All results write to Supabase (Lesson 162)

### 1b: Download + Process 2 R2-Only Photos
- 2 photos have no local file (R2-only). Download from R2 first:
  ```bash
  python scripts/download_from_r2.py --photo-ids <ids>
  ```
- Then run batch on them

### 1c: Verify Complete Coverage
- After batch: `SELECT count(*) FROM date_labels` should be ≥279
- `SELECT count(*) FROM date_labels WHERE data->>'gedcom_context_sent' = 'true'` should be ≥275
- Any gaps → investigate and re-run

## Phase 2: PRD-059 Temporal Co-Occurrence — Event Grouping (~3h)

### Design: Event Clustering
**This is the core new feature for 144b.** User explicitly wants this.

Group photos into "events" (same occasion/timeframe) using:
1. **Date proximity**: Photos with `best_year_estimate` within ±2 years
2. **Shared faces**: ≥2 faces in common suggests same event
3. **Location match**: Same `location_estimate` strengthens grouping

**Schema**: New `photo_events` table or JSONB in existing table:
```json
{
  "event_id": "evt_abc123",
  "photo_ids": ["photo1", "photo2", "photo3"],
  "estimated_date_range": [1918, 1922],
  "shared_face_ids": ["face_a", "face_b"],
  "shared_identity_ids": ["id_albert", "id_esther"],
  "location": "Dayton, Ohio",
  "event_type": "family_gathering|wedding|portrait|vacation"
}
```

### Implementation
1. **Algorithm** (`rhodesli_ml/temporal_cooccurrence.py`):
   - Load all date_labels with `best_year_estimate`
   - Load face-to-identity mappings
   - For each person: group their photos by estimated date (±2 years)
   - Within each date group: sub-cluster by shared faces
   - Output: list of events with photo_ids, date range, shared identities
   - Write to Supabase `photo_events` table

2. **Person Timeline UI** (enhance person page):
   - Below the photo grid, add "Timeline" tab or section
   - Show events as horizontal timeline with photo thumbnails
   - Each event card: date range, photo count, identified people
   - "Frequent Companions" sidebar: who appears most often with this person

3. **Sort Integration**:
   - Once events exist, person page sort should work naturally
   - "Earliest First" uses event date, with photos within event sorted by position

### Tests
- Event clustering: happy path (3 photos same era + shared faces → 1 event)
- Edge cases: single photo (event of 1), photos with no date estimate (excluded)
- Timeline rendering: verify HTML output with event cards
- Sort: verify chronological ordering matches date estimates

## Phase 3: Geo Dual-Write + Anchor Verify (PARALLEL with Phase 2)

### 3a: Geocode + Dual-Write
- For each photo with `location_primary` in date_labels:
  1. Geocode the place string to lat/lng (use existing geocoding script)
  2. Write to `photo_locations` table (the map reads from this table)
- Verify: map pins appear for batch-processed photos

### 3b: Anchor Compare Browser Verify
- Navigate to a photo page with the anchor compare panel
- Test the flow: enter anchor photo ID, click Compare, view results
- Screenshot evidence required (Lesson 97)

## Codex Audit Strategy

| After Phase | Scope | Block on P0/P1? |
|-------------|-------|-----------------|
| Phase 0 | Bug fixes — sort, display, data repair | Yes |
| Phase 1 | Batch output quality spot-check | Yes for first |
| Phase 2 | Event clustering algorithm, timeline UI | Yes |
| Phase 3 | Geo/anchor — security, data integrity | Yes |

## Parallelization Plan

| Track | Phase | Dependencies |
|-------|-------|-------------|
| Track A (worktree) | 0a: Sort fix | None |
| Track B (worktree) | 0b: 0% display fix | None |
| Track C (worktree) | 0c: 3481 data repair | None |
| Sequential | Phase 1: Batch completion | After Phase 0 |
| Sequential | Phase 2: Event grouping algorithm | After Phase 1 |
| Track D (worktree) | Phase 3a: Geo dual-write | After Phase 1 |
| Track E (worktree) | Phase 3b: Anchor verify | None |

## Key Constraints
- **Budget**: ~$3.36 for 61 remaining photos + ~$2.09 if any GEDCOM re-runs needed
- **Gemini quota**: 250 RPD on Tier 1 — 61 photos fits easily
- **Browser verification MANDATORY** for: sort fix, timeline UI, anchor compare, map pins
- **Codex audit MANDATORY** after every phase
- Follow `batch-data-pipeline.md` for all outputs
- All data writes to Supabase (Lesson 162)
- No doc >300 lines (Lesson 106)
