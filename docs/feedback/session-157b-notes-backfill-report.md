# Session 157b — NOTES-BACKFILL-156 Report

**Run mode:** DRY-RUN
**Run timestamp:** 2026-05-09T02:22:20.542555+00:00
**Script:** `scripts/session157_notes_backfill.py`

## Survey

- Local identities (data/identities.json): 3457
- Supabase identities: 4112
- Identities in both: 3457
- Identities only in local: 0
- Identities only in Supabase: 655
- Total local top-level notes: 0
- Total local metadata.notes: 0
- Total Supabase metadata.notes: 0
- Identities needing backfill: 0

## Result

**No deltas found.** Local data has no orphan notes that are missing from Supabase.

Interpretation: between Sessions 105-156, no `add_note()` calls landed in
production data that weren't already round-tripped through Supabase metadata.
The Lesson 179 round-trip fix shipped in Session 156 (commit on main) is
sufficient — there is no historical orphan corpus requiring migration.

The single Supabase identity with metadata.notes
(`ef39908e-283a-4cec-8f72-3ec83bc8d84f` — Belle Isle Conservatory Young Man)
was created in Session 156 itself, after the round-trip fix landed.

## Algorithm

1. Read `data/identities.json` (in-memory dict the app shadow-writes from).
2. Read all Supabase `identities` rows (paginated, >1000 supported).
3. For each identity in BOTH, reconcile note sources:
   - Local top-level `notes` (the keypath `add_note()` writes).
   - Local `metadata.notes` (in case any path wrote there directly).
   - Supabase `metadata.notes` (the persisted source).
4. Dedup by `note.id` if present, else by `(text, timestamp)`.
5. Where local has notes Supabase doesn't, write the union back via
   `shadow_write_identity(strict=True)` so Session 156's round-trip
   embeds top-level `notes` into `metadata.notes` correctly.

## Lineage

- Lesson 179: round-trip notes silently dropped Sessions 105-156.
- Session 156 commit `feat(session-156)`: shadow_write_identity round-trip fix.
- Session 157b Track A1.2 (this run): orphan reconciliation.
