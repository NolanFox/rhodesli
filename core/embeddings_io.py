"""
Atomic Embeddings I/O plus schema-tolerant face-data loading.

Provides safe, concurrent-safe operations for reading and appending to
the embeddings.npy file used by the recognition system.

Uses portalocker for file locking and atomic rename for crash safety.
See registry.py for the same pattern applied to the identity registry.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_embeddings(embeddings_path: Path) -> list[dict]:
    """
    Load embeddings from .npy file.

    Args:
        embeddings_path: Path to embeddings.npy file

    Returns:
        List of face embedding dicts, or empty list if file doesn't exist
    """
    # Defer numpy import (heavy dependency)
    import numpy as np

    embeddings_path = Path(embeddings_path)

    if not embeddings_path.exists():
        return []

    loaded = np.load(embeddings_path, allow_pickle=True)
    return list(loaded)


def generate_face_id(filename: str, face_index: int) -> str:
    """Generate the stable legacy face ID used across clustering scripts."""
    stem = Path(filename).stem
    return f"{stem}:face{face_index}"


def _extract_face_vectors(entry: dict):
    """Return `(mu, sigma_sq)` for one embedding row or `(None, None)` if invalid."""
    # Defer numpy import (heavy dependency)
    import numpy as np

    if "mu" in entry:
        mu = np.asarray(entry["mu"], dtype=np.float32)
        sigma_sq = entry.get("sigma_sq")
        if sigma_sq is None:
            sigma_sq = np.full(mu.shape[0], 0.55, dtype=np.float32)
        else:
            sigma_sq = np.asarray(sigma_sq, dtype=np.float32)
        return mu, sigma_sq

    embedding_vec = entry.get("embedding")
    if embedding_vec is None:
        embedding_vec = entry.get("embeddings")
    if embedding_vec is None:
        return None, None

    mu = np.asarray(embedding_vec, dtype=np.float32)
    det_score = float(entry.get("det_score", 0.5) or 0.5)
    sigma_sq_val = 1.0 - (det_score * 0.9)
    sigma_sq = np.full(mu.shape[0], sigma_sq_val, dtype=np.float32)
    return mu, sigma_sq


def load_face_data(embeddings_path: Path) -> dict[str, dict]:
    """Load embeddings as `face_id -> metadata` with schema-tolerant vector parsing."""
    embeddings_path = Path(embeddings_path)
    if not embeddings_path.exists():
        raise FileNotFoundError(f"Embeddings not found: {embeddings_path}")

    face_data = {}
    filename_face_counts = {}

    for entry in load_embeddings(embeddings_path):
        filename = entry.get("filename")
        if not filename:
            logger.warning("Skipping embedding row without filename: %s", sorted(entry.keys()))
            continue

        face_index = filename_face_counts.get(filename, 0)
        filename_face_counts[filename] = face_index + 1

        face_id = entry.get("face_id") or generate_face_id(filename, face_index)
        mu, sigma_sq = _extract_face_vectors(entry)
        if mu is None or sigma_sq is None:
            logger.warning(
                "Skipping embedding row for %s with unsupported keys: %s",
                filename,
                sorted(entry.keys()),
            )
            continue

        face_data[face_id] = {
            "mu": mu,
            "sigma_sq": sigma_sq,
            "bbox": entry.get("bbox"),
            "det_score": entry.get("det_score"),
            "quality": entry.get("quality"),
            "filename": filename,
            "filepath": entry.get("filepath"),
        }

    return face_data


def atomic_append_embeddings(embeddings_path: Path, new_faces: list[dict]) -> int:
    """
    Atomically append new face embeddings to the embeddings file.

    Uses the same portalocker pattern as registry.py for crash safety:
    1. Acquire exclusive lock
    2. Load existing data
    3. Append new data
    4. Write to temp file
    5. fsync to disk
    6. Atomic rename to target

    Args:
        embeddings_path: Path to embeddings.npy file
        new_faces: List of face embedding dicts to append

    Returns:
        Number of faces appended
    """
    # Defer heavy imports (testability)
    import numpy as np
    import portalocker

    if not new_faces:
        return 0

    embeddings_path = Path(embeddings_path)

    # Ensure parent directories exist
    embeddings_path.parent.mkdir(parents=True, exist_ok=True)

    lock_path = embeddings_path.with_suffix(".lock")
    temp_path = embeddings_path.with_suffix(".tmp.npy")

    # Ensure lock file exists
    lock_path.touch(exist_ok=True)

    # Acquire exclusive lock
    with open(lock_path, "r+") as lock_file:
        portalocker.lock(lock_file, portalocker.LOCK_EX)

        try:
            # Load existing embeddings
            existing = load_embeddings(embeddings_path)

            # Append new faces
            combined = existing + list(new_faces)

            # Write to temp file
            np.save(temp_path, combined, allow_pickle=True)

            # Sync to disk
            with open(temp_path, "rb") as f:
                os.fsync(f.fileno())

            # Atomic rename
            os.rename(temp_path, embeddings_path)

        finally:
            portalocker.unlock(lock_file)

    return len(new_faces)
