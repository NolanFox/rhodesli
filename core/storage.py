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

import json
import logging
import os
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Storage configuration
STORAGE_MODE = os.getenv("STORAGE_MODE", "local")  # "local" or "r2"
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

# R2 write credentials (optional — only needed for upload persistence)
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "")


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


# =============================================================================
# R2 Write Operations (for upload persistence)
# =============================================================================

_r2_client = None


def can_write_r2() -> bool:
    """Check if R2 write credentials are configured."""
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME)


def _get_r2_client():
    """Get or create a boto3 S3 client for R2 writes."""
    global _r2_client
    if _r2_client is not None:
        return _r2_client

    import boto3
    endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    _r2_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    )
    return _r2_client


def upload_bytes_to_r2(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to R2 and return the public URL.

    Args:
        key: R2 object key (e.g., "uploads/compare/abc123.jpg")
        data: File content as bytes
        content_type: MIME type

    Returns:
        Public URL for the uploaded object
    """
    client = _get_r2_client()
    client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return f"{R2_PUBLIC_URL}/{key}"


def download_bytes_from_r2(key: str) -> bytes | None:
    """Download bytes from R2. Returns None if not found."""
    try:
        client = _get_r2_client()
        response = client.get_object(Bucket=R2_BUCKET_NAME, Key=key)
        return response["Body"].read()
    except Exception:
        return None


def get_upload_url(upload_key: str) -> str:
    """Get the public URL for an upload key."""
    if is_r2_mode() and R2_PUBLIC_URL:
        return f"{R2_PUBLIC_URL}/{quote(upload_key)}"
    return f"/uploads/{quote(upload_key)}"
