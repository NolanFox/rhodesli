# Session 94 — Branch Analysis: session-82c/gemini-rerun

**Date**: 2026-03-09
**Branch**: `session-82c/gemini-rerun`
**Diverged from main at**: `9dad59f` (session 82 prompts/context)
**Commits on branch (not on main)**: 14

## Summary

The branch can be closed. All valuable work has been re-implemented on main
through Sessions 83-93, with better architecture (Supabase-backed, not JSON).

## Commit Analysis

| Commit | Description | Status on Main |
|--------|-------------|----------------|
| `bd637b0` | Session 82c phase 0 — gemini state audit | Superseded by Session 89 (AD-201/202) |
| `9e6be21` | Asheville litmus test — 3 GEDCOM variants | Finding captured in AD-148 (Session 61C); refined in AD-159 (Session 65b) |
| `0cfef61` | AD-194 gemini GEDCOM enrichment assessment | AD-194 reassigned to "Inline Find Similar" on main (Session 84). GEDCOM enrichment decisions captured in AD-148, AD-159, AD-211 |
| `aeeaf04` | Gemini enrichment batch pipeline with budget gates | Superseded by `scripts/batch_analyze.py` + `scripts/process_batch_results.py` on main |
| `71aefaf` | Surface gemini enrichment results with gatekeeper | Main uses Supabase `gemini_api_calls` table + admin re-analyze button (AD-202) instead of JSON proposals |
| `b10e617` | Session 82c complete — enrichment pipeline | Session log; branch never merged |
| `45a7ee6` | Add session 82c to docs/sessions/ for stop hook | Stop hook artifact |
| `f4bfdcd` | Auto-fix session review concerns | Minor doc fixes |
| `f1c0128` | Sync production data changes | Data sync; stale |
| `59bd08e` | Cherry-pick fastcore pin from main | Already on main |
| `195f967` | Hotfix changelog + lesson 100 | Already on main |
| `382dd10` | Session 82a audit report | Historical doc (brainstorming). Many ideas implemented: masonry grid (82e), help needed page (82e), identify mode (82e), share for help (82e) |
| `9fad706` | Competitor UX analysis | Historical doc |
| `025fb46` | Session 82a ideation doc | Historical doc; 30 ideas, ~15 shipped in later sessions |
| `2eb3d24` | Phase 3, 4, 5 UX audit deliverables + mockups | 5 mockup PNGs + implementation plan. Most proposals already shipped. |

## Key Unique Assets (Not on Main)

1. **`scripts/asheville_litmus_test.py`** (482 lines) — Controlled experiment script.
   The findings are already on main (AD-148). The script itself is a one-shot experiment, not reusable.

2. **`scripts/run_gemini_enrichment.py`** (514 lines) — Batch enrichment with budget gates.
   Superseded by `scripts/batch_analyze.py` on main, which uses the unified extraction architecture (AD-143) and logs to Supabase.

3. **`scripts/stage_enrichment_proposals.py`** (231 lines) — JSON-based Gatekeeper staging.
   Main uses Supabase + admin re-analyze button instead. The JSON proposal pattern was not adopted.

4. **`data/enrichment_proposals.json`** (758 lines) — 82c batch results as proposals.
   Stale. Session 93 re-ran all 72 GEDCOM-eligible photos with better results (AD-211).

5. **`tests/test_enrichment_proposals.py`** (599 lines) — Tests for the JSON proposal UI.
   Tests a pattern (JSON proposals + app/main.py UI) that was never adopted on main.

6. **`results/asheville_litmus_test.json`** + **`results/enrichment_82c_batch1.json`** — Raw experiment data.
   Historical interest only. Session 93 produced the definitive batch results.

7. **5 mockup PNGs** in `docs/assessments/mockups/` — UX ideation mockups from 82a.
   Historical interest. Most concepts already shipped.

8. **Session 82a docs** (ideation, audit report, competitor analysis, implementation plan, top proposals).
   Brainstorming artifacts. Many ideas implemented in Sessions 82e-93.

## AD Numbering Conflict

The branch used AD-194 for "Gemini GEDCOM Enrichment — Curated Variant Validated."
On main, AD-194 is "Inline Find Similar Expansion Panel" (Session 84).
The 82c findings are distributed across AD-148, AD-159, AD-192, AD-211 on main.

## Cherry-Pick Decision

**Nothing to cherry-pick.** All valuable work is already on main:
- Asheville litmus test finding → AD-148 (curated GEDCOM optimal)
- Batch enrichment pipeline → `scripts/batch_analyze.py` (unified architecture)
- Gatekeeper UI for results → Admin re-analyze button + Supabase logging
- 82a UX ideas → Most shipped in Sessions 82e-93
- Batch results → Session 93 re-ran all 72 photos with better methodology

## Recommendation

Delete the branch. The 14 commits represent work that was correctly
re-implemented with better architecture (Supabase over JSON, unified
extraction over ad-hoc scripts) in subsequent sessions.
