# PRD-030: Multi-Collection Support

**Status:** PLANNED
**Priority:** P2
**Author:** Session 91F
**Date:** 2026-03-07

---

## Problem Statement

Rhodesli currently operates as a single-community application for the
Jewish Community of Rhodes. The architecture (JSON files, single R2 prefix,
no community scoping) prevents onboarding additional heritage photo
collections. To grow beyond Rhodes, the platform needs community-scoped
data isolation with cross-community person linking.

## User Stories

1. **As a platform admin**, I want to create a new community so I can
   onboard a second photo collection (e.g., Fox family photos).

2. **As a community admin**, I want uploaded photos to be scoped to my
   community so they don't mix with other communities' photos.

3. **As a researcher**, I want to link a person in one community to the
   same person in another community (cross-community identification).

## Solution Overview

### Community-Scoped Data

Add a `communities` table and scope photos, identities, and embeddings
by `community_id`. All existing data becomes the "Rhodes" community.

### Schema Changes

```sql
-- New table
CREATE TABLE communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    settings JSONB DEFAULT '{}'::jsonb
);

-- New table: cross-community person linking
CREATE TABLE global_persons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE global_person_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    global_person_id UUID REFERENCES global_persons(id),
    community_id UUID REFERENCES communities(id),
    identity_id UUID NOT NULL,
    link_type TEXT NOT NULL CHECK (link_type IN ('gedcom', 'ml_proposal', 'human_confirmed')),
    confidence FLOAT,
    linked_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Existing table modifications
ALTER TABLE photos ADD COLUMN community_id UUID REFERENCES communities(id);
ALTER TABLE identities ADD COLUMN community_id UUID REFERENCES communities(id);
```

### GlobalPersonID

Three linking mechanisms:
- **GEDCOM link**: Admin links identity to a GEDCOM record
- **ML proposal**: Face embedding similarity suggests match
- **Human confirmed**: Admin confirms two identities are the same person

### R2 Storage

Per-community prefixes: `rhodesli-photos/{community_slug}/raw_photos/`

### Migration Plan

1. Create `communities` table, seed with Rhodes
2. Backfill `community_id` on all existing photos/identities
3. R2 prefix migration (or keep flat with metadata-based scoping)
4. Update all queries to filter by `community_id`

## Acceptance Criteria

- [ ] Communities table exists with Rhodes as first entry
- [ ] All existing photos and identities have `community_id` set
- [ ] New photo uploads are scoped to a community
- [ ] Identity management is scoped to a community
- [ ] GlobalPersonID linking works between communities
- [ ] No data loss during migration

## Out of Scope

- Row-level security (RLS) policies
- ML service extraction to separate process
- Community-specific UX (landing pages, branding)
- Self-service community creation (admin-only initially)
- Cross-community search and browse

## Dependencies

- PRD-027 Phase B/C: Full Postgres migration must complete first
- Shadow writes (Session 90b) must be verified for parity

## Related Documents

- `docs/architecture/MULTI_TENANT.md` — Architecture design
- `docs/architecture/DATA_MODEL.md` — Current data model
