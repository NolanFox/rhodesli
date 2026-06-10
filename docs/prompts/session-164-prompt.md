# Session 164 Prompt — GEDCOM Storage Redesign (PRD-064 / Option B-plus), End-to-End

**Context (READ FIRST):** [docs/session_context/session-164-context.md](../session_context/session-164-context.md)
**Design:** [PRD-064](../prds/064_gedcom_history_storage_redesign.md) ·
**Design audit:** [session-163-codex-audit.md](../session_context/session-163-codex-audit.md)
**Predecessor:** Session 163 (Supabase recovery + this design)
**Mode:** implementation → data-integrity. Effort: **Opus `max`**. Think carefully,
step-by-step. This touches the data layer — Lesson 153–156 category.

---

## Mission
Replace the bloat-prone versioned GEDCOM mirror with **Option B-plus**: current-state-
only Postgres tables + a tiny per-version manifest + immutable, lossless, content-
addressed history artifacts in R2, written by a **single-transaction atomic importer**,
with a **conflict-checked compensating-unwind** utility and a **version-diff ("what's
new") capability**. End state: amazingly good, not over-engineered, doesn't break, no
bloat, fast, preserves everything, practical.

## Non-negotiable design tenets (acceptance gates, verified in Phase 9)
1. **No bloat** — DB ≤ 300 MB after migration; history lives compressed in R2, never
   duplicated into Postgres. One row per entity in current-state tables.
2. **Doesn't break** — import is atomic: a failed/partial import leaves **ZERO** new or
   orphan rows. Proven by a structural test (invert the current
   `test_gedcom_versioning.py:649` which today asserts the opposite).
3. **Runs fast** — latest-version reads require no `is_current` filter, no version dedup,
   no multi-state scan.
4. **Preserves everything** — every GEDCOM version's raw file + canonical snapshot +
   entity-level `{before, after, hashes}` diff is in R2, lossless (typed JSON, not
   stringified). Exact point-in-time reconstruction + exact unwind are possible.
5. **Practical, not over-engineered** — imports are rare (admin-only, ~quarterly). No
   distributed-systems machinery. A single Postgres transaction is the whole atomicity
   story.
6. **Use-case aware** — the R2 diff artifact is designed to power a future
   **"what's new in this version"** view (valuable for rhodesli AND fox-genealogy /
   rhodes-wiki). Keep the artifact schema clean + documented as a cross-repo standard.

## Phases

### Phase 0 — Orient & verify inherited state
- Re-read this prompt + PRD-064 + the Codex design audit.
- Verify: DB size, `gedcom_individuals_v2` still present, R2 snapshots intact
  (`gedcom-cleanup-snapshots/2026-06-08-session-163/` + session-156), pooler 5432 works,
  Management-API SQL works, `SUPABASE_ACCESS_TOKEN` present. Confirm site still
  restricted (expected). `make test-fast` baseline green.

### Phase 1 — Plan + pre-implementation Codex audit of the PLAN
- Write a concrete implementation plan (schema DDL, importer flow, artifact schema,
  unwind algorithm, migration steps, test list).
- **Codex audit the PLAN** (`codex exec "<plan review prompt>" </dev/null`, gpt-5.5/
  xhigh; verify model pin fresh first). Apply P0/P1 before coding. Save to
  `docs/session_context/session-164-codex-audit-plan.md` with provenance header.

### Phase 2 — Artifact schema + R2 layer (the source of truth for history)
- Define the **GEDCOM history artifact** (document in PRD-064 / a new
  `docs/architecture/GEDCOM_HISTORY.md`, cross-repo-reusable):
  - `raw.ged.gz` (original upload), `snapshot.jsonl.gz` (canonical current state at this
    version), `diff.json.gz` = per-entity `{entity_type, entity_id, change_type:
    added|modified|removed, before:JSONB|null, after:JSONB|null, before_hash, after_hash}`.
  - Content-addressed keys; manifest stores each artifact's SHA-256.
- Implement upload + verify (re-download + hash-check) as a **mandatory** import step.

### Phase 3 — Current-state schema + tiny manifest
- Canonical tables `gedcom_individuals`, `gedcom_families`, `gedcom_relationships`:
  one row per entity (drop `is_current`/`superseded_by`/`first_seen`/`last_seen`/per-
  state duplication). Keep only typed semantic columns + JSONB payloads the app reads.
- `gedcom_versions` manifest: when/who/counts/source_hash + R2 artifact SHA-256s + a
  **small diff summary** (counts: added/modified/removed, and the list of changed
  entity IDs — IDs only, payloads stay in R2). This powers a fast "what changed" overview
  without reading R2; details fetched from the artifact on demand.

### Phase 4 — Atomic importer rewrite (the core correctness fix)
- Rewrite `scripts/import_gedcom_version.py` (and/or `rhodesli_ml/importers/`):
  parse → canonicalize → diff (canonical semantic payloads only; no positional list
  paths; no DB-metadata noise) → upload+verify R2 artifacts → **ONE psycopg
  transaction on port 5432 under `pg_advisory_xact_lock(community)`** that allocates the
  version number, applies all current-table upserts/deletes, writes the manifest, and
  marks the version `applied`; COMMIT. Any exception → full ROLLBACK.
- Remove `--skip-change-log` and any non-fatal audit path. Refuse to import if R2
  artifacts didn't upload+verify. Dedup source-hash inside the txn (idempotent re-import).

### Phase 5 — Reconstruction + conflict-checked unwind utility
- `reconstruct_version(v)` — rebuild any version's full state from R2 (snapshot or replay).
- `unwind(version)` — apply a **new compensating version**: for each entity in that
  version's diff, only revert if the entity's current hash == that diff's `after_hash`
  (safe); otherwise record a conflict and require explicit resolution. Never destroy a
  later version's change. Treat added/removed/modified + relationships as one logical unit.

### Phase 6 — Migrate + delete technical debt
- Migrate `gedcom_individuals_v2`/`families_v2` (latest state per `gedcom_id`) → canonical
  current-state tables. Backfill `gedcom_versions` artifact hashes from the existing R2
  snapshots where possible.
- Snapshot-first, then DROP `gedcom_*_v2` and collapse `app/gedcom_dual_read.py` into a
  single clean current-state reader. Update `app/relationship_routes.py` + all callers.
- Verify DB ≤ 300 MB. Remove now-dead code/scripts (note them in the assessment).

### Phase 7 — Tests (both suites; structural + regression)
Mandatory structural tests: (a) failed import → ZERO rows (invert `:649`); (b) import
refused if R2 artifact upload/verify fails; (c) current-state tables have exactly one
row per entity (uniqueness constraint + test); (d) unwind conflict detection; (e)
reconstruct_version round-trips to the R2 snapshot; (f) diff artifact is lossless
(typed JSON, adds/removes carry full payloads). `make test-fast` + ML suite green.

### Phase 8 — Post-implementation Codex audit of ALL work
- `codex exec` over the new importer + schema + unwind + migration + tests. Fix P0/P1;
  BACKLOG/justify P2. Save `docs/session_context/session-164-codex-audit-impl.md` w/
  provenance. Iterate if fixes introduce issues.

### Phase 9 — Restore service + browser verify (Claude Chrome, READ-ONLY on prod)
- **USER GATE:** user upgrades to Pro (only lever that lifts the Fair-Use restriction
  before ~25 Jun). Confirm REST 200 + `/health` `supabase: ok`.
- Force app refresh if needed (Railway redeploy needs `railway login`).
- Browser-verify: landing, People (non-zero), a person page, **relationships/family
  page** (the GEDCOM-backed surface), Photos, Map, GEDCOM admin version list,
  Help Identify, 404. Screenshots → `docs/screenshots/session-164/`.
- Verify acceptance gates 1–6 with evidence.

### Phase 10 — Document + closeout
- ADs for the storage architecture + atomicity + unwind decisions (provenance).
- `docs/architecture/GEDCOM_HISTORY.md` (cross-repo artifact spec) ≤ 300 lines.
- PRD-064 status → SHIPPED. ROADMAP + SESSION_HISTORY + CHANGELOG (version bump) +
  BACKLOG. New lessons. Memory backup. `git log origin/main..HEAD` empty. `/session-review`.

## Acceptance criteria (all must pass)
- [ ] DB ≤ 300 MB; current-state tables one-row-per-entity (constraint enforced).
- [ ] Atomic import: failed import leaves ZERO rows (test proves it).
- [ ] Import refused without verified R2 artifacts; `--skip-change-log` gone.
- [ ] Lossless R2 history: raw + snapshot + typed entity diff; reconstruct round-trips.
- [ ] Unwind works with three-way conflict detection (test proves it).
- [ ] "What's new" overview available from manifest summary + R2 diff (at least an API/
      script; thin admin UI optional).
- [ ] Latest reads need no version filtering; relationship/family pages fast.
- [ ] Both Codex audits (plan + impl) logged; P0/P1 resolved.
- [ ] Site live (post-upgrade), browser-verified; both test suites green.
- [ ] All technical debt removed (`_v2` tables, dual-read shim, dead scripts).

## Rules
- Browser automation READ-ONLY on production (Lesson 149).
- Snapshot-first before any destructive DB step (data-repair protocol; R2 is the unwind).
- Single-transaction imports only — no per-batch commits (Lesson 199).
- Don't over-build: rare admin batch job; simplest correct design wins.
