# GEDCOM History Storage — Artifact Format & Atomic Import Spec

**Parent:** [OVERVIEW.md](OVERVIEW.md)
**Status:** SHIPPED — Session 164 (2026-06-10), PRD-064 Option B-plus
**Scope:** Cross-repo reusable standard (rhodesli / fox-genealogy / rhodes-wiki)

This document specifies how GEDCOM genealogy data is stored, versioned, and
unwound. It is a first-class, repo-portable deliverable: the artifact format and
import contract are intended for reuse by any project that imports GEDCOM and
needs a lossless, auditable history without database bloat.

---

## 1. Design rationale

Three properties must hold simultaneously:

1. **Fast/cheap latest read** — the serving path reads current state only.
2. **Lossless, auditable history** — every change recorded, every version
   reconstructable, every change unwindable.
3. **No bloat** — failed imports must leave ZERO rows (the root cause of the
   1.3 GB Supabase incident — Lesson 199).

The chosen split (PRD-064 "Option B-plus", validated by two independent Codex
audits) is:

- **Current state lives in Postgres** — exactly one row per entity. No
  `is_current` filter, no multi-state rows, no version_id on read. Smallest,
  fastest footprint.
- **All history lives in Cloudflare R2** — immutable per-version artifacts (raw
  GEDCOM + lossless snapshot + typed diff). The database never stores a
  duplicated payload blob; the lossless payload exists only in R2.
- **The importer is one atomic Postgres transaction.** Failure = full rollback =
  zero rows. This structurally prevents the failed-retry bloat that earlier
  per-batch-commit importers produced.

**Why not a field-level change log in Postgres (rejected Option A):** per-field
rows recreate the multi-million-row table problem, and add/remove entries that
store `NULL → NULL` cannot reconstruct a version (fails the audit requirement).
Entity-level diffs in R2 are lossless and free of DB bloat.

**Why not keep multi-state rows (rejected Option C):** still stores full JSON per
state, far less compact than R2 artifacts, and keeps the bloat risk alive.

---

## 2. R2 history artifact layer

For each **applied** version, three compressed artifacts are written under:

```
gedcom-history/<community>/v<NNNN>-<source_hash12>/
    raw.ged.gz          original GEDCOM bytes (NULL for compensating versions)
    snapshot.jsonl.gz   one JSON line per entity, ALL bundle types (lossless)
    diff.json.gz        typed before/after diff vs the base version
```

`<NNNN>` is the zero-padded version number; `<source_hash12>` is the first 12
chars of the source GEDCOM hash. Keys are immutable once written.

### 2.1 raw.ged.gz

The exact original GEDCOM bytes that were imported, gzipped. `NULL` (artifact
absent) for **compensating versions** (unwinds), which have no source file.

> Always archive the EXACT imported bytes. A later archived export of the "same"
> tree may not byte-match the version actually imported (Lesson 203).

### 2.2 snapshot.jsonl.gz — lossless current state of the version

One JSON object per line, covering **all** bundle entity types:
`individuals`, `families`, `relationships`, `sources`, `media_objects`,
`events`, `records`. Each line:

```json
{"entity_type":"individuals","entity_id":"@I132506612777@","payload":{...},"payload_hash":"a1b2c3..."}
```

- `payload` — the complete entity record (lossless).
- `payload_hash` — see §3. This is the canonical hash and is the unit of
  comparison across versions and during unwind.

The snapshot is the source of truth for reconstructing any historical version
and for computing the next version's diff base.

### 2.3 diff.json.gz — typed change record vs the base version

```json
{
  "schema_version": 1,
  "version_number": 10,
  "base_version": 9,
  "source_hash": "f778...",
  "generated_at": "2026-06-10T00:00:00Z",
  "entities": {
    "individuals": { "added": [...], "modified": [...], "removed": [...] },
    "families":    { "added": [...], "modified": [...], "removed": [...] },
    "relationships": { "added": [...], "modified": [...], "removed": [...] }
  }
}
```

Each item in `added` / `modified` / `removed`:

```json
// added
{"entity_type":"individuals","entity_id":"@I900@","change_type":"added",
 "before":null,"after":{...},"before_hash":null,"after_hash":"9f8e..."}

// modified
{"entity_type":"individuals","entity_id":"@I132506612777@","change_type":"modified",
 "before":{...},"after":{...},"before_hash":"a1b2...","after_hash":"c3d4..."}

// removed
{"entity_type":"families","entity_id":"@F42@","change_type":"removed",
 "before":{...},"after":null,"before_hash":"77aa...","after_hash":null}
```

Because both `before` and `after` payloads are stored in full (not just changed
fields), the diff is lossless and supports exact unwind. This artifact directly
powers the "what's new in this version" use case (§6).

---

## 3. The hash contract

There is exactly ONE hash, computed once per entity at bundle-build time:

- **THE hash** = `gedcom_snapshot.canonical_payload_hash` — SHA-256 over the
  canonical JSON of the entity payload, **excluding** `raw_record_json` and the
  `payload_hash` field itself (so the hash is stable against cosmetic raw-record
  variation and never hashes itself).
- This same value is stored as `payload_hash` in the snapshot, and as
  `before_hash` / `after_hash` in the diff. Comparisons (version diffing,
  unwind safety checks) use it everywhere.

