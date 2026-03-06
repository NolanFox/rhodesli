# PRD-027: Data Migration — Railway Volume JSON to Supabase/Postgres

**Author:** Session 90, Track D
**Date:** 2026-03-05
**Status:** Draft
**Session:** Future (estimated 2-3 sessions)

---

## Problem Statement

Rhodesli's core data (identities, photo index, embeddings) lives on a Railway persistent volume as JSON/NumPy files. If the volume is lost — due to Railway infrastructure failure, accidental deletion, or disk corruption — there is no automated recovery path. The app would go fully offline until data is manually reconstructed from git history and R2 photos.

Session 59C migrated *user-entered* data (annotations, identity overrides, relationships, GEDCOM matches) to Supabase via dual-write (AD-135). But the three most critical files — `identities.json`, `photo_index.json`, and `embeddings.npy` — remain volume-only with no real-time backup.

**Who is affected:** Everyone. A volume loss means complete data loss for the archive.

**Why now:** The archive is actively shared with the Jews of Rhodes Facebook community (~2,000 members). Data loss would destroy community trust and months of admin curation (69 confirmed identities, 665 total identities, 274 photos).

---

## Current State: What Lives Where

### Railway Volume (HIGH risk — single point of failure)

| File | Records | Size | Description | Backup? |
|------|---------|------|-------------|---------|
| `identities.json` | ~777 identities | ~500KB | Identity metadata, face assignments, states, merge history | Git only (stale) |
| `photo_index.json` | ~296 photos, ~982 faces | ~200KB | Photo metadata, face-to-photo mapping, dimensions | Git only (stale) |
| `embeddings.npy` | ~1182 embeddings | ~2.3MB | 512-dim face embedding vectors (NumPy pickle) | Git only (stale) |
| `date_labels.json` | ~100+ labels | ~20KB | Human-verified photo date labels for ML training | Git only (stale) |
| `photo_locations.json` | ~270 entries | ~50KB | Gemini-estimated photo locations | Git only (stale) |
| `birth_year_estimates.json` | ~200+ entries | ~30KB | ML-estimated birth years per identity | Git only (stale) |
| `proposals.json` | variable | ~50KB | ML clustering proposals for admin review | Regenerable |
| `co_occurrence_graph.json` | ~300 nodes | ~100KB | Face co-occurrence in photos | Regenerable |
| Other optional files | — | ~50KB | `surname_variants.json`, `photo_search_index.json`, `rhodes_context_events.json`, `location_dictionary.json` | Git / regenerable |

**Critical gap:** Git-bundled copies are only updated on deploy (`git push`). Between deploys, admin actions (confirm, merge, rename, reject) modify `identities.json` on the volume. A volume loss between deploys loses all admin work since the last push.

### Supabase/Postgres (LOW risk — managed, backed up)

| Table | Records | Description | Source of Truth? |
|-------|---------|-------------|-----------------|
| `identity_overrides` | ~100+ | User-modified identity records (CONFIRMED, SKIPPED, merged, metadata) | Yes (AD-135) |
| `annotations` | ~50+ | Community name suggestions, bios | Yes |
| `relationships` | ~1,019 | Person-to-person relationships (UUID + GEDCOM) | Yes |
| `gedcom_matches` | ~56 | GEDCOM-to-identity link decisions | Yes |
| `gedcom_individuals` | ~21,809 | GEDCOM family tree individuals | Yes |
| `gedcom_relationships` | ~145,574 | GEDCOM family relationships | Yes |
| `gedcom_events` | ~40,140 | GEDCOM life events (birth, death, marriage) | Yes |
| `gedcom_versions` | ~2 | GEDCOM file version tracking | Yes |
| `gedcom_enrichment_queue` | variable | Pending GEDCOM enrichment tasks | Yes |
| `gedcom_face_links` | ~61 | Identity-to-GEDCOM linking with confidence | Yes |
| `face_gemini_alignments` | ~270 | Gemini face alignment results per photo | Yes |
| `gemini_api_calls` | ~500+ | API call audit log (cost, tokens, status) | Yes |

### Cloudflare R2 (LOW risk — object storage with redundancy)

| Content | Count | Description |
|---------|-------|-------------|
| `raw_photos/` | ~274 | Full-resolution archive photos |
| `crops/` | ~1000+ | Face crop thumbnails |

### Recovery capability if volume is lost TODAY

