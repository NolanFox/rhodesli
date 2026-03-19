# Session 118 — Codex Audit → ML Verification → TOOLS-002 Completion

@docs/session_context/session-118-context.md
@tasks/lessons.md

## Goal

Audit-first session: run Codex CLI against Sessions 115-117 work to catch issues before building more, verify the ML service end-to-end in production, complete remaining TOOLS-002 phases, and close all harness gaps. The Codex audit is an experimental strategy trial — evaluate whether cross-AI review adds value to the Rhodesli workflow.

## Strategy: Codex-First, Then Build

```
Step 1: Codex audits Sessions 115-117 code (ML service, community routing, pipeline wiring)
Step 2: Triage findings → fix CRITICAL/HIGH → adjust remaining phases if needed
Step 3: ML service verification (health check + local vs cloud comparison)
Step 4: TOOLS-002 Phase 4-5 (if verification passes)
Step 5: Codex audits Session 118 work (evaluate the strategy)
Step 6: Decision: adopt Codex auditing into harness or not (HD-NNN)
```

## CRITICAL CONSTRAINTS

1. **AUDIT FIRST** — Run Codex before any new code. Fix findings before proceeding.
2. **VERIFICATION BEFORE FEATURES** — ML service must be verified before Phase 4-5.
3. **ZERO REGRESSIONS** — `make test-fast` before every commit.
4. **Browser automation is READ-ONLY on production** (Lesson 149).
5. **/clear between phases** — commit first, then /clear immediately.
6. **DO NOT remove local InsightFace** until ML service is verified stable for 24h+.
7. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`, `app/perf_cache.py`.

## Pre-Requisites

```bash
echo "118" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — record count and time
```

Read:
- `docs/session_context/session-118-context.md`
- `docs/assessments/session-117-assessment.md`
- `core/ingest_inbox.py:386-465` (detect_faces wrapper)
- `core/ml_client.py`

---

## Phase 0: Orient + Session Log (5 min)

### 0A: Create session log, verify baseline tests pass
### 0B: Check ML service deploy status via Railway MCP
### 0C: Check web app health

**Commit:** `docs: session 118 phase 0 — orient`
**/clear**

---

## Phase 1: Codex Audit of Sessions 115-117 (25 min)

### 1A: Audit ML Service Integration

Run Codex in non-interactive mode to audit the core ML service work:

```bash
codex exec "You are auditing code in a heritage photo archive (Rhodesli). Review these files for bugs, edge cases, data corruption risks, and security issues:

1. core/ingest_inbox.py — Focus on the detect_faces() function (search for 'def detect_faces'). Check:
   - Async/sync boundary handling (asyncio.run vs run_until_complete)
   - PFE embedding transformation correctness
   - Error handling completeness — can any exception cause data corruption?
   - Silent failure modes that could cause embeddings to be wrong

2. core/ml_client.py — The HTTP client for the ML service. Check:
   - Timeout handling
   - Auth token security
   - Connection pooling / resource leaks
   - Thread safety of the singleton

3. ml_service/detect.py — The ML service detection endpoint. Check:
   - Input validation (what happens with corrupted images?)
   - Response format consistency
   - Model loading reliability
   - Memory leaks from repeated requests

4. core/ml_run_logger.py — ML run provenance logger. Check:
   - Supabase error handling
   - Thread safety
   - Any path that could block the main request

Report as: SEVERITY (CRITICAL/HIGH/MEDIUM/LOW) | FILE:LINE | DESCRIPTION | SUGGESTED FIX

Only report real issues, not style preferences."
```

### 1B: Audit Community Routing Safety

```bash
codex exec "Review the community routing safety implementation in this heritage photo archive:

1. tests/test_community_routing_safety.py — Are these tests comprehensive enough? What's missing?

2. app/main.py — Search for 'class CommunityMiddleware'. Check:
   - Can the community_slug be manipulated via URL crafting?
   - Are there any routes that bypass the middleware?
   - Can community_explicit be spoofed?

3. app/upload_routes.py — Search for 'def post' (the upload handler). Check:
   - Can the upload_community hidden field be tampered with?
   - What happens if community_slug doesn't match upload_community?
   - Is there a race condition between community validation and file save?

Report only CRITICAL and HIGH findings with specific file:line references."
```

### 1C: Triage Results

For each Codex finding:
1. **Verify**: Is this a real issue? Read the code Codex references.
2. **Classify**: CRITICAL (fix now) / HIGH (fix now) / MEDIUM (BACKLOG) / LOW (skip) / FALSE POSITIVE
3. **Fix or Log**: Fix CRITICAL/HIGH immediately. MEDIUM → BACKLOG with breadcrumb.

Log ALL findings and dispositions in the session log, even false positives.

### 1D: Adjust Remaining Phases

If Codex found CRITICAL issues:
- Phase 2 (verification) must wait until fixes are deployed
- Add fix tasks to Phase 2

If Codex found nothing actionable:
- Proceed as planned

**Commit:** `fix/docs: session 118 phase 1 — Codex audit findings + fixes`
**/clear**

---

## Phase 2: ML Service Health + End-to-End Verification (25 min)

### 2A: Add ML Health Endpoint

Add a `/api/admin/ml-health` endpoint to the web app (admin-only):
```python
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

### 2B: Deploy and Check ML Service

```bash
git push origin main
# Wait for deploy
curl -s https://rhodesli.nolanandrewfox.com/api/admin/ml-health
```

### 2C: Local vs Cloud Detection Comparison

Since Railway internal networking is not accessible from local, create a comparison
endpoint or script that runs on Railway:

