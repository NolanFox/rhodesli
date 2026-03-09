# Session 95 Context: Fox MVP + Standalone Tool Suite

Predecessor: [Session 94 Context](session-94-context.md)

## Background

Session 94 produced PRD-035 (Multi-Community Platform + Fox Family MVP) through
deep interactive planning with Nolan. All feedback is captured in
`docs/session_context/session-94-fox-brain-dump.md` (9 parts of detailed requirements).

Session 94 also completed 4 background housekeeping tracks (branches ready to merge):
- `session-94/doc-sync` — BACKLOG.md updated to v0.96.0
- `session-94/ci-verify` — ruff config fixed for CI
- `session-94/branch-cleanup` — 82c branch analysis (fully superseded)
- `session-94/ux-fixes` — UX-042 source photo links, UX-134 mobile overflow

## Session 95 Goals

### Track 1: PRD-035 Phase 1 — Fox MVP (Community Infrastructure)
Build the multi-community platform foundation and get the Fox Family Archive live.

**Key requirements (from PRD-035):**
- Community model with `/c/{slug}` URL prefix routing
- Community-scoped browse, upload, identity pages
- Community CRUD for admin
- Bulk upload improvements (50→200 cap, TIFF→JPG, batch metadata)
- Community landing pages (per-community hero, stats)
- Migration: tag all existing Rhodes data with `rhodes` community_id
- Backward compatibility: existing URLs redirect to `/c/rhodes/...`
- Community boundary UX: users NEVER accidentally cross into another community

**Critical UX constraint (from Nolan):**
> "If you're coming to the platform for the Rhodes Jewish community, you should NOT
> accidentally wander into Fox family photos unless you fully understand what that is
> and intend to check it out."

### Track 2: TOOLS-001 — Standalone Tool Suite
Build date estimator and face compare as standalone, community-agnostic tools.

**Key requirements (from Nolan + PRD-034):**
- Date estimator standalone page at `/tools/estimate`
- Face compare standalone page at `/tools/compare`
- Tools hub/landing at `/tools`
- Shared navigation bar across all tools (consistent links at top)
- Community-agnostic language (works for any photo, not just Rhodes)
- Consistent URL paths and visual design
- Think of it like the existing sharing pages but for ML tools

**Current state:**
- `/estimate` exists — full Gemini date/location estimation, works well
- `/compare` exists — full face comparison workspace, works well
- Both currently use Rhodes-specific branding in places
- No shared tool navigation between them
- No tools hub/landing page

## File Conflict Analysis (Verified Safe for Parallel)

| Track 1 Files | Track 2 Files | Overlap |
|---------------|---------------|---------|
| `app/page_routes.py` | `app/estimate_routes.py` | NONE |
| `app/upload_routes.py` | `app/compare_routes.py` | NONE |
| `app/admin_routes.py` | New: `app/tools_routes.py` | NONE |
| `app/main.py` (middleware) | No changes to main.py | NONE |
| `app/supabase_data.py` | No changes | NONE |
| New migration scripts | No changes | NONE |

**Safe to parallelize via worktrees.**

## Technical Context

### Community Infrastructure (Track 1)

**Supabase tables that already exist:**
- `communities` — seeded with Rhodes (Session 91)
- `gedcom_versions` — has `community_id` field
- `identities`, `photos` — have `community_id` columns

**Tables to create:**
- `photo_communities` — many-to-many (photo can be in multiple communities)
- `identity_communities` — many-to-many with `is_primary` flag
- `upload_batches` — source/date/location metadata per batch

**Schema details:** `docs/prds/035_multi_community/DATA_MODEL.md`

**Community routing approach:**
- Middleware extracts community slug from URL prefix `/c/{slug}`
- Sets `request.state.community` for downstream route handlers
- Routes filter queries by `community_id`
- Existing URLs without `/c/` prefix default to Rhodes community

**Backward compatibility strategy:**
- `/browse` → `/c/rhodes/browse` (302 redirect or serve directly as Rhodes)
- `/identify/{id}` → `/c/rhodes/identify/{id}`
- All existing share links continue to work
- Facebook community links continue to work

### Standalone Tools (Track 2)

**Current route structure:**
- `/estimate` — date/location estimator (estimate_routes.py)
- `/compare` — face comparison workspace (compare_routes.py)

**Target route structure:**
- `/tools` — tools hub landing page
- `/tools/estimate` — date/location estimator (standalone, community-agnostic)
- `/tools/compare` — face comparison (standalone, community-agnostic)
- Old `/estimate` and `/compare` URLs redirect to `/tools/...`

**Shared tool navigation bar:**
```
┌──────────────────────────────────────────────────────┐
│  [Tools Hub]  |  [Date Estimator]  |  [Face Compare] │
└──────────────────────────────────────────────────────┘
```
Similar to how the Rhodes sharing pages have navigation links at the top.

### Upload Pipeline (Track 1)

**Current limits (upload_routes.py:345-347):**
```python
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file
MAX_FILES_PER_UPLOAD = 50
```

**Changes needed:**
- Raise `MAX_FILES_PER_UPLOAD` to 200
- Add TIFF detection + Pillow conversion to JPG (95% quality)
- Add batch metadata form (source, date_range_hint, location_hint, notes)
- Client-side chunked upload (groups of 20) with progress bar
- Store batch info in `upload_batches` table

## Merge Order for Session 94 Branches

Before starting new work, merge the 4 Session 94 branches:
```bash
./scripts/merge.sh session-94/doc-sync session-94/ci-verify session-94/branch-cleanup session-94/ux-fixes
```
Order: docs → CI → branch cleanup → UX fixes (least → most code impact).

## Key Documents to Read

| Document | Why |
|----------|-----|
| `docs/prds/035_multi_community_platform.md` | The PRD for this session |
| `docs/prds/035_multi_community/PHASES.md` | Phase 1 acceptance criteria |
| `docs/prds/035_multi_community/DATA_MODEL.md` | Schema changes |
| `docs/prds/035_multi_community/UPLOAD_PIPELINE.md` | Upload improvements |
| `docs/session_context/session-94-fox-brain-dump.md` | All of Nolan's feedback |
| `docs/prds/034_standalone_tool_suite.md` | Standalone tools master plan |
| `docs/architecture/MULTI_TENANT.md` | Existing multi-tenant design |
| `docs/collections/fox_family_prep.md` | Fox family integration steps |

## Risk Assessment

- **Track 1 (Fox MVP):** MEDIUM risk — significant routing changes, must not break existing URLs
- **Track 2 (Tools):** LOW risk — mostly UI/branding changes to existing working tools
- **Merge conflicts:** LOW — verified zero file overlap between tracks
- **Test regressions:** MEDIUM — community routing could break existing route tests

## Deferred to Future Sessions

- PRD-035 Phase 2: Global identity + cross-community linking
- PRD-035 Phase 3: Multi-GEDCOM primary/secondary
- PRD-035 Phase 4: Scale, Google import, subdomain routing
- TOOLS-002: ML service extraction
- Context capture enrichment chat (linked to TOOLS-004)
- Actual Fox family photo upload (Nolan provides photos after infra is ready)
