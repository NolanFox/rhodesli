# Session 115 — Community Routing Safety + ML Service Extraction Phase 1

@docs/session_context/session-115-context.md
@docs/prds/052_community_routing_safety.md
@docs/architecture/ML_SERVICE.md
@tasks/lessons.md

## Goal

Harden community routing for external sharing (COMMUNITY-017) and begin ML service extraction (TOOLS-002 Phase 1). After this session: (1) every data-modifying route is verified safe against community mis-assignment, (2) a standalone ML service skeleton exists with face detection endpoint and tests, (3) ml_runs schema supports environment tracking and community-scoped runs.

## CRITICAL CONSTRAINTS

1. **ZERO REGRESSIONS** — run `make test-fast` before every commit. Both test suites before deploy.
2. **Browser automation is READ-ONLY on production** — never click action buttons (Lesson 149).
3. **/clear between phases** — non-negotiable. Commit first, then /clear immediately.
4. **DO NOT modify `core/ingest_inbox.py`** — extract/copy code FROM it to ml_service, don't change it. The existing face detection pipeline must remain intact.
5. **DO NOT modify the CommunityMiddleware class** — audit it, test around it, add guards to route handlers. The middleware itself is stable.
6. **DO NOT touch**: `app/perf_cache.py`, `core/neighbors.py` (frozen), `embeddings.npy` handling.
7. **Schema migrations are additive-only** — ALTER TABLE ADD COLUMN with defaults. Never drop or rename.
8. **ML service is LOCAL-ONLY this session** — do NOT deploy to Railway or wire into web app. That's Session 116.

## Pre-Requisites (do these FIRST, before Phase 0)

```bash
echo "115" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — record time and pass count
```

Read these files to orient:
- `docs/session_context/session-115-context.md`
- `docs/prds/052_community_routing_safety.md`
- `docs/assessments/session-114-assessment.md`
- `docs/architecture/ML_SERVICE.md`
- `docs/architecture/ml_service/API.md`

---

## Phase 0: Orient + Baseline (10 min)

### 0A: Verify Session 114 Deploy
```bash
curl -s https://rhodesli.nolanandrewfox.com/health | python -m json.tool
```
Confirm health endpoint returns 200 with expected counts.

### 0B: Set Up Session Log
Create `docs/session_logs/session-115-log.md` with phase checklist mirroring this prompt.

### 0C: Read Critical Code
1. Read `app/main.py:477-536` — CommunityMiddleware + is_community_explicit()
2. Read `app/upload_routes.py` — find all POST handlers, check for community guards
3. Skim `core/ingest_inbox.py:1-80` — understand the face detection entry points
4. Read `scripts/migrations/create_ml_run_tables.sql` — current ml_runs schema

### 0D: Baseline Metrics
Record in session log:
- App test count and time
- ML test count and time
- Current ml_runs row count (if accessible via Supabase)

**Commit:** `docs: session 115 phase 0 — orient + session log`
**/clear**

---

## Phase 1: Community Routing Audit + Hardening (40 min)

This phase ensures every data-modifying route is safe before external sharing.

### 1A: Audit All POST/PUT/DELETE Routes

Systematically grep every route file for data-modifying endpoints:

```bash
grep -rn "@app\.\(post\|put\|delete\)\|@rt\(" app/ --include="*.py" | grep -v "test"
```

For EACH data-modifying route found, classify:

| Route | File | Community Guard? | Risk |
|-------|------|-------------------|------|
| POST /upload | upload_routes.py | ? | HIGH |
| POST /confirm | identity_routes.py | ? | MEDIUM |
| POST /annotation | engagement_routes.py | ? | HIGH |
| ... | ... | ... | ... |

The classification rules:
- **Admin-only routes**: OK — sole admin is implicitly Rhodes-scoped. Document this assumption.
- **Contributor/public routes**: MUST check `is_community_explicit()` or require `/c/{slug}/` prefix.
- **API routes**: Skip middleware by design — verify they get community from request body/params, not middleware.

