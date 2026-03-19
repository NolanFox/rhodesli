# Session 118 — ML Service Verification + Remaining TOOLS-002 + Codex Audit Trial

@docs/session_context/session-118-context.md
@tasks/lessons.md

## Goal

Verify the ML service works end-to-end in production, complete remaining TOOLS-002 phases, run a Codex CLI audit trial to evaluate cross-AI review, and close all harness gaps from Sessions 115-117. This is a verification-first session — no new features until existing work is confirmed working.

## CRITICAL CONSTRAINTS

1. **VERIFICATION FIRST** — Phases 1-2 must pass before any new code. If ML service is broken, fix it before proceeding.
2. **ZERO REGRESSIONS** — `make test-fast` before every commit. Both test suites before deploy.
3. **Browser automation is READ-ONLY on production** (Lesson 149).
4. **/clear between phases** — commit first, then /clear immediately.
5. **DO NOT remove local InsightFace** until ML service is verified stable for 24h+ in production.
6. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`, `app/perf_cache.py`.

## Pre-Requisites

```bash
echo "118" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — record count and time
```

Read these files to orient:
- `docs/session_context/session-118-context.md`
- `docs/assessments/session-117-assessment.md`
- `docs/assessments/session-116-assessment.md`
- `core/ingest_inbox.py:386-465` (detect_faces wrapper)
- `core/ml_client.py`

---

## Phase 0: Orient + ML Service Health Check (15 min)

### 0A: Check ML Service Deploy Status

```bash
# Check Railway deploy status
mcp__railway-mcp-server__list-deployments (service: ml-service, limit: 2)

# Check web app health
curl -s https://rhodesli.nolanandrewfox.com/health | python3 -m json.tool
```

### 0B: Check ML Service Health From Web App

The web app has `ML_SERVICE_URL=http://ml-service.railway.internal:5002` configured.
Test if the web app can reach the ML service:

1. Add a temporary health check endpoint to the web app:
```python
# In app/sync_routes.py or similar admin-only route file
@rt("/api/admin/ml-health")
def get(sess=None):
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    from core.ml_client import get_ml_client
    import asyncio
    client = get_ml_client()
    if not client.is_configured:
        return {"status": "not_configured", "ml_service_url": ""}
    try:
        result = asyncio.run(client.health())
        return {"status": "connected", **result}
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}
```

2. Deploy and test: `curl https://rhodesli.nolanandrewfox.com/api/admin/ml-health`

### 0C: If ML Service Is Down

If the ml-service is not running or unreachable:
1. Check Railway logs: `mcp__railway-mcp-server__get-logs (service: ml-service, logType: deploy)`
2. Check if it was scaled down by Railway (hobby plan sleep)
3. Redeploy if needed: `railway service redeploy --service ml-service --yes`
4. Document the issue in session log

### 0D: Set Up Session Log

Create `docs/session_logs/session-118-log.md` with phase checklist.

**Commit:** `docs: session 118 phase 0 — orient + ML service health check`
**/clear**

---

## Phase 1: Local vs Cloud Detection Comparison (25 min)

This is the critical verification: same image, same model, same results?

### 1A: Select Test Image

Choose a photo from the existing archive with known face count:
```bash
# Find a photo with known faces (e.g., 3+ faces for a good test)
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from core.photo_registry import PhotoRegistry
reg = PhotoRegistry.load()
# Find a photo with 3+ faces
for pid, photo in reg.photos.items():
    if len(photo.get('face_ids', [])) >= 3:
        print(f'{pid}: {photo[\"path\"]} — {len(photo[\"face_ids\"])} faces')
        break
"
```

### 1B: Run Local Detection

```python
from core.ingest_inbox import extract_faces
from pathlib import Path

# Run LOCAL detection (bypasses ML service)
faces_local, w_local, h_local = extract_faces(Path("raw_photos/TEST_IMAGE.jpg"))
print(f"Local: {len(faces_local)} faces, {w_local}x{h_local}")
for i, f in enumerate(faces_local):
    print(f"  Face {i}: bbox={f['bbox']}, det_score={f['det_score']:.4f}, quality={f['quality']:.4f}")
    print(f"    mu[:5]={f['mu'][:5].tolist()}")
```

### 1C: Run ML Service Detection

```python
from core.ml_client import MLServiceClient
import asyncio

client = MLServiceClient(base_url="http://ml-service.railway.internal:5002", token="...")
# OR: test from local against Railway's internal URL (won't work locally)
# Instead, test via the detect_faces wrapper:

from core.ingest_inbox import detect_faces
# Force ML service path by setting env var temporarily
import os
os.environ["ML_SERVICE_URL"] = "http://ml-service.railway.internal:5002"
faces_ml, w_ml, h_ml = detect_faces(Path("raw_photos/TEST_IMAGE.jpg"))
```

