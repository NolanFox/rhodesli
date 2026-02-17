# PRD: Gemini-InsightFace Face Alignment via Coordinate Bridging

**Author:** Nolan Fox
**Date:** 2026-02-17
**Status:** Draft
**Session:** TBD

---

## Problem Statement

Currently, Rhodesli matches Gemini's per-person descriptions (age, gender, clothing) to InsightFace face detections using left-to-right x-coordinate sorting (`match_faces_to_ages()` in `rhodesli_ml/pipelines/birth_year_estimation.py`). This works only when face counts match between Gemini and InsightFace -- and they frequently do not.

**The failure mode**: In group photos, Gemini may describe 4 visible people while InsightFace detects 12 faces -- including faces in background posters, newspaper clippings, small children partially occluded, and reflections. When `len(photo_face_ids) != len(subject_ages)`, the current code returns an empty dict and `"count_mismatch"`, discarding all age data for that photo.

**Impact**:
- ~40% of group photos have count mismatches, yielding zero face-to-age data
- Vida Capeluto (15 photos, most prominent identity) gets 0 birth year estimates because all her photos have face count mismatches (documented in PRD-008 results)
- Birth year estimation pipeline (AD-071) skips these photos entirely
- Temporal consistency auditor (AD-054) cannot cross-check ages for mismatched photos
- The more complex the photo (group portraits, family gatherings), the less data we extract -- exactly the photos that contain the most genealogical value

## Who This Is For

| Role | Value |
|------|-------|
| ML pipeline | Correct face-to-description alignment enables accurate birth year estimation |
| Admin (Nolan) | Vida Capeluto and other group-photo identities finally get birth year estimates |
| Family members | More person pages show birth year, age overlays on timeline become accurate |
| Timeline viewer | Age badges on group photos become reliable instead of missing |

---

## Two Approaches Evaluated

### Approach A: Gemini Provides Its Own Coordinates

Prompt Gemini to return bounding boxes (`box_2d` in `[y_min, x_min, y_max, x_max]` format, normalized to 0-1000) for each person it describes.

**How it works**:
1. Gemini analyzes the photo and returns per-person descriptions with `box_2d` coordinates
2. Post-processing converts Gemini's normalized coordinates to pixel coordinates
3. IoU (Intersection over Union) or center-point distance matching pairs each Gemini box to the nearest InsightFace detection
4. Matched pairs link Gemini descriptions to InsightFace embeddings

**Pros**:
- Uses Gemini's spatial understanding directly
- Gemini already supports `box_2d` output natively

**Cons**:
- Requires IoU matching with tuned thresholds (what IoU is "close enough"?)
- Gemini coordinates may not align precisely with InsightFace (different face region definitions -- Gemini may box the head, InsightFace the tight face crop)
- Unmatched boxes on either side need graceful handling
- EXIF orientation differences between what Gemini sees and the stored bounding boxes create coordinate system mismatches
- Adds a matching layer that can fail silently

### Approach B: Feed InsightFace Coordinates TO Gemini (RECOMMENDED)

Include InsightFace bounding boxes in the Gemini prompt as labeled regions. Ask Gemini to describe each labeled face.

**How it works**:
1. Extract all InsightFace face detections with bounding boxes for the photo
2. Assign each face a letter label (Face A, Face B, ...) sorted by x-coordinate
3. Include in the Gemini prompt: "I have detected 12 faces in this photo at these pixel coordinates: Face A [120,45,210,180], Face B [350,90,420,230], ..."
4. Ask Gemini: "For each face label, provide the estimated age, gender, and clothing description. If a face label corresponds to a background face (newspaper, poster, reflection) or is too small/blurry to describe, mark it as 'not_a_subject'."
5. Gemini returns descriptions keyed by face label (A, B, C, ...)
6. Face labels map directly to InsightFace face_ids -- no post-hoc matching needed

**Pros**:
- Guaranteed 1:1 mapping between descriptions and face detections
- No IoU thresholds, no matching layer, no silent failures
- Gemini naturally handles the "which faces are real subjects vs background" problem
- Simpler implementation (no coordinate conversion, no matching algorithm)
- Face count mismatch is inherently resolved -- Gemini describes the faces we actually detected

**Cons**:
- Prompt engineering needed to ensure Gemini understands pixel coordinate format
- Long face lists (12+ faces) may confuse the model or exceed practical attention limits
- Gemini may sometimes fail to match a coordinate to a visible face (occluded, tiny)
- Slightly larger prompts (coordinate data adds ~100-200 tokens per photo)

---

## Recommended Approach: B (Coordinate Bridging)

Approach B is recommended because:

1. **Guaranteed mapping**: Every face label maps to exactly one InsightFace face_id. No ambiguity.
2. **Simpler code**: No IoU computation, no threshold tuning, no matching failures to handle.
3. **Better data quality**: Gemini explicitly marks background/non-subject faces as `not_a_subject`, which is information we currently lack entirely.
4. **Solves the root cause**: The problem is not that coordinates are hard to match -- it's that Gemini and InsightFace see different numbers of people. Approach B makes Gemini describe what InsightFace detected, not what Gemini independently identifies.

