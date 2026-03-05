# Session 89c: Fix Re-analyze + Photo Location ID Mismatch + Analysis Metadata UX

**Context**: `docs/session_context/session-89c-context.md`
**Predecessor**: Session 89b (location persistence, model label, GEDCOM reasoning)

## Problem Statement

Three bugs block the re-analyze feature from working end-to-end on the Leon's Restaurant photo (3192877a90a174e9):

1. **Gemini 504 timeout** — Re-analyze fails with "DEADLINE_EXCEEDED". The Gemini 3.1 Pro API times out server-side on this photo. No retry logic exists.

2. **Photo location ID mismatch** — `_load_photo_locations()` does NOT dual-key inbox IDs to SHA256 IDs. The photo page looks up `3192877a90a174e9` but photo_locations.json stores it under `inbox_staged-20260210-182610_5_757557421.130308`. Result: no inline Leaflet map, even though location data exists. This bug affects ALL inbox-uploaded photos with location data.

3. **No analysis metadata in UI** — After analysis, users can't see when it was run or what model produced the results. The `reanalyzed_at` timestamp and model version are stored in JSON but never displayed.

Additionally:
- "Run Face Analysis" button naming is confusing (it's face detection, not photo analysis)
- The prompt used for each analysis should be reconstructable from stored metadata

## Ground Truth: Leon's Restaurant Photo

- **Photo ID**: 3192877a90a174e9 (SHA256) = `inbox_staged-20260210-182610_5_757557421.130308` (inbox)
- **Filename**: 757557421.130308.jpg
- **People**: Victor Capelluto + Victoria Capuano Capeluto
- **True location**: Leon's Restaurant, Asheville, NC (opened 1937, per GEDCOM + Ancestry records)
- **True date**: ~1938-1940 (Victor visited from Japan in 1938 "in transit to Asheville, N.C." per ship manifest; also visited 1940)
- **Current AI result**: "circa 1944, NYC or Miami" (Gemini 3-flash, no GEDCOM) — location WRONG
- **Current photo_locations.json**: lat=25.7617, lng=-80.1918 (Miami) — WRONG but map never shows because of ID mismatch

## Prior Work

| Session | What | Relevance |
|---------|------|-----------|
| 89 | Unified Gemini prompt (AD-201), re-analyze endpoint (AD-202) | Core feature |
| 89b | Location persistence fix, model label fix, GEDCOM reasoning display | 3 bugs fixed |
| 81 | AD-192: GEDCOM-enriched location prompting + Asheville test suite | Ground truth |
| 64 | `gemini_api_calls` Supabase logging (AD-152) | API tracking |

**The dual-keying pattern already exists** in `_load_date_labels()` (app/main.py line 920-930). That's why date estimates display correctly for inbox photos. The same pattern just needs to be applied to `_load_photo_locations()`.

---

## Session Protocol

- Set `.claude/current_session.txt` to `89c`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Create `docs/session_logs/session-89c-log.md` with phase checklist
- Commit after every act (conventional commits)
- Use `/clear` between acts (NEVER /compact)
- Browser verify with Claude Chrome (admin is logged in)
- Screenshots to `docs/screenshots/session-89c/`

## Parallelization Analysis

Act 1 (orient) is sequential. Acts 2 and 3 touch different files (`app/main.py` vs `app/estimate_routes.py`) and could theoretically parallel, but Act 3 depends on Act 2's fix to verify the map renders. Acts 4-5 must be sequential (deploy then verify).

**Recommendation**: Sequential execution. This is a focused bug-fix session.

---

## Deliverables

### Act 1: Orient + Confirm Root Causes (5 min)

1. Read this prompt and `docs/session_context/session-89c-context.md`
2. Read `tasks/lessons.md`, `tasks/todo.md`
3. Confirm the ID mismatch:
   - `grep "3192877a90a174e9" data/photo_locations.json` → no match
   - `grep "inbox_staged-20260210-182610_5_757557421.130308" data/photo_locations.json` → Miami entry exists
4. Confirm `_load_photo_locations()` lacks dual-keying (line 16687-16704)
5. Confirm `_load_date_labels()` has dual-keying (line 920-930)
6. Check Railway logs for the 504 error: `mcp__railway-mcp-server__get-logs` with filter "Gemini OR error"
7. Commit: `docs(session): session 89c orient`

### Act 2: Fix Photo Location ID Mismatch (15 min)

**Goal**: `_load_photo_locations()` gets dual-keying so inline maps render for ALL inbox-uploaded photos.

1. In `app/main.py`, modify `_load_photo_locations()` (line 16687):
   - After loading `data.get("photos", {})`, iterate entries
   - For any key starting with `inbox_`, compute SHA256 ID from the photo's filename
   - Store under both the inbox ID and the SHA256 ID (same pattern as `_load_date_labels()`)
   - Use `PhotoRegistry` to look up the filename from the inbox ID

2. Write tests:
   - Test that `_load_photo_locations()` returns entries under BOTH inbox and SHA256 keys
   - Test that a photo page for an inbox-uploaded photo renders the Leaflet map div
   - Test with photo_id `3192877a90a174e9` specifically

3. Run `make test-fast`
4. Commit: `fix(map): dual-key photo_locations for inbox IDs — inline maps now render`

### Act 3: Add Retry Logic to Re-analyze + Analysis Metadata UX (20 min)

**Goal**: Re-analyze survives Gemini 504 timeouts. Analysis results show timestamp + model.

**3a: Retry logic**
1. In `app/estimate_routes.py`, modify `_call_gemini_date_estimate()`:
   - Add retry logic: up to 2 retries on 504/503/timeout errors
   - Exponential backoff: wait 5s, then 15s
   - Log each retry attempt
   - On final failure, still return None (existing error handling)

2. Consider increasing the base timeout for GEDCOM context from 120s to 180s (Gemini Pro can be slow with large prompts)

**3b: Analysis metadata display**
1. In `app/main.py`, in the model badge area (line ~18714):
   - Show analysis timestamp: "Analyzed with Gemini 3.1-pro on Mar 5, 2026"
   - Use `reanalyzed_at` if present, fall back to `analyzed_at` or batch timestamp
   - Format as human-readable relative time if recent ("2 hours ago") or absolute date

2. Store `prompt_version` in date_labels entry alongside model:
   - e.g., `"prompt_version": "v3_enriched"` or `"prompt_version": "v3_visual_only"`
   - This + `gemini_config` in Supabase enables full prompt reconstruction

**3c: Rename "Run Face Analysis" button**
1. Find the "Run Face Analysis" button text in `app/main.py`
2. Rename to "Detect Faces" (clearer distinction from AI photo analysis)

3. Write tests:
   - Test retry on 504 (mock Gemini to fail once then succeed)
   - Test metadata displays in model badge
   - Test button text change

4. Run `make test-fast` + `make test-ml`
5. Commit: `fix(estimate): retry on Gemini timeout + analysis metadata in UI`

### Act 4: Deploy + Re-analyze Leon's Restaurant Photo (15 min)

1. `make test-fast` + `make test-ml` — all pass
2. Push to main (triggers Railway deploy)
3. Wait for deploy completion (check health endpoint)
4. Navigate to https://rhodesli.nolanandrewfox.com/photo/3192877a90a174e9 with Claude Chrome
5. **Verify inline map now renders** (should show Miami initially — from existing photo_locations data)
6. Click "Re-analyze" button
7. Wait for completion (may take 30-60s with retries)
8. **Verify results**:
   - Location updates to "Asheville, North Carolina" (or similar)
   - Map repositions to Asheville area (~35.6, -82.6)
   - Model badge shows "Gemini 3.1-pro" with timestamp
   - GEDCOM reasoning visible in Photo Detective Evidence
9. Screenshot all results to `docs/screenshots/session-89c/`
10. Also verify photo 746dd11e5b4d86a1 (Victoria in Asheville) still displays correctly
11. Commit any data file updates: `fix(data): Leon's Restaurant re-analyzed — Asheville location`

### Act 5: Assessment + Docs (10 min)

1. Run `/session-review`
2. Write `docs/assessments/session-89c-assessment.md`:
   - What shipped (with evidence — screenshots, test results)
   - What was deferred (with BACKLOG entries)
   - Red flags and next-session verifications
3. Update mandatory docs:
   - `CHANGELOG.md` — add session 89c entry
   - `ROADMAP.md` — update relevant items
   - `docs/ml/ALGORITHMIC_DECISIONS.md` — AD entry for retry logic if significant
   - `docs/roadmap/SESSION_HISTORY.md` — session 89c entry
   - `SESSION_LOG.md` + archive to `docs/session_logs/session-89c-log.md`
4. Final commit: `docs(session): session 89c assessment — re-analyze fix + location ID mismatch`

## Acceptance Criteria

- [ ] Inline Leaflet map renders on photo 3192877a90a174e9 (was broken, now fixed)
- [ ] `_load_photo_locations()` dual-keys inbox IDs to SHA256 IDs
- [ ] Re-analyze succeeds with retry logic (survives 504 timeouts)
- [ ] After re-analyze: location updates from Miami to Asheville
- [ ] Model badge shows model name + analysis timestamp (e.g., "Analyzed with Gemini 3.1-pro on Mar 5, 2026")
- [ ] "Run Face Analysis" renamed to "Detect Faces"
- [ ] Photo 746dd11e5b4d86a1 still works correctly (regression check)
- [ ] All tests pass (`make test-fast` + `make test-ml`)
- [ ] Browser verified via Claude Chrome with screenshots
- [ ] Assessment file, session log, CHANGELOG updated

## Non-Goals (Out of Scope)

- Batch re-processing of all photos (defer to separate session)
- Storing full prompt text in Supabase (store version + config for reconstruction instead)
- Auto-retry on client-side HTMX (retry is server-side only)
- Changes to GEDCOM context builder itself
- Map UI improvements beyond fixing the rendering bug

## Key File Reference

| File | Lines | What to Change |
|------|-------|----------------|
| `app/main.py:16687-16704` | `_load_photo_locations()` | ADD dual-keying (copy pattern from line 920-930) |
| `app/main.py:883-934` | `_load_date_labels()` | REFERENCE for dual-keying pattern |
| `app/main.py:18714-18722` | Model badge display | ADD timestamp display |
| `app/estimate_routes.py:490-493` | Gemini client timeout | INCREASE + ADD retry |
| `app/estimate_routes.py:457-595` | `_call_gemini_date_estimate()` | ADD retry loop |
| `app/main.py` | "Run Face Analysis" button | RENAME to "Detect Faces" |
| `data/photo_locations.json:2277` | Leon's Restaurant entry | Will be updated by re-analyze |
