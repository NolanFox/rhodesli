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
) -> None:
    """
    Write job status to a JSON file.

    Args:
        inbox_dir: Directory for status files
        job_id: Job identifier
        status: Status string (processing, success, error)
        faces_extracted: Number of faces found
        identities_created: List of identity IDs created
        error: Error message if status is "error"
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


def process_uploaded_file(
    filepath: Path,
    job_id: str,
    data_dir: Path = None,
    crops_dir: Path = None,
) -> dict:
    """
    Main entry point for processing an uploaded file.

    Args:
        filepath: Path to uploaded image
        job_id: Unique job identifier
        data_dir: Data directory (default: project/data)
        crops_dir: Crops output directory (default: project/app/static/crops)

    Returns:
        Result dict with status, faces_extracted, identities_created
    """
    from core.embeddings_io import atomic_append_embeddings
    from core.photo_registry import PhotoRegistry
    from core.registry import IdentityRegistry

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

    try:
        # Extract faces
        logger.info(f"Extracting faces from {filepath}")
        faces = extract_faces(filepath)
        logger.info(f"Found {len(faces)} face(s)")

        if not faces:
            write_status_file(
                inbox_dir, job_id, "success",
                faces_extracted=0,
            )
            return {
                "status": "success",
                "faces_extracted": 0,
                "identities_created": [],
            }

        # Generate face_ids
        for i, face in enumerate(faces):
            face["face_id"] = generate_face_id(filepath.name, i, job_id)

        # Append to embeddings atomically
        atomic_append_embeddings(embeddings_path, faces)
        logger.info(f"Appended {len(faces)} embeddings")

        # Register in photo registry
        photo_id = f"inbox_{job_id}_{filepath.stem}"
        try:
            photo_registry = PhotoRegistry.load(photo_index_path)
        except FileNotFoundError:
            photo_registry = PhotoRegistry()

        for face in faces:
            photo_registry.register_face(photo_id, str(filepath), face["face_id"])

        photo_registry.save(photo_index_path)
        logger.info(f"Registered faces in photo registry")

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
        logger.info(f"Created {len(identity_ids)} INBOX identities")

        # Generate crops
        for face in faces:
            generate_crop(face, crops_dir)

        logger.info(f"Generated face crops")

        # Write final status
        write_status_file(
            inbox_dir, job_id, "success",
            faces_extracted=len(faces),
            identities_created=identity_ids,
        )

        return {
            "status": "success",
            "faces_extracted": len(faces),
            "identities_created": identity_ids,
        }

    except Exception as e:
        logger.error(f"Error processing {filepath}: {e}")
        write_status_file(
            inbox_dir, job_id, "error",
            error=str(e),
        )
        return {
            "status": "error",
            "error": str(e),
        }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Process uploaded file for inbox ingestion"
    )
    parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Path to uploaded file",
    )
    parser.add_argument(
        "--job-id",
        type=str,
        required=True,
        help="Unique job identifier",
    )
    args = parser.parse_args()

    result = process_uploaded_file(args.file, args.job_id)

    if result["status"] == "error":
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