---

## User Flows

### Flow 1: Re-labeling Pipeline (Admin/ML)

1. Admin runs `python -m rhodesli_ml.scripts.generate_date_labels --coordinate-bridging --dry-run`
2. Script loads `data/embeddings.npy` and `data/photo_index.json` to get InsightFace bounding boxes per photo
3. For each photo, constructs Gemini prompt with face coordinate labels
4. Gemini returns per-face descriptions keyed by label
5. Script maps labels back to face_ids and writes to `date_labels.json` with new `face_descriptions` field
6. Admin reviews dry-run output, then runs with `--execute` to write labels

### Flow 2: Birth Year Estimation (Automatic)

1. `run_birth_year_estimation()` loads updated `date_labels.json`
2. For each photo with `face_descriptions`, looks up age by face_id directly (no bbox sorting needed)
3. Count mismatches are eliminated -- every face with a description has a direct age mapping
4. Vida Capeluto and other previously-skipped identities now get birth year estimates

### Flow 3: New Photo Upload (Future)

1. New photo uploaded and processed through InsightFace
2. Face detections with bounding boxes passed to Gemini labeling
3. Gemini descriptions automatically aligned to detected faces
4. No separate alignment step needed

---

## Data Model Changes

### date_labels.json -- Extended Schema

**Before** (current):
```json
{
  "photo_id": "ca69d9decc37b0ec",
  "subject_ages": [36, 28, 5],
  "best_year_estimate": 1939,
  ...
}
```

**After** (with face alignment):
```json
{
  "photo_id": "ca69d9decc37b0ec",
  "subject_ages": [36, 28, 5],
  "face_descriptions": {
    "Image 054_compress:face0": {
      "age": 36,
      "gender": "male",
      "clothing_notes": "Dark suit, white shirt, fedora",
      "is_subject": true
    },
    "Image 054_compress:face1": {
      "age": 28,
      "gender": "female",
      "clothing_notes": "Floral dress, pearl necklace",
      "is_subject": true
    },
    "Image 054_compress:face2": {
      "age": 5,
      "gender": "male",
      "clothing_notes": "Sailor suit",
      "is_subject": true
    },
    "inbox_739db7ec49ac": {
      "is_subject": false,
      "reason": "Background face in newspaper clipping"
    }
  },
  "face_alignment_method": "coordinate_bridging",
  "prompt_version": "v3_coordinate_bridging",
  "best_year_estimate": 1939,
  ...
}
```

### New fields in each date label

| Field | Type | Description |
|-------|------|-------------|
| `face_descriptions` | dict | Map of face_id to description object |
| `face_alignment_method` | string | "coordinate_bridging" or "x_sort_legacy" |
| `prompt_version` | string | Prompt version that generated this label |

### Each face description object

| Field | Type | Description |
|-------|------|-------------|
| `age` | int | Estimated age (if subject) |
| `gender` | string | "male", "female", "unknown" |
| `clothing_notes` | string | Brief clothing/attire description |
| `is_subject` | bool | True = real person, False = background/artifact |
| `reason` | string | (Optional) Why face is not a subject |

### Backward compatibility

- `subject_ages` array is preserved for backward compatibility
- `match_faces_to_ages()` checks for `face_descriptions` first, falls back to x-sort
- Old labels without `face_descriptions` continue to work unchanged

---

## Technical Constraints

### EXIF Orientation Normalization

InsightFace bounding boxes are computed on the raw pixel grid. If the image has EXIF orientation metadata (rotation, flip), the visual image Gemini sees may be rotated relative to the raw pixel grid. Bounding box coordinates must be normalized to the visual orientation before being included in the Gemini prompt.

Steps:
1. Read EXIF orientation tag (already available via `core/exif.py`)
2. Transform InsightFace bbox coordinates to match the displayed orientation
3. Pass transformed coordinates to Gemini
4. Map Gemini's face labels back to original InsightFace face_ids (label assignment happens before transformation, so labels are stable)

### Gemini API Limits

- Prompt size: ~100-200 additional tokens per photo for coordinates (12 faces x ~15 tokens each). Well within Gemini's context window.
- Photos with >20 detected faces: Consider truncating to the 20 largest bounding boxes (by area) to avoid overwhelming the model. Flag omitted faces.

### Cost

- Re-processing all 271 photos at Gemini Flash pricing: ~$0.50-$1.00
- The coordinate data adds minimal token cost (text, not image tokens)
- Single API call per photo (same as current pipeline)

### Prompt Engineering

The coordinate bridging prompt must clearly instruct Gemini to:
1. Match each labeled face region to what it sees in the image
2. Report `is_subject: false` for non-subject faces (background, newspaper, artifacts)
3. Provide age, gender, clothing for subject faces
4. Handle cases where a bounding box doesn't correspond to a visible face (occluded, false positive)

### Existing Code Impact

