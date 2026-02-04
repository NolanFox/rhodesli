"""
File Hash Registry for idempotent ingestion.

Maps file content SHA256 hashes to their extracted face_ids,
enabling retry-safe ingestion that skips already-processed files.

This prevents duplicate identities when:
- An upload fails partway through and is retried
- The same file is uploaded multiple times
- A batch contains duplicate files
"""

import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = 1


class FileHashRegistry:
    """
    Registry mapping file content hashes to face metadata.

    Internal structure:
    - _hashes: hash -> {face_ids: list, job_id: str, filename: str}
    """

    def __init__(self):
        self._hashes: dict[str, dict] = {}

    @staticmethod
    def compute_hash(filepath: Path) -> str:
        """
        Compute SHA256 hash of file contents.

        Reads file in chunks to handle large files efficiently.

        Args:
            filepath: Path to the file to hash

        Returns:
            64-character hex string (SHA256 digest)
        """
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def register_file(
        self,
        file_hash: str,
        face_ids: list[str],
        job_id: str,
        filename: str,
    ) -> None:
        """
        Register a processed file with its extracted face_ids.

        Args:
            file_hash: SHA256 hash of file content
            face_ids: List of face IDs extracted from this file
            job_id: Ingestion job that processed this file
            filename: Original filename
        """
        self._hashes[file_hash] = {
            "face_ids": face_ids,
            "job_id": job_id,
            "filename": filename,
        }

    def lookup(self, file_hash: str) -> dict | None:
        """
        Look up file by its content hash.

        Args:
            file_hash: SHA256 hash to look up

        Returns:
            Entry dict if found, None otherwise
        """
        return self._hashes.get(file_hash)

    def get_face_ids_for_hash(self, file_hash: str) -> list[str]:
        """
        Get face_ids for a file hash.

        Args:
            file_hash: SHA256 hash to look up

        Returns:
            List of face IDs, or empty list if hash not found
        """
        entry = self._hashes.get(file_hash)
        return entry["face_ids"] if entry else []

    def remove_by_job(self, job_id: str) -> list[str]:
        """
        Remove all entries for a specific job.

        Used during job cleanup to remove hash mappings.

        Args:
            job_id: Job ID to remove

        Returns:
            List of removed hashes
        """
        removed = []
        for hash_val, entry in list(self._hashes.items()):
            if entry.get("job_id") == job_id:
                del self._hashes[hash_val]
                removed.append(hash_val)
        return removed

    def save(self, path: Path) -> None:
        """
        Save registry to JSON file.

        Args:
            path: Path to save to
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(
                {
                    "schema_version": SCHEMA_VERSION,
                    "hashes": self._hashes,
                },
                f,
                indent=2,
            )

    @classmethod
    def load(cls, path: Path) -> "FileHashRegistry":
        """
        Load registry from JSON file.

        Returns empty registry if file doesn't exist.

        Args:
            path: Path to load from

        Returns:
            FileHashRegistry instance
        """
        registry = cls()
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            registry._hashes = data.get("hashes", {})
        return registry
