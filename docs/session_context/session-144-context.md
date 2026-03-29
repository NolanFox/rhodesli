# Session 144 Context

**Predecessor**: Session 143 (docs/assessments/session-143-assessment.md)
**Date**: 2026-03-29
**State**: v0.99.54, 3942 tests, 547 date_labels, 275/279 Fox photos processed

---

## What Session 143 Delivered
- AD-232: Single source of truth (no JSON fallback), 19 tests
- Photo page renders all Gemini batch fields (face analysis, group comp, clothing, reasoning)
- Old nested label format normalized (date_estimation/location dicts unwrapped)
- P0 face card text fix (nested `<a>` tags)
- Face overlay label positioning (adaptive above/below)
- Transcript-based /clear hook (HD-032)
- Comprehensive data audit script + volume sync script
- Gemini batch: 275/279 Fox photos processed ($10.50)
- Codex P1 fixes: cache poisoning, skip-existing safety
- 96 new tests

## What Session 143 Found Needs Fixing

### GEDCOM Context Gaps (AD-234)
1. **Rose (2nd wife) missing** — either not in March 11 GEDCOM export or not linked. New GEDCOM available at `~/Downloads/gedcom_20260328/`
2. **Alternate birth year used** — Albert shows "abt 1896" instead of primary 1892
3. **Esther's death date not in context** — she died Jun 11, 1966 per GEDCOM but context builder doesn't include spouse death dates
4. **No spouse timeline** — context just lists one spouse, no chronological sequence
5. **No structured relationship blocks** — free-form GEDCOM dump instead of clear CONFIRMED/KNOWN sections

### Identity Linking Needed
- Rose → "Rose Weiss Baygel Fox" (Albert's wife #2)
- Jean → "Jean Baumann Kassel Fox" (Albert's wife #3)
- Both need GEDCOM face links after import

### Photos Needing Re-Run (AFTER enrichment)
- **83 photos**: Session 142 batch — have dates but missing GEDCOM context, evidence, reasoning, scene
- **4 photos**: Session 143 timeouts — never processed
- **Total**: 87 photos, fits in 250 RPD daily limit

### Anchor Photo Refinement (AD-233)
- Three-model test showed Gemini Chat strongest at relative age comparison
- Codex disagreed (interpreted fuller face as younger vs matured)
- Human-in-the-loop required — implement as admin tool, not automated
- Dormant multi_pass.py scaffold exists

## Past GEDCOM Import Issues
Check these lessons before importing:
- Previous imports may have reset face links
- Row counts must be verified before/after
- Snapshot existing data before destructive import
- The importer at `rhodesli_ml/importers/gedcom_parser.py` handles the .ged file

## Key Files
- `rhodesli_ml/gedcom_context.py` — builds GEDCOM context string for Gemini prompts
- `rhodesli_ml/importers/gedcom_parser.py` — parses .ged files
- `scripts/run_combined_pipeline.py` — build_gedcom_context() + load_gedcom_data()
- `scripts/batch_gemini_for_person.py` — batch runner
- `~/Downloads/gedcom_20260328/` — latest GEDCOM export
- `docs/feedback/session-143-feedback-interactive.md` — user feedback with full context
- `docs/session_context/session-143-anchor-comparison-prompt.md` — anchor test prompt + results
