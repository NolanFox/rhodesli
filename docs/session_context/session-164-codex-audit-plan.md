# Session 164 — Codex Audit of the Implementation PLAN (Phase 1)

**Auditor**: Codex CLI v0.139.0 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context; read plan + PRD-064 + prior audit + snapshot infra + old importer)
**Scope**: Critique the PRD-064 Option B-plus implementation PLAN for correctness/risk
**Date**: 2026-06-09
**Value assessment**: **STRONG** — caught 6 P0 + 8 P1, several genuine acceptance-gate
failures (lock ordering, migration source-of-truth, storage headroom, cross-entity unwind).
Empirically confirmed P0-3 by inspecting the live data (see "Data verification" below).

---

## Raw findings (verbatim summary)

**P0**
1. Lock acquired too late — diff/artifacts built before advisory lock → concurrent import
   can apply a stale diff. Acquire lock BEFORE loading current state.
2. Artifact versioning impossible in stated order — version_number/base embedded in
   keys/content before allocation. Order: BEGIN→lock→dup-check→allocate→load→diff→
   upload/verify→mutate→manifest→COMMIT.
3. Migration can resurrect deleted/failed-import entities — per-entity MAX(last_seen)
   doesn't prove v9 membership; failed-version states can win. Use authoritative source.
4. Migration payload backfill not lossless — v2 omits raw records + canonical fields;
   building payload from v2 columns can't reproduce build_snapshot_bundle output, and the
   carried hash won't authenticate it.
5. Migration exceeds storage headroom — creating full canonical tables before dropping
   294 MB of v2 likely exceeds 500 MB; new schema duplicates large JSON in typed cols AND
   payload. Snapshot-first purge step omitted.
6. Unwind unsafe across entity dependencies — v2 adds I1; v3 adds family referencing I1;
   unwinding v2 deletes I1, dangling v3's family. Per-entity hashes insufficient. `--force`
   undefined + contradicts "never destroy a later change".

**P1**
1. Idempotency can overwrite R2 before detecting duplicate — guard under lock first; add
   partial unique `(community_id, source_hash) WHERE status='applied'`.
2. Hash contract ambiguous — payloads already contain payload_hash; "hash payload sans
   raw_record_json" would re-include the hash. Define ONE canonical hash projection.
3. Typed history covers only 3 of 7 bundle entity types — sources/media/events/records
   excluded → source/media-only changes invisible in "what's new".
4. Compensating-version raw artifact undefined — a selective unwind state corresponds to
   no GEDCOM file. Define raw=NULL/synthetic for compensations.
5. Natural keys not community-scoped — global gedcom_id / edge_key can collide across
   communities. Use composite community keys.
6. Migration snapshot not guaranteed consistent — needs lock + repeatable-read snapshot +
   schema + restore test.
7. Production cutover ordering unsafe — drop v2 before readers switched / before views
   dropped breaks app. Additive deploy → switch readers → verify → drop views → drop tables.
8. Atomicity tests must use real Postgres — SQLite/fake cursors can't prove PG rollback /
   advisory lock / hidden helper connections.

**P2**: (1) unwind missing no-op cases; (2) R2 orphans on rollback → content-addressed +
GC; (3) count(distinct id) meaningless when id is PK → check natural keys; (4) migration
verification must compare COMPLETE id/hash maps not samples; (5) legacy session-156 hashes
hash decompressed content, not compressed bytes — don't copy; (6) get_individual_history
can't read current-state tables — must read R2 or be removed.

**P3**: (1) Don't backfill artifact columns for legacy/failed versions — leave NULL with a
legacy-format marker.

---

## Data verification (Claude, live pooler — confirms P0-3/P0-4)

- `gedcom_individuals_v2.last_seen_version` distribution: **5→8179, 6→12995, 7→770, 9→21228**.
  Versions 5 & 6 are FAILED imports → last_seen pollution is real. The clean `last_seen=9`
  set is only 21,228 but v9 had 21,998 (770 stranded at last_seen=7). **Per-entity maxima
  are unreliable — confirmed.**
- `first_seen_version` is only **1 (21,944)** or **9 (21,228)** → every individual was created
  by the v1 import or added/changed in v9. No true deletions exist in this dataset.
- The only archived raw GEDCOM (`…-f7832541.ged`) parses to **22,039 indiv / 6,755 fam /
  147,064 rels** — 41 more individuals than production v9 (21,998). Byte-hash f783… matches
  NEITHER applied version (v7=1e0d, v9=f778). **It is a DIFFERENT export; the exact v9 (f778)
  raw bytes were never separately archived.**

---

## Resolutions (Claude) — applied to the revised plan