### 1B: Fix Any Unguarded Write Routes

For each unguarded contributor/public write route:
1. Add `is_community_explicit()` check at the top
2. If not explicit: return 400 with clear error message asking user to navigate via community page
3. Do NOT silently default to Rhodes

**Important**: Admin-only routes protected by `_check_admin()` are acceptable without community guard — the admin knows which community they're in. But document this assumption in the test file as a comment.

### 1C: Verify Upload Path End-to-End

Trace the full upload flow:
1. `POST /upload` → where does community_id come from?
2. Does `_background_ingest()` use the correct community?
3. Does the photo end up in the right `photo_communities` entry?
4. What happens if `is_community_explicit()` is False? Does the route reject?

Read the actual code path, don't assume. Document findings in session log.

### 1D: Write Comprehensive Tests

Create `tests/test_community_routing_safety.py`:

```python
# Test 1: Upload on explicit community route succeeds
# Test 2: Upload on non-explicit route (no /c/ prefix) is rejected for non-admin
# Test 3: Admin upload on non-explicit route still works (admin is implicitly scoped)
# Test 4: Annotation submission on non-explicit route is rejected for non-admin
# Test 5: Platform root (/) renders neutral page for anonymous user
# Test 6: Platform root (/) redirects logged-in user appropriately
# Test 7: All data-modifying routes are covered by either admin guard or community guard
# Test 8: is_community_explicit() returns False for bare URLs
# Test 9: is_community_explicit() returns True for /c/{slug}/ URLs
# Test 10: Existing test_community_prefix_audit still passes (no regressions)
```

### 1E: 2nd/3rd Order Effects

- **HTMX endpoints**: POST endpoints called by HTMX must include community prefix in the `hx-post` URL. The existing `test_community_prefix_audit.py` catches static HTML, but verify it also catches `hx-post` attributes.
- **Email notification links**: If we send emails with links, they must include `/c/{slug}/` prefix. Check `app/notification_routes.py` or email templates.
- **API endpoints**: `/api/` routes skip middleware — verify they get community context from request body or query params where needed.

### Tests
Run `make test-fast` — must pass with 0 failures.
Run new tests specifically: `pytest tests/test_community_routing_safety.py -v`

**Commit:** `feat(community): session 115 phase 1 — community routing audit + safety tests (PRD-052)`
**/clear**

---

## Phase 2: ML Service Skeleton (45 min)

Create a standalone FastAPI ML service that can detect faces and extract embeddings. This session: local only. Session 116: deploy to Railway.

### 2A: Directory Structure

```
ml_service/
  __init__.py
  main.py              # FastAPI app + health endpoint
  detect.py            # Face detection endpoint
  config.py            # Environment config
  Dockerfile           # Separate from web service
  requirements.txt     # ML-specific dependencies
  tests/
    __init__.py
    test_health.py      # Health endpoint test
    test_detect.py      # Face detection test (with mock)
    conftest.py         # Shared fixtures
```

### 2B: FastAPI Application (`ml_service/main.py`)

```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import os, time

app = FastAPI(title="Rhodesli ML Service", version="0.1.0")

# Auth: Bearer token (ML_SERVICE_TOKEN env var)
ML_SERVICE_TOKEN = os.getenv("ML_SERVICE_TOKEN", "dev-token")

async def verify_token(authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {ML_SERVICE_TOKEN}":
        raise HTTPException(status_code=401)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "models_loaded": _models_loaded(),
        "execution_environment": os.getenv("EXECUTION_ENVIRONMENT", "local"),
        "uptime_seconds": time.time() - _start_time,
    }
```

### 2C: Face Detection Endpoint (`ml_service/detect.py`)

