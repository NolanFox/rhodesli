# Session 114 — Data Stability Completion + Harness Gaps + Test Performance

@docs/session_context/session-114-context.md
@docs/prds/051_single_source_of_truth.md
@tasks/lessons.md

## Goal

Finish the Single Source of Truth migration (PRD-051 Phases 2 + 4), close harness documentation gaps from Sessions 112-113, and improve test suite performance. This session is about stability and completeness — no new features.

## CRITICAL CONSTRAINTS

1. **ZERO REGRESSIONS** — run `make test-fast` before every commit. Run both `pytest tests/ -x -q` and `pytest rhodesli_ml/tests/ -x -q` before deploy.
2. **Browser automation is READ-ONLY on production** — never click action buttons (Lesson 149).
3. **/clear between phases** — non-negotiable. Commit first, then /clear immediately. Do NOT read the next phase first.
4. **TTL cache every new Supabase read** — minimum 120s. We are on the free plan with a disk IO warning (OD-011).
5. **JSON writes stay** — only change READ paths. JSON backup writes remain for emergency recovery.
6. **Do NOT touch**: `app/perf_cache.py`, `core/neighbors.py` (frozen), `embeddings.npy` handling. These are stable.

## Pre-Requisites (do these FIRST, before Phase 0)

```bash
echo "114" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — record time and pass count
```

Read these files to orient:
- `docs/session_context/session-114-context.md`
- `docs/prds/051_single_source_of_truth.md`
- `docs/assessments/session-113-assessment.md`
- `docs/assessments/session-112-assessment.md`

---

## Phase 0: Harness Gap Closure (15 min)

### 0A: SESSION_HISTORY.md Backfill

SESSION_HISTORY.md is missing Sessions 66-113. The version table has some entries but no narrative summaries.

1. Read `docs/roadmap/SESSION_HISTORY.md` to understand the current format
2. Read `ROADMAP.md` "Recently Completed" section for Sessions 100-113 summaries
3. Backfill SESSION_HISTORY.md with one-line summaries for Sessions 100-113 in the version table format (version, date, session, test count). These sessions are well-documented in ROADMAP.md.
4. For Sessions 66-99: add a note "See ROADMAP.md Recently Completed (archived) and individual session logs in docs/session_logs/" — do NOT attempt to reconstruct 34 sessions.

### 0B: SESSION_LOG.md Reset

1. Clear SESSION_LOG.md and set it up as the Session 114 running log
2. Include: session number, date, predecessor link, phase checklist

### 0C: Stop Hook Improvement

The stop hook (`.claude/hooks/stop-gate.sh`) currently checks for assessment file + clean git. It does NOT check that SESSION_HISTORY.md was updated. Add a check:

1. Read the current stop-gate.sh
2. Add a check: grep for the current session number in `docs/roadmap/SESSION_HISTORY.md`. If missing, warn (exit 0 with message, not exit 2 — the backfill can happen in the harness phase).
3. Test the hook manually: `bash .claude/hooks/stop-gate.sh`

**Commit:** `docs: session 114 phase 0 — harness gap closure (SESSION_HISTORY backfill, stop hook improvement)`
**/clear**

---

## Phase 1: PRD-051 Phase 2A — Proposals to Supabase Reads (25 min)

proposals.json is the most complex migration because it has multiple read sites.

### 1A: Audit Current Read Paths

Grep for all `proposals.json` and `_load_proposals` references in `app/`. Document every read site. The context file lists these but verify against current code:
- `app/main.py:1628` — `_load_proposals()`
- `app/cluster_review_routes.py:75` — duplicate `_load_proposals()`
- `app/identity_routes.py:210` — reads during confirm
- `app/engagement_routes.py:80` — discovery suggestions
- `app/sync_routes.py` — health check reads

### 1B: Create Unified Proposals Reader

1. In `app/main.py`, modify `_load_proposals()` to read from `ml_proposals` Supabase table when `DATA_SOURCE=postgres`
2. Add a TTL cache (120s) — proposals don't change during normal browsing, only during clustering
3. Add cache invalidation in recluster and upload pipeline paths
4. Remove the duplicate `_load_proposals()` in `cluster_review_routes.py` — import from main instead
5. Keep JSON write-through in clustering paths (backup only)

### 1C: Wire All Read Sites

