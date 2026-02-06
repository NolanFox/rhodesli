"""
Storage abstraction for photos and face crops.

Supports two modes:
- Local mode (default): serves from filesystem via app routes
- R2 mode: returns Cloudflare R2 public URLs

Local development uses local mode by default. Production uses R2 mode
when STORAGE_MODE=r2 and R2_PUBLIC_URL are set.

Environment variables:
- STORAGE_MODE: "local" (default) or "r2"
- R2_PUBLIC_URL: Base URL for R2 bucket (e.g., "https://pub-xxx.r2.dev")
"""

import os
from pathlib import Path
from urllib.parse import quote

# Storage configuration
STORAGE_MODE = os.getenv("STORAGE_MODE", "local")  # "local" or "r2"
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")


def is_r2_mode() -> bool:
    """Check if running in R2 mode (photos served from Cloudflare R2)."""
    return STORAGE_MODE == "r2" and bool(R2_PUBLIC_URL)


def get_photo_url(photo_path: str) -> str:
    """
    Get URL for a full photo.

    Args:
        photo_path: Path to photo, can be:
            - Just filename: "photo.jpg"
            - Relative path: "raw_photos/photo.jpg"
            - Full path: "/path/to/raw_photos/photo.jpg"

    Returns:
        URL to access the photo (either local route or R2 URL)
    """
    # Extract just the filename
    filename = Path(photo_path).name

    if is_r2_mode():
        # R2 mode: return public R2 URL
        return f"{R2_PUBLIC_URL}/raw_photos/{quote(filename)}"
    else:
        # Local mode: return local route
        return f"/photos/{quote(filename)}"


def get_crop_url(identity_id: str, face_index: int = 0) -> str:
    """
    Get URL for a face crop image.

    Args:
        identity_id: The identity UUID
        face_index: Which face crop (default 0 for primary)

    Returns:
        URL to access the crop (either local static or R2 URL)
    """
    crop_filename = f"{identity_id}_{face_index}.jpg"

    if is_r2_mode():
        # R2 mode: return public R2 URL
        return f"{R2_PUBLIC_URL}/crops/{crop_filename}"
    else:
        # Local mode: return static file route
        return f"/static/crops/{crop_filename}"


def get_crop_url_by_filename(crop_filename: str) -> str:
    """
    Get URL for a face crop image by its filename.

    Unlike get_crop_url() which constructs the filename from identity_id,
    this takes the filename directly. Used when the crop filename is already
    resolved (e.g., from resolve_face_image_url).

    Args:
        crop_filename: Crop filename like "inbox_abc123.jpg" or "photo_22.5_0.jpg"

    Returns:
        URL to access the crop (either local static or R2 URL)
    """
    if is_r2_mode():
        # R2 mode: return public R2 URL
        return f"{R2_PUBLIC_URL}/crops/{quote(crop_filename)}"
    else:
        # Local mode: return static file route
        return f"/static/crops/{quote(crop_filename)}"