Extract the face detection logic from `core/ingest_inbox.py` `extract_faces()`. Key decisions:
- Accept image as multipart upload OR R2 URL
- Return JSON with faces array (bbox, embedding, det_score, quality, landmarks)
- Log processing time
- Include model version info in response

```python
@app.post("/api/v1/detect-and-embed", dependencies=[Depends(verify_token)])
async def detect_and_embed(file: UploadFile):
    """Detect faces and extract 512-dim PFE embeddings from a photo."""
    # 1. Save uploaded file to temp path
    # 2. Call extract_faces() (copied from ingest_inbox.py)
    # 3. Return structured response with model_info
    return {
        "faces": [...],
        "image_size": [width, height],
        "processing_time_ms": elapsed,
        "model_info": {
            "insightface_version": insightface.__version__,
            "detection_model": "buffalo_l",
            "embedding_dim": 512,
        }
    }
```

**CRITICAL**: Copy the detection logic from `core/ingest_inbox.py` — do NOT import from it. The ML service must be fully standalone. If `extract_faces()` has dependencies on other core modules, copy those too. Keep the copy minimal.

### 2D: ML Service Dockerfile

```dockerfile
FROM python:3.11-slim

# System deps (same as web Dockerfile)
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*

# Python deps
COPY ml_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Pre-download models at build time (same strategy as web Dockerfile)
RUN python -c "from insightface.app import FaceAnalysis; FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])"

COPY ml_service/ /app/ml_service/
WORKDIR /app

ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV EXECUTION_ENVIRONMENT=railway_ml_service

EXPOSE 5002
CMD ["uvicorn", "ml_service.main:app", "--host", "0.0.0.0", "--port", "5002"]
```

### 2E: ML Service requirements.txt

```
fastapi>=0.100
uvicorn
insightface==0.7.3
onnxruntime>=1.20
opencv-python-headless<4.11
numpy
Pillow
python-multipart
```

Keep this MINIMAL — only what the ML service needs. No supabase, no fasthtml, no gemini.

### 2F: ML Client HTTP Wrapper (`core/ml_client.py`)

This is the interface the web app will use (Session 116 wiring):

```python
"""HTTP client for the Rhodesli ML Service.

Usage (Session 116):
    from core.ml_client import MLServiceClient
    client = MLServiceClient(base_url=os.getenv("ML_SERVICE_URL"))
    result = await client.detect_and_embed(image_path)
"""

class MLServiceClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    async def health(self) -> dict:
        """Check ML service health."""

    async def detect_and_embed(self, image_path: str) -> dict:
        """Send image to ML service, get faces + embeddings back."""

    async def is_available(self) -> bool:
        """Check if ML service is reachable. Used for fallback logic."""
```

This is a STUB for now — the actual HTTP calls will be wired in Session 116.

### 2G: Tests

Create `ml_service/tests/`:

```python
# test_health.py
# - Test health endpoint returns expected fields
# - Test version matches
# - Test models_loaded field reflects actual state

# test_detect.py (with mocked InsightFace)
# - Test detect endpoint accepts image upload
# - Test detect endpoint returns correct response shape
# - Test detect endpoint includes model_info
# - Test detect endpoint returns 401 without token
# - Test detect endpoint returns 400 for non-image file

# test_ml_client.py (in tests/ not ml_service/tests/)
# - Test MLServiceClient.health() calls correct URL
# - Test MLServiceClient.detect_and_embed() sends multipart
# - Test MLServiceClient.is_available() handles connection errors
```

Run ML service tests: `pytest ml_service/tests/ -v`
Run app tests: `make test-fast` (must not regress)

**Commit:** `feat(ml-service): session 115 phase 2 — ML service skeleton with detect endpoint`
**/clear**

---

## Phase 3: ML Run Provenance + Schema Migration (25 min)

### 3A: Schema Migration

Create `scripts/migrations/alter_ml_runs_add_provenance.sql`:

