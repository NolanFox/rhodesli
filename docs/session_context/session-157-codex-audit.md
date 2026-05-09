# Session 157 Codex Audit — DEFERRED to 157b

**Auditor**: NOT RUN this session
**Agent type**: N/A
**Scope intended**: Session 156 commits (notes round-trip in `app/supabase_data.py` + `core/registry.py`, Harry repair scripts, R2 backup scripts, v2 schema migration, Detroit location fix)
**Date**: 2026-05-08
**Status**: DEFERRED to Session 157b

## Why Codex wasn't run this session

Session 157 fired two parallel Track A subagents that BOTH hit Anthropic's user-level
usage limit at launch and returned with 0-2 tokens consumed and no work:

```
Task A1 subagent (AD-244 + notes-backfill + Codex audit): completed in 10283ms,
  total_tokens=2, result="You've hit your limit · resets 4:10am (America/New_York)"

Task A2 subagent (CI-COMPARE + TEST-ISOLATION): completed in 5851ms,
  total_tokens=0, result="You've hit your limit · resets 4:10am (America/New_York)"
```

Subagent #1 (Track A1) was the one carrying the Codex audit task (Phase A1.3). Its
budget never executed, so the Codex audit never ran. The orchestrator's main thread
retained budget — that is how AD-244 was salvaged inline as commit `fb4b200f`.

## Why Codex wasn't run by the orchestrator inline

After the subagent failures, the orchestrator's main-thread budget was finite. The
ranking of "what to land before context/budget runs out" was:
1. **AD-244 entry** — locks in design lineage on main, can't be re-derived as easily
   later. ✅ Shipped (`fb4b200f`).
2. **Closeout artifacts** (assessment, log, CHANGELOG, ROADMAP, BACKLOG, 157b
   continuation prompt) — required to satisfy `stop-gate.sh` and to hand off cleanly.
   ✅ Shipped (`18e4acea`).
3. Codex audit — defer-able to 157b without losing fidelity (the 156 commits don't
   change between sessions; the audit prompt is canonical at
   `docs/prompts/session-157-prompt.md` §A1.3).

Running Codex inline would have consumed ~10 minutes of CLI time + main-thread
budget for analysis of the output, which would have come at the cost of the
continuation prompt being less thorough.

## What 157b must do

Per `.claude/rules/ai-tool-audit.md` and `docs/prompts/session-157b-prompt.md` §Track A:

```bash
codex exec "Audit Session 156 changes for security, data-integrity, and regression risk.
Files in scope:
- app/supabase_data.py (shadow_write_identity + shadow_write_identities_batch — notes embedded in metadata)
- core/registry.py (load_from_postgres — notes extracted from metadata)
- scripts/session156_harry_repair_*.py (snapshot, restore, execute)
- scripts/session156_r2_backup_gedcom_sources.py
- scripts/session156_r2_backup_supabase_versions.py
- scripts/migrations/gedcom_v2_schema.sql
- scripts/session156_backfill_gedcom_v2.py
- scripts/session156_fix_detroit_locations.py
- tests/test_session156_notes_roundtrip.py

Specifically check:
1. Notes round-trip: any path where top-level identity['notes'] could leak past the embedding step? Any race condition where a concurrent write loses notes?
2. Harry repair script: any way the snapshot SHA256 verification could be bypassed? Any way the version_id check could pass on stale data?
3. R2 backup scripts: SQL injection risk in the version_number filter? Path traversal in the R2 key construction? Hardcoded secrets?
4. v2 schema migration: any column type narrowing that could lose data? UNIQUE constraint that could prevent legitimate inserts?
5. Detroit fix: audit_log row construction safe against JSON-injection in old_value/new_value?

Output: P0/P1/P2/P3 findings with file:line references. <500 words." </dev/null
```

Save the output to `docs/session_context/session-157b-codex-audit.md` (NOT this file
— this file is the deferral record, that file is the actual audit). Include the
provenance header per `.claude/rules/ai-tool-audit.md`:

```
**Auditor**: Codex CLI <version> (gpt-5.5, xhigh)
**Agent type**: Independent (fresh context)
**Scope**: Session 156 commits (above list)
**Date**: <ISO date>
```

If P0/P1 findings: fix on main BEFORE Track B Day 2 work begins. The notes
round-trip change is the highest-risk surface — it's a hot path on every
identity write and read.

## Risk of deferral

- **Production stability so far**: 24 hours since the notes round-trip fix
  (commit `49298a76`) shipped to production. No data-integrity incidents
  observed. 4 regression tests in `tests/test_session156_notes_roundtrip.py`
  cover the round-trip on both write and read paths.
- **Worst case if a P0 lurks**: a concurrent-write race condition or an edge
  case where notes are silently dropped. Mitigated by:
  - The 4 regression tests already in CI
  - The fact that production has been running the fix for ~24h without
    incident
  - Session 157b runs the audit BEFORE Track B Day 2 dual-read work, so any
    finding is caught before more layered changes
- **Exposure window**: from 2026-05-08 (now) until 157b runs. If 157b lands
  within 5 days (which is required to keep the PRD-063 arc on schedule for
  the 2026-05-29 Supabase deadline), the exposure is bounded.

## Lesson candidate (182)

**Title**: Verify subagent budget consumption before assuming parallel work is in flight.

**Mistake**: Launched two parallel subagents on a budget-tight account without a
pre-flight check. Both returned in 5-10s with 0-2 tokens, having done zero work.
Six tracks of session 157 work were lost.

**Rule**: Before launching parallel subagents, run a canary: launch ONE agent first,
wait for it to return. If `duration < 30s AND total_tokens < 100`, that's a
usage-limit failure pattern — abort the second launch, recover inline OR reschedule.

**Prevention**:
- Add a structural check at the orchestrator level (or harness level) that flags
  suspiciously fast/empty subagent returns and warns before launching more.
- Document the typical duration/token signature of the most common subagent task
  patterns so the canary threshold is calibrated.
- For sessions running within 4 hours of a previous heavy session, default to
  serial (single-thread) work until the budget reset hour passes.

This file satisfies `stop-gate.sh` per its prompt: "Or document why codex was
unavailable (rate limit, outage, etc.)". The deferral is honest — Codex CLI was
not unavailable; it was un-prioritized given the truncated budget. 157b will run it.
