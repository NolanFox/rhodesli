# Tech Debt Audit

**Last updated:** 2026-03-07
**Session:** 92, Track H

---

## 1. App Layer (`app/`)

### Route File Sizes

| File | Lines | Status |
|------|-------|--------|
| page_routes.py | 10,821 | OVER BUDGET -- largest file in codebase |
| main.py | 9,413 | Reduced from 26,100 (Session 91b) but still large |
| compare_routes.py | 5,553 | Acceptable for feature complexity |
| admin_routes.py | 3,262 | Acceptable |
| identity_routes.py | 3,252 | Acceptable |
| match_facecompare_routes.py | 1,750 | OK |
| person_routes.py | 1,641 | OK |
| browse_routes.py | 1,522 | OK |
| estimate_routes.py | 1,365 | OK |
| discoveries_routes.py | 1,146 | OK |
| engagement_routes.py | 1,132 | OK |
| event_routes.py | 976 | OK |
| upload_routes.py | 939 | OK |
| relationship_routes.py | 921 | OK |
| photo_routes.py | 808 | OK |
| supabase_data.py | 728 | OK |
| Others | <700 each | OK |

**Total app layer: ~47,000 lines across 24 files.**

### main.py Remaining Extractions

`main.py` at 9,413 lines still contains:
- Global state management (`_identities`, `_photo_index`, caches)
- Utility functions (`_check_admin`, `_check_login`, helpers)
- PostHog integration
- Leaflet map auto-init script
- HTMX event handlers and global JS
- Landing page route and layout (`_base_page`)
- Several API endpoints that could move to dedicated route files

**Recommended extractions (priority order):**
1. `_base_page()` + layout helpers --> `app/layout.py` (~500 lines)
2. Global JS/CSS (Leaflet init, HTMX handlers) --> `app/static/js/` files
3. API utility endpoints --> `app/api_routes.py`

### page_routes.py is the New Monolith

At 10,821 lines, `page_routes.py` has become what `main.py` was before
Session 91b. It contains the tree visualization (D3), map page (Leaflet),
timeline, social graph, and numerous page-level routes.

**Recommended split:**
1. Tree/graph visualization --> `app/tree_routes.py` (~2,000 lines)
2. Map + location pages --> `app/map_routes.py` (~1,000 lines)
3. Timeline page --> `app/timeline_routes.py` (~500 lines)

---

## 2. ML Layer (`rhodesli_ml/`)

### Module Inventory

| Directory | Files | Purpose | Status |
|-----------|-------|---------|--------|
| calibration/ | 7 | Similarity calibration + ONNX export | ACTIVE |
| config/ | 1 | MLflow config | ACTIVE (env-gated) |
| data/ | 4 | Dataset loaders, augmentations | ACTIVE |
| date_inference/ | 2 | Photo date estimation | ACTIVE |
| evaluation/ | 3 | Embedding health, regression gate | ACTIVE |
| graph/ | 3 | Co-occurrence, relationship, social | ACTIVE |
| importers/ | 4 | GEDCOM parsing, matching | ACTIVE |
| models/ | 3 | Date classifier, similarity, registry | ACTIVE |
| pipelines/ | 1 | Birth year estimation | ACTIVE |
| scripts/ | 15 | Various CLI tools | MIXED |
| training/ | 2 | Calibrator + date model training | ACTIVE |
| utils/ | 1 | API logger | ACTIVE |
| root | 4 | gedcom_context, gemini, tracking | ACTIVE |

### Potential Dead Code

| File | Concern |
|------|---------|
| `scripts/session_80_synthesize.py` | Session-specific, not reusable |
| `scripts/compare_models.py` | Duplicated in `scripts/` (top-level) |
| `scripts/evaluate_calibrator.py` | One-time evaluation, results captured in AD |
| `analysis/kinship_calibration.py` | Research spike, not used in production |
| `analysis/validate_birth_years.py` | Research spike, not used in production |
| `calibration/export_onnx.py` | ONNX export path not deployed |
| `calibration/inference_onnx.py` | ONNX inference not deployed |
| `date_inference/inference_onnx.py` | ONNX date inference not deployed |

The ONNX modules (3 files) are forward-looking for ML service extraction.
Keep them but mark as "not yet deployed."

---

## 3. Scripts (`scripts/`)

### Obsolete After Supabase Migration

