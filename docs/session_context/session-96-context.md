# Session 96 Context — Community Data Scoping Hotfix + Bulk Upload Planning

**Predecessor:** [Session 95 context](session-95-context.md) (Fox MVP + Standalone Tool Suite)
**Date:** 2026-03-09
**Type:** Hotfix + planning

---

## What Triggered This Session
Nolan switched to Fox Family community (`/c/fox-family/`) and found multiple data scoping bugs from screenshots:
1. Photos section showed all 297 Rhodes photos in Fox Family
2. Sidebar counts on upload page showed Rhodes data (People 71, Photos 297)
3. Admin bar links hardcoded to `/admin/section/...` without community prefix
4. Unresolved merge conflict in sidebar docstring from Session 95b worktree merge
5. About page shows Rhodes-specific content from Fox Family sidebar

## Root Cause
Session 95/95b built the community middleware and scoping functions correctly, but integration was incomplete. Routes and components were only partially updated to extract community from `request.state` and pass it through to filtering functions.

## What Shipped (Session 96)
- `render_photos_section()` — community photo filter via `_get_community_photo_ids()`
- `upload_routes.py` — `_compute_sidebar_counts(registry, community=community)`
- `_admin_bar()` — community-aware counts and URL prefixing
- Merge conflict resolved in sidebar docstring
- Test updated: `test_admin_bar_links_to_admin_sections`

## What Was Deferred
- **About page community content** — `/about` still hardcodes Rhodes history. Needs community-specific about pages or generic fallback. See BACKLOG COMMUNITY-001.
- **Tools photo picker** — `/tools/estimate` "SELECT A PHOTO" shows Rhodes photos. By design (tools are cross-community).
- **CI/CD fix** — GitHub Actions workflow fails because `./venv/bin/pytest` doesn't exist in CI. Pre-existing since Session 92. Not blocking deploys (Railway deploys from git push).

## Bulk Upload: Charlie Fox Collection