| Data | Recovery | Effort | Data Loss |
|------|----------|--------|-----------|
| Raw photos + crops | R2 restore | Minutes | None |
| User-modified identities | Supabase `identity_overrides` -> JSON rebuild | ~1 hour | None (dual-write since Session 59C) |
| Annotations, relationships, GEDCOM matches | Supabase -> JSON rebuild | ~1 hour | None |
| GEDCOM tree data | Supabase (21K+ individuals) | Minutes | None |
| Face alignments | Supabase `face_gemini_alignments` | Minutes | None |
| **ML-only identities (PROPOSED, INBOX)** | **Git bundle (stale)** | **Hours** | **All changes since last deploy** |
| **photo_index.json** | **Git bundle (stale)** | **Hours** | **All photos added since last deploy** |
| **embeddings.npy** | **Git bundle (stale) + re-run face detection** | **Days** | **Re-detection may produce different face IDs** |
| **date_labels.json** | **Git bundle (stale)** | **Hours** | **Labels added since last deploy** |
| **photo_locations.json** | **Re-run Gemini (~$8)** | **Hours + cost** | **Regenerable but costs money** |

**Verdict:** User-curated data (the most valuable kind) is protected. But ML pipeline data and the photo registry have no real-time backup. A volume loss would require hours of reconstruction and would likely produce face ID mismatches.

---

## Migration Options

### Option A: Nightly R2 Backup (Minimal Change)

**Concept:** Cron job (or Railway scheduled task) copies critical JSON/NPY files to R2 nightly.

**What changes:**
- New script: `scripts/backup_to_r2.py` — uploads `identities.json`, `photo_index.json`, `embeddings.npy`, `date_labels.json`, `photo_locations.json` to `r2://rhodesli-photos/backups/YYYY-MM-DD/`
- Railway cron or startup hook triggers it
- Recovery script: `scripts/restore_from_r2.py`

**Effort:** 1 session (half-day)

| Pros | Cons |
|------|------|
| Minimal code change | Up to 24 hours of data loss |
| No schema migration | Still JSON-based, no query capability |
| Easy rollback (just stop cron) | Doesn't address the architectural debt |
| Works with existing init_railway_volume.py | Backup could silently fail |

**Risk:** LOW. Worst case: backup script has a bug and doesn't run; status quo unchanged.

**Rollback:** Delete the cron job. No data changes.

---

### Option B: Shadow Writes (Dual-Write JSON + Supabase)

**Concept:** Extend the existing dual-write pattern (already used for identity_overrides) to cover ALL identities, photo_index, and embeddings metadata.

**What changes:**

1. **New Supabase tables:**
   - `identities` — all 777 identities (not just user-modified ones)
   - `photos` — all 296 photos with metadata
   - `faces` — all 982 face records with photo_id, identity_id, bbox
   - `face_embeddings` — 1182 embedding vectors (as `float4[]` or `vector(512)`)

2. **Dual-write in app:**
   - `save_registry()` -> upserts to `identities` table (already partially done via `identity_overrides`)
   - `save_photo_registry()` -> upserts to `photos` + `faces` tables
   - Embedding changes -> upserts to `face_embeddings`

3. **Startup sync unchanged:** JSON remains primary read path; Supabase is backup.

4. **Future flip:** Once Supabase data is verified consistent, flip read path to Postgres.

**Effort:** 2-3 sessions

| Session | Scope |
|---------|-------|
| 1 | Schema design + table creation + migration script for existing data |
| 2 | Dual-write wiring in save_registry/save_photo_registry + tests |
| 3 | Verification, consistency checks, optional read-path flip |

| Pros | Cons |
|------|------|
| Incremental — app continues working on JSON | More code to maintain (dual-write) |
| Proven pattern (identity_overrides already works) | Supabase write failures degrade silently |
| Enables future Postgres-first architecture | Embedding vectors need pgvector or float arrays |
| Real-time backup (every save goes to Supabase) | Test suite needs mock updates for new tables |
| Enables SQL queries on identity/photo data | |

**Risk:** MEDIUM. Dual-write bugs could cause Supabase data to diverge from JSON. Mitigation: consistency check script that compares JSON vs Supabase counts and checksums.

**Rollback:** Remove dual-write calls. Supabase tables remain but are unused. JSON continues as before.

---

### Option C: Full Migration (Supabase Source of Truth)

**Concept:** Move ALL data reads and writes to Supabase. JSON files become export artifacts, not the source of truth.

**What changes:**

1. **Everything in Option B**, plus:
2. **Replace JSON reads:** `IdentityRegistry.load()` reads from Supabase, not `identities.json`
3. **Replace photo_index reads:** `PhotoRegistry.load()` reads from Supabase
4. **Replace embedding reads:** `np.load(embeddings.npy)` replaced with Supabase query
5. **Remove atomic file writes:** No more portalocker, temp files, etc.
6. **Remove init_railway_volume.py data sync:** Volume only needed for model weights
7. **Update deploy pipeline:** No more git-bundled JSON files

**Effort:** 4-6 sessions

