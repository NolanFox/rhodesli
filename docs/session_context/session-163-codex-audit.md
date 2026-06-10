# Session 163 — Codex Audit: GEDCOM History Storage Redesign (PRD-064)

**Auditor**: Codex CLI v0.139.0 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context, read PRD-064 + import_gedcom_version.py + repo)
**Scope**: Critique Option A; recommend best design for R1–R5
**Date**: 2026-06-09

## Verdict
**Do NOT adopt Option A as written.** Best fit = **Option B-plus**:
current-state tables in Postgres + a small per-version manifest in Postgres +
immutable compressed raw GEDCOM + canonical snapshot + entity-level
`{before, after, hashes}` diff artifacts in R2. Every DB mutation in ONE direct
Postgres transaction; rollback = conflict-checked compensating import.

## P0 findings
1. **R5 already violated — import is NOT atomic.** Each entity batch opens/commits its
   own connection (`import_gedcom_version.py:516`); a later failure only marks the
   version `failed`, leaving inserted rows behind. A test even *asserts* rows survive
   failure (`test_gedcom_versioning.py:649`). **This is the actual root cause of the
   bloat** (7 failed versions each left partial rows).
2. **Field-level change-log cannot reliably unwind.** Added/removed entities store NULL
   for both before & after (`import_gedcom_version.py:326`); modified values are
   stringified (lose JSON types, JSON-null vs missing). So Option A's field log does
   NOT satisfy R3.
3. **R1 is optional today.** Change-log failures are non-fatal and `--skip-change-log`
   exists — an import can be `applied` with no audit history.

## P1 findings
1. **Field-level rows = wrong granularity** (the old field log hit 1.65M rows). Ranking:
   - Best: B-plus (entity-level before/after stored compressed in R2).
   - Acceptable if DB-queryable history becomes mandatory: one Postgres row per changed
     *entity* with typed `before_payload JSONB`, `after_payload JSONB` + hashes.
   - Reject: one row per changed *field*.
2. **Existing diff infra unsafe to reuse unchanged** — compares full DB rows vs payloads
   (reports metadata as changes); positional list paths `[3]` misreport reorders. Diff
   only canonical semantic payloads.
3. **Mid-history reverse-replay is incorrect.** v2: A→B, v3: B→C — reversing v2 destroys
   v3. Rollback must be a NEW compensating version with three-way hash check (safe only
   if current hash == original after_hash, else conflict).

## P2 findings
- Allocate version number + source-hash check INSIDE the txn under a community-scoped
  `pg_advisory_xact_lock` (current MAX+1 races).
- Single authoritative `imported_at`/`imported_by` on the version.
- Content-address R2 keys; store SHA-256 in `gedcom_versions`.
- Make R2 archiving a MANDATORY import prerequisite (today the backup scripts are
  one-off ops tools, not part of the importer).

## Atomic import mechanism (Codex)
ONE Postgres transaction (NOT staging+swap, NOT table-rename):
1. Parse → canonicalize → diff → upload+verify raw/snapshot/diff to R2.
2. One psycopg conn on port 5432 (direct/session pooler).
3. BEGIN; `pg_advisory_xact_lock(community)`.
4. Apply all current-table inserts/updates/deletes + manifest + redirects + queue rows.
5. Insert version as `applied`; COMMIT. Any exception → full rollback.
Table-rename adds lock/view-dependency hazards; permanent staging doesn't solve
atomicity; transactions give all-or-nothing visibility.

## Assessment (Claude)
**Value: STRONG.** Codex caught three things I missed: (1) the non-atomic import is the
*actual* bloat root cause (not just "we didn't finish PRD-063"); (2) my field-log
wouldn't satisfy R3 because adds/removes store NULL; (3) reverse-replay is unsafe.
It converged on the user's own "alternative" (history in R2, current-only in DB) and
showed it's the BEST option, not a compromise. Adopting B-plus. No findings rejected.
