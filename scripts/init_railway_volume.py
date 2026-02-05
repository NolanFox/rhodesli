"""
First-run initialization for Railway persistent volume.

Copies bundled data files into the volume if they don't already exist.
This runs as part of the start command on first deploy.

Railway supports only ONE persistent volume per service. When STORAGE_DIR
is set, the volume is mounted at that path and we create subdirectories:
  /app/storage/
  ├── data/          ← identities.json, photo_index.json, embeddings, etc.
  ├── raw_photos/    ← source photographs
  └── staging/       ← future upload staging area

The Docker image bundles data in /app/data_bundle/ and /app/photos_bundle/.
On first run, these are copied to the appropriate subdirectories.
On subsequent runs, the volume already has data, so this is a no-op.
"""

import os
import shutil
from pathlib import Path

# Storage configuration (mirrors core/config.py logic)
STORAGE_DIR = os.getenv("STORAGE_DIR")  # Only set on Railway

if STORAGE_DIR:
    # Railway single-volume mode
    VOLUME_DATA_DIR = os.path.join(STORAGE_DIR, "data")
    VOLUME_PHOTOS_DIR = os.path.join(STORAGE_DIR, "raw_photos")
    VOLUME_STAGING_DIR = os.path.join(STORAGE_DIR, "staging")
    MARKER_DIR = STORAGE_DIR  # Marker lives in volume root
else:
    # Local/legacy mode (individual paths)
    VOLUME_DATA_DIR = os.getenv("DATA_DIR", "data")
    VOLUME_PHOTOS_DIR = os.getenv("PHOTOS_DIR", "raw_photos")
    VOLUME_STAGING_DIR = os.path.join(VOLUME_DATA_DIR, "staging")
    MARKER_DIR = VOLUME_DATA_DIR

# Bundle paths (where Docker image has the seed data)
BUNDLED_DATA = Path("/app/data_bundle")
BUNDLED_PHOTOS = Path("/app/photos_bundle")


def init_volume():
    """Copy bundled data to volume if it doesn't exist yet."""

    # Ensure target directories exist
    data_dir = Path(VOLUME_DATA_DIR)
    photos_dir = Path(VOLUME_PHOTOS_DIR)
    staging_dir = Path(VOLUME_STAGING_DIR)
    marker_dir = Path(MARKER_DIR)

    data_dir.mkdir(parents=True, exist_ok=True)
    photos_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Check if volume has been initialized
    marker = marker_dir / ".initialized"
    if marker.exists():
        print("[init] Volume already initialized, skipping seed data copy.")
        print(f"[init] Data dir: {data_dir}")
        print(f"[init] Photos dir: {photos_dir}")
        print(f"[init] Staging dir: {staging_dir}")
        return

    print("[init] First run detected. Initializing volume from bundled data...")
    if STORAGE_DIR:
        print(f"[init] Single-volume mode: STORAGE_DIR={STORAGE_DIR}")
    else:
        print("[init] Legacy mode: using DATA_DIR and PHOTOS_DIR separately")

    # Copy bundled data files
    if BUNDLED_DATA.exists():
        # Check if bundle has actual data (not just .gitkeep)
        bundle_items = [f for f in BUNDLED_DATA.iterdir() if f.name != ".gitkeep"]
        if bundle_items:
            print(f"[init] Copying data from {BUNDLED_DATA} to {data_dir}...")
            copied_count = 0
            for item in bundle_items:
                dest = data_dir / item.name
                if not dest.exists():
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                    copied_count += 1
                    print(f"[init]   Copied: {item.name}")
            print(f"[init] Copied {copied_count} data items.")
        else:
            print(f"[init] WARNING: Data bundle is empty (GitHub deploy detected).")
            print(f"[init] Volume must be seeded via 'railway up' or manual upload.")
    else:
        print(f"[init] No bundled data found at {BUNDLED_DATA}")

    # Copy bundled photos
    if BUNDLED_PHOTOS.exists():
        # Check if bundle has actual photos (not just .gitkeep)
        photo_items = [f for f in BUNDLED_PHOTOS.iterdir() if f.name != ".gitkeep"]
        if photo_items:
            print(f"[init] Copying photos from {BUNDLED_PHOTOS} to {photos_dir}...")
            copied_count = 0
            for item in photo_items:
                dest = photos_dir / item.name
                if not dest.exists():
                    shutil.copy2(item, dest)
                    copied_count += 1
            print(f"[init] Copied {copied_count} photos.")
        else:
            print(f"[init] WARNING: Photos bundle is empty (GitHub deploy detected).")
            print(f"[init] Volume already seeded? Or use 'railway up' to seed with local photos.")
    else:
        print(f"[init] No bundled photos found at {BUNDLED_PHOTOS}")

    print(f"[init] Staging directory: {staging_dir}")

    # Create initialization marker
    marker.touch()
    print("[init] Volume initialization complete.")
    print(f"[init] Marker created: {marker}")


if __name__ == "__main__":
    init_volume()
