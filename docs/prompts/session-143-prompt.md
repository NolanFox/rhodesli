# Session 143: Data Repair + Gemini Batch Completion + Photo Page Fix

## Context
Session 142 left data display issues on photo pages, 195 unprocessed Fox Family photos,
and a Rhodes data sync gap. See `docs/session_context/session-143-context.md`.

## Phase 0: Orient + Verify Baseline
```bash
echo "143" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline (~3846 tests)
```
- Verify site health: `curl https://rhodesli.nolanandrewfox.com/health`
- Read Session 142 postmortem: `docs/session_context/session-142-batch-failure-postmortem.md`
- Read lessons 159-162 in `tasks/lessons.md`

## Phase 1: Photo Page Rendering Fix (PARALLEL Track A)

The photo page shows incomplete AI analysis data. The JSONB `data` column in `date_labels`
has all the fields but the template doesn't render them.

1. **Audit the photo page template** — grep for how `_load_date_labels()` results are consumed in `app/page_routes.py` and `app/photo_routes.py`
2. **Map field names** — the batch produces `location_estimate` but old code may expect `location`. Map ALL field name differences.
3. **Fix the rendering** — ensure face_analysis, group_composition, scene_description, clothing_notes, subject_ages, location ALL display when present
4. **Test with the Albert Fox photo**: `inbox_fox-charlie-001_12_01635_p_13akf5twbc0904` — has complete data including GEDCOM
5. **Test with a Rhodes photo**: verify existing Rhodes labels still render correctly
6. **Browser verify** both photos show complete AI analysis

## Phase 2: Rhodes Data Sync (PARALLEL Track B)

Rhodes photos analyzed through the web UI stored results on Railway volume JSON only.
When app switched to Supabase-first reading, these became invisible.

1. **Inventory the gap** — query `gemini_api_calls` for all successful re_analysis/date_estimation calls, cross-reference with `date_labels` table. How many photos have API results but no date_labels entry?
2. **For each missing photo** — recover from `gemini_api_calls.full_response` column and upsert to `date_labels`
3. **Verify Victoria's Leon's Restaurant photo** renders correctly after sync: `https://rhodesli.nolanandrewfox.com/photo/3192877a90a174e9`
4. **Check face_alignment data** — the "Face Analysis" section on Victoria's photo showed data before. Where is it stored? Is it in a different table?

## Phase 3: Gemini Batch Completion (SEQUENTIAL — after billing enabled)

**PREREQUISITE**: User must enable billing at https://aistudio.google.com/apikey

1. **Re-run ALL 279 photos** (not just remaining 195) — the 82 without GEDCOM need redo:
   ```bash
   python scripts/batch_gemini_for_person.py \
     --identity 65207728-9ee6-48c1-be68-a2da23354caf \
     --identity 85546ebf-75b9-4971-a9d4-b2ce2271bc19 \
     --no-skip-existing --max-cost 20 --delay 1.5
   ```
2. **Verify first result** — quality check will warn if GEDCOM missing. STOP if any enrichment fails.
3. **After completion** — verify ALL 279 photos have date_labels in Supabase
4. **Browser verify** 3 sample photos show complete AI analysis
5. **Re-run event_grouping.py** with complete data
6. **Update event_groups.json** and verify admin page

## Phase 4: "Conflicting Face Assignment" Investigation (PARALLEL Track C)

Victoria Capeluto's person page shows "Needs review" / "Conflicting face assignment" on several photos.

1. Investigate — are these candidate_ids (proposed matches) or actual data conflicts?
2. If candidate_ids: this is normal. Consider whether UI should show differently for confirmed people.
3. If actual conflicts: audit and repair.

## Phase 5: Codex Audit + Session Close

1. Run Codex on ALL changed files
2. Fix P0/P1 findings
3. Browser verify: landing, person page (Esther, Albert, Victoria), photo page (Albert's 1917, Victoria's Leon's)
4. Full harness close: assessment, CHANGELOG, ROADMAP, BACKLOG, SESSION_HISTORY, lessons
5. `git log origin/main..HEAD` must be empty
6. Deploy health verified

## Verification Gate

For EACH photo page fix, verify with the Feature Reality Contract:
- [ ] Data exists in Supabase date_labels table
- [ ] App loads it via _load_date_labels()
- [ ] Photo page template renders ALL fields (date, location, face analysis, scene, ages)
- [ ] Production browser shows complete AI analysis
- [ ] Test covers the rendering path

## Key Constraints
- **DO NOT** store data only in local JSON — Supabase is source of truth (Lesson 162)
- **DO NOT** give URLs without checking the page first (Lesson 159)
- **DO NOT** run batch without verifying first result quality (Lesson 161)
- **DO NOT** declare done without browser verification of actual data display
- Follow `.claude/rules/batch-data-pipeline.md` for all batch output
