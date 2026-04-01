# Session 147 Pre-Implementation Codex Audit

**Auditor**: Codex CLI v0.117.0 (gpt-5.4)
**Agent type**: Independent (fresh context)
**Scope**: Session 147 plan — prompt, context, batch script, admin routes, SQL migration
**Date**: 2026-04-01
**Tokens used**: 490,724

---

## P0 — Review decisions not durable across batch reruns
The `--execute` upsert overwrites all rows with `status="PENDING"`, destroying REJECTED/NEEDS_MORE/ACCEPTED states. Batch reruns would resurrect rejected suggestions, violating "prevent re-suggestion" behavior.
**Fix**: Query existing reviewed rows before upsert, skip any with non-PENDING status. Add `test_rerun_preserves_reviewed_status()`.
**Refs**: compute_identity_suggestions.py:535, prompt Phase 1e

## P1 — Accept ignores suggested_identity_id merge case
The table has `suggested_identity_id` for pointing to existing confirmed people, but the plan always renames/confirms the target in place. When `suggested_identity_id` is set, accept should MERGE into the confirmed identity, not rename.
**Fix**: Branch on `suggested_identity_id` — NULL → rename+confirm, non-NULL → merge_identities().
**Refs**: session_146_identity_suggestions.sql:8, registry.py:880/1166

## P1 — GEDCOM link writes to wrong data surface
`set_metadata({"gedcom_id": ...})` does not accept `gedcom_id`. Canonical GEDCOM links are stored via `gedcom_face_links` through the existing link flow in `relationship_routes.py:1293`.
**Fix**: Use existing GEDCOM link function or write directly to `gedcom_face_links` table.

## P1 — CSRF internally inconsistent
Sample calls `_check_origin(request)` but doesn't declare `request` in signature. ML review pattern endpoints currently omit origin checks.
**Fix**: Add `request` to function signature. Add `_check_origin` to all three new endpoints.

## P2 — Row model mismatch across tracks
Phase 1 scores "is this person a Fox family member?" while Phases 2/3 assume specific named suggestions. UNIQUE(target_identity_id, family_id) allows only 1 row per person per family, so "top 3 suggestions" is impossible.
**Fix**: UI shows 1 suggestion card, not a list. Remove `.limit(3)`.

## P2 — Verification too thin
Plan only runs `make test-fast` but project requires both app and ML test suites.
**Fix**: Run `make test-full` or `make test-fast && make test-ml`.

## P2 — Missing high-risk test paths
Tests mostly cover happy-path rendering. Missing: rerun idempotency, stale merged/confirmed targets, suggested_identity_id merge branch, GEDCOM link persistence, person-page Supabase read failure.
**Fix**: Add 4-5 additional tests covering these paths.

## P3 — Helper function names don't exist
`_main_mod._get_supabase_client()` and `_main_mod._load_full_registry()` are not in the codebase.
**Fix**: Grep for actual function names and use those.

## P3 — Hardcoded testimony needs provenance
Hardcoded constants are fine as stopgap but should include source/session provenance in payloads and a migration test.

---

## Disposition

| Finding | Severity | Action |
|---------|----------|--------|
| Batch rerun idempotency | P0 | ACCEPT — added to Phase 1e, new test |
| Accept merge case | P1 | ACCEPT — rewritten in Phase 3a |
| GEDCOM link surface | P1 | ACCEPT — corrected in Phase 3a |
| CSRF request param | P1 | ACCEPT — noted in Phase 3a |
| Row model / UI mismatch | P2 | ACCEPT — fixed Phase 2a to single card |
| Verification thin | P2 | ACCEPT — added make test-ml to Phase 4a |
| Missing tests | P2 | ACCEPT — 3 new tests added to Phase 3 |
| Helper names | P3 | ACCEPT — noted as grep instruction |
| Testimony provenance | P3 | ACCEPT — noted as TODO in Phase 1c |