**Alternative for local testing:** If the ML service isn't reachable from local machine (internal Railway networking), run the comparison via a script deployed to Railway, or add a `/api/admin/detect-compare` endpoint that runs both paths and returns the diff.

### 1D: Compare Results

```python
import numpy as np

assert len(faces_local) == len(faces_ml), f"Face count mismatch: {len(faces_local)} vs {len(faces_ml)}"
assert w_local == w_ml and h_local == h_ml, "Image size mismatch"

for i, (fl, fm) in enumerate(zip(faces_local, faces_ml)):
    # Compare embeddings
    cosine_sim = np.dot(fl['mu'], fm['mu']) / (np.linalg.norm(fl['mu']) * np.linalg.norm(fm['mu']))
    print(f"Face {i}: cosine_sim={cosine_sim:.6f}, bbox_diff={np.abs(np.array(fl['bbox']) - np.array(fm['bbox'])).sum():.1f}")
    assert cosine_sim > 0.999, f"Embedding mismatch on face {i}: cosine_sim={cosine_sim}"
```

### 1E: Document Results

Log comparison results in session log:
- Face count: local vs ML service
- Embedding cosine similarity per face
- Bbox differences
- PASS/FAIL verdict

### 1F: Tests

No new tests needed — this is a verification phase, not code change.
Verify existing tests still pass: `make test-fast`

**Commit:** `docs: session 118 phase 1 — local vs cloud detection comparison results`
**/clear**

---

## Phase 2: Codex CLI Audit Trial (20 min)

### 2A: Rationale

The Codex CLI (OpenAI) provides a "second opinion" perspective on code quality.
Per the user's multi-agent strategy (Sessions 97-100 memory), Codex catches different
issues than Claude — particularly data integrity problems, edge cases, and silent failures.

This is an EXPERIMENTAL trial to evaluate whether Codex auditing adds value to the Rhodesli workflow.

### 2B: Run Codex Audit

```bash
# Audit the ML service integration code specifically
codex "Review the ML service integration in core/ingest_inbox.py (the detect_faces function at line 386-465) and core/ml_client.py. Focus on:
1. Edge cases in the async/sync boundary handling
2. Data format correctness (PFE embedding transformation)
3. Error handling completeness
4. Silent failure modes that could cause data corruption
5. Any security concerns with the HTTP client
Report findings as: CRITICAL / HIGH / MEDIUM / LOW with specific line numbers."
```

### 2C: Run Codex Audit on Community Routing

```bash
codex "Review tests/test_community_routing_safety.py and the CommunityMiddleware in app/main.py:477-536. Check:
1. Are there any data-modifying routes that bypass the community guard?
2. Can the upload route be tricked into assigning photos to wrong community?
3. Are there HTMX POST endpoints missing community prefix?
4. Any XSS or injection risks in community slug handling?
Report findings with specific file:line references."
```

### 2D: Evaluate Codex Results

