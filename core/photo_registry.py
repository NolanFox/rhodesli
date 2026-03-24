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

# Fields every photo entry must have with a truthy value before persistence.
# "path" = relative filename, "collection" = archive grouping.
# width/height are strongly recommended but not required (set during face detection).
REQUIRED_PHOTO_FIELDS = ["path", "collection"]


def validate_photo_entry(photo_id: str, entry: dict) -> None:
    """Raise ValueError if a photo entry is missing required fields.

    Called automatically by PhotoRegistry.save() to prevent incomplete
    entries from reaching disk.
    """
    missing = [f for f in REQUIRED_PHOTO_FIELDS if not entry.get(f)]
    if missing:
        raise ValueError(f"Photo {photo_id} missing required fields: {missing}")


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
        self._filename_to_photo_id: dict[str, str] = {}  # basename -> photo_id
        self._sha256_to_photo_id: dict[str, str] = {}  # SHA256(basename)[:16] -> photo_id

    def register_photo(self, photo_id: str, path: str, source: str = "", collection: str = "") -> None:
        """Register a photo without any faces (e.g., documents, buildings, far-away groups)."""
        if photo_id not in self._photos:
            self._photos[photo_id] = {
                "path": path,
                "face_ids": set(),
                "source": source,
                "collection": collection or source or "Uncategorized",
            }

    def register_face(self, photo_id: str, path: str, face_id: str, source: str = "", collection: str = "") -> None:
        """
        Register a face as appearing in a photo.

        Args:
            photo_id: Stable identifier for the photo
            path: File path (metadata only, not primary key)
            face_id: Identifier for the detected face
            source: Provenance/origin label (e.g., "Betty Capeluto's Album")
            collection: Archive classification (e.g., "Betty Capeluto Miami Collection")
        """
        if photo_id not in self._photos:
            self._photos[photo_id] = {
                "path": path,
                "face_ids": set(),
                "source": source,
                "collection": collection or source or "Uncategorized",
            }

        self._photos[photo_id]["face_ids"].add(face_id)
        self._face_to_photo[face_id] = photo_id

    def set_source(self, photo_id: str, source: str) -> None:
        """
        Set or update the source/provenance label for a photo.

        Source = where the photo came from (e.g., "Newspapers.com", "Betty Capeluto's Album").

        Args:
            photo_id: Photo identifier
            source: Provenance/origin label
        """
        if photo_id in self._photos:
            self._photos[photo_id]["source"] = source

    def get_source(self, photo_id: str) -> str:
        """
        Get the source/provenance label for a photo.

        Args:
            photo_id: Photo identifier

        Returns:
            Source string, or empty string if photo unknown or no source set
        """
        if photo_id not in self._photos:
            return ""
        return self._photos[photo_id].get("source", "")

    def set_collection(self, photo_id: str, collection: str) -> None:
        """
        Set or update the collection/classification label for a photo.

        Collection = how the archive organizes it (e.g., "Immigration Records", "Wedding Photos").
        Separate from source (provenance/origin).

        Args:
            photo_id: Photo identifier
            collection: Classification label
        """
        if photo_id in self._photos:
            self._photos[photo_id]["collection"] = collection

    def get_collection(self, photo_id: str) -> str:
        """
        Get the collection/classification label for a photo.

        Args:
            photo_id: Photo identifier

        Returns:
            Collection string, or empty string if photo unknown or no collection set
        """
        if photo_id not in self._photos:
            return ""
        return self._photos[photo_id].get("collection", "")

    def set_source_url(self, photo_id: str, source_url: str) -> None:
        """
        Set or update the source URL (citation link) for a photo.

        Args:
            photo_id: Photo identifier
            source_url: URL where the photo was found
        """
        if photo_id in self._photos:
            self._photos[photo_id]["source_url"] = source_url

    def get_source_url(self, photo_id: str) -> str:
        """
        Get the source URL for a photo.

        Args:
            photo_id: Photo identifier

        Returns:
            Source URL string, or empty string if not set
        """
        if photo_id not in self._photos:
            return ""
        return self._photos[photo_id].get("source_url", "")

    def resolve_photo_id(self, photo_id: str) -> str | None:
        """Resolve a photo_id to the canonical registry ID.

        Handles the inbox vs SHA256 ID mismatch: if ``photo_id`` is not a
        direct key in ``_photos``, tries to resolve via the filename→photo_id
        index (which bridges SHA256 URL IDs to inbox registry IDs).

        Returns the canonical photo_id, or None if unresolvable.
        """
        if photo_id in self._photos:
            return photo_id
        # Try resolving via pre-built SHA256 reverse index
        if not self._filename_to_photo_id:
            self._build_filename_index()
        return self._sha256_to_photo_id.get(photo_id)

    def _build_filename_index(self) -> None:
        """Build filename and SHA256 indexes for cross-ID resolution."""
        import hashlib

        self._filename_to_photo_id = {}
        self._sha256_to_photo_id = {}
        for pid, entry in self._photos.items():
            path = entry.get("path", "")
            if path:
                fname = Path(path).name
                self._filename_to_photo_id[fname] = pid
                # Pre-compute SHA256 ID for O(1) reverse lookup
                sha_id = hashlib.sha256(fname.encode("utf-8")).hexdigest()[:16]
                self._sha256_to_photo_id[sha_id] = pid

    def get_faces_in_photo(self, photo_id: str) -> set[str]:
        """
        Get all face_ids detected in a photo.

        Args:
            photo_id: Photo identifier (accepts both inbox and SHA256 formats)

        Returns:
            Set of face_ids, or empty set if photo unknown
        """
        if photo_id not in self._photos:
            # Try resolving cross-ID format
            resolved = self.resolve_photo_id(photo_id)
            if resolved:
                return self._photos[resolved]["face_ids"].copy()
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

    def set_dimensions(self, photo_id: str, width: int, height: int) -> bool:
        """
        Set image dimensions for a photo.

        Args:
            photo_id: Photo identifier
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            True if photo exists and dimensions were set, False otherwise
        """
        if photo_id not in self._photos:
            return False
        self._photos[photo_id]["width"] = width
        self._photos[photo_id]["height"] = height
        return True

    def set_metadata(self, photo_id: str, metadata: dict) -> bool:
        """
        Set metadata fields on a photo (BE-012).

        Only allowlisted keys are accepted; others are silently ignored.

        Args:
            photo_id: Photo identifier
            metadata: Dict of key-value pairs to set

        Returns:
            True if photo exists and metadata was set, False otherwise
        """
        if photo_id not in self._photos:
            return False

        valid_keys = {
            "date_taken",
            "date_estimate",
            "location",
            "caption",
            "occasion",
            "photographer",
            "donor",
            "notes",
            "camera",
            "back_image",
            "back_transcription",
            "transform",
            "back_transform",
            "uploaded_by",
            "upload_date",
            "job_id",
            "created_at",
            "updated_at",
            "media_group_id",
            "media_role",
            "parent_photo_id",
            "related_media",
        }
        for key, value in metadata.items():
            if key in valid_keys:
                self._photos[photo_id][key] = value
        return True

    def get_metadata(self, photo_id: str) -> dict:
        """
        Get metadata fields for a photo.

        Returns:
            Dict of metadata fields (excluding path, face_ids, source, width, height)
        """
        if photo_id not in self._photos:
            return {}

        skip_keys = {"path", "face_ids", "source", "collection", "source_url", "width", "height"}
        return {k: v for k, v in self._photos[photo_id].items() if k not in skip_keys and v}

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

        # Validate all entries before writing
        for photo_id, photo_data in self._photos.items():
            validate_photo_entry(photo_id, photo_data)

        # Convert sets to lists for JSON serialization, preserve metadata
        photos_serializable = {}
        for photo_id, photo_data in self._photos.items():
            entry = {
                "path": photo_data["path"],
                "face_ids": sorted(photo_data["face_ids"]),  # sorted for determinism
                "source": photo_data.get("source", ""),
                "collection": photo_data.get("collection", ""),
                "source_url": photo_data.get("source_url", ""),
            }
            # Preserve all extra metadata fields (BE-012)
            for key, value in photo_data.items():
                if key not in ("path", "face_ids", "source", "collection", "source_url") and value is not None:
                    entry[key] = value
            photos_serializable[photo_id] = entry

        data = {
            "schema_version": 1,
            "photos": photos_serializable,
            "face_to_photo": self._face_to_photo,
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"PhotoRegistry saved to {path} ({len(self._photos)} photos, {len(self._face_to_photo)} faces)")

    @classmethod
    def load_from_postgres(cls) -> "PhotoRegistry | None":
        """Load registry from Supabase Postgres.

        Queries photos + photo_faces tables and reconstructs the same
        in-memory structure as the JSON load() method.

        Returns:
            PhotoRegistry instance, or None if Supabase is unavailable.
        """
        try:
            from app.supabase_data import get_supabase_client
        except ImportError:
            logger.warning("supabase_data not available for Postgres photo load")
            return None

        client = get_supabase_client()
        if not client:
            return None

        try:
            # Load photos (paginated)
            all_photos = []
            page_size = 1000
            offset = 0
            while True:
                result = (
                    client.table("photos")
                    .select(
                        "photo_id, path, source, collection, source_url, "
                        "width, height, upload_date, uploaded_by, job_id, created_at, updated_at"
                    )
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                if not result.data:
                    break
                all_photos.extend(result.data)
                if len(result.data) < page_size:
                    break
                offset += page_size

            # Load photo_faces (paginated)
            all_faces = []
            offset = 0
            while True:
                result = (
                    client.table("photo_faces")
                    .select("face_id, photo_id")
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                if not result.data:
                    break
                all_faces.extend(result.data)
                if len(result.data) < page_size:
                    break
                offset += page_size

            # Build face_id -> photo_id mapping
            face_to_photo = {}
            photo_face_ids: dict[str, set] = {}
            for face_row in all_faces:
                fid = face_row["face_id"]
                pid = face_row["photo_id"]
                face_to_photo[fid] = pid
                photo_face_ids.setdefault(pid, set()).add(fid)

            registry = cls()
            for row in all_photos:
                photo_id = row["photo_id"]
                entry: dict = {
                    "path": row.get("path", ""),
                    "face_ids": photo_face_ids.get(photo_id, set()),
                    "source": row.get("source", ""),
                    "collection": row.get("collection", ""),
                    "source_url": row.get("source_url", ""),
                }
                # Preserve dimension and metadata fields
                if row.get("width") is not None:
                    entry["width"] = row["width"]
                if row.get("height") is not None:
                    entry["height"] = row["height"]
                if row.get("upload_date"):
                    entry["upload_date"] = row["upload_date"]
                if row.get("uploaded_by"):
                    entry["uploaded_by"] = row["uploaded_by"]
                if row.get("job_id"):
                    entry["job_id"] = row["job_id"]
                if row.get("created_at"):
                    entry["created_at"] = row["created_at"]
                if row.get("updated_at"):
                    entry["updated_at"] = row["updated_at"]
                registry._photos[photo_id] = entry

            registry._face_to_photo = face_to_photo

            # Pre-build filename index for cross-ID resolution (inbox vs SHA256)
            registry._build_filename_index()

            logger.info(
                f"PhotoRegistry loaded from Postgres "
                f"({len(registry._photos)} photos, {len(registry._face_to_photo)} faces)"
            )
            return registry

        except Exception as e:
            logger.warning(f"PhotoRegistry.load_from_postgres failed: {e}")
            return None

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

        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"PhotoRegistry: corrupted JSON in {path}: {e}")
            raise ValueError(f"PhotoRegistry file is corrupted ({path}): {e}") from e

        if data.get("schema_version") != 1:
            raise ValueError(f"PhotoRegistry schema version mismatch: expected 1, got {data.get('schema_version')}")

        try:
            registry = cls()

            # Restore photos with face_ids as sets, preserve metadata fields
            for photo_id, photo_data in data["photos"].items():
                entry = {
                    "path": photo_data["path"],
                    "face_ids": set(photo_data["face_ids"]),
                    "source": photo_data.get("source", ""),  # Backward compatible
                    "collection": photo_data.get("collection", ""),
                    "source_url": photo_data.get("source_url", ""),
                }
                # Restore all extra metadata fields (BE-012)
                for key, value in photo_data.items():
                    if key not in ("path", "face_ids", "source", "collection", "source_url"):
                        entry[key] = value
                registry._photos[photo_id] = entry

            # Restore face_to_photo mapping
            registry._face_to_photo = data["face_to_photo"]
        except KeyError as e:
            logger.error(f"PhotoRegistry: missing required key {e} in {path}")
            raise ValueError(f"PhotoRegistry file is missing required key {e} ({path})") from e

        logger.info(
            f"PhotoRegistry loaded from {path} ({len(registry._photos)} photos, {len(registry._face_to_photo)} faces)"
        )

        return registry
