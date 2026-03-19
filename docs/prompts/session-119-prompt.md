# Session 119 — ML Service End-to-End Verification (Interactive)

@docs/session_context/session-119-context.md
@tasks/lessons.md

## Goal

Verify the ML service works end-to-end in production by uploading a real photo and comparing results. This is the gate for TOOLS-002 Phase 5 (remove local InsightFace from web Dockerfile). Interactive session — user provides real-time feedback, browser verification throughout.

## CRITICAL CONSTRAINTS

1. **Browser automation is READ-ONLY on production** (Lesson 149).
2. **User uploads the test photo manually** — Claude watches logs and verifies results.
3. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`, `app/perf_cache.py`.
4. **If ML service fails**: document the failure, do NOT remove local fallback.
5. **/clear between phases** — commit first, then /clear immediately.

## Pre-Requisites

```bash
echo "119" > .claude/current_session.txt
echo "interactive" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — record count and time
```

Read:
- `docs/session_context/session-119-context.md`
- `docs/assessments/session-118-assessment.md`
- `core/ingest_inbox.py:386-465` (detect_faces wrapper)
- `core/ml_client.py`

---

## Phase 0: Orient + Health Check (5 min)

### 0A: Create session log, verify baseline tests pass
### 0B: Check ML service health via `/api/admin/ml-health`
- Record uptime (should be 12-24h+ since Session 118 deploy)
- Record `models_loaded` status
- If ML service is down: investigate Railway logs, fix, re-deploy
### 0C: Check web app health

**Commit:** `docs: session 119 phase 0 — orient`
**/clear**

---

## Phase 1: Pre-Warm ML Service (10 min)

### 1A: Warm the Model

The model lazy-loads on first request and takes 30-60s. The client timeout is 60s. To avoid a timeout on the real upload, pre-warm the model.

**Option A — Increase timeout temporarily:**
Change `core/ml_client.py` timeout from 60s to 180s. This is safe because `detect_faces()` runs in a background thread during upload.

**Option B — Add warm endpoint:**
Add `GET /api/v1/warm` to `ml_service/detect.py` that calls `get_face_analyzer()` and returns `{"status": "warm", "model": "buffalo_l"}`. Call it from `/api/admin/ml-health` or manually.

Choose whichever is simpler. The goal is: first real detection should not timeout.

### 1B: Trigger Model Load

Call the warm endpoint or send a tiny test image to force model load. Verify via Railway logs that the model loaded successfully.

### 1C: Re-check Health

Hit `/api/admin/ml-health` again — `models_loaded` should now be `true`.

**Commit:** `feat(ml): session 119 phase 1 — ML service pre-warm`
**/clear**

---

## Phase 2: Upload Test Photo (15 min)

### 2A: Select Test Photo

Pick a photo already in the archive that has known face count and embeddings:
```bash
# Find a photo with 2-4 faces and existing embeddings
python -c "
import numpy as np
emb = np.load('data/embeddings.npy', allow_pickle=True)
from collections import Counter
counts = Counter(e['filename'] for e in emb)
for fname, count in counts.most_common(10):
    if 2 <= count <= 4:
        print(f'{fname}: {count} faces')
        break
"
```

### 2B: User Uploads Photo

Ask user to upload the selected photo via the web UI. Claude watches:
1. Railway web app logs for `[ml-service]` prefix
2. Railway ml-service logs for detection request
3. Upload completion and face count

### 2C: Verify Results in Browser (READ-ONLY)

Navigate to the uploaded photo's page:
- Face count matches expected?
- Face crops render correctly?
- Identities created?
- Cross-batch proposals generated?

**Commit:** `docs: session 119 phase 2 — upload verification results`
**/clear**

---

## Phase 3: Embedding Comparison (15 min)

### 3A: Get Local Embeddings

For the test photo, extract embeddings from `data/embeddings.npy`:
```python
import numpy as np
emb = np.load('data/embeddings.npy', allow_pickle=True)
local_faces = [e for e in emb if e['filename'] == 'TEST_PHOTO.jpg']
```

### 3B: Get ML Service Embeddings

If the upload went through the ML service, the new embeddings are also in `data/embeddings.npy` (saved by the upload pipeline). Compare:

```python
from numpy.linalg import norm

for local, cloud in zip(local_faces, cloud_faces):
    cos_sim = np.dot(local['embeddings'][0], cloud['embeddings'][0]) / (
        norm(local['embeddings'][0]) * norm(cloud['embeddings'][0])
    )
    print(f"Cosine similarity: {cos_sim:.6f}")
```

### 3C: Document Results

In session log, record:
- Face count: local vs ML service
- Cosine similarity per face
- Bbox differences (if any)
- PASS/FAIL verdict

AD-229 criterion: cosine similarity ≥0.999

**Commit:** `docs: session 119 phase 3 — embedding comparison results`
**/clear**

---

## Phase 4: Performance & Monitoring (10 min)

### 4A: Check Detection Time

From Railway logs, record:
- Model load time (first request)
- Detection time per photo (subsequent requests)
- Compare to local detection time (~2-5s)

### 4B: Check Railway Resource Usage

Via Railway MCP or dashboard:
- ML service memory usage
- ML service CPU usage
- Estimated monthly cost

### 4C: Update AD-229

Update the stability criteria checklist:
- [ ] 24h uptime → record current uptime
- [ ] 3 successful uploads → record count
- [ ] Cosine similarity ≥0.999 → record value
- [ ] Billing ≤$5/mo → record estimate

If all criteria met: recommend proceeding with Phase 5 in next session.
If not: document what's missing and timeline.

**Commit:** `docs: session 119 phase 4 — performance + AD-229 update`
**/clear**

---

## Phase 5: Harness Outputs (10 min)

### 5A: Final Documentation

1. Assessment: `docs/assessments/session-119-assessment.md`
2. CHANGELOG: v0.99.29 (if code changes made)
3. ROADMAP: TOOLS-002 Phase 5 status update
4. SESSION_HISTORY: Session 119 entry
5. Session log: `docs/session_logs/session-119-log.md`

### 5B: Browser Verification (READ-ONLY)

Screenshots of:
1. Uploaded photo with face crops
2. ML health endpoint (models_loaded: true)
3. Any new proposals generated

**Commit:** `docs: session 119 harness outputs — assessment, changelog, roadmap`

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| ML service healthy? | `/api/admin/ml-health` | `models_loaded: true` |
| Upload went through ML service? | Railway logs for `[ml-service]` | Present |
| Face count matches? | Compare local vs ML service | Same count |
| Cosine similarity ≥0.999? | Embedding comparison | ≥0.999 |
| Crops render correctly? | Browser screenshot | Visible |
| AD-229 updated? | `grep "AD-229" docs/ml/ALGORITHMIC_DECISIONS.md` | Updated |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | `ls docs/assessments/session-119-assessment.md` | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

This session is mostly sequential — each phase depends on the previous:
- Phase 0 (health) → Phase 1 (warm) → Phase 2 (upload) → Phase 3 (compare)
- Phase 4 (monitoring) can partially overlap with Phase 3
- Phase 5 (harness) is independent
