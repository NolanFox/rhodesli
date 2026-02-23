# Session 62: PRD-015 Face Alignment — Coordinate Bridging Implementation

Read CLAUDE.md. Read all .claude/rules/*.md files.
Read docs/session_context/session_62_planning_context.md.
Read CHANGELOG.md (first 10 lines). Read ROADMAP.md. Read BACKLOG.md.
Read docs/ALGORITHMIC_DECISIONS.md (last 30 lines).
Read docs/prds/015_gemini_face_alignment.md.

## SESSION IDENTITY
- **Session**: 62
- **Predecessor**: 61B (wrote PRD-015 v2, unified extraction, self-assessment)
- **Lineage**: 60 → 60B → 61 → 61B → 62 (this session)
- **Goal**: Implement PRD-015 face alignment end-to-end — feed InsightFace
  coordinates to Gemini, get per-face descriptions, store results,
  show on photo page UI. Test on real photos.
- **Parallel**: May run simultaneously with Session 61C (ML experiments).
  If 61C is running, use git worktree. See Phase 0.
- **Estimated time**: 70-90 minutes
- **Context file**: `docs/session_context/session_62_planning_context.md`
- **Post-62**: Session 63 = Platt scaling (AD-145), batch re-run decision
- **Deferred**: LoRA (PRD-023), GEDCOM integration (61C), batch 271-photo re-run

---

## ⚠️ CRITICAL: WORKTREE SETUP FOR PARALLEL OPERATION

Check if Session 61C is running. If so, use a worktree.

```bash
# Check for active parallel session
git branch | grep -q "session-61c" && \
  echo "⚠ Session 61C active — USE WORKTREE" || \
  echo "✓ No conflict — can work on main"

# If worktree needed:
git checkout -b session-62 2>/dev/null || git checkout session-62
git worktree add .claude/worktrees/session-62 session-62 2>/dev/null
cd .claude/worktrees/session-62
echo "Working in worktree: $(pwd)"

# If no worktree needed: work on main as normal
```

### File Ownership (if parallel with 61C)
- 62 OWNS: app/*, app/templates/*, tests/test_app*, tests/test_face_alignment*
- 62 CREATES: app/face_alignment.py (new module)
- 62 APPENDS ONLY: ROADMAP.md, BACKLOG.md, ALGORITHMIC_DECISIONS.md
- DO NOT TOUCH: rhodesli_ml/* (61C owns), scripts/*, results/*

---

## ⚠️ CONTEXT MANAGEMENT — MANDATORY

### Before ANYTHING else:
```bash
cp docs/session_context/session_62_planning_context.md /tmp/session_62_context.md
cat > /tmp/session_62_checklist.md << 'EOF'
# Session 62 Phase Checklist
# Lineage: 60 → 60B → 61 → 61B → 62
- [ ] PHASE 0: Orient + Worktree Setup
- [ ] PHASE 1: EXIF Orientation Handler
- [ ] PHASE 2: Coordinate Bridging Module
- [ ] PHASE 3: Face Alignment API Endpoint
- [ ] PHASE 4: Photo Page UI — Per-Face Descriptions
- [ ] PHASE 5: Real Photo Testing (curl + browser)
- [ ] PHASE 6: Documentation + Self-Assessment
EOF
```

### Between EVERY phase (MANDATORY — do not skip):
```bash
git add -A && git commit -m "62 phase N: [description]"
sed -i 's/- \[ \] PHASE N/- [x] PHASE N/' /tmp/session_62_checklist.md
cat /tmp/session_62_checklist.md
```

### CLEAR AFTER EVERY PHASE (MANDATORY — context WILL run out otherwise):
```bash
/clear
```
After clearing, ALWAYS re-read state from disk:
```bash
cat docs/prompts/session_62_prompt.md | sed -n '/^## PHASE N_NEXT/,/^## PHASE N_AFTER/p' | head -80
cat /tmp/session_62_context.md | head -60
cat /tmp/session_62_checklist.md
git log --oneline -5
```
**Why /clear and NOT /compact**: /compact is lossy and expensive — it
summarizes your context and loses detail. /clear wipes the slate completely
and lets you re-read fresh from disk. That's why we save everything to
/tmp and docs/prompts/. Session 61C ran out of context because it used
/compact instead of /clear. Do not repeat that mistake.

### At session end:
```bash
cat docs/prompts/session_62_prompt.md | head -20
cat /tmp/session_62_checklist.md
# Fix any unchecked items. Then run PHASE 6 self-assessment.
```

---

## PHASE 0: ORIENT + VERIFY PREREQUISITES (~5 min)

### 0A: Read State
```bash
cat CLAUDE.md
cat docs/session_context/session_62_planning_context.md
cat docs/prds/015_gemini_face_alignment.md
head -20 CHANGELOG.md
git log --oneline -10
cat ROADMAP.md
cat BACKLOG.md
```

### 0B: Verify Prerequisites Exist
```bash
echo "=== 1. UNIFIED EXTRACTION MODULE ==="
python3 -c "
from rhodesli_ml.gemini_extraction import EXTRACTION_PRESETS, build_extraction_prompt
print(f'Presets: {list(EXTRACTION_PRESETS.keys())}')
print('✓ Module importable')
" 2>/dev/null || echo "✗ Import failed — need to check what happened"

echo "=== 2. GEMINI API KEY ==="
python3 -c "
import os
key = os.getenv('GEMINI_API_KEY', '')
print(f'Key present: {bool(key)}, length: {len(key)}')
" || echo "✗ No key"

echo "=== 3. INSIGHTFACE AVAILABLE ==="
python3 -c "
from insightface.app import FaceAnalysis
print('✓ InsightFace importable')
" 2>/dev/null || echo "⚠ InsightFace not available locally — test via existing face data"

echo "=== 4. PRD-015 EXISTS ==="
ls docs/prds/015_gemini_face_alignment.md && echo "✓" || echo "✗ MISSING"
grep -c "Approach B\|coordinate.*bridg" docs/prds/015_gemini_face_alignment.md

echo "=== 5. AD-143 EXISTS ==="
grep -c "AD-143\|face alignment.*coordinate" docs/ALGORITHMIC_DECISIONS.md

echo "=== 6. EXISTING FACE DATA ==="
python3 -c "
# Check how faces are currently stored — bounding boxes available?
import json
# Try to find existing face detection data
import glob
files = glob.glob('data/**/*faces*', recursive=True) + \
        glob.glob('data/**/*detection*', recursive=True)
