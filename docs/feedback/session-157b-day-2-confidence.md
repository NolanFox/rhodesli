# Session 157b — PRD-063 Day 2 Confidence Assessment (Track B4)

**Date**: 2026-05-09
**Author**: Session 157b orchestrator (Claude Opus 4.7)
**Decision required**: PROCEED to Session 158 cutover OR HOLD for 157c?
**Recommendation**: **PROCEED**

## Day 2 deliverables status

| Track | Deliverable | Status | Evidence |
|---|---|---|---|
| **B1** | Catch-up backfill v1 → v2 since 2026-05-08T04:56:15Z | NO-OP CONFIRMED | `scripts/session157_full_backfill_gedcom_v2.py` ran dry-run; 0 post-cutover rows in either table; commit `8047dbc8` |
| **B2** | Dual-read helper module + 4 unit tests + wire into `_load_gedcom_individual` | SHIPPED | `app/gedcom_dual_read.py` (~180 lines); 13 tests passing; wired into `app/relationship_routes.py:_load_gedcom_individual`; commit `52eaed38` |
| **B3** | Side-by-side query timing (100 iter × 4 paths × 2 backends) | SHIPPED | `scripts/session157b_query_timing.py`; `docs/session_context/session-157b-query-timing.md`; commit `a8fa858a` |
| **B4** | This document | SHIPPED | (current commit) |

## Carry from Phase 157b-0

v1/v2/manifest row counts at session start (verified 2026-05-09 02:18 UTC):
- `gedcom_individuals_v2`: **21,998** (matches Session 156 backfill)
- `gedcom_families_v2`: **6,741** (matches)
- `gedcom_change_manifest`: **9** (matches)
- Post-cutover v1 deltas: **0** in both individuals and families
- Harry Fox repair: 5 anchors / version_id=14 (matches Session 156)
- Belle Isle Conservatory Young Man (`ef39908e-...`): INBOX, has notes (matches)

## Track B1 detail — backfill catch-up

