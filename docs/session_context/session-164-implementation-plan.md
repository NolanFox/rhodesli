# Session 164 — Implementation Plan (PRD-064 Option B-plus)

**Status:** PLAN (pre-Codex-audit) · **Date:** 2026-06-09 · **Effort:** Opus max
**Design:** PRD-064 §4 (Option B-plus) · **Audit basis:** session-163-codex-audit.md

This plan is the concrete blueprint for the end-to-end GEDCOM storage redesign.
It will be Codex-audited (Phase 1) before any code is written; P0/P1 applied first.

---

## 0. Inherited state (verified Phase 0)

- DB **423 MB**. `gedcom_individuals_v2` **267 MB / 43,172 rows** (21,998 distinct
  `gedcom_id`; histogram 1-state×824, 2-state×21,174). `gedcom_families_v2`
  13,158 rows / 6,741 distinct. `gedcom_relationships` 140,796 rows — **already
  current-only** (all `is_current=true`, distinct `edge_key`=140,796; Session 163
  cleaned superseded rows).
- `gedcom_versions`: 9 rows, only **v7 (hash 1e0d…) + v9 (hash f778…) are `applied`**;
  v1-v6 + v8 are `failed` retries (the bloat source).
- **v1 tables `gedcom_individuals`/`gedcom_families` no longer exist** (158e dropped
  them). The `gedcom_dual_read.py` v1-fallback path is therefore dead code.
- Reusable infra: `rhodesli_ml/importers/gedcom_parser.parse_gedcom`,
  `gedcom_snapshot.build_snapshot_bundle` → `GedcomSnapshotBundle`
  (`.individuals/.families/.relationships/.sources/.media_objects/.events/.records`,
  each `dict[id → canonical payload incl. payload_hash]`),
  `canonical_payload_hash`, `diff_entity_maps` (already returns entity-level
  `{added, removed, modified, unchanged}` with **full before/after payloads + hashes**,
  computed over **canonical bundle payloads**, not DB rows — satisfies Codex P1).
- R2 snapshots intact: `gedcom-cleanup-snapshots/2026-06-08-session-163/`,
  `gedcom-version-snapshots/2026-05-08-session-156/`,
  `gedcom-source-snapshots/2026-05-08-session-156/`.
- Pooler 5432 + Management-API SQL both work under the 402 restriction.

---

## 1. Target schema (current-state only)

### `gedcom_individuals` (canonical, one row per `gedcom_id`)
```
gedcom_id      text PRIMARY KEY        -- @I…@ xref
community_id   text NOT NULL DEFAULT 'rhodesli'
name, given_name, surname, gender      text
birth_date, birth_place,
death_date, death_place                text
names_json, events_json,
family_as_spouse_json, family_as_child_json,
notes_json, citations_json             jsonb
payload      jsonb NOT NULL            -- FULL canonical snapshot payload (lossless)
payload_hash text NOT NULL             -- canonical_payload_hash(payload sans raw_record_json)
version_number integer NOT NULL        -- the version that last wrote this row
updated_at   timestamptz NOT NULL DEFAULT now()
```
- One row per entity (PK on `gedcom_id`). NO `is_current`, `first_seen`,
  `last_seen`, `superseded_by`, no per-state duplication.
- `payload` holds the complete canonical snapshot so the app never needs the `_v2`
  per-column projection for new fields; the typed columns are kept for fast SQL
  filters/indexing (surname search, etc.) and back-compat with current readers.

### `gedcom_families` (canonical, one row per `family_gedcom_id`)
```
family_gedcom_id text PRIMARY KEY
community_id   text NOT NULL DEFAULT 'rhodesli'
husband_xref, wife_xref text
children_xrefs_json, marriage_event_json, events_json,
notes_json, citations_json jsonb
payload      jsonb NOT NULL
payload_hash text NOT NULL
version_number integer NOT NULL
updated_at   timestamptz NOT NULL DEFAULT now()
```

### `gedcom_relationships` (re-use existing table; drop versioning columns)
Keep: `id`, `individual_gedcom_id`, `related_gedcom_id`, `relationship_type`,
`family_gedcom_id`, `edge_key` (UNIQUE), `relationship_payload`, `payload_hash`,
`version_number` (new), `updated_at`. **Drop:** `is_current`, `version_id`,
`superseded_by`. Unique key = `edge_key` (already 1:1). community_id implicit
(rhodesli only) — add column for parity, default 'rhodesli'.

### `gedcom_versions` (manifest — keep, extend)
Existing columns kept. ADD:
```
raw_artifact_sha256      text   -- sha256 of raw.ged.gz in R2
snapshot_artifact_sha256 text   -- sha256 of snapshot.jsonl.gz
diff_artifact_sha256     text   -- sha256 of diff.json.gz
artifact_prefix          text   -- R2 key prefix for this version's artifacts
diff_summary             jsonb  -- {added,modified,removed counts + changed entity IDs by type}
```
- `status` ∈ {applied} only (atomic importer never writes `failed` rows — a failed
  import rolls back and inserts NOTHING, including no version row). Keep existing
  `failed` rows as historical audit metadata; they reference zero entity rows.

