#!/usr/bin/env python3
"""
Robust Bulk Ingestion Script for Rhodesli.

Safely processes large photo collections with:
- Incremental processing (skips already-processed files)
- Fault tolerance (bad files logged, never crash)
- Full provenance (ingest_manifest.json audit trail)

Usage:
    python scripts/ingest_bulk.py                     # Process all photos
    python scripts/ingest_bulk.py --limit 100         # Process first 100 new photos
    python scripts/ingest_bulk.py --force             # Reprocess all files
    python scripts/ingest_bulk.py --input other_dir   # Custom input directory
"""

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# ============================================================
# CONFIGURATION
# ============================================================

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_INPUT_DIR = project_root / "raw_photos"
DEFAULT_OUTPUT_PATH = project_root / "data" / "embeddings.npy"
DEFAULT_MANIFEST_PATH = project_root / "data" / "ingest_manifest.json"
DEFAULT_ERROR_LOG_PATH = project_root / "logs" / "ingest_errors.log"
DEFAULT_MODEL = "buffalo_l"
DEFAULT_DET_SIZE = 640


# ============================================================
# PROGRESS DISPLAY
# ============================================================

def get_progress_tracker(total: int):
    """
    Return a progress tracker (tqdm if available, fallback otherwise).
    """
    try:
        from tqdm import tqdm
        return tqdm(total=total, desc="Processing", unit="img")
    except ImportError:
        return FallbackProgress(total)


class FallbackProgress:
    """Simple progress tracker when tqdm is not available."""

    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.desc = ""

    def update(self, n: int = 1):
        self.current += n
        print(f"[{self.current}/{self.total}] {self.desc}")

    def set_postfix_str(self, s: str):
        self.desc = s

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ============================================================
# LOADING / SAVING EMBEDDINGS
# ============================================================

def load_existing_embeddings(path: Path) -> tuple[list[dict], set[str]]:
    """
    Load existing embeddings and extract processed filenames.

    Returns:
        (embeddings_list, set_of_processed_filenames)
    """
    if not path.exists():
        return [], set()

    data = np.load(path, allow_pickle=True)
    embeddings = list(data)

    # Extract unique filenames that have been processed
    processed_filenames = set()
    for face in embeddings:
        filename = face.get("filename")
        if filename:
            processed_filenames.add(filename)

    return embeddings, processed_filenames


