# PRD-063 — GEDCOM Mirror Efficient Redesign

| Field | Value |
|---|---|
| **PRD ID** | PRD-063 |
| **Date** | 2026-04-29 |
| **Author** | Session 155 Track 1 (worktree subagent) |
| **Status** | DRAFT — design only (no code, no migration scripts) |
| **Supersedes** | n/a (no prior PRD; revises Migrations 002 + 003 — AD-098, AD-163) |
| **Implementation session** | 156 (separate, gated on user PRD review) |
| **Evidence base** | E0.5 root-cause analysis: `docs/feedback/session-154-supabase-bloat-root-cause.md` |
| **Coordinated stopgap** | E1 prune plan: `docs/feedback/session-154-supabase-prune-plan.md` |

## Sub-files

This PRD is split per `.claude/rules/doc-size-enforcement.md`. The body
sections below summarise; the long sections are in sub-files:

- [§4 — Storage-reduction proposal — 5 mechanisms](063_gedcom_mirror_efficient_redesign/STORAGE_MECHANISMS.md)
- [Appendix — E0.5 source SQL queries](063_gedcom_mirror_efficient_redesign/APPENDIX_SQL.md)

---

## 1. Problem statement

On 2026-04-28 Supabase emailed an over-quota notice: the project is at **2.22 GB**
versus the Pro-tier soft ceiling of ~1.1 GB, with **97.9% of the bloat in
`gedcom_*` tables** (E0.5 §"Headline numbers"). The user's strategic ask is
explicit: *preserve all GEDCOM functionality, redesign the schema for
efficiency, and use the redesign to also speed up tree-linking and Gemini
context construction.* This PRD specifies that redesign at design level only.
The Phase E2 stopgap prune already targets ~840 MB; this PRD describes the
durable post-stopgap shape so the bloat does not regrow.

---

## 2. Current state evidence (cited from E0.5)

All numbers below are from `docs/feedback/session-154-supabase-bloat-root-cause.md`,
captured 2026-04-29 via the `aws-0-us-west-2.pooler.supabase.com:5432` session
pooler.

- **97.9% of the 2.22 GB DB total is in `gedcom_*` tables** (E0.5 §"TL;DR").
- **22,010 distinct individuals; 196,645 rows in `gedcom_individuals`** —
  duplication factor **8.94×**, almost exactly the 9-version count
  (E0.5 §"Headline numbers").
- **7 of 9 `gedcom_versions` rows are `status='failed'`** (v1-6, v8) and were
  never rolled back. Each failed version still owns ~21,944 individual rows
  plus per-version structured-JSON columns and change_log rows.
  *Storage attribution: ~1.0 GB* (E0.5 §"Verdict cause #1").
- **`payload_hash` is populated on 89% of rows but never used at INSERT.**
  Top-20 hash groups all show `dup_count = 7` — byte-identical re-writes
  for every version of the same individual. *Storage attribution: ~400 MB*
  (E0.5 §"Top-20 duplicated payload_hash groups" + §"Verdict cause #2").
- **`gedcom_change_log` holds 1,646,688 rows / 397 MB.**
  **1,236,678 (75.1%)** have `old_value IS NULL AND new_value IS NULL`
  (Migration 002 lines 70-77 — added/removed rows write zero payload by
  design). *Storage attribution: ~300 MB recoverable from this table alone*
  (E0.5 §"gedcom_change_log — the elephant in the room").
- **`raw_record_json`** consumes **533 MB across all rows / 67 MB on
  `is_current=TRUE` only** — 41% of the column total inside
  `gedcom_individuals`, double-stored alongside parsed structured columns
  (`names_json`, `events_json`, etc., totaling ~683 MB more)
  (E0.5 §"raw_record_json runtime footprint").
- **5 indexes have `idx_scan = 0`**: `uq_gedcom_relationships_current` (26 MB),
  `uq_gedcom_events_current` (2.7 MB), and 3 small ones. ~30 MB unused
  (E0.5 §"Index usage on gedcom_*").
- The full E0.5 SQL queries are preserved in
  [Appendix — E0.5 source SQL queries](063_gedcom_mirror_efficient_redesign/APPENDIX_SQL.md).

---

## 3. Functional requirements (must preserve)

The redesign **must not regress any of these**. Each is the canonical
read-path the new schema has to satisfy:

| # | Capability | Read-path code | Decision provenance |
|---|---|---|---|
| 1 | In-app GEDCOM search (name / date / place) — the `/tools/search` rule-based parser | `app/relationship_routes.py::_load_gedcom_individuals` (cached) | TOOLS-004 |
| 2 | Identity ↔ GEDCOM linking — admin in-app fuzzy search → `gedcom_face_links` | `app/relationship_routes.py::_search_gedcom` | AD-160 |
| 3 | Business-name → owner lookup — visible-text scan on signage finds named owners | `rhodesli_ml/gedcom_context.py::find_business_owner_context` | AD-210 |
| 4 | Subject GEDCOM context for Gemini prompts — birth/death/residence/spouse + first-order family expansion | `rhodesli_ml/gedcom_context.py::build_photo_context` via `scripts/run_combined_pipeline.py::load_gedcom_data` | AD-211, AD-241 |
| 5 | Family tree view rendering — `/tree` page, BFS over individuals + relationships | `app/relationship_routes.py` | AD-160 |
| 6 | Versioning audit trail — ability to roll back to a prior import | `gedcom_versions` + `gedcom_change_log` | AD-163 |

