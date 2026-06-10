# Session 164 Log — GEDCOM Storage Redesign (PRD-064 Option B-plus)

Started: 2026-06-09
Prompt: docs/prompts/session-164-prompt.md
Context: docs/session_context/session-164-context.md
Plan: docs/session_context/session-164-implementation-plan.md

## Phase Checklist
- [x] Phase 0: Orient & verify inherited state
- [x] Phase 1: Implementation plan + Codex audit of plan (6 P0 + 8 P1, STRONG)
- [x] Phase 2: Artifact schema + R2 layer (gedcom_history.py, 14 tests)
- [x] Phase 3: Current-state schema + tiny manifest (session164_canonical_schema.sql)
- [x] Phase 4: Atomic importer rewrite (single txn; real-PG atomicity proven)
- [x] Phase 5: Reconstruction + conflict-checked unwind
- [x] Phase 6: Migrate + delete technical debt (DB 423→244 MB, verify OVERALL PASS)
- [x] Phase 7: Tests (8 new + live atomicity probe; 1014 targeted pass)
- [x] Phase 8: Post-implementation Codex audit (BLOCK → all fixed → re-audit SAFE)
- [ ] Phase 9: Restore service + browser verify (USER GATE: Pro upgrade — pending)
- [x] Phase 10: Document + closeout (GEDCOM_HISTORY.md, AD-247–250, lessons 202–204)

## Migration execution (Phase 6, live)
- drop-v2: 423 MB → 130 MB (freed 294 MB); manifest verified (6 files, 21998 indiv) first.
- create-schema: canonical gedcom_individuals/families created (composite PKs).
- populate: 21,998 individuals + 6,741 families inserted; 140,796 relationships augmented
  (community_id+version_number), is_current/version_id/superseded_by dropped, NOT NULL set. COMMIT.
- backfill-artifacts: v9 R2 history at gedcom-history/rhodesli/v0009-f77859a8ca32/
  (raw 2.2MB + snapshot 14MB + diff 14MB, re-download sha256 verified); 8 versions → legacy.
- verify: OVERALL PASS — count==distinct, complete id→hash map == R2 extract (0 diff), DB 244 MB ≤ 300.
- Real-PG atomicity probe: PASS (forced mid-apply failure left ZERO rows; versions/counts unchanged).

## Test status
- New GEDCOM suites: 61 pass (history/import/unwind/dual-read/migration-summary).
- Targeted regression (gedcom/relationship/admin/import/migration/postgres/supabase): 1014 passed.
- 2 pre-existing stale failures (test_supabase_data.py identity_overrides — removed Session 130, unrelated).
- 5 e2e errors (need live server). No Session-164 regressions.

## Pending (Phase 9 — user)
Site DOWN until Pro upgrade lifts the 402 Fair-Use restriction. After upgrade: confirm REST 200 +
/health supabase ok + browser-verify (esp. relationship/family pages). Then push deploy health check.

## Phase 0 — Orient (DONE)
- DB **423 MB** (pooler + Mgmt-API both work under 402 restriction).
- `gedcom_individuals_v2`: 267 MB, 43,172 rows, 21,998 distinct (1-state×824, 2-state×21,174).
- `gedcom_families_v2`: 13,158 rows, 6,741 distinct.
- `gedcom_relationships`: 140,796 rows — ALREADY current-only (all is_current=true).
- `gedcom_versions`: 9 rows; only v7 (1e0d) + v9 (f778) applied; 7 failed retries (bloat source).
- v1 `gedcom_individuals`/`gedcom_families` tables GONE (158e dropped) → dual_read v1 path dead.
- R2 snapshots intact: session-163 cleanup + session-156 version/source.
- `SUPABASE_ACCESS_TOKEN` present. Site restricted (402, expected — down pending Pro upgrade).
- Baseline `make test-fast`: green except 1 expected `402 exceed_db_size_quota` live-REST test
  (`test_identity_suggestions.py::test_table_exists`). Pre-commit gate (5-file subset) = 179 passed.

## Phase 1 — Plan (DONE)
- Wrote `docs/session_context/session-164-implementation-plan.md` (schema DDL, R2 artifact
  spec, atomic importer flow, reconstruct/unwind, migration, test list).
- Codex audit of the PLAN: see session-164-codex-audit-plan.md.
