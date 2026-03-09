# PRD-035: Data Model Changes

**Parent:** [PRD-035](../035_multi_community_platform.md)

## Communities Table (exists, needs enhancement)

```sql
-- Already exists from Session 91. Additions marked with (+)
ALTER TABLE communities ADD COLUMN IF NOT EXISTS
  landing_title TEXT,           -- (+) "Fox Family Archive"
  landing_subtitle TEXT,        -- (+) "Preserving our family's visual history"
  landing_hero_style TEXT,      -- (+) CSS/theme for community landing
  default_gedcom_version_id UUID, -- (+) Primary GEDCOM for this community
  is_public BOOLEAN DEFAULT true, -- (+) Future: private communities
  created_by UUID;              -- (+) Admin who created it
```

## Photos — Community Membership (many-to-many)

```sql
-- A photo can belong to multiple communities
CREATE TABLE IF NOT EXISTS photo_communities (
  photo_id TEXT NOT NULL,
  community_id UUID NOT NULL REFERENCES communities(id),
  added_at TIMESTAMPTZ DEFAULT now(),
  added_by UUID,               -- Who added it to this community
  PRIMARY KEY (photo_id, community_id)
);
```

## Identities — Community Membership

```sql
-- An identity can appear in multiple communities
CREATE TABLE IF NOT EXISTS identity_communities (
  identity_id UUID NOT NULL,
  community_id UUID NOT NULL REFERENCES communities(id),
  is_primary BOOLEAN DEFAULT false,  -- Primary community for this identity
  added_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (identity_id, community_id)
);
```

## GEDCOM Multi-Tree (extends AD-163)

```sql
-- gedcom_versions already has community_id — no change needed
-- New: link GEDCOM individuals to platform identities across trees
ALTER TABLE global_person_links ADD COLUMN IF NOT EXISTS
  gedcom_version_id UUID REFERENCES gedcom_versions(id),
  is_primary_tree BOOLEAN DEFAULT false;
```

## Upload Batches (new)

```sql
CREATE TABLE IF NOT EXISTS upload_batches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  community_id UUID NOT NULL REFERENCES communities(id),
  uploaded_by UUID,
  source_description TEXT,      -- "Charlie's photo box"
  date_range_hint TEXT,         -- "1950s-1960s"
  location_hint TEXT,           -- "Detroit, Michigan"
  notes TEXT,                   -- Free-form context
  photo_count INTEGER,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Link photos to their upload batch
ALTER TABLE photos ADD COLUMN IF NOT EXISTS
  upload_batch_id UUID REFERENCES upload_batches(id);
```