print(f'Face data files: {files[:5]}')
" 2>/dev/null || echo "Need to check face data format"

echo "=== 7. PHOTO ACCESS ==="
python3 -c "
# Verify we can access photos (R2 or local)
import os
r2_key = os.getenv('R2_ACCESS_KEY_ID', '')
print(f'R2 configured: {bool(r2_key)}')
" 2>/dev/null
```

### 0C: Understand Current Face Data Format
This is CRITICAL. Before building anything, understand:
1. Where are InsightFace bounding boxes stored? (Supabase? JSON files?)
2. What format? ([x1, y1, x2, y2] in pixels?)
3. How are faces currently linked to photos?
4. How does the current x-sorting work? (find the code, read it)

```bash
echo "=== CURRENT FACE-TO-DESCRIPTION MAPPING ==="
grep -rn "x.*sort\|left.*right\|face.*order\|bbox.*sort\|sort.*face" \
  --include="*.py" app/ rhodesli_ml/ | head -10

echo "=== FACE STORAGE ==="
grep -rn "bbox\|bounding_box\|face_box\|detection\|x1.*y1" \
  --include="*.py" app/ rhodesli_ml/ | head -15

echo "=== FACE-PHOTO LINK ==="
grep -rn "face.*photo\|photo.*face\|face_id.*photo_id" \
  --include="*.py" app/ rhodesli_ml/ | head -10
```

Document what you find. The implementation depends entirely on
where InsightFace coordinates currently live.

Commit: `chore: 62 orient — prerequisites verified, face data format documented`

---

## PHASE 1: EXIF ORIENTATION HANDLER (~8 min)

### Goal
Ensure photos sent to Gemini have the same pixel orientation that
InsightFace processed. Historical scanned photos may have EXIF
orientation metadata that causes coordinate misalignment.

### 1A: Create EXIF Handler
Create `app/exif_handler.py`:

```python
"""
EXIF orientation normalization for Gemini-InsightFace alignment.

Problem: InsightFace operates on the decoded image (auto-rotated by PIL).
Gemini may or may not respect EXIF orientation when analyzing coordinates.
Solution: Strip EXIF orientation and save in displayed orientation before
sending to Gemini. This ensures both systems see the same pixel layout.

AD reference: AD-143 (face alignment via coordinate bridging)
PRD reference: PRD-015 v2
"""

