# PRD-035: Multi-Community Platform + Fox Family MVP

**Date:** 2026-03-09
**Session:** 94
**Status:** Draft — Approved by Nolan
**Supersedes:** PRD-030 (multi-collection), partially
**References:** PRD-034 (standalone tools), AD-206 (GlobalPersonID), MULTI_TENANT.md
**Brain dump:** `docs/session_context/session-94-fox-brain-dump.md`

**Sub-documents:**
- [Data Model Changes](035_multi_community/DATA_MODEL.md)
- [Upload Pipeline Improvements](035_multi_community/UPLOAD_PIPELINE.md)
- [GEDCOM Multi-Tree Architecture](035_multi_community/GEDCOM_MULTI_TREE.md)
- [Phased Implementation Plan](035_multi_community/PHASES.md)

---

## Problem Statement

Rhodesli has proven that ML + human-in-the-loop can unlock identity, relationship,
and context information from old photos — something Google Photos, Amazon Rekognition,
and Mylio have failed to do. The platform currently serves one community (Rhodes).
Nolan has ~5 additional family branches with hundreds of digitized photos ready for
the same workflow. The architecture must scale from 1 community to N without breaking
existing functionality or losing the community-specific UX that makes Rhodesli work.

## Vision

Anyone can create a space for their family, community, or personal photo archive.
Upload old media, add genealogical context (GEDCOM, NL chat, manual tags), and
discover identities, relationships, and stories — aided by ML that works across
every community on the platform.

**Ultimate goal:** Search for faces across every old photo ever archived on the
platform — personal collections, community archives, institutional holdings.

---

## User Stories

### Community Admin (Nolan for Fox MVP)
- I can create a new community ("Fox Family Archive") with its own landing page
- I can bulk-upload hundreds of photos with source metadata per batch
- I can assign a GEDCOM tree to the community for enrichment
- I can run the ML/human-in-the-loop identification workflow scoped to my community
- I can see when a face in my community matches someone in another community
- I can confirm or reject cross-community identity links

### Community Member (Nolan's cousins)
- I arrive at the Fox Family Archive landing page via a shared link
- I browse only Fox photos — I never accidentally see Rhodes photos
- I can help identify faces or provide context about people in photos
- I can share a specific identity page with family via link or social

### Cross-Community User (Nolan as admin of both)
- I view Roland Fox's identity page and see photos from BOTH Fox and Rhodes
- Each photo is clearly labeled with its community of origin
- I can click a cross-community photo and get a clear "This is from Rhodes" indicator
- Browse pages remain scoped to the community I'm in

---

## Architecture

### Community Model

```
Platform (rhodesli.nolanandrewfox.com)
  ├── /c/rhodes        → Jewish Community of Rhodes (existing)
  │     ├── /browse    → Rhodes photos only
  │     ├── /identify  → Rhodes identities (+ cross-links)
  │     └── /upload    → Upload to Rhodes
  ├── /c/fox-family    → Fox Family Archive (new)
  │     ├── /browse    → Fox photos only
  │     ├── /identify  → Fox identities (+ cross-links)
  │     └── /upload    → Upload to Fox
  └── /               → Platform landing (pick a community)
```

**Approach A (MVP):** URL-prefixed communities on same domain.
**Path to B (future):** Subdomain routing (`rhodes.domain.com`, `fox.domain.com`).

### Global Identity Model

Identities are global — one "Roland Fox" across the entire platform. The identity
has a `primary_community_id` for default context but belongs to all communities
where his face appears.

```
Identity: Roland Fox (UUID: abc-123)
  ├── primary_community: fox-family
  ├── communities: [fox-family, rhodes]
  ├── faces:
  │     ├── face_001 → photo in Fox collection
  │     ├── face_002 → photo in Fox collection
  │     └── face_003 → photo in Rhodes collection
  └── gedcom_links:
        ├── primary: Fox tree (GEDCOM version 3)
        └── secondary: [Rhodes tree (GEDCOM version 1)]
```

### Community Boundary Rules

