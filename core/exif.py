"""
EXIF extraction utility (BE-013).

Extracts date, camera, GPS from uploaded photos where available.
Uses PIL/Pillow which is already a project dependency.

All heavy imports (PIL) are deferred to maintain testability of pure functions.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# EXIF tag IDs
EXIF_DATE_ORIGINAL = 36867   # DateTimeOriginal
EXIF_DATE_DIGITIZED = 36868  # DateTimeDigitized
EXIF_DATE_MODIFIED = 306     # DateTime
EXIF_MAKE = 271              # Camera make
EXIF_MODEL = 272             # Camera model
EXIF_GPS_INFO = 34853        # GPSInfo


def extract_exif(image_path: str | Path) -> dict:
    """
    Extract EXIF metadata from an image file.

    Returns a dict with available fields:
    - date_taken: str (ISO-ish format, e.g. "1945-06-15" or "2026-02-10 14:30:00")
    - camera: str (make + model)
    - gps_lat: float
    - gps_lon: float

    Returns empty dict if no EXIF data or PIL not available.
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
    except ImportError:
        logger.warning("PIL not available — EXIF extraction disabled")
        return {}

    result = {}
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if not exif_data:
            return {}

        # Extract date
        for tag_id in (EXIF_DATE_ORIGINAL, EXIF_DATE_DIGITIZED, EXIF_DATE_MODIFIED):
            if tag_id in exif_data and exif_data[tag_id]:
                raw_date = str(exif_data[tag_id]).strip()
                # Convert "2026:02:10 14:30:00" to "2026-02-10 14:30:00"
                result["date_taken"] = raw_date.replace(":", "-", 2)
                break

        # Extract camera
        make = str(exif_data.get(EXIF_MAKE, "")).strip()
        model = str(exif_data.get(EXIF_MODEL, "")).strip()
        if make or model:
            camera = f"{make} {model}".strip()
            # Avoid duplication like "Canon Canon EOS 5D"
            if make and model.startswith(make):
                camera = model
            result["camera"] = camera

        # Extract GPS
        gps_info = exif_data.get(EXIF_GPS_INFO)
        if gps_info:
            lat = _convert_gps(gps_info.get(2), gps_info.get(1))
            lon = _convert_gps(gps_info.get(4), gps_info.get(3))
            if lat is not None and lon is not None:
                result["gps_lat"] = round(lat, 6)
                result["gps_lon"] = round(lon, 6)

    except Exception as e:
        logger.debug(f"EXIF extraction failed for {image_path}: {e}")

    return result


def _convert_gps(coords, ref) -> float | None:
    """Convert GPS coordinates from EXIF format to decimal degrees."""
    if not coords or not ref:
        return None
    try:
        degrees = float(coords[0])
        minutes = float(coords[1])
        seconds = float(coords[2])
        decimal = degrees + minutes / 60 + seconds / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except (TypeError, ValueError, IndexError):
        return None
