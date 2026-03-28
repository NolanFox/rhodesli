# Session 143: Single Source of Truth + Data Repair + Gemini Batch Completion

## Context
Session 142 is the 12th data integrity incident. The root cause is always the same: multiple
data stores (local JSON, Railway volume, Supabase) that get out of sync. Fallback paths
silently mask data loss. This session's #1 priority is eliminating fallback paths — not features.
See `docs/session_context/session-143-context.md`.

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
- Read ALL data-related lessons: 78, 104, 105, 116, 133, 136, 141, 142, 144, 145, 150, 153, 154, 162

---

## Phase 1: ELIMINATE FALLBACK PATHS — Single Source of Truth (HIGHEST PRIORITY)

**This is the #1 task. Do NOT skip or defer. Every fallback path is a silent data loss vector.**

The app currently reads data with "try Supabase, fall back to JSON" patterns. This has caused
12 data integrity incidents. The fix: Supabase is THE source. No fallbacks. If Supabase is
down, the app shows an error — it does NOT silently serve stale data.

1. **Audit every data loader** — grep for all functions that have Supabase-then-JSON fallback:
   - `_load_date_labels()` in app/main.py (~line 2294)
   - `load_registry()` — already Supabase-only (good)
   - `_load_proposals()` — check
   - `_load_photo_locations()` — check
   - `_load_face_alignments()` — check
   - Any other `DATA_SOURCE` branching
2. **For each loader with a fallback**: Remove the JSON fallback. If Supabase returns None, return empty dict (not stale JSON data).
3. **Add structural test**: `test_no_json_fallback_in_data_loaders` — fails if any loader reads from local JSON when DATA_SOURCE=postgres
4. **Migrate any data that exists ONLY on Railway volume JSON to Supabase** — this is Phase 2
5. **Document as AD-232**: Single source of truth enforcement

## Phase 2: Rhodes Data Sync — Railway Volume → Supabase (PARALLEL Track B)

Rhodes photos analyzed through the web UI stored results on Railway volume JSON only.
When fallbacks are removed (Phase 1), these will be GONE unless migrated first.

1. **Inventory the gap** — query `gemini_api_calls` for all successful re_analysis/date_estimation calls, cross-reference with `date_labels` table
2. **For each missing photo** — recover from `gemini_api_calls.full_response` and upsert to `date_labels`
3. **Also check**: photo_locations, face_alignments — any other data stored only on volume
4. **Write a migration script** that pulls ALL volume-only data into Supabase
5. **Verify Victoria's Leon's Restaurant photo** renders correctly
6. **Verify face_alignment data** — the "Face Analysis" section data. Where is it stored?

## Phase 3: Data Audit Retrospective — WHY didn't past audits catch this? (PARALLEL Track C)

Past sessions (96e, 105, 108, 114, 132, 133) ran data integrity audits. None caught the
date_labels Supabase gap or the volume-only storage pattern.

1. **Read past audit scripts**: `scripts/check_data_integrity.py`, any reconciliation scripts
2. **Identify what they checked** — did they check date_labels? photo_locations? face_alignments?
3. **Identify what they missed** — the pattern "data exists on volume but not in Supabase"
4. **Write a COMPREHENSIVE data audit** (`scripts/comprehensive_data_audit.py`) that checks:
   - Every Supabase table the app reads has ALL expected data
   - No "orphaned" data on Railway volume that isn't in Supabase
   - No photo_id in gemini_api_calls without corresponding date_labels entry
   - No identity with faces but no photo_faces entries
   - Cross-reference ALL data stores
5. **Have Codex independently write its OWN data audit** — different perspective, may catch different gaps
6. **Run BOTH audits** and compare findings
7. **Document gaps** — what each audit found that the other missed

## Phase 4: Photo Page Rendering Fix (PARALLEL Track A)

The photo page shows incomplete AI analysis. JSONB `data` column has all fields but template doesn't render them.

