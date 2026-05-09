# Session 157b — Track E (GEDCOM upload UAT) deferred to Session 158

**Date**: 2026-05-09
**Decision by**: User (Nolan), in-session
**Recommendation by**: Session 157b orchestrator (Claude Opus 4.7)

## File state at decision time

- Path: `~/Downloads/gedcom_20260508/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`
- Size: 17,912,544 bytes (17.08 MB)
- sha256: `f7832541543d36de144627001028eec4414691439257d120023103036c5bef3f`
- mtime: 2026-05-08 04:20 (same file referenced by Session 156)
- No newer Fox-family GEDCOM exists in `~/Downloads/`
- E1 sha256 freshness check (per retroactive review P2): PASSED — file unchanged since Session 156

The R2 archive at `gedcom-source-snapshots/2026-05-08-session-156/` is still
the canonical archive of this file. No re-archive needed.

## Reasoning for deferral

Day 2 outcomes (Tracks B1-B4) are already strong — PROCEED verdict for
Session 158 cutover. Importing a new GEDCOM version in 157b would:

1. **Add ~250-300 MB to v1** (Lesson 163 v1 scaling issue) just before the
   158 DROP-v1 step that releases that disk anyway. Wasteful.
2. **Force the catch-up backfill (B1) to be re-run** to pull the new
   `is_current=TRUE` rows from v1 into v2. The current B1 NO-OP confirmation
   would be invalidated.
3. **Risk a UAT failure during 157b** that would block the cutover. The
   v1 importer has known bloat issues (Lesson 163); a failed UAT mid-session
   creates rollback work and split-brain risk.

Better path: import AFTER 158 cutover. Once v1 is dropped and v2 is canonical,
the import path either (a) writes to v1 if 158 keeps v1 as a write target
during dual-read, or (b) needs a v2-aware importer. The 158 prompt should
nail down which.

## What rolls to Session 158

### Track E1' (refreshed) — User confirmation
- Re-check sha256 of `~/Downloads/gedcom_20260508/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`
- Re-check `~/Downloads/` for any newer dump
- Confirm with user before proceeding

### Track E2' — Pre-import baseline
Capture row counts for `gedcom_versions`, `gedcom_individuals`,
`gedcom_records`, `gedcom_events`, `gedcom_relationships`, `gedcom_change_log`,
`gedcom_families`, plus v2 row counts and Supabase total DB size.

### Track E3' — Upload via importer
Path TBD based on 158 cutover decisions:
- If v1 still alive: existing `python scripts/import_gedcom.py --file <path>`
- If v1 dropped: needs a v2-aware importer (likely a 158-track work item)

Watch for Lesson 163. Snapshot pre-error state. R2 archive provides rollback.

### Track E4' — 4 verification points
1. Easier to upload — was the rollback path clean?
2. Easier to understand changes per family — query `gedcom_change_manifest`
3. Storage growth fixed — measure size delta. Expected: small (delta only,
   not full-table re-add) since v2 dedup-on-insert is the whole point.
4. Supabase not broken — health endpoints, browser-verify, `pytest`.

### Track E5' — UAT writeup + commit

## BACKLOG entry

`GEDCOM-UAT-156` (originally rolled from 156 to 157, then to 157b) →
DEFERRED again to Session 158 with explicit reasoning above. Update
the BACKLOG entry to reflect the third roll and the strategic
reasoning (storage waste + cutover safety).
