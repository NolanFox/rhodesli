# PRD-051: Single Source of Truth — Eliminate JSON Data Split-Brain

**Author:** Session 111d
**Status:** PROPOSED
**Priority:** P0 — Data integrity (8 documented incidents)
**Estimated effort:** 4-5 sessions across 4 phases

## Problem Statement

Rhodesli stores structured data in THREE places simultaneously:
1. **Local JSON files** (committed to git, used by ML pipeline)
2. **Railway volume JSON files** (seeded from git on deploy, mutated by admin actions)
3. **Supabase Postgres** (shadow-synced, sometimes background threads that silently fail)

When any write to one source fails, the sources diverge. The next read may come from a different source than the last write went to. This has caused **8 documented data corruption incidents** across Sessions 56, 69, 78, 85, 133, 141, 144, 147, and 150.

Session 111d: Direct Supabase data repair didn't propagate to the Railway volume OR the `identity_overrides` table, leaving a stale `merged_into` redirect active for 30+ minutes despite multiple deploy restarts.

## Proposed Solution

Make **Supabase Postgres the single source of truth** for all structured data. Eliminate JSON reads in production entirely. Keep JSON only as:
- Emergency backup (written alongside Supabase, never read in production)
- ML pipeline input (local dev only, synced FROM Supabase)

## Current Data Inventory

| File | Size | In Supabase? | Can Eliminate JSON Read? |
|------|------|-------------|------------------------|
| `identities.json` | 1.9 MB | Yes | **YES — Phase 1** |
| `photo_index.json` | 703 KB | Yes | **YES — Phase 1** (caution: `_build_caches()` reads directly) |
| `proposals.json` | 216 KB | Partially (`ml_proposals`) | **YES — Phase 2** |
| `date_labels.json` | — | Yes | **YES — already has Supabase path** |
| `photo_locations.json` | — | Yes | **YES — already has Supabase path** |
| `birth_year_estimates.json` | — | Yes | **YES — already has Supabase path** |
| `annotations.json` | — | Yes | **YES — Phase 2** |
| `embeddings.npy` | 12.5 MB | No | **NO — must stay on disk** |
| `surname_variants.json` | — | No | **No — static reference, no split-brain risk** |

## Phase Plan

### Phase 1: Eliminate dual-read for identities and photos (1 session) — DONE (Session 112)
**Goal:** Production never reads from JSON for identities or photos.

1. Remove all `if DATA_SOURCE == "json"` branches from read paths
2. Set `DATA_SOURCE=postgres` as the ONLY mode (remove the config option)
3. Fix `_build_caches()` to use `load_photo_registry()` instead of `json.load(photo_index.json)`
4. Keep JSON writes as backup only (write-through, never read back)
5. Set `DATA_SOURCE=postgres` in local `.env` so dev matches production
6. Tests: verify all read paths go through Supabase, not JSON

### Phase 2: Wire remaining JSON-only reads to Supabase (1-2 sessions) — DONE (Session 114)
1. `proposals.json` → read from `ml_proposals` table
2. `annotations.json` → read from `annotations` table
3. `relationships.json` → read from `relationships` table
4. `gedcom_matches.json` → read from `gedcom_matches` table
5. `photo_search_index.json` → Supabase full-text search or keep as static

### Phase 3: Refactor ML pipeline for Supabase reads (1 session) — DEFERRED (local-only, no prod risk)
1. `cluster_new_faces.py`: Use `IdentityRegistry.load_from_postgres()` instead of `json.load()`
2. `ingest_inbox.py`: Write identities/photos to Supabase directly
3. Simplify `push_to_production.py` — only needed for `embeddings.npy` + crops
4. Add `load_dotenv()` to all ML scripts

### Phase 4: Remove JSON from deploy pipeline (1 session) — DONE (Session 114)
1. Remove `identities.json` and `photo_index.json` from `REQUIRED_DATA_FILES`
2. Update `init_railway_volume.py` — only require `embeddings.npy`
3. Remove JSON fallback code from all load functions
4. Add Supabase health check to app startup
5. Keep JSON generation as optional backup/export command

## What Stays on Disk Permanently
- `embeddings.npy` — binary NumPy, cannot go in Supabase
- `surname_variants.json` — static reference data, bundled in git
- `rhodes_context_events.json` — static reference data
- Face crops and raw photos — served from R2

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Supabase downtime = app has no data | Add startup health check. Keep JSON as emergency read-only fallback (separate from normal read path). |
| Egress budget (free plan 5GB/month) | Current estimate ~1-2 GB/month with 1 admin. Monitor. Upgrade to Pro ($25/mo) if needed. |
| Performance — Supabase reads slower than JSON | TTL caches already in place (120s for registry). Cold load ~200-400ms vs ~50ms for JSON. Acceptable. |
| ML pipeline needs local data | ML scripts read from Supabase via `load_from_postgres()`. Only `embeddings.npy` stays local. |
| Breaking changes during migration | Phase 1 is the critical fix. Each phase is independently shippable. Tests gate every change. |

## Success Criteria
- Zero data divergence incidents after Phase 1
- No JSON files read in production code paths
- `_build_caches()` does not call `json.load()`
- All admin actions (confirm, merge, reject, skip, tag) persist immediately and survive app restart
- Direct Supabase data repairs take effect within TTL window (120s) without deploy restart

## Out of Scope
- pgvector migration for embeddings (separate initiative, deferred)
- Multi-tenant database architecture (future)
- Real-time sync / websockets