| Script | Reason | Action |
|--------|--------|--------|
| `migrate_to_supabase.py` | One-time migration, completed Session 59C | DELETE |
| `migrate_photo_metadata.py` | One-time migration | DELETE |
| `migrate_photo_sources.py` | One-time migration | DELETE |
| `migrate_alignments_to_supabase.py` | One-time, completed Session 64 | DELETE |
| `backfill_supabase.py` | One-time backfill | DELETE |
| `backfill_upload_dates.py` | One-time, completed Session 90b | DELETE |
| `backfill_dimensions.py` | One-time, completed | DELETE |
| `backfill_merge_history.py` | One-time backfill | DELETE |
| `session_80_synthesize.py` | Session-specific | DELETE |
| `fix_absolute_paths.py` | One-time fix | DELETE |
| `fix_collection_metadata.py` | One-time fix | DELETE |
| `fix_matilda_gedcom_link.py` | One-time fix | DELETE |

### Keep but Consolidate

| Script | Note |
|--------|------|
| `check_data_integrity.py` | Merge with `verify_data_integrity.py` |
| `data_integrity_report.py` | Merge with above |
| `push_to_production.py` | Keep -- critical deploy path |
| `init_railway_volume.py` | Keep -- critical deploy path |
| `upload_to_r2.py` | Keep -- photo upload path |
| `production_smoke_test.py` | Keep -- verification |
| `sync_from_production.py` | Keep -- dev workflow |
| `download_staged.py` | Keep -- upload pipeline |

**12 scripts recommended for deletion, 3 for consolidation.**

---

## 4. Data Files (`data/`)

### File Status

| File | Size | Status | Notes |
|------|------|--------|-------|
| `identities.json` | Primary | DUAL-WRITE | JSON + Supabase shadow |
| `photo_index.json` | Primary | DUAL-WRITE | JSON + Supabase shadow |
| `embeddings.npy` | ~2.3 MB | JSON-ONLY | No Supabase equivalent yet |
| `annotations.json` | User data | SUPABASE | Production writes go to Supabase |
| `relationships.json` | ML output | DEPRECATED | Replaced by Supabase gedcom_rels |
| `gedcom_matches.json` | ML output | DEPRECATED | In Supabase gedcom_matches table |
| `proposals.json` | ML output | CACHE-ONLY | Generated by clustering pipeline |
| `co_occurrence_graph.json` | ML output | CACHE-ONLY | Generated, not source of truth |
| `date_labels.json` | ML output | CACHE-ONLY | Generated by Gemini pipeline |
| `photo_locations.json` | ML output | CACHE-ONLY | Generated by Gemini pipeline |
| `golden_set.json` | ML eval | STATIC | Ground truth for calibration |
| `file_hashes.json` | Dedup | JSON-ONLY | Could move to Supabase |
| `surname_variants.json` | Reference | STATIC | Manually curated |
| `rhodes_context_events.json` | Reference | STATIC | Historical events for Gemini |
| `location_dictionary.json` | Reference | STATIC | Location aliases |
| `photo_search_index.json` | Search | CACHE-ONLY | Generated index |
| `birth_year_estimates.json` | ML output | CACHE-ONLY | Generated estimates |
| `ancestry_links.json` | Reference | STATIC | Manual ancestry.com links |
| `gedcom_match_review.csv` | Admin | DEPRECATED | Replaced by in-app review |

### Migration Priority

**Phase 1 (DATA_SOURCE=postgres flip):**
- `identities.json` --> Already dual-writing, flip to Postgres primary
- `photo_index.json` --> Already dual-writing, flip to Postgres primary

**Phase 2 (Post-flip cleanup):**
- `relationships.json` --> DELETE (Supabase has data)
- `gedcom_matches.json` --> DELETE (Supabase has data)
- `gedcom_match_review.csv` --> DELETE (in-app review)

**Phase 3 (pgvector, see PGVECTOR_EVALUATION.md):**
- `embeddings.npy` --> Migrate to face_embeddings table

**Keep as-is (static reference data):**
- `golden_set.json`, `surname_variants.json`, `rhodes_context_events.json`,
  `location_dictionary.json`, `ancestry_links.json`

---

## 5. Prioritized Cleanup Plan

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| P1 | Delete 12 obsolete scripts | 1 hour | Reduce confusion |
| P1 | Delete 3 deprecated data files | 30 min | Reduce deploy size |
| P2 | Split page_routes.py (10.8K lines) | 1 track | Enable parallel work |
| P2 | Consolidate 3 data integrity scripts | 1 hour | Single entry point |
| P3 | Extract layout.py from main.py | 1 track | Cleaner separation |
| P3 | Move inline JS to static files | 1 track | Cacheable, testable |
| P4 | Flip DATA_SOURCE=postgres | 1 session | Remove JSON dependency |
| P4 | Remove ONNX dead code (or deploy it) | 1 hour | Clarity |

---

## Related Documents

- `docs/architecture/PGVECTOR_EVALUATION.md` -- Embedding migration analysis
- `docs/architecture/OVERVIEW.md` -- Architecture overview (needs update)
- `ROADMAP.md` Phase F -- Scale & Generalize remaining work
- `.claude/rules/data-layer.md` -- Data layer rules