```sql
-- Session 115: ML Run Provenance Columns
-- Additive-only — no breaking changes to existing rows

-- What environment executed this run
ALTER TABLE ml_runs ADD COLUMN IF NOT EXISTS
  execution_environment TEXT DEFAULT 'local_laptop';
-- Values: 'local_laptop', 'railway_web', 'railway_ml_service', 'ci', 'test'

-- What ML models and versions were used
ALTER TABLE ml_runs ADD COLUMN IF NOT EXISTS
  model_versions JSONB DEFAULT '{}';
-- Example: {"insightface": "0.7.3", "buffalo": "buffalo_l", "calibration": "isotonic_v3"}

-- Scope: which community was this run for (NULL = all communities)
ALTER TABLE ml_runs ADD COLUMN IF NOT EXISTS
  community_id UUID;
-- FK to communities table. NULL means cross-community or global run.

-- Fine-grained scope filter for subset runs
ALTER TABLE ml_runs ADD COLUMN IF NOT EXISTS
  scope_filter JSONB DEFAULT NULL;
-- Examples:
--   {"photo_ids": ["abc123", "def456"]}        — run on specific photos
--   {"identity_ids": ["uuid1", "uuid2"]}        — run on specific identities
--   {"batch_id": "upload-2026-03-18"}           — run on specific upload batch
--   {"exclude_confirmed": true}                  — skip already-confirmed
-- NULL means "entire population for the given community_id"
```

### 3B: Run Migration

Execute the migration against Supabase:
```bash
# Read .env for Supabase credentials
source .env
# Run via psql or Supabase SQL editor
```

If direct psql is not available, use the Supabase management API or add the migration to the app startup sequence.

### 3C: Update ML Run Writers

Find all places that write to `ml_runs` and add the new columns:

```bash
grep -rn "ml_runs" app/ core/ scripts/ --include="*.py"
```

For each writer:
1. Add `execution_environment` — detect from env var `EXECUTION_ENVIRONMENT` (default: 'local_laptop')
2. Add `model_versions` — capture actual versions at runtime
3. Add `community_id` — pass through from caller (if community-scoped)
4. Add `scope_filter` — pass through from caller (if subset run)

Create a helper function to standardize this:

```python
# In core/ml_run_logger.py (NEW)
def log_ml_run(
    supabase_client,
    pipeline_type: str,
    config: dict,
    triggered_by: str = "manual",
    community_id: str | None = None,
    scope_filter: dict | None = None,
    parent_run_id: str | None = None,
) -> str:
    """Create an ml_runs record with full provenance. Returns run_id."""
    import os
    run_data = {
        "pipeline_type": pipeline_type,
        "config_json": config,
        "triggered_by": triggered_by,
        "execution_environment": os.getenv("EXECUTION_ENVIRONMENT", "local_laptop"),
        "model_versions": _get_model_versions(),
        "community_id": community_id,
        "scope_filter": scope_filter,
        "parent_run_id": parent_run_id,
        "status": "running",
    }
    result = supabase_client.table("ml_runs").insert(run_data).execute()
    return result.data[0]["run_id"]

def complete_ml_run(supabase_client, run_id: str, result_summary: dict, duration_ms: int):
    """Mark an ml_run as completed with results."""
    supabase_client.table("ml_runs").update({
        "status": "completed",
        "result_summary": result_summary,
        "duration_ms": duration_ms,
    }).eq("run_id", run_id).execute()

def _get_model_versions() -> dict:
    """Detect installed model versions at runtime."""
    versions = {}
    try:
        import insightface
        versions["insightface"] = insightface.__version__
    except ImportError:
        pass
    # Add more as needed
    return versions
```

### 3D: Scale Considerations

