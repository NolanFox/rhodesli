# Session 143 Context

**Predecessor**: Session 142 (docs/session_context/session-142-batch-failure-postmortem.md)
**Date**: 2026-03-28
**State**: v0.99.54, 3846 tests, site healthy but data display issues

---

## Critical State Summary

### Session 142 Delivered
- 12 UX feedback fixes (FB-001–012) — all deployed and browser-verified
- 3 Codex P1 security fixes (CSRF, merge side effects, rematch target)
- Batch Gemini script with GEDCOM preload, quota early-stop, Supabase sync
- PRD-059 temporal co-occurrence: event grouping script, admin UI page, research
- 4 Codex audits, Lessons 159-162, new harness rule (batch-data-pipeline.md)

### Session 142 Left Broken
1. **84 Fox Family photos have data in Supabase but photo page doesn't render all fields** — face_analysis, group_composition, scene_description ARE in the JSONB `data` column but the photo page template doesn't read them from the new format
2. **195 Fox Family photos still need Gemini analysis** — blocked by free tier quota (250/day). Need billing enabled (Tier 1: 1,500/day, ~$15 total)
3. **82 of 84 Fox photos lack GEDCOM context** — overnight batch timed out on Supabase GEDCOM loading. Preload fix implemented but photos need re-run
4. **Rhodes re-analysis data gap** — Victoria Capeluto and other Rhodes photos had AI analysis done through web UI that stored on Railway volume JSON only, NOT in Supabase. When app switched to reading Supabase first, these became invisible. Need to sync Railway volume date_labels.json → Supabase
5. **"Conflicting face assignment" / "Needs review" badges** on Victoria's photos — pre-existing candidate face assignments, not from Session 142

### Gemini API Situation
- **Model**: gemini-3.1-pro-preview (confirmed correct)
- **Free tier**: 250 requests/day — insufficient for 279-photo batch
- **Paid Tier 1**: 1,500/day, $0/month, pay-per-use (~$0.055/photo)
- **Action needed**: Enable billing at https://aistudio.google.com/apikey
- **Prompt improvements ready**: capture_vs_print, scene_description, reasoning_summary added to "full" preset (AD-231)
- **GEDCOM preload ready**: loads tree once, not per-photo (~30 min batch vs 6h)
- **Quality check ready**: first-result verification for GEDCOM, face coords, all fields
- **Supabase sync ready**: upserts to date_labels table on each successful result

### Photo Page Rendering Issue
The photo page reads date labels via `_load_date_labels()` which returns `{photo_id: data}`. The `data` dict for batch labels has a different structure than what the page template expects:
- Batch format: `{"estimated_decade": 1910, "face_analysis": [...], "location_estimate": {...}}`
- Old format: `{"estimated_decade": 1910, "location": {...}}` (location key differs)
- The page template checks specific keys — need to audit which keys it reads vs which the batch produces

### Key Files
- `scripts/batch_gemini_for_person.py` — batch Gemini with GEDCOM preload + Supabase sync
- `scripts/event_grouping.py` — temporal event grouping
- `app/temporal_routes.py` — event groups admin page
- `rhodesli_ml/gemini_extraction.py` — improved "full" preset
- `rhodesli_ml/data/date_labels.json` — 353 local labels
- `rhodesli_ml/data/event_groups.json` — 8 event groups, 3 companions
- `docs/session_context/session-142-batch-failure-postmortem.md` — full postmortem
- `docs/session_context/session-142-co-occurrence-analysis.md` — GEDCOM cross-reference
- `docs/session_context/session-142-prompt-comparison.md` — old vs new prompt
- `docs/session_context/session-142-codex-prompt-audit.md` — Codex P0/P1 findings

### Lessons from Session 142
| # | Summary |
|---|---|
| 159 | Always verify deploy health before ending session |
| 160 | Batch scripts must verify logging on first call |
| 161 | Verify FULL output quality on first batch call |
| 162 | Batch outputs must write to Supabase, not local JSON |

### BACKLOG Items from Session 142
- BATCH-001 (P2): Atomic JSON writes for date_labels.json
- BATCH-002 (P2): Already done — batch writes to Supabase now
- BATCH-003 (P1): Backfill done — 82 gemini_api_calls rows inserted
- BATCH-004 (P0): GEDCOM preload — DONE
- BATCH-005 (P1): Resume batch for remaining 195 photos — needs billing
- FB-009 (P2): Speed Loop auto-suggestion — feature gap

### Data Integrity Pattern (12th occurrence)
Session 142 is the 12th data integrity incident. Root cause is always: multiple data stores (local JSON, Railway volume, Supabase) getting out of sync. The harness now has `.claude/rules/batch-data-pipeline.md` but the broader fix (single source of truth with no fallbacks) remains unimplemented.
