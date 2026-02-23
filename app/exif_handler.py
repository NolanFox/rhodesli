"""
EXIF orientation normalization for Gemini-InsightFace alignment.

Problem: InsightFace operates on the decoded image (auto-rotated by PIL).
Gemini may or may not respect EXIF orientation when analyzing coordinates.
Solution: Strip EXIF orientation and save in displayed orientation before
sending to Gemini. This ensures both systems see the same pixel layout.

AD reference: AD-144 (face alignment via coordinate bridging)
PRD reference: PRD-015 v2
"""

import io
import logging

logger = logging.getLogger(__name__)

# EXIF orientation tag ID
EXIF_ORIENTATION_TAG = 0x0112


def normalize_orientation(image_bytes: bytes) -> bytes:
    """
    Strip EXIF orientation and return image in its displayed orientation.
    This ensures Gemini and InsightFace see the same pixel layout.

    Args:
        image_bytes: Raw image file bytes (may have EXIF orientation)
    Returns:
        Image bytes with orientation applied and EXIF stripped
    """
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes))

    # Apply EXIF orientation transform (rotates/flips as needed)
    img = ImageOps.exif_transpose(img)

    # Re-save without EXIF orientation metadata
    output = io.BytesIO()
    fmt = img.format or "JPEG"
    # Strip all EXIF data to prevent orientation confusion
    img.save(output, format=fmt)
    return output.getvalue()


def get_image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """Return (width, height) of the orientation-corrected image."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)
    return img.size  # (width, height)


def has_exif_orientation(image_bytes: bytes) -> bool:
    """Check if image has non-trivial EXIF orientation tag."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    try:
        exif = img.getexif()
        if not exif:
            return False
        orientation = exif.get(EXIF_ORIENTATION_TAG)
        # Orientation 1 = normal (no transform needed)
        return orientation is not None and orientation != 1
    except Exception:
        return False
