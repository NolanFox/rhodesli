# Session 142 Codex Audit Round 2 — GEDCOM Preload + Backfill

**Auditor**: Codex CLI v0.115.0 (gpt-5.4)
**Agent type**: Independent (fresh context)
**Phase**: GEDCOM preload + backfill audit
**Date**: 2026-03-27

**Note**: Codex completed its investigation (read both scripts, traced GEDCOM preload path,
validated source data for duplicates, checked column schemas) but was truncated before
producing a ranked report. Findings below are synthesized from Codex's raw investigation
steps combined with Claude Code review of the same scripts.

---

## Scripts Audited
1. `scripts/batch_gemini_for_person.py` — Batch Gemini date estimation (736 lines)
2. `scripts/backfill_gemini_logs.py` — Audit log backfill to Supabase (209 lines)

---

## Data Safety: Does Backfill Create Duplicates?

**Codex validated**: 82 batch entries in `date_labels.json`, 82 unique photo_ids, 0 duplicates.

**Backfill dedup mechanism** (lines 157-168 of backfill script):
- Queries existing rows WHERE `batch_id = 'session_142_esther_albert_backfill'`
- Filters out already-inserted photo_ids
- This is **correct** for idempotent re-runs of the same backfill

**P2: Dedup is batch_id-scoped, not photo_id-scoped globally**
The backfill checks for duplicates only within `batch_id = 'session_142_esther_albert_backfill'`.
If the same photo_id was already logged via a different batch_id (e.g., from the live
`log_gemini_call()` path or a future batch), the backfill would create a second row.
In practice this is acceptable because: (a) the original `log_gemini_call()` failed for
all 82 photos (that's why the backfill exists), and (b) `gemini_api_calls` is an append-only
audit log where multiple calls to the same photo are expected. Not a bug, but worth noting.

---

## Performance: GEDCOM Preload

**P0 fix verified correct** (lines 296-341 of batch script):
- `load_gedcom_data()` called ONCE at startup (was per-photo before Session 142 Codex audit)
- Identity registry paginated from Supabase ONCE (1000-row pages)
- `_face_to_identity` reverse map built ONCE
- `_get_cached_gedcom_context()` caches per photo_id via `_gedcom_cache` dict
- `build_gedcom_context()` called with pre-loaded data, no Supabase per call

**Assessment**: GEDCOM preload is correctly implemented. The pre-Session-142 pattern
would have made ~82 Supabase round-trips for GEDCOM data; now it makes 1.

**P3: Supabase client created multiple times**
Lines 63-64 and 104-106 both call `create_client(url, key)` independently.
Then lines 313-318 create yet another client. Each `create_client()` is cheap
(no connection pool), but could be consolidated for clarity.

---

## Error Handling

**Batch script**:
- **Good**: Retry logic with exponential backoff for 503/504/timeout (lines 460-522)
- **Good**: `finally` block ensures Supabase logging even on failure (line 523)
- **Good**: Incremental save every 10 photos (line 698)
- **Good**: Graceful fallback from Supabase to local JSON for identity reads (line 86)

**P2: Logging failure in `finally` block is swallowed silently**
Line 579: `except Exception as log_err: logger.warning(...)` — this is exactly what
happened in the original run (prompt manifest columns missing). The warning was logged
but processing continued. This is actually the correct behavior for an audit log
(don't fail the batch because logging failed), but the warning message should include
the column name or Supabase error detail so the operator can fix the schema.

**P2: `_call_gemini_full` returns None for both "empty response" and "API error"**
Lines 490-492 and 504: both return None. The caller (line 640) treats all None returns
the same way. The `status` variable is set correctly in the `finally` block for
Supabase logging, but the caller cannot distinguish "Gemini returned empty" from
"validation failed" from "network error." Not a data safety issue since all failures
are logged, but limits operational debugging.

**Backfill script**:
- **Good**: Individual row fallback when batch insert fails (lines 186-193)
- **Good**: Post-insert verification count (lines 198-204)

**P2: No `cost_usd` column populated in backfill**
The backfill `build_row()` function (lines 116-140) does not include `cost_usd`.
The batch script does compute and log cost. This means backfilled rows will have
NULL cost, making cost aggregation queries incomplete. Could be added trivially
from the estimated token counts.

---

## Supabase Query Efficiency

**Batch script**:
- **Good**: `photo_faces` paginated correctly (lines 108-117, 1000-row pages)
- **Good**: Identity preload paginated (lines 321-338)
- **Good**: Selective columns: `.select("identity_id, name, anchor_ids, candidate_ids")`

**P3: `photo_faces` loads ALL rows, not just for target identities**
Lines 108-117 load the entire `photo_faces` table (~3000 rows). For 82 photos, this
is overkill but fast enough. If the table grows to 50K+ rows, should filter by
photo_id IN (...) using the known photo set.

**Backfill script**:
- **Good**: Batch inserts of 20 rows (line 178)
- **Good**: Dedup query before insert (lines 157-161)

---

## Security

**P1: Supabase credentials in script accept both ANON_KEY and SERVICE_ROLE_KEY**
Lines 62 and 105: `os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")`.
The service role key bypasses Row Level Security. For a local batch script this is
acceptable (it's operator tooling, not a web endpoint), but the fallback order should
prefer ANON_KEY (which is what happens due to `or` short-circuit). The concern is if
someone sets only SERVICE_ROLE_KEY in .env — they'd get RLS bypass without realizing it.

**P3: `GEMINI_API_KEY` logged indirectly via prompt text**
The `prompt_text` field (line 575) is written to Supabase. It does NOT contain the API
key, but if someone modified `build_extraction_prompt` to include auth headers, it could
leak. Current implementation is safe.

**P3: No input validation on `--identity` UUIDs**
The argparse accepts any string as identity IDs. Invalid UUIDs would simply not match
any Supabase rows (graceful failure), but a malformed input could cause confusing logs.

---

## Codex Data Validation Results

Codex ran these checks directly on the source data:
- `date_labels.json` batch entries: **82 entries, 82 unique photo_ids, 0 duplicates**
- All entries have trigger: `session_142_esther_albert`
- Batch context keys: `['identities', 'trigger']`
- Sample entry confirmed: face_coordinates_sent=True, gedcom_context_sent=False (GEDCOM
  preload was added after the batch ran, confirming the optimization is for future runs)

---

## Summary

| Severity | Count | Items |
|----------|-------|-------|
| **P0** | 0 | None |
| **P1** | 1 | SERVICE_ROLE_KEY fallback in batch script |
| **P2** | 3 | Backfill dedup scope, logging failure detail, missing cost_usd in backfill |
| **P3** | 3 | Multiple Supabase clients, full photo_faces load, no UUID validation |

**Overall assessment**: Both scripts are well-engineered for their purpose. The GEDCOM
preload optimization is correctly implemented. The backfill has appropriate idempotency
guards. No P0 issues found. The P1 (SERVICE_ROLE_KEY) is acceptable for operator tooling
but should be documented.
