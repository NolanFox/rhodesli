"""
Photo Registry: Maps photos to faces for co-occurrence validation.

Core invariant: Two faces appearing in the same photo can NEVER belong
to the same identity (they are physically distinct people in that moment).

This registry enables the Safety Foundation by providing:
- photo_id -> set of face_ids mapping
- face_id -> photo_id reverse lookup

Design principles:
- photo_id is a stable, deterministic identifier (not the file path)
- File paths are metadata only, not primary keys
- All data is serializable and reloadable without recomputation
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PhotoRegistry:
    """
    Registry mapping photos to faces and faces to photos.

    Internal structures:
    - _photos: photo_id -> { path: str, face_ids: set[str], source: str }
    - _face_to_photo: face_id -> photo_id
    """

    def __init__(self):
        self._photos: dict[str, dict] = {}
        self._face_to_photo: dict[str, str] = {}

    def register_face(self, photo_id: str, path: str, face_id: str, source: str = "") -> None:
        """
        Register a face as appearing in a photo.

        Args:
            photo_id: Stable identifier for the photo
            path: File path (metadata only, not primary key)
            face_id: Identifier for the detected face
            source: Collection/provenance label (e.g., "Betty Capeluto Miami Collection")
        """
        if photo_id not in self._photos:
            self._photos[photo_id] = {
                "path": path,
                "face_ids": set(),
                "source": source,
            }

        self._photos[photo_id]["face_ids"].add(face_id)
        self._face_to_photo[face_id] = photo_id

    def set_source(self, photo_id: str, source: str) -> None:
        """
        Set or update the source/collection label for a photo.

        Args:
            photo_id: Photo identifier
            source: Collection/provenance label
        """
        if photo_id in self._photos:
            self._photos[photo_id]["source"] = source

    def get_source(self, photo_id: str) -> str:
        """
        Get the source/collection label for a photo.

        Args:
            photo_id: Photo identifier

        Returns:
            Source string, or empty string if photo unknown or no source set
        """
        if photo_id not in self._photos:
            return ""
        return self._photos[photo_id].get("source", "")

    def get_faces_in_photo(self, photo_id: str) -> set[str]:
        """
        Get all face_ids detected in a photo.

        Args:
            photo_id: Photo identifier

        Returns:
            Set of face_ids, or empty set if photo unknown
        """
        if photo_id not in self._photos:
            return set()
        return self._photos[photo_id]["face_ids"].copy()

    def get_photo_for_face(self, face_id: str) -> Optional[str]:
        """
        Get the photo_id containing a face.

        Args:
            face_id: Face identifier

        Returns:
            photo_id, or None if face unknown
        """
        return self._face_to_photo.get(face_id)

    def get_photos_for_faces(self, face_ids: list[str]) -> set[str]:
        """
        Get all photo_ids containing any of the given faces.

        Args:
            face_ids: List of face identifiers

        Returns:
            Set of photo_ids
        """
        photo_ids = set()
        for face_id in face_ids:
            photo_id = self._face_to_photo.get(face_id)
            if photo_id:
                photo_ids.add(photo_id)
        return photo_ids

    def get_photo_path(self, photo_id: str) -> str | None:
        """
        Get the file path for a photo.

        Args:
            photo_id: Photo identifier

        Returns:
            File path string, or None if photo unknown
        """
        if photo_id not in self._photos:
            return None
        return self._photos[photo_id]["path"]

    def save(self, path: Path = None) -> None:
        """
        Save registry to JSON file.

        Args:
            path: Target file path (default: data/photo_index.json)
        """
        if path is None:
            path = Path(__file__).resolve().parent.parent / "data" / "photo_index.json"

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert sets to lists for JSON serialization
        photos_serializable = {}
        for photo_id, photo_data in self._photos.items():
            photos_serializable[photo_id] = {
                "path": photo_data["path"],
                "face_ids": sorted(photo_data["face_ids"]),  # sorted for determinism
                "source": photo_data.get("source", ""),
            }

        data = {
            "schema_version": 1,
            "photos": photos_serializable,
            "face_to_photo": self._face_to_photo,
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"PhotoRegistry saved to {path} ({len(self._photos)} photos, {len(self._face_to_photo)} faces)")

    @classmethod
    def load(cls, path: Path = None) -> "PhotoRegistry":
        """
        Load registry from JSON file.

        Args:
            path: Source file path (default: data/photo_index.json)

        Returns:
            Loaded PhotoRegistry instance
        """
        if path is None:
            path = Path(__file__).resolve().parent.parent / "data" / "photo_index.json"

        path = Path(path)

        with open(path) as f:
            data = json.load(f)

        if data.get("schema_version") != 1:
            raise ValueError(
                f"PhotoRegistry schema version mismatch: expected 1, "
                f"got {data.get('schema_version')}"
            )

        registry = cls()

        # Restore photos with face_ids as sets
        for photo_id, photo_data in data["photos"].items():
            registry._photos[photo_id] = {
                "path": photo_data["path"],
                "face_ids": set(photo_data["face_ids"]),
                "source": photo_data.get("source", ""),  # Backward compatible
            }

        # Restore face_to_photo mapping
        registry._face_to_photo = data["face_to_photo"]

        logger.info(f"PhotoRegistry loaded from {path} ({len(registry._photos)} photos, {len(registry._face_to_photo)} faces)")

        return registry
