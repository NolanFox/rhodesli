#!/usr/bin/env python3
"""
Bulk ingestion script for Rhodesli.

Convenience wrapper for core/ingest.py with sensible defaults for bulk processing.
Processes photos from raw_photos/ and outputs to data/embeddings.npy.

Usage:
    python scripts/ingest_bulk.py                    # Process all photos
    python scripts/ingest_bulk.py --limit 100        # Process first 100 photos
    python scripts/ingest_bulk.py --input other_dir  # Custom input directory
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(
        description="Bulk ingest photos for Rhodesli"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=project_root / "raw_photos",
        help="Input directory (default: raw_photos/)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=project_root / "data" / "embeddings.npy",
        help="Output file (default: data/embeddings.npy)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of photos to process (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without executing",
    )
    args = parser.parse_args()

    # Build the core ingest command
    cmd = [
        sys.executable,
        str(project_root / "core" / "ingest.py"),
        "--input", str(args.input),
        "--output", str(args.output),
    ]

    if args.limit is not None:
        cmd.extend(["--limit", str(args.limit)])

    if args.dry_run:
        print("Would run:")
        print("  " + " ".join(cmd))
        print()

        # Count input files
        if args.input.exists():
            extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
            files = [f for f in args.input.rglob("*") if f.suffix.lower() in extensions]
            if args.limit:
                files = files[:args.limit]
            print(f"Input: {args.input}")
            print(f"Files: {len(files)}")
            print(f"Output: {args.output}")
        else:
            print(f"WARNING: Input directory does not exist: {args.input}")
        return 0

    # Execute
    print(f"Processing photos from: {args.input}")
    print(f"Output: {args.output}")
    if args.limit:
        print(f"Limit: {args.limit} photos")
    print()

    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
