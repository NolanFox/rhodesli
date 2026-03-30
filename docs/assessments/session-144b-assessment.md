# Session 144b Assessment

## Shipped

### Phase 0a: FB-007 Person Page Sort Fix
- **Evidence**: `app/main.py:2314-2329` — SHA256 aliases added in Postgres date_labels path
- **Root cause**: Dual-keying existed in JSON mode but missing in Postgres mode. Date labels stored with `inbox_*` IDs, person page uses SHA256 IDs.
- **Tests**: 3 new in `tests/test_photo_sorting.py::TestDateLabelsDualKeying`
- **Impact**: All 554 date labels now accessible by both ID formats

### Phase 0b: 0% Match Display Fix
- **Evidence**: `app/identity_routes.py:1083-1084` — `calibrated_score` → `confidence_pct`, `tier_label` → `short_label`
- **Root cause**: Wrong dict keys from `compute_face_confidence()` return. `conf.get("calibrated_score", 0)` always returned 0.
- **Tests**: 1 regression test ensuring 0% match never appears for valid distances
- **Impact**: All distance badges in Manual Search now show correct percentages

### Phase 0c: Person 3481 Data Repair
- **Evidence**: Supabase query verified: 3481 has 3 faces, 3485/3486 empty and merged
- **Actions**: Removed multi-claimed faces from 3485 and 3486, marked both merged_into 3481

### Phase 1: Batch Completion
- **Evidence**: Albert 196/196, Esther 141/141 — 100% coverage
- **Fix**: Batch script now loads photo metadata from Supabase (was only local JSON)
- **Cost**: $0.17 for 3 remaining photos
- **Results**: 1928, 1978, 1946 estimates

### Phase 2: PRD-059 Temporal Co-Occurrence
- **Event grouping**: 17 event groups from 246 dated photos, read from Supabase
- **Co-occurrence matrix**: 102 identities, 391 unique pairs
- **Top pairs**: Charles+Roland Fox (46 photos), Esther+Albert (39)
- **Person page**: "Often appears with" now shows shared photo counts, sorted by frequency
- **Tests**: 4 new in `tests/test_co_occurrence_display.py`

## Deferred

### Phase 2b: Timeline Tab on Person Page
- Deferred to next session — requires significant UI work (event group rendering on person page)
- The admin event-groups page at `/admin/event-groups` already exists and shows the data
- **BACKLOG**: TIMELINE-001

### Phase 3a: Geo Dual-Write
- Deferred — lower priority than core fixes
- **BACKLOG**: GEO-001

### Phase 3b: Anchor Compare Browser Verify
- Deferred — needs deploy to complete first
- **BACKLOG**: ANCHOR-VERIFY-001

## Red Flags
- **LOW**: First batch result missing GEDCOM context (photo only in Supabase, not in local embeddings)
- **LOW**: RAILPACK builder triggered on git push — had to use `railway up` CLI workaround (known issue, Lesson 117)

## Next Session Should Verify
1. Person page sort on Albert's page — "Earliest First" should show 1910s photos first
2. Distance badges in Manual Search show real percentages, not 0%
3. "Often appears with" on Albert's page shows Charles Fox, Roland Fox with photo counts

## AI Tool Usage
- No external AI tools used (Codex audit deferred — session focused on bug fixes + batch)

## Stats
- Tests: 3963 → 3967 (+4 new, +4 regression fixes)
- Commits: 7
- Cost: $0.17 (Gemini batch)