| File | Change |
|------|--------|
| `rhodesli_ml/scripts/generate_date_labels.py` | Add coordinate bridging prompt variant, face label generation |
| `rhodesli_ml/pipelines/birth_year_estimation.py` | Check `face_descriptions` before falling back to `match_faces_to_ages()` |
| `rhodesli_ml/data/date_labels.py` | Schema validation for new fields |
| `rhodesli_ml/scripts/clean_labels.py` | Validate `face_descriptions` structure |
| `rhodesli_ml/scripts/audit_temporal_consistency.py` | Use direct face-to-age mapping when available |

---

## Acceptance Criteria

```
TEST 1: Coordinate bridging prompt generates valid face descriptions
  - Process a test photo with known face count mismatch (e.g., 4 subjects, 12 detections)
  - Assert: face_descriptions has entries for all 12 face_ids
  - Assert: exactly 4 have is_subject=true
  - Assert: each subject has age, gender, clothing_notes

TEST 2: Face descriptions correctly mapped to InsightFace face_ids
  - Process a photo where face positions are known
  - Assert: face_descriptions keys match actual face_ids from embeddings.npy
  - Assert: ages are plausible (0-100)

TEST 3: Birth year estimation uses face_descriptions when available
  - Mock a label with face_descriptions containing a known identity's face_id
  - Assert: birth year pipeline finds the age for that face_id directly
  - Assert: no x-sort fallback invoked

TEST 4: Count mismatch photos now produce birth year estimates
  - Process Vida Capeluto's photos (previously all count_mismatch)
  - Assert: at least 5 of her 15 photos produce usable face-to-age mappings
  - Assert: birth year estimate generated with evidence

TEST 5: Backward compatibility with old labels
  - Process a label WITHOUT face_descriptions
  - Assert: match_faces_to_ages() x-sort fallback works as before
  - Assert: no error or regression

TEST 6: Non-subject faces correctly identified
  - Process a newspaper photo with embedded face images
  - Assert: newspaper faces marked is_subject=false
  - Assert: subject_ages list matches only is_subject=true faces

TEST 7: EXIF orientation handled correctly
  - Process a photo with EXIF rotation (orientation != 1)
  - Assert: coordinates passed to Gemini match visual orientation
  - Assert: face labels map back to correct InsightFace face_ids

TEST 8: No regression on date estimation accuracy
  - Compare best_year_estimate and confidence before/after re-processing
  - Assert: >=95% of photos have same or better date estimates
  - Assert: no photo date shifts by more than 1 decade

TEST 9: Match rate >= 90%
  - Across all 271 photos, compute % of face descriptions correctly assigned
  - Assert: >= 90% of is_subject=true faces have plausible age/gender
  - (Validation: spot-check 20 photos manually)

TEST 10: Graceful fallback when Gemini cannot describe a face
  - Process a photo where some bboxes are tiny or occluded
  - Assert: those faces get is_subject=false or age=null
  - Assert: pipeline doesn't crash
```

---

## Out of Scope

- Real-time face alignment during photo upload (future ML-051/ML-052)
- Using face descriptions for identity matching (embedding-based only, per Rule 4)
- Gemini-based face recognition (violates "No Generative AI for forensic matching")
- Per-person relationship detection from spatial positioning (unreliable, per AD-049)
- Multi-model ensemble (run Gemini twice with different prompts)
- Client-side coordinate visualization

---

## Novelty

No known prior work combines VLM (Vision Language Model) spatial understanding with face detection embeddings specifically for heritage/genealogy photo analysis. The "coordinate bridging" approach -- feeding detection coordinates INTO the VLM rather than asking the VLM to provide coordinates -- is a novel inversion that eliminates the post-hoc matching problem entirely.

Existing approaches in the literature:
- **Object detection + VLM**: GLIP, Grounding DINO -- VLM provides coordinates, matched to detections via IoU
- **Set-of-Mark prompting**: Overlay visual markers on images before VLM processing -- requires image modification
- **Coordinate bridging (this approach)**: Pass detector coordinates as text tokens, ask VLM to describe each region -- no image modification, no IoU matching, guaranteed 1:1 mapping

---

## Priority Order

1. Prompt engineering for coordinate bridging (foundation -- everything depends on Gemini understanding the format)
2. EXIF orientation normalization (required before coordinates are meaningful)
3. `generate_date_labels.py` updates (prompt variant + face description parsing)
4. `birth_year_estimation.py` updates (use face_descriptions when available)
5. Re-process all 271 photos
6. Validate match rate and birth year improvements
7. Update `clean_labels.py` and `audit_temporal_consistency.py`

---

## Migration Plan

1. **Phase 1: Validate** -- Process 10 test photos with coordinate bridging prompt, manually verify alignment accuracy
2. **Phase 2: Full re-process** -- Re-label all 271 photos with coordinate bridging (~$0.50-$1.00 cost)
3. **Phase 3: Birth year re-estimation** -- Re-run birth year pipeline with new face descriptions
4. **Phase 4: Measure impact** -- Compare birth year estimate count and confidence before/after (target: Vida Capeluto gets an estimate)
