# Session 100c Context — Fox Family Cluster Review & Platform Reliability

**Predecessor:** Session 100b-cont3 (docs/session_context/session-100b-context.md)
**Date:** 2026-03-13
**Agent:** Claude Code (Opus 4.6)

## Problem Statement

Fox Family has 635 photos with ~1600 INBOX identities. The cluster review page exists but the tagging workflow is too slow and fragmented. Users need a batch-first cluster confirmation flow to make the 635-photo archive usable. Additionally, the Rhodes platform has a production reliability issue: DATA_SOURCE=postgres is set but the app falls back to JSON.

## Two Workstreams

### Workstream A: Platform Reliability (P0 — blocks everything)
**Problem:** Production app says "Supabase connection skipped" despite DATA_SOURCE=postgres. Data fixes applied to Supabase (Yaacov Franco face swap, Solomon orphan removal) are not being served to users.

**Known state:**
- DATA_SOURCE=postgres is set on Railway (confirmed in session 100b-cont3 prompt)
- Supabase URL and ANON_KEY are configured
- Health endpoint says "Supabase connection skipped"
- Local git has correct data (committed dc84696, 07ac0db)
- Deploy SUCCESS (f0013a7c, 2026-03-13T05:35:42Z)

**Investigation needed:**
1. Check Railway deploy logs for Python import errors (supabase-py, postgrest)
2. Check Dockerfile — does it COPY supabase dependencies?
3. Check app/main.py startup path for DATA_SOURCE=postgres → what exactly does "connection skipped" mean?
4. Check if `load_registry_from_postgres()` is being called and what it returns

**Fallback:** If Supabase can't be fixed quickly, push corrected JSON to Railway volume via sync API.

### Workstream B: Fox Family Cluster Review UX (P1 — main session goal)
**Problem:** 1600 INBOX identities across 635 photos. Current review is one-at-a-time. Users need to "speed run" through face tagging like Lightroom/Mylio.

**Current state of cluster review:**
- Route: `/admin/upload-review` (cluster_review_routes.py)
- Three sections: Grouped Identities, Potential Review Groups, Proposal Matches
- Community scoping works (COMMUNITY-011 fixed in Session 96d)
- Proposals.json has 1122 Fox-filtered proposals (Session 96e)
- PRD037-004 still marked incomplete ("Wire cluster review into community sidebar")

**What competing software does (from Session 100 audit):**
1. **Cluster-first tagging** — name one cluster, tag all faces in it
2. **Batch confirm/reject** — approve whole clusters at once
3. **Ignore/noise suppression** — dismiss background strangers quickly
4. **Auto-advance** — after naming one, move to next unresolved
5. **Any-view tagging** — tag from photo, person, review queue, or cluster view

**Key gaps in Rhodesli:**
1. No true batch cluster-confirmation flow
2. No "ignore remaining unknowns in this photo/group" path
3. No auto-advance after naming
4. Face cards don't let you cycle through an identity's faces
5. Dense multi-face photos compress targets too small

## Relevant PRDs & Decisions
- PRD-037: Post-Upload Intelligence Pipeline (docs/prds/037_post_upload_intelligence.md)
- PRD-038: Longitudinal Face Modeling (docs/prds/SDD-038_longitudinal_face_modeling.md)
- AD-179: Two-tier auto-clustering (Tier 1 <0.85 auto-add, Tier 2 0.85-1.10 suggestions)
- AD-216: Photo-derived community identity sets
- Session 100 Fox Family screenshot audit (docs/assessments/session-100-fox-family-screenshot-audit.md)
- Session 100 face tagging audit (docs/assessments/session-100-face-tagging-and-fox-family-audit.md)

## Existing BACKLOG Items
- COMMUNITY-015: Internal links missing community prefix
- COMMUNITY-016: `/api/proposed-matches` only reads registry, not proposals.json
- UX-202: One-Click Bulk Tag Confirmation
- ML-117: Rollout gate tuning with fresh Fox-family labels
- DATA-011: Visual confirmation gate for admin confirm workflow
- DATA-012: Data integrity CI for CONFIRMED identities

## Technical Architecture for Cluster Review

### Current data flow:
1. `scripts/cluster_new_faces.py` generates `proposals.json` with match suggestions
2. `_background_ingest()` in upload_routes.py triggers auto-clustering after upload
3. `cluster_review_routes.py` reads proposals.json + registry for grouped view
4. Community scoping via `_get_community_identity_ids(community)`

### What needs to change for batch-first UX:
1. **Cluster groups need a "confirm all" action** — currently each proposal is confirmed individually
2. **Need "dismiss group" action** — mark a cluster of INBOX faces as noise/unresolvable
3. **Auto-advance** — after confirming/dismissing, next group loads automatically
4. **Progress tracking** — show "47 of 1122 reviewed" counter
5. **Keyboard shortcuts** — Y=confirm, N=skip, D=dismiss for speed

## Deferred from 100b series
- Supabase production debugging (Workstream A above)
- Browser verification of face cycling arrows
- Browser verification of Yaacov Franco fix
- ML test suite verification

## Post-Session Planning
- If cluster review ships: next session should collect Fox Family labels for ML-117
- If Supabase fixed: next session should verify all data fixes render correctly
- COMMUNITY-017 (default community routing) blocks wider sharing — consider for 101
