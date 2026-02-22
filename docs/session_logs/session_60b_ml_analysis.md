# Session 60 ML Analysis

Prepared: 2026-02-22
Analyst: Claude Opus 4.6 (research-only session, no code changes)

---

## What Was Built

Session 60 (v0.63.0) created three new ML artifacts and 55 ML tests.

**Source code (3 files, 873 lines):**
- `rhodesli_ml/gemini_config.py` (79 lines) -- Centralized Gemini model names, pricing tables, API key accessor
- `rhodesli_ml/utils/api_logger.py` (223 lines) -- Per-call JSON logging with cost tracking and result-to-result comparison
- `rhodesli_ml/scripts/progressive_refinement.py` (571 lines) -- Fact gathering, enriched prompt construction, mock/real pipeline runner

**Test code (3 files, 721 lines):**
- `rhodesli_ml/tests/test_config.py` (94 lines, 10 tests)
- `rhodesli_ml/tests/test_api_logger.py` (283 lines, 17 tests)
- `rhodesli_ml/tests/test_progressive_refinement.py` (344 lines, 20 tests)

**Generated data:** `rhodesli_ml/data/refinement_results.json` (3 mock results) and 3 API log entries -- all from mock dry-run, not real Gemini calls.

**NOT created (referenced but missing):** AD-136, AD-137, AD-138 are cited in source code comments, session log, and CHANGELOG, but were never written into `docs/ml/ALGORITHMIC_DECISIONS.md`. The file's next counter is still at AD-136.

---

## How the Progressive Refinement Pipeline Works

```
identities.json ──┐
photo_index.json ──┤
relationships.json ┼──→ gather_facts_for_photo() ──→ build_enriched_prompt() ──→ Gemini API ──→ compare_analyses()
annotations.json ──┤                                                                              │
date_labels.json ──┘                                                                              ↓
                                                                                          refinement_results.json
```

1. **Load data** -- 5 JSON files: identities, photo_index, date_labels, relationships, annotations.
2. **Find eligible photos** -- Photos where at least one CONFIRMED identity has an anchor face. Sorted by fact count descending.
3. **Gather facts** -- For each photo: confirmed people + birth years + GEDCOM relationships + approved annotations.
4. **Build enriched prompt** -- 2,600-char template with domain expertise + verified facts section.
5. **Call Gemini or mock** -- Mock returns hardcoded response. Real mode calls `call_gemini()`.
6. **Compare** -- Diffs old vs new: decade changes, confidence changes, range narrowing.
7. **Log and save** -- Per-call JSON logs + aggregated results file.

### What an enriched prompt looks like (top photo, 19 facts)

```
CONFIRMED IDENTITIES in this photo:
  - Victoria Cukran Capeluto (born 1918)
  - Victoria Capuano Capeluto (born 1905)
  - Big Leon Capeluto (born 1902)
  - Moise Capeluto (born 1904)

KNOWN RELATIONSHIPS:
  - Big Leon Capeluto <-> Victoria Capuano Capeluto (spouse)
  - Big Leon Capeluto <-> Selma Capeluto (parent child)
  - Big Leon Capeluto <-> Nace Capeluto (parent child)
  - Big Leon Capeluto <-> Betty Capeluto Fox (parent child)
  ... (11 relationships total)

COLLECTION: Betty Capeluto Miami Collection
```

The prompt instructs Gemini to cross-reference birth years with apparent ages: "If someone born in 1905 appears to be ~30 years old, the photo is circa 1935."

### Critical gap in real mode

When `mock=False`, `run_refinement()` calls `call_gemini()` from `generate_date_labels.py`, which uses its OWN hardcoded prompt -- NOT the enriched prompt with birth years and relationships. The enriched prompt is built and logged but never sent to the API.

- **Mock mode:** Demonstrates the concept correctly (enriched prompt + comparison).
- **Real mode:** The enriched prompt is discarded. The API call uses the original un-enriched visual-only prompt. The "progressive refinement" does not actually happen.

**This is the most important finding.** The pipeline is well-designed scaffolding that does not yet deliver its core capability.

---

## The 41 Eligible Photos

A photo is eligible when a CONFIRMED identity has an anchor face in it. Of 271 photos and 54 confirmed identities, exactly 41 photos qualify. All 271 already have Gemini date labels, so these 41 are where the system has both identity AND date data.

**Fact count distribution:**

| Facts | Photos | Description |
|-------|--------|-------------|
| 19 | 4 | 4 Capeluto family members + 11 GEDCOM relationships |
| 16 | 1 | 3 confirmed people + 10 relationships |
| 10-12 | 7 | 2-3 confirmed people with relationships |
| 7 | 8 | 1-3 confirmed people, some with relationships |
| 2-5 | 17 | Single person with birth year, maybe 1 relationship |
| 2 | 4 | Minimal: 1 person + birth year, or 2 people without birth years |