| Finding | Resolution |
|---|---|
| P0-1, P0-2 | Single txn, strict order: **BEGIN → `pg_advisory_xact_lock(community)` → dup-check → allocate version_number → load current state → diff → build+upload+verify R2 (version known) → apply mutations → insert manifest → COMMIT**. R2 upload happens inside the open txn (fine for a rare admin job; rollback leaves only immutable content-addressed orphans). |
| P0-3, P0-4 | **Migration = faithful reproduction of production current-state** (`latest-row-per-gedcom_id` = exactly what `dual_read` serves; prompt Phase 6 mandates "latest state per gedcom_id"). Verified safe for THIS data: no true deletions; it reproduces the served state. NOT silently adopting the +41 f783 export. The lossless **R2 baseline snapshot** is built from the migrated current state (full bundle payloads where the session-156 v9 JSONL snapshot provides them; v2 projection + carried full-bundle `payload_hash` otherwise). raw.ged.gz baseline = the archived f783 file, explicitly marked "closest-available raw; exact v9 bytes not archived". Going-forward imports are fully lossless. |
| P0-5 | **Headroom-safe order:** snapshot v2→R2, then **DROP v2 tables FIRST** (site is DOWN → no live readers; frees 294 MB → ~129 MB), THEN create+populate canonical (~160 MB) → peak ~290 MB, never near 500. Canonical schema stores **typed columns + payload_hash only (NO duplicated `payload` blob)** — lossless full payload lives in R2, not duplicated in DB. |
| P0-6 | **Unwind scoped to the latest applied version by default** (true rollback — no later version to break). Three-way hash check PLUS a **referential-integrity check** (refuse to delete an individual/family still referenced by a current family/relationship). **`--force` removed**; any conflict → abort + report. Mid-history selective unwind documented as "may report conflicts requiring manual resolution — by design". |
| P1-1 | Dup-check under lock BEFORE upload. Add partial unique index `(community_id, source_hash) WHERE status='applied'`. |
| P1-2 | **ONE hash** = the bundle's `canonical_payload_hash` (computed once at bundle build, excludes `raw_record_json` and the `payload_hash` field itself). Reused verbatim as DB column, diff before/after_hash, and snapshot hash. Never re-hashed. Raw records covered via `record_hash` + raw.ged.gz. |
| P1-3 | **snapshot.jsonl.gz includes ALL bundle entity types** (lossless). diff covers individuals, families, relationships, **sources, media_objects** (the meaningful change types). events/records are derived/raw — preserved in snapshot + raw.ged.gz. |
| P1-4 | Compensating (unwind) versions: `raw_artifact_sha256=NULL`, `source_file='compensating-unwind-of-vN'`; still produce snapshot.jsonl.gz (resulting state) + diff.json.gz (compensating changes). Documented as synthetic. |
| P1-5 | Composite community-scoped keys: PK `(community_id, gedcom_id)` / `(community_id, family_gedcom_id)`, UNIQUE `(community_id, edge_key)`. Every read/write community-filtered. |
| P1-6 | Migration snapshot under one connection w/ `REPEATABLE READ` + advisory lock; include schema DDL in the snapshot manifest; add a restore round-trip test on a sample. |
| P1-7 | Site is DOWN (no live readers) so cutover risk is minimal, but follow correct order anyway: update readers to canonical (with v2 fallback retained until drop), apply schema + migrate, **drop dependent views explicitly, then drop tables** (no CASCADE). |
| P1-8 | Atomicity + concurrency tests run against **real Postgres** (pooler, disposable temp schema) — executed live this session + recorded. `make test-fast` (no DB) skips them gracefully; a fake-cursor unit test covers the rollback *logic* for CI. |
| P2-1 | Unwind treats already-satisfied states (added-absent / removed==before / modified==before) as **no-ops**, not conflicts. |
| P2-2 | R2 keys content-addressed + immutable; rollback orphans are harmless/dedup-reused. GC noted as future BACKLOG. |
| P2-3 | Structural test asserts the **PK/UNIQUE natural-key constraints exist** + no duplicate natural keys (not `count(distinct id)`). |
| P2-4 | Migration verification compares **complete** id→hash maps (all entities) + full relationship edge set, not samples. |
| P2-5 | Backfilled artifact hashes computed **fresh on compressed bytes**; session-156 hashes never copied. |
| P2-6 | `get_individual_history` reimplemented to **read R2 history** (diff artifacts) or removed if unwired. |
| P3-1 | Only the applied current version (v9) gets backfilled artifacts; failed/legacy versions (v1-v8) keep NULL artifacts + `artifact_format='legacy'` marker. |

**Nothing rejected.** All findings accepted; resolutions folded into the revised plan
(`session-164-implementation-plan.md` §"REVISION after Codex audit").