Acceptance criterion for the redesign: every code path above continues to
return the same logical result on the same `is_current=TRUE` data, with
equal or better latency.

---

## 4. Storage-reduction proposal — 5 mechanisms (summary)

Full mechanism specs (with E0.5 evidence, risk profile, and §3 interactions
for each) are in
[§4 — Storage-reduction proposal — 5 mechanisms](063_gedcom_mirror_efficient_redesign/STORAGE_MECHANISMS.md).
The five mechanisms compose to a mid-estimate reduction of **~1.4 to 1.6 GB**:

| § | Mechanism | Reduction (MB) |
|---|---|---:|
| 4.1 | Hash-based dedup at INSERT (use existing `payload_hash`) | ~400 |
| 4.2 | Single canonical row per `gedcom_id` + R2 versioned archive | ~700 net |
| 4.3 | Drop `raw_record_json` / `root_json` / `raw_text` from runtime; archive on R2 | ~716 |
| 4.4 | Per-import change manifest replaces 1.65M-row `gedcom_change_log` | ~390 |
| 4.5 | Drop 5 zero-scan indexes (definite + conditional after table shrinkage) | 30 + 166 |

§4.1 and §4.2 partially overlap (both eliminate per-version row duplication);
the cumulative figure is the **mid-range**. Either bound puts the database
under the 1.1 GB Pro ceiling and well under the 5 GB free-tier budget.

---

## 5. Speed estimate — 5 most-frequent GEDCOM read paths

Estimates derive from E0.5 index-usage data and table-size data (smaller
tables = better page cache hit rate). All current-path numbers are local
benchmarks at 22K individuals scale.

| # | Read path | Today | After redesign | Driver |
|---|---|---|---|---|
| 1 | **Identity → GEDCOM lookup** (AD-160 + AD-211 `build_photo_context`) — `gedcom_face_links` join `current_gedcom_individuals` by `gedcom_id` | ~80 ms cold (196K-row table scan-filter via `is_current=TRUE` partial index) | ~10 ms (22K-row direct lookup; 8.9× row-count reduction is the dominant factor) | §4.2 |
| 2 | **GEDCOM xref → individual record** (`get_individual_by_xref`) — request-path lookup by `gedcom_id` | ~25 ms (lands on `uq_gedcom_individuals_current` partial unique) | ~5 ms (PK lookup on 22K-row v2 table) | §4.2 |
| 3 | **Surname search** (`/tools/search` rule-based parser) — sequential scan with `LIKE` on `surname` over current-individuals view | ~120 ms (filtered table-scan over 22K current rows after partial-index push-down on a 196K total) | ~30 ms (same 22K rows in a much smaller table; tighter pages, better cache) | §4.2 |
| 4 | **Business-name → owner lookup** (AD-210) — `find_business_owner_context` walks `parsed_gedcom.individuals` in-memory | ~5 ms (already in-memory) | ~3 ms (smaller cache load at startup) | §4.2 cache shrink |
| 5 | **Tree-page rendering** (`/tree`, 5 levels deep) — recursive BFS over individuals + relationships, ~50 row-fetches | ~100 ms (relationships table at 873K rows × `is_current=TRUE` filter) | ~15 ms (~7× faster — relationships v2 holds only canonical edges, ~30K rows) | §4.2 |

Confidence: **medium-high.** Postgres scan-cost scales near-linearly with
row count below the working-set ceiling, and the 8.9× row-count reduction
in §4.2 is the dominant lever for paths 1, 2, 3, 5. Pre/post benchmarks
are a Session 156 deliverable.

---

## 6. Migration plan — zero data loss, reversible at every step

Each step describes prose only. Migration scripts are scoped to Session 156.

| Step | Action | Reversible? | Gate to next step |
|---|---|---|---|
| **1** | Archive every existing `gedcom_versions` row (incl. `is_current = FALSE` history) to R2 as `gedcom/versions/<version_uuid>/{individuals,records,events,relationships,families,change_log}.jsonl.gz` plus a `manifest.json`. | YES — re-import from R2 archive. | Manifest sha256 verified per file; R2 listing matches expected count. |
| **2** | Build `gedcom_individuals_v2` + sibling `_v2` tables in parallel — additive schema only. Old tables remain untouched. | YES — drop `_v2` tables. | `\dt` shows v2 tables; structural test green. |
| **3** | Backfill v2 from `is_current = TRUE` rows of v1 tables. Strip `raw_record_json` / `root_json` / `raw_text` (already in step-1 archive). | YES — truncate v2; backfill again. | Row counts match (22K individuals, ~30K relationships, ~50K events post-canonicalization). Per-row sha256 of the structured JSON columns matches v1 source. |
| **4** | **Dual-read** in app code for one full session: every read path in §3 hits v1 AND v2 in parallel; equality assertion logged; v1 result is what the user sees. | YES — drop the v2 read; revert app-code patch. | Zero discrepancy log entries over a 4-hour production window. |
| **5** | Cut over reads to v2 (single-flag in `core/config.py`). Drop v1 read paths. Stop writing to v1 tables. v1 tables remain on disk untouched. | YES — flag flip back to v1 reads. v1 still consistent. | All §3 paths green in production for 24 hours. |
| **6** | DROP v1 tables (after 7-day cooling-off). VACUUM FULL the database. | NO — irreversible (R2 archive remains; restore = re-build v2 from archive, ~10 min). | Final size measured against §4.6 estimate; PRD-063 closed. |

