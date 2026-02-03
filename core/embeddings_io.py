"""
Atomic Embeddings I/O.

Provides safe, concurrent-safe operations for reading and appending to
the embeddings.npy file used by the recognition system.

Uses portalocker for file locking and atomic rename for crash safety.
See registry.py for the same pattern applied to the identity registry.
"""

import os
from pathlib import Path


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