**Verified fact sources:** 54 confirmed identities (39 with birth years, range 1832-1975), 19 GEDCOM relationships (14 parent-child, 5 spouse), 6 approved community annotations. Relationships are concentrated in the Big Leon Capeluto family tree, which is why photos with those family members accumulate 10-11 relationship facts.

---

## What the Tests Verify

**test_config.py (10 tests):** Model defaults, pricing schema with required fields, `get_model_pricing()` known/unknown, `get_api_key()` error handling, env var overrides, legacy model preservation, cost_tracker integration.

**test_api_logger.py (17 tests):** Log file creation with correct fields, verified facts storage, previous-result comparison (decade/confidence diffs), cost math ($1.25/M input tokens), prompt hashing for >5000 chars, load/filter/limit, cost summary aggregation, invalid JSON handling, previous result retrieval.

**test_progressive_refinement.py (20 tests):** Fact gathering (finds confirmed, excludes INBOX/merged, extracts birth years, gathers relationships/annotations, counts correctly). Prompt building with/without facts, annotation inclusion. Comparison engine (no-change, decade shifts, confidence improvements/regressions, range narrowing). Eligibility ranking. Mock pipeline produces expected fields. Missing API key returns None. Safety defaults (dry-run limit=3, max cost=$1.00).

**NOT tested:** The real API call path (lines 398-415). Whether `call_gemini()` receives the enriched prompt (it does not). Integration with web app. Cost cap batch reduction.

---

## Ground Truth State

| Metric | Count |
|--------|-------|
| Total identities | 775 (54 confirmed, 403 inbox, 0 proposed, 113 merged) |
| Confirmed with birth year | 39 of 54 |
| Total photos | 271 across 8 collections |
| Photos with confirmed identities | 41 |
| Gemini date labels | 271 (262 gemini-3-flash-preview, 9 gemini-2.5-flash) |
| Human-corrected date labels | 0 |
| CORAL (local model) labels | 0 (only used for uploads, never run retroactively) |
| GEDCOM relationships | 19 |
| Approved annotations | 6 |

---

## What Running This For Real Would Produce

**What would happen today:** 41 photos identified correctly. But `call_gemini()` runs with the ORIGINAL prompt (not enriched), so you get 41 new visual-only estimates. Changes would reflect model version differences (flash vs pro), not verified facts. Results saved to `refinement_results.json` and api_logs.

**What would NOT happen:** Web app would not pick up results (nothing in `app/main.py` reads `refinement_results.json`). Date labels on the site would not change. Admin would not see suggestions (correction flow is manual pencil-icon only).

**Cost:** $1.31 for 41 photos with gemini-2.5-pro ($0.032/photo), or $0.45 with flash ($0.011/photo).

**Existing mock results examined:** The 3 api_logs entries all contain the same hardcoded mock response (decade 1940, year 1942). The "comparison" section correctly shows a decade shift (1950s to 1940s) by diffing the mock against the real existing label. The existing label for the top photo (inbox_b5e8a89e_9) was originally 1950s from gemini-3-flash-preview, based on visual analysis of a wedding photo with white dinner jackets. Birth year math (people born 1902-1918 appearing in their 30s-40s) would suggest 1940s instead, which is exactly what the enriched prompt is designed to test.

---

## What Moved the Needle -- Honest Assessment

**Genuinely new:** Centralized Gemini config (real maintainability win). API logging with cost audit trail. Fact-gathering logic that identifies the 41 richest photos. The enriched prompt template (the core intellectual contribution).

**Scaffolding without real capability yet:** The pipeline cannot send enriched prompts to Gemini. Mock results are identical for all photos. Comparison engine has nothing real to compare. No connection to the web app.

**Unchanged from Session 57/58:** CORAL model, MLflow registry, web app date display, production date labels.

**Bottom line:** Session 60 ML work is a well-designed framework that is about 60% complete. The remaining 40% -- sending enriched prompts and feeding results to the web app -- is the part that matters most.

---

## Recommended Next Steps

| # | Step | Effort | Cost | Impact |
|---|------|--------|------|--------|
| 1 | **Fix enriched prompt gap** -- make `run_refinement()` send the enriched prompt to Gemini (modify `call_gemini()` to accept prompt override, or call API directly) | 30 min | $0 | Critical -- without this, nothing works |
| 2 | **Real 3-photo test** -- run on the top photo (inbox_b5e8a89e_9, 19 facts, existing label says 1950s, birth year math says 1940s) | 10 min | $0.10 | Validates the concept |
| 3 | **Build results-to-web bridge** -- script/endpoint to merge refinement results into date_labels.json for admin review | 1-2 hrs | $0 | Makes results visible |
| 4 | **Full 41-photo batch** -- expect meaningful improvements for ~20 photos with 7+ facts | 15 min | $1.31 | Real improved date estimates |
| 5 | **Write AD-136/137/138** -- they are referenced everywhere but do not exist | 15 min | $0 | Documentation hygiene |
| 6 | **CORAL retroactive run** -- run local model on all 271 photos, compare to Gemini | 1 hr | $0 | Free independent validation |

Total estimated cost for steps 1-4: approximately $1.41.