def save_embeddings(embeddings: list[dict], path: Path):
    """Save embeddings to .npy file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, embeddings, allow_pickle=True)


# ============================================================
# IMAGE DISCOVERY
# ============================================================

def discover_images(input_dir: Path) -> list[Path]:
    """
    Recursively discover all supported image files in input directory.

    Returns sorted list for deterministic processing order.
    """
    if not input_dir.exists():
        return []

    images = [
        f for f in input_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(images)


# ============================================================
# FACE EXTRACTION (single image)
# ============================================================

def process_single_image(app, image_path: Path) -> list[dict]:
    """
    Extract face embeddings from a single image.

    Uses deferred imports for testability.

    Args:
        app: Initialized InsightFace FaceAnalysis instance
        image_path: Path to image file

    Returns:
        List of face dicts with PFE format (mu, sigma_sq, metadata)
    """
    import cv2
    from core.pfe import create_pfe

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")

    image_shape = img.shape[:2]  # (height, width)
    faces = app.get(img)
    results = []

    for face in faces:
        embedding = face.normed_embedding  # 512-D unit vector
        raw_norm = float(np.linalg.norm(face.embedding))
        det_score = float(face.det_score)
        bbox = face.bbox.tolist()

        face_data = {
            "filename": image_path.name,
            "filepath": str(image_path),
            "embedding": embedding,
            "quality": raw_norm,
            "det_score": det_score,
            "bbox": bbox,
        }

        # Convert to PFE format
        pfe = create_pfe(face_data, image_shape)
        results.append(pfe)

    return results


# ============================================================
# MODEL INITIALIZATION
# ============================================================

def initialize_model(model_name: str, det_size: int):
    """
    Initialize InsightFace model.

    Attempts GPU/MPS acceleration, falls back to CPU.
    """
    from insightface.app import FaceAnalysis

    # Try providers in order of preference
    providers_to_try = [
        ["CUDAExecutionProvider"],  # NVIDIA GPU
        ["CoreMLExecutionProvider"],  # Apple Silicon (MPS)
        ["CPUExecutionProvider"],  # Fallback
    ]

    for providers in providers_to_try:
        try:
            app = FaceAnalysis(name=model_name, providers=providers)
            app.prepare(ctx_id=0, det_size=(det_size, det_size))
            print(f"Model initialized with provider: {providers[0]}")
            return app
        except Exception:
            continue

    # Final fallback - let it auto-select
    print("Falling back to auto-selected provider...")
    app = FaceAnalysis(name=model_name)
    app.prepare(ctx_id=-1, det_size=(det_size, det_size))
    return app


# ============================================================
# ERROR LOGGING
# ============================================================

def log_error(error_log_path: Path, filename: str, error: Exception):
    """Append error to the error log file."""
    error_log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    error_type = type(error).__name__
    error_msg = str(error)

    with open(error_log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {filename}: {error_type}: {error_msg}\n")


# ============================================================
# MANIFEST (Provenance)
# ============================================================

def load_manifest(path: Path) -> dict:
    """Load existing manifest or return empty dict."""
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(path: Path, manifest: dict):
    """Save manifest to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def update_manifest(
    manifest_path: Path,
    input_directory: str,
    total_scanned: int,
    new_processed: int,
    skipped: int,
    errors: int,
    model_version: str,
):
    """Update manifest with run statistics."""
    manifest = load_manifest(manifest_path)

    # Update with this run's data
    manifest["last_run"] = datetime.now(timezone.utc).isoformat()
    manifest["input_directory"] = input_directory
    manifest["total_files_scanned"] = total_scanned
    manifest["new_files_processed"] = new_processed
    manifest["skipped_files"] = skipped
    manifest["errors"] = errors
    manifest["model_version"] = model_version

    save_manifest(manifest_path, manifest)


# ============================================================
# MAIN INGEST FUNCTION
# ============================================================

