# PRD-035: Upload Pipeline Improvements

**Parent:** [PRD-035](../035_multi_community_platform.md)

## Current Limitations
- `MAX_FILES_PER_UPLOAD = 50` in `app/upload_routes.py:347`
- `MAX_FILE_SIZE = 50 MB` per file
- No batch metadata (source, date hint, location)
- No TIFF support
- Processing is synchronous (server timeout risk for large batches)

## Proposed Changes (Phase 1)

1. **Raise cap:** 50 → 200 files per upload
2. **TIFF auto-conversion:** Pillow converts TIFF→JPG (95% quality) on upload,
   stores original TIFF in R2 archival prefix, serves JPG for display/ML
3. **Batch metadata form:** Source description, date range hint, location hint,
   notes — stored in `upload_batches` table, associated with each photo
4. **Chunked upload:** Client-side chunking (JS) to avoid timeout on large batches.
   Upload in groups of 20, show progress bar per chunk.
5. **Background processing:** Face detection runs in background thread (already
   implemented), extend to handle larger batches with progress tracking

## Future: Google Drive/Photos Import (Phase 4)

- Google Photos API: OAuth → list albums → select → download media items → ingest
- Google Drive API: OAuth → browse folders → select → download → ingest
- Requires Google Cloud project + OAuth consent screen
- Unverified app OK for Nolan's personal use; verified needed for paid users
- Manual download+upload works for MVP

## TIFF Conversion Detail

```python
from PIL import Image

def convert_tiff_to_jpg(tiff_path, quality=95):
    """Convert TIFF to JPG, preserving EXIF where possible."""
    img = Image.open(tiff_path)
    # Preserve EXIF data
    exif = img.info.get('exif', b'')
    jpg_path = tiff_path.rsplit('.', 1)[0] + '.jpg'
    if exif:
        img.save(jpg_path, 'JPEG', quality=quality, exif=exif)
    else:
        img.save(jpg_path, 'JPEG', quality=quality)
    return jpg_path
```

Upload pipeline flow:
1. Client uploads files (any format: JPG, PNG, TIFF, HEIC)
2. Server detects format
3. If TIFF/HEIC: convert to JPG, store original in `r2://{community}/archival/`
4. JPG used for display, face detection, ML pipeline
5. Batch metadata stored in `upload_batches` table
6. Each photo linked to batch via `upload_batch_id`
