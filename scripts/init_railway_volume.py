"""
First-run initialization for Railway persistent volume.

Copies bundled JSON data files into the volume if they don't already exist.
This runs as part of the start command on first deploy.
# Force rebuild: 2026-02-05-v3

Architecture (AD-135):
  - ML-generated data (photo_index.json, embeddings.npy) → Railway Volume (from bundle)
  - User-entered data (confirmations, annotations, etc.) → Supabase Postgres
  - JSON files on volume are a READ CACHE rebuilt from Supabase on app startup
  - Photos and crops → Cloudflare R2 (NOT bundled in image)

Railway supports only ONE persistent volume per service. When STORAGE_DIR
is set, the volume is mounted at that path and we create subdirectories:
  /app/storage/
  └── data/          ← identities.json, photo_index.json, embeddings, etc.

Startup sequence:
  1. init_railway_volume.py — seeds ML data from Docker bundle
  2. app startup_event() — syncs user data from Supabase → JSON cache

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
REQUIRED_DATA_FILES = ["identities.json", "photo_index.json", "embeddings.npy"]

# Optional files that should be synced from bundle when they differ.
# These are NOT required for the app to start, but enhance functionality.
#
# AD-135: User-entered data is NO LONGER synced from bundle — it lives in
# Supabase and is synced to JSON on app startup. Files excluded:
#   - annotations.json — user submissions via web UI
#   - relationships.json — user-entered and GEDCOM-derived relationships
#   - gedcom_matches.json — user review decisions on GEDCOM matches
#   - ancestry_links.json — derived from user-reviewed GEDCOM matches
# These are rebuilt from Supabase on every app start (see app/supabase_data.py).
OPTIONAL_SYNC_FILES = [
    "proposals.json",
    "surname_variants.json",
    "date_labels.json",
    "photo_search_index.json",
    "rhodes_context_events.json",
    "co_occurrence_graph.json",
    "location_dictionary.json",
    "photo_locations.json",
    "birth_year_estimates.json",
]


def volume_is_valid(data_dir: Path) -> bool:
    """Check if volume has the critical data files."""
    for filename in REQUIRED_DATA_FILES:
        if not (data_dir / filename).exists():
            return False
    return True


def _migrate_photo_dimensions(data_dir: Path) -> None:
    """
    Migrate photo dimensions from bundle to existing photo_index.json.

    If the bundle has photo dimensions but the volume's photo_index.json
    doesn't, merge them in. This is a one-time migration for the R2 mode
    photo dimensions feature.
    """
    import json

    bundle_photo_index = BUNDLED_DATA / "photo_index.json"
    volume_photo_index = data_dir / "photo_index.json"

    if not bundle_photo_index.exists() or not volume_photo_index.exists():
        return

    try:
        with open(bundle_photo_index) as f:
            bundle_data = json.load(f)
        with open(volume_photo_index) as f:
            volume_data = json.load(f)

        # Check if bundle has dimensions that volume doesn't
        bundle_photos = bundle_data.get("photos", {})
        volume_photos = volume_data.get("photos", {})

        # Count photos that need dimensions
        needs_update = 0
        for photo_id, photo_data in bundle_photos.items():
            bundle_width = photo_data.get("width", 0)
            bundle_height = photo_data.get("height", 0)

            if bundle_width > 0 and bundle_height > 0:
                volume_entry = volume_photos.get(photo_id, {})
                volume_width = volume_entry.get("width", 0)
                volume_height = volume_entry.get("height", 0)

                if volume_width == 0 or volume_height == 0:
                    needs_update += 1

        if needs_update == 0:
            return  # No migration needed

        print(f"[init] Migrating photo dimensions for {needs_update} photos...")

        # Merge dimensions from bundle into volume
        for photo_id, photo_data in bundle_photos.items():
            bundle_width = photo_data.get("width", 0)
            bundle_height = photo_data.get("height", 0)

            if bundle_width > 0 and bundle_height > 0:
                if photo_id in volume_photos:
                    volume_entry = volume_photos[photo_id]
                    if volume_entry.get("width", 0) == 0:
                        volume_entry["width"] = bundle_width
                        volume_entry["height"] = bundle_height

        # Write back
        with open(volume_photo_index, "w") as f:
            json.dump(volume_data, f, indent=2)

        print("[init] Photo dimensions migration complete.")

    except Exception as e:
        print(f"[init] WARNING: Photo dimensions migration failed: {e}")
        # Non-fatal - volume still works, just without face overlays


def _auto_backup_volume(data_dir: Path) -> str | None:
    """Create a timestamped backup of all critical volume data files.

    Called before any sync operation to ensure recovery is always possible.
    Keeps last 5 backups to prevent unbounded disk growth.
    Prunes BEFORE creating new backup to avoid ENOSPC failures.

    Returns the backup directory path, or None if nothing to back up.
    """
    import datetime

    backup_root = data_dir / "auto_backups"
    try:
        backup_root.mkdir(exist_ok=True)
    except OSError:
        print("[init] WARNING: Cannot create backup directory, skipping backup")
        return None

    # Prune old backups FIRST — keep last 5 (was 10, reduced to save space)
    try:
        existing = sorted([d for d in backup_root.iterdir() if d.is_dir()])
        while len(existing) > 4:  # Keep 4 so new one makes 5
            old = existing.pop(0)
            shutil.rmtree(old)
            print(f"[init] Pruned old backup: {old.name}")
    except OSError as e:
        print(f"[init] WARNING: Error pruning backups: {e}")

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_root / ts

    files_to_backup = [
        "identities.json",
        "photo_index.json",
        "embeddings.npy",
        "annotations.json",
        "relationships.json",
        "ancestry_links.json",
        "match_decisions.jsonl",
        "identification_responses.json",
    ]

    backed_up = 0
    for filename in files_to_backup:
        src = data_dir / filename
        if src.exists():
            try:
                if not backup_dir.exists():
                    backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, backup_dir / filename)
                backed_up += 1
            except OSError as e:
                print(f"[init] WARNING: Failed to backup {filename}: {e}")
                break

    if backed_up > 0:
        print(f"[init] Auto-backup: {backed_up} files saved to auto_backups/{ts}")
    else:
        return None

    return str(backup_dir)


def _count_confirmed_identities(filepath: Path) -> int:
    """Count CONFIRMED identities in an identities.json file."""
    import json

    try:
        with open(filepath) as f:
            data = json.load(f)
        ids = data.get("identities", data)
        return sum(1 for v in ids.values() if isinstance(v, dict) and v.get("state") == "CONFIRMED")
    except Exception:
        return -1


def _is_volume_user_modified(data_dir: Path, filename: str) -> bool:
    """Check if a volume file has user modifications that must not be overwritten.

    For identities.json: volume has MORE confirmed identities than bundle.
    For photo_index.json: volume has MORE photos than bundle.
    For embeddings.npy: volume has MORE entries than bundle (AD-165).
    For date_labels.json/photo_locations.json: volume has reanalyzed entries.
    For other files: always returns False (safe to overwrite).
    """
    import json

    volume_file = data_dir / filename
    bundle_file = BUNDLED_DATA / filename

    if not volume_file.exists() or not bundle_file.exists():
        return False

    if filename == "identities.json":
        volume_confirmed = _count_confirmed_identities(volume_file)
        bundle_confirmed = _count_confirmed_identities(bundle_file)
        if volume_confirmed > bundle_confirmed:
            print(
                f"[init] SAFETY GATE: Volume {filename} has {volume_confirmed} "
                f"confirmed identities but bundle only has {bundle_confirmed}. "
                f"Refusing to overwrite — volume has user modifications."
            )
            return True

    elif filename == "photo_index.json":
        try:
            with open(volume_file) as f:
                v_data = json.load(f)
            with open(bundle_file) as f:
                b_data = json.load(f)
            v_count = len(v_data.get("photos", {}))
            b_count = len(b_data.get("photos", {}))
            if v_count > b_count:
                print(
                    f"[init] SAFETY GATE: Volume {filename} has {v_count} "
                    f"photos but bundle only has {b_count}. "
                    f"Refusing to overwrite — volume has user modifications."
                )
                return True
        except Exception:
            pass

    elif filename == "embeddings.npy":
        # AD-165: embeddings.npy had NO safety gate — every deploy overwrote it,
        # destroying any embeddings added by the upload pipeline. Compare entry
        # count: if volume has more entries, it has upload data we must preserve.
        try:
            import numpy as np

            v_entries = len(np.load(str(volume_file), allow_pickle=True))
            b_entries = len(np.load(str(bundle_file), allow_pickle=True))
            if v_entries > b_entries:
                print(
                    f"[init] SAFETY GATE: Volume {filename} has {v_entries} "
                    f"embeddings but bundle only has {b_entries}. "
                    f"Refusing to overwrite — volume has upload data."
                )
                return True
        except Exception:
            pass

    elif filename in ("date_labels.json", "photo_locations.json"):
        # Protect re-analyze results: if any entry in the volume file has
        # "reanalyzed_at", the admin ran re-analysis and we must not overwrite.
        try:
            v_text = volume_file.read_text()
            if '"reanalyzed_at"' in v_text:
                print(
                    f"[init] SAFETY GATE: Volume {filename} has reanalyzed entries. "
                    f"Refusing to overwrite — volume has admin re-analysis data."
                )
                return True
        except Exception:
            pass

    return False


def _sync_essential_files(data_dir: Path) -> int:
    """Update essential data files from bundle if they differ.

    Git-tracked data files are the source of truth for pipeline-generated data.
    When the Docker image bundles newer data (from a git push), overwrite the
    volume copy — UNLESS the volume has user modifications (more confirmed
    identities, more photos, etc.).

    Creates a timestamped backup of the volume copy before overwriting.

    Safety gates (AD-134):
    - Auto-backup all volume data before any sync
    - Count-based check: refuse to overwrite if volume has more confirmed/photos
    - Timestamped .bak files for individual file recovery

    Returns the number of files updated.
    """
    import hashlib
    import time

    # Protection B: Auto-backup before any sync
    _auto_backup_volume(data_dir)

    updated = 0
    blocked = 0
    ts = int(time.time())

    all_sync_files = REQUIRED_DATA_FILES + OPTIONAL_SYNC_FILES

    for filename in all_sync_files:
        bundle_file = BUNDLED_DATA / filename
        volume_file = data_dir / filename

        if not bundle_file.exists() or not volume_file.exists():
            continue

        # Compare by content hash — skip if identical
        bundle_hash = hashlib.md5(bundle_file.read_bytes()).hexdigest()
        volume_hash = hashlib.md5(volume_file.read_bytes()).hexdigest()

        if bundle_hash == volume_hash:
            continue

        # Protection A+C: Check if volume has user modifications
        if _is_volume_user_modified(data_dir, filename):
            blocked += 1
            continue

        # Bundle differs from volume and is safe to overwrite
        backup = data_dir / f"{filename}.bak.{ts}"
        shutil.copy2(volume_file, backup)
        shutil.copy2(bundle_file, volume_file)
        updated += 1
        print(f"[init] Updated {filename} from bundle (backup: {backup.name})")

    if blocked > 0:
        print(f"[init] Safety gate blocked {blocked} file(s) from being overwritten.")

    return updated


def init_volume():
    """Copy bundled data to volume if it doesn't exist yet.

    On existing volumes, syncs essential data files from the Docker bundle
    when they differ (i.e., when a git push included updated data).

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
            if BUNDLED_DATA.exists():
                # Sync essential data files from bundle if they differ
                # (this is how git-pushed data reaches the production volume)
                updated = _sync_essential_files(data_dir)
                if updated:
                    print(f"[init] Synced {updated} essential file(s) from bundle.")

                # Add any missing optional files
                for item in BUNDLED_DATA.iterdir():
                    if item.name == ".gitkeep":
                        continue
                    dest = data_dir / item.name
                    if not dest.exists():
                        if item.is_dir():
                            shutil.copytree(item, dest)
                        else:
                            shutil.copy2(item, dest)
                        print(f"[init] Added missing file: {item.name}")

            # MIGRATION: Update photo_index.json with dimensions if bundle has them
            _migrate_photo_dimensions(data_dir)

            print("[init] Volume already initialized and valid.")
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
            print("[init] Data bundle is empty (likely GitHub deploy).")
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


def _run_r2_backup():
    """Run R2 backup of volume data on startup (non-blocking).

    Only runs if R2 write credentials are available.
    Failures are logged but do not prevent app startup.
    """
    try:
        from core.storage import can_write_r2

        if not can_write_r2():
            print("[init] R2 write credentials not available, skipping startup backup")
            return

        from scripts.backup_volume_to_r2 import run_backup

        data_dir = Path(VOLUME_DATA_DIR)
        print("[init] Running startup backup to R2...")
        result = run_backup(dry_run=False, data_dir=data_dir)
        if result["errors"]:
            print(f"[init] Backup completed with errors: {result['errors']}")
        else:
            print(
                f"[init] Backup complete: {result['uploaded']} file(s) uploaded, {result['pruned']} old backup(s) pruned"
            )
    except Exception as e:
        print(f"[init] WARNING: Startup backup failed (non-fatal): {e}")


if __name__ == "__main__":
    success = init_volume()

    # Run R2 backup after successful volume init
    if success:
        _run_r2_backup()

    # Exit with error code if initialization failed
    # This helps Railway detect failed deploys
    exit(0 if success else 1)
