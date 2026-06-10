# Session 164 — Codex Audit of the IMPLEMENTATION (Phase 8, pre-migration)

**Auditor**: Codex CLI v0.139.0 (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context; read plan + all new code)
**Scope**: importer + R2 artifact layer + unwind + LIVE migration + schema + reader
**Date**: 2026-06-10
**Verdict**: **BLOCK** (pre-fix) → all P0/P1/P2/P3 resolved (commit `32264ef1`) → re-audit
**Value assessment**: **STRONG** — reproduced an executable unwind bug (`KeyError: 'old_payload'`),
caught the lossless-diff-base flaw, incomplete baseline artifact, and verify gaps. Run BEFORE the
destructive migration — exactly when it matters most.

## Why audit before executing
The Phase 8 audit was deliberately run BEFORE the live migration (not after, as the prompt orders),
because the migration irreversibly mutates 267 MB of production data. Codex returned BLOCK — proving
the value of auditing the migration script before running it.

## Findings (verbatim severity) → resolution (commit `32264ef1`)

| # | Finding | Resolution |
|---|---|---|
| P0-A | Going-forward diffs not lossless: old payloads from reduced DB columns; sources/media always diff vs empty | Importer diff base now = **previous applied version's R2 snapshot** (full lossless payloads, all 5 types) via `load_diff_base_maps` + `_latest_applied_artifact_prefix`. DB == prev snapshot (atomic), so equivalent but lossless. Test: re-import same bundle → 0 added/0 modified. |
| P0-B | v9 baseline artifact omits relationships + other types → not lossless | Baseline snapshot + diff now include individuals + families + **relationships** (all in canonical DB), streamed chunked. sources/media omitted w/ explicit `gedcom_versions.notes` provenance (preserved in raw.ged.gz + session-156 + v2 full backup). |
| P0-C | Migration `verify` never checks relationship count/edge-set or DB-size limit | `cmd_verify` adds relationship count>0 + near-expected + edge-set check, and a **HARD `pg_database_size > 300 MB → FAIL`** gate. |
| P0-D | Executed unwind broken: inverse entries lack `old_payload` → `KeyError`; no resulting snapshot but marks `v1` | `_add_inverse` emits old_payload/new_payload per change_type; executed unwind builds+uploads a resulting-state snapshot before marking `v1`. Reproduction now returns clean. Executed-unwind test added. |
| P0-E | Snapshot gate bypassable; schema.sql only column comments (not restorable) | `cmd_snapshot` emits real `CREATE TABLE` DDL (`_build_restorable_ddl`); `cmd_drop_v2` `head_object`s every manifest file + asserts current-individuals count == 21998 before DROP. |
| P1-A | Migration not community-scoped | `cmd_snapshot` asserts single community (rhodesli) or aborts; assumption documented. |
| P1-B | Relationship invariants nullable (NULL community bypasses unique index) | `cmd_populate` end-of-txn `SET NOT NULL` on relationships community_id/version_number/edge_key/payload_hash with a pre-check. |
| P1-C | Headroom not guarded | `cmd_populate` aborts if DB already > 350 MB; `cmd_drop_v2` warns on freed<=0 (idempotent). |
| P1-D | Unwind ref-check rejects same-unwind removals; sources/media treated absent | `compute_unwind_plan` takes a `removal_set`; current hashes/refs derived from reconstructed latest R2 snapshot. Added-family-graph rollback test. |
| P1-E | History reads omit community filter | `get_individual_history` filters `gedcom_versions` by community_id. |
| P2 | baseline diff_summary shape; dry-run vs empty; downloads unverified | 5-type IDs-inclusive `build_baseline_diff_summary` (pure, tested); dry-run/preview diff vs real current state when factories supplied; optional `expected_sha256` verify on downloads. |
| P3 | history silently returns partial timeline | `get_individual_history` appends `{"incomplete": true, "reason": ...}` on failure. |

**Nothing rejected.** 8 new tests added (executed unwind, R2 diff-base, migration summary).
Targeted suite 61 pass; fast gate 179 pass.

A focused **re-audit of the migration** was run after the fixes (verdict logged below) before
executing the live migration. See `session-164-codex-reaudit.md`.
