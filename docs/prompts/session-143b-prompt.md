# Session 143b: Gemini Batch + Audit Fixes + Hook Redesign

## Context
Session 143 completed Phases 0-4, 6-7 and fixed 6 feedback items. See `docs/assessments/session-143-assessment.md`.
See `docs/session_context/session-143-context.md` for full predecessor context.

## Remaining from Session 143

### Phase 5: Gemini Batch Completion (HIGHEST PRIORITY)
Already on Tier 1 Postpay (1,500 RPD). Script ready with all fixes.

1. Run batch: `source venv/bin/activate && python scripts/batch_gemini_for_person.py --person "Esther Burd Fox" --person "Albert Fox" --no-skip-existing --max-cost 20`
2. **STOP after first result** — verify: GEDCOM context present, face_analysis populated, all fields non-empty
3. After completion, verify ALL photos in Supabase `date_labels`
4. Browser verify 3 sample Fox Family photo pages show AI Analysis
5. Re-run `scripts/event_grouping.py` if needed

### Comprehensive Data Audit Fixes
Session 143 audit found 5/14 checks failing:
1. **20 CONFIRMED identities with no anchor_ids** — promote candidate_ids or investigate
2. **2 orphan anchor faces** for Netanel Menashe — repair or remove
3. **Schema mismatch** in audit script — fix `gemini_api_calls.feature` and `photos.face_ids` column refs
4. **48 multi-hop merges** — flatten to direct targets
5. **1 GEDCOM link to merged identity** — redirect

### Hook Redesign (FB-003, HD-032)
The pre-work-clear-gate hook doesn't work. Research agent produced findings in `docs/session_context/session-143-hooks-research.md`.
1. Read the research findings
2. Implement the recommended approach
3. Test that it actually enforces /clear without being gameable

### Test Fixture Alignment (Codex P2)
`tests/test_ai_analysis_rendering.py` BATCH_LABEL fixture doesn't match actual batch script output.
Update to use string `location_estimate` + `location_evidence` dict + `visible_text` string.

### Face Overlay Browser Verification
Session 143 deployed adaptive label positioning but Railway main app build was still running.
1. Verify face overlay labels on Fox Family group photo
2. Check labels don't overflow photo edges
3. Check labels don't overlap adjacent face boxes

## Parallelization Plan
| Track | Task | Dependencies |
|-------|------|-------------|
| Main | Phase 5 Gemini batch | None (sequential, monitor) |
| Track A | Audit script fixes (schema) | None |
| Track B | Data repairs (orphan faces, merges) | None |
| Track C | Hook redesign | Research doc ready |
| Track D | Test fixture alignment | None |

## Key Constraints
- **DO NOT** run batch without verifying first result (Lesson 161)
- **DO NOT** lose data — all repairs must snapshot first (Lesson 155)
- Follow `.claude/rules/batch-data-pipeline.md` for batch output
- Browser verify after deploy
