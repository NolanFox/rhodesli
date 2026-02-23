# Session 64b Assessment
## "Execute What 64 Deferred"

- **Duration**: ~90 minutes
- **Phases**: 7/7 completed
- **Tests**: +8 new (GEDCOM context builder), 3468 total (2930 app + 538 ML)
- **Commits**: 4 feature/test commits + 1 docs commit + 1 self-assessment = 6 total
- **Version**: v0.67.1

## Shipped

- [x] Phase 1: Supabase tables created — `face_gemini_alignments` + `gemini_api_calls` tables executed via psycopg2 (psql unavailable locally). Verified via Supabase REST API.
- [x] Phase 2: 127 face alignments migrated from JSON to Supabase — 0 failures. App code (`load_alignments()` in `app/face_alignment.py:519`) already reads Supabase-first with JSON fallback.
- [x] Phase 3: GEDCOM context builder implemented — `_build_parsed_gedcom_from_supabase()` builds full ParsedGedcom object graph from Supabase. Handles individuals, events, relationships, family reconstruction. 8 new tests.
- [x] Phase 4: Dry-run combined pipeline on 3 strategic photos — All 3 success. GEDCOM-enriched: 1 (Betty/Victoria/Moise Capeluto photo). 10 API calls logged to `gemini_api_calls` table. Fixed 3 bugs: column name mismatch, Supabase pagination limit, identity JSON envelope unwrapping.
- [x] Phase 5: Production deploy + smoke test — All 7 routes return 200. Photo pages load with face card markers (6 on Vida Capeluto photo).
- [x] Phase 6: AD-153 through AD-157 documented. ROADMAP.md, SESSION_HISTORY.md updated.
- [x] Phase 7: Self-assessment (this document).

## Session 63 Concerns — Final Status

| # | Concern | Status | Evidence |
|---|---------|--------|----------|
| 1 | Face alignment stored in JSON, not Supabase | **RESOLVED** | 127 records migrated to `face_gemini_alignments` table. App reads Supabase-first (`load_alignments()` line 519). JSON is fallback cache only. |
| 2 | 144 photos rate-limited, need re-run | **PARTIAL** | Combined pipeline + batch retry infrastructure ready (`--retry-failed` flag). Not yet executed — needs API key budget + scheduling. |
| 3 | "Combined pipeline" unclear | **RESOLVED** | `scripts/run_combined_pipeline.py` sends coordinates + GEDCOM context in single Gemini call. Centralized model config. Batch retry support. |
| 4 | Vida Capeluto not tested | **RESOLVED** | Photo `b9f591a56e25b71a` (Image 924, 6 faces) processed in dry-run. Alignment succeeded. Production photo page verified with 6 face card markers. |
| 5 | Calibrated scores not in UI | **RESOLVED (Session 64)** | Session 64 wired calibrated scores into compare/match display. Verified in production. |
| 6 | Recalibration hooks dead | **RESOLVED (Session 64)** | Session 64 wired `on_face_merge`, `on_match_reject`, `on_identity_confirm` into app merge/identify endpoints. |
| 7 | Cost suspiciously low | **RESOLVED** | `gemini_api_calls` table now tracks every call with model, tokens, cost, status. 10 calls logged during dry-run. Future runs will have full cost audit trail. |

## Bugs Found & Fixed During Session

1. **Column name mismatch** (`gedcom_xref` vs `gedcom_id` in `gedcom_face_links` table) — silently swallowed by broad except. Fixed in `load_gedcom_data()`.
2. **Supabase default 1000-row pagination** — Only loaded 1000 of 21,809 individuals. Added pagination loops with `.range(offset, offset+999)` for all three GEDCOM tables.
3. **Identity JSON envelope not unwrapped** — `build_gedcom_context()` received `{schema_version, identities, history}` instead of the inner identities dict. Added unwrapping logic.
4. **Test mocks didn't handle `.range()` chain** — Rewrote mock using `mock_table` function dispatch.

## Deferred

- **144 rate-limited photos**: Infrastructure ready (`--retry-failed` flag + combined pipeline), but not executed. Needs API key budget decision and scheduling.
- **OPS-001 Custom SMTP**: Code ready, needs RESEND_API_KEY in Railway env var. Not in scope for this session.

## Red Flags

- **LOW**: Broad `except Exception` in `load_gedcom_data()` silently caught the column name bug. Consider narrowing exception handling in GEDCOM loading paths.
- **LOW**: The `_build_parsed_gedcom_from_supabase` function loads ALL 21,809 individuals + 145K relationships into memory. Fine for Rhodes (single community), but won't scale for multi-tenant without query scoping.

## Remaining for Session 65

1. Retry 144 rate-limited photos with combined pipeline
2. OPS-001: Custom SMTP (add RESEND_API_KEY to Railway)
3. FE-041: "Help Identify" mode for non-admin users
4. ML-053: Multi-pass Gemini for low-confidence re-labeling
5. PRODUCT-002: Face Compare Tier 2 shared backend

## Recommended Session 65 Priorities

1. **Retry 144 photos** — Combined pipeline + batch retry infrastructure is ready. Just needs execution. This completes alignment coverage from 47% to 100%.
2. **FE-041: Help Identify mode** — Highest product value for community engagement. Enables non-admin users to contribute identifications.
3. **Multi-pass Gemini (ML-053)** — Use the 10 logged API calls + 127 alignments to identify low-confidence results that benefit from re-analysis.

## Next Session Should Verify FIRST

1. Both Supabase tables (`face_gemini_alignments`, `gemini_api_calls`) still exist and have data
2. Combined pipeline dry-run still works (no model deprecation)
3. Production photo pages still show face card markers
4. Test count hasn't regressed (expect 3468+)

---
*Predecessor: [Session 64 Assessment](docs/session_context/session_64_assessment.md)*
*Prompt: [docs/prompts/session-64b-prompt.md](docs/prompts/session-64b-prompt.md)*