def normalize_orientation(image_bytes: bytes) -> bytes:
    """
    Strip EXIF orientation and return image in its displayed orientation.
    This ensures Gemini and InsightFace see the same pixel layout.

    Args:
        image_bytes: Raw image file bytes (may have EXIF orientation)
    Returns:
        Image bytes with orientation applied and EXIF stripped
    """

def get_image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """Return (width, height) of the orientation-corrected image."""

def has_exif_orientation(image_bytes: bytes) -> bool:
    """Check if image has non-trivial EXIF orientation tag."""
```

### 1B: Tests
- `test_normalize_no_exif` — image without EXIF passes through unchanged
- `test_normalize_with_rotation` — rotated image gets corrected
- `test_dimensions_after_normalize` — width/height are post-rotation
- `test_idempotent` — normalizing twice gives same result

Commit: `feat: EXIF orientation handler for face alignment — PRD-015`

---

## PHASE 2: COORDINATE BRIDGING MODULE (~15 min)

### Goal
Build the core face alignment logic: take InsightFace face detections
for a photo, format them for Gemini, call Gemini, parse the response,
and store the aligned results.

### 2A: Create Face Alignment Module
Create `app/face_alignment.py`:

```python
"""
PRD-015: Gemini-InsightFace Face Alignment via Coordinate Bridging

Approach B (chosen): Feed InsightFace bounding box coordinates to Gemini
as part of the analysis prompt. Gemini describes each face using the IDs
we provide, guaranteeing 1:1 correspondence.

AD-143: Why Approach B over A
- Guaranteed 1:1 mapping (no IoU matching needed)
- Robust to face count mismatches
- No post-hoc coordinate matching thresholds

Novel: No known prior work combining VLM spatial understanding with
face detection embeddings for heritage photo analysis.
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class FaceDetection:
    """InsightFace detection result for one face in a photo."""
    face_id: str           # Our internal face ID
    bbox: list[int]        # [x1, y1, x2, y2] in pixels
    embedding_id: str      # Reference to stored embedding
    identity_name: Optional[str] = None  # If already identified

@dataclass
class AlignedFaceDescription:
    """Gemini's description aligned to a specific InsightFace detection."""
    face_id: str
    bbox: list[int]
    gemini_description: str
    estimated_age: Optional[int] = None
    gender: Optional[str] = None
    clothing: Optional[str] = None
    position_in_photo: Optional[str] = None
    identifying_features: Optional[str] = None
    identity_name: Optional[str] = None  # Pre-existing ID if any
    matched: bool = True   # False if Gemini couldn't describe this face

@dataclass
class AlignmentResult:
    """Full alignment result for one photo."""
    photo_id: str
    faces_detected: int         # InsightFace count
    faces_described: int        # Gemini described count
    aligned_faces: list[AlignedFaceDescription]
    gemini_only_faces: list     # Faces Gemini saw but InsightFace didn't
    unmatched_faces: list[str]  # Face IDs InsightFace found but Gemini skipped
    model_used: str
    cost: float
    input_tokens: int
    output_tokens: int


def format_faces_for_gemini(faces: list[FaceDetection]) -> str:
    """
    Format InsightFace detections as a coordinate block for Gemini.

    Output example:
    "I have detected 4 faces in this photo at these bounding box
    coordinates (in pixels, format [x1, y1, x2, y2]):
    Face_A: [120, 80, 280, 310]
    Face_B: [350, 60, 490, 290]
    ..."
    """

def build_alignment_prompt(faces: list[FaceDetection],
                           additional_context: str = "") -> str:
    """
    Build the full Gemini prompt for face alignment.

    Includes:
    - Face coordinates block
    - Request for per-face analysis (age, gender, description, clothing)
    - JSON output schema for structured parsing
    - Optional additional context (e.g., GEDCOM data in future)
    """

