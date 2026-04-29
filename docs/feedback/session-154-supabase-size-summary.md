# Session 154 — Supabase DB Size Summary (Phase E0, Read-Only)

**Captured:** 2026-04-29 (UTC) via session pooler `aws-0-us-west-2.pooler.supabase.com:5432`
**Total DB size:** 2,269 MB (2.22 GB)
**Free-tier limit:** 1,100 MB → **over by ~1.17 GB**
**Grace ends:** 2026-05-29

> Phase E0 = discovery only. NO deletes. Phase E1 will plan pruning based on this.
> See raw machine-readable data in `session-154-supabase-size-baseline.json`.

---

## Top-line finding

**GEDCOM-related tables consume 97.9% of the database (2.17 GB of 2.22 GB).**
Everything else combined (auth, identities, photos, embeddings, faces, gemini calls,
audit logs, etc.) is only ~50 MB. **All pruning gains are in `gedcom_*` tables.**

---

## Top 5 tables by total bytes

| Rank | Table | Total | Table | Idx | Rows (exact) | Notes |
|------|---|---|---|---|---|---|
| 1 | `public.gedcom_individuals` | **783 MB** | 434 MB | 25 MB | 196,645 | TOAST = 324 MB (huge JSONB blobs in `raw_record_json`/`names_json`/`birth_event_json`) |
| 2 | `public.gedcom_relationships` | **406 MB** | 270 MB | 136 MB | 872,738 | Index overhead is 33% of total |
| 3 | `public.gedcom_change_log` | **397 MB** | 260 MB | 131 MB | **1,646,688** | Lesson 163 alarm — versioned-importer journal that never gets pruned |
| 4 | `public.gedcom_events` | **273 MB** | 245 MB | 27 MB | 226,116 | TOAST tiny; bulk is `raw_node_json` + `citations_json` |
| 5 | `public.gedcom_records` | **272 MB** | 235 MB | 12 MB | 118,824 | `root_json` alone = 106 MB |

Other tables of any meaningful size:
- `public.gedcom_families` — 75 MB / 33,324 rows
- `public.gemini_api_calls` — 12 MB / 904 rows (NOT a problem despite being TEXT-heavy)
- `public.gedcom_media_objects` — 8.7 MB / 3,352 rows
- `public.gedcom_sources` — 6.7 MB / 3,228 rows
- Everything else < 7 MB

---

## Biggest single columns (suspected pruning targets)

These are the columns that, if any could be dropped or shrunk, would reclaim the most:

| Column | Table | Bytes | Notes |
|---|---|---|---|
| `raw_record_json` | gedcom_individuals | **179.55 MB** | Raw GEDCOM payload. Likely redundant if structured columns are used elsewhere. |
| `root_json` | gedcom_records | **106.30 MB** | Whole-record JSONB. Same denormalization concern. |
| `names_json` | gedcom_individuals | 87.98 MB | |
| `raw_node_json` | gedcom_events | 86.95 MB | |
| `birth_event_json` | gedcom_individuals | 68.27 MB | |
| `xref_id` | gedcom_change_log | 54.01 MB | TEXT, repeated across 1.6 M rows. Index-eligible compression, or change_log truncation. |
| `citations_json` | gedcom_events | 52.91 MB | |
| `payload_hash` | gedcom_relationships | 45.08 MB | TEXT hash, 873K rows. |
| `raw_text` | gedcom_records | 38.83 MB | |
| `edge_key` | gedcom_relationships | 32.66 MB | |
| `id`, `version_id` | gedcom_change_log | 25.13 MB each | UUID columns × 1.6 M rows. |

---

## Suspected pruning targets (for Phase E1 to evaluate, NOT yet acted on)

1. **`gedcom_change_log` — 397 MB, 1.65 M rows.** This is exactly what Lesson 163
   warned about. Confirm whether anything actually reads from it (audit/rollback?)
   or whether it's pure dead weight from the importer. **Truncating or aggressive
   retention (e.g., last N versions) likely reclaims ~400 MB cleanly.**

2. **Raw JSON denormalization columns** (`raw_record_json`, `root_json`,
   `raw_node_json`, `raw_text`) — total ~411 MB across 4 tables. If the importer
   stores raw GEDCOM AND parses it into structured columns, the raw blobs may be
   redundant. **Need to check if anything queries these at runtime** before
   dropping.

3. **`gedcom_relationships` indexes — 136 MB / 33% of table total.** Investigate
   whether all indexes are actually used (`pg_stat_user_indexes.idx_scan`).
   Unused indexes are pure waste here.

4. **Multiple GEDCOM versions accumulated.** Need to query `gedcom_records` for
   distinct version_ids and confirm whether old GEDCOM versions are kept
   forever vs only the current one — Lesson 165 mentioned the IS-NULL view bug;
   we may have unversioned legacy rows + versioned new rows BOTH retained.

---

## Biggest open questions for Phase E1

1. **Is `gedcom_change_log` (1.65M rows) read by anything in production?** If no,
   it's 397 MB of free reclaim. Lesson 163 says the importer can't even finalize
   when this table grows large — so it's actively HARMFUL.
2. **How many distinct GEDCOM versions are stored?** If we keep 5 versions × 175 K
   individuals each, that's our 783 MB. Might be reducible to current-only.
3. **Are the `_json` raw blobs queried at runtime, or only during import?** If
   import-only, they can be dropped post-finalize.
4. **Does PostgreSQL have any bloat?** `pg_total_relation_size` includes dead tuples
   that VACUUM FULL would reclaim. We should run `pgstattuple` on the top 5 tables
   in Phase E1 to estimate dead-row overhead before designing pruning.
5. **Why does `gedcom_relationships` have 136 MB of indexes?** Need an
   index-usage audit (`pg_stat_user_indexes`).

---

## Things that are NOT a problem

- `gemini_api_calls` is only 12 MB despite OD-011 worrying about it. ✓
- All identity/photo/face tables combined are < 10 MB. ✓
- Auth and audit_log are negligible. ✓
- No surprise high-egress culprit hiding outside the GEDCOM stack.

---

## Connection notes for future sessions

- Direct DB host (`db.<ref>.supabase.co`) is **IPv6-only**. Local Macs without IPv6
  cannot reach it.
- **Use the session pooler:** `aws-0-us-west-2.pooler.supabase.com:5432`
  with username `postgres.fvynibivlphxwfowzkjl` and the same password.
- Project region is `us-west-2`.
- Add `DATABASE_URL_POOLER` to `.env` to make this reusable. (Phase E1 prep.)

---

## Notes / anomalies

- `pg_class.reltuples` was within ~3% of `COUNT(*)` for all top-5 tables —
  autovacuum is running, stats are fresh.
- No connection / rate-limit issues encountered. Free-tier limits do NOT block
  read-only catalog queries.
- Total reported by `pg_database_size` (2,269 MB) is slightly less than the
  Supabase email's 2.39 GB; the email likely includes WAL, replication slots, or
  control-plane overhead beyond what `pg_database_size` reports.