### Constraints proving "one row per entity"
- PK on `gedcom_individuals.gedcom_id`, `gedcom_families.family_gedcom_id`,
  UNIQUE on `gedcom_relationships.edge_key`. A structural test asserts
  `count(*) == count(distinct id)` for each.

---

## 2. R2 history artifact (the lossless source of truth)

Per successful version `v`, content-addressed under
`gedcom-history/<community>/v<NNNN>-<source_hash12>/`:

| Artifact | Content | Compression |
|---|---|---|
| `raw.ged.gz` | original uploaded GEDCOM bytes | gzip |
| `snapshot.jsonl.gz` | canonical current-state at v: one JSON line per entity `{entity_type, entity_id, payload, payload_hash}` | gzip JSONL |
| `diff.json.gz` | `{schema_version, version_number, base_version, source_hash, generated_at, entities:{individuals|families|relationships:{added:[…],modified:[…],removed:[…]}}}` where each item = `{entity_type, entity_id, change_type, before, after, before_hash, after_hash}` — typed JSON (NOT stringified); adds carry `after`+`after_hash`, before=null; removes carry `before`+`before_hash`, after=null; modified carry both | gzip JSON |

- Keys content-addressed (include `source_hash` prefix). Each artifact's SHA-256 is
  computed on the **compressed bytes**, stored in `gedcom_versions`, and **verified by
  re-download** before the DB transaction commits (mandatory step).
- `diff_summary` cached into `gedcom_versions.diff_summary` = counts + the lists of
  changed entity IDs (IDs only; payloads stay in R2) → instant "what's new" overview.
- Schema documented in `docs/architecture/GEDCOM_HISTORY.md` as a cross-repo standard.

---

## 3. Atomic importer (`scripts/import_gedcom_version.py` rewrite)

New, simpler flow. Reuses parse/bundle/diff; deletes swap-plan/change-log/redirect/
multi-state machinery.

```
import_gedcom(file, community='rhodesli', notes, execute):
  1. raw_bytes = read(file); source_hash = sha256(raw_bytes)
  2. parsed = parse_gedcom(file); bundle = build_snapshot_bundle(parsed, source_file)
  3. new_maps = {individuals: bundle.individuals, families: bundle.families,
                 relationships: bundle.relationships}   # canonical payloads
  4. # read CURRENT state maps from canonical tables (id -> {payload, payload_hash})
     old_maps = load_current_maps(conn)
  5. diffs = {et: diff_entity_maps(et, old_maps[et], new_maps[et]) for et in 3 types}
  6. build artifacts (raw.ged.gz, snapshot.jsonl.gz, diff.json.gz) in memory
  7. # MANDATORY: upload to R2 + re-download + hash-verify. Any failure -> ABORT (no DB write).
     upload_and_verify(artifacts) -> {sha256 per artifact, artifact_prefix}
  8. ONE psycopg2 conn, port 5432:
     BEGIN
       SELECT pg_advisory_xact_lock(hashtext('gedcom_import:'||community))
       # idempotent re-import guard INSIDE txn:
       if exists(applied version with source_hash == source_hash): ROLLBACK + return "already applied"
       version_number = (SELECT COALESCE(MAX(version_number),0)+1 FROM gedcom_versions WHERE community=…)
       apply diffs to canonical tables:
          added/modified individuals|families -> upsert (PK) with version_number
          removed individuals|families       -> delete by id
          relationships: delete edges in removed, upsert edges in added/modified
       INSERT gedcom_versions(... status='applied', artifact shas, artifact_prefix, diff_summary)
     COMMIT
     # any exception -> conn rollback -> ZERO rows changed
  9. return {version_number, summary}
```

