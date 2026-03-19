-- Session 122: WORKSPACE-001 Phase 1 — Personal Archive Schema
-- Run via Supabase SQL editor

-- Add personal archive columns to communities table
ALTER TABLE communities ADD COLUMN IF NOT EXISTS owner_id UUID;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS is_personal BOOLEAN DEFAULT false;
ALTER TABLE communities ADD COLUMN IF NOT EXISTS privacy TEXT DEFAULT 'public';

-- Indexes for owner lookup
CREATE INDEX IF NOT EXISTS idx_communities_owner_id ON communities(owner_id);

-- One personal archive per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_communities_personal_owner
    ON communities(owner_id) WHERE is_personal = true;
