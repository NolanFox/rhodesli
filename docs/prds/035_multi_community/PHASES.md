# PRD-035: Phased Implementation Plan

**Parent:** [PRD-035](../035_multi_community_platform.md)

## Phase 1: Community Infrastructure + Fox MVP (2-3 sessions)

**Goal:** Fox Family Archive is live, browsable, and uses the ML workflow.

| Task | Description | Files | Status |
|------|-------------|-------|--------|
| Community CRUD | Admin can create/edit communities | `app/admin_routes.py` | DONE (Session 95) |
| Community routing | `/c/{slug}` URL prefix, community context in nav | `app/main.py`, middleware | DONE (Session 95) — but nav doesn't show community name |
| Community-scoped browse | Browse page filters by active community | `app/page_routes.py` | **NOT DONE** — browse shows all Rhodes photos regardless of community |
| Community-scoped upload | Upload assigns photos to active community | `app/upload_routes.py` | **NOT DONE** — upload page shows Rhodes sidebar, photos go to Rhodes |
| Bulk upload improvements | Raise cap (50→200), TIFF→JPG auto-conversion, batch metadata form | `app/upload_routes.py` | PARTIAL — cap+TIFF done, batch metadata form NOT wired |
| Upload batches | Source/date/location per batch, stored in `upload_batches` table | New table + upload form | PARTIAL — table exists, `create_upload_batch()` function exists, form NOT wired |
| Community landing pages | Per-community hero, stats, featured photos | `app/page_routes.py` | DONE (Session 95) — empty state shown for Fox |
| Migrate existing data | Tag all existing photos/identities with `rhodes` community_id | Migration script | DONE (Session 95) — 295 photos + 894 identities tagged |
| Fox community setup | Create Fox community, import first batch of photos | Admin flow | PARTIAL — community exists in Supabase, no photos uploaded yet |
| Sidebar data scoping | Sidebar counts (matches, photos, people) scoped to community | `app/main.py` sidebar | **NOT DONE** — sidebar shows global Rhodes data on all communities |
| Workspace switcher | Admin can switch between communities | `app/main.py` nav | **NOT DONE** — no switcher UX |

**Post-Session 95 assessment (Nolan feedback):** Infrastructure is 80% done. The critical gap is **data scoping** — the middleware routes URLs correctly but route handlers don't filter data by community. COMMUNITY-001 in BACKLOG tracks this. Without it, the platform doesn't actually function as separate workspaces.

**Backward compatibility:** Existing `/browse`, `/identify`, etc. redirect to
`/c/rhodes/browse`, `/c/rhodes/identify` (or serve Rhodes as default when no
community prefix). No existing URLs break.

## Phase 2: Global Identity + Cross-Community Linking (2 sessions)

**Goal:** People who appear in both Fox and Rhodes are the same identity.

| Task | Description |
|------|-------------|
| Global identity model | `identity_communities` table, community membership |
| Cross-community face matching | Extend clustering to search across communities |
| Identity page cross-community section | "Also appears in" panel with community badges |
| Photo detail community banner | "This photo is from Fox Family Archive" indicator |
| Community provenance badges | Badge on photo cards showing origin community |
| Admin cross-community merge | Merge identities across communities |
| Share URLs with community context | `/c/rhodes/identify/{id}` routing |

## Phase 3: Multi-GEDCOM + Context Enrichment (2 sessions)

**Goal:** Multiple GEDCOM trees, primary/secondary model, richer context capture.

See [GEDCOM_MULTI_TREE.md](GEDCOM_MULTI_TREE.md) for full detail.

## Phase 4: Scale + Polish (1-2 sessions)

**Goal:** Ready for additional family branches and potential paid users.

| Task | Description |
|------|-------------|
| Per-community admin permissions | Multiple admins per community |
| Public/private photo controls | Mark photos as private within a community |
| Google Drive/Photos import | OAuth integration for bulk import from Google |
| Subdomain routing option | `rhodes.domain.com` as alternative to `/c/rhodes` |
| Community onboarding wizard | Guided flow: create → upload → context → review |
| Platform landing page | Neutral landing showing all public communities |

## Session Estimates

| Phase | Sessions | Dependencies |
|-------|----------|-------------|
| Phase 1 | 2-3 | None — can start immediately |
| Phase 2 | 2 | Phase 1 complete |
| Phase 3 | 2 | Phase 2 complete |
| Phase 4 | 1-2 | Phase 3 complete, may overlap |

**Total: 7-9 sessions to full platform**
**Fox MVP (Phase 1): 2-3 sessions**

## Acceptance Criteria

### Phase 1 (MVP)
- [ ] `/c/fox-family` serves Fox Family Archive landing page
- [ ] `/c/fox-family/browse` shows only Fox photos
- [ ] `/c/rhodes/browse` shows only Rhodes photos (unchanged behavior)
- [ ] Existing URLs (`/browse`, `/identify/X`) redirect to `/c/rhodes/...`
- [ ] Upload to Fox community works with batch metadata
- [ ] TIFF files auto-convert to JPG on upload
- [ ] Upload cap raised to 200
- [ ] Admin can create new communities
- [ ] All existing tests pass (no regressions)

### Phase 2 (Global Identity)
- [ ] Roland Fox identity page shows photos from both Fox and Rhodes
- [ ] Photos have community provenance badges
- [ ] Cross-community match surfaces as Discovery suggestion
- [ ] Admin can merge identities across communities
- [ ] Share URLs include community context

### Phase 3 (Multi-GEDCOM)
- [ ] Multiple GEDCOM trees can be imported to different communities
- [ ] Primary/secondary tree assignment works
- [ ] Gemini calls include context from all linked trees
- [ ] Tree visualization uses primary tree only

### Phase 4 (Scale)
- [ ] Per-community admin permissions
- [ ] Google Drive/Photos import
- [ ] Platform landing page showing all public communities