**Script**: `scripts/session157_full_backfill_gedcom_v2.py`. Reads
`is_current=TRUE AND created_at > '2026-05-08T04:56:15Z'` rows from
`gedcom_individuals` and `gedcom_families`, computes payload_hash (or
re-uses v1's column), INSERTs into v2 with `ON CONFLICT (payload_hash)
DO NOTHING`, then UPDATEs `last_seen_version` for already-known hashes.

**Result**: 0 rows in both tables. No concurrent genealogy session imported
between Sessions 156 and 157b. The Day 1 backfill captured the entire
production v1 state. `--execute` correctly skipped per spec ("only run if
dry-run shows >0 deltas AND nothing surprising").

**Implication for cutover**: v2 is a complete superset of v1's
`is_current=TRUE` rows for the canonical fields (name, given_name, surname,
gender, birth_date/place, death_date/place, names_json, events_json,
family_as_*, notes_json, citations_json). The dual-read fallback path
should never trigger in production unless a future genealogy session
imports between now and Session 158 — and the catch-up script can be
re-run on demand to keep v2 current.

## Track B2 detail — dual-read helper

**Module**: `app/gedcom_dual_read.py`
- `get_individual(gedcom_id, *, include_rich=False, sb=None)` — v2-preferred,
  v1 fallback (current_gedcom_individuals view → gedcom_individuals base
  table). Handles PGRST205 / "relation does not exist" silently to support
  pre-cutover environments.
- `get_family(family_gedcom_id, *, sb=None)` — v2-preferred, v1 fallback.
- Documented thin/rich field constants matching AD-244 schema.

**Wired into**: `app/relationship_routes.py::_load_gedcom_individual`. This
is the single per-id read path used by `/tools/search` GEDCOM lookups,
person-page GEDCOM context (Belle Isle, Harry Fox, Albert Fox, etc.),
and `/tree`. Bulk loaders (`_load_gedcom_individuals`) intentionally
untouched: they read the entire mirror at once via TTL cache, where v2's
smaller row count would only matter if the cache hit rate degraded.

**Out of scope** (per prompt): `gedcom_records`, `gedcom_events`,
`gedcom_relationships` remain v1-only. Anything reading those continues
unchanged.

**Tests**: 13 unit tests (`tests/test_dual_read_helper.py`) covering the
4 spec cases (v2-only, both, v1-only, neither) plus PGRST205 fallthrough,
empty-id short-circuit, and field-constant schema sanity. All passing.

`make test-fast`: 4259 passed (4246 baseline + 13 new).

## Track B3 detail — query timing

**Script**: `scripts/session157b_query_timing.py`. 100 iter × 4 paths × 2
backends via psycopg2 pooler connections (no app TTL caches). Sampled 50
random gedcom_ids and 20 random surnames from v2 to use as test inputs
(both also exist in v1 since v2 is a subset of v1's is_current=TRUE rows).

**Headline**: all 4 measured paths are **statistical ties** on median
(differences within 5%). v2 wins p95 tail latency on 3 of 4 paths.

| Path | v1 median | v2 median | Median Δ | v1 p95 | v2 p95 | p95 Δ | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| `1_single_id_lookup` | 81.29ms | 80.57ms | -0.9% | 115.56ms | 87.39ms | **-32%** | TIE (v2 better p95) |
| `2_bulk_thin_load` | 100.40ms | 100.63ms | +0.2% | 401.42ms | 381.07ms | **-5%** | TIE (v2 marginally better p95) |
| `3_surname_search` | 114.19ms | 109.67ms | -4.0% | 153.69ms | 152.18ms | -1% | TIE |
| `4_is_current_filter` | 83.88ms | 82.77ms | -1.3% | 302.31ms | 148.92ms | **-51%** | TIE (v2 dramatically better p95) |
| `5_dual_read_helper` (e2e) | n/a | 104.33ms | n/a | n/a | 159.61ms | n/a | reference |

**Why ties everywhere on median**: us-west-2 pooler latency floor (~80ms)
dominates query execution time. The 18× / 14× row reduction shows up in
tail latency (p95) rather than median.

**Why no regressions**: PostgreSQL row reads at this size (~22K vs ~196K)
are both well within page-cache, and both have an index on gedcom_id (v2
has `uq_gedcom_individuals_v2_payload_hash` plus implicit gedcom_id index;
v1 has the standard gedcom_id index). Indexes mean per-id lookups are
O(log n) for both, and 22K vs 196K is ~14 vs ~17 levels of B-tree height.
Negligible difference.

**Verdict**: GREEN — no path is meaningfully slower on v2.

## Open issues for Session 158

The Session 158 prompt should account for:

1. **Other v2 tables not built yet** — `gedcom_records`, `gedcom_events`,
   `gedcom_relationships` are still v1-only. Decision: either (a) build
   v2 versions of these in 158 before cutover (~2-3 hours), or (b) keep
   v1 alive for these specific reads and DROP only `gedcom_individuals` +
   `gedcom_families` from v1.
   - **Recommended**: option (b). The storage win comes mostly from
     gedcom_individuals (175K v1 rows, 22K v2 rows, ~150 MB savings). The
     other tables are smaller. Read-bridge for them is fine.

2. **Bulk read path** — `_load_gedcom_individuals` (cache-miss bulk loader)
   not yet wired to v2. Decision: wire it in 158 before DROPping v1, or
   leave v1 alive for bulk reads only. The query timing showed v2 is
   ~tied on bulk reads, so either approach works. Wiring is preferable
   for cleanliness.

3. **`current_gedcom_individuals` view** — v1 view is the most-used read
   path today. After DROP v1 tables, this view must either (a) be re-pointed
   at v2, or (b) be dropped entirely with all readers re-pointed to v2 by
   the dual-read helper.
   - **Recommended**: drop the view; readers go through the helper or
     direct v2 reads.

4. **VACUUM FULL** is mandatory after DROPping v1 to reclaim disk. PRD-063
   §4.3 sequence. The R2 archives at `gedcom-version-snapshots/2026-05-08-session-156/`
   are the rollback path if anything goes wrong.

5. **Re-run query timing post-cutover** to confirm production parity.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Concurrent genealogy session imports between 157b and 158 | LOW (no recent imports) | Catch-up script `session157_full_backfill_gedcom_v2.py` is idempotent and ready |
| Row not found in v2 because Session 156 backfill missed an edge case | VERY LOW | Day 1 backfill ran clean per session-156-assessment.md; dual-read fallback covers it anyway |
| v2 read regression we didn't measure (e.g., specific surname index gap) | LOW | Dual-read helper falls back to v1 silently; cutover plan in 158 keeps v1 around for 24h before final DROP |
| Lost data in DROP v1 step | VERY LOW | R2 archive at `gedcom-version-snapshots/2026-05-08-session-156/v9/` provides full rollback |

## Recommendation

**PROCEED to Session 158 cutover.** All Day 2 deliverables shipped. Catch-up
backfill is a no-op (no production drift). Dual-read helper unit-tested
and wired. Query timing is GREEN with non-regressing medians and notably
better v2 tail latency. Three structural choices for 158 (bulk wiring,
view handling, other-tables strategy) are documented above with
recommendations.

**Session 158 prompt should include**:
- Phase 158-0: re-verify carry (v2 row counts, post-157b drift, Harry/Belle Isle)
- Phase 158-1: re-run B1 catch-up backfill (idempotent; should still be 0)
- Phase 158-2: cutover decision (full v2 vs v2-for-individuals-and-families-only)
- Phase 158-3: DROP v1 tables (with R2 rollback path documented in commit)
- Phase 158-4: VACUUM FULL on Supabase
- Phase 158-5: re-query timing + DB size; expect drop from 2.22 GB → 600-700 MB
- Phase 158-6: browser-verify all canonical pages + GEDCOM-aware pages
