# Session 158 Prompt — Critical Review (during 157b /session-review pass 2)

**Reviewer**: Claude Opus 4.7 (rhodesli-157-b session, /session-review skill pass 2)
**Subject**: `docs/prompts/session-158-prompt.md` (commit `ded637a2`)
**Date**: 2026-05-09
**Status**: 3 high-value safety edits applied inline (commit pending). 9 lower-priority notes captured here for the 158 implementer to consider during execution.

## Edits applied to the prompt

### EDIT-1 — User authorization gate before Phase 158-6 DROP (HIGH SAFETY VALUE)

The original prompt auto-progressed from Phase 158-5 (wait + re-verify) to Phase 158-6 (DROP + VACUUM FULL) on a "clean" state. Since DROP is the irreversibility threshold and the user explicitly asked to "be really careful not to lose data", added Phase 158-6.0 as a mandatory `AskUserQuestion` gate offering PROCEED / HOLD / ROLLBACK. HOLD lets the session pause in the renamed state for 24h+ and resume via 158b — preserving an extra day of reversibility.

### EDIT-2 — Tiebreaker order in `current_gedcom_individuals_v2` view (CORRECTNESS)

Original `ORDER BY gedcom_id, last_seen_version DESC, payload_hash` was non-deterministic when two rows for the same gedcom_id share `last_seen_version` (e.g., both last seen at v9). Added `first_seen_version DESC` as a second tiebreaker so the view always returns the most recently introduced state.

### EDIT-3 — Date placeholder in R2 prefix (CLERICAL)

`gedcom-pre-drop-snapshots/2026-05-DD-session-158/` had a literal "DD" placeholder. Replaced with `$(date -u +%Y-%m-%d)-session-158/` so the script computes it at run time.

## Lower-priority notes (NOT applied — surfaced for the 158 implementer)

### NOTE-1 — Albert Fox xref placeholder

Phase 158-1 uses `'@I143@'`, `'@I_ESTHER@'`, `'@I_REVA@'` as placeholder gedcom_ids. The actual xrefs need to be resolved at session start via:

```sql
SELECT gedcom_id, name, surname FROM gedcom_individuals
WHERE surname IN ('Fox', 'Burd', 'Heft') AND given_name IN ('Albert', 'Esther', 'Reva')
  AND is_current = TRUE
ORDER BY surname, given_name;
```

Pick three from the result. Albert Fox should have multiple historical states (Detroit/NYC corrections); Reva Heft should show the relationship correction (originally Irving's wife → corrected to Meyer's wife in Session 152).

### NOTE-2 — Phase 158-2 row count threshold

Prompt says "If unique payload_hash count > 100K: STOP." The threshold is reasonable but somewhat arbitrary. A better heuristic: the post-backfill v2 row count should be **strictly less than v1's total row count** (currently ~196K) AND **at least equal to the current v2 row count** (22K). If outside this range, investigate.

```python
v1_total = supabase.table("gedcom_individuals").select("*", count="exact").limit(1).execute().count
v2_current = supabase.table("gedcom_individuals_v2").select("*", count="exact").limit(1).execute().count
# After backfill:
expected_lower_bound = v2_current  # at minimum, didn't lose anything
expected_upper_bound = v1_total     # at maximum, every row was unique (no dedup)
# Reasonable observed range based on dedup factor 156 saw on individuals (8.94×):
# (v2_current * 1.0) up to (v1_total * 0.3) ≈ 22K to 60K
```

### NOTE-3 — Phase 158-2 ON CONFLICT update logic

Prompt's pseudocode: "UPDATE first_seen_version where the existing row's first_seen_version > computed min." The SQL needs to be careful — `ON CONFLICT (payload_hash) DO UPDATE SET first_seen_version = LEAST(EXCLUDED.first_seen_version, gedcom_individuals_v2.first_seen_version), last_seen_version = GREATEST(...)` is the correct pattern. The 156 backfill script uses `ON CONFLICT DO NOTHING` plus a separate UPDATE pass. Either works; the implementer should pick one and verify the version-range invariant holds post-backfill.

### NOTE-4 — VACUUM FULL downtime expectation

Phase 158-6 runs `VACUUM FULL` on 7 tables. At ~22K rows for individuals, ~6K for families, this is fast (each table <1s typically). But Supabase's pooler may impose stricter locking semantics than a direct connection. Consider running `VACUUM (FULL, VERBOSE)` to capture timing per table. Add a `time` wrapper to capture wall-clock for the closeout report.

