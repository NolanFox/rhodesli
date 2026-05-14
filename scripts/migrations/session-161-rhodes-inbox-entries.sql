-- Session 161 Phase 1 — rhodes_inbox_entries provenance table
--
-- Tracks the rhodesli-side status of inbox entries produced by rhodes-wiki.
-- The rhodes-wiki vault filesystem (inbox/pending/ → inbox/approved/ →
-- inbox/rejected/) mirrors this row's `status` field for offline-readable
-- provenance, but Supabase is AUTHORITATIVE (AD-S161-6, see
-- docs/architecture/RHODES_INBOX.md after Phase 9 closeout).
--
-- Schema design notes (post Codex pre-execution audit):
--   - slug TEXT PRIMARY KEY — directly indexable; the only natural ID
--     ("2026-04-28_2360240064471306"). Verified slug pattern in
--     app/rhodes_inbox._SLUG_PATTERN.
--   - rhodesli_photo_id TEXT REFERENCES photos(photo_id) — verified that
--     photos.photo_id is TEXT PRIMARY KEY in scripts/sql/001_photos_table.sql.
--   - kinship_triples_json JSONB — cached on first detail-view load
--     (AD-S161-4 + Codex P1-7); rendering reads from this column, not
--     recomputed on every request.
--   - rejection_reason length cap 4096 (Codex P3-B).
--   - status CHECK constraint enforces the 3 allowed values; the atomic
--     CAS in app/rhodes_inbox.mark_approved relies on this guarantee.
--   - Indexes: idx_status for "list pending" queries; idx_fb_post for
--     dedup checks across duplicate FB posts.
--
-- Apply via psycopg2 over Supabase pooler (us-west-2, port 5432, session
-- mode) — same pattern as scripts/migrations/session158b_*.sql.

CREATE TABLE IF NOT EXISTS rhodes_inbox_entries (
    slug TEXT PRIMARY KEY,
    fb_post_id TEXT NOT NULL,
    fb_group_id TEXT,
    fb_post_url TEXT NOT NULL,
    fb_author_name TEXT,
    fb_author_id TEXT,
    captured_at TIMESTAMPTZ,
    captured_by TEXT,
    contract_version TEXT DEFAULT '0.1.0',
    parser_version TEXT,
    comments_count INT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT CHECK (rejection_reason IS NULL OR length(rejection_reason) <= 4096),
    rhodesli_photo_id TEXT REFERENCES photos(photo_id) ON DELETE SET NULL,
    kinship_triples_json JSONB,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rhodes_inbox_status ON rhodes_inbox_entries(status);
CREATE INDEX IF NOT EXISTS idx_rhodes_inbox_fb_post ON rhodes_inbox_entries(fb_post_id);

-- Sanity check after creation (run manually):
--   SELECT count(*) FROM rhodes_inbox_entries;
--   -- expected: 0 immediately after migration; row(s) appear once the
--   --   admin route's first detail-view-load triggers an upsert.
