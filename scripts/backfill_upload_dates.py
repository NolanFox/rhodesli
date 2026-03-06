#!/usr/bin/env python3
"""Backfill upload dates for all photos in photo_index.json.

Defaults to dry-run and only writes when `--execute` is passed.

Strategy:
- Legacy SHA-based photos: mark as added in the initial tracked archive batch
  on 2026-02-10.
- Inbox/community photos: extract the upload job ID from the photo ID and use
  the first git commit where that job ID appeared in `data/photo_index.json`.
  If git history is unavailable, fall back to the legacy batch date.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PHOTO_INDEX_PATH = DATA_DIR / "photo_index.json"
LEGACY_BATCH_DATE = "2026-02-10"

sys.path.insert(0, str(PROJECT_ROOT))

from core.photo_registry import PhotoRegistry


def extract_job_id(photo_id: str) -> str | None:
    """Extract the upload job ID from an inbox photo ID."""
    if not photo_id.startswith("inbox_"):
        return None
    remainder = photo_id[len("inbox_"):]
    if "_" not in remainder:
        return None
    job_id, _ = remainder.split("_", 1)
    return job_id or None


def format_iso_day(day_str: str) -> str:
    """Convert YYYY-MM-DD into a UTC ISO timestamp at midnight."""
    dt = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return dt.isoformat()


def git_first_seen_date(search_token: str, repo_root: Path = PROJECT_ROOT) -> str | None:
    """Return the first git commit date where the token appears in photo_index.json."""
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--follow",
                "--reverse",
                "--format=%ad",
                "--date=short",
                "-S",
                search_token,
                "--",
                "data/photo_index.json",
            ],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def infer_upload_metadata(
    photo_id: str,
    git_date_lookup=git_first_seen_date,
    legacy_batch_date: str = LEGACY_BATCH_DATE,
) -> dict:
    """Infer upload_date/job_id for a photo without mutating the registry."""
    if not photo_id.startswith("inbox_"):
        return {"upload_date": format_iso_day(legacy_batch_date)}

    job_id = extract_job_id(photo_id)
    if not job_id:
        return {"upload_date": format_iso_day(legacy_batch_date)}

    first_seen = git_date_lookup(job_id) or git_date_lookup(photo_id) or legacy_batch_date
    return {
        "upload_date": format_iso_day(first_seen),
        "job_id": job_id,
    }


def plan_backfill(
    registry: PhotoRegistry,
    git_date_lookup=git_first_seen_date,
    legacy_batch_date: str = LEGACY_BATCH_DATE,
) -> list[dict]:
    """Return planned metadata updates for photos missing archive-entry fields."""
    lookup_cache: dict[str, str | None] = {}

    def cached_git_date_lookup(token: str) -> str | None:
        if token not in lookup_cache:
            lookup_cache[token] = git_date_lookup(token)
        return lookup_cache[token]

    changes = []
    for photo_id, photo in sorted(registry._photos.items()):
        inferred = infer_upload_metadata(
            photo_id,
            git_date_lookup=cached_git_date_lookup,
            legacy_batch_date=legacy_batch_date,
        )
        update = {}

        if not photo.get("upload_date") and inferred.get("upload_date"):
            update["upload_date"] = inferred["upload_date"]
        if photo_id.startswith("inbox_") and not photo.get("job_id") and inferred.get("job_id"):
            update["job_id"] = inferred["job_id"]

        if update:
            changes.append(
                {
                    "photo_id": photo_id,
                    "path": photo.get("path", ""),
                    "update": update,
                }
            )
    return changes


def apply_backfill(registry: PhotoRegistry, changes: list[dict]) -> int:
    """Apply planned changes through PhotoRegistry metadata updates."""
    applied = 0
    for change in changes:
        if registry.set_metadata(change["photo_id"], change["update"]):
            applied += 1
    return applied


def backfill_upload_dates(
    photo_index_path: Path = PHOTO_INDEX_PATH,
    dry_run: bool = True,
    git_date_lookup=git_first_seen_date,
    legacy_batch_date: str = LEGACY_BATCH_DATE,
) -> tuple[int, list[dict]]:
    """Backfill upload dates in photo_index.json via PhotoRegistry."""
    registry = PhotoRegistry.load(photo_index_path)
    changes = plan_backfill(registry, git_date_lookup=git_date_lookup, legacy_batch_date=legacy_batch_date)

    if dry_run or not changes:
        return len(changes), changes

    backup_path = photo_index_path.with_suffix(
        f".backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy2(photo_index_path, backup_path)

    applied = apply_backfill(registry, changes)
    registry.save(photo_index_path)
    return applied, changes


def print_plan(changes: list[dict]) -> None:
    """Print a concise preview of the planned changes."""
    if not changes:
        print("No photos need backfill.")
        return

    counters = Counter("inbox" if c["photo_id"].startswith("inbox_") else "legacy" for c in changes)
    print(f"Photos needing backfill: {len(changes)}")
    print(f"  Legacy batch photos: {counters.get('legacy', 0)}")
    print(f"  Inbox/community photos: {counters.get('inbox', 0)}")
    print()

    for change in changes[:10]:
        print(f"  {change['photo_id']}: {change['update']}")
    if len(changes) > 10:
        print(f"  ... and {len(changes) - 10} more")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill upload dates for all photos")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes to data/photo_index.json (default: dry-run)",
    )
    parser.add_argument(
        "--photo-index",
        type=Path,
        default=PHOTO_INDEX_PATH,
        help=f"Path to photo_index.json (default: {PHOTO_INDEX_PATH.relative_to(PROJECT_ROOT)})",
    )
    args = parser.parse_args()

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTE"
    print(f"Backfill upload dates ({mode})")
    print(f"  Photo index: {args.photo_index}")
    print(f"  Legacy batch date: {LEGACY_BATCH_DATE}")
    print()

    updated_count, changes = backfill_upload_dates(args.photo_index, dry_run=dry_run)
    print_plan(changes)

    if dry_run:
        print(f"\nDRY RUN — would update {updated_count} photo(s).")
    else:
        print(f"\nUpdated {updated_count} photo(s).")


if __name__ == "__main__":
    main()