def parse_alignment_response(response: dict,
                             faces: list[FaceDetection]) -> AlignmentResult:
    """
    Parse Gemini's structured response and align to InsightFace faces.

    Handles:
    - Perfect match (Gemini described all faces)
    - Partial match (Gemini skipped some small/blurry faces)
    - Extra faces (Gemini saw faces InsightFace missed)
    """

async def run_face_alignment(photo_id: str,
                             image_bytes: bytes,
                             faces: list[FaceDetection],
                             model: str = "gemini-3.1-pro-preview",
                             additional_context: str = "") -> AlignmentResult:
    """
    Full face alignment pipeline for one photo:
    1. Normalize EXIF orientation
    2. Format faces for Gemini
    3. Build prompt (with optional GEDCOM context for future)
    4. Call Gemini API
    5. Parse response
    6. Return aligned result
    """
```

### 2B: Structured JSON Output Schema
Define the expected Gemini response format:
```json
{
  "faces": [
    {
      "face_id": "Face_A",
      "estimated_age": 45,
      "gender": "male",
      "description": "Middle-aged man with dark mustache",
      "clothing": "Dark three-piece suit with white shirt",
      "position": "Center of group, standing",
      "identifying_features": "Prominent mustache, slightly receding hairline"
    }
  ],
  "additional_faces_not_in_coordinates": [
    {
      "description": "Partially visible face at far right edge",
      "approximate_location": "right edge, partially cropped"
    }
  ],
  "scene_context": "Formal group portrait, likely studio setting"
}
```

### 2C: Supabase Storage
Create table and storage functions:
```sql
CREATE TABLE IF NOT EXISTS face_gemini_alignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id TEXT NOT NULL,
    face_id TEXT NOT NULL,
    model_used TEXT NOT NULL,
    gemini_description TEXT,
    estimated_age INTEGER,
    gender TEXT,
    clothing TEXT,
    position_in_photo TEXT,
    identifying_features TEXT,
    matched BOOLEAN DEFAULT true,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(photo_id, face_id, model_used)
);
```

### 2D: Tests
- `test_format_faces_for_gemini_basic`
- `test_format_faces_empty_list`
- `test_build_alignment_prompt_includes_coordinates`
- `test_parse_perfect_match` — all faces described
- `test_parse_partial_match` — Gemini skips some faces
- `test_parse_extra_faces` — Gemini sees faces InsightFace missed
- `test_alignment_result_dataclass`
- `test_supabase_storage_and_retrieval`

Commit: `feat: face alignment coordinate bridging module — PRD-015 core`

---

## PHASE 3: FACE ALIGNMENT API ENDPOINT (~10 min)

### Goal
Wire the face alignment module into the app so it can be triggered
per-photo (admin action) or in bulk (future batch job).

### 3A: API Endpoint
Add to `app/main.py`:

```python
@app.post("/api/face-alignment/{photo_id}")
async def run_face_alignment_endpoint(photo_id: str):
    """
    Run Gemini face alignment for a specific photo.
    Admin-only action (follows Gatekeeper pattern).

    1. Load photo from R2/local storage
    2. Load InsightFace face detections from Supabase
    3. Normalize EXIF orientation
    4. Run coordinate bridging with Gemini
    5. Store results in face_gemini_alignments table
    6. Return aligned descriptions
    """

@app.get("/api/face-alignment/{photo_id}")
async def get_face_alignment(photo_id: str):
    """
    Get stored face alignment results for a photo.
    Returns cached results if available, null if not yet aligned.
    """