def ingest_bulk(
    input_dir: Path,
    output_path: Path,
    manifest_path: Path,
    error_log_path: Path,
    model_name: str = DEFAULT_MODEL,
    det_size: int = DEFAULT_DET_SIZE,
    limit: int | None = None,
    force: bool = False,
) -> dict:
    """
    Run bulk ingestion with fault tolerance and incremental processing.

    Args:
        input_dir: Directory to scan for images
        output_path: Path to embeddings.npy
        manifest_path: Path to ingest_manifest.json
        error_log_path: Path to error log
        model_name: InsightFace model name
        det_size: Detection size
        limit: Max files to process (None = no limit)
        force: If True, reprocess all files

    Returns:
        Summary dict with statistics
    """
    # Discover images
    print(f"Scanning: {input_dir}")
    all_images = discover_images(input_dir)
    total_scanned = len(all_images)
    print(f"Found {total_scanned} image file(s)")

    if total_scanned == 0:
        print("No images found. Exiting.")
        return {
            "total_scanned": 0,
            "new_processed": 0,
            "skipped": 0,
            "errors": 0,
            "faces_extracted": 0,
        }

    # Load existing embeddings
    existing_embeddings, processed_filenames = load_existing_embeddings(output_path)
    print(f"Existing embeddings: {len(existing_embeddings)} faces from {len(processed_filenames)} files")

    # Determine which images to process
    if force:
        print("--force specified: reprocessing all files")
        images_to_process = all_images
        # Clear existing embeddings when forcing full reprocess
        existing_embeddings = []
    else:
        images_to_process = [
            img for img in all_images
            if img.name not in processed_filenames
        ]
        print(f"New images to process: {len(images_to_process)}")

    skipped = total_scanned - len(images_to_process)

    # Apply limit
    if limit is not None and limit > 0:
        images_to_process = images_to_process[:limit]
        print(f"Limited to {len(images_to_process)} image(s)")

    if not images_to_process:
        print("No new images to process. All files already ingested.")
        update_manifest(
            manifest_path,
            str(input_dir),
            total_scanned,
            0,
            skipped,
            0,
            model_name,
        )
        return {
            "total_scanned": total_scanned,
            "new_processed": 0,
            "skipped": skipped,
            "errors": 0,
            "faces_extracted": len(existing_embeddings),
        }

    # Initialize model
    print(f"\nLoading InsightFace model: {model_name}")
    app = initialize_model(model_name, det_size)

    # Process images with fault tolerance
    new_faces = []
    new_processed = 0
    errors = 0

    progress = get_progress_tracker(len(images_to_process))

    for image_path in images_to_process:
        progress.set_postfix_str(image_path.name)

        try:
            faces = process_single_image(app, image_path)
            new_faces.extend(faces)
            new_processed += 1

        except Exception as e:
            errors += 1
            print(f"\nWARNING: Failed to process {image_path.name}: {e}")
            log_error(error_log_path, image_path.name, e)
            # Continue processing remaining files - NEVER crash

        progress.update(1)

    progress.close()

    # Combine and save embeddings
    all_embeddings = existing_embeddings + new_faces
    save_embeddings(all_embeddings, output_path)
    print(f"\nSaved {len(all_embeddings)} total faces to: {output_path}")

    # Update manifest
    update_manifest(
        manifest_path,
        str(input_dir),
        total_scanned,
        new_processed,
        skipped,
        errors,
        model_name,
    )
    print(f"Manifest updated: {manifest_path}")

    if errors > 0:
        print(f"Error log: {error_log_path}")

    return {
        "total_scanned": total_scanned,
        "new_processed": new_processed,
        "skipped": skipped,
        "errors": errors,
        "faces_extracted": len(all_embeddings),
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Robust bulk ingestion for Rhodesli",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Input directory (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output embeddings file (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of NEW files to process (default: no limit)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all files, ignoring existing embeddings",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"InsightFace model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--det-size",
        type=int,
        default=DEFAULT_DET_SIZE,
        help=f"Detection size (default: {DEFAULT_DET_SIZE})",
    )
    args = parser.parse_args()

    # Validate input directory
    if not args.input.exists():
        print(f"ERROR: Input directory does not exist: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Derive paths
    manifest_path = args.output.parent / "ingest_manifest.json"
    error_log_path = project_root / "logs" / "ingest_errors.log"

    # Run ingest
    print("=" * 60)
    print("RHODESLI BULK INGESTION")
    print("=" * 60)
    print(f"Input:    {args.input}")
    print(f"Output:   {args.output}")
    print(f"Model:    {args.model}")
    print(f"Force:    {args.force}")
    print(f"Limit:    {args.limit or 'None'}")
    print("=" * 60)
    print()

    try:
        summary = ingest_bulk(
            input_dir=args.input,
            output_path=args.output,
            manifest_path=manifest_path,
            error_log_path=error_log_path,
            model_name=args.model,
            det_size=args.det_size,
            limit=args.limit,
            force=args.force,
        )

        # Print summary
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total files scanned:   {summary['total_scanned']}")
        print(f"New files processed:   {summary['new_processed']}")
        print(f"Files skipped:         {summary['skipped']}")
        print(f"Errors:                {summary['errors']}")
        print(f"Total faces extracted: {summary['faces_extracted']}")
        print("=" * 60)

        if summary["errors"] > 0:
            print(f"\nSome files failed. Check: {error_log_path}")
            sys.exit(0)  # Still exit 0 - errors are logged, not fatal

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Partial progress may be lost.")
        sys.exit(130)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
