# Session 142 Assessment

## Shipped

### Interactive Feedback Fixes (FB-001 through FB-012)
- [x] **FB-001** (P1): Similar Identities links → person page — FIXED (e953ba6)
- [x] **FB-002** (P1): Compare "View Photo" missing community prefix — FIXED (e953ba6)
- [x] **FB-003** (P1): Multi-merge Focus mode toast instead of redirect — FIXED (e953ba6)
- [x] **FB-004** (P0): "Confirm as [Name]" now merges with target — FIXED (efa43f5)
- [x] **FB-006** (P1): Bulk merge "already merged" shown as info — FIXED (efa43f5)
- [x] **FB-007** (P1): Similar panel filters merged identities — FIXED (efa43f5)
- [x] **FB-008** (P1): Neighbor fetch limit 20→100 — FIXED (7a32cf7)
- [x] **FB-010** (P1): Face overlay click → person page — FIXED (06b70e3)
- [x] **FB-011** (P2): "Confirm Only" button alongside "Confirm as [Name]" — FIXED (2b13269)
- [x] **FB-012** (P2): Expansion panel cleared after confirm — FIXED (4f5f1d4)

### Codex Audit Fixes
- [x] **P1 CSRF**: `/inbox/{id}/confirm` missing `_check_origin()` — FIXED
- [x] **P1 Merge Side Effects**: Confirm+merge runs `_merge_annotations()` + recalibration — FIXED
- [x] **P2 Rematch Target**: Post-confirm rematching uses surviving target ID — FIXED
- [x] **P0 Face Sort**: Face coordinates sorted left-to-right for Gemini — FIXED

### Infrastructure
- [x] **Startup retry**: 3-attempt retry with 10/20/30s backoff for Supabase identity load
- [x] **Batch Gemini logging**: Fixed schema mismatch (manifest fields → gemini_config JSONB)

### Batch Gemini Estimation
- [x] Script: `scripts/batch_gemini_for_person.py` — full preset, face coords, GEDCOM, Supabase logging
- [x] 80/279 Esther+Albert photos processed with rich metadata
- [x] Data saved to `rhodesli_ml/data/date_labels.json` (344 labels total)

### Documentation
- [x] PRD-059: Temporal Co-Occurrence Analysis
- [x] Session 140 prompt backfilled (harness gap)
- [x] 3 Codex audits: security, prompt, speed — all logged
- [x] Lessons 159-160 added
- [x] CHANGELOG, ROADMAP, BACKLOG, SESSION_HISTORY updated

## Deferred (User Approved)
- **FB-009** (P2): Speed Loop auto-suggestion — feature gap, needs proposal pipeline
- **BATCH-001** (P2): Atomic JSON writes for date_labels.json
- **BATCH-002** (P2): Write batch results to Supabase date labels
- **BATCH-003** (P1): Backfill 80 Supabase audit log entries
- **BATCH-004** (P0): GEDCOM preload optimization (load once, not per photo)
- **BATCH-005** (P1): Resume batch for remaining 199 photos after quota resets

## Red Flags
- **MEDIUM**: Supabase audit logging failed for all 80 batch Gemini calls (schema mismatch). Fixed in code, needs backfill. Data saved locally — no data loss.
- **MEDIUM**: Supabase free tier instability caused 3 failed Railway deploys. Startup retry fix prevents future occurrences. Lesson 159 added.
- **LOW**: GEDCOM context loading is O(photos × full_tree) — ~60-90s per photo. Codex speed audit P0: preload once. Batch took ~6h instead of ~30min.

## AI Tool Usage

### Codex Audit #1: Security + Code Quality
- **Tool**: Codex CLI v0.115 (o4-mini)
- **Agent type**: Independent (fresh context)
- **Task**: Audit Session 142 changed files
- **Findings**: 3 P1 (CSRF, merge side effects, label store), 2 P2 (rematch target, JSON safety)
- **Acted on**: All 3 P1s + 1 P2 fixed
- **Value assessment**: STRONG — CSRF vulnerability would not have been caught otherwise

### Codex Audit #2: Gemini Prompt Quality
- **Tool**: Codex CLI v0.115 (o4-mini)
- **Agent type**: Independent (fresh context)
- **Task**: Review extraction prompt and batch script for optimization
- **Findings**: 3 P0 (face sort, contract drift, scene overwrite), 4 P1 (capture-vs-print, GEDCOM curated, admin preset, per-face ages)
- **Acted on**: Face sort P0 fixed. Contract drift and GEDCOM curated deferred to next session.
- **Value assessment**: STRONG — identified prompt/consumer contract drift that would have produced incomplete data

### Codex Audit #3: Batch API Speed
- **Tool**: Codex CLI v0.115 (o4-mini)
- **Agent type**: Independent (fresh context)
- **Task**: Analyze GEDCOM loading bottleneck
- **Findings**: P0 (preload GEDCOM once), P1 (precompute face→identity→gedcom maps), P2 (reuse client, buffer logging)
- **Value assessment**: MODERATE — confirmed the diagnosis, provided implementation guidance

## Next Session Should Verify
1. Resume Gemini batch (199 remaining photos) with GEDCOM preload optimization
2. Backfill 80 Supabase audit log entries from date_labels.json
3. Spot-check 10 date labels for accuracy
4. Browser verify FB-001/004/010/011 fixes on production
5. Begin PRD-059 Phase 2 (event grouping)
