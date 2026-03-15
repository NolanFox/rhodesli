-- Session 102: GEDCOM trigram index for fast name search (PERF-006)
-- Run against Supabase SQL editor
-- Requires pg_trgm extension

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gedcom_name_trgm
  ON gedcom_individuals USING GIN (name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gedcom_given_trgm
  ON gedcom_individuals USING GIN (given_name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gedcom_surname_trgm
  ON gedcom_individuals USING GIN (surname gin_trgm_ops);
