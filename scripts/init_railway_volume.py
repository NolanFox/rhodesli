"""
First-run initialization for Railway persistent volume.

Copies bundled data files into the volume if they don't already exist.
This runs as part of the start command on first deploy.
# Force rebuild: 2026-02-05-v2

Railway supports only ONE persistent volume per service. When STORAGE_DIR
is set, the volume is mounted at that path and we create subdirectories:
  /app/storage/
  ├── data/          ← identities.json, photo_index.json, embeddings, etc.
  ├── raw_photos/    ← source photographs
  └── staging/       ← future upload staging area

The Docker image bundles data in /app/data_bundle/ and /app/photos_bundle/.
On first run, these are copied to the appropriate subdirectories.
On subsequent runs, the volume already has data, so this is a no-op.

CRITICAL: The .initialized marker is ONLY created when data is actually copied.
If bundles are empty (GitHub deploy), no marker is created, allowing future
CLI deploys to seed the volume.
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

# Critical files that MUST exist for valid initialization
REQUIRED_DATA_FILES = ["identities.json", "photo_index.json"]


def volume_is_valid(data_dir: Path) -> bool:
    """Check if volume has the critical data files."""
    for filename in REQUIRED_DATA_FILES:
        if not (data_dir / filename).exists():
            return False
    return True


def init_volume():
    """Copy bundled data to volume if it doesn't exist yet.

    Returns True if volume is ready to use, False if seeding failed.
    """

    # Ensure target directories exist
    data_dir = Path(VOLUME_DATA_DIR)
    photos_dir = Path(VOLUME_PHOTOS_DIR)
    staging_dir = Path(VOLUME_STAGING_DIR)
    marker_dir = Path(MARKER_DIR)

    data_dir.mkdir(parents=True, exist_ok=True)
    photos_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    marker = marker_dir / ".initialized"

    # SANITY CHECK: If marker exists but data is missing, we have a corrupted state
    if marker.exists():
        if volume_is_valid(data_dir):
            print("[init] Volume already initialized and valid, skipping seed.")
            print(f"[init] Data dir: {data_dir}")
            print(f"[init] Photos dir: {photos_dir}")
            print(f"[init] Staging dir: {staging_dir}")
            return True
        else:
            print("[init] WARNING: Volume marked as initialized but data is MISSING.")
            print("[init] Detected corrupted state. Removing marker and attempting re-initialization...")
            marker.unlink()
            # Fall through to initialization logic

    print("[init] First run detected. Initializing volume from bundled data...")
    if STORAGE_DIR:
        print(f"[init] Single-volume mode: STORAGE_DIR={STORAGE_DIR}")
    else:
        print("[init] Legacy mode: using DATA_DIR and PHOTOS_DIR separately")

    # Track what we actually copy
    data_copied = 0
    photos_copied = 0

    # Copy bundled data files
    if BUNDLED_DATA.exists():
        # Check if bundle has actual data (not just .gitkeep)
        bundle_items = [f for f in BUNDLED_DATA.iterdir() if f.name != ".gitkeep"]
        if bundle_items:
            print(f"[init] Copying data from {BUNDLED_DATA} to {data_dir}...")
            for item in bundle_items:
                dest = data_dir / item.name
                if not dest.exists():
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
                    data_copied += 1
                    print(f"[init]   Copied: {item.name}")
            print(f"[init] Copied {data_copied} data items.")
        else:
            print(f"[init] Data bundle is empty (likely GitHub deploy).")
    else:
        print(f"[init] No bundled data found at {BUNDLED_DATA}")

    # Copy bundled photos
    if BUNDLED_PHOTOS.exists():
        # Check if bundle has actual photos (not just .gitkeep)
        photo_items = [f for f in BUNDLED_PHOTOS.iterdir() if f.name != ".gitkeep"]
        if photo_items:
            print(f"[init] Copying photos from {BUNDLED_PHOTOS} to {photos_dir}...")
            for item in photo_items:
                dest = photos_dir / item.name
                if not dest.exists():
                    shutil.copy2(item, dest)
                    photos_copied += 1
            print(f"[init] Copied {photos_copied} photos.")
        else:
            print(f"[init] Photos bundle is empty (likely GitHub deploy).")
    else:
        print(f"[init] No bundled photos found at {BUNDLED_PHOTOS}")

    print(f"[init] Staging directory: {staging_dir}")

    # CRITICAL: Only create marker if we actually have valid data
    if volume_is_valid(data_dir):
        marker.touch()
        print("[init] Volume initialization complete.")
        print(f"[init] Marker created: {marker}")
        print(f"[init] Summary: {data_copied} data items, {photos_copied} photos copied.")
        return True
    elif data_copied == 0 and photos_copied == 0:
        # Nothing was copied - this is a GitHub deploy on an empty volume
        print("")
        print("=" * 60)
        print("[init] ERROR: No data to seed and volume is empty.")
        print("[init] This happens when deploying from GitHub (bundles are empty).")
        print("[init] ")
        print("[init] TO FIX: Deploy using 'railway up' from your local machine.")
        print("[init] This will upload data/ and raw_photos/ from your local copy.")
        print("=" * 60)
        print("")
        # Do NOT create marker - allow future CLI deploy to seed
        return False
    else:
        # Some data copied but critical files missing - something went wrong
        print("")
        print("=" * 60)
        print("[init] ERROR: Initialization incomplete.")
        print(f"[init] Copied {data_copied} data items, {photos_copied} photos.")
        print(f"[init] But required files are missing: {REQUIRED_DATA_FILES}")
        print("[init] Check disk space and permissions.")
        print("=" * 60)
        print("")
        # Do NOT create marker - allow retry
        return False


if __name__ == "__main__":
    success = init_volume()
    # Exit with error code if initialization failed
    # This helps Railway detect failed deploys
    exit(0 if success else 1)
