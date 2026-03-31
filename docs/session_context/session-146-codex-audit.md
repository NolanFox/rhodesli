**Auditor**: Codex CLI v0.117.0 (o4-mini)
**Agent type**: Independent (fresh context)
**Phase**: Phase 2 — PRD-059 Phase 4 Foundation
**Date**: 2026-03-31
**Scope**: scripts/compute_identity_suggestions.py, tests/test_identity_suggestions.py, scripts/sql/session_146_identity_suggestions.sql

## Findings

### P1: RLS policies too permissive — FIXED
- identity_suggestions_write used `USING(true) WITH CHECK(true)` — anyone with anon key could write
- **Fix**: Tightened to `auth.role() = 'service_role'` for writes, `authenticated` for reads
- Script now uses SUPABASE_SERVICE_ROLE_KEY for writes

### P2: Missing unique constraint for upsert — FIXED
- Script uses `on_conflict='target_identity_id,family_id'` but no unique constraint existed
- Repeat `--execute` runs would accumulate duplicate rows
- **Fix**: Added `UNIQUE (target_identity_id, family_id)` constraint

### P2: Non-hermetic Supabase test — NOTED
- `test_table_exists` hits live Supabase. Fails without network/credentials.
- Acceptable for this project (all tests run locally with .env). Not a CI concern yet.

### P3: Embedding loader test reimplements logic — NOTED
- Test doesn't call `load_embeddings()` directly. Acceptable risk for now — the dry-run validates the real path.

### P3: Import-time .env loading — NOTED
- Script mutates os.environ at import. Standard pattern for this project's batch scripts.

## Value Assessment: STRONG
- P1 RLS finding is a real security gap that would have shipped to production
- P2 upsert/unique constraint is a correctness issue that would cause duplicate rows
- Both fixed immediately
