# Session 90c: Close All 90b Deferrals — Gemini Fix + Face Alignment + Test Cleanup

**Context**: `docs/session_context/session-90c-context.md`
**Predecessor**: Session 90b (v0.93.1, commit 49f3755)

## Problem Statement

Session 90b deferred several items. This session closes ALL of them. The highest-priority fix is the Leon's Restaurant photo: Gemini says "San Francisco" when it should say "Tampa, FL." The fix requires both prompt engineering and passing collection metadata to Gemini. Face analysis is also empty because the "Detect Faces" pipeline was never run (incorrectly assumed to need InsightFace locally — it's pure Gemini API).

## Session Protocol
- Set `.claude/current_session.txt` to `90c`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Commit after every act, `/clear` between acts
- Use Claude Chrome for ALL frontend verification — no exceptions (Lesson 97)
- Run `/session-review` at session end
- Screenshots to `docs/screenshots/session-90c/`

---

## Act 0: Orient + Sync Production Data (10 min)

1. Read this prompt, context file, `tasks/lessons.md`
2. `git log --oneline -5`, `git status`
3. Set `.claude/current_session.txt` to `90c`
4. Create `docs/session_logs/session-90c-log.md` with phase checklist
5. **CRITICAL: Sync production data** — Leon's Restaurant photo (3192877a90a174e9) exists on production but NOT in local photo_index.json. Run:
   ```bash
   python scripts/sync_from_production.py
   ```
   If this script doesn't exist or fails, manually pull photo_index.json from production using the sync API:
   ```bash
   curl -s "https://rhodesli.nolanandrewfox.com/api/sync/pull?file=photo_index" -o data/photo_index.json
   ```
6. Verify photo 3192877a90a174e9 exists locally after sync

Commit: `chore(data): sync production photo_index.json`

---

## Act 1: Improve Gemini Prompt — Collection Context + Location Disambiguation (30 min)

### 1a. Pass Collection/Source Metadata to Gemini

**The Problem:** The Gemini prompt currently receives ONLY the image + GEDCOM context. Collection name, source, and photo filename are NOT passed. The collection name "Nace Capeluto Tampa Collection" is a STRONG location signal that Gemini never sees.

**File to modify:** `rhodesli_ml/gemini_extraction.py`

**What to add:** A new optional parameter `photo_metadata` (dict) to `build_extraction_prompt()` that includes:
- `collection`: e.g., "Nace Capeluto Tampa Collection"
- `source`: e.g., "personal photos"
- `visible_text`: Any text previously extracted from the photo (if available)
- `filename`: Original filename (may contain useful context)

Add a new prompt section between "Genealogical Context" and "JSON Output":
```
## Photo Metadata Context
Collection: {collection}
Source: {source}
{visible_text_if_any}

IMPORTANT: The collection name often indicates the geographic origin of photos.
For example, "Tampa Collection" strongly suggests photos were taken in or near Tampa.
Use this as corroborating evidence alongside visual and biographical analysis.
```

**Wire it up:** In `app/estimate_routes.py`, the `_call_gemini_date_estimate()` and the reanalyze handler must pass photo metadata to the prompt builder.

### 1b. Improve Location Prompt — Signage Cross-Reference + Transit Disambiguation

**File to modify:** `rhodesli_ml/gemini_extraction.py`, specifically the `"location"` section in `PROMPT_SECTIONS`.

**Add to Step 2 (Biographical Cross-Reference):**
```
**Step 2b: Business Name Cross-Reference**
- Cross-reference visible business names (signs, storefronts) with known family members
- Example: A sign reading "LEON'S RESTAURANT" + a family member named "Leon Capeluto"
  strongly suggests this is Leon's business. Use Leon's known locations.
- Business name matches are VERY STRONG location evidence.

**Step 2c: Immigration & Transit Disambiguation**
- Passenger list and immigration records show PORTS OF ENTRY, which may be transit points
  (e.g., San Francisco was a major Pacific port — arrivals often continued to other cities)
- Do NOT assume a port-of-entry city is where someone lived
- Residence events, occupation events, and children's birth places are more reliable
  indicators of where someone actually lived than immigration ports
- When visual evidence (signage, architecture) conflicts with transit/immigration records,
  PREFER the visual evidence for determining photo location
```

