# pgvector Migration Evaluation

**Last updated:** 2026-03-07
**Status:** DEFERRED
**Decision context:** Phase F (Scale & Generalize), ROADMAP.md

---

## Current State

Face embeddings are stored in `data/embeddings.npy` as a NumPy array of dicts,
loaded with `np.load(path, allow_pickle=True)`.

| Metric | Value |
|--------|-------|
| Embedding count | ~550 faces |
| Dimensions | 512 (PFE vectors from InsightFace) |
| File size | ~2.3 MB |
| Load time | <100ms (local file read) |
| Similarity search | In-memory NumPy dot product (Euclidean distance) |
| Location | Railway persistent volume (`data/embeddings.npy`) |

The app loads all embeddings into RAM at startup via `_build_caches()` in
`app/main.py`. Nearest-neighbor search uses `core/neighbors.py` (FROZEN --
do not modify) which computes pairwise distances against the full set.

---

## pgvector Capability

Supabase natively supports the `pgvector` extension with:
- `vector(512)` column type for storing embeddings
- HNSW index for approximate nearest neighbor (ANN) search
- IVFFlat index as an alternative for smaller datasets
- Cosine, L2 (Euclidean), and inner product distance functions
- SQL-native similarity search: `ORDER BY embedding <-> query_vector LIMIT k`

### Proposed Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE face_embeddings (
    face_id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(photo_id),
    embedding vector(512) NOT NULL,
    det_score FLOAT,
    quality FLOAT,
    bbox JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- HNSW index for fast ANN search
CREATE INDEX face_embeddings_hnsw_idx
    ON face_embeddings USING hnsw (embedding vector_l2_ops)
    WITH (m = 16, ef_construction = 64);
```

---

## Migration Path

1. **Backfill script**: Read `embeddings.npy`, insert each entry into
   `face_embeddings` table via Supabase client. Map face_id from filename+index
   or explicit face_id field.
2. **Dual-read period**: App reads from both NumPy (primary) and Postgres
   (shadow) for validation. Compare search results for consistency.
3. **Flip**: Set `EMBEDDING_SOURCE=postgres` env var. App queries Supabase
   for similarity search instead of local NumPy.
4. **Cleanup**: Remove `embeddings.npy` from git tracking, `REQUIRED_DATA_FILES`,
   and `init_railway_volume.py`.

Estimated effort: 2-3 session tracks (backfill, dual-read validation, flip).

---

## Pros

| Benefit | Detail |
|---------|--------|
| Unified data layer | All structured data in one place (Supabase) |
| SQL similarity search | `ORDER BY embedding <-> $1 LIMIT 10` replaces custom Python |
| No .npy management | Eliminates file sync, git tracking, deploy bundling |
| Scalable indexing | HNSW handles 100K+ vectors efficiently |
| Transactional writes | Embedding inserts are atomic with identity creation |
| Backup included | Supabase handles backup/restore for embeddings |
| Multi-service access | ML service can query same embeddings without file sync |

---

## Cons

| Risk | Detail |
|------|--------|
| Query latency | Network round-trip (~5-50ms) vs local NumPy (<1ms) |
| ANN accuracy | HNSW is approximate; exact search requires seq scan |
| Migration complexity | 550 embeddings with mixed ID formats (legacy + inbox) |
| neighbors.py is FROZEN | Core similarity logic cannot be modified; would need new path |
| Cost | Supabase storage for vectors is minimal but query cost scales |
| Testing | Tests currently mock NumPy loads; would need Supabase mocks |
| Rollback risk | If Postgres search gives different results than NumPy |

### Latency Analysis

Current flow (NumPy):
- Load: ~50ms at startup (one-time)
- Search: <1ms per query (in-memory dot product)

pgvector flow:
- No startup load
- Search: ~5-20ms per query (network + HNSW index)
- Acceptable for web UI (users won't notice 20ms difference)
- Problematic for batch operations (clustering 550 faces = 550 queries)

---

## Recommendation

**DEFER migration until one of these triggers is met:**

1. **Embedding count exceeds 5,000** -- At this scale, the .npy file grows to
   ~20 MB and startup load becomes noticeable. HNSW indexing provides real
   value for ANN search at this scale.

2. **ML service extraction** -- When the ML pipeline moves to a separate
   FastAPI service (planned Session 92+), both services need access to
   embeddings. Postgres becomes the natural shared store.

3. **Multi-tenant deployment** -- When serving multiple communities, each
   needs its own embedding space. Postgres row-level security handles this
   naturally; .npy files would require per-tenant file management.

### Why Not Now

At ~550 faces, the current system works well:
- 2.3 MB loads instantly
- In-memory search is sub-millisecond
- No network dependency for core ML operations
- Migration effort (2-3 tracks) is better spent on user-facing features

### Intermediate Step

Before full migration, consider shadow-writing new embeddings to Supabase
(similar to the identity shadow-write pattern from Session 90b). This builds
the table incrementally without requiring a big-bang migration.

---

## Related Decisions

- AD-110: Serving Path Contract (web requests never run heavy ML)
- AD-149/152: Similarity calibration (isotonic regression on distances)
- DATA-006: Shadow writes to Supabase (Session 90b)
- Phase F roadmap: pgvector listed as remaining work

## References

- Supabase pgvector docs: https://supabase.com/docs/guides/ai/vector-columns
- HNSW paper: Malkov & Yashunin, 2018
- `core/neighbors.py` -- FROZEN, current similarity search implementation
- `core/embeddings_io.py` -- Current embedding I/O
