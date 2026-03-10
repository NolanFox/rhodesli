# PRD-038: Recalibration Architecture

**Parent**: [docs/prds/038_longitudinal_face_modeling.md](../038_longitudinal_face_modeling.md)
**Status**: PLANNED | **Priority**: P1 (blocks continuous improvement)
**Key question**: When, where, and how should calibration re-run as confirmations accumulate?

---

## Current State

### What Exists
- `rhodesli_ml/recalibration_hooks.py` — Hooks fire on merge/reject/confirm admin actions
- `rhodesli_ml/similarity_calibration.py` — `SimilarityCalibrator` with isotonic regression, `should_recalibrate()` and `recalibrate_if_needed()` methods
- `calibration_pairs` Supabase table — Stores labeled pairs with similarity scores
- Three trigger conditions: >20 new pairs, model >30 days old, class ratio shift >50%
- Rate limiting: max 1 recalibration/hour, drift detection at threshold shift >0.1
- Hooks wired into `app/engagement_routes.py:727-740`

### What's Broken
1. **ML deps not on Railway** (AD-007): `sklearn.isotonic.IsotonicRegression` import fails on production. The `_check_recalibration()` call silently catches the ImportError at `logging.debug` level.
2. **Embeddings path hardcoded**: `_get_embedding()` reads from `data/embeddings.npy` — correct locally, but Railway volume path differs (`/app/data/` or `STORAGE_DIR`).
3. **Silent failure**: Exception handler in `engagement_routes.py:740` uses `logging.debug` — production never sees these failures.
4. **No monitoring**: No way to know if calibration is stale, how many pairs exist, or when last recalibration occurred.
5. **No persistence of calibrated model on Railway**: Even if sklearn ran, the fitted model would need to be stored somewhere Railway can access it.

### Net Effect
Recalibration hooks fire on every admin action but silently fail. The calibration model is frozen at whatever was last trained locally. As confirmations grow, the model doesn't improve.

---

## Architecture Options

### Option A: Local-Only Recalibration (RECOMMENDED for now)
**How**: Keep all ML on local machine. Add a `make recalibrate` command that:
1. Pulls latest `calibration_pairs` from Supabase
2. Reruns isotonic regression locally
3. Exports updated model artifact
4. Pushes artifact to production via deploy

**When it runs**:
- Manually after admin confirmation sessions (e.g., "I just confirmed 30 identities, recalibrate")
- As part of a periodic "ML maintenance" workflow (weekly/monthly)
- Before any new clustering run (`cluster_new_faces.py` checks model freshness)

**Trigger events** (logged, not auto-executed):
| Event | Where | Action |
|-------|-------|--------|
| Admin confirms identity | `engagement_routes.py` | Insert pairs into `calibration_pairs` (WORKS NOW) |
| Admin merges faces | `engagement_routes.py` | Insert match pair (WORKS NOW) |
| Admin rejects match | `engagement_routes.py` | Insert non-match pair (WORKS NOW) |
| >20 new pairs accumulated | `calibration_pairs` count | Log "recalibration recommended" to Sentry |
| Model >30 days old | Model metadata | Log warning on startup |
| Pre-clustering check | `cluster_new_faces.py` | Warn if model is stale, offer `--recalibrate` flag |

**What changes**:
- Fix `recalibration_hooks.py` to ONLY insert pairs (remove `_check_recalibration` from production path)
- Upgrade `logging.debug` to `logging.warning` for visibility
- Fix embeddings path to use `core.config.STORAGE_DIR` (Lesson 114)
- Add `scripts/recalibrate.py` CLI tool
- Add model freshness check to `cluster_new_faces.py`
- Add `/api/admin/calibration-status` endpoint showing pair count, model age, drift
- Add Sentry alert when pair count exceeds recalibration threshold

**Effort**: 1 session
**Risk**: LOW — separates data collection (production) from model fitting (local)

### Option B: Railway Cron Job
**How**: Schedule a Railway cron service that runs recalibration weekly.
**Problem**: Requires sklearn on Railway (violates AD-007), or a separate ML service container.
**Effort**: 2 sessions (new service + deployment)
**When to consider**: When we have >1000 pairs and manual recalibration becomes a bottleneck.

### Option C: Supabase Edge Function
**How**: Supabase Edge Function triggered by row count in `calibration_pairs`.
**Problem**: Edge functions run Deno, not Python. Would need to rewrite calibrator in JS or call an external ML service.
**Effort**: 3+ sessions
**When to consider**: Only if we build a full ML service (TOOLS-002).

### Option D: Full ML Service (TOOLS-002 dependency)
**How**: Dedicated ML service (Railway container with torch/sklearn). Recalibration runs as an API endpoint.
**Problem**: TOOLS-002 is a 3-4 session project not yet started.
**When to consider**: When ML service extraction is complete.

---

## Recommended Implementation Plan

### Phase 1: Fix Data Collection (immediate, <1 session)
1. Fix embeddings path in `recalibration_hooks.py` to use `core.config.STORAGE_DIR`
2. Upgrade `logging.debug` → `logging.warning` in engagement_routes exception handler
3. Remove `_check_recalibration()` from production hooks (it can't work without sklearn)
4. Add pair count to `/api/admin/calibration-status` endpoint
5. Verify pairs are actually accumulating in Supabase after admin actions

### Phase 2: Local Recalibration CLI (1 session, part of ML-115)
```bash
# Pull pairs from Supabase, retrain, export
python scripts/recalibrate.py --pull-pairs --fit --export

# Check if recalibration is needed
python scripts/recalibrate.py --check

# Dry run (show what would change)
python scripts/recalibrate.py --dry-run
```

### Phase 3: Pre-Clustering Gate (part of ML-110)
```python
# In cluster_new_faces.py, before clustering:
cal = SimilarityCalibrator(model_path="rhodesli_ml/artifacts/calibration_v1.pt")
should, reason = cal.should_recalibrate()
if should:
    logger.warning(f"Calibration model is stale: {reason}")
    if not args.force:
        print(f"Run `python scripts/recalibrate.py` first, or use --force to skip")
        sys.exit(1)
```

### Phase 4: Monitoring Dashboard (future, part of admin tools)
- `/admin/ml-status` page showing:
  - Calibration pair count (match vs non-match)
  - Model version and age
  - Last recalibration date
  - Current AUC estimate
  - Drift warnings

---

## Decision: Why Option A

1. **Respects AD-007** — ML stays local, production stays lightweight
2. **Data collection already works** — Just needs path fix and visibility
3. **Lowest risk** — No new services, no new dependencies
4. **Sufficient at scale** — Even at 10K faces, recalibration is a 30-second local operation
5. **Natural workflow** — Admin does confirmations → runs recalibrate → deploys. Same pattern as clustering.
6. **Migration path** — When TOOLS-002 (ML service) ships, recalibration moves to the service with zero data model changes

---

## Breadcrumbs
- AD-149: Similarity calibration design
- AD-152: Calibration pipeline + API call logging
- ML-115: Recalibrate thresholds (BACKLOG)
- TOOLS-002: ML service extraction (future home for auto-recalibration)
- Lesson 114: STORAGE_DIR derivation only in config.py