| Session | Scope |
|---------|-------|
| 1 | Schema design + table creation + bulk migration |
| 2 | IdentityRegistry Postgres adapter (read + write) |
| 3 | PhotoRegistry Postgres adapter + face/embedding queries |
| 4 | Remove JSON read paths, update all tests (~200+ test mocks reference JSON) |
| 5 | Embedding vector handling (pgvector vs float arrays, neighbor queries) |
| 6 | Verification, deploy pipeline update, cleanup |

| Pros | Cons |
|------|------|
| Clean architecture — one source of truth | Highest effort (4-6 sessions) |
| SQL queries unlock analytics, search, filtering | ~200+ tests need mock updates |
| pgvector enables in-database similarity search | Supabase latency adds ~50ms per read |
| No more deploy data safety concerns | Railway volume still needed for ML model weights |
| Eliminates entire class of JSON sync bugs | If Supabase is down, app is down (no fallback) |
| Simplifies init_railway_volume.py | embeddings.npy neighbor search is fast in NumPy — Postgres may be slower |

**Risk:** HIGH during migration. A bug in the Postgres read path could serve stale or empty data. Mitigation: feature flag (`DATA_SOURCE=json|postgres`) to flip between backends.

**Rollback:** Flip feature flag back to `json`. JSON files are still on the volume.

---

## Comparison Matrix

| Criterion | A: R2 Backup | B: Shadow Writes | C: Full Migration |
|-----------|-------------|-------------------|-------------------|
| **Data loss window** | Up to 24h | Near-zero (per-save) | Near-zero |
| **Recovery time** | ~1 hour | ~10 min (rebuild JSON from Supabase) | Instant (Supabase IS the data) |
| **Effort** | 1 session | 2-3 sessions | 4-6 sessions |
| **Risk during implementation** | Low | Medium | High |
| **Architectural improvement** | None | Moderate (backup + future-ready) | Full (clean architecture) |
| **Test suite impact** | None | ~20 new tests | ~200+ test updates |
| **Enables SQL queries** | No | Yes (write side) | Yes (read + write) |
| **Enables pgvector search** | No | No | Yes |
| **Deploy safety improvement** | Minor | Significant | Eliminates the problem |

---

## Recommendation

**Do A now, then B. Defer C.**

### Phase 1: R2 Backup (Next available session, ~0.5 days)

Ship nightly R2 backups immediately. This closes the "total data loss" risk with minimal code change. Even if everything else is deferred, this prevents catastrophic loss.

### Phase 2: Shadow Writes (2-3 sessions, ~1-2 weeks)

Extend the proven dual-write pattern to all identities and photo_index. This gives near-zero data loss window and positions for a future Postgres-first flip. The identity_overrides pattern is already battle-tested.

**Key design decisions for Phase 2:**
- Embedding storage: `float4[]` column vs pgvector `vector(512)`. Recommend `float4[]` initially (simpler, no extension needed), with pgvector migration as a future optimization.
- Table granularity: One `identities` table (full records as JSONB) vs normalized tables. Recommend JSONB initially (matches current identity_overrides pattern), normalize later.
- Consistency checking: Weekly cron that compares JSON record counts + checksums against Supabase.

### Phase 3: Full Migration (Future, when triggered)

**Trigger:** When any of these occur:
- 3+ JSON sync bugs in a 4-week period
- Need for SQL-based analytics or search
- pgvector similarity search becomes a product requirement
- Railway volume has an actual failure

Until triggered, the dual-write pattern provides adequate safety without the test suite disruption of a full migration.

### Timeline

| Phase | Target | Effort | Prerequisite |
|-------|--------|--------|--------------|
| A: R2 Backup | Session 91 | 0.5 days | R2 credentials in Railway env |
| B: Shadow Writes | Sessions 92-93 | 2-3 days | Phase A complete |
| C: Full Migration | TBD (triggered) | 4-6 days | Phase B running stable for 2+ weeks |

---

## Out of Scope

- pgvector installation and similarity search optimization
- Multi-tenant data isolation
- GDPR/data deletion compliance
- Photo binary storage migration (already in R2)
- ML model weight storage (stays on Railway volume)
- CI/CD pipeline changes (separate BACKLOG item OPS-002)

---

## Technical Constraints

- Supabase free tier: 500MB database, 1GB file storage — current data fits easily (~3MB total)
- Railway persistent volume: 5GB, currently ~2GB used (mostly ML model weights)
- `embeddings.npy` uses NumPy pickle format with `allow_pickle=True` — needs serialization for Postgres
- `neighbors.py` is FROZEN — any embedding storage change must preserve the same API
- Face IDs have two formats (legacy `Image 924_compress:face4` and inbox `inbox_739db7ec49ac`) — schema must handle both
- Supabase PostgREST has a 1000-row default limit — pagination required for bulk reads (already handled in relationship sync)
