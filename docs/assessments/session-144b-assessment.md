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

### Afternoon Continuation: Infrastructure + Data Integrity

#### Phase 3a: Geo Dual-Write — DONE
- Geocode script updated: reads from Supabase, writes to both JSON + Supabase `photo_locations`
- Added 9 locations to dictionary (Dayton OH, Detroit MI, Hamilton OH, Cincinnati OH, etc.)
- **541/554 photos geocoded (97.7%)** — up from 268 at session start
- Photo locations dual-keying bug fixed (same inbox_*/SHA256 mismatch as date_labels)

#### Phase 3b: Anchor Compare Browser Verify — DONE
- Playwright screenshots confirm anchor compare panel renders on production
- Input field, Compare button, expanded/collapsed states all verified
- Screenshots saved to `docs/screenshots/session-144b/`

#### Data Integrity Fixes
- **DATA-AUDIT-001**: 55 CONFIRMED with empty anchors. 23 candidates promoted to anchors, 31 merged ghosts (filtered), 1 placeholder (Solomon Galante — GEDCOM-first, valid)
- **DATA-AUDIT-002**: 52 multi-hop merge chains flattened. 0 circular, 0 dangling
- **BATCH-003**: Verified all 82 Session 142 API calls logged in Supabase (was already fixed)
- **SESSION_HISTORY + BACKLOG**: Updated and closed 8 items

#### Security
- **SEC-003**: CSRF `_check_origin()` added to `/tools/search` POST
- Photo locations Postgres dual-keying fix (same pattern as date_labels)
- Face overlay label CSS: `max-width: 120px` + `display: inline-block` + `text-overflow: ellipsis`

### Evening Continuation: Security + UX + Batch

#### SEC-001: PostgREST Filter Injection — DONE
- `.or_()` calls now apply both `_sanitize_postgrest_value` AND `_escape_ilike`
- 3 structural + unit tests
- Codex audit: 0 P0, 0 P1, safe for current vectors

#### FB-005: Needs Name Filter — DONE
- "Needs Name" filter pill added to confirmed section on main page
- Uses canonical `"Unidentified Person "` prefix (Codex P2 fix)
- Already existed on `/people` page (browse_routes.py) — now available from both entry points

#### BATCH-GEDCOM-38: GEDCOM Context Backfill — MOSTLY DONE
- `--rerun-without-gedcom` flag added to batch script
- 36/41 photos re-processed with GEDCOM context ($1.65)
- **277/282 Albert+Esther photos now have GEDCOM context** (was 241)
- 5 remain (Gemini rate-limited, run on next quota reset)
- Codex P1 fix: flag now fails closed when Supabase unavailable

#### Event Groups + Geocode Regenerated
- 18 event groups (was 17), 21 frequent companions
- 541 map pins (97.7% match rate)

## Deferred

### Phase 2b: Timeline Tab on Person Page
- Timeline already exists at `/timeline?person=<id>` with link from person page
- TIMELINE-002 in BACKLOG for inline rendering on person page
- The admin event-groups page at `/admin/event-groups` already shows the data

### GEDCOM Backfill: 5 remaining photos
- Gemini quota rate-limited. Run `--rerun-without-gedcom` when quota resets.

## Red Flags
- **LOW**: RAILPACK builder triggered on git push — had to use `railway up` CLI workaround (known issue, Lesson 117)
- **LOW**: Worktree agents picked up stale branches (Session 139) — had to discard and work directly on main
- **LOW**: 5/282 Albert+Esther photos still lack GEDCOM context (rate-limited)

## Next Session Should Verify
1. Person page sort on Albert's page — "Earliest First" should show 1910s photos first
2. Distance badges in Manual Search show real percentages, not 0%
3. "Often appears with" on Albert's page shows Charles Fox, Roland Fox with photo counts
4. Map shows ~541 pins (was ~268)
5. "Needs Name" filter on confirmed section works

## AI Tool Usage
- **Codex CLI v0.117.0** (o4-mini): 2 audit rounds
  - Round 1: P1 fail-open, P2 incomplete columns, P3 CSS — all fixed
  - Round 2: P2 placeholder prefix inconsistency — fixed
  - Value: MODERATE — caught real bugs

## Stats
- Tests: 3963 → 3980 (+17 new)
- Commits: 20
- Cost: $1.82 (Gemini batch: $0.17 + $1.65)
- BACKLOG items closed: 12 (SORT-001, DISPLAY-0PCT, GEO-001, FACE-OVERLAY-EDGE, DATA-AUDIT-001, DATA-AUDIT-002, BATCH-003, BATCH-GEDCOM-38, SEC-001, SEC-003, ANCHOR-UI-001, FB-005)
- Map pins: 268 → 541
- GEDCOM coverage: 241/282 → 277/282
