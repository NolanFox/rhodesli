# Session 90b Planning Context

**Predecessor**: Session 90 (v0.92.2, commit 42caecd)
**Prompt**: `docs/prompts/session-90b-prompt.md`
**Date**: 2026-03-06

---

## Origin: Nolan's Feedback After Session 90

Nolan reviewed Session 90 output and identified these issues:

### 1. Upload Date Sorting is BROKEN on Production (P0)
**Screenshots confirm**: Switching between "Upload Date (Newest)" and "Upload Date (Oldest)" on `/photos` page does NOT rearrange photos. Both sort orders show Image 001, 054, 006, 053 as the first row.

**Root cause analysis**:
- `_sort_photos()` at `app/main.py:15576` looks logically correct
- Upload date distribution is heavily skewed: 155 photos at `2026-02-10`, 114 at `2026-02-14`, 24 at `2026-03-05`
- For `upload_newest`, the 24 March 5 photos should appear first — but they DON'T
- Possible causes:
  - `_photo_cache` doesn't include `upload_date` for photos where `get_metadata(sha256_id)` fails due to ID mismatch (inbox_* vs SHA256 keys)
  - Production `_photo_cache` wasn't rebuilt after deploy (stale in-memory cache)
  - Data reached photo_index.json but `_build_caches()` at line 3002 doesn't propagate `upload_date` to `_photo_cache` for all photos
- **Key code path**: `_build_caches():3072-3074` calls `photo_registry.get_metadata(photo_id)` which only works if `photo_id` matches a key in photo_index.json. For community uploads, photo_index.json uses `inbox_*` IDs but `_photo_cache` uses SHA256 IDs.
- **THIS MUST BE BROWSER-VERIFIED WITH CLAUDE CHROME. No exceptions.**

