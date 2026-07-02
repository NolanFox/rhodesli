# Rhodesli Data Model

**Last updated:** 2026-07-02 (Postgres-canonical correction — Fable eval QW-4)

**Supabase/Postgres is the SOURCE OF TRUTH for ALL structured data** — identities,
photos, faces, `date_labels`, relationships, and GEDCOM current-state. Since
Session 112 the app runs with `DATA_SOURCE=postgres` and **reads from Postgres,
never from JSON** (AD-232 eliminated the JSON read-fallback across all data
loaders; PRD-051 "Single Source of Truth").

The JSON files (`identities.json`, `photo_index.json`, `file_hashes.json`) and
`embeddings.npy` are now a **local cache + deploy/backup mirror only — NOT
canonical.** They preserve the on-disk schema for the local ML pipeline and for
seeding a fresh Railway volume, but the running app does not treat them as
authoritative.

> **Breadcrumbs:** `.claude/rules/data-layer.md` · AD-232 / PRD-051 in
> `docs/ml/ALGORITHMIC_DECISIONS.md` · GEDCOM storage: `GEDCOM_HISTORY.md` ·
> **Never repair data by editing JSON alone** — the Postgres read path
> overwrites it (split-brain; Lessons 144/150/153). Before any data-write or
> repair work, load the `split-brain-data-audit` skill.

---

## Write pattern — shadow-write / write-through

Admin **and** contributor actions write **through to Supabase** (the canonical
store); the JSON files are written afterward only as a backup mirror. There is no
JSON-only write path in normal operation. A write that reaches JSON but not
Supabase is invisible to the app and will be silently reverted on the next
Postgres read — this is the recurring "split-brain" failure class.

---

## identities (Supabase table; mirrored to `identities.json`)

The in-memory registry and the JSON mirror share this record shape:

| Field | Type | Description |
|-------|------|-------------|
| `identity_id` | string (UUID) | Primary key |
| `name` | string | Display name or "Unidentified Person NNN" |
| `state` | string | One of: `CONFIRMED`, `PROPOSED`, `INBOX` |
| `anchor_ids` | list[string] | Face IDs confirmed to belong to this identity |
| `candidate_ids` | list[string] | Face IDs proposed (not yet confirmed) |
| `negative_ids` | list[string] | Face IDs explicitly rejected from this identity |
| `version_id` | integer | Optimistic concurrency version counter |
| `created_at` | string (ISO 8601) | Creation timestamp |
| `updated_at` | string (ISO 8601) | Last modification timestamp |
| `merged_into` | string (UUID) | Present only if this identity was merged into another |

**Identity states:**
- `CONFIRMED` — Admin has verified this identity
- `PROPOSED` — ML pipeline proposed this cluster
- `INBOX` — Newly ingested, awaiting triage

Live counts are ~1,824 identities across all communities — see the ROADMAP header
for the current figure (ROADMAP is the live source of truth for scale).

**Face ID formats:**
- Legacy: `"Image 924_compress:face4"` (filename stem + colon + face index)
- Inbox: `"inbox_739db7ec49ac"` (hex hash, from ingestion pipeline)

**JSONB read/write guard:** Supabase JSONB list columns (`anchor_ids`, etc.) can
silently store string-encoded arrays — reads AND writes are guarded via
`_ensure_list()` (Lesson 142). Top-level identity fields that aren't mapped to an
explicit column (e.g. `notes`) must be round-tripped through the `metadata` JSONB
column or they silently fail to persist (Lesson 179).

---

## photos & faces (Supabase tables; mirrored to `photo_index.json`)

The photo record shape (canonical in the `photos` table, mirrored in JSON):

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Filename relative to `raw_photos/` (e.g., `"Image 001_compress.jpg"`) |
| `face_ids` | list[string] | All face IDs detected in this photo |
| `source` | string | Provenance/origin (e.g., `"Newspapers.com"`, `"Betty's Album"`) |
| `collection` | string | Archive classification (e.g., `"Immigration Records"`) |
| `source_url` | string | Citation URL |
| `width` | integer | Photo width in pixels |
| `height` | integer | Photo height in pixels |

The `photo_faces` table maps every face ID to its parent photo. The READ path
queries it, so the WRITE path MUST populate it alongside photos (Lesson 145).

**Photo ID formats:**
- Standard: `"a3d2695fe0804844"` — SHA256(filename)[:16]
- Inbox: `"inbox_b5e8a89e_0_603575867.895093"` — from ingestion pipeline

Live counts are ~1,127 photos across multiple community collections (Fox Family,
Rhodes, Capeluto, Fader, and others) — see the ROADMAP header for current figures.

---

## embeddings.npy (local ML artifact — read-only for the app)

`embeddings.npy` stays the local face-embedding artifact. It is **read-only for
the web app** and regenerated only by the local ML face-detection pipeline —
never mutated on the server.

NumPy array of dicts, loaded with `np.load(path, allow_pickle=True)`. Each entry:

| Field | Type | Description |
|-------|------|-------------|
| `filename` | string | Photo filename (e.g., `"Image 001_compress.jpg"`) |
| `bbox` | list[4] or string | Bounding box `[x1, y1, x2, y2]` in pixels |
| `face_id` | string (optional) | Explicit face ID (inbox entries only) |
| `embeddings` | array | 512-dim PFE embedding vectors |
| `det_score` | float | Detection confidence score |
| `quality` | float | Face quality score |

When `face_id` is absent, the app generates one from filename + face index via
`generate_face_id()`.

---

## GEDCOM (current-state Postgres + R2 history)

GEDCOM data uses **current-state Postgres tables** — `gedcom_individuals`,
`gedcom_families`, `gedcom_relationships` (one row per entity, composite
community-scoped PKs) — plus a **content-addressed R2 history layer** and an
**atomic single-transaction importer** (a failed import writes ZERO rows). This
replaced the bloat-prone multi-state mirror in Session 164 (PRD-064 Option
B-plus). Full spec: `GEDCOM_HISTORY.md`.

---

## file_hashes.json (dedup mirror)

SHA-256 hashes for photo deduplication, checked on upload to prevent duplicate
ingestion. A local/mirror artifact like the other JSON files.

---

## Photo ID Generation

Photo IDs are deterministic, based on the filename:

```python
def generate_photo_id(filename: str) -> str:
    basename = Path(filename).name
    return hashlib.sha256(basename.encode("utf-8")).hexdigest()[:16]
```

Photos ingested through the inbox pipeline use a different ID format (`inbox_*`);
both formats coexist. Normalize to canonical SHA256 IDs before cross-referencing
(Lesson 25 / 63 — the dual-ID-space split-brain).

---

## Data Integrity Rules

1. **Supabase/Postgres is canonical.** The app reads from Postgres; JSON +
   `embeddings.npy` are cache/backup mirrors, not the source of truth.
2. Admin AND contributor mutations write **through to Supabase** first, then
   mirror to JSON as backup. Never edit JSON alone to "repair" data.
3. Writes surface failures — no fire-and-forget `except: pass` Supabase writes
   (Lessons 123/136/153).
4. `embeddings.npy` is modified only by the local face-detection pipeline
   (local only, never on the server).
5. Batch scripts that produce app-consumed data MUST write to the Supabase table
   the app reads from, not just local JSON (`.claude/rules/batch-data-pipeline.md`).
6. All paths in mirror files are **relative** (e.g., `"raw_photos/photo.jpg"`).