### 1c. Tests

- Test that `build_extraction_prompt()` includes collection metadata when provided
- Test that the location section mentions signage cross-reference
- Test that photo metadata dict is properly formatted and injected

Commit: `feat(gemini): pass collection metadata + improve location disambiguation (AD-204)`

---

## Act 2: Run Face Alignment on Leon's Restaurant Photo (15 min)

### 2a. Verify Face Alignment Works on Railway

The "Detect Faces" button at `/api/face-alignment/{photo_id}` does NOT require InsightFace. It uses pre-existing bounding box coordinates from embeddings.npy and sends them to Gemini for per-face descriptions (coordinate bridging, AD-146).

**Steps:**
1. Open Leon's Restaurant photo in Chrome: `https://rhodesli.nolanandrewfox.com/photo/3192877a90a174e9`
2. Click "Detect Faces" button
3. Verify per-face descriptions appear (age, gender, clothing, identifying features)
4. If button fails: check the admin endpoint response, inspect logs, fix any issues

**Expected result:** Two face descriptions:
- Face 0: Young man in light-colored suit with wide lapels, ~30s
- Face 1: Young woman with shoulder-length curled hair, dark skirt, ~20s-30s

### 2b. Add Model + Timestamp to Face Analysis Section

The Photo Detective section shows "Analyzed with Gemini 3.1-pro on Mar 5, 2026" but the Face Analysis section does NOT show when/how descriptions were generated.

**Fix:** In the face analysis section builder (`_build_face_alignment_section()` in main.py), add a line showing:
- "Face descriptions generated by {model} on {date}" (matching Detective UX)
- Read this from the face_alignments storage (Supabase or JSON)

### 2c. Research: Combine Face + Geo into One Gemini Call?

Currently two separate calls. Nolan asks if they should be one.
- Try a combined prompt locally (dry run) and compare quality
- If quality is acceptable, consider merging to save cost/latency
- Log decision as AD-205 either way
- **Do not block on this** — it's a research question, not a blocker

### 2d. Screenshot Evidence

Take Chrome screenshot showing face descriptions populated.

Commit: `feat(faces): run face alignment on Leon's Restaurant photo`

---

## Act 3: Re-run Gemini Analysis with Improved Prompt (20 min)

### 3a. Re-analyze Leon's Restaurant Photo

After Act 1's prompt improvements are deployed:

1. Push the code changes to production (git push)
2. Wait for deploy to complete
3. Open Leon's Restaurant photo in Chrome
4. Click "Re-analyze Photo"
5. Verify the new analysis says "Tampa, FL" (not SF/NYC)
6. Verify the evidence text mentions:
   - "LEON'S RESTAURANT" sign
   - "Nace Capeluto Tampa Collection"
   - Tampa as the location with high confidence

### 3b. If Gemini Still Gets It Wrong