**Option A — Admin endpoint (preferred):**
Add `/api/admin/detect-compare` that:
1. Takes a photo_id parameter
2. Runs `extract_faces()` (local) on the photo
3. Runs `detect_faces()` (ML service) on the same photo
4. Returns face count, embedding cosine similarity, bbox differences

**Option B — Log-based verification:**
1. Upload a test photo via the web UI
2. Check Railway logs for `[ml-service]` prefix (ML service was used)
3. OR check for `[ml-service] Failed, falling back` (service was down)
4. Verify the photo appears correctly with detected faces in the UI

### 2D: Document Results

In session log, record:
- ML service health status
- Detection path used (ML service or local fallback?)
- If comparison done: face count match, cosine similarity values
- PASS/FAIL verdict for ML service end-to-end

**Commit:** `feat(admin): session 118 phase 2 — ML health endpoint + verification results`
**/clear**

---

## Phase 3: TOOLS-002 Phase 4 — Auto-Clustering Verification (15 min)

### 3A: Check If Already Wired

Cross-batch matching may already be triggered in the upload pipeline (Session 109).

```bash
grep -n "cross_batch" app/upload_routes.py
```

If already wired: verify it works with community_id and ml_runs logging. Skip to Phase 4.
If not wired: add the integration per the context file.

### 3B: Wire or Verify

If wiring needed, add cross-batch matching trigger in `_background_ingest()` after
`process_directory()` returns. Use `MLRunContext` for provenance logging.

### 3C: Tests

- Verify existing cross-batch tests still pass
- Add test for community-scoped cross-batch matching if missing

**Commit:** `feat/docs: session 118 phase 3 — cross-batch clustering verification`
**/clear**

---

## Phase 4: TOOLS-002 Phase 5 — Local ML Removal Evaluation (10 min)

### 4A: Evaluate Stability

Based on Phase 2 results:
- Is ML service reachable from web app? → Required for Phase 5
- Has it been running without crashes? → Check deploy history
- Is Railway billing acceptable? → Check or ask user

### 4B: AD-229 Decision

Write AD-229: ML Service as Mandatory Dependency
- If stable: recommend removing model downloads from web Dockerfile in next session
- If not stable: defer with specific stability criteria

### 4C: Plan (Don't Implement)

If proceeding, document the exact Dockerfile changes needed:
- Lines to remove (model downloads, InsightFace system deps)
- Expected image size reduction
- Fallback behavior when ML service is down

**Commit:** `docs: session 118 phase 4 — AD-229 ML service stability evaluation`
**/clear**

---

## Phase 5: Post-Work Codex Audit (15 min)

### 5A: Audit Session 118 Changes

Run Codex against the code written in this session:

```bash
# Get the diff of what changed
git diff HEAD~N..HEAD --name-only  # N = number of commits this session

codex exec "Review the changes made in the last session to this heritage photo archive.
Focus on: [list the specific files changed].
Check for: bugs, edge cases, data corruption risks, regressions.
Compare to the existing test coverage — are there gaps?
Report CRITICAL/HIGH findings only."
```

### 5B: Evaluate Codex Strategy

In the session log, document:
1. **Phase 1 findings**: How many real issues did Codex catch?
2. **Phase 5 findings**: How many real issues in new code?
3. **False positive rate**: What percentage of findings were not real?
4. **Time cost**: How long did each audit take?
5. **Verdict**: Is this worth adding to the regular workflow?

### 5C: HD Decision

Write HD-NNN: Codex CLI Audit Strategy
- **If valuable**: Add to `.claude/rules/codex-audit.md` with trigger conditions
- **If mixed**: Define specific scopes (e.g., only for data-layer changes)
- **If not valuable**: Document why and close

**Commit:** `docs: session 118 phase 5 — Codex strategy evaluation + HD-NNN`
**/clear**

---

## Phase 6: Harness Outputs (10 min)

### 6A: Fix Remaining Gaps

1. BACKLOG.md: Add PRD-052 breadcrumb to COMMUNITY-017, update version header
2. Verify all session logs exist (115, 116, 117, 118)
3. Verify all assessments exist

### 6B: Final Documentation

1. Assessment: `docs/assessments/session-118-assessment.md`
2. CHANGELOG: v0.99.28
3. ROADMAP: TOOLS-002 Phase 4 status
4. SESSION_HISTORY: Session 118 entry
5. Session log: `docs/session_logs/session-118-log.md`

### 6C: Browser Verification (READ-ONLY)

Screenshots of:
1. `/api/admin/ml-health` response
2. Root landing page
3. Fox Family landing page
4. Upload page (no actual upload)
5. Person detail with face crops

**Commit:** `docs: session 118 harness outputs — assessment, changelog, roadmap`

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| Codex Phase 1 audit done? | Session log has findings table | Documented |
| ML health endpoint exists? | `curl .../api/admin/ml-health` | Returns status |
| Detection comparison done? | Session log has results | PASS or documented issues |
| Cross-batch verified? | `grep "cross_batch" app/upload_routes.py` | Present |
| AD-229 documented? | `grep "AD-229" docs/ml/ALGORITHMIC_DECISIONS.md` | Present |
| Codex strategy decided? | HD-NNN in HARNESS_DECISIONS.md | Present |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | `ls docs/assessments/session-118-assessment.md` | Exists |
| All session logs exist? | `ls docs/session_logs/session-11{5,6,7,8}-log.md` | All 4 exist |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

**Phase 1** (Codex audit) can run both audit commands in parallel (independent scopes).
**Phase 2** (ML verification) and **Phase 5** (post-work audit) are sequential.
**Phase 3** (clustering) depends on Phase 2 passing.
**Phase 6** (harness) is independent of Phase 3-5.