In session log, document:
- What Codex found that we didn't catch
- What Codex flagged that was already addressed
- False positives (things Codex flagged that aren't real issues)
- **Verdict**: Is Codex auditing worth adding to the regular workflow?

If Codex finds actionable issues:
- Fix CRITICAL/HIGH issues in this session
- Log MEDIUM/LOW to BACKLOG

### 2E: Decision: Adopt or Skip

Based on results, make a harness decision (HD-NNN):
- If valuable: add Codex audit step to `.claude/rules/` as a post-implementation check
- If not valuable: document why and skip
- If mixed: define specific scopes where Codex adds value (e.g., data integrity only)

**Commit:** `docs: session 118 phase 2 — Codex audit trial results + HD-NNN decision`
**/clear**

---

## Phase 3: TOOLS-002 Phase 4 — Auto-Clustering After Detection (25 min)

**Only proceed if Phase 1 passes (ML service verified working).**

### 3A: Current State

After `process_directory()` runs face detection:
1. Faces are saved to embeddings.npy ✓
2. Photos registered in photo_registry ✓
3. Crops generated ✓
4. INBOX identities created ✓
5. **Cross-batch matching NOT triggered** — this is the gap

### 3B: Wire Cross-Batch Matching

In `app/upload_routes.py` `_background_ingest()`, after `process_directory()` returns:

```python
# After line ~924 (community tagging), add:
if result.get("face_ids"):
    try:
        from core.cross_batch_matching import find_cross_batch_matches
        from core.ml_run_logger import MLRunContext

        # Get Supabase client for logging
        supabase_client = _get_supabase_client()  # implement this helper

        with MLRunContext(supabase_client, "cross_batch",
                         triggered_by="upload_webhook",
                         community_id=upload_community_id) as run:
            matches = find_cross_batch_matches(
                new_face_ids=result["face_ids"],
                identities=registry.identities,
                face_data=face_data_cache,
                photo_registry=photo_registry,
                community_id=upload_community_id,
            )
            run.set_result({"matches": len(matches), "proposals_written": 0})

        if matches:
            # Write to ml_proposals Supabase table
            _write_proposals_to_supabase(supabase_client, matches, run_id=run.run_id)

        logging.info("[upload] Cross-batch matching: %d matches for %d new faces",
                    len(matches), len(result["face_ids"]))
    except Exception as e:
        logging.error("[upload] Cross-batch matching failed: %s", e)
```

### 3C: Verify Cross-Batch Already Exists

**Check first**: `core/cross_batch_matching.py` might already be wired into the upload pipeline
(Session 109). Grep for it in upload_routes.py before adding duplicate code.

```bash
grep -n "cross_batch" app/upload_routes.py
```

### 3D: Tests

- Test: after upload, cross-batch matching is triggered
- Test: ML run is logged with correct pipeline_type and community_id
- Test: proposals are written to Supabase

**Commit:** `feat(upload): session 118 phase 3 — auto-clustering after detection (TOOLS-002 Phase 4)`
**/clear**

---

## Phase 4: TOOLS-002 Phase 5 — Evaluate Local ML Removal (15 min)

**Only proceed if Phase 1 confirms ML service is stable.**

### 4A: Evaluate (DO NOT IMPLEMENT YET)

The goal is to remove InsightFace model downloads from the web Dockerfile to shrink the image.
But this makes the ML service a hard dependency — if it's down, uploads fail.

**Decision criteria:**
- Has the ML service been running for 24h+ without issues? → Proceed
- Has it crashed or restarted? → Defer
- Is Railway billing acceptable with two services? → Check

### 4B: If Proceeding — Plan Only

Create a detailed plan for Phase 5 implementation in the session log:
1. What to remove from Dockerfile (model downloads, InsightFace deps)
2. What to keep (`extract_faces()` code stays as dead fallback)
3. What to add (health gate: uploads blocked if ML service down and no local models)
4. Estimated image size reduction
5. Risk assessment

### 4C: Decision

AD-229: ML service as mandatory dependency — evaluate and decide.
If the ML service has been stable, create the AD entry recommending Phase 5.
If not stable, document the stability issues and defer.

**Commit:** `docs: session 118 phase 4 — TOOLS-002 Phase 5 evaluation (AD-229)`
**/clear**

---

## Phase 5: Harness Cleanup + Final Documentation (15 min)

### 5A: Fix Remaining Harness Gaps

From the Session 115-117 audit:
1. Update BACKLOG.md COMMUNITY-017 entry with PRD-052 breadcrumb
2. Update BACKLOG.md version header to current date
3. Verify Session 117 context file has post-session planning section

### 5B: Deploy + Browser Verification

```bash
git push origin main
```

Browser verification (READ-ONLY):
1. Health endpoint: `/api/health`
2. ML health endpoint: `/api/admin/ml-health` (new)
3. Root landing: neutral platform page
4. Fox Family: `/c/fox-family/` with correct prefixes
5. Upload page loads (do NOT actually upload)
6. Person detail page with face crops

### 5C: Harness Outputs

1. Assessment: `docs/assessments/session-118-assessment.md`
2. CHANGELOG: v0.99.28
3. ROADMAP: update TOOLS-002 status
4. SESSION_HISTORY: Session 118 entry
5. Session log archive
6. BACKLOG updates

**Commit:** `docs: session 118 harness outputs — assessment, changelog, roadmap`

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| ML service health? | `/api/admin/ml-health` | status: connected |
| Local vs cloud detection? | Session log comparison | cosine_sim > 0.999 |
| Codex audit done? | Session log verdict | Documented |
| Cross-batch wiring? | `grep "cross_batch" app/upload_routes.py` | Present (or already existed) |
| Phase 5 evaluated? | AD-229 in ALGORITHMIC_DECISIONS.md | Present |
| Harness gaps fixed? | BACKLOG breadcrumbs, todo.md | Updated |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | `ls docs/assessments/session-118-assessment.md` | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

- Phase 1 (verification) and Phase 2 (Codex audit) are independent and CAN run in parallel
- Phase 3 depends on Phase 1 passing
- Phase 4 depends on Phase 1 + Phase 3
- Phase 5 is independent (harness cleanup)

**Recommendation:** Run Phase 1 and Phase 2 in parallel (different files, no conflicts). Then sequential for Phase 3-5.