If the improved prompt STILL says SF/NYC:
1. Check what GEDCOM context was actually sent (check server logs or gemini_api_calls table)
2. Consider adding Leon Capeluto (Victor's brother) to the GEDCOM context even though he's not IN the photo — he's the restaurant owner
3. Consider adding a "collection_location_hint" field that explicitly tells Gemini "this collection is from Tampa, FL"

### 3c. Verify All Analysis Sections

After re-analysis, the photo page should show:
- Location: "Tampa, Florida, United States" (high confidence)
- Date: circa 1940s (already correct)
- Scene: Mentions Leon's Restaurant
- Face analysis: Per-face descriptions (from Act 2)
- Photo Detective Evidence: Geographic analysis mentions Tampa, not SF

Screenshot evidence for all sections.

Commit: `fix(gemini): Leon's Restaurant re-analysis — Tampa FL (AD-204)`

---

## Act 4: Fix Remaining Test Issues (15 min)

### 4a. Investigate 7 Flaky Order-Dependent Tests

These tests pass individually but fail intermittently in the full suite:
- `test_person_links.py` (3 tests)
- `test_public_photo_viewer.py` (1 test)
- `test_search.py` (1 test)
- `test_skipped_focus.py` (2 tests)

**Investigation:**
1. Run with `--randomly-seed=1234` to reproduce ordering
2. Find which test(s) run before these that corrupt state
3. Likely cause: route module loading order affects which route handles a path
4. Fix: add proper test isolation (fresh TestClient per test, or reset route order)

### 4b. Fix or Skip

If root cause is clear: fix it. If it requires significant refactoring: mark as `@pytest.mark.xfail(reason="order-dependent, #BACKLOG-XXX")` with a BACKLOG entry.

Commit: `fix(tests): resolve order-dependent test flakiness`

---

## Act 5: Browser Verification + Final Verification (15 min)

**ALL must be verified with Claude Chrome. No exceptions.**

1. **Leon's Restaurant photo** (3192877a90a174e9):
   - [ ] Location says "Tampa, Florida" (not SF/NYC)
   - [ ] Face analysis shows 2 face descriptions (not "No face descriptions")
   - [ ] Photo Detective evidence mentions Tampa
   - [ ] Date estimate is circa 1940s
   - [ ] Map pin on Tampa
2. **Upload date sorting** — still works (regression check)
3. **Person page** — Victor Capelluto loads correctly
4. **Landing page** — general smoke test
5. **Back-of-photo** — verify David Franco photo flip still works

Save all screenshots to `docs/screenshots/session-90c/`

---

## Act 6: Assessment + Docs (10 min)

Standard mandatory outputs:

1. Write `docs/assessments/session-90c-assessment.md`
2. Update `docs/session_logs/session-90c-log.md`
3. Update `CHANGELOG.md` — new version entry
4. Update `ROADMAP.md` — mark deferred items complete
5. Update `docs/BACKLOG.md` — update relevant items
6. Update `docs/roadmap/SESSION_HISTORY.md` — session 90c entry
7. Update `docs/ml/ALGORITHMIC_DECISIONS.md` — AD-204 (collection context + location disambiguation)

---

## Acceptance Criteria

- [ ] Gemini prompt includes collection name and source metadata
- [ ] Gemini prompt has signage cross-reference instructions
- [ ] Gemini prompt has transit vs. residence disambiguation
- [ ] Leon's Restaurant photo: Gemini says Tampa, FL (browser verified)
- [ ] Leon's Restaurant photo: Face descriptions populated (browser verified)
- [ ] Leon's Restaurant photo: Photo Detective evidence mentions Tampa
- [ ] 7 flaky tests fixed or marked xfail with BACKLOG entry
- [ ] All tests pass (`make test-fast`)
- [ ] Browser verified via Claude Chrome with screenshots
- [ ] Assessment + session log + CHANGELOG + ROADMAP updated

## Key Architectural Facts (Read Before Starting)

1. **Two pipelines:** "Re-analyze Photo" = date/location/scene (one Gemini call). "Detect Faces" = per-face descriptions from bboxes (separate Gemini call). Both use Gemini API, neither needs InsightFace on Railway.

2. **Collection metadata NOT passed to Gemini** — this is the main gap. `build_extraction_prompt()` in `rhodesli_ml/gemini_extraction.py` takes `gedcom_context` but has no parameter for collection/source metadata.

3. **GEDCOM data is sparse for Leon's Restaurant:** Victor has birth+death only. Victoria has birth only. Big Leon has birth+death only. No residence/occupation events. The GEDCOM tree file doesn't include immigration/passenger list records.

4. **Production data divergence:** Photo 3192877a90a174e9 exists on production but not locally. MUST sync production data first.

5. **Face alignment route:** POST `/api/face-alignment/{photo_id}` in `app/photo_routes.py:312`. Loads bboxes from embeddings cache, sends to Gemini, stores results.

6. **Gemini reanalyze route:** POST `/api/photo/{photo_id}/reanalyze` in `app/estimate_routes.py:1111`. Calls `_call_gemini_date_estimate()` with GEDCOM context.

7. **Prompt builder:** `rhodesli_ml/gemini_extraction.py` — `build_extraction_prompt()` function. Sections defined in `PROMPT_SECTIONS` dict.

## Non-Goals

- Full Supabase migration (shadow writes already wired in 90b)
- Further main.py extraction beyond 26K lines
- New UX features
- Batch re-analysis of all photos (just Leon's Restaurant)

## Estimated Cost

- 2 Gemini API calls (face alignment + re-analysis): ~$0.06
- No batch processing needed
