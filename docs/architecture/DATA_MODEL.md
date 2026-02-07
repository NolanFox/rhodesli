# Rhodesli Data Model

**Last updated:** 2026-02-06

All canonical data is stored in JSON files and a NumPy array on the Railway persistent volume. There is no relational database for canonical data.

---

## identities.json

Top-level structure:

```json
{
  "schema_version": 1,
  "identities": { "<uuid>": { ... }, ... }
}
```

Each identity record:

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
- `CONFIRMED` -- Admin has verified this identity (23 currently)
- `PROPOSED` -- ML pipeline proposed this cluster (181 currently)
- `INBOX` -- Newly ingested, awaiting triage (88 currently)

**Face ID formats:**
- Legacy: `"Image 924_compress:face4"` (filename stem + colon + face index)
- Inbox: `"inbox_739db7ec49ac"` (hex hash, from ingestion pipeline)

---

## photo_index.json

Top-level structure:

```json
{
  "schema_version": 1,
  "photos": { "<photo_id>": { ... }, ... },
  "face_to_photo": { "<face_id>": "<photo_id>", ... }
}
```

Each photo record:

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Filename relative to `raw_photos/` (e.g., `"Image 001_compress.jpg"`) |
| `face_ids` | list[string] | All face IDs detected in this photo |
| `source` | string | Collection name (e.g., `"Vida Capeluto NYC Collection"`) |
| `width` | integer | Photo width in pixels |
| `height` | integer | Photo height in pixels |

**Photo ID formats:**
- Standard: `"a3d2695fe0804844"` -- SHA256(filename)[:16]
- Inbox: `"inbox_b5e8a89e_0_603575867.895093"` -- from ingestion pipeline

The `face_to_photo` dict maps every face ID to its parent photo ID. Currently 373 entries.

**Collections (4 total):**
- Vida Capeluto NYC Collection
- Betty Capeluto Miami Collection
- Nace Capeluto Tampa Collection
- Newspapers.com

---

## embeddings.npy

NumPy array of dicts, loaded with `np.load(path, allow_pickle=True)`.

Each entry:

| Field | Type | Description |
|-------|------|-------------|
| `filename` | string | Photo filename (e.g., `"Image 001_compress.jpg"`) |
| `bbox` | list[4] or string | Bounding box `[x1, y1, x2, y2]` in pixels |
| `face_id` | string (optional) | Explicit face ID (inbox entries only) |
| `embeddings` | array | 512-dim PFE embedding vectors |
| `det_score` | float | Detection confidence score |
| `quality` | float | Face quality score |

When `face_id` is absent, the app generates one from filename + face index using `generate_face_id()`.

Current size: ~2.3 MB for ~550 faces.

---

## file_hashes.json

SHA-256 hashes for photo deduplication.

```json
{
  "Image 001_compress.jpg": "abc123...",
  ...
}
```

Checked on upload to prevent duplicate photos from being ingested.

---

## Photo ID Generation

The web app generates photo IDs deterministically:

```python
def generate_photo_id(filename: str) -> str:
    basename = Path(filename).name
    hash_bytes = hashlib.sha256(basename.encode("utf-8")).hexdigest()
    return hash_bytes[:16]
```

Photos ingested through the inbox pipeline use a different ID format (`inbox_*`), but both formats coexist in `photo_index.json`.

---

## Data Integrity Rules

1. All canonical data files are **read-only** for the web app during normal operation
2. Admin actions (confirm, reject, merge, rename, detach) write to `identities.json` using atomic writes (temp file + rename with portalocker)
3. `photo_index.json` is only modified during photo ingestion
4. `embeddings.npy` is only modified during face detection pipeline (local only, never on server)
5. All paths in data files are **relative** (e.g., `"raw_photos/photo.jpg"`) -- never absolute