### The Collection
- 636 photos from Uncle Charlie (Roland Fox's brother), digitized by cousin David
- Files in Google Drive + Google Photos, all small JPGs (~5MB)
- Collection: "Charles Fox Dayton Ohio Collection", Source: "Personal Photos"
- Current web upload caps at 200 files → need local pipeline
- Common use case: scanning services bulk-digitize family photo collections

### Cross-Community People: Betty Capeluto & Roland Fox
Betty Capeluto and Roland Fox are **confirmed identities in the Rhodes archive** with existing face embeddings. They appear prominently in the Charlie Fox collection. This creates a cross-community matching scenario that is a first for Rhodesli.

**What will happen mechanically during clustering:**
1. `cluster_new_faces.py` compares every new Fox Family face embedding against ALL confirmed identities (including Rhodes)
2. Faces matching Betty/Roland will get Tier 1 (<0.85 distance) or Tier 2 (0.85-1.30) matches against their Rhodes identity records
3. Tier 1 matches: face_id added to the **Rhodes identity's** `candidate_ids` — the face joins the existing person, not a new Fox Family person
4. Tier 2 matches: logged as Discovery suggestions for admin review
5. **The identity itself stays in Rhodes** — it doesn't get duplicated into Fox Family

**What this means for UX:**
- On the Fox Family browse page, photos will show faces but those faces link to Rhodes identities
- The person detail page for Betty Capeluto (a Rhodes identity) will now show faces from BOTH communities
- Sidebar counts: Fox Family "People" count only includes identities tagged in `identity_communities` for fox-family — Betty/Roland won't appear there unless explicitly tagged
- **Gap**: There's currently no mechanism to tag an existing Rhodes identity as also belonging to Fox Family. The `identity_communities` table supports it, but no UI or pipeline does it automatically.

**Known weaknesses to watch for:**
- Identity pages are not community-scoped — `/person/{id}` shows all faces regardless of community. This is actually correct (Betty IS one person) but may confuse Fox Family users who don't know about Rhodes.
- No "shared people" indicator — nothing tells the user "this person also appears in the Rhodes archive"
- If we later want Fox Family to have its OWN identity for Betty (separate from Rhodes), there's no architecture for that yet. Current design assumes one identity per person globally.
- Discovery suggestions will appear on the Rhodes triage page, not Fox Family's — admin needs to check both.

### Nolan's GEDCOM-First Workflow Insight
**Key insight**: Many people in the Charlie Fox collection are in Nolan's GEDCOM. The optimal workflow is:

1. **Upload + face detection** (automated)
2. **Auto-cluster** to match faces to known identities (automated)
3. **Surface top identities by face count** — "Roland Fox: 38 faces, Betty Capeluto: 22 faces, Unknown: 15 faces"
4. **Admin links top identities to GEDCOM** — 5-10 clicks for the most impactful people
5. **THEN run Gemini** with enriched GEDCOM context (birth years, family relationships, known locations)

**Why this order matters:**
- Gemini date estimation quality scales directly with GEDCOM context richness
- A photo of Betty Capeluto with no GEDCOM context: Gemini guesses "c. 1950s" from clothing
- Same photo WITH GEDCOM (born 1925, married 1948, lived in Miami): Gemini returns "1952-1956, high confidence" using birth year + apparent age math
- At ~$0.04/photo for Pro, running Gemini on 636 photos costs ~$25. Linking GEDCOM first maximizes the value of that spend.
- This workflow works for BOTH known people (Betty, Roland) AND unknown people — once you identify and link an unknown person to GEDCOM, all their photos benefit retroactively on re-analysis.

**This should become automatic after every upload** (PRD-037): Upload → cluster → show triage page → admin links GEDCOM → batch Gemini. Not just for this collection — for every community that uploads photos.

### Current Pipeline: What's Automated vs Manual

| Step | Current State | After PRD-037 |
|------|--------------|---------------|
| Face detection | Automated (in upload thread) | Same |
| Face crop generation | Automated | Same |
| Community tagging | Automated (for non-Rhodes) | Same |
| R2 upload | Automated (in upload thread) | Same |
| Auto-clustering | **MANUAL** (`cluster_new_faces.py`) | Automated (Phase 1) |
| Surface top identities | **MANUAL** (admin browses inbox) | Automated triage page (Phase 2) |
| GEDCOM linking | **MANUAL** (per-identity search) | Inline on triage page (Phase 2) |
| Gemini date estimation | **MANUAL** (per-photo on /tools/estimate) | Batch with cost estimate (Phase 3) |
| Identity confirmation | **MANUAL** (per-face admin action) | Same (Gatekeeper pattern) |

### Pipeline Research Summary
Full pipeline analysis was conducted via code exploration. Key findings documented in PRD-037. Critical code paths:
- `core/ingest_inbox.py` — `process_directory()` handles face detection, embedding storage, photo registration, INBOX identity creation
- `core/auto_cluster.py` — `run_backfill()` for Tier 1/2 clustering, `dedup_inbox()` for duplicate detection
- `app/upload_routes.py` — `_background_ingest()` thread orchestrates ingest → R2 upload → community tagging → cache invalidation
- Auto-clustering thresholds: Tier 1 < 0.85 (auto-candidate), Tier 2 0.85-1.30 (discovery suggestion), calibrated against 982 same-person pairs
- Gemini runs on-demand only via `/tools/estimate` or `scripts/batch_reanalyze.py`
- GEDCOM linking is admin-only via identity detail page search panel

## Key Decisions
- **Local pipeline for immediate ingest** (Option A) — fastest path for 636 photos
- **Auto-cluster after upload** (PRD-037 Phase 1) — wire clustering into `_background_ingest()`
- **GEDCOM triage page** (PRD-037 Phase 2) — surface top identities by face count for linking
- **Gemini AFTER GEDCOM linking** — deferred to future session after admin links top identities
- **Cross-community identity sharing** — faces join existing Rhodes identities, no duplication. Gap: no UI to tag identity as belonging to multiple communities.

## Strategic Context: Growth Readiness
This upload is the first real test of Rhodesli as a multi-community platform. The Fox Family archive needs to work well enough that:
1. Nolan can show family members the archive and have them recognize people
2. The GEDCOM-first workflow proves the value of enriched date estimation
3. Cross-community people (Betty, Roland) demonstrate that Rhodesli's identity system works across archives
4. The upload experience informs what self-service onboarding (TOOLS-006) needs to look like

If this goes well, the next growth step is inviting other Rhodes community members to create their own archives with their family collections.

## Post-Session Planning

### Session 96b (next, same session family)
- Charlie Fox collection ingest via local pipeline (636 photos)
- Auto-cluster against confirmed identities (Betty Capeluto, Roland Fox should match)
- Upload to R2, push to production
- Build PRD-037 Phase 1 (auto-cluster after upload)
- Build PRD-037 Phase 2 (GEDCOM triage page)
- Prompt: `docs/prompts/session-96b-prompt.md`

### Future Session (after 96b)
- GEDCOM linking for top Fox Family identities (admin manual task)
- Batch Gemini estimation with enriched GEDCOM context
- PRD-037 Phase 3 (batch Gemini UI with cost estimate)
- CI/CD fix (install deps in GitHub Actions)
- About page community content (COMMUNITY-001 remaining gap)

## Breadcrumbs
- PRD: `docs/prds/037_post_upload_intelligence.md`
- Prompt: `docs/prompts/session-96b-prompt.md`
- Assessment: `docs/assessments/session-96-assessment.md`
- Session log: `docs/session_logs/session-96-log.md`
- BACKLOG: COMMUNITY-001 (updated), UPLOAD-001 (new)
- ROADMAP: Session 96 in Recently Completed
- CHANGELOG: v0.97.1