```

### 3B: Admin Trigger UI
Add a "Run Face Analysis" button on the photo page (admin-only):
- Button visible only to authenticated admin
- Clicking triggers POST to `/api/face-alignment/{photo_id}`
- Shows loading spinner during Gemini call
- Displays results when complete
- Shows cost of the API call

### 3C: Integration with Existing Photo Flow
The face alignment should integrate cleanly with the existing
photo page without disrupting current functionality:
- If alignment exists: show per-face descriptions below face boxes
- If no alignment: show current behavior (no descriptions)
- Admin can trigger alignment for any photo on demand
- Future: batch alignment job for all 271 photos

Commit: `feat: face alignment API endpoint + admin trigger — PRD-015`

---

## PHASE 4: PHOTO PAGE UI — PER-FACE DESCRIPTIONS (~10 min)

### Goal
Update the photo page to display Gemini's per-face descriptions
alongside the face bounding boxes.

### 4A: Photo Page Enhancement
When face alignment data exists for a photo:
- Each face bounding box gets a hoverable/clickable description panel
- Panel shows: estimated age, gender, clothing, identifying features
- If face is already identified: show name + Gemini description
- If face is unidentified: Gemini description helps with identification
- Mismatch indicator if Gemini saw different face count

### 4B: Description Cards
For each aligned face, show a card (expandable):
```
┌─────────────────────────────┐
│ Face A: [Big Leon Capeluto] │  ← identity name if known
│ Age: ~45  |  Male           │
│ Dark three-piece suit       │
│ Center of group, standing   │
│ "Prominent mustache..."     │  ← identifying features
│                             │
│ [🔍 Identify] [📝 Correct] │  ← action buttons
└─────────────────────────────┘
```

### 4C: Mismatch UI
If face counts don't match:
```
⚠ InsightFace detected 4 faces, Gemini described 5.
1 additional face detected by Gemini (not matched to a detection).
```
This surfaces the Vida Capeluto-type problem for admin review.

### 4D: Mobile-Responsive
Cards should work on mobile — collapsible, not overlapping face boxes.

Commit: `feat: photo page per-face descriptions UI — PRD-015`

---

## PHASE 5: REAL PHOTO TESTING (~12 min)

### Goal
Test face alignment on real photos, not mocks. This is the phase
that catches the bugs unit tests miss.

### 5A: Test on 3-5 Real Photos via curl
```bash
echo "=== REAL PHOTO TESTING ==="

# Start app locally
# (or test against production if deployed)

# Pick 3-5 photos with different characteristics:
# 1. Photo with 2 faces (simple case)
# 2. Photo with 5+ faces (group photo — the hard case)
# 3. Photo with known identity (verify description matches)
# 4. Photo where x-sorting is known to fail
# 5. Photo with EXIF orientation (if any)

# For each photo:
# Step 1: GET current face detections
curl -s "http://localhost:5001/api/faces/{photo_id}" | python3 -m json.tool

# Step 2: Run face alignment
curl -X POST "http://localhost:5001/api/face-alignment/{photo_id}" | python3 -m json.tool

# Step 3: Verify alignment makes sense
# - Does Gemini's "center of group" match the actual center face?
# - Do age estimates seem reasonable for the era?
# - Are descriptions unique per face (not generic)?
# - If identity is known, does description match?

# Step 4: Check cost
curl -s "http://localhost:5001/api/face-alignment/{photo_id}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Cost: \${d.get(\"cost\",0):.4f}')"
```

### 5B: Verify Vida Capeluto Case
If the Vida Capeluto photo is accessible, run face alignment on it
specifically. This was the motivating example for PRD-015.
- Does the face count mismatch get detected?
- Are descriptions assigned to the correct faces?

### 5C: Screenshot the Results
If Claude Chrome or browser testing is available:
- Take screenshots of the photo page WITH face descriptions
- Verify the UI is readable and descriptions are positioned correctly
- Check mobile layout

### 5D: Cost Verification
```bash
python3 << 'EOF'
# Sum all face alignment API costs from this session
# Should be < $0.50 for 3-5 photos
# Log to session outcomes
EOF
```

Commit: `test: face alignment real photo verification — PRD-015`

---

## PHASE 6: DOCUMENTATION + SELF-ASSESSMENT (~10 min)

### 6A: Write AD
- AD-XXX: Face Alignment Implementation Results
  - What was implemented (Approach B coordinate bridging)
  - Real photo test results (accuracy, cost, mismatch handling)
  - EXIF orientation handling decision
  - Comparison to old x-sorting (improvement measured)
  - What remains: batch re-run, LoRA integration

### 6B: Update BACKLOG.md (append-only)
New items from this session:
- Batch face alignment for all 271 photos (~$7.60 estimated)
- Face alignment integration with GEDCOM context (after 61C results)
- Mobile UI refinement for face description cards
- Auto-trigger face alignment on new photo upload

### 6C: Update ROADMAP.md (with conflict check)
```bash
cp ROADMAP.md /tmp/roadmap_pre_62.md
# Make updates — append only, do not rewrite existing items
diff /tmp/roadmap_pre_62.md ROADMAP.md
wc -l ROADMAP.md  # Must stay < 150
```

### 6D: Session Outcomes
Create `docs/session_context/session_62_outcomes.md`:
- PRD-015 implementation status
- Real photo test results (N photos tested, accuracy, mismatches)
- API cost for test photos
- Comparison: old x-sorting vs new coordinate bridging
- What Session 63 should do (Platt scaling? batch re-run? merge 61C?)
- Merge instructions for 61C integration

### 6E: CHANGELOG + SESSION_HISTORY

### 6F: SELF-ASSESSMENT (mandatory per .claude/rules/self-assessment.md)
```bash
echo "=== SESSION 62 SELF-ASSESSMENT ==="
cat docs/prompts/session_62_prompt.md | head -20

