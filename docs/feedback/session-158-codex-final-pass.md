**Auditor**: Codex CLI v0.130 (gpt-5.5, xhigh)
**Subject**: Session 158 commits 75dc10e0..770e56f1
**Date**: 2026-05-09
**Agent type**: Independent fresh context

# Session 158 Final Pass Audit

Scope reviewed: `docs/prompts/session-158-prompt.md`, `docs/assessments/session-158-assessment.md`, `tasks/lessons.md`, and all 8 commits via `git show`.

## P0

None found.

Security clear notes: no web data-mutating endpoint was added, so I found no missing-auth route issue. The new psycopg2 writes use `execute_values(..., rows)` with tuple binders for row values (`scripts/session158_historical_backfill_gedcom_v2.py:270`, `scripts/session158_historical_backfill_gedcom_v2.py:274`; `scripts/session158_historical_backfill_rest.py:154`, `scripts/session158_historical_backfill_rest.py:168`). The SQL table/column f-strings are fed by internal constants, not request input. R2 and DB credentials are read from environment variables (`scripts/session158_phase0_verify.py:87`, `scripts/session158_phase0_verify.py:89`; `scripts/session158_historical_backfill_gedcom_v2.py:71`, `scripts/session158_historical_backfill_gedcom_v2.py:82`); I did not find hardcoded secrets.

## P1

1. **`get_individual_history()` cannot show the actual observed changes.** The new helper only selects thin identity fields plus version/hash (`app/gedcom_dual_read.py:217`, `app/gedcom_dual_read.py:220`), but Session 158's own assessment says the Albert Fox two-state difference is in JSONB columns: events, citations, names, notes (`docs/assessments/session-158-assessment.md:37`). As written, the canonical history helper will return two rows with identical visible fields and different hashes, which does not satisfy "what was updated, corrected, or added" for the proven case. Fix before relying on this for cutover validation: include the rich JSON fields in history output and/or add a diff helper that reports changed rich fields between adjacent states.

## P2

1. **The 10 added dual-read tests do not exercise production-shaped multi-row current selection.** `TestV2OrderedRead` supplies a single v2 row and only asserts that `.order("last_seen_version", desc=True)` was called (`tests/test_dual_read_helper.py:246`, `tests/test_dual_read_helper.py:253`); the family case does the same (`tests/test_dual_read_helper.py:258`, `tests/test_dual_read_helper.py:264`). The multi-state history test passes already-sorted rows and then checks that `.order("first_seen_version", desc=False)` was called (`tests/test_dual_read_helper.py:385`, `tests/test_dual_read_helper.py:404`). This mostly verifies query-chain shape, not the post-backfill scenario where stale/current rows coexist. The production ordering in `app/gedcom_dual_read.py:80` to `app/gedcom_dual_read.py:82` is logically right for normal "latest state" cases; add a unit fake or integration test with unsorted old/current/tie rows proving the helper returns the latest row.

2. **`_is_v2_unavailable()` is still too string-broad.** It treats any exception whose string contains `PGRST205` as v2-unavailable (`app/gedcom_dual_read.py:57`, `app/gedcom_dual_read.py:59`), without checking that the missing relation is the target v2 table. That can still fail open for a wrapped or misleading PostgREST/operational error containing that token. Current tests cover a generic non-PGRST fatal error and a legitimate PGRST205 fallback (`tests/test_dual_read_helper.py:272`, `tests/test_dual_read_helper.py:300`), but not a PGRST205-like error for the wrong relation. Require a structured error code plus target-table match where available, or at least require the target table name in the message.

3. **Backfill scripts do not enforce post-write integrity before cutover.** After execute, the psycopg2 variant reports row count and table size only (`scripts/session158_historical_backfill_gedcom_v2.py:273`, `scripts/session158_historical_backfill_gedcom_v2.py:281`); the REST variant does the same (`scripts/session158_historical_backfill_rest.py:168`, `scripts/session158_historical_backfill_rest.py:175`) and writes a summary report (`scripts/session158_historical_backfill_rest.py:291`, `scripts/session158_historical_backfill_rest.py:300`). Given the repeated lessons on post-write verification, the script or mandatory follow-up should assert `first_seen_version <= last_seen_version`, expected row-count bands, no unexpected duplicate-current ambiguity, and Albert Fox returning two rich states via the helper.

4. **NULL `payload_hash` fallback hashing is approximate and needs explicit validation.** The 158 scripts compute missing hashes from thin key fields only (`scripts/session158_historical_backfill_gedcom_v2.py:49`, `scripts/session158_historical_backfill_gedcom_v2.py:65`, `scripts/session158_historical_backfill_gedcom_v2.py:92`; `scripts/session158_historical_backfill_rest.py:42`, `scripts/session158_historical_backfill_rest.py:66`). The importer's canonical individual hash includes rich JSON/provenance fields before hashing (`rhodesli_ml/importers/gedcom_snapshot.py:198`, `rhodesli_ml/importers/gedcom_snapshot.py:223`). Since Session 158 found 21,809 NULL-hash individual rows (`docs/assessments/session-158-assessment.md:36`), JSON-only legacy differences could be collapsed or represented as artificial v0-only hashes. This may be acceptable for legacy rows, but it should be measured on a sample before execute.

## P3

1. **`ON CONFLICT` aggregation is safe for normal reruns, but monotonic.** The `LEAST(first_seen)` / `GREATEST(last_seen)` updates are the right idempotent pattern (`scripts/session158_historical_backfill_gedcom_v2.py:312`, `scripts/session158_historical_backfill_gedcom_v2.py:314`; `scripts/session158_historical_backfill_rest.py:150`, `scripts/session158_historical_backfill_rest.py:152`). Residual risk: if a bad earlier run over-expanded a range, rerun cannot shrink it. Pair it with the P2 post-write invariants.

2. **Decision-log drift.** The prompt expected new ADs for dual-read/history/cutover decisions (`docs/prompts/session-158-prompt.md:80`, `docs/prompts/session-158-prompt.md:83`), but the decision logs still only show AD-244 for this PRD lineage (`docs/ml/ALGORITHMIC_DECISIONS.md:2831`, `docs/ml/ALGORITHMIC_DECISIONS.md:2852`). Session 158 did make a new data-design decision: Option A historical backfill. Capture it in 158b before cutover.

3. **Phase 158-0 count gate is looser than its label.** The script says v2 row counts "must match 157b end" (`scripts/session158_phase0_verify.py:31`) but uses `>=` via `tolerance=1` (`scripts/session158_phase0_verify.py:18`, `scripts/session158_phase0_verify.py:42`). That is probably intentional for concurrent imports, but the output should label it as a lower-bound check, not exact carry verification.