### NOTE-5 — Track E v2 importer split-write (events vs individuals)

Phase 158-8 path B builds a v2 importer. The prompt mentions: "the new v2 importer (Path B) writes to v2 individuals/families AND v1 events/relationships/records — that's a split write." Worth noting: a split-write importer may end up partially-applied if it crashes between the v2 INSERT and the v1 INSERT. Wrap the entire upload in a single transaction (or use a saga pattern with explicit rollback).

### NOTE-6 — Codex final-pass audit timing

Track Z step 12 says "MANDATORY this session" but the audit runs AFTER all phases including DROP. The audit reviews COMMITTED CODE — it cannot UNDO the DROP. Still useful for catching anything missed, but the user should know: the audit is a forward-looking gate for future work, not a rollback trigger. If the audit surfaces a P0/P1 in the cutover code, that's a 158b hotfix, not a 158 rollback.

A separate Codex audit BETWEEN Phase 158-4 (RENAME) and Phase 158-6 (DROP) would catch issues while still in the reversible RENAME state. Worth considering as a Phase 158-5.5 add-on. The implementer can choose.

### NOTE-7 — Bulk loader cache invalidation post-cutover

Phase 158-4.1 rewires `_load_gedcom_individuals` to read from `current_gedcom_individuals_v2`. The TTL cache (`_gedcom_individuals_cache`) needs explicit invalidation post-cutover so production reads pick up the new view immediately rather than waiting for TTL expiry (300s).

```python
# Post-cutover, force-invalidate via the existing helper
import app.relationship_routes as rr
rr._invalidate_gedcom_cache()
```

Or hit the admin endpoint `/api/admin/gedcom-cache-invalidate` if one exists. Add to Phase 158-4.3 smoke section.

### NOTE-8 — Migration script idempotency

Phase 158-4.1 SQL migration (`scripts/migrations/session158_current_v2_view.sql`) should be safe to re-run. The current draft uses `CREATE OR REPLACE VIEW` which is idempotent. Good.

Phase 158-2 historical backfill should also be idempotent (re-running on already-backfilled v2 = no-op). The 156 backfill achieves this via `ON CONFLICT (payload_hash) DO NOTHING`. Phase 158-2 should adopt the same pattern.

### NOTE-9 — gedcom_change_log signal preservation

Phase 158-6 DROPs `gedcom_change_log` (1.65M rows). Most of these are noise (re-imports of unchanged rows). But there may be a small subset of HIGH-SIGNAL rows — e.g., rows where `old_value != new_value` for a specific person.

Before DROP, consider: write a one-shot script that extracts the high-signal rows (where actual cell-level changes happened) and archives them as a JSON file in R2 at `gedcom-change-log-signal/2026-05-DD-session-158/`. Storage cost: probably <10 MB compressed. Benefit: per-cell change history is queryable in addition to the per-row history that v2 supports natively.

This is OPTIONAL — change-history queryability via v2's `first_seen_version`/`last_seen_version` already gives you "what changed for this person between versions". The change_log adds "WHO made the change" provenance which Rhodesli's use case (single-user GEDCOM editor) doesn't strictly need.

## Verdict

The 158 prompt is well-structured for safety. The 3 applied edits add explicit user authorization for the irreversible step, fix a determinism bug in the bulk view, and correct a clerical placeholder. The 9 lower-priority notes are implementation refinements that the future-session implementer can decide on at run time.

**Overall**: prompt is APPROVED for clean-session execution after the 3 edits. The user has plenty of safety nets (R2 archive, fresh pg_dump, rename-not-drop, wait period, user-auth gate, codex audit). The biggest risk remaining is **Phase 158-2 historical backfill correctness** — the SQL aggregation logic must be carefully tested on a small subset before running on the full 196K-row v1 dataset. Phase 158-1's change-history reality check provides the test corpus.

## Auto-Fix Summary

- Issues found: 12 total (3 high-value, 9 lower-priority)
- Auto-fixed inline (prompt edits): 3
- Captured in this review for the 158 implementer: 9
- Auto-fix subagent NOT spawned: the work is small enough to do inline, and a subagent would re-introduce Lesson 180 worktree-isolation risk on prompt files
