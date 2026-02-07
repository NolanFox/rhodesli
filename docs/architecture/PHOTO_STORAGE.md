# Rhodesli Photo Storage

**Last updated:** 2026-02-06

Photos and face crops are served differently depending on the environment. Local development reads from the filesystem; production reads from Cloudflare R2.

---

## Storage Modes

Controlled by environment variables:

| Variable | Values | Default |
|----------|--------|---------|
| `STORAGE_MODE` | `"local"` or `"r2"` | `"local"` |
| `R2_PUBLIC_URL` | R2 public bucket URL (e.g., `https://pub-xxx.r2.dev`) | empty |

R2 mode is active when `STORAGE_MODE=r2` AND `R2_PUBLIC_URL` is set.

---

## Local Mode (Development)

- **Full photos:** `raw_photos/<filename>` served via `/photos/<filename>` route
- **Face crops:** `app/static/crops/<identity_id>_<face_index>.jpg` served via `/static/crops/` route
- Photo dimensions read from filesystem when not cached in `photo_index.json`

---

## R2 Mode (Production)

- **Full photos:** `{R2_PUBLIC_URL}/raw_photos/<filename>` (public URL, no auth needed)
- **Face crops:** `{R2_PUBLIC_URL}/crops/<crop_filename>` (public URL)
- Photo dimensions must be cached in `photo_index.json` (`width`/`height` fields) since the filesystem is not available for on-the-fly measurement

### R2 Bucket Structure

```
rhodesli-photos/          (bucket name)
  raw_photos/
    Image 001_compress.jpg
    Image 054_compress.jpg
    603575867.895093.jpg   (inbox-style filenames)
    ...
  crops/
    2cf08b25-...jpg
    inbox_739db7ec49ac.jpg
    ...
```

---

## URL Generation (core/storage.py)

Three functions handle all photo/crop URL generation:

**`get_photo_url(photo_path)`** -- Returns URL for a full photo.
- Extracts basename from any path format (filename, relative, or absolute)
- Local: `/photos/<filename>`
- R2: `{R2_PUBLIC_URL}/raw_photos/<filename>`

**`get_crop_url(identity_id, face_index=0)`** -- Returns URL for a face crop by identity.
- Constructs filename as `{identity_id}_{face_index}.jpg`
- Local: `/static/crops/<filename>`
- R2: `{R2_PUBLIC_URL}/crops/<filename>`

**`get_crop_url_by_filename(crop_filename)`** -- Returns URL for a crop by its filename directly.
- Used when the crop filename is already resolved (e.g., inbox-style crops)
- Local: `/static/crops/<filename>`
- R2: `{R2_PUBLIC_URL}/crops/<filename>`

All functions URL-encode filenames to handle spaces and special characters.

---

## Photo ID Generation

Photo IDs are deterministic, based on the filename:

```python
def generate_photo_id(filename: str) -> str:
    basename = Path(filename).name
    return hashlib.sha256(basename.encode("utf-8")).hexdigest()[:16]
```

This produces 16-character hex strings like `"a3d2695fe0804844"`.

### Inbox-Style IDs

Photos ingested through the upload/inbox pipeline use a different ID format: `inbox_<batch_id>_<index>_<original_filename>`. These coexist with SHA256 IDs in `photo_index.json`. The web app handles both formats transparently.

---

## Photo Dimensions

Photo dimensions (`width`, `height`) are stored in `photo_index.json` for each photo entry. These are critical in R2 mode because:

1. The filesystem is not available on Railway for measuring images
2. Face bounding box overlays require knowing the image dimensions to scale correctly
3. Dimensions are cached during the local ingestion pipeline and persist in the JSON

If dimensions are missing (legacy photos), the app falls back to reading from R2 with a cached response, but this is slower and unreliable.

---

## Uploading to R2

Photos are uploaded to R2 from a local machine using `scripts/upload_to_r2.py`:

```bash
# Preview
python scripts/upload_to_r2.py --dry-run

# Upload
python scripts/upload_to_r2.py --execute
```

Requires `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_BUCKET_NAME` environment variables. These are only needed locally, not on Railway.