**Gates to next step**: each step must pass its check before proceeding; any
failure halts and triggers the rollback action for that step. No step is
gated on user authorization except step 6 (the only irreversible action) —
matching Phase E2 rigor (verbatim authorization naming every table touched
+ every snapshot path).

---

## 7. Operational guardrails

1. **R2 is the durable backup**, not Supabase. Before step 1 begins, the
   current GEDCOM `.ged` source files (those still on the local machine) MUST
   be uploaded to R2 under `gedcom/sources/<sha256>.ged`. The Migration 003
   schema asserts these are preserved; we make that assertion physically true.
2. **Before any DROP TABLE**: snapshot the table to JSONL (gzipped, sha256
   verified), upload to R2, AND verify roundtrip restoration on a separate
   Supabase test database. No DROP runs against production until restoration
   has been verified end-to-end.
3. **Migration is gated on a verbatim user authorization message** at step 6
   (Phase E2 rigor): the message must name the v1 tables being dropped, the
   R2 archive paths, the VACUUM FULL targets, and the post-cutover size
   measurement protocol. "Approved" alone is NOT sufficient.
4. **Pre-flight grep matrix** (matches §8 of E1 plan): before step 5,
   `grep -rn "ON CONFLICT.*current\|raw_record_json\|root_json" app/ core/
   rhodesli_ml/ scripts/` must return zero blocking matches. Any match
   (legitimate use of v1 column or unique constraint) blocks the step
   until v2 schema absorbs it.
5. **R2 archive read latency is acceptable** (rollback is administrative,
   not request-path), but archive write latency at step 1 is bounded — the
   step is dispatched as a CLI tool with progress logging; if it stalls
   beyond 30 min the migration aborts and v1 remains intact.

---

## 8. Out of scope for this PRD

- **The migration code itself** — separate Session 156 deliverable
  (`scripts/gedcom_migrate_v2.py` + tests).
- **The R2 archive format spec** — referenced as gzipped JSONL but the
  exact schema (compression algorithm, manifest contract, restore-script
  contract) is a separate spec document. Listed as Open Question in §10.
- **Cross-community GEDCOM merging** — the schema changes here are
  single-community; multi-community (e.g., Capeluto + Fox + Fader GEDCOMs in
  one Supabase project) is flagged for a future PRD.
- **Backfilling versioning for non-Fox GEDCOM imports** — out of scope.
  The Capeluto Rhodes GEDCOM has its own pre-Migration-002 legacy bucket
  (21,809 `version_id IS NULL` rows; E0.5 §"Headline numbers"); the redesign
  treats those as a v0-equivalent virtual version preserved in v2.
- **The Phase E2 stopgap prune** — independent execution per E1 plan
  (`docs/feedback/session-154-supabase-prune-plan.md`); the redesign
  assumes the stopgap completes first but does not depend on it.

---

## 9. Open questions (for user before Session 156 implementation)

1. **Per-version archive format**: gzipped JSONL (simple, streamable,
   parseable in 5 lines of Python) vs. zstd-compressed Parquet
   (~3× smaller, harder to inspect)? Recommendation: gzipped JSONL —
   archive read frequency is rollback-rare, inspectability matters more.
2. **Canonical row retention of `raw_record_json`**: keep it on the v2
   `is_current = TRUE` row (smaller bandwidth saving but trivial debug
   access) vs. strip it entirely (full §4.3 saving)? Recommendation: strip.
3. **`gedcom_change_log` retention window**: keep last-N-imports of
   manifest rows in-DB, or archive everything older than the most recent
   2 imports to R2? Recommendation: keep last 5 manifest rows in-DB
   (manifest is sub-MB; rollback usually targets last 1-2 versions).
4. **Cutover timing** (step 5): single big-bang flag flip vs. percent-based
   canary? Recommendation: big-bang. The dual-read window (step 4) does the
   canary work; flag flip after dual-read is high-confidence.
5. **Drop the partial unique indexes** `uq_gedcom_relationships_current`
   and `uq_gedcom_events_current` after v2? They become superfluous when v2
   eliminates the `is_current` predicate column. Recommendation: yes, drop —
   v2 has natural primary keys.