### 2. Photo Page Metadata Gaps (P1)
Photo page for `a75e6b54b0eb6c50` is missing:
- **Upload person** (who uploaded — e.g., Claude Benatar's email)
- **Upload date** display (no photo page shows upload date)
- **ML enrichment**: No date estimate, no face coordinate analysis, no location estimate
- **Map/Timeline links**: No connection to Map, Timeline, Tree pages from photo page

The Benatar photo specifically needs full Gemini analysis run: date estimation, location estimation, face-targeted age estimation. This was supposed to happen automatically on upload but didn't.

### 3. a75e6b54b0eb6c50 Status (Clarification)
- **Session 90 prompt** said to delete this as a "phantom duplicate"
- **Session 90 assessment** flagged it as a red flag (not cleaned)
- **Reality from Nolan**: "It seems that was already all addressed" — the photo page works, Person 877 is there
- **Local state**: NOT in local `photo_index.json`. The real Benatar photo is `inbox_0c57277a_0_unknown` (path: `raw_photos/unknown.jpg`)
- **Production**: Returns 200 with face detected + Person 877
- **ACTION**: DO NOT DELETE. Nolan shared this link with Claude Benatar. Keep it working.
- **Investigation needed**: Understand why it exists on production but not locally (likely the cleanup_isolated_photo script was never run, or production has a different photo_index.json state)

### 4. main.py Refactor (Overdue)
- **34,384 lines** — the largest file by far
- Track A in Session 90 stalled (subagent failed silently)
- Upload routes were lost TWICE during merges
- Blocks parallel worktree development (Lesson 88)
- Extracted so far: `compare_routes.py` (4,875 lines), `estimate_routes.py` (1,351 lines)

### 5. Supabase Migration Progress Needed
- PRD-027 written but no implementation started
- User wants: "Within a few sessions I want all of the data logged"
- Currently in Supabase: identity_overrides, annotations, relationships, gedcom_*, face_gemini_alignments, gemini_api_calls
- NOT in Supabase: identities.json, photo_index.json, embeddings.npy, date_labels.json, photo_locations.json, birth_year_estimates.json

### 6. Website Performance
- User reports: "It really seems a lot slower than it should"
- Session 90 added: `loading="lazy"` on images, CDN preconnects
- Remaining suspects: 294 photos rendered at once (no pagination), full embeddings.npy (~2.3MB) loaded at startup, `_build_caches()` iterates all photos synchronously, Supabase calls during page render
- Need to profile and identify top 3 bottlenecks

### 7. Hook Issues
- **Stop hook bug**: Checks for `docs/sessions/SESSION_0${S}.md` but actual path is `docs/session_logs/session-NN-log.md`
- **Orphaned hook scripts**: `session-stop-gate.py`, `session-stop-gate.sh` in `.claude/hooks/` but not referenced in `settings.json`
- **Test gate**: Works but `scripts/test-gate.sh` runs on every git commit — need to verify it's not adding unnecessary overhead
- User: "We've been having a lot of issues with our hooks. Please make sure they are in a good place."

### 8. Testing Gaps
- 21 flaky xdist tests remain
- Test count: ~3630 (target was <2500)
- Test runtime: ~5 min (target was <3 min)
- Session 90 removed 245 tests but more pruning needed

---

## Key File Reference

| File | Lines | Purpose |
|------|-------|---------|
| `app/main.py` | 34,384 | Monolithic web app — NEEDS REFACTORING |
| `app/compare_routes.py` | 4,875 | Compare routes (already extracted) |
| `app/estimate_routes.py` | 1,351 | Estimate routes (already extracted) |
| `app/supabase_data.py` | 580 | Supabase functions |
| `core/photo_registry.py` | ~300 | PhotoRegistry class |
| `data/photo_index.json` | — | 295 photos, 982 faces |
| `data/identities.json` | — | ~777 identities |
| `.claude/settings.json` | 52 | Hook configuration |
| `docs/prds/027_data_migration.md` | — | Migration plan (draft) |

---

## Nolan's Exact Feedback (Preserved)

> "RE: upload date and sorting. No photo page has upload date visible. Additionally, sorting on the photos page appears to be completely broken. This is a HUGE miss. Did you event test this on the website. A frontend or ux change like this NEEDS to be tested with claude chrome. No exceptions."

> "Regarding a75e6b54b0eb6c50 and person 877, it seems that that was already all addressed. The fact that you cited that as undone work makes me skeptical that the rest of your assessment of what was left undone is incorrect."

> "The photo page does not have upload person (Claude benatar's email), the date upload, or any of the ML enrichment present (I think you probably need to run the full ML as well as the gemini prompt with 3.1 pro with both the photo date estimate, the face coordinates for targeted person age estimate, and the location estimate prompts). Then you should be able to link this to the map, timeline, etc. This looks incomplete."

> "We have talked about fixing testing and breaking up main.py A LOT. Finally get it done."

> "I also want you to make progress on the supabase migration. Within a few sessions I want all of the data logged."

> "Take one more pass at website performance. It really seems a lot slower than it should."

> "Please make sure [hooks] are in a good place."

> "Please keep our roadmap and other documents in mind / updated as we build this out. Don't forget to properly breadcrumb things."

---

## Session 90 Red Flags (Re-evaluated)

| Red Flag | Session 90 Status | 90b Action |
|----------|-------------------|------------|
| Phantom photo a75e6b54b0eb6c50 | "NOT CLEANED" | KEEP IT — user shared link with community |
| Upload routes lost during merge | Fixed (95a8db1) | Prevent via main.py refactor |
| Upload date sorting | "DEPLOYED + VERIFIED" | ACTUALLY BROKEN — fix and browser verify |
| Auto-compacted (4th time) | Hooks simplified | Verify hooks are correct |
| 21 flaky xdist tests | Pre-existing | Fix |
| Test count 3630 (target 2500) | 245 removed | Continue pruning |
| Test runtime ~5 min (target 3 min) | Subprocess elimination | Continue optimization |

---

## Breadcrumbs

- **Predecessor context**: `docs/session_context/` (no session 90 context exists)
- **Session 90 prompt**: `docs/prompts/session-90-prompt.md`
- **Session 90 assessment**: `docs/assessments/session-90-assessment.md`
- **Session 90 log**: `docs/session_logs/session-90-log.md`
- **PRD-027 (migration)**: `docs/prds/027_data_migration.md`
- **BACKLOG**: `docs/BACKLOG.md` — FB-40-22 (upload attribution), Postgres migration item
- **Lessons**: `tasks/lessons.md` — especially Lesson 88 (main.py blocks parallel), Lesson 97 (visual verification), Lesson 94 (wait for deploy)