echo "--- Phase 0: Prerequisites ---"
python3 -c "from app.face_alignment import run_face_alignment; print('✓')" \
  2>/dev/null || echo "✗ Module not importable"

echo "--- Phase 1: EXIF ---"
python3 -c "from app.exif_handler import normalize_orientation; print('✓')" \
  2>/dev/null || echo "✗ Module not importable"

echo "--- Phase 2: Coordinate Bridging ---"
grep -q "format_faces_for_gemini\|build_alignment_prompt" app/face_alignment.py \
  && echo "✓ Core functions exist" || echo "✗ Missing functions"

echo "--- Phase 3: API Endpoint ---"
grep -q "face-alignment" app/main.py \
  && echo "✓ Endpoint registered" || echo "✗ No endpoint"

echo "--- Phase 4: UI ---"
grep -rq "face.*description\|gemini.*description\|alignment.*card" \
  app/templates/ && echo "✓ UI elements" || echo "✗ No UI"

echo "--- Phase 5: Real Tests ---"
ls results/face_alignment_test_*.json 2>/dev/null && \
  echo "✓ Test results saved" || echo "⚠ No saved test results"

echo "--- Tests ---"
pytest tests/test_face_alignment*.py -x -q --tb=short 2>&1 | tail -3

echo "--- ROADMAP ---"
wc -l ROADMAP.md | awk '{
  print ($1<=150) ? "✓ ROADMAP ok ("$1")" : "✗ ROADMAP too long ("$1")"
}'

echo "=== WRITE ASSESSMENT ==="
# Create docs/session_context/session_62_assessment.md
```

**Fix any failures before declaring session complete.**

### 6G: Merge (if in worktree)
```bash
# If 61C has already merged: merge 62 into main
cd /path/to/main/repo
git merge session-62 --no-ff -m "merge: session 62 — PRD-015 face alignment implementation"
git worktree remove .claude/worktrees/session-62
git branch -d session-62

# If 61C has NOT merged yet: leave on branch, document merge order
echo "62 ready to merge AFTER 61C merges first" > /tmp/merge_notes.md

# If on main: just push
git push origin main
```

---

## SESSION RULES

- **CLEAR AFTER EVERY PHASE** — this is mandatory, not optional.
  Run `/clear` then re-read next phase from prompt file + context + checklist.
  Do NOT use `/compact` — it is lossy and expensive. `/clear` + re-read is correct.
  Session 61C ran out of context because it used /compact instead of /clear.
- This session focuses on PRD-015 implementation — stay in scope
- Minimal Gemini API usage — 3-5 test photos only, not bulk
- Deploy via git push (NOT Railway dashboard)
- Commit after every phase with descriptive message
- Update BOTH ROADMAP and BACKLOG when completing/deferring items
- Before editing ROADMAP/BACKLOG: save to /tmp for diff
- After editing: verify nothing lost, ROADMAP stays < 150 lines
- If in worktree: append-only to shared docs, never rewrite
- DO NOT TOUCH rhodesli_ml/* (Session 61C owns these files)
- End with self-assessment (Phase 6F) — MANDATORY
- All algorithmic decisions → ALGORITHMIC_DECISIONS.md with provenance
- Test on REAL photos, not just unit tests — Phase 5 is critical
- EXIF orientation must be handled BEFORE coordinate comparison
- Surface face count mismatches in UI (don't silently drop faces)
