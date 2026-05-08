**Parent:** [PRD-063 hub](../063_gedcom_mirror_efficient_redesign.md)

# PRD-063 Appendix — E0.5 source SQL queries

Captured 2026-04-29 via `aws-0-us-west-2.pooler.supabase.com:5432`. Full
results are in `docs/feedback/session-154-supabase-bloat-root-cause.json`.

```sql
-- q1: duplication factor
SELECT COUNT(DISTINCT gedcom_id), COUNT(*) FROM gedcom_individuals;
-- q2: per-version row counts
SELECT version_id, status, COUNT(*) FROM gedcom_individuals
  LEFT JOIN gedcom_versions ON gedcom_versions.id = gedcom_individuals.version_id
  GROUP BY 1, 2 ORDER BY 1;
-- q3: top duplicated payload_hash groups
SELECT payload_hash, COUNT(*) FROM gedcom_individuals
  WHERE payload_hash IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 20;
-- q4: change_log NULL/NULL phantom rows
SELECT COUNT(*) FILTER (WHERE old_value IS NULL AND new_value IS NULL),
       COUNT(*) FROM gedcom_change_log;
-- q5: index usage
SELECT relname, indexrelname, pg_relation_size(indexrelid), idx_scan
  FROM pg_stat_user_indexes WHERE relname LIKE 'gedcom_%' ORDER BY 3 DESC;
```