Document in the session log how this schema scales:
- **Dozens of communities**: Each run targets one community via `community_id`. Global runs (calibration, cross-community matching) use `community_id=NULL`.
- **Hundreds of communities**: `scope_filter` enables targeting subsets without per-community overhead. A single "re-cluster all Fox Family photos from March" run uses `scope_filter={"batch_id": "fox-march-2026"}`.
- **Environment comparison**: Query `SELECT * FROM ml_runs WHERE pipeline_type='clustering' ORDER BY created_at` and compare `result_summary` across `execution_environment` values to validate cloud vs local parity.
- **No over-engineering**: We're adding 4 nullable columns with sensible defaults. Existing code continues to work unchanged. New code passes the extra context.

### 3E: Tests

```python
# tests/test_ml_run_logger.py
# - Test log_ml_run creates record with all fields
# - Test execution_environment defaults to 'local_laptop'
# - Test model_versions captures insightface version
# - Test community_id is nullable (global runs)
# - Test scope_filter is nullable (full-population runs)
# - Test complete_ml_run updates status and result_summary
# - Test _get_model_versions() handles missing packages gracefully
```

Run: `make test-fast` — must pass with 0 failures.

**Commit:** `feat(ml): session 115 phase 3 — ml_runs provenance schema + run logger (AD-227)`
**/clear**

---

## Phase 4: AD + Documentation Updates (15 min)

### 4A: AD-227 — ML Run Provenance Tracking

Add to `docs/ml/ALGORITHMIC_DECISIONS.md`:

```
### AD-227: ML Run Provenance — Environment + Scope Tracking (2026-03-18)

**Context:** Moving ML pipeline from local laptop to cloud service (TOOLS-002).
Need to track which environment executed each run and compare outputs.
Also need community-scoped runs as we scale to dozens of communities.

**Decision:** Add 4 columns to ml_runs: execution_environment (TEXT),
model_versions (JSONB), community_id (UUID), scope_filter (JSONB).
All nullable with sensible defaults. Existing code unchanged.

**Rationale:** Environment tracking enables quality comparison during migration.
Community scoping enables per-archive ML runs without processing the full population.
scope_filter enables fine-grained targeting (batch, photo set, identity set).
All additive — no breaking changes.

**Gap/Risk:** community_id FK to communities table not enforced at DB level (no
foreign key constraint) to avoid blocking runs when communities table is unavailable.
Application-level validation only.
```

### 4B: Update ROADMAP.md

- Add Session 115 to "Recently Completed" or "In Progress"
- Check off COMMUNITY-017 (or update status to "HARDENED, remaining: upload form selector")
- Update TOOLS-002 status: "Phase 1 (Extract) complete"

### 4C: Update BACKLOG.md

- COMMUNITY-017: Update status — audit complete, tests added, remaining: upload form dropdown (WORKSPACE-001)
- TOOLS-002: Update — Phase 1 skeleton shipped

### 4D: Update CHANGELOG.md

Add v0.99.24 entry with community routing hardening + ML service skeleton.

**Commit:** `docs: session 115 phase 4 — AD-227, ROADMAP, BACKLOG, CHANGELOG updates`
**/clear**

---

## Phase 5: Deploy + Production Verification (15 min)

### 5A: Final Test Gate

```bash
source venv/bin/activate
pytest tests/ -x -q         # App tests — must pass
pytest rhodesli_ml/tests/ -x -q  # ML tests — must pass
pytest ml_service/tests/ -x -q   # ML service tests — must pass
```

All three suites must pass with ZERO failures.

### 5B: Deploy

```bash
git push origin main
```

Wait for Railway deploy. Verify with `mcp__railway-mcp-server__list-deployments`.
Note: ML service is NOT deployed yet (Session 116). Only the web app deploys.

### 5C: Production Verification (READ-ONLY)

Using browser automation (screenshots only, NO clicks):
1. **Health**: `/api/health` returns 200
2. **Root landing**: `rhodesli.nolanandrewfox.com/` shows neutral platform page (not Rhodes default)
3. **Rhodes landing**: `/c/rhodes/` shows Rhodes community page
4. **Fox Family landing**: `/c/fox-family/` shows Fox Family community page
5. **People page**: identity list renders
6. **Person detail**: confirmed identity loads with face crops
7. **Tools**: `/tools/estimate` loads (community-agnostic)

