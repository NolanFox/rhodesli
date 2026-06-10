# Session 164 Context — GEDCOM Storage Redesign (PRD-064 / Option B-plus)

**Predecessor:** [session-163-context.md](session-163-context.md) (Supabase Free-tier
recovery + this design)
**Design doc:** [PRD-064](../prds/064_gedcom_history_storage_redesign.md)
**Codex design audit:** [session-163-codex-audit.md](session-163-codex-audit.md)
**Date planned:** 2026-06-09 · **Type:** data-integrity engineering (high stakes)
**Effort:** Opus `max` (Lesson 153–156 category) · think carefully, step-by-step.

## Why this session exists
Session 163 brought production back from a paused/over-quota Supabase project and
discovered the DB had bloated to 1.3 GB — **96% GEDCOM, most of it duplicate rows from
failed-and-retried imports**. We cleaned it to 423 MB (no data loss; all archived to R2)
but the underlying data model is still wrong: `gedcom_individuals_v2` keeps full JSON
rows per version-state, the importer is **not atomic** (per-batch commits leave orphan
rows on failure — the actual bloat root cause), and version history is stored the
wasteful way. PRD-064 + Codex audit settled the target design: **Option B-plus**.

## The design (B-plus) — see PRD-064 §4 for detail
- **Postgres = current state only:** one row per individual/family/relationship. No
  `is_current`, no multi-state rows, no `gedcom_*_v2` suffix churn.
- **Postgres = tiny per-version manifest** (`gedcom_versions`) with when/who/counts/
  source-hash + SHA-256 of each R2 artifact.
- **R2 = immutable per successful version:** raw GEDCOM + canonical snapshot +
  entity-level `{before, after, hashes}` diff (compressed, content-addressed).
- **Import = ONE Postgres transaction** (port 5432 + `pg_advisory_xact_lock`); R2
  upload+verify is a prerequisite; any error → full rollback. (Fixes R5.)
- **Unwind = conflict-checked compensating version** (three-way hash check), never
  reverse-replay.

## Requirements being satisfied (user, Session 163)
R1 always record changes · R2 fast latest retrieval · R3 always unwind + track when ·
R4 stay < 500 MB Free with headroom · R5 failed imports leave ZERO rows.

## Design tenets (user's quality bar — these are acceptance gates, not vibes)
- **Amazingly good but NOT over-engineered.** Imports are rare (2 real in 4 months) and
  admin-only — do not build distributed-systems machinery for a once-a-quarter batch job.
- **Doesn't break.** Atomic; failed import = zero rows; covered by structural tests.
- **No bloat.** Current-state-only in DB; history compressed in R2. Target DB ≤ 300 MB.
- **Runs fast.** Latest-version reads need no version filtering or dedup.
- **Preserves everything but practical.** Full lossless history in R2; exact unwind;
  but history is NOT duplicated into expensive Postgres.

## Codex P0/P1 to resolve (from the design audit — verify each is fixed)
- P0: importer not atomic (`import_gedcom_version.py:516` per-batch commits;
  `test_gedcom_versioning.py:649` asserts rows survive failure — that test must be
  inverted to assert ZERO rows survive).
- P0: change-log adds/removes store NULL→NULL (can't reconstruct) → entity-level
  before/after payloads instead.
- P0: `--skip-change-log` / non-fatal change-log makes audit optional → remove; R2
  artifact write is mandatory.
- P1: diff compares full DB rows incl. metadata + positional list paths → diff canonical
  semantic payloads only.
- P1: reverse-replay unsafe → compensating-version + three-way hash check.
- P2: version-number MAX+1 races → allocate inside txn under advisory lock; single
  authoritative `imported_at`/`imported_by`; content-addressed R2 keys + SHA-256.

## Technical debt to clean up this session
- `app/gedcom_dual_read.py` (v1/v2 dual-read shim) — collapse once v2 is gone.
- `gedcom_individuals_v2` / `gedcom_families_v2` naming → canonical `gedcom_individuals`
  / `gedcom_families` (current-state). Archive + drop the `_v2` tables.
- Failed-version rows in `gedcom_versions` (7 of 9) — keep as audit metadata but ensure
  no orphan entity rows remain.
- Vestigial views already dropped (`current_gedcom_events/records`). Verify
  `current_gedcom_relationships` view is still correct or fold into current-state table.
- `scripts/session163_gedcom_cleanup.py` snapshot/cleanup is one-off — fold the
  R2-archive step into the importer as a mandatory prerequisite.

## State inherited from Session 163 (verify FIRST in Phase 0)
- DB ~423 MB (`gedcom_individuals_v2` 267 MB the remaining target). Supabase project
  `fvynibivlphxwfowzkjl`, org `pkkbvxtoywxxfwyajikj`, Free plan, billing cycle resets
  ~25 Jun 2026.
- **Site is DOWN** (Fair-Use restriction; lifts only on Pro upgrade or cycle reset).
- R2 snapshots: `gedcom-cleanup-snapshots/2026-06-08-session-163/` (full events/records/
  relationships, sha256 in manifest.json) + `gedcom-version-snapshots/2026-05-08-session-156/`.
- Pooler session mode (port 5432, user `postgres.<ref>`) works; Management API SQL
  endpoint works even under restriction; Railway CLI was Unauthorized (need `railway login`).
- `SUPABASE_ACCESS_TOKEN` (sbp_) is in `.env`.

## Billing decision (user)
User will **upgrade to Pro once the data layer is solid** (pays for full month → do it
when everything's good), then optionally downgrade to Free next cycle (DB will fit
comfortably). Upgrade is the only way to lift the restriction before ~25 Jun.

## How version history will actually be USED (user, Session 163)
We do NOT need fast in-DB recall of past GEDCOM versions. But we WILL eventually want to
**highlight "what's new" version-over-version** (e.g. "this GEDCOM added 54 people,
changed 12 — here's the list") — valuable for rhodesli AND for fox-genealogy /
rhodes-wiki. The B-plus design serves this directly and cheaply:
- The per-version R2 `diff.json.gz` artifact (`{added, modified, removed}` with typed
  before/after) IS the "what changed" record. A "what's new" view reads one artifact.
- `gedcom_versions` caches a tiny **diff summary** (counts + changed entity-IDs only,
  payloads stay in R2) so the overview is instant without touching R2.
- Keep the artifact schema clean + documented (`docs/architecture/GEDCOM_HISTORY.md`) so
  it's a reusable cross-repo standard for all genealogy work.
This means the artifact format is a first-class deliverable, not just a backup.

## Deferred to a later session
- RHODES-WIKI-004 (original 163 scope: dossier auto-update + wiki/ pages).
- Optional: in-DB queryable change history (only if a real use case appears; R2 diffs
  suffice for now).
