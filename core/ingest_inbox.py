"""
Inbox Ingestion Pipeline.

Standalone script for processing uploaded files into INBOX identities.
Designed to be invoked via subprocess from the web server.

Usage:
    python core/ingest_inbox.py --file /path/to/upload.jpg --job-id abc123

Flow:
1. Accept file path and job_id
2. Detect faces with InsightFace
3. Generate PFE embeddings
4. Append to embeddings.npy atomically
5. Register faces in PhotoRegistry
6. Create INBOX identity for each face
7. Write status to data/inbox/{job_id}.status.json
8. Generate face crops to app/static/crops/
"""

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def generate_face_id(filename: str, face_index: int, job_id: str) -> str:
    """
    Generate a deterministic face_id from inputs.

    Args:
        filename: Source image filename
        face_index: Index of this face within the image (0-based)
        job_id: Ingestion job identifier

    Returns:
        Unique, deterministic face_id string
    """
    unique_str = f"{job_id}:{filename}:{face_index}"
    hash_bytes = hashlib.sha256(unique_str.encode()).hexdigest()[:12]
    return f"inbox_{hash_bytes}"


def write_status_file(
    inbox_dir: Path,
    job_id: str,
    status: str,
    faces_extracted: int = 0,
    identities_created: list[str] = None,
    error: str = None,
    total_files: int = None,
    files_succeeded: int = None,
    files_failed: int = None,
    errors: list[dict] = None,
    current_file: str = None,
) -> None:
    """
    Write job status to a JSON file.

    Args:
        inbox_dir: Directory for status files
        job_id: Job identifier
        status: Status string (processing, success, error, partial)
        faces_extracted: Number of faces found
        identities_created: List of identity IDs created
        error: Error message if status is "error"
        total_files: Total files in batch (for ZIP uploads)
        files_succeeded: Number of files processed successfully
        files_failed: Number of files that failed
        errors: List of per-file error dicts [{filename, error}]
        current_file: Name of file currently being processed
    """
    inbox_dir.mkdir(parents=True, exist_ok=True)
    status_path = inbox_dir / f"{job_id}.status.json"

    data = {
        "job_id": job_id,
        "status": status,
        "faces_extracted": faces_extracted,
        "identities_created": identities_created or [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if error:
        data["error"] = error

    # Batch processing metadata
    if total_files is not None:
        data["total_files"] = total_files
    if files_succeeded is not None:
        data["files_succeeded"] = files_succeeded
    if files_failed is not None:
        data["files_failed"] = files_failed
    if errors:
        data["errors"] = errors
    if current_file:
        data["current_file"] = current_file

    with open(status_path, "w") as f:
        json.dump(data, f, indent=2)


def create_inbox_identities(
    registry,
    faces: list[dict],
    job_id: str,
) -> list[str]:
    """
    Create an INBOX identity for each extracted face.

    Args:
        registry: IdentityRegistry instance
        faces: List of face dicts with face_id field
        job_id: Job identifier for provenance

    Returns:
        List of created identity IDs
    """
    from core.registry import IdentityState

    identity_ids = []

    for face in faces:
        face_id = face["face_id"]
        filename = face.get("filename", "unknown")

        provenance = {
            "source": "inbox_ingest",
            "job_id": job_id,
            "filename": filename,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        identity_id = registry.create_identity(
            anchor_ids=[face_id],
            user_source="inbox_ingest",
            state=IdentityState.INBOX,
            provenance=provenance,
        )

        identity_ids.append(identity_id)

    return identity_ids


def extract_faces(filepath: Path) -> list[dict]:
    """
    Extract faces from an image using InsightFace.

    This function contains the heavy ML imports and processing.

    Args:
        filepath: Path to image file

    Returns:
        List of PFE face dicts with mu, sigma_sq, bbox, etc.
    """
    # Defer heavy imports
    import cv2
    import numpy as np
    from insightface.app import FaceAnalysis

    from core.pfe import create_pfe

    if not filepath.exists():
        raise FileNotFoundError(f"Image not found: {filepath}")

    img = cv2.imread(str(filepath))
    if img is None:
        raise ValueError(f"Could not read image: {filepath}")

    image_shape = img.shape[:2]

    # Initialize InsightFace
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))

    faces = app.get(img)
    results = []

    for face in faces:
        embedding = face.normed_embedding
        raw_norm = float(np.linalg.norm(face.embedding))
        det_score = float(face.det_score)
        bbox = face.bbox.tolist()

        face_data = {
            "filename": filepath.name,
            "filepath": str(filepath),
            "embedding": embedding,
            "quality": raw_norm,
            "det_score": det_score,
            "bbox": bbox,
        }

        pfe = create_pfe(face_data, image_shape)
        results.append(pfe)

    return results


def generate_crop(
    face: dict,
    crops_dir: Path,
) -> str:
    """
    Generate a face crop image.

    Args:
        face: Face dict with filepath and bbox
        crops_dir: Output directory for crops

    Returns:
        Filename of the generated crop
    """
    # Defer heavy imports
    import cv2

    from core.crop_faces import add_padding, sanitize_filename

    filepath = Path(face["filepath"])
    bbox = face["bbox"]
    face_id = face["face_id"]

    img = cv2.imread(str(filepath))
    if img is None:
        logger.warning(f"Could not read image for crop: {filepath}")
        return None

    x1, y1, x2, y2 = add_padding(bbox, img.shape)
    crop = img[y1:y2, x1:x2]

    crops_dir.mkdir(parents=True, exist_ok=True)

    crop_filename = f"{face_id}.jpg"
    crop_path = crops_dir / crop_filename

    cv2.imwrite(str(crop_path), crop)
    return crop_filename


def is_image_file(filename: str) -> bool:
    """Check if filename has an image extension."""
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
    return Path(filename).suffix.lower() in image_extensions


def process_single_image(
    filepath: Path,
    job_id: str,
    file_index: int,
    embeddings_path: Path,
    photo_index_path: Path,
    identity_path: Path,
    crops_dir: Path,
) -> dict:
    """
    Process a single image file (internal helper).

    Args:
        filepath: Path to image file
        job_id: Job identifier
        file_index: Index for unique face_id generation in batch
        embeddings_path: Path to embeddings.npy
        photo_index_path: Path to photo_index.json
        identity_path: Path to identities.json
        crops_dir: Path to crops directory

    Returns:
        Result dict with faces_extracted, identity_ids, or error
    """
    from core.embeddings_io import atomic_append_embeddings
    from core.photo_registry import PhotoRegistry
    from core.registry import IdentityRegistry
    from core.ui_safety import has_surrogate_escapes

    # GUARDRAIL: Warn about filenames with surrogate escapes (but don't modify)
    # These will cause issues at the UI layer but we preserve data fidelity here
    filename_str = str(filepath.name)
    if has_surrogate_escapes(filename_str):
        logger.warning(
            f"Filename contains surrogate escapes (invalid UTF-8): {repr(filename_str)}. "
            "This may cause display issues in the web UI."
        )

    # Extract faces
    faces = extract_faces(filepath)

    if not faces:
        return {
            "faces_extracted": 0,
            "identity_ids": [],
        }

    # Generate face_ids (include file_index to ensure uniqueness in batch)
    for i, face in enumerate(faces):
        face["face_id"] = generate_face_id(f"{file_index}_{filepath.name}", i, job_id)

    # Append to embeddings atomically
    atomic_append_embeddings(embeddings_path, faces)

    # Register in photo registry
    photo_id = f"inbox_{job_id}_{file_index}_{filepath.stem}"
    try:
        photo_registry = PhotoRegistry.load(photo_index_path)
    except FileNotFoundError:
        photo_registry = PhotoRegistry()

    for face in faces:
        photo_registry.register_face(photo_id, str(filepath), face["face_id"])

    photo_registry.save(photo_index_path)

    # Create INBOX identities
    try:
        identity_registry = IdentityRegistry.load(identity_path)
    except FileNotFoundError:
        identity_registry = IdentityRegistry()

    identity_ids = create_inbox_identities(
        registry=identity_registry,
        faces=faces,
        job_id=job_id,
    )

    identity_registry.save(identity_path)

    # Generate crops
    for face in faces:
        generate_crop(face, crops_dir)

    return {
        "faces_extracted": len(faces),
        "identity_ids": identity_ids,
    }


def process_uploaded_file(
    filepath: Path,
    job_id: str,
    data_dir: Path = None,
    crops_dir: Path = None,
) -> dict:
    """
    Main entry point for processing an uploaded file.

    Handles both single images and ZIP archives. For ZIP files,
    processes each image independently with error isolation.

    Args:
        filepath: Path to uploaded image or ZIP
        job_id: Unique job identifier
        data_dir: Data directory (default: project/data)
        crops_dir: Crops output directory (default: project/app/static/crops)

    Returns:
        Result dict with status, faces_extracted, identities_created
    """
    import tempfile
    import zipfile

    project_root = Path(__file__).resolve().parent.parent

    if data_dir is None:
        data_dir = project_root / "data"

    if crops_dir is None:
        crops_dir = project_root / "app" / "static" / "crops"

    inbox_dir = data_dir / "inbox"
    embeddings_path = data_dir / "embeddings.npy"
    identity_path = data_dir / "identities.json"
    photo_index_path = data_dir / "photo_index.json"

    # Write initial status
    write_status_file(inbox_dir, job_id, "processing")

    # Check if ZIP file
    if filepath.suffix.lower() == ".zip":
        return _process_zip_file(
            filepath=filepath,
            job_id=job_id,
            inbox_dir=inbox_dir,
            embeddings_path=embeddings_path,
            photo_index_path=photo_index_path,
            identity_path=identity_path,
            crops_dir=crops_dir,
        )

    # Single image processing
    try:
        logger.info(f"Extracting faces from {filepath}")
        result = process_single_image(
            filepath=filepath,
            job_id=job_id,
            file_index=0,
            embeddings_path=embeddings_path,
            photo_index_path=photo_index_path,
            identity_path=identity_path,
            crops_dir=crops_dir,
        )

        logger.info(f"Found {result['faces_extracted']} face(s)")

        write_status_file(
            inbox_dir, job_id, "success",
            faces_extracted=result["faces_extracted"],
            identities_created=result["identity_ids"],
            total_files=1,
            files_succeeded=1,
            files_failed=0,
        )

        return {
            "status": "success",
            "faces_extracted": result["faces_extracted"],
            "identities_created": result["identity_ids"],
        }

    except Exception as e:
        logger.error(f"Error processing {filepath}: {e}")
        write_status_file(
            inbox_dir, job_id, "error",
            error=str(e),
            total_files=1,
            files_succeeded=0,
            files_failed=1,
            errors=[{"filename": filepath.name, "error": str(e)}],
        )
        return {
            "status": "error",
            "error": str(e),
        }


def _process_zip_file(
    filepath: Path,
    job_id: str,
    inbox_dir: Path,
    embeddings_path: Path,
    photo_index_path: Path,
    identity_path: Path,
    crops_dir: Path,
) -> dict:
    """
    Process a ZIP archive containing multiple images.

    Per-file error isolation ensures a single corrupt image
    does not abort the entire batch.

    Args:
        filepath: Path to ZIP file
        job_id: Job identifier
        inbox_dir: Path for status files
        embeddings_path: Path to embeddings.npy
        photo_index_path: Path to photo_index.json
        identity_path: Path to identities.json
        crops_dir: Path to crops directory

    Returns:
        Result dict with aggregated status
    """
    import tempfile
    import zipfile

    logger.info(f"Processing ZIP archive: {filepath}")

    try:
        with zipfile.ZipFile(filepath, "r") as zf:
            # Filter to image files only (skip __MACOSX, .DS_Store, etc.)
            image_files = [
                name for name in zf.namelist()
                if is_image_file(name)
                and not name.startswith("__MACOSX")
                and not name.startswith(".")
                and "/" not in name.split("/")[-1].startswith(".")
            ]

            total_files = len(image_files)
            if total_files == 0:
                write_status_file(
                    inbox_dir, job_id, "success",
                    faces_extracted=0,
                    total_files=0,
                    files_succeeded=0,
                    files_failed=0,
                )
                return {
                    "status": "success",
                    "faces_extracted": 0,
                    "identities_created": [],
                    "total_files": 0,
                }

            logger.info(f"Found {total_files} image(s) in ZIP")

            # Track aggregated results
            total_faces = 0
            all_identity_ids = []
            files_succeeded = 0
            files_failed = 0
            errors = []

            # Process each image with error isolation
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                for file_index, image_name in enumerate(image_files):
                    # Update progress status
                    write_status_file(
                        inbox_dir, job_id, "processing",
                        faces_extracted=total_faces,
                        identities_created=all_identity_ids,
                        total_files=total_files,
                        files_succeeded=files_succeeded,
                        files_failed=files_failed,
                        current_file=image_name,
                    )

                    try:
                        # Extract single file to temp dir
                        extracted_path = tmpdir_path / Path(image_name).name
                        with zf.open(image_name) as src, open(extracted_path, "wb") as dst:
                            dst.write(src.read())

                        logger.info(f"Processing [{file_index + 1}/{total_files}]: {image_name}")

                        result = process_single_image(
                            filepath=extracted_path,
                            job_id=job_id,
                            file_index=file_index,
                            embeddings_path=embeddings_path,
                            photo_index_path=photo_index_path,
                            identity_path=identity_path,
                            crops_dir=crops_dir,
                        )

                        total_faces += result["faces_extracted"]
                        all_identity_ids.extend(result["identity_ids"])
                        files_succeeded += 1

                        logger.info(f"  Found {result['faces_extracted']} face(s)")

                    except Exception as e:
                        # Error isolation: log and continue
                        logger.error(f"  Error processing {image_name}: {e}")
                        files_failed += 1
                        errors.append({
                            "filename": image_name,
                            "error": str(e),
                        })

            # Determine final status
            if files_failed == 0:
                final_status = "success"
            elif files_succeeded == 0:
                final_status = "error"
            else:
                final_status = "partial"  # Some succeeded, some failed

            write_status_file(
                inbox_dir, job_id, final_status,
                faces_extracted=total_faces,
                identities_created=all_identity_ids,
                total_files=total_files,
                files_succeeded=files_succeeded,
                files_failed=files_failed,
                errors=errors if errors else None,
            )

            return {
                "status": final_status,
                "faces_extracted": total_faces,
                "identities_created": all_identity_ids,
                "total_files": total_files,
                "files_succeeded": files_succeeded,
                "files_failed": files_failed,
                "errors": errors,
            }

    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {e}")
        write_status_file(
            inbox_dir, job_id, "error",
            error=f"Invalid ZIP file: {e}",
        )
        return {
            "status": "error",
            "error": f"Invalid ZIP file: {e}",
        }
    except Exception as e:
        logger.error(f"Error processing ZIP: {e}")
        write_status_file(
            inbox_dir, job_id, "error",
            error=str(e),
        )
        return {
            "status": "error",
            "error": str(e),
        }


def process_directory(
    directory: Path,
    job_id: str,
    data_dir: Path = None,
    crops_dir: Path = None,
) -> dict:
    """
    Process a directory of uploaded files (images and/or ZIPs).

    Each file is processed independently with error isolation.
    ZIP files are extracted and their contents processed.

    Args:
        directory: Path to directory containing uploaded files
        job_id: Unique job identifier
        data_dir: Data directory (default: project/data)
        crops_dir: Crops output directory (default: project/app/static/crops)

    Returns:
        Result dict with aggregated status
    """
    project_root = Path(__file__).resolve().parent.parent

    if data_dir is None:
        data_dir = project_root / "data"

    if crops_dir is None:
        crops_dir = project_root / "app" / "static" / "crops"

    inbox_dir = data_dir / "inbox"
    embeddings_path = data_dir / "embeddings.npy"
    identity_path = data_dir / "identities.json"
    photo_index_path = data_dir / "photo_index.json"

    # Collect all files to process (expand ZIPs)
    files_to_process = []
    zip_files = []

    for item in directory.iterdir():
        if item.is_file():
            if item.suffix.lower() == ".zip":
                zip_files.append(item)
            elif is_image_file(item.name):
                files_to_process.append(item)

    # Count total files (images directly + images inside ZIPs)
    total_images = len(files_to_process)
    zip_image_counts = {}

    import tempfile
    import zipfile

    # Pre-scan ZIPs to count images
    for zf_path in zip_files:
        try:
            with zipfile.ZipFile(zf_path, "r") as zf:
                image_names = [
                    name for name in zf.namelist()
                    if is_image_file(name)
                    and not name.startswith("__MACOSX")
                    and not name.startswith(".")
                    and not name.split("/")[-1].startswith(".")
                ]
                zip_image_counts[zf_path] = image_names
                total_images += len(image_names)
        except zipfile.BadZipFile:
            # Will be counted as 1 failed file
            total_images += 1

    # Write initial status
    write_status_file(
        inbox_dir, job_id, "processing",
        total_files=total_images,
        files_succeeded=0,
        files_failed=0,
    )

    # Track aggregated results
    total_faces = 0
    all_identity_ids = []
    files_succeeded = 0
    files_failed = 0
    errors = []
    file_index = 0

    # Process standalone images
    for img_path in files_to_process:
        write_status_file(
            inbox_dir, job_id, "processing",
            faces_extracted=total_faces,
            identities_created=all_identity_ids,
            total_files=total_images,
            files_succeeded=files_succeeded,
            files_failed=files_failed,
            current_file=img_path.name,
        )

        try:
            logger.info(f"Processing [{file_index + 1}/{total_images}]: {img_path.name}")

            result = process_single_image(
                filepath=img_path,
                job_id=job_id,
                file_index=file_index,
                embeddings_path=embeddings_path,
                photo_index_path=photo_index_path,
                identity_path=identity_path,
                crops_dir=crops_dir,
            )

            total_faces += result["faces_extracted"]
            all_identity_ids.extend(result["identity_ids"])
            files_succeeded += 1
            logger.info(f"  Found {result['faces_extracted']} face(s)")

        except Exception as e:
            logger.error(f"  Error processing {img_path.name}: {e}")
            files_failed += 1
            errors.append({
                "filename": img_path.name,
                "error": str(e),
            })

        file_index += 1

    # Process ZIP files
    for zf_path in zip_files:
        try:
            with zipfile.ZipFile(zf_path, "r") as zf:
                image_names = zip_image_counts.get(zf_path, [])

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)

                    for image_name in image_names:
                        write_status_file(
                            inbox_dir, job_id, "processing",
                            faces_extracted=total_faces,
                            identities_created=all_identity_ids,
                            total_files=total_images,
                            files_succeeded=files_succeeded,
                            files_failed=files_failed,
                            current_file=f"{zf_path.name}:{image_name}",
                        )

                        try:
                            # Extract single file to temp dir
                            extracted_path = tmpdir_path / Path(image_name).name
                            with zf.open(image_name) as src, open(extracted_path, "wb") as dst:
                                dst.write(src.read())

                            logger.info(f"Processing [{file_index + 1}/{total_images}]: {zf_path.name}:{image_name}")

                            result = process_single_image(
                                filepath=extracted_path,
                                job_id=job_id,
                                file_index=file_index,
                                embeddings_path=embeddings_path,
                                photo_index_path=photo_index_path,
                                identity_path=identity_path,
                                crops_dir=crops_dir,
                            )

                            total_faces += result["faces_extracted"]
                            all_identity_ids.extend(result["identity_ids"])
                            files_succeeded += 1
                            logger.info(f"  Found {result['faces_extracted']} face(s)")

                        except Exception as e:
                            logger.error(f"  Error processing {image_name}: {e}")
                            files_failed += 1
                            errors.append({
                                "filename": f"{zf_path.name}:{image_name}",
                                "error": str(e),
                            })

                        file_index += 1

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file {zf_path.name}: {e}")
            files_failed += 1
            errors.append({
                "filename": zf_path.name,
                "error": f"Invalid ZIP file: {e}",
            })

    # Determine final status
    if files_failed == 0:
        final_status = "success"
    elif files_succeeded == 0:
        final_status = "error"
    else:
        final_status = "partial"

    write_status_file(
        inbox_dir, job_id, final_status,
        faces_extracted=total_faces,
        identities_created=all_identity_ids,
        total_files=total_images,
        files_succeeded=files_succeeded,
        files_failed=files_failed,
        errors=errors if errors else None,
    )

    return {
        "status": final_status,
        "faces_extracted": total_faces,
        "identities_created": all_identity_ids,
        "total_files": total_images,
        "files_succeeded": files_succeeded,
        "files_failed": files_failed,
        "errors": errors,
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Process uploaded file(s) for inbox ingestion"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file",
        type=Path,
        help="Path to uploaded file (single image or ZIP)",
    )
    group.add_argument(
        "--directory",
        type=Path,
        help="Path to directory containing uploaded files",
    )
    parser.add_argument(
        "--job-id",
        type=str,
        required=True,
        help="Unique job identifier",
    )
    args = parser.parse_args()

    if args.directory:
        result = process_directory(args.directory, args.job_id)
    else:
        result = process_uploaded_file(args.file, args.job_id)

    if result["status"] == "error":
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
