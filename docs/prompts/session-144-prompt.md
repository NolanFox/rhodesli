# Session 144: GEDCOM Re-Import + Context Enrichment + Batch Re-Run

## Context
Session 143 completed 275/279 Fox photo batch, but review revealed GEDCOM context gaps.
See `docs/session_context/session-143-anchor-comparison-prompt.md` and `docs/feedback/session-143-feedback-interactive.md`.
AD-233 (anchor refinement) and AD-234 (GEDCOM enrichment) document the decisions.

## Phase 0: Orient + GEDCOM Re-Import (HIGHEST PRIORITY)
```bash
echo "144" > .claude/current_session.txt
source venv/bin/activate && make test-fast
```

1. **Import new GEDCOM** from `~/Downloads/gedcom_20260328/`
   - Read past GEDCOM import lessons — check `tasks/lessons.md` and `docs/ml/ALGORITHMIC_DECISIONS.md` for previous import issues
   - Run the importer carefully — this replaces ALL GEDCOM data
   - Verify row counts before and after
   - **DO NOT lose existing GEDCOM face links** — they map identities to GEDCOM records

2. **Link Albert's wives** after import:
   - Find Rose Weiss in the new GEDCOM → link to Albert Fox identity
   - Find Jean Baumann in the new GEDCOM → link to Albert Fox identity
   - **Rename identities**: Rose → "Rose Weiss Baygel Fox", Jean → "Jean Baumann Kassel Fox"
   - Verify spouse_family links in the imported GEDCOM connect correctly

3. **Verify import**: Check that Albert now has multiple spouse families, Esther's death date is present, Rose and Jean are linked

## Phase 1: GEDCOM Context Enrichment (AD-234)

### P0: Spouse Timeline Block
- File: `rhodesli_ml/gedcom_context.py` (~line 168, 272)
- Add a "Spouse Timeline" section to the GEDCOM context string
- For each identified person in the photo, emit:
  ```
  Spouse Timeline for Albert Fox:
  1. Esther Burd — married May 6, 1920 (Hamilton, Ohio) — died Jun 11, 1966
  2. Rose Weiss Baygel — married [date] — died [date]
  3. Jean Baumann Kassel — married [date] — died [date]
  CONSTRAINT: If photo shows a woman with Albert, she must be the wife alive at the estimated date.
  ```
- Sort by marriage date
- Include derived temporal bounds: "Photos with Rose must be after 1966"

### P1: Birth Date Resolution
- File: `rhodesli_ml/importers/gedcom_parser.py` (~line 287)
- When multiple birth dates exist, identify primary vs alternate
- In context string: "Born: 1892 [primary]; alternate: abt 1896 [secondary]"
- Instruct Gemini to use primary for age math

### P1: Structured Relationship Blocks
- File: `rhodesli_ml/gemini_extraction.py` (~line 227)
- The `verified_facts` parameter exists but isn't used by batch/interactive callers
- Wire it: pass structured CONFIRMED IDENTITIES and KNOWN RELATIONSHIPS
- These are easier for Gemini to reason about than free-form GEDCOM dump

## Phase 2: Re-Run 83+4 Photos
After GEDCOM enrichment is implemented and tested:

1. **Re-run 83 Session 142 photos** that lack GEDCOM context, evidence, reasoning
   - Use `--no-skip-existing` but only for these specific photos
   - Verify first result has: GEDCOM context with spouse timeline, evidence, reasoning, all fields

2. **Retry 4 timeout photos** from Session 143 batch

3. **Verify on production**: Check 3 sample photos show improved analysis

## Phase 3: Anchor Photo Refinement Prototype (AD-233)
If time permits after Phases 0-2:

1. Implement multi-image Gemini call in `rhodesli_ml/multi_pass.py`
2. Test with the Albert Fox oval portrait (send Detroit group photo as anchor)
3. Compare API result to Gemini Chat result from Session 143
4. Admin UI: "Compare with anchor" button on photo page

## Parallelization Plan
| Track | Phase | Dependencies |
|-------|-------|-------------|
| Sequential | Phase 0 (GEDCOM import) | Must complete first |
| Sequential | Phase 1 (context enrichment) | Depends on Phase 0 |
| Sequential | Phase 2 (batch re-run) | Depends on Phase 1 |
| Track B | Phase 3 (anchor prototype) | Independent, can start after Phase 1 |

## Key Constraints
- **GEDCOM import is destructive** — snapshot before, verify after
- **DO NOT re-run batch before GEDCOM enrichment** — would waste API calls
- **DO NOT lose existing face-to-GEDCOM links** during import
- **Gemini 3.1 Pro**: 250 RPD on Tier 1. 83+4=87 photos fits in one day.
- Follow batch-data-pipeline.md for all outputs
- Browser verify after every phase
- Codex audit after every phase
