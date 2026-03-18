# Session 114 Context — Data Stability Completion + Harness Gaps + Performance

**Predecessor:** Session 113 (Audit Logging + Embeddings Sync)
**Assessment:** [session-113-assessment.md](../assessments/session-113-assessment.md)
**PRD:** [PRD-051: Single Source of Truth](../prds/051_single_source_of_truth.md)

## Problem Statement

Sessions 112-113 completed PRD-051 Phase 1 (Supabase-only reads for identities/photos) and AUDIT-001 Phase 1 (audit logging). But three gaps remain:

1. **PRD-051 Phases 2-4 incomplete** — proposals.json, annotations.json, relationships.json, gedcom_matches.json still have JSON read paths. The split-brain risk exists for these files until eliminated.
2. **Harness documentation gaps** — SESSION_HISTORY.md missing Sessions 66-113 (last entry: Session 65a). SESSION_LOG.md root file stale (shows Session 92). These gaps block safe ROADMAP trimming and violate Lesson 77.
3. **Test suite speed regression** — `make test-fast` target exists with pytest-xdist (`-n 4`), but actual runtime is ~47-90s. PERF-001 targets <30s. The flaky `test_my_contributions_page_accessible` test hasn't been fixed.

## Research Findings

### PRD-051 Phase 2: JSON Read Locations

| File | JSON Read Location | Supabase Table | Cache | Migration Complexity |
|------|--------------------|----------------|-------|---------------------|
| proposals.json | `app/main.py:1628` (`_load_proposals()`), `cluster_review_routes.py:75`, `identity_routes.py:210`, `engagement_routes.py:80` | `ml_proposals` (partial — writes exist, reads don't) | `_proposals_cache` | MEDIUM — multiple read sites, need TTL cache |
| annotations.json | `engagement_routes.py:510` (`_load_annotations()`) | `annotations` table (reads + writes exist) | `_annotations_cache` | LOW — already has DATA_SOURCE conditional, just remove JSON branch |
| relationships.json | `relationship_routes.py:62` (`_load_relationship_graph()`) | `relationships` table (full replace pattern) | None | LOW — single read site, add TTL cache |
| gedcom_matches.json | `page_routes.py:10158, 10310` | `gedcom_face_links` (sync exists) | None | LOW — 2 read sites in page_routes |
| photo_search_index.json | `app/main.py:1762` (`_load_search_index()`) | None — ML pipeline generated | `_search_index_cache` | DEFER — static reference data, no split-brain risk |

### PRD-051 Phase 3: ML Pipeline

ML scripts (`cluster_new_faces.py`, `ingest_inbox.py`) read from JSON. These run locally only, not on Railway. Lower priority than app read paths. Can defer to Phase 3 without split-brain risk since local scripts are the writers, not readers-of-production-state.

### PRD-051 Phase 4: Deploy Pipeline Cleanup

Once Phases 1-2 are done, `init_railway_volume.py` only needs `embeddings.npy`. Remove identities.json and photo_index.json from `REQUIRED_DATA_FILES`. Add Supabase health check to app startup.

### Harness Gaps

**SESSION_HISTORY.md**: Last detailed entry is Session 65a. The version table goes to Session 93 (v0.96.0) but has no narrative for Sessions 66-113. Backfill needed for at least Sessions 100-113 (recent, high-value context). Older sessions (66-99) can be summarized from ROADMAP "Recently Completed" entries that were already trimmed.

**SESSION_LOG.md**: Shows Session 92 only. Should be cleared and used as the active session's running log, then archived to `docs/session_logs/` at session end.

**Harness improvement needed**: The stop hook should verify SESSION_HISTORY.md was updated. Currently it only checks for assessment file + clean git.

### Performance Opportunities

1. **Test speed**: pytest-xdist already configured (`-n 4`). Investigate: is the bottleneck app import time (FastHTML startup), test isolation overhead, or actual test execution? Profile with `--durations=20`.
2. **Flaky test**: `test_my_contributions_page_accessible` fails in full suite, passes alone. Likely test ordering / shared state issue.
3. **App performance**: Session 111f shipped vectorized distance computation (perf_cache.py). Focus mode 124ms, speed-run 171ms. Further wins likely in: reducing Supabase round-trips during page loads, lazy-loading expensive computations.

### Supabase Egress Consideration

Every new Supabase read path adds egress. Current TTL caches (120s registry, 30s suggestions/clusters) keep usage manageable. New reads for proposals/annotations/relationships should use TTL caches (120s minimum) per OD-011 thresholds. Grace period until April 13.

## Scope for Session 114

### In Scope
1. Harness gap fixes (SESSION_HISTORY backfill, SESSION_LOG reset, stop hook improvement)
2. PRD-051 Phase 2: Wire proposals, annotations, relationships, gedcom_matches to Supabase reads
3. PRD-051 Phase 4: Remove JSON from deploy pipeline, add Supabase health check
4. Test speed investigation + fix (profile, fix flaky test, optimize if possible)

### Out of Scope
- PRD-051 Phase 3 (ML pipeline Supabase reads) — local-only scripts, no production split-brain risk
- CLUSTER-QUALITY-001 (Harry Fox visual review) — needs human eyes, not code
- AUDIT-001 Phase 2 (timeline UI) — UX feature, not data stability
- Supabase Pro upgrade decision — monitoring only until April 13
- New features of any kind

## Risk Mitigation

- **ZERO regressions** — run both test suites before every commit
- **TTL caches on all new Supabase reads** — egress budget protection
- **JSON writes preserved** — backup path stays, only reads change
- **Rollback plan** — if Supabase reads fail, `DATA_SOURCE=json` environment variable restores old behavior (Phase 1 already supports this)

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | `_load_proposals()`, `_load_search_index()` |
| `app/engagement_routes.py` | `_load_annotations()` |
| `app/relationship_routes.py` | `_load_relationship_graph()` |
| `app/cluster_review_routes.py` | Duplicate `_load_proposals()` |
| `app/page_routes.py` | gedcom_matches.json reads |
| `app/supabase_data.py` | All Supabase read/write functions |
| `scripts/init_railway_volume.py` | Deploy pipeline JSON requirements |
| `docs/roadmap/SESSION_HISTORY.md` | Needs backfill |
| `SESSION_LOG.md` | Needs reset |
| `.claude/hooks/stop-gate.sh` | Needs SESSION_HISTORY check |

## Breadcrumbs

- PRD-051: `docs/prds/051_single_source_of_truth.md`
- Session 112 assessment: `docs/assessments/session-112-assessment.md`
- Session 113 assessment: `docs/assessments/session-113-assessment.md`
- BACKLOG: DATA-025 (Phase 2), DATA-026 (Phase 4), PERF-001 (test speed)
- OD-011: Supabase egress budget thresholds
- Lesson 77: Never trim without verifying destination
- Lesson 145: photo_faces must be written alongside photos
