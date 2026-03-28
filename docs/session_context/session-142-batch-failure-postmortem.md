# Session 142: Batch Gemini Pipeline Failure Postmortem

**Date**: 2026-03-27
**Severity**: HIGH — 84 API calls produced data invisible to production for 20+ hours
**Lessons**: 159, 160, 161, 162
**Harness gaps identified**: 3

---

## What Happened (Timeline)

### Phase 1: Script Creation (~1:20 AM)
- Created `scripts/batch_gemini_for_person.py`
- Used `_call_gemini_date_estimate()` from `app/estimate_routes.py` — **"quick" preset** (date + location only, no face analysis)
- Read identities from local `data/identities.json` — **stale data** (79 faces for Esther vs 144 in Supabase)
- Output: `rhodesli_ml/data/date_labels.json` — **local file, NOT Supabase**

### Phase 2: Data Source Fix (~1:33 AM)
- Fixed to read identities from Supabase (source of truth) — now 282 photos
- Fixed Supabase pagination (1000-row default limit)
- **Still writing to local JSON, not Supabase**

### Phase 3: Preset Upgrade (~1:40 AM)
- Upgraded from "quick" to "full" preset — face analysis, subject ages, group composition
- Added face coordinates (sorted left-to-right per Codex P0)
- **Test run: 2 photos successful** with rich data
- **Did NOT verify GEDCOM context was included** — test photos happened to not have GEDCOM links

### Phase 4: Overnight Batch (~1:45 AM - 6:11 AM)
- Launched 279-photo batch
- `_build_gedcom_context_for_photo()` loads entire GEDCOM tree (15,000+ individuals) from Supabase PER PHOTO — takes ~60-90s each
- Supabase timed out on GEDCOM loading for nearly every photo
- Script logged warnings but **continued silently**
- **82 photos completed without GEDCOM context** (`gedcom_context_sent: False`)
- Hit Gemini quota (250/day) at 6:11 AM
- **Supabase audit logging also failed** — `contract_valid` and `full_response_hash` columns don't exist in `gemini_api_calls` table

### Phase 5: Discovery (~8:30 AM)
- User asked about photo count — discovered local JSON had 79 faces (stale)
- Fixed to read from Supabase — 144 faces for Esther, 196 for Albert
- **Still didn't check GEDCOM context or Supabase audit logs**

### Phase 6: GEDCOM Preload Fix (~9:00 AM)
- Implemented one-time GEDCOM preload — eliminated per-photo Supabase queries
- Confirmed working: "GEDCOM context 2190 tokens (full)"
- **But 82 photos already processed without GEDCOM cannot be un-done**

### Phase 7: Multiple Quota Hits (~12:35 PM, 4:35 PM)
- Quota resets are per-day (UTC midnight), not rolling 24h
- Each retry attempt consumed quota: test calls, partial batches
- **Only 2 more photos completed across 2 attempts**

### Phase 8: User Discovery (~9:28 PM)
- User navigated to photo page: **"No Gemini analysis has been run on this photo yet."**
- **84 date labels existed in local JSON but NOT in Supabase `date_labels` table**
- Production app reads from Supabase, not local JSON
- **Data was invisible to production for 20+ hours**

### Phase 9: Fix (~9:35 PM)
- Synced 84 labels to Supabase `date_labels` table
- Verified photo page now shows "circa 1917" with GEDCOM-derived location
- Added Supabase upsert to batch script for future runs

---

## Root Causes

### 1. Local JSON Output (Lesson 162)
**What**: Script wrote to `rhodesli_ml/data/date_labels.json` but production reads from Supabase `date_labels` table.
**Why harness missed it**: `data-layer.md` rule says "Postgres/Supabase is the source of truth" but applies to app code. No rule covered batch scripts. The old `generate_date_labels.py` script wrote to local JSON because it predated the Supabase migration. New script copied that pattern.
**Fix**: New rule `.claude/rules/batch-data-pipeline.md` + batch script now upserts to Supabase.

### 2. No First-Result Quality Check (Lesson 161)
**What**: 82 photos ran without GEDCOM context. Never detected because only API success was checked.
**Why harness missed it**: No rule for "verify enrichment flags on batch output." `production-verification.md` covers deployed code, not batch data quality.
**Fix**: First-result quality check added to batch script. Warns on missing GEDCOM, face coords, or analysis fields.

### 3. No Supabase Audit Log Verification (Lesson 160)
**What**: 82 `gemini_api_calls` rows failed to insert due to schema mismatch. Logged as warnings, never checked.
**Why harness missed it**: Warnings in batch output were buried in 1000+ lines of GEDCOM loading logs. No rule for "verify audit log insertion after first call."
**Fix**: Backfill script created. Batch script now uses correct column set.

### 4. Stale Local Data (Existing Lesson 78/133)
**What**: Local `identities.json` had 79 faces for Esther vs 144 in Supabase.
**Why harness missed it**: `production-data-sync.md` says "sync before ML work" but the batch script was new code, not a traditional ML pipeline.
**Fix**: Script reads from Supabase directly.

### 5. URL Given Without Browser Verification (Lesson 159)
**What**: Gave user a photo URL without checking if the page showed AI analysis.
**Why harness missed it**: `browser-read-only.md` covers production interactions but doesn't mandate "verify data appears before sharing URLs."
**Fix**: Added to Lesson 162 — "Must verify data appears in production UI after batch completes."

---

## Harness Gaps Identified

| Gap | Rule File | Fix |
|---|---|---|
| Batch scripts not covered by data-layer rules | `.claude/rules/data-layer.md` | New rule: `.claude/rules/batch-data-pipeline.md` |
| No first-result quality check rule | None | Added to batch script + Lesson 161 |
| No "verify batch output in UI" rule | `.claude/rules/production-verification.md` | Extended via Lesson 162 |

---

## Lessons Added

| # | Summary | Breadcrumbs |
|---|---|---|
| 159 | Deploy health check before session end | `deployment-lessons.md`, `production-verification.md` |
| 160 | Verify logging on first batch call | `deployment-lessons.md` |
| 161 | Verify FULL output quality on first call | `deployment-lessons.md` |
| 162 | Batch outputs must write to Supabase | `deployment-lessons.md`, `batch-data-pipeline.md` |

---

## What Would Have Caught This

1. **After first batch photo**: Check `gedcom_context_sent` field → would have caught missing GEDCOM
2. **After first batch photo**: Query `gemini_api_calls` table → would have caught logging failure
3. **After batch complete**: Check Supabase `date_labels` count → would have caught missing sync
4. **Before giving URL to user**: Open page in browser → would have caught "No AI analysis"

---

## Cost of This Failure

- **84 API calls (~$4.60)** produced lower-quality results (no GEDCOM context)
- **~250 quota-blocked calls** wasted daily quota across 3 days
- **20+ hours** of production data being invisible
- **User trust degradation** — multiple promises of working features that didn't work
- **Re-run needed**: All 279 photos must be re-processed (~$15.35) to get proper GEDCOM context

---

## Related Decisions & Documents

- AD-231: Prompt improvements (capture_vs_print, scene_description, reasoning_summary)
- PRD-059: Temporal co-occurrence analysis
- `docs/session_context/session-142-codex-prompt-audit.md`: Codex P0 findings on prompt
- `docs/session_context/session-142-codex-speed-audit.md`: GEDCOM preload optimization
- `docs/session_context/session-142-prompt-comparison.md`: Old vs new prompt comparison