Separately, each **compressed artifact file** has an **artifact SHA-256** =
`sha256(gzipped bytes)`. The three artifact hashes are stored in
`gedcom_versions` and **verified by re-downloading the artifact before COMMIT** —
if a re-downloaded artifact's hash doesn't match, the import aborts and rolls
back.

---

## 4. Manifest — `gedcom_versions` columns

The only history Postgres retains is a tiny per-version manifest row:

| Column | Purpose |
|--------|---------|
| `version_number`, `community_id`, `status` | identity + applied/failed state |
| `source_hash` | hash of the imported GEDCOM (dedup key) |
| `raw_artifact_sha256` | SHA-256 of `raw.ged.gz` (NULL for compensating) |
| `snapshot_artifact_sha256` | SHA-256 of `snapshot.jsonl.gz` |
| `diff_artifact_sha256` | SHA-256 of `diff.json.gz` |
| `artifact_prefix` | the `gedcom-history/<community>/v<NNNN>-<hash12>/` key prefix |
| `artifact_format` | `"v1"` (full B-plus) or `"legacy"` (pre-redesign versions) |
| `diff_summary` (jsonb) | cached counts + changed entity IDs (IDs only) |
| `created_at`, `created_by`, `notes` | when/who/freeform provenance |

No duplicated payload blob is stored in the DB — the lossless payload lives only
in R2. A partial unique index on `(community_id, source_hash) WHERE status='applied'`
makes re-imports idempotent.

---

## 5. Atomic import flow

The importer (`scripts/import_gedcom_version.py`) runs as **one psycopg2
transaction** on the pooler session-mode port (5432). Ordered steps:

1. `pg_advisory_xact_lock` — serialize concurrent imports for the community.
2. **Dup-check** — if an `applied` version with this `source_hash` exists, no-op
   (idempotent).
3. **Allocate version number** — `MAX(version_number)+1` *inside* the txn under
   the advisory lock (avoids MAX+1 races).
4. **Load diff base** — read the PREVIOUS applied version's `snapshot.jsonl.gz`
   from R2 (lossless base; never re-parse an archived file).
5. **Diff** — compute the typed entity-level diff (added/modified/removed) using
   THE hash.
6. **Build + upload + verify R2 artifacts** — write `raw.ged.gz`,
   `snapshot.jsonl.gz`, `diff.json.gz`; re-download each and verify its
   artifact SHA-256.
7. **Apply current-table mutations** — upsert/delete `gedcom_individuals`,
   `gedcom_families`, `gedcom_relationships` to the new current state.
8. **Insert manifest** row into `gedcom_versions`.
9. **COMMIT.**

Any exception at any step → full **ROLLBACK** → ZERO rows changed. (Proven on
real Postgres by forcing a mid-apply failure: 0 rows persisted.)

---

## 6. "What's new" use case

`gedcom_versions.diff_summary` caches per-version change counts plus the IDs of
changed entities (IDs only — payloads stay in R2). A future "what changed in this
version" view reads the summary for an instant overview, and reads the R2
`diff.json.gz` only when the user drills into specific before/after payloads.
This is the native version-over-version change report for rhodesli and any
reusing repo.

---

## 7. Unwind model — conservative compensating version

Unwind (`scripts/gedcom_unwind.py`) does **NOT** reverse-replay a diff. It
creates a new **compensating version** (latest applied by default) whose current
state equals the target prior state, reconstructed from that version's R2
snapshot. Safety gates before applying:

- **Three-way hash check** — for each entity, the current DB hash must equal the
  `after_hash` recorded when the change being unwound was applied. If current
  state has drifted from what the change produced, the unwind would clobber an
  intervening edit → **conflict, abort** (no `--force`).
- **Referential-integrity check** — the resulting state must not orphan
  relationships/families, ignoring removals that belong to the same unwind.

A compensating version has no `raw.ged.gz` (no source file) but still produces a
`snapshot.jsonl.gz` and `diff.json.gz` like any other applied version, so the
history chain stays continuous and the unwind is itself auditable and
re-unwindable.

`reconstruct_version(v)` rebuilds any historical version's full state directly
from its R2 snapshot — used by both unwind and offline audit.

---

## 8. Acceptance invariants

A conforming implementation MUST satisfy:

- **No bloat** — a failed import leaves ZERO rows (structural test required;
  never write a test asserting partial rows survive — Lesson 199).
- **Atomic** — all current-table mutations + manifest insert happen in one
  transaction; R2 artifacts are uploaded-and-verified before COMMIT.
- **Fast** — the serving path reads one row per entity, no version filtering.
- **Lossless** — full before/after payloads in R2; any version is exactly
  reconstructable from its snapshot.
- **Practical** — imports are rare and admin-initiated; reconstruction/unwind
  are batch, admin-only operations and may read R2.

---

## See also

- `docs/prds/064_gedcom_history_storage_redesign.md` — the redesign PRD (SHIPPED).
- `docs/ml/ALGORITHMIC_DECISIONS.md` — AD entries for the storage model, atomic
  importer, artifact/hash contract, and unwind.
- `docs/session_context/session-164-codex-audit-plan.md` /
  `session-164-codex-audit-impl.md` — the two independent Codex audits.
- Lessons 199, 202–204 in `tasks/lessons.md`.
