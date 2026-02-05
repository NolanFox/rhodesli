"""
First-run initialization for Railway persistent volume.

Copies bundled data files into the volume if they don't already exist.
This runs as part of the start command on first deploy.

The Docker image bundles data in /app/data_bundle/ and /app/photos_bundle/.
On first run, these are copied to the mounted volume paths.
On subsequent runs, the volume already has data, so this is a no-op.
"""

import os
import shutil
from pathlib import Path

# Volume mount paths (these are where Railway mounts persistent storage)
VOLUME_DATA_DIR = os.getenv("DATA_DIR", "data")
VOLUME_PHOTOS_DIR = os.getenv("PHOTOS_DIR", "raw_photos")

# Bundle paths (where Docker image has the seed data)
BUNDLED_DATA = Path("/app/data_bundle")
BUNDLED_PHOTOS = Path("/app/photos_bundle")


def init_volume():
    """Copy bundled data to volume if it doesn't exist yet."""

    # Ensure target directories exist
    data_dir = Path(VOLUME_DATA_DIR)
    photos_dir = Path(VOLUME_PHOTOS_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    photos_dir.mkdir(parents=True, exist_ok=True)

    # Check if volume has been initialized
    marker = data_dir / ".initialized"
    if marker.exists():
        print("[init] Volume already initialized, skipping seed data copy.")
        return

    print("[init] First run detected. Initializing volume from bundled data...")

    # Copy bundled data files
    if BUNDLED_DATA.exists():
        print(f"[init] Copying data from {BUNDLED_DATA} to {data_dir}...")
        copied_count = 0
        for item in BUNDLED_DATA.iterdir():
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
        print(f"[init] No bundled data found at {BUNDLED_DATA}")

    # Copy bundled photos
    if BUNDLED_PHOTOS.exists():
        print(f"[init] Copying photos from {BUNDLED_PHOTOS} to {photos_dir}...")
        copied_count = 0
        for item in BUNDLED_PHOTOS.iterdir():
            dest = photos_dir / item.name
            if not dest.exists():
                shutil.copy2(item, dest)
                copied_count += 1
        print(f"[init] Copied {copied_count} photos.")
    else:
        print(f"[init] No bundled photos found at {BUNDLED_PHOTOS}")

    # Create staging directory for production uploads
    staging_dir = data_dir / "staging"
    staging_dir.mkdir(exist_ok=True)
    print(f"[init] Created staging directory: {staging_dir}")

    # Create initialization marker
    marker.touch()
    print("[init] Volume initialization complete.")
    print(f"[init] Marker created: {marker}")


if __name__ == "__main__":
    init_volume()