| Page | Scoping | Cross-Community Behavior |
|------|---------|------------------------|
| Landing page | Community-specific | No cross-community content |
| Browse | Strictly scoped | Only shows photos from active community |
| Upload | Strictly scoped | Photos uploaded to active community |
| Identity page | Global + scoped | Shows all photos, grouped by community with badges |
| Photo detail | Source community | Banner: "This photo is from [Community Name]" |
| Search | Community-scoped default | Optional "Search all communities" toggle |
| Discover | Community-scoped | Cross-community matches shown as explicit suggestions |
| Share links | Include community | `/c/rhodes/identify/{id}` — always land in right |

### Cross-Community Identity UX

When viewing an identity page within a community:

1. **Default section:** Photos from the active community (full cards, same as today)
2. **Cross-community section** (below, clearly separated):
   - Header: "Also appears in: Fox Family Archive (3 photos)"
   - Expandable panel with thumbnail grid
   - Each thumbnail has community badge
   - Clicking opens photo detail WITH community banner
3. **Navigation stays in original community** — clicking a cross-community photo
   doesn't switch your nav context. A banner indicates provenance with a link
   to browse that community if interested.

### Cross-Community Face Matching

Follows existing Gatekeeper pattern:

| Confidence | Action | Admin Experience |
|-----------|--------|-----------------|
| Tier 1 (high) | Auto-link to global identity | Notification: "Linked face" |
| Tier 2 (medium) | Discovery suggestion | "May be Roland Fox from Rhodes" |
| Manual | Admin merges via search | Search across all communities |
| Error correction | Admin unlinks/detaches | Reversible, like current detach |

---

## Branding Strategy

### Near-Term (MVP)
- Keep "Rhodesli" as project codename and internal brand
- Domain: `rhodesli.nolanandrewfox.com`
- Each community has its own branded landing page
- No mention of "Rhodesli" on community-specific pages

### If Commercialization (Future)
- Neutral product name (TBD), Rhodesli becomes the Rhodes community
- Domain changes to neutral product domain, current URLs redirect

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Breaking existing Rhodes functionality | HIGH | Backward-compat redirects, tests |
| Community-scoped queries slow | MEDIUM | Postgres indexes on community_id |
| Cross-community false positives | MEDIUM | Gatekeeper pattern, admin review |
| Upload pipeline timeout on 200+ photos | MEDIUM | Chunked upload, background processing |
| Scope creep from platform vision | HIGH | Strict phase gates, MVP-first |

## Success Metrics (Fox MVP)

1. Fox Family Archive is live at `/c/fox-family` with 100+ photos
2. ML face detection + clustering runs on Fox photos
3. Nolan can do the identification workflow (confirm, reject, merge, rename)
4. Identity pages show community provenance badges
5. Existing Rhodes functionality is unchanged (regression tests pass)
6. At least one cross-community identity (Roland Fox) appears in both
7. Share links work: `/c/fox-family/identify/{id}` renders correctly with OG tags

---

## Detailed Sub-Documents

- **[Data Model](035_multi_community/DATA_MODEL.md)** — Schema changes for communities, photo/identity membership, upload batches, GEDCOM multi-tree
- **[Upload Pipeline](035_multi_community/UPLOAD_PIPELINE.md)** — Cap increase, TIFF conversion, batch metadata, Google import (future)
- **[GEDCOM Multi-Tree](035_multi_community/GEDCOM_MULTI_TREE.md)** — Primary/secondary trees, cross-tree linking, pgvector decision
- **[Phases](035_multi_community/PHASES.md)** — 4-phase implementation plan with acceptance criteria and session estimates

---

## Breadcrumbs

- Brain dump: `docs/session_context/session-94-fox-brain-dump.md`
- Supersedes: `docs/prds/030_multi_collection.md` (partial)
- Architecture: `docs/architecture/MULTI_TENANT.md` (needs update)
- GEDCOM versioning: AD-163, GlobalPersonID: AD-206
- Fox prep: `docs/collections/fox_family_prep.md`
- Upload pipeline: `app/upload_routes.py` lines 345-352
- Standalone tools: `docs/prds/034_standalone_tool_suite.md`
- Context capture → TOOLS-004: `docs/prds/032_nl_query.md`
- pgvector: `docs/architecture/PGVECTOR_EVALUATION.md`