Verify every read site now goes through the unified reader. The key transformation:
- Old: `json.load(open(data_path / "proposals.json"))`
- New: `_load_proposals()` → Supabase with TTL cache → fallback to JSON only if DATA_SOURCE=json

### 1D: Tests

Write tests that verify:
- `_load_proposals()` reads from Supabase when DATA_SOURCE=postgres
- TTL cache works (second call within 120s doesn't hit Supabase)
- Cache invalidation works (after recluster, cache is cleared)
- Fallback to JSON works when DATA_SOURCE=json
- All downstream consumers (cluster review, identity confirm, engagement) get proposals

### 1E: Second-Order Effects

- **Egress**: proposals table is ~211KB. At 120s TTL with 1 admin, that's ~150MB/month. Acceptable.
- **Staleness**: 120s TTL means newly generated proposals take up to 2 minutes to appear. Acceptable for admin workflow.
- **Cluster review page**: Must work with Supabase-sourced proposals. Verify the data shape matches what the UI expects.

**Commit:** `feat(data): PRD-051 phase 2A — proposals read from Supabase (session 114)`
**/clear**

---

## Phase 2: PRD-051 Phase 2B — Annotations + Relationships + GEDCOM Matches (20 min)

These three are simpler migrations because each has fewer read sites.

### 2A: Annotations

`_load_annotations()` in `engagement_routes.py:510` already has a DATA_SOURCE conditional. The work:
1. Verify the Supabase read path actually works (it may have bugs — test it)
2. Remove the JSON fallback branch (keep JSON write-through)
3. Add TTL cache if not present (120s)
4. Test: annotations load from Supabase, cache works, write-through preserved

### 2B: Relationships

`_load_relationship_graph()` in `relationship_routes.py:62` reads JSON only.
1. Add Supabase read path using existing `supabase_data.py` relationship reader
2. Add TTL cache (300s — relationships change rarely, only on GEDCOM re-import)
3. Remove JSON read, keep JSON write-through
4. Test: relationships load from Supabase, family tree page still renders

### 2C: GEDCOM Matches

`page_routes.py:10158` and `page_routes.py:10310` read gedcom_matches.json for xref resolution.
1. Add Supabase read from `gedcom_face_links` table (or equivalent)
2. Add TTL cache (300s — GEDCOM links change only during manual linking)
3. Remove JSON read, keep JSON write-through
4. Test: GEDCOM person pages still resolve xrefs

### 2D: photo_search_index.json — SKIP

This is ML pipeline output (static reference data generated by `export_search_metadata.py`). No split-brain risk. Leave as-is per PRD-051 scope.

### 2E: Tests for All Three

Write tests covering:
- Each reader returns correct data from Supabase
- TTL caches work for each
- JSON fallback works when DATA_SOURCE=json
- No regressions in downstream consumers (family tree, GEDCOM pages, engagement)

**Commit:** `feat(data): PRD-051 phase 2B — annotations, relationships, gedcom_matches read from Supabase (session 114)`
**/clear**

---

## Phase 3: PRD-051 Phase 4 — Deploy Pipeline Cleanup + Stale Row Reconciliation (25 min)

With Phases 1-2 done, production no longer reads any JSON files except embeddings.npy and static reference data. Clean up the deploy pipeline and reconcile stale Supabase rows.

### 3A: init_railway_volume.py

1. Read `scripts/init_railway_volume.py` to understand REQUIRED_DATA_FILES and OPTIONAL_SYNC_FILES
2. Remove `identities.json` and `photo_index.json` from REQUIRED_DATA_FILES — these are now backup-only
3. Remove `proposals.json`, `annotations.json`, `relationships.json`, `gedcom_matches.json` from any sync lists
4. Keep `embeddings.npy` as REQUIRED (still disk-only)
5. Keep `surname_variants.json`, `rhodes_context_events.json` (static reference, no Supabase table)
6. Add a startup health check: on app boot, verify Supabase connection with a lightweight query (e.g., `SELECT 1`). Log warning if it fails but don't crash — JSON backup exists.

### 3B: push_to_production.py

1. Read `scripts/push_to_production.py` to understand what it pushes
2. Remove JSON data files from push list (identities, photos, proposals)
3. Keep embeddings.npy and crops in push list
4. Keep the script for embeddings + R2 uploads — it's still needed

### 3C: Dockerfile

1. Verify Dockerfile doesn't COPY JSON data files that are no longer needed at runtime
2. Keep embeddings.npy COPY
3. Keep static reference files

### 3D: DATA-009 — Stale Row Reconciliation

Now that Supabase is the single read source, stale rows from old shadow syncs are no longer hidden — they're actively served. This is the right moment to clean them up.

1. Read `app/supabase_data.py` to understand the current sync patterns (additive-only, no pruning)
2. Write a reconciliation script `scripts/reconcile_supabase.py` with two modes:
   - `--dry-run`: Compare Supabase row counts against canonical sources. Report stale rows (identities with no matching face data, photos with no face_to_photo entry, orphaned photo_faces rows, proposals for non-existent identities). Output a JSON diff artifact before any changes.
   - `--execute`: After dry-run review, prune stale rows with logged deletions
3. The script must:
   - Always produce a machine-readable diff artifact (`data/reconciliation_YYYY-MM-DD.json`) BEFORE any deletes (Lesson 124)
   - Log every deletion to `audit_log` table with action="reconcile_prune"
   - Never delete rows that have `provenance="human"` — only system-generated stale data
   - Support `--table` flag to target specific tables (identities, photos, photo_faces, ml_proposals)
4. Run `--dry-run` and log the output in the session log. Do NOT run `--execute` in this session — the dry-run report is the deliverable. Nolan will review before any actual pruning.

### 3E: Tests

- Test that `init_railway_volume.py` only requires embeddings.npy
- Test startup health check logs warning on Supabase failure
- Verify deploy safety tests (`TestDockerfileModuleCoverage`) still pass
- Test reconciliation dry-run produces correct diff artifact format
- Test that `--execute` without prior `--dry-run` is blocked (safety gate)

**Commit:** `feat(deploy): PRD-051 phase 4 — deploy cleanup + DATA-009 reconciliation script (session 114)`
**/clear**

---

## Phase 4: Test Performance (20 min)

### 4A: Profile

```bash
source venv/bin/activate
pytest tests/ -x -q --durations=50 2>&1 | tail -60
```

Identify the 20 slowest tests. Categorize:
- App import overhead (one-time cost, shared across workers)
- Supabase mock setup (per-test cost)
- Actual test logic (e.g., heavy computation, file I/O)

### 4B: Fix Flaky Test

`test_my_contributions_page_accessible` fails in full suite, passes alone. This is a test ordering issue:
1. Find the test and read it
2. Identify shared state it depends on (likely a mock that another test modifies)
3. Fix the isolation issue (probably needs its own mock setup, not relying on global state)
4. Verify it passes in both isolated and full-suite runs

### 4C: Optimize Slow Tests

Based on profiling results:
- If app import is the bottleneck: consider `conftest.py` fixture that imports once and shares
- If mock setup is expensive: consider session-scoped fixtures for common mocks
- If specific tests are slow (>2s each): investigate and optimize or mark as `@pytest.mark.slow`
- Do NOT change test behavior — only execution speed

### 4D: Verify

```bash
time make test-fast   # Target: <30s
time make test-full   # Record baseline
make test-ml          # Must still pass
```

Record before/after times in session log.

**Commit:** `perf(tests): fix flaky test + optimize slow tests (session 114)`
**/clear**

---

## Phase 5: Deploy + Production Verification (10 min)

### 5A: Final Test Gate

```bash
source venv/bin/activate
pytest tests/ -x -q
pytest rhodesli_ml/tests/ -x -q
```

Both must pass with ZERO failures.

### 5B: Deploy

```bash
git push origin main
```

Wait for Railway deploy. Verify with `mcp__railway-mcp-server__list-deployments` — builder must be DOCKERFILE.

### 5C: Production Verification (READ-ONLY)

Using browser automation (screenshots only, NO clicks):
1. **Health endpoint**: `/api/health` returns 200 with expected counts
2. **Home page**: Photos load, sidebar counts correct
3. **People page**: Identity list renders
4. **Person detail**: Pick a confirmed identity, verify face crops load
5. **Proposals page**: Verify proposals render (now from Supabase)
6. **Family tree**: Verify relationships render (now from Supabase)

Log each check as PASS/FAIL in session log.

**Commit:** `docs: session 114 deploy verification`
**/clear**

---

## Phase 6: Harness Outputs (10 min)

### 6A: Assessment

Write `docs/assessments/session-114-assessment.md`:
- What shipped (with evidence per phase)
- What was deferred (with reason and BACKLOG entry)
- Red flags (with severity)
- What Session 115 should verify first

### 6B: Documentation Updates

1. **CHANGELOG.md**: Add v0.99.23 entry
2. **ROADMAP.md**: Check off DATA-025 (Phase 2), DATA-026 (Phase 4), PERF-001 (if <30s achieved). Add to "Recently Completed"
3. **BACKLOG.md**: Update DATA-009, DATA-025, DATA-026, PERF-001 status
4. **SESSION_HISTORY.md**: Add Session 114 entry (the stop hook should remind you)
5. **SESSION_LOG.md**: Archive to `docs/session_logs/session-114-log.md`
6. **PRD-051**: Update status — Phase 1 DONE (Session 112), Phase 2 DONE (Session 114), Phase 4 DONE (Session 114). Phase 3 DEFERRED (ML pipeline, local-only, no prod split-brain risk).

### 6C: Update PRD-051 Status

Mark PRD-051 as MOSTLY COMPLETE:
- Phase 1: DONE (Session 112)
- Phase 2: DONE (Session 114)
- Phase 3: DEFERRED (ML scripts only, no production risk)
- Phase 4: DONE (Session 114)

**Commit:** `docs: session 114 harness outputs — assessment, changelog, roadmap`

---

## Verification Gate

Before declaring done, re-read this prompt and verify:

| Check | Method | Expected |
|-------|--------|----------|
| SESSION_HISTORY.md backfilled? | `grep "114" docs/roadmap/SESSION_HISTORY.md` | Found |
| Stop hook improved? | `grep "SESSION_HISTORY" .claude/hooks/stop-gate.sh` | Found |
| proposals.json reads eliminated? | `grep -r "proposals.json" app/ --include="*.py"` | Only in write paths |
| annotations.json reads eliminated? | `grep -r "annotations.json" app/ --include="*.py"` | Only in write/fallback paths |
| relationships.json reads eliminated? | `grep -r "relationships.json" app/ --include="*.py"` | Only in write paths |
| gedcom_matches.json reads eliminated? | `grep -r "gedcom_matches.json" app/ --include="*.py"` | Only in write/fallback paths |
| TTL caches on new Supabase reads? | grep for cache decorators/TTL | Present on proposals, annotations, relationships, gedcom |
| init_railway_volume.py cleaned? | `grep "identities.json" scripts/init_railway_volume.py` | NOT in REQUIRED_DATA_FILES |
| Supabase health check exists? | grep for startup health check | Present |
| Reconciliation script exists? | `ls scripts/reconcile_supabase.py` | Exists |
| Dry-run produces diff artifact? | `python scripts/reconcile_supabase.py --dry-run` | JSON artifact written |
| Flaky test fixed? | `pytest tests/test_my_contributions_page_accessible -x -q` | PASS |
| Test speed improved? | `time make test-fast` | <30s or documented reason |
| Both test suites pass? | `make test-fast && make test-ml` | PASS |
| Deploy successful? | Railway deploy status | DOCKERFILE builder, healthy |
| Assessment file exists? | `ls docs/assessments/session-114-assessment.md` | Exists |
| CHANGELOG updated? | `grep "v0.99.23" CHANGELOG.md` | Found |
| ROADMAP updated? | `grep "Session 114" ROADMAP.md` | Found |

## Parallelization Plan

Phases 1 and 2 touch different files and can potentially run in parallel worktrees:
- **Track A**: Phase 1 (proposals — touches main.py, cluster_review_routes, identity_routes, engagement_routes)
- **Track B**: Phase 2 (annotations/relationships/gedcom — touches engagement_routes, relationship_routes, page_routes)

**CAUTION**: Both tracks touch `engagement_routes.py`. If parallelizing, Track B must NOT modify the annotations reader in engagement_routes until Track A is merged. Sequential execution is safer for this session.

**Recommendation**: Execute sequentially. The total time is ~90 min. Parallelization saves ~20 min but adds merge risk. Not worth it for a stability session.