1. **Audit the photo page template** — grep for how `_load_date_labels()` results are consumed
2. **Map field names** — batch produces `location_estimate`, old code may expect `location`
3. **Fix the rendering** — face_analysis, group_composition, scene_description, clothing_notes, subject_ages, location
4. **Test with Albert Fox photo**: `inbox_fox-charlie-001_12_01635_p_13akf5twbc0904`
5. **Test with Rhodes photo**: verify existing labels still render
6. **Browser verify** BOTH photos show complete AI analysis

## Phase 5: Gemini Batch Completion (SEQUENTIAL — after billing enabled)

**PREREQUISITE**: User must enable billing at https://aistudio.google.com/apikey

1. **Re-run ALL 279 photos** with `--no-skip-existing --max-cost 20`
2. **Verify first result** — STOP if GEDCOM missing or any enrichment fails
3. **After completion** — verify ALL 279 in Supabase date_labels
4. **Browser verify** 3 sample photos
5. **Re-run event_grouping.py**, update admin page

## Phase 6: "Conflicting Face Assignment" Investigation (PARALLEL Track D)

Victoria Capeluto's person page shows "Needs review" / "Conflicting face assignment."

1. Investigate — candidate_ids (normal) or actual conflicts?
2. If candidates: consider UI change for confirmed people
3. If conflicts: audit and repair

## Phase 7: Codex Audit — MULTIPLE PASSES

1. **Codex Pass 1**: Audit all code changes from this session — security, correctness
2. **Codex Pass 2**: Audit the data audit scripts — did they miss anything?
3. **Codex Pass 3**: Have Codex write its OWN independent data audit and run it
4. **Compare all findings** — document what each pass caught that others missed
5. **Log Codex performance** per `.claude/rules/ai-tool-audit.md`

## Parallelization Plan

| Track | Phases | Dependencies | Can Run With |
|-------|--------|-------------|-------------|
| Track A | Phase 4 (photo page fix) | None | B, C, D |
| Track B | Phase 2 (Rhodes sync) | None | A, C, D |
| Track C | Phase 3 (audit retrospective) | None | A, B, D |
| Track D | Phase 6 (face assignment) | None | A, B, C |
| Sequential | Phase 1 (fallback removal) | Must complete before Phase 5 | — |
| Sequential | Phase 5 (Gemini batch) | Phase 1 + billing | — |
| Sequential | Phase 7 (Codex multi-pass) | After all code changes | — |

Launch Tracks A, B, C, D as parallel worktree subagents immediately after Phase 0.
Phase 1 runs on main. Phase 5 after Phase 1 + billing. Phase 7 after all changes.

## Phase 8: Session Close

1. Run `/session-review` skill — catches gaps automatically
2. Browser verify: landing, Esther, Albert, Victoria person pages, 3 photo pages
3. Full harness close: assessment, CHANGELOG, ROADMAP, BACKLOG, SESSION_HISTORY
4. `git log origin/main..HEAD` must be empty
5. Deploy health verified
6. Run comprehensive data audit one final time — must be clean
7. Run `/ux-review` on any screenshots taken

## Verification Gate

For EACH data fix:
- [ ] Data exists in Supabase (NOT local JSON)
- [ ] App loads from Supabase with NO JSON fallback
- [ ] Production page renders the data correctly
- [ ] Structural test prevents regression
- [ ] Comprehensive audit passes

## Key Constraints
- **#1 PRIORITY**: Eliminate JSON fallbacks. Supabase is the ONLY source.
- **DO NOT** store data only in local JSON (Lesson 162)
- **DO NOT** give URLs without checking the page (Lesson 159)
- **DO NOT** run batch without verifying first result quality (Lesson 161)
- **DO NOT** declare done without browser verification of actual data display
- **DO NOT** trust past data audits — they missed this. Write new ones.
- Follow `.claude/rules/batch-data-pipeline.md` for all batch output
- Follow `.claude/rules/data-layer.md` — Supabase is source of truth, period
