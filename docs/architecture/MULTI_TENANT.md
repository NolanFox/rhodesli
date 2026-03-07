# Multi-Tenant Architecture Design

**Last updated:** 2026-03-07

This document describes the planned multi-tenant architecture for Rhodesli,
enabling multiple heritage photo communities to share a single platform instance.

---

## GlobalPersonID

People appear across multiple collections and communities. GlobalPersonID
provides a unified cross-referencing system.

### Three Linking Mechanisms

| Mechanism | Source | Confidence | Example |
|-----------|--------|------------|---------|
| GEDCOM link | Admin links identity to GEDCOM record | HIGH | Isaac Cohen (identity) = Isaac Cohen (GEDCOM I123) |
| ML proposal | Face embedding similarity | MEDIUM | "Face in Photo A looks like face in Photo B" |
| Human confirmed | Admin or contributor confirms match | HIGHEST | Admin confirms two identities are the same person |

### Schema

```sql
-- Global person records that span communities
CREATE TABLE global_persons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Links between community-local identities and global persons
CREATE TABLE global_person_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    global_person_id UUID REFERENCES global_persons(id),
    community_id UUID REFERENCES communities(id),
    identity_id UUID NOT NULL,  -- community-local identity
    link_type TEXT NOT NULL CHECK (link_type IN ('gedcom', 'ml_proposal', 'human_confirmed')),
    confidence FLOAT,
    linked_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Community Schema

```sql
CREATE TABLE communities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,  -- URL-safe identifier
    description TEXT,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    settings JSONB DEFAULT '{}'::jsonb
);

-- community_id added to existing tables
ALTER TABLE photos ADD COLUMN community_id UUID REFERENCES communities(id);
ALTER TABLE identities ADD COLUMN community_id UUID REFERENCES communities(id);
```

---

## R2 Storage Organization

Per-community prefixes in Cloudflare R2:

```
rhodesli-photos/
  rhodes/                    # Rhodes community (current)
    raw_photos/
    crops/
  fox-family/                # Future: Fox family collection
    raw_photos/
    crops/
```

The `STORAGE_MODE` and `R2_PUBLIC_URL` configuration remains the same.
Community-specific prefixes are appended to the base URL.

---

## Migration Plan

### Phase 1: Rhodes Seed
1. Create `communities` table with Rhodes as first entry
2. Backfill `community_id` on all existing photos and identities
3. All existing data maps to the Rhodes community

### Phase 2: Read Flip (DATA_SOURCE flag)
1. Feature flag `DATA_SOURCE` controls whether app reads from JSON or Postgres
2. Shadow writes already active (Session 90b)
3. Flip reads to Postgres once shadow write parity is verified

### Phase 3: Second Community
1. Admin UI for community creation
2. Upload pipeline scoped to community
3. Identity management scoped to community

---

## Future Work (Out of Scope)

- **RLS policies**: Row-level security for community data isolation
- **ML service extraction**: Separate FastAPI service for face detection/embedding
- **Cross-community search**: Finding people across communities
- **UX changes**: Community selector, community-specific landing pages

---

## Related Documents

- `docs/prds/030_multi_collection.md` — PRD for multi-collection support
- `docs/architecture/DATA_MODEL.md` — Current data model
- `docs/architecture/PHOTO_STORAGE.md` — Current photo storage
