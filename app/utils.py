"""
Pure utility functions extracted from app/main.py.

These have no dependencies on app state, caches, or route handlers.
Only stdlib + core.storage dependencies.
"""

import hashlib
import re
from pathlib import Path

from core import storage


def _pl(count, singular, plural=None):
    """Pluralize: _pl(3, 'face') -> '3 faces', _pl(1, 'face') -> '1 face'."""
    plural = plural or f"{singular}s"
    return f"{count} {singular}" if count == 1 else f"{count} {plural}"


def _section_for_state(state: str) -> str:
    """Map identity state to the correct sidebar section for navigation links."""
    if state == "CONFIRMED":
        return "confirmed"
    elif state == "SKIPPED":
        return "skipped"
    elif state in ("REJECTED", "CONTESTED"):
        return "rejected"
    else:  # INBOX, PROPOSED
        return "to_review"


def make_css_id(raw_id: str) -> str:
    """
    Create a safe CSS identifier from a face_id.
    Replaces colons, spaces, and special chars with hyphens.
    Example: "John Doe:face0" -> "face-card-John-Doe-face0"
    """
    safe = re.sub(r'[^a-zA-Z0-9\-_]', '-', raw_id)
    safe = re.sub(r'-+', '-', safe)
    return f"face-card-{safe}"


def generate_photo_id(filename: str) -> str:
    """
    Generate a stable, deterministic photo_id from filename.

    Always uses basename for consistency — all photos live in raw_photos/.
    """
    basename = Path(filename).name
    hash_bytes = hashlib.sha256(basename.encode("utf-8")).hexdigest()
    return hash_bytes[:16]


def generate_face_id(filename: str, face_index: int) -> str:
    """
    Generate a stable face ID from filename and index.
    Format: {filename_stem}:face{index}
    """
    stem = Path(filename).stem
    return f"{stem}:face{face_index}"


def sanitize_stem(stem: str) -> str:
    """
    Sanitize a filename stem to match crop file naming convention.
    Mirrors the logic in core/crop_faces.py:sanitize_filename().
    """
    sanitized = stem.lower()
    sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized


def parse_quality_from_filename(filename: str) -> float:
    """Extract quality score from filename like 'brass_rail_21.98_0.jpg'."""
    match = re.search(r'_(\d+\.\d+)_\d+\.jpg$', filename)
    if match:
        return float(match.group(1))
    return 0.0


def photo_url(filename: str) -> str:
    """
    Generate a properly URL-encoded path for a photo.

    In local mode: returns /photos/{filename} (served by app route)
    In R2 mode: returns Cloudflare R2 public URL for raw_photos/
    """
    return storage.get_photo_url(filename)


def _read_app_version() -> str:
    """Extract version from CHANGELOG.md header."""
    changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    if changelog.exists():
        try:
            with open(changelog) as f:
                for line in f:
                    m = re.search(r'\[v(\d+\.\d+\.\d+)\]', line)
                    if m:
                        return f"v{m.group(1)}"
        except Exception:
            pass
    return "v0.0.0"


APP_VERSION = _read_app_version()
