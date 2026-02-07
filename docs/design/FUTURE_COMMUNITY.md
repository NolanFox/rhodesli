# Future Community Features

**Last updated:** 2026-02-06

This document contains planned features that are NOT YET IMPLEMENTED. These designs were created during the initial system design session and are preserved here for future implementation.

---

## NOT YET IMPLEMENTED: Postgres Tables

The community layer will use Supabase Postgres for annotations, photo uploads, and activity logging. Canonical data remains in JSON files.

### profiles

Links Supabase auth users to application-specific data.

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  email TEXT NOT NULL,
  display_name TEXT,
  role TEXT NOT NULL DEFAULT 'contributor'
    CHECK (role IN ('admin', 'contributor', 'viewer')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
  ON profiles FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Admins can view all profiles"
  ON profiles FOR SELECT USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
  );
```

### invites

Invite tokens for invite-only signup.

```sql
CREATE TABLE invites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL,
  invited_by UUID NOT NULL REFERENCES profiles(id),
  token TEXT NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days'
);

CREATE INDEX idx_invites_token ON invites(token);
CREATE INDEX idx_invites_email ON invites(email);
ALTER TABLE invites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage invites"
  ON invites FOR ALL USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'admin')
  );
```

### annotations

Community-submitted enrichments awaiting moderation.

```sql
CREATE TABLE annotations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id UUID NOT NULL REFERENCES profiles(id),
  target_type TEXT NOT NULL CHECK (target_type IN ('identity', 'photo', 'face')),
  target_id TEXT NOT NULL,
  annotation_type TEXT NOT NULL CHECK (annotation_type IN (
    'name_suggestion', 'date_suggestion', 'location_suggestion',
    'relationship_note', 'general_note'
  )),
  payload JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'accepted', 'rejected')),
  reviewed_by UUID REFERENCES profiles(id),
  reviewed_at TIMESTAMPTZ,
  review_notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_annotations_target ON annotations(target_type, target_id);
CREATE INDEX idx_annotations_status ON annotations(status);
CREATE INDEX idx_annotations_author ON annotations(author_id);
```

### photo_uploads

Staging area for community photo contributions.

```sql
CREATE TABLE photo_uploads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id UUID NOT NULL REFERENCES profiles(id),
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_size_bytes INTEGER,
  file_hash TEXT,
  source_collection TEXT,
  source_notes TEXT,
  estimated_date TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'accepted', 'rejected', 'processing')),
  reviewed_by UUID REFERENCES profiles(id),
  reviewed_at TIMESTAMPTZ,
  review_notes TEXT,
  canonical_photo_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_photo_uploads_status ON photo_uploads(status);
CREATE INDEX idx_photo_uploads_author ON photo_uploads(author_id);
```

### activity_log

Append-only audit trail for community and admin actions.

```sql
CREATE TABLE activity_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id UUID REFERENCES profiles(id),
  action TEXT NOT NULL,
  target_type TEXT,
  target_id TEXT,
  details JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activity_log_actor ON activity_log(actor_id);
CREATE INDEX idx_activity_log_target ON activity_log(target_type, target_id);
CREATE INDEX idx_activity_log_created ON activity_log(created_at DESC);
```

---

## NOT YET IMPLEMENTED: Three-Tier Permission Model

The planned permission model adds a contributor role between viewer and admin:

| Role | Description | Default For |
|------|-------------|-------------|
| `viewer` | Read-only access | Not logged in |
| `contributor` | Can submit annotations and photos | New signups |
| `admin` | Full access, moderation, canonical writes | NolanFox@gmail.com |

### Planned Contributor Permissions

Contributors would be able to:
- Submit name suggestions for identities
- Submit date, location, and relationship notes
- Upload photos (to staging, pending admin approval)
- View their own pending submissions

Contributors would NOT be able to:
- Confirm/reject identities
- Merge identities
- Detach faces
- Rename identities directly
- Manage users

---

## NOT YET IMPLEMENTED: Contributor Annotation Flow

### Name Suggestion

1. Contributor clicks "Suggest Name" on an identity card
2. Modal form collects: suggested name, confidence level, notes
3. Submission creates a `pending` annotation in Postgres
4. Admin sees suggestion in moderation queue
5. On accept: admin applies name to `identities.json` (atomic write)
6. On reject: annotation status updated, contributor notified

### Photo Upload (Community)

1. Contributor selects files and provides source/collection metadata
2. Files saved to `data/staging/` (not `raw_photos/`)
3. Record created in `photo_uploads` table with status `pending`
4. Admin reviews in moderation queue
5. On accept: triggers ingestion pipeline (face detection, embeddings, etc.)
6. On reject: files cleaned up, contributor notified

Photo upload acceptance triggers a multi-step pipeline:
1. Move files from `data/staging/` to `raw_photos/`
2. Run face detection
3. Generate embeddings
4. Update `embeddings.npy`, `photo_index.json`, `identities.json`
5. Update `file_hashes.json`

This takes 30-60 seconds per photo and should run as a background task.

---

## NOT YET IMPLEMENTED: UI Modifications for Contributors

### Sidebar Changes

Contributors would see additional sidebar items:
- "Upload Photos" (with badge for pending uploads)
- "My Contributions" (with count of pending items)

Admins would additionally see:
- "Pending Approvals" (with count)
- "Activity Log"
- "User Management"

Anonymous visitors would see a message: "This is an invite-only community archive."

### Identity Card Changes

- Anonymous: no action buttons, "Sign in to suggest names or notes" message
- Contributors: "Suggest Name" and "Add Note" buttons only (no confirm/reject/merge)
- Admins: full existing UI plus annotation review indicators

---

## NOT YET IMPLEMENTED: Implementation Phases

| Phase | Effort | Description |
|-------|--------|-------------|
| Phase C: Annotation Engine | 2-3 sessions | Annotation CRUD, submission forms, contributor view |
| Phase D: Photo Upload Queue | 1-2 sessions | Staged uploads with admin moderation |
| Phase E: Admin Dashboard | 2-3 sessions | Moderation queue, activity log, user management |
| Phase F: Polish & Security | 1-2 sessions | Rate limiting, CSRF, error pages, backup automation |
