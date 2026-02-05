"""
First-run initialization for Railway persistent volume.

Copies bundled JSON data files into the volume if they don't already exist.
This runs as part of the start command on first deploy.
# Force rebuild: 2026-02-05-v3

Architecture:
  - JSON data (identities.json, photo_index.json) → Railway Volume
  - Photos and crops → Cloudflare R2 (NOT bundled in image)

Railway supports only ONE persistent volume per service. When STORAGE_DIR
is set, the volume is mounted at that path and we create subdirectories:
  /app/storage/
  └── data/          ← identities.json, photo_index.json, embeddings, etc.

Photos are served from Cloudflare R2 via public URLs. They are NOT seeded
from Docker image bundles. See scripts/upload_to_r2.py to upload photos.

The Docker image bundles JSON data in /app/data_bundle/.
On first run, this is copied to the volume.
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
    MARKER_DIR = STORAGE_DIR  # Marker lives in volume root
else:
    # Local/legacy mode (individual paths)
    VOLUME_DATA_DIR = os.getenv("DATA_DIR", "data")
    MARKER_DIR = VOLUME_DATA_DIR

# Bundle paths (where Docker image has the seed data)
BUNDLED_DATA = Path("/app/data_bundle")

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
    marker_dir = Path(MARKER_DIR)

    data_dir.mkdir(parents=True, exist_ok=True)

    marker = marker_dir / ".initialized"

    # SANITY CHECK: If marker exists but data is missing, we have a corrupted state
    if marker.exists():
        if volume_is_valid(data_dir):
            print("[init] Volume already initialized and valid, skipping seed.")
            print(f"[init] Data dir: {data_dir}")
            print("[init] Photos served from R2 (STORAGE_MODE=r2, R2_PUBLIC_URL)")
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
        print("[init] Legacy mode: using DATA_DIR")

    # Track what we actually copy
    data_copied = 0

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

    # CRITICAL: Only create marker if we actually have valid data
    if volume_is_valid(data_dir):
        marker.touch()
        print("[init] Volume initialization complete.")
        print(f"[init] Marker created: {marker}")
        print(f"[init] Summary: {data_copied} data items copied.")
        print("[init] Photos are served from Cloudflare R2 (not from volume).")
        return True
    elif data_copied == 0:
        # Nothing was copied - this is a GitHub deploy on an empty volume
        print("")
        print("=" * 60)
        print("[init] ERROR: No data to seed and volume is empty.")
        print("[init] This happens when deploying from GitHub (bundles are empty).")
        print("[init] ")
        print("[init] TO FIX: Deploy using 'railway up --no-gitignore' from your local machine.")
        print("[init] This will upload data/ from your local copy.")
        print("[init] ")
        print("[init] NOTE: Photos come from R2, not from the image.")
        print("[init] Run 'python scripts/upload_to_r2.py --execute' locally to upload photos.")
        print("=" * 60)
        print("")
        # Do NOT create marker - allow future CLI deploy to seed
        return False
    else:
        # Some data copied but critical files missing - something went wrong
        print("")
        print("=" * 60)
        print("[init] ERROR: Initialization incomplete.")
        print(f"[init] Copied {data_copied} data items.")
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