- **Removed:** `--skip-change-log` flag, all non-fatal change-log paths,
  `_insert_rows_direct_db` per-batch commits, swap plans, redirects table writes,
  enrichment-queue writes (keep enrichment queue OUT of the import txn or include as
  best-effort post-commit; default: drop from importer, it's a separate concern).
- **Dry-run** (`--execute` absent): do steps 1-5 + print summary; skip 6-8.
- Re-import of an identical source hash is a no-op (idempotent), detected inside txn.
- Use `psycopg2.extras.execute_values` for batch upserts **within the single txn**
  (batching for speed ≠ per-batch commit — one COMMIT at the end).

## 4. Reconstruct + unwind (`scripts/gedcom_history.py`, new)

```
reconstruct_version(v) -> dict[entity_type -> {id -> payload}]:
   download snapshot.jsonl.gz for v from R2, parse → full state. (round-trips snapshot)

unwind(version_number, execute) -> compensating import:
   target = version to revert (its diff.json.gz from R2)
   load current canonical state (hashes)
   for each entity in target.diff:
     change_type added    -> we must REMOVE it; safe iff current_hash == after_hash
     change_type removed  -> we must RE-ADD before; safe iff entity absent now
     change_type modified -> we must restore `before`; safe iff current_hash == after_hash
     else -> CONFLICT (a later version changed it); collect, do not touch
   if conflicts and not --force: report conflicts, abort (no DB change)
   else: apply the inverse as a NEW version (compensating) via the SAME atomic
         importer txn path (new version_number, new R2 artifacts describing the
         compensating diff). Never reverse-replay; never destroy a later change.
```
- Treat add/remove/modify + relationships as one logical unit per version.
- The compensating change is itself a new `applied` version with its own R2 artifacts
  → fully auditable + itself unwindable.

## 5. Migration (`scripts/session164_migrate_to_current_state.py`, one-off)

1. **Snapshot-first**: dump `gedcom_individuals_v2`, `gedcom_families_v2`,
   `gedcom_relationships`, `gedcom_versions` to R2
   `gedcom-cleanup-snapshots/2026-06-09-session-164/` (gzip CSV + sha256 manifest).
   Verify before proceeding.
2. Create canonical tables `gedcom_individuals`, `gedcom_families` (new) +
   alter `gedcom_relationships` (add `version_number`, `community_id`; will drop
   versioning cols after backfill).
3. **Backfill latest state**: for each `gedcom_id`, copy the v2 row with
   MAX(`last_seen_version`) (tiebreak payload_hash) into `gedcom_individuals`,
   building `payload` from the v2 JSON columns. Same for families. version_number =
   the version_number for that last_seen_version (v9 → 9). Relationships already
   current → set version_number = 9, drop is_current/version_id/superseded_by.
4. Backfill `gedcom_versions` artifact hashes from existing session-156 R2 snapshots
   where derivable; otherwise leave NULL (historical versions predate the new
   artifact format — note in manifest. New imports populate going forward).
5. Verify row counts == distinct counts; verify a sample of payloads round-trip.
6. **DROP** `gedcom_individuals_v2`, `gedcom_families_v2` (+ their `current_*_v2`
   views). VACUUM (not FULL — DROP already reclaims; FULL needs AccessExclusive and
   158e showed it times out). Re-measure DB size (target ≤ 300 MB).
7. Collapse `app/gedcom_dual_read.py` → single clean current-state reader
   (`get_individual`/`get_family`/`get_individual_history` read canonical tables;
   history now comes from R2 not multi-row v2). Update `app/relationship_routes.py`,
   `app/page_routes.py`, `app/main.py` callers + any scripts.

## 6. Tests (`tests/test_gedcom_atomic_import.py` + edits)

| ID | Test | Mechanism |
|---|---|---|
| a | failed import → ZERO new rows | INVERT `test_gedcom_versioning.py:649`; force exception mid-apply (monkeypatch upsert to raise on 2nd batch), assert canonical table counts unchanged + no version row |
| b | import refused if R2 upload/verify fails | monkeypatch verify to fail → assert abort + ZERO DB writes |
| c | one row per entity | uniqueness: PK + a test asserting count==distinct on all 3 tables |
| d | unwind conflict detection | construct current_hash ≠ after_hash → assert CONFLICT, no DB change |
| e | reconstruct_version round-trips snapshot | build snapshot → upload → reconstruct → equal maps |
| f | diff artifact lossless | added carries full `after`+hash; removed carries full `before`+hash; modified both; typed JSON survives gzip round-trip |
| g | idempotent re-import | same source_hash twice → 2nd is no-op, version count unchanged |

Most run with mocked R2 (in-memory) + a SQLite/fake or a transactional fixture;
the atomicity test uses a real psycopg2 txn against a disposable schema if available,
else a fake-cursor harness that proves rollback semantics. ML suite must stay green.

## 7. Sequencing / commits (atomic per phase, /clear between)

P2 R2 artifact layer + GEDCOM_HISTORY.md → commit.
P3 schema DDL (migration file, not yet applied) → commit.
P4 atomic importer rewrite → commit.
P5 reconstruct + unwind → commit.
P6 migration script + APPLY + dual-read collapse + caller updates → commit.
P7 tests → commit.
P8 Codex impl audit + fixes → commit.
P10 docs + closeout.

## 8. Risks / watch-items
- Under the 402 restriction, REST is down but pooler+Mgmt-API work → all DB work uses
  psycopg2 on 5432 (NOT the supabase REST client). App readers still use REST and
  won't work until Pro upgrade (Phase 9) — tests that hit live REST stay red until then.
- The migration mutates 267 MB of production data → snapshot-first is mandatory; keep
  v2 tables until canonical tables verified, only then DROP.
- `payload` column duplicates typed columns → acceptable (one row/entity; the win is
  killing the 2× state duplication, not column-level normalization). Keep payload as
  the lossless source; typed columns are derived projections for indexing.
- Relationships have NO per-entity version history need (regenerated from families) →
  treat as derived; the diff still records them for completeness/unwind.
