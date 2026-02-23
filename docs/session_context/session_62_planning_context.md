# Session 62 Planning Context
# "PRD-015: Gemini-InsightFace Face Alignment — The Portfolio Crown Jewel"

## Source: Claude planning conversations, Feb 22, 2026
## Breadcrumbs: 61 → 61B (PRD-015 v2 written) → 62 (this session implements it)
## Parallel: Runs simultaneously with Session 61C via git worktree

---

## 1. PARALLELIZATION — RUNNING WITH 61C

### Confirmed: 62 Can Run Simultaneously with 61C
61C is doing ML experiments (GEDCOM enrichment, Flash vs Pro).
62 is doing app-level implementation (face alignment endpoint, UI).
Different files, different concerns.

### Worktree Setup
Whichever session starts second takes the worktree. If 61C started
first on main, 62 uses a worktree. If 61C is in a worktree, 62
works on main.

### File Ownership
| File/Directory | 62 Owns | 61C Owns | Shared (merge carefully) |
|----------------|---------|----------|--------------------------|
| app/main.py | ✓ | | |
| app/templates/* | ✓ | | |
| app/face_alignment.py | ✓ (new) | | |
| tests/test_face_alignment.py | ✓ (new) | | |
| tests/test_app*.py | ✓ | | |
| rhodesli_ml/* | | ✓ | |
| scripts/* | | ✓ | |
| results/* | | ✓ | |
| ROADMAP.md | | | ✓ |
| BACKLOG.md | | | ✓ |
| CHANGELOG.md | | | ✓ |
| docs/ALGORITHMIC_DECISIONS.md | ✓ (append) | ✓ (append) | ✓ |

### Merge Strategy
- 61C merges FIRST (smaller scope, lower conflict risk)
- 62 merges SECOND, resolving any shared doc conflicts
- Both sessions append-only to shared docs (no rewriting)
- If AD number conflict: 62 takes the higher number

---

## 2. THE PROBLEM — WHY FACE ALIGNMENT MATTERS

### Current State: X-Sorting (Broken)
When a photo has multiple faces, we currently match InsightFace
detections to Gemini descriptions by left-to-right sort order.
This fails when:
- Face counts don't match (Gemini sees 5, InsightFace detects 4)
- Faces are at similar x-coordinates (group photo, vertical layout)
- Gemini's ordering doesn't match spatial ordering

**Failure rate: ~40% of multi-face photos** have at least one
mismatched description. This is the Vida Capeluto count mismatch
problem — Gemini sees different faces than InsightFace and the
descriptions get assigned to the wrong people.

### The Fix: Coordinate Bridging (Approach B)
Feed InsightFace bounding boxes TO Gemini as part of the prompt.
Gemini then describes each face using the IDs we provide.
Guaranteed 1:1 correspondence — no matching needed.

### Why This Is Portfolio-Grade
Nobody is doing this for heritage photo analysis. The approach of
using a VLM's spatial understanding to bridge per-person descriptions
to face detection embeddings via coordinate alignment is novel. This
is the most impressive ML work in the project from a technical
interview perspective.

---

## 3. TECHNICAL DESIGN

### Two Approaches (Approach B is chosen)

**Approach A (rejected): Gemini-provides-coordinates**
Ask Gemini to return bounding boxes, then match to InsightFace via IoU.
Problem: Gemini's boxes may not align precisely with InsightFace's,
and IoU matching adds a fragile post-processing step.

**Approach B (chosen): Feed InsightFace coordinates TO Gemini**
```
"I have detected 4 faces in this photo at these bounding box
coordinates (in pixels, format [x1, y1, x2, y2]):
Face_A: [120, 80, 280, 310]
Face_B: [350, 60, 490, 290]
Face_C: [520, 100, 650, 340]
Face_D: [700, 90, 830, 320]

For each face, provide: estimated age, gender, physical description,
clothing description, position in photo, and any identifying features."
```

Result: Gemini returns analysis keyed by Face_A, Face_B, etc.
Each Face_X maps directly to InsightFace detection index X.

### Coordinate Systems
- **InsightFace**: `[x1, y1, x2, y2]` in raw pixel coordinates
- **Gemini**: `[y_min, x_min, y_max, x_max]` normalized 0-1000
- For Approach B, we send InsightFace pixel coords (no conversion needed)
- If we ever need Approach A fallback: multiply Gemini by image_dim/1000

### EXIF Orientation Caveat
Historical scanned photos may have EXIF orientation metadata that
causes coordinate misalignment. InsightFace operates on the
decoded image (post-orientation). Gemini operates on the raw file
(may or may not respect EXIF).

**Mitigation**: Before sending to Gemini, strip EXIF orientation
and re-save the image in its displayed orientation. This ensures
both systems see the same pixel layout.

### Integration with Unified Extraction
61B built `rhodesli_ml/gemini_extraction.py` with configurable
presets. The `face_analysis` extraction type should accept
InsightFace coordinates as input parameters. Session 62 extends
this by:
1. Adding a `face_alignment` extraction type to the unified prompt
2. Building the endpoint that gathers InsightFace faces, formats
   coordinates, calls Gemini, and stores the aligned result
3. Updating the photo page UI to show aligned descriptions

### Data Storage
Results stored in Supabase alongside existing face data:
- `face_gemini_descriptions` table: face_id, gemini_description,
  age_estimate, gender, clothing, position, photo_id, model_used
- Links to existing face/identity tables
- Versioned: re-running with a new model creates new rows,
  doesn't overwrite

### Mismatch Handling
When Gemini sees a different number of faces than InsightFace:
- Log the mismatch with both counts
- For faces InsightFace found but Gemini didn't describe:
  mark as "unmatched_by_gemini" (common for very small/blurry faces)
- For faces Gemini describes but InsightFace didn't detect:
  log as "gemini_only" — potential InsightFace miss
- Surface mismatch count in admin UI for review

---

## 4. AD REFERENCES FROM 61B

From Session 61B Phase 6:
- **AD-143**: Face alignment via coordinate bridging (PRD-015 v2)
  Decision: Approach B preferred (feed InsightFace coords to Gemini)
- **AD-144**: Similarity calibration — Platt scaling first, LoRA later
- **AD-145**: Platt scaling as Stage 1 (deferred to Session 63)
- **PRD-015 v2**: Updated for Gemini 3.1 Pro, coordinate format,
  success criteria
- **PRD-023**: LoRA similarity calibration research PRD

---

## 5. SCOPE BOUNDARIES FOR SESSION 62

### In Scope
- Implement coordinate bridging (Approach B) end-to-end
- EXIF orientation handling
- New `/api/face-alignment` endpoint (or integrated into existing flow)
- Photo page UI showing per-face Gemini descriptions
- Test on real photos with curl (not just unit tests)
- Supabase storage for aligned descriptions
- Mismatch detection and logging

### Out of Scope (tracked in BACKLOG)
- Batch re-run of all 271 photos (cost ~$7.60, needs separate approval)
- LoRA fine-tuning (Session 63+, depends on Platt scaling results)
- GEDCOM enrichment integration (61C handles this)
- Flash vs Pro comparison (61C handles this)
- Platt scaling implementation (Session 63)

### Gemini API Budget
Session 62 should use minimal API calls — just enough to test the
face alignment on 3-5 real photos. Estimated cost: < $0.50.
No bulk re-runs in this session.

---

## 6. APP THESIS REMINDER

From Nolan's words:
- Help people **identify** photos / people → Face alignment directly
  serves this by giving accurate per-face descriptions
- **Solve mysteries** through photo context → Aligned descriptions
  mean the right description goes to the right face
- **Deepen understanding** → Per-face age/clothing/position data
  enriches what we know about each person in a photo

Face alignment is infrastructure that makes EVERY other feature better.
When descriptions are correctly assigned to faces, identification
accuracy improves, community contributions are more targeted, and
the entire identity management system becomes more trustworthy.
