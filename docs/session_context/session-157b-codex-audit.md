**Auditor**: Codex CLI v0.130.0 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context, no prior knowledge of session 156)
**Scope**: Session 156 commits — security, data-integrity, regression risk
**Date**: 2026-05-08
**Phase**: Session 157b Track A1.3
**Subagent**: Track A canary subagent #1 (Session 157b)

# Session 157b Codex Audit — Session 156 Commits

## Files in scope

- `app/supabase_data.py` — `shadow_write_identity` + `shadow_write_identities_batch` (notes embedded in metadata)
- `core/registry.py` — `load_from_postgres` (notes extracted from metadata), `add_note`
- `scripts/session156_harry_repair_snapshot.py`
- `scripts/session156_harry_repair_restore.py`
- `scripts/session156_harry_repair_execute.py`
- `scripts/session156_r2_backup_gedcom_sources.py`
- `scripts/session156_r2_backup_supabase_versions.py`
- `scripts/migrations/gedcom_v2_schema.sql`
- `scripts/session156_backfill_gedcom_v2.py`
- `scripts/session156_fix_detroit_locations.py`
- `tests/test_session156_notes_roundtrip.py`

## Audit prompt

Specifically check:

1. **Notes round-trip** — any path where top-level `identity['notes']` could leak past the embedding step? Any race condition where a concurrent write loses notes?
2. **Harry repair script** — any way the snapshot SHA256 verification could be bypassed? Any way the version_id check could pass on stale data?
3. **R2 backup scripts** — SQL injection risk in version_number filter? Path traversal in R2 key construction? Hardcoded secrets?
4. **v2 schema migration** — any column type narrowing that could lose data? UNIQUE constraint that could prevent legitimate inserts?
5. **Detroit fix** — audit_log row construction safe against JSON-injection in old_value/new_value?

---

## Findings

### P0
**None found.**

### P1

**P1-A — Harry repair preflight is not atomic**
- **File**: `scripts/session156_harry_repair_execute.py:90` (preflight read), with later writes at `:238` and `:242`.
- **Issue**: The script reads `version_id` + anchors, asserts they match snapshot, then later upserts the new identity and the detached Harry row unconditionally. A concurrent edit after the read can be overwritten while the version check has already "passed"; a failure between the new-identity insert and the Harry upsert leaves partial state.
- **Recommended fix**: Use a transactional RPC, or a conditional `UPDATE ... WHERE identity_id = HARRY_ID AND version_id = snapshot_version`, and insert the new identity only after that update returns exactly one row.
- **Impact for 157b**: This script already executed successfully in Session 156 (commit included). The race condition is no longer a live risk for THAT mutation, but the pattern needs hardening before any future similar repair script. **Logging as Track A1.3 BACKLOG note for next data-repair script (no in-flight risk).**

**P1-B — Note writes are last-writer-wins on `metadata` JSONB**
- **File**: `core/registry.py:2265` (`add_note`); `app/supabase_data.py:825` (`shadow_write_identities_batch`); `app/supabase_data.py:887` (full `metadata` overwrite).
- **Issue**: `add_note()` appends to `identity["notes"]` but does not bump `version_id`. Batch writes skip only when Postgres has a STRICTLY higher version, then replace the whole `metadata` JSONB. Concurrent note/metadata edits at the same `version_id` can silently lose one note list.
- **Recommended fix**: Either (a) `add_note()` must bump `version_id`, or (b) note writes must use a JSONB-merge SQL update (`metadata = metadata || jsonb_build_object('notes', $new)`) instead of full overwrite.
- **Impact for 157b**: This is the SAME failure pattern as Lesson 179 (notes silently dropped) but at a finer granularity — concurrent writes during the same TTL window. Not blocking 157b deliverables, but should be fixed before high-concurrency note workflows. **Logging as new BACKLOG item for Session 158 / next data-integrity sprint.**

### P2

**P2-A — Snapshot SHA256 is self-attested**
- **File**: `scripts/session156_harry_repair_execute.py:75`, `scripts/session156_harry_repair_restore.py:40`.
- **Issue**: The snapshot file embeds its own `_meta.payload_sha256`. Anyone who edits the snapshot payload can also recompute `_meta.payload_sha256`, so the verification check is bypassable.
- **Recommended fix**: Store the expected hash out-of-band — committed to git in a separate file, or pass via CLI argument from the orchestrating session log.
- **Impact for 157b**: The Session 156 snapshot is already committed to git, so its hash is implicitly out-of-band via git history. Future repair scripts should make this explicit. **Logging note in BACKLOG for repair-script template.**

**P2-B — `UNIQUE (payload_hash)` is global despite `community_id`**
- **File**: `scripts/migrations/gedcom_v2_schema.sql:62`, `:107`.
- **Issue**: Identical GEDCOM payloads uploaded by different communities will conflict on `payload_hash`. The backfill uses `ON CONFLICT (payload_hash) DO NOTHING`, which would silently drop the second community's row.
- **Recommended fix**: Make the unique key composite: `UNIQUE (community_id, payload_hash)`.
- **Impact for 157b**: PRD-063 v2 backfill already ran with the global unique constraint and produced expected counts. If multiple communities later upload identical GEDCOMs, this becomes a real bug. **Adding to BACKLOG for PRD-063 Day 2/3 schema review.**

### P3

**P3-A — Raw `--prefix` interpolated into R2 keys**
- **File**: `scripts/session156_r2_backup_gedcom_sources.py:63`.
- **Issue**: User-supplied `--prefix` is interpolated into R2 object keys. Not filesystem traversal, but allows R2 namespace escape/misplacement.
- **Recommended fix**: Validate `--prefix` against a regex (e.g., `^[a-zA-Z0-9_./-]+$`) and reject `..` segments.
- **Impact for 157b**: Script is admin-only and operator-supplied prefixes are trusted. Low priority. **Note only.**

### No finding

- Scoped shadow writes do not send top-level `notes` (the `notes` key is not in the row dict; only `metadata` is, with notes pre-embedded).
- R2 SQL filters use constants/parameters; secrets come from environment variables (no hardcoded credentials).
- Detroit fix's `old_value`/`new_value` are constructed with `json.dumps`, so JSON injection is not present.

---

## Surfaced for orchestrator (157b parent agent)

**P0**: 0
**P1**: 2 (both deferrable — no in-flight risk to current 157b deliverables, but require BACKLOG entries)
**P2**: 2 (1 schema review for PRD-063 Day 2, 1 repair-script template note)
**P3**: 1 (low-priority validation hardening)

**No Track A1.3 in-session fix required** — all findings are forward-looking hardening for future data-repair scripts and the PRD-063 Day 2 schema review. Adding BACKLOG items recommended.

---

## Codex invocation log

```
codex exec "..." </dev/null
```

- CLI version: `codex-cli 0.130.0`
- Model: `gpt-5.5`
- Reasoning effort: `xhigh`
- Pin source: `~/.codex/config.toml` (verified before run)
- Tokens used: 124,861
- Wall-clock: ~5 minutes
- Result: success (no stdin hang, no truncation)

The `</dev/null` form (per Lesson 173 / Session 155 diagnosis) worked on first try with codex-cli 0.130.0. No fallback to Claude subagent needed.