Log each check as PASS/FAIL in session log.

### 5D: Verify ML Schema Migration

If Supabase migration was run:
```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'ml_runs'
ORDER BY ordinal_position;
```
Verify: execution_environment, model_versions, community_id, scope_filter all present.

**Commit:** `docs: session 115 deploy verification`
**/clear**

---

## Phase 6: Harness Outputs (15 min)

### 6A: Assessment

Write `docs/assessments/session-115-assessment.md`:
- What shipped (with evidence per phase)
- What was deferred (with reason and BACKLOG entry)
- Red flags (with severity)
- What Session 116 should verify first

### 6B: Documentation Updates

1. **SESSION_HISTORY.md**: Add Session 115 entry
2. **SESSION_LOG.md**: Archive to `docs/session_logs/session-115-log.md`
3. **ALGORITHMIC_DECISIONS.md**: Verify AD-227 is present
4. **tasks/todo.md**: Update TOOLS-002 and COMMUNITY-017 status

### 6C: Session 116 Prep

Write a brief note in the session log about Session 116 scope:
- Deploy ML service to Railway as internal service
- Wire web app to call ML service (ML_SERVICE_URL env var)
- Fallback: if ML service unavailable, use local InsightFace
- Community-scoped clustering via ml_runs.community_id

**Commit:** `docs: session 115 harness outputs — assessment, changelog, roadmap`

---

## Verification Gate

Before declaring done, re-read this prompt and verify:

| Check | Method | Expected |
|-------|--------|----------|
| All POST routes audited? | Session log has full audit table | Every route classified |
| Upload path is safe? | `grep "is_community_explicit" app/upload_routes.py` | Guard present |
| Community routing tests pass? | `pytest tests/test_community_routing_safety.py -v` | All pass |
| Existing community tests pass? | `pytest tests/test_community_prefix_audit.py -v` | All pass |
| ML service skeleton exists? | `ls ml_service/main.py ml_service/detect.py` | Both exist |
| ML service Dockerfile exists? | `ls ml_service/Dockerfile` | Exists |
| ML client stub exists? | `ls core/ml_client.py` | Exists |
| ML service tests pass? | `pytest ml_service/tests/ -v` | All pass |
| ml_runs schema migrated? | Check Supabase for new columns | 4 new columns present |
| ML run logger exists? | `ls core/ml_run_logger.py` | Exists |
| AD-227 documented? | `grep "AD-227" docs/ml/ALGORITHMIC_DECISIONS.md` | Found |
| All test suites pass? | `make test-fast && make test-ml` | PASS |
| Deploy successful? | Railway deploy status | DOCKERFILE builder |
| Assessment file exists? | `ls docs/assessments/session-115-assessment.md` | Exists |
| CHANGELOG updated? | `grep "v0.99.24" CHANGELOG.md` | Found |
| ROADMAP updated? | `grep "Session 115" ROADMAP.md` | Found |
| `git log origin/main..HEAD` empty? | git log | Empty (all pushed) |

## Parallelization Plan

**Track A** (Phase 1 — Community Routing) and **Track B** (Phase 2 — ML Service) touch completely different files and CAN run in parallel worktrees.

| Track | Files Touched | Dependencies |
|-------|--------------|--------------|
| A: Community Routing | `app/upload_routes.py`, `app/engagement_routes.py`, `tests/test_community_routing_safety.py` | None |
| B: ML Service | `ml_service/` (NEW), `core/ml_client.py` (NEW) | None |

**Merge order**: Track A first (safety-critical), then Track B (new code, no conflicts).
**Recommendation**: Parallelize if context allows. But given data safety priority, Phase 1 should be done carefully with full audit before moving on. Sequential execution is acceptable.
