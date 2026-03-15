-- Migration: Add trigram indexes for GEDCOM name search
-- Context: FB-120 / PERF-006 — GEDCOM search takes ~1 minute, needs <3s
-- The pg_trgm extension enables fast fuzzy/ILIKE searches via GIN indexes.
--
-- Run against Supabase Postgres:
--   psql $DATABASE_URL -f scripts/migrations/add_gedcom_trigram_index.sql
--
-- CONCURRENTLY avoids table locks on production.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gedcom_name_trgm
  ON gedcom_individuals USING GIN (name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gedcom_given_trgm
  ON gedcom_individuals USING GIN (given_name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gedcom_surname_trgm
  ON gedcom_individuals USING GIN (surname gin_trgm_ops);
