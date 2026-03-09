# Session 96c Continuation — Fix Identity Sync + Browser Verify

## Context
Session 96c shipped the photo-derived community identity set (AD-216) and all infrastructure changes. But Fox Family still shows "0 identities" in production.

**What shipped (Acts 1-5):**
- Photo-derived identity set: `_get_community_identity_ids()` rewritten (app/main.py:558)
- Admin section enabled for ALL communities (removed is_rhodes gate, line 4488)
- Upload Review link in admin sidebar
- ML feature zeroing removed — proposals/discoveries/annotations computed for all communities
- `_compute_discoveries()` accepts community_identity_ids filter
- Discoveries route passes community to sidebar counts
- Landing page uses photo-derived identity count
- `add_identity_to_community()` wired into upload background ingest
- Cross-community search verified global
- 81+ community-related tests pass
- Commits: a4b17a4, be9dcff, fe2d0c6, 2eb0674, 83fe3ba, e1f1a24, 9b4749f

**What's blocking (the "0 identities" bug):**
- Debug endpoint `/api/debug/community-ids?slug=fox-family` shows:
  - 636 community photos, 635 resolve via aliases (inbox_* → SHA256)
  - **1652 faces match resolved photo IDs** — alias resolution WORKS
  - **identity_count: 0** — `get_identity_for_face()` returns None for ALL faces
- **Root cause hypothesis**: Production uses `DATA_SOURCE=postgres`. Fox Family INBOX identities (1600+ from Charlie Fox ingest, Session 96b) exist in JSON but may NOT have been synced to Supabase. The registry loads from Postgres → no Fox Family identities → face lookup returns None.

## Act 1: Diagnose Identity Sync (5 min)

1. Check how many identities are in Supabase vs JSON on production
   - `curl https://rhodesli.nolanandrewfox.com/health` shows identity count from registry
   - Compare to local `data/identities.json` identity count
2. Check if Fox Family inbox identities exist in Supabase `identities` table
   - Query for identity_ids containing "inbox_" face IDs
   - Or check total count in Supabase identities table
3. If identities are missing from Supabase:
   - The ingest pipeline (Session 96b) added faces to JSON but may not have synced to Supabase
   - Need to run sync: either `sync_from_supabase_on_startup` (pulls from Supabase) or push JSON identities TO Supabase

## Act 2: Fix Identity Sync (10-20 min)

Based on diagnosis:
- **If Supabase is missing identities**: The save_registry function should dual-write. Check if the background ingest used save_registry or wrote JSON directly. Fix by running a one-time Supabase backfill.
- **If Supabase has identities but different face IDs**: The face_id format mismatch needs debugging.
- **Alternative approach**: If DATA_SOURCE=postgres is the issue, consider making `_get_community_identity_ids` load registry from JSON as fallback when Postgres returns empty for face lookup.

## Act 3: Remove Debug Endpoint + Final Browser Verify (15 min)

1. Remove `/api/debug/community-ids` endpoint from page_routes.py
2. Browser verify all 8 checks:
   - Fox Family landing page: N identities (not 0)
   - Fox Family sidebar: Review section with non-zero counts
   - Fox Family admin section: Uploads, GEDCOM, etc.
   - Fox Family photos page: photo grid
   - Fox Family To Review: pending matches
   - Upload Review page: cluster matches
   - Search across communities: find Rhodes identity from Fox Family
   - Rhodes sidebar: unchanged, correct counts
3. Save screenshots to docs/screenshots/session-96c/

## Act 4: Assessment + Session Wrap (10 min)

1. Re-read original prompt: `cat docs/prompts/session-96c-prompt.md`
2. Write `docs/assessments/session-96c-assessment.md`
3. Update CHANGELOG.md, ROADMAP.md, BACKLOG.md
4. Final `make test-fast` — all pass
5. Create session log with per-act status

**Commit:** `docs: session 96c assessment — community-scoped review pipeline shipped`

## Key Files
| File | What to check |
|------|---------------|
| `app/main.py:558` | `_get_community_identity_ids()` — photo-derived set |
| `app/main.py:886` | `load_registry()` — DATA_SOURCE=postgres path |
| `app/supabase_data.py` | Identity sync functions |
| `app/page_routes.py:157` | Debug endpoint (REMOVE after fix) |
| `data/identities.json` | Local identity count (includes Fox Family) |
| `scripts/push_to_production.py` | How identities get to production |

## Pre-existing test failures (NOT caused by this session)
- `tests/test_community_infra.py::TestCommunityLandingPage::test_community_landing_page_with_content` — circular import, pre-existing
- `tests/e2e/test_discovery_layer.py::test_decade_filter_filters_gallery` — decade filter badge mismatch, pre-existing
