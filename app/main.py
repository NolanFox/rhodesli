"""
Rhodesli Forensic Workstation.

A triage-focused interface for identity verification with epistemic humility.
The UI reflects backend state - it never calculates probabilities.

Error Semantics:
- 409 = Variance Explosion (faces too dissimilar)
- 423 = Lock Contention (another process is writing)
- 404 = Identity or face not found
"""

import hashlib
import io
import json
import logging
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
from fasthtml.common import *
from PIL import Image
from starlette.datastructures import UploadFile
from starlette.responses import FileResponse

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.registry import IdentityRegistry, IdentityState
from core.config import (
    MATCH_THRESHOLD_HIGH,
    MATCH_THRESHOLD_MEDIUM,
    HOST,
    PORT,
    DEBUG,
    PROCESSING_ENABLED,
    DATA_DIR,
    PHOTOS_DIR,
)
from core.ui_safety import ensure_utf8_display
from core import storage
from app.auth import (
    is_auth_enabled, SESSION_SECRET, INVITE_CODES,
    get_current_user, User,
    login_with_supabase, signup_with_supabase, validate_invite_code,
    send_password_reset, update_password, get_oauth_url, get_user_from_token,
    exchange_code_for_session,
)

# --- INSTRUMENTATION IMPORT ---
from core.event_recorder import get_event_recorder

static_path = Path(__file__).resolve().parent / "static"
# Data and photos paths come from config, which handles STORAGE_DIR for Railway
data_path = Path(DATA_DIR) if Path(DATA_DIR).is_absolute() else project_root / DATA_DIR
photos_path = Path(PHOTOS_DIR) if Path(PHOTOS_DIR).is_absolute() else project_root / PHOTOS_DIR

# No blanket auth — all GET routes are public.
# Specific POST routes use @require_admin or @require_login decorators.

app, rt = fast_app(
    pico=False,
    secret_key=SESSION_SECRET,
    hdrs=(
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Script(src="https://cdn.tailwindcss.com"),
        # Hyperscript required for _="on click..." modal interactions
        Script(src="https://unpkg.com/hyperscript.org@0.9.12"),
        # Global: handle auth error hash fragments and recovery redirects
        Script("""
            document.addEventListener('DOMContentLoaded', function() {
                var hash = window.location.hash.substring(1);
                if (!hash) return;
                var params = new URLSearchParams(hash);
                var error = params.get('error');
                var errorCode = params.get('error_code');
                var errorDesc = params.get('error_description');

                // If user lands on wrong page with a valid recovery token, redirect
                var type = params.get('type');
                if (type === 'recovery' && params.get('access_token')) {
                    window.location.href = '/reset-password' + window.location.hash;
                    return;
                }

                if (error) {
                    var messages = {
                        'otp_expired': 'This link has expired. Please request a new one.',
                        'access_denied': 'There was a problem with your login link. Please try again.'
                    };
                    var msg = messages[errorCode] || (errorDesc ? errorDesc.replace(/\\+/g, ' ') : 'An error occurred.');

                    var container = document.getElementById('toast-container');
                    if (container) {
                        var toast = document.createElement('div');
                        toast.className = 'px-4 py-3 rounded shadow-lg flex items-center bg-red-600 text-white';
                        toast.innerHTML = '<span class="mr-2">&#10007;</span><span>' + msg + '</span>';
                        container.appendChild(toast);
                        setTimeout(function() { toast.remove(); }, 8000);
                    }

                    history.replaceState(null, '', window.location.pathname + window.location.search);
                }
            });
        """),
        # Global: intercept HTMX 401 responses to show login modal instead of swapping content
        Script("""
            document.body.addEventListener('htmx:beforeSwap', function(evt) {
                if (evt.detail.xhr.status === 401) {
                    evt.detail.shouldSwap = false;
                    var modal = document.getElementById('login-modal');
                    if (modal) modal.classList.remove('hidden');
                }
            });
        """),
        # Global: styled confirmation dialog replacing native confirm()
        Script("""
            document.body.addEventListener('htmx:confirm', function(evt) {
                evt.preventDefault();
                var modal = document.getElementById('confirm-modal');
                if (!modal) { evt.detail.issueRequest(true); return; }
                document.getElementById('confirm-modal-message').textContent = evt.detail.question;
                modal.classList.remove('hidden');
                document.getElementById('confirm-modal-yes').onclick = function() {
                    modal.classList.add('hidden');
                    evt.detail.issueRequest(true);
                };
                document.getElementById('confirm-modal-no').onclick = function() {
                    modal.classList.add('hidden');
                };
            });
        """),
    ),
    static_path=str(static_path),
)

# --- INSTRUMENTATION LIFECYCLE HOOKS ---
@app.on_event("startup")
async def startup_event():
    """Initialize required directories and log the start of a session/run."""
    # Deployment safety: ensure all required directories exist
    required_dirs = [
        data_path / "uploads",
        data_path / "inbox",
        data_path / "cleanup_backups",
        static_path / "crops",
        Path(__file__).resolve().parent.parent / "logs",
    ]
    for dir_path in required_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Load photo path cache for serving inbox uploads
    _load_photo_path_cache()
    print(f"[startup] Photo path cache: {len(_photo_path_cache)} inbox photos indexed")

    get_event_recorder().record("RUN_START", {
        "action": "server_start",
        "timestamp_utc": datetime.utcnow().isoformat()
    }, actor="system")

@app.on_event("shutdown")
async def shutdown_event():
    """Log the end of a session/run."""
    get_event_recorder().record("RUN_END", {
        "action": "server_shutdown",
        "timestamp_utc": datetime.utcnow().isoformat()
    }, actor="system")
# ---------------------------------------

# Photo path lookup cache (loaded at startup)
# Maps filename (basename) -> full path for photos stored outside raw_photos/
_photo_path_cache: dict[str, Path] = {}


def _load_photo_path_cache():
    """
    Build filename -> path lookup from photo_index.json.

    Called at startup to enable O(1) photo path resolution without
    filesystem searching. Includes paths for inbox uploads (data/uploads/)
    which are stored outside raw_photos/.
    """
    global _photo_path_cache
    _photo_path_cache.clear()

    photo_index_path = data_path / "photo_index.json"
    if not photo_index_path.exists():
        return

    with open(photo_index_path) as f:
        index = json.load(f)

    missing_files = []
    for photo_id, photo_data in index.get("photos", {}).items():
        path_str = photo_data.get("path", "")
        if not path_str:
            continue

        path = Path(path_str)

        # Resolve relative paths against project root
        if path.is_absolute():
            full_path = path
        else:
            full_path = project_root / path

        # Cache inbox uploads (data/uploads/) for serving
        # Legacy raw_photos/ files are served via StaticFiles fallback
        if "data/uploads" in path_str or path.is_absolute():
            _photo_path_cache[full_path.name] = full_path
            # Track missing files for startup warning
            if not full_path.exists():
                missing_files.append(path_str)

    if missing_files:
        print(f"[startup] WARNING: {len(missing_files)} photos in index have missing files")
        print(f"[startup] First 5 missing: {missing_files[:5]}")


@app.get("/photos/{filename:path}")
async def serve_photo(filename: str):
    """
    Serve photos from raw_photos/ or data/uploads/.

    Resolution order:
    1. raw_photos/{filename} (legacy photos)
    2. photo_path_cache lookup (inbox uploads)
    """
    # Try 1: Legacy raw_photos location
    legacy_path = photos_path / filename
    if legacy_path.exists() and legacy_path.is_file():
        return FileResponse(legacy_path)

    # Try 2: Lookup in photo_path_cache (populated from photo_index.json)
    if filename in _photo_path_cache:
        cached_path = _photo_path_cache[filename]
        if cached_path.exists():
            return FileResponse(cached_path)
        else:
            # File moved/deleted - return 404 with diagnostic info
            return Response(
                content=f"Photo file missing: {cached_path}",
                status_code=404,
                media_type="text/plain"
            )

    # Not found anywhere
    return Response(
        content=f"Photo not found: {filename}",
        status_code=404,
        media_type="text/plain"
    )


# IMPORTANT: Move photos route to position 0 to take precedence over
# FastHTML's catch-all static route (/{fname:path}.{ext:static})
for i, route in enumerate(app.routes):
    if getattr(route, "path", None) == "/photos/{filename:path}":
        photos_route = app.routes.pop(i)
        app.routes.insert(0, photos_route)
        break

# Registry path - single source of truth
REGISTRY_PATH = data_path / "identities.json"


def load_registry():
    """Load the identity registry (backend authority)."""
    if REGISTRY_PATH.exists():
        return IdentityRegistry.load(REGISTRY_PATH)
    return IdentityRegistry()


def save_registry(registry):
    """Save registry with atomic write (backend handles locking)."""
    registry.save(REGISTRY_PATH)


# =============================================================================
# USER ACTION LOGGING (LEGACY - REPLACED BY EVENT RECORDER)
# =============================================================================
# We keep this for backward compatibility if needed, but EventRecorder is primary now.

logs_path = Path(__file__).resolve().parent.parent / "logs"


def _check_admin(sess) -> Response | None:
    """Return a 401/403/redirect Response if user is not admin, else None.
    When auth is disabled, always allows access.
    Returns 401 (not 303) so HTMX beforeSwap handler can show login modal."""
    if not is_auth_enabled():
        return None  # Auth disabled — everyone has access
    user = get_current_user(sess or {})
    if not user:
        return Response("", status_code=401)
    if not user.is_admin:
        return Response(
            to_xml(toast("You don't have permission to do this.", "error")),
            status_code=403,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )
    return None


def _check_login(sess) -> Response | None:
    """Return a 401/redirect Response if user is not logged in, else None.
    When auth is disabled, always allows access.
    Returns 401 (not 303) so HTMX beforeSwap handler can show login modal."""
    if not is_auth_enabled():
        return None  # Auth disabled — everyone has access
    user = get_current_user(sess or {})
    if not user:
        return Response("", status_code=401)
    return None


def log_user_action(action: str, **kwargs) -> None:
    """
    Log a user action to the append-only user_actions.log.

    Format: ISO_TIMESTAMP | ACTION | key=value key=value ...

    Args:
        action: Action name (e.g., "DETACH", "MERGE", "RENAME")
        kwargs: Key-value pairs to log
    """
    logs_path.mkdir(parents=True, exist_ok=True)
    log_file = logs_path / "user_actions.log"

    timestamp = datetime.now(timezone.utc).isoformat()
    kvs = " ".join(f"{k}={v}" for k, v in kwargs.items())
    line = f"{timestamp} | {action} | {kvs}\n"

    with open(log_file, "a") as f:
        f.write(line)


# =============================================================================
# FACE DATA & PHOTO REGISTRY LOADERS
# =============================================================================

_face_data_cache = None
_photo_registry_cache = None


def load_face_embeddings() -> dict[str, dict]:
    """
    Load face embeddings as face_id -> {mu, sigma_sq} dict.

    Returns:
        Dict mapping face_id to {"mu": np.ndarray, "sigma_sq": np.ndarray}
    """
    embeddings_path = data_path / "embeddings.npy"
    if not embeddings_path.exists():
        return {}

    embeddings = np.load(embeddings_path, allow_pickle=True)

    face_data = {}
    filename_face_counts = {}

    for entry in embeddings:
        filename = entry["filename"]

        # Track face index per filename (same logic as generate_face_id)
        if filename not in filename_face_counts:
            filename_face_counts[filename] = 0
        face_index = filename_face_counts[filename]
        filename_face_counts[filename] += 1

        # Use stored face_id if present (inbox format), otherwise generate legacy format
        face_id = entry.get("face_id") or generate_face_id(filename, face_index)

        # Extract mu and sigma_sq
        if "mu" in entry:
            mu = entry["mu"]
            sigma_sq = entry["sigma_sq"]
        else:
            # Legacy format: use embedding directly, compute default sigma_sq
            mu = np.asarray(entry["embedding"], dtype=np.float32)
            # Default sigma_sq based on det_score if available
            det_score = entry.get("det_score", 0.5)
            sigma_sq_val = 1.0 - (det_score * 0.9)  # 0.1 to 1.0
            sigma_sq = np.full(512, sigma_sq_val, dtype=np.float32)

        face_data[face_id] = {
            "mu": np.asarray(mu, dtype=np.float32),
            "sigma_sq": np.asarray(sigma_sq, dtype=np.float32),
        }

    return face_data


def get_face_data() -> dict[str, dict]:
    """Get face data with caching."""
    global _face_data_cache
    if _face_data_cache is None:
        _face_data_cache = load_face_embeddings()
    return _face_data_cache


def load_photo_registry():
    """Load the photo registry for merge validation."""
    global _photo_registry_cache
    if _photo_registry_cache is None:
        from core.photo_registry import PhotoRegistry
        photo_index_path = data_path / "photo_index.json"
        if photo_index_path.exists():
            _photo_registry_cache = PhotoRegistry.load(photo_index_path)
        else:
            _photo_registry_cache = PhotoRegistry()
    return _photo_registry_cache


# =============================================================================
# PHOTO CONTEXT HELPERS
# =============================================================================

def generate_photo_id(filename: str) -> str:
    """
    Generate a stable, deterministic photo_id from filename or filepath.

    For absolute paths (inbox uploads), uses full path to avoid collisions
    when same filename exists in different upload directories.
    For relative paths (raw_photos/), uses basename for backward compatibility.
    """
    path = Path(filename)
    if path.is_absolute():
        # Inbox uploads: use full path to differentiate upload sessions
        hash_bytes = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    else:
        # Legacy raw_photos: use basename only (backward compatible)
        hash_bytes = hashlib.sha256(path.name.encode("utf-8")).hexdigest()
    return hash_bytes[:16]


def generate_face_id(filename: str, face_index: int) -> str:
    """
    Generate a stable face ID from filename and index.
    Format: {filename_stem}:face{index}
    """
    stem = Path(filename).stem
    return f"{stem}:face{face_index}"


def make_css_id(raw_id: str) -> str:
    """
    Create a safe CSS identifier from a face_id.
    Replaces colons, spaces, and special chars with hyphens.
    Example: "John Doe:face0" -> "face-card-John-Doe-face0"
    """
    # Replace non-alphanumeric characters with hyphens
    safe = re.sub(r'[^a-zA-Z0-9\-_]', '-', raw_id)
    # Collapse multiple hyphens to look cleaner
    safe = re.sub(r'-+', '-', safe)
    return f"face-card-{safe}"


def load_embeddings_for_photos():
    """
    Load embeddings and build photo metadata cache.

    Returns:
        dict mapping photo_id -> {
            "filename": str,
            "filepath": str,
            "faces": list of {face_id, bbox, face_index}
        }
    """
    embeddings_path = data_path / "embeddings.npy"
    if not embeddings_path.exists():
        return {}

    embeddings = np.load(embeddings_path, allow_pickle=True)

    # Group faces by photo_id
    photos = {}
    filename_face_counts = {}

    for entry in embeddings:
        filename = entry["filename"]

        # Track face index per filename
        if filename not in filename_face_counts:
            filename_face_counts[filename] = 0
        face_index = filename_face_counts[filename]
        filename_face_counts[filename] += 1

        # Use filepath for photo_id to avoid collisions when same filename
        # exists in multiple upload directories
        filepath = entry.get("filepath", f"raw_photos/{filename}")
        photo_id = generate_photo_id(filepath)
        # Use stored face_id if present (inbox format), otherwise generate legacy format
        face_id = entry.get("face_id") or generate_face_id(filename, face_index)

        # Parse bbox - it might be a string or list
        bbox = entry["bbox"]
        if isinstance(bbox, str):
            bbox = json.loads(bbox)
        elif hasattr(bbox, "tolist"):
            bbox = bbox.tolist()

        if photo_id not in photos:
            photos[photo_id] = {
                "filename": filename,
                "filepath": filepath,
                "faces": [],
            }

        photos[photo_id]["faces"].append({
            "face_id": face_id,
            "bbox": bbox,  # [x1, y1, x2, y2]
            "face_index": face_index,
            "det_score": float(entry.get("det_score", 0)),
            "quality": float(entry.get("quality", 0)),
        })

    return photos


_photo_dimensions_cache = None


def _load_photo_dimensions_cache() -> dict:
    """Load photo dimensions from photo_index.json into a cache."""
    global _photo_dimensions_cache
    if _photo_dimensions_cache is not None:
        return _photo_dimensions_cache

    _photo_dimensions_cache = {}
    photo_index_path = data_path / "photo_index.json"
    if photo_index_path.exists():
        try:
            import json
            with open(photo_index_path) as f:
                data = json.load(f)
            for photo_id, photo_data in data.get("photos", {}).items():
                width = photo_data.get("width", 0)
                height = photo_data.get("height", 0)
                if width > 0 and height > 0:
                    # Index by path and by filename for flexible lookup
                    path = photo_data.get("path", "")
                    if path:
                        _photo_dimensions_cache[path] = (width, height)
                        _photo_dimensions_cache[Path(path).name] = (width, height)
        except Exception as e:
            logging.warning(f"Failed to load photo dimensions cache: {e}")

    return _photo_dimensions_cache


def get_photo_dimensions(filename_or_path: str) -> tuple:
    """
    Get image dimensions for a photo.

    Args:
        filename_or_path: Either a filename (looks in raw_photos/), a relative
            path like 'raw_photos/file.jpg', or an absolute path. Tries the
            path directly first, then falls back to raw_photos/{basename}.

    Returns:
        (width, height) tuple or (0, 0) if file not found
    """
    path = Path(filename_or_path)

    # In R2 mode, photos aren't stored locally, so use cached dimensions
    # from photo_index.json instead of reading from filesystem
    if storage.is_r2_mode():
        cache = _load_photo_dimensions_cache()
        # Try exact path first, then filename only
        if str(filename_or_path) in cache:
            return cache[str(filename_or_path)]
        if path.name in cache:
            return cache[path.name]
        # If not in cache, return (0, 0) - can't read from R2 directly
        return (0, 0)

    # Local mode: read from filesystem
    filepath = None

    # Try 1: Path as provided (works for relative paths like 'raw_photos/file.jpg'
    # and absolute paths)
    if path.exists():
        filepath = path
    else:
        # Try 2: Look in raw_photos/ by basename only
        filepath = photos_path / path.name
        if not filepath.exists():
            return (0, 0)

    try:
        with Image.open(filepath) as img:
            return img.size  # (width, height)
    except Exception:
        return (0, 0)


def get_identity_for_face(registry, face_id: str) -> dict:
    """
    Find the identity containing a face.

    Returns:
        Identity dict or None if not found
    """
    for identity in registry.list_identities():
        all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        for entry in all_face_ids:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid == face_id:
                return identity
    return None


def find_shared_photo_filename(
    target_id: str,
    neighbor_id: str,
    registry,
    photo_registry,
) -> str:
    """
    Find the filename of a shared photo between two identities.

    Used to show users why a merge is blocked (co-occurrence).

    Returns:
        Filename of shared photo, or empty string if none found.
    """
    # Get all face IDs for both identities
    faces_a = registry.get_all_face_ids(target_id)
    faces_b = registry.get_all_face_ids(neighbor_id)

    # Get photo_ids for each identity's faces
    photos_a = photo_registry.get_photos_for_faces(faces_a)
    photos_b = photo_registry.get_photos_for_faces(faces_b)

    # Find intersection
    shared_photos = photos_a & photos_b

    if shared_photos:
        # Get filename for first shared photo
        first_photo_id = next(iter(shared_photos))
        photo_path = photo_registry.get_photo_path(first_photo_id)
        if photo_path:
            return Path(photo_path).name

    return ""


def get_first_anchor_face_id(identity_id: str, registry) -> str | None:
    """
    Get the first anchor face ID for an identity.

    Used for showing thumbnails in neighbor cards.

    Returns:
        First anchor face ID, or None if identity has no anchors.
    """
    try:
        anchor_ids = registry.get_anchor_face_ids(identity_id)
        return anchor_ids[0] if anchor_ids else None
    except KeyError:
        return None


# Photo metadata cache (rebuilt on each request for simplicity)
_photo_cache = None
_face_to_photo_cache = None


def _build_caches():
    """Build photo and face-to-photo caches."""
    global _photo_cache, _face_to_photo_cache
    if _photo_cache is None:
        _photo_cache = load_embeddings_for_photos()
        # Build reverse mapping: face_id -> photo_id
        _face_to_photo_cache = {}
        for photo_id, photo_data in _photo_cache.items():
            for face in photo_data["faces"]:
                _face_to_photo_cache[face["face_id"]] = photo_id

        # Merge source data from photo_index.json
        try:
            from core.photo_registry import PhotoRegistry
            photo_registry = PhotoRegistry.load(data_path / "photo_index.json")
            for photo_id in _photo_cache:
                source = photo_registry.get_source(photo_id)
                _photo_cache[photo_id]["source"] = source
        except FileNotFoundError:
            # No photo_index.json yet, set empty sources
            for photo_id in _photo_cache:
                _photo_cache[photo_id]["source"] = ""


def get_photo_metadata(photo_id: str) -> dict:
    """Get photo metadata including face bboxes."""
    _build_caches()
    return _photo_cache.get(photo_id)


def get_photo_id_for_face(face_id: str) -> str:
    """Get the photo_id containing a face."""
    _build_caches()
    return _face_to_photo_cache.get(face_id)


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
    In R2 mode: returns Cloudflare R2 public URL

    Encodes the filename to handle spaces and special characters.
    """
    return storage.get_photo_url(filename)


_crop_files_cache = None


def get_crop_files():
    """
    Get set of available crop filenames.

    In local mode: reads from static/crops directory.
    In R2 mode: builds the expected crop filenames from embeddings data,
    since we can't list R2 bucket contents.

    Crop filename format: {sanitized_stem}_{quality:.2f}_{face_index}.jpg
    """
    global _crop_files_cache
    if _crop_files_cache is not None:
        return _crop_files_cache

    # Try local mode first
    crops_dir = static_path / "crops"
    if crops_dir.exists():
        crop_files = {f.name for f in crops_dir.glob("*.jpg")}
        if crop_files:
            _crop_files_cache = crop_files
            return _crop_files_cache

    # R2 mode or no local crops: build from embeddings
    # The embeddings have: filename, quality, and we compute face_index
    # by tracking order of faces within each unique filename
    crop_files = set()

    embeddings_path = Path(DATA_DIR) / "embeddings.npy"
    if embeddings_path.exists():
        try:
            embeddings = np.load(embeddings_path, allow_pickle=True)
            filename_face_counts = {}

            for entry in embeddings:
                if not isinstance(entry, dict):
                    continue

                filename = entry.get("filename", "")
                quality = entry.get("quality")

                if not filename or quality is None:
                    continue

                # Get face index (order within this filename)
                face_index = filename_face_counts.get(filename, 0)
                filename_face_counts[filename] = face_index + 1

                # Build crop filename
                stem = Path(filename).stem
                sanitized = stem.lower()
                sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)
                sanitized = sanitized.strip('_')

                crop_filename = f"{sanitized}_{quality:.2f}_{face_index}.jpg"
                crop_files.add(crop_filename)

        except Exception as e:
            logging.warning(f"Failed to build crop files from embeddings: {e}")

    _crop_files_cache = crop_files
    return _crop_files_cache


def sanitize_stem(stem: str) -> str:
    """
    Sanitize a filename stem to match crop file naming convention.
    Mirrors the logic in core/crop_faces.py:sanitize_filename().
    """
    sanitized = stem.lower()
    sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized


def resolve_face_image_url(face_id: str, crop_files: set) -> str:
    """
    Resolve a canonical face ID to its crop image URL.

    Supports two face_id formats:
    1. Legacy: {filename_stem}:face{index} -> {sanitized_stem}_{quality}_{index}.jpg
    2. Inbox: inbox_{hash} -> inbox_{hash}.jpg (direct mapping)

    In local mode: returns /static/crops/{filename}
    In R2 mode: returns Cloudflare R2 public URL

    Args:
        face_id: Canonical face identifier
        crop_files: Set of available crop filenames

    Returns:
        URL path to the crop image, or None if no matching crop file is found.
    """
    # Inbox format: face_ids starting with "inbox_" have crops named exactly {face_id}.jpg
    # In R2 mode, inbox crops aren't in embeddings.npy (and thus not in crop_files),
    # so we return the URL directly without checking crop_files.
    if face_id.startswith("inbox_"):
        inbox_crop = f"{face_id}.jpg"
        # In local mode, verify it exists; in R2 mode, assume it exists
        if storage.is_r2_mode() or inbox_crop in crop_files:
            return storage.get_crop_url_by_filename(inbox_crop)

    # Fall back to legacy format parsing
    # Legacy face_ids use format: {filename_stem}:face{index}
    if ":face" not in face_id:
        return None

    stem, face_suffix = face_id.rsplit(":face", 1)
    try:
        face_index = int(face_suffix)
    except ValueError:
        return None

    # Sanitize the stem to match crop file naming
    sanitized = sanitize_stem(stem)

    # Find matching crop file: {sanitized}_{quality}_{index}.jpg
    # Quality is a float like 22.17, index matches face_index
    pattern = re.compile(
        rf'^{re.escape(sanitized)}_[\d.]+_{face_index}\.jpg$'
    )

    for crop in crop_files:
        if pattern.match(crop):
            return storage.get_crop_url_by_filename(crop)

    return None


# =============================================================================
# UI COMPONENTS
# =============================================================================

def toast_container() -> Div:
    """
    Toast notification container.
    UX Intent: Non-blocking feedback for actions.
    """
    return Div(
        id="toast-container",
        cls="fixed top-4 right-4 z-50 flex flex-col gap-2"
    )


def toast(message: str, variant: str = "info") -> Div:
    """
    Single toast notification.
    Variants: success, error, warning, info
    """
    # UI BOUNDARY: sanitize message for safe rendering
    safe_message = ensure_utf8_display(message)

    colors = {
        "success": "bg-emerald-600 text-white",
        "error": "bg-red-600 text-white",
        "warning": "bg-amber-500 text-white",
        "info": "bg-stone-700 text-white",
    }
    icons = {
        "success": "\u2713",
        "error": "\u2717",
        "warning": "\u26a0",
        "info": "\u2139",
    }
    return Div(
        Span(icons.get(variant, ""), cls="mr-2"),
        Span(safe_message),
        cls=f"px-4 py-3 rounded shadow-lg flex items-center {colors.get(variant, colors['info'])} animate-fade-in",
        # Auto-dismiss after 4 seconds
        **{"_": "on load wait 4s then remove me"}
    )


def toast_with_undo(
    message: str,
    source_id: str,
    target_id: str,
    variant: str = "info",
) -> Div:
    """
    Toast notification with inline Undo button (D5).

    Used for "Not Same Person" rejection - allows immediate reversal.
    Auto-dismisses after 8 seconds (longer than standard toast to allow undo).
    """
    colors = {
        "success": "bg-emerald-600 text-white",
        "error": "bg-red-600 text-white",
        "warning": "bg-amber-500 text-white",
        "info": "bg-stone-700 text-white",
    }
    icons = {
        "success": "\u2713",
        "error": "\u2717",
        "warning": "\u26a0",
        "info": "\u2139",
    }
    return Div(
        Span(icons.get(variant, ""), cls="mr-2"),
        Span(message, cls="flex-1"),
        Button(
            "Undo",
            cls="ml-3 px-2 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"/api/identity/{source_id}/unreject/{target_id}",
            hx_swap="outerHTML",
            hx_target="closest div",  # Replace the toast itself
            type="button",
        ),
        cls=f"px-4 py-3 rounded shadow-lg flex items-center {colors.get(variant, colors['info'])} animate-fade-in",
        # Longer dismiss time to allow undo
        **{"_": "on load wait 8s then remove me"}
    )


def sidebar(counts: dict, current_section: str = "to_review", user: "User | None" = None) -> Aside:
    """
    Fixed sidebar navigation for the Command Center.

    Args:
        counts: Dict with keys: to_review, confirmed, skipped, rejected
        current_section: Currently active section
        user: Current user (None if anonymous)
    """
    def nav_item(href: str, icon: str, label: str, count: int, section_key: str, color: str):
        """Single navigation item with badge."""
        is_active = current_section == section_key

        # Dark theme: Active vs inactive styling
        if is_active:
            container_cls = f"bg-slate-700 text-white"
            badge_cls = f"bg-{color}-500 text-white"
        else:
            container_cls = "text-slate-300 hover:bg-slate-700/50"
            badge_cls = f"bg-{color}-500/20 text-{color}-400"

        return A(
            Span(
                Span(icon, cls="mr-2"),
                Span(label),
                cls="flex items-center"
            ),
            Span(
                str(count),
                cls=f"px-2 py-0.5 text-xs font-bold rounded-full {badge_cls}"
            ),
            href=href,
            cls=f"flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] {container_cls}"
        )

    return Aside(
        # Header
        Div(
            H1("Rhodesli", cls="text-xl font-bold text-white"),
            P("Identity System", cls="text-xs text-slate-400 mt-0.5"),
            cls="px-6 py-5 border-b border-slate-700"
        ),
        # Upload Button (admin-only until moderation queue built)
        Div(
            A(
                Svg(
                    Path(
                        stroke_linecap="round",
                        stroke_linejoin="round",
                        stroke_width="2",
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                    ),
                    cls="w-4 h-4",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24"
                ),
                " Upload",
                href="/upload",
                cls="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-500 transition-colors"
            ) if (user and user.is_admin) else None,
            cls="px-4 py-4"
        ),
        # Navigation
        Nav(
            # Review Section
            Div(
                P(
                    "Review",
                    cls="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2"
                ),
                nav_item("/?section=to_review", "📥", "Inbox", counts["to_review"], "to_review", "blue"),
                nav_item("/?section=skipped", "⏸", "Skipped", counts["skipped"], "skipped", "yellow"),
                cls="mb-4"
            ),
            # Library Section
            Div(
                P(
                    "Library",
                    cls="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2"
                ),
                nav_item("/?section=confirmed", "✓", "Confirmed", counts["confirmed"], "confirmed", "green"),
                nav_item("/?section=rejected", "🗑️", "Dismissed", counts["rejected"], "rejected", "gray"),
                cls="mb-4"
            ),
            # Browse Section (photo-centric)
            Div(
                P(
                    "Browse",
                    cls="px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2"
                ),
                nav_item("/?section=photos", "📷", "Photos", counts.get("photos", 0), "photos", "slate"),
                cls="mb-4"
            ),
            cls="flex-1 px-3 py-2 space-y-1 overflow-y-auto"
        ),
        # Footer with user info and stats
        Div(
            # User info / auth link
            Div(
                Div(
                    Span(user.email, cls="text-xs text-slate-400 truncate"),
                    Span(" (admin)" if user.is_admin else "", cls="text-xs text-indigo-400"),
                    cls="flex items-center gap-1"
                ),
                A("Sign out", href="/logout", cls="text-xs text-slate-500 hover:text-slate-300 underline"),
                cls="flex items-center justify-between mb-2"
            ) if user else Div(
                A("Sign in", href="/login", cls="text-xs text-slate-400 hover:text-slate-300 underline"),
                cls="mb-2"
            ),
            Div(
                f"{counts['confirmed']} of {counts['to_review'] + counts['confirmed']} identified",
                cls="text-xs text-slate-500 font-data"
            ),
            Div("v0.6.0", cls="text-xs text-slate-600 mt-1"),
            cls="px-4 py-3 border-t border-slate-700"
        ),
        # Close button for mobile
        Div(
            Button(
                Span("\u00d7", cls="text-2xl"),
                onclick="closeSidebar()",
                cls="text-slate-400 hover:text-white p-2 min-h-[44px] min-w-[44px] flex items-center justify-center"
            ),
            cls="absolute top-3 right-3 lg:hidden"
        ),
        id="sidebar",
        cls="fixed left-0 top-0 h-screen w-64 bg-slate-800 border-r border-slate-700 flex flex-col z-40 -translate-x-full lg:translate-x-0 transition-transform"
    )


def section_header(title: str, subtitle: str, view_mode: str = None, section: str = None) -> Div:
    """
    Section header with optional Focus/Browse toggle.
    """
    header_content = [
        Div(
            H2(title, cls="text-2xl font-bold text-white"),
            P(subtitle, cls="text-sm text-slate-400 mt-1"),
        )
    ]

    # Add view toggle for to_review section
    if section == "to_review" and view_mode is not None:
        toggle = Div(
            A(
                "Focus",
                href="/?section=to_review&view=focus",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg {'bg-white text-slate-900' if view_mode == 'focus' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
            ),
            A(
                "View All",
                href="/?section=to_review&view=browse",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg {'bg-white text-slate-900' if view_mode == 'browse' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
            ),
            cls="flex items-center gap-2"
        )
        header_content.append(toggle)

    return Div(
        *header_content,
        cls="flex items-center justify-between mb-6"
    )


def identity_card_expanded(identity: dict, crop_files: set, is_admin: bool = True) -> Div:
    """
    Expanded identity card for Focus Mode review.
    Shows larger thumbnail and prominent actions (admin only).
    """
    identity_id = identity["identity_id"]
    raw_name = ensure_utf8_display(identity.get("name"))
    name = raw_name or f"Unidentified Person"
    state = identity["state"]

    # Get all faces
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_count = len(all_face_ids)

    # Get first face for main thumbnail
    main_crop_url = None
    main_photo_id = None
    if all_face_ids:
        first_face = all_face_ids[0]
        face_id = first_face if isinstance(first_face, str) else first_face.get("face_id", "")
        main_crop_url = resolve_face_image_url(face_id, crop_files)
        main_photo_id = get_photo_id_for_face(face_id)

    # Build face grid for additional faces (skip first since it's shown as main thumbnail)
    face_previews = []
    for face_entry in all_face_ids[1:6]:  # Skip first face, show up to 5 more
        if isinstance(face_entry, str):
            face_id = face_entry
        else:
            face_id = face_entry.get("face_id", "")
        crop_url = resolve_face_image_url(face_id, crop_files)
        if crop_url:
            # Get photo_id for this face to make it clickable
            face_photo_id = get_photo_id_for_face(face_id)
            if face_photo_id:
                face_previews.append(
                    Button(
                        Img(
                            src=crop_url,
                            cls="w-16 h-16 rounded object-cover border border-slate-600 hover:border-indigo-400 transition-colors",
                            alt=f"Face {face_id[:8]}"
                        ),
                        cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded transition-all",
                        hx_get=f"/photo/{face_photo_id}/partial?face={face_id}",
                        hx_target="#photo-modal-content",
                        **{"_": "on click remove .hidden from #photo-modal"},
                        type="button",
                        title="Click to view photo"
                    )
                )
            else:
                face_previews.append(
                    Img(
                        src=crop_url,
                        cls="w-16 h-16 rounded object-cover border border-slate-600",
                        alt=f"Face {face_id[:8]}"
                    )
                )

    # Action buttons - only for admins
    if is_admin:
        base_confirm_url = f"/inbox/{identity_id}/confirm" if state == "INBOX" else f"/confirm/{identity_id}"
        base_reject_url = f"/inbox/{identity_id}/reject" if state == "INBOX" else f"/reject/{identity_id}"
        confirm_url = f"{base_confirm_url}?from_focus=true"
        reject_url = f"{base_reject_url}?from_focus=true"
        skip_url = f"/identity/{identity_id}/skip?from_focus=true"

        actions = Div(
            Button(
                "✓ Confirm",
                cls="px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors",
                hx_post=confirm_url,
                hx_target="#focus-card",
                hx_swap="outerHTML",
                type="button",
            ),
            Button(
                "⏸ Skip",
                cls="px-4 py-2 bg-yellow-500 text-white font-medium rounded-lg hover:bg-yellow-600 transition-colors",
                hx_post=skip_url,
                hx_target="#focus-card",
                hx_swap="outerHTML",
                type="button",
            ),
            Button(
                "✗ Reject",
                cls="px-4 py-2 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-colors",
                hx_post=reject_url,
                hx_target="#focus-card",
                hx_swap="outerHTML",
                type="button",
            ),
            Button(
                "Find Similar",
                cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors ml-auto",
                hx_get=f"/api/identity/{identity_id}/neighbors",
                hx_target=f"#neighbors-{identity_id}",
                hx_swap="innerHTML",
                type="button",
            ),
            cls="flex items-center gap-3 mt-6"
        )
    else:
        actions = Div(
            Button(
                "Find Similar",
                cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors",
                hx_get=f"/api/identity/{identity_id}/neighbors",
                hx_target=f"#neighbors-{identity_id}",
                hx_swap="innerHTML",
                type="button",
            ),
            cls="flex items-center gap-3 mt-6"
        )

    return Div(
        Div(
            # Left: Main Face
            Div(
                Div(
                    Img(
                        src=main_crop_url or "",
                        alt=name,
                        cls="w-full h-full object-cover"
                    ) if main_crop_url else Span("?", cls="text-6xl text-slate-500"),
                    cls="w-48 h-48 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center"
                ),
                Button(
                    "View Full Photo →",
                    cls="mt-2 text-sm text-indigo-400 hover:text-indigo-300",
                    hx_get=f"/photo/{main_photo_id}/partial" if main_photo_id else None,
                    hx_target="#photo-modal-content",
                    **{"_": "on click remove .hidden from #photo-modal"} if main_photo_id else {},
                    type="button",
                ) if main_photo_id else None,
                cls="flex-shrink-0"
            ),
            # Right: Details + Actions
            Div(
                H3(name, cls="text-xl font-semibold text-white"),
                P(
                    f"{face_count} face{'s' if face_count != 1 else ''}",
                    cls="text-sm text-slate-400 mt-1"
                ),
                # Face grid preview
                Div(
                    *face_previews,
                    cls="flex gap-2 mt-4 flex-wrap"
                ) if len(face_previews) > 1 else None,
                # Neighbors container
                Div(id=f"neighbors-{identity_id}", cls="mt-4"),
                actions,
                cls="flex-1 min-w-0"
            ),
            cls="flex gap-6"
        ),
        cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-6",
        id="focus-card"
    )


def identity_card_mini(identity: dict, crop_files: set, clickable: bool = False) -> Div:
    """
    Mini identity card for queue preview in Focus Mode.

    Args:
        identity: Identity dict
        crop_files: Set of available crop files
        clickable: If True, clicking loads this identity in focus mode
    """
    identity_id = identity["identity_id"]

    # Get first face for thumbnail
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    crop_url = None
    if all_face_ids:
        first_face = all_face_ids[0]
        face_id = first_face if isinstance(first_face, str) else first_face.get("face_id", "")
        crop_url = resolve_face_image_url(face_id, crop_files)

    img_element = Img(
        src=crop_url or "",
        cls="w-full h-full object-cover"
    ) if crop_url else Span("?", cls="text-2xl text-slate-500")

    if clickable:
        # Wrap in a link that loads this identity in focus mode
        return A(
            Div(
                img_element,
                cls="w-full aspect-square rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center hover:ring-2 hover:ring-indigo-400 transition-all"
            ),
            href=f"/?section=to_review&view=focus&current={identity_id}",
            cls="w-24 flex-shrink-0 cursor-pointer",
            title="Click to review this identity"
        )
    else:
        return Div(
            Div(
                img_element,
                cls="w-full aspect-square rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center"
            ),
            cls="w-24 flex-shrink-0"
        )


def render_to_review_section(
    to_review: list,
    crop_files: set,
    view_mode: str,
    counts: dict,
    current_id: str = None,
    is_admin: bool = True,
) -> Div:
    """Render the To Review section with Focus or Browse mode."""

    # For focus mode, prioritize items with more faces (more context to review)
    high_confidence = sorted(
        to_review,
        key=lambda x: len(x.get("anchor_ids", []) + x.get("candidate_ids", [])),
        reverse=True
    )[:10]

    # If a specific identity was requested, move it to the front
    if current_id and view_mode == "focus":
        # Find the requested identity
        current_identity = None
        remaining = []
        for item in high_confidence:
            if item["identity_id"] == current_id:
                current_identity = item
            else:
                remaining.append(item)
        # If not found in high_confidence, search full list
        if not current_identity:
            for item in to_review:
                if item["identity_id"] == current_id:
                    current_identity = item
                    break
        # Reorder with current at front
        if current_identity:
            high_confidence = [current_identity] + remaining[:9]

    if view_mode == "focus":
        if high_confidence:
            # Show one item expanded + queue preview
            content = Div(
                identity_card_expanded(high_confidence[0], crop_files, is_admin=is_admin),
                # Queue Preview
                Div(
                    H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                    Div(
                        *[identity_card_mini(i, crop_files, clickable=True) for i in high_confidence[1:6]],
                        Div(
                            f"+{len(high_confidence) - 6} more",
                            cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square"
                        ) if len(high_confidence) > 6 else None,
                        cls="flex gap-3 overflow-x-auto pb-2"
                    ),
                    cls="mt-6"
                ) if len(high_confidence) > 1 else None,
            )
        else:
            # Empty state
            content = Div(
                Div("🎉", cls="text-4xl mb-4"),
                H3("All caught up!", cls="text-lg font-medium text-white"),
                P("No items to review.", cls="text-slate-400 mt-1"),
                A(
                    "Upload more photos →",
                    href="/upload",
                    cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium"
                ),
                cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-12 text-center"
            )
    else:
        # Browse mode - show grid
        cards = [
            identity_card(identity, crop_files, lane_color="blue", show_actions=True, is_admin=is_admin)
            for identity in to_review
        ]
        cards = [c for c in cards if c]  # Filter None

        if cards:
            content = Div(*cards)
        else:
            content = Div(
                "No items to review. Great job! 🎉",
                cls="text-center py-12 text-slate-400"
            )

    return Div(
        section_header(
            "Inbox",
            f"{counts['to_review']} items need your attention",
            view_mode=view_mode,
            section="to_review"
        ),
        content,
        cls="space-y-6"
    )


def render_confirmed_section(confirmed: list, crop_files: set, counts: dict, is_admin: bool = True) -> Div:
    """Render the Confirmed section."""
    cards = [
        identity_card(identity, crop_files, lane_color="emerald", show_actions=False, is_admin=is_admin)
        for identity in confirmed
    ]
    cards = [c for c in cards if c]

    if cards:
        content = Div(*cards)
    else:
        content = Div(
            "No confirmed identities yet.",
            cls="text-center py-12 text-slate-400"
        )

    return Div(
        section_header("Confirmed", f"{counts['confirmed']} people identified"),
        content,
        cls="space-y-6"
    )


def render_skipped_section(skipped: list, crop_files: set, counts: dict, is_admin: bool = True) -> Div:
    """Render the Skipped section."""
    cards = [
        identity_card(identity, crop_files, lane_color="stone", show_actions=False, is_admin=is_admin)
        for identity in skipped
    ]
    cards = [c for c in cards if c]

    if cards:
        content = Div(*cards)
    else:
        content = Div(
            "No skipped items.",
            cls="text-center py-12 text-slate-400"
        )

    return Div(
        section_header("Skipped", f"{counts['skipped']} items deferred"),
        content,
        cls="space-y-6"
    )


def render_rejected_section(dismissed: list, crop_files: set, counts: dict, is_admin: bool = True) -> Div:
    """Render the Rejected/Dismissed section."""
    cards = [
        identity_card(identity, crop_files, lane_color="rose", show_actions=False, is_admin=is_admin)
        for identity in dismissed
    ]
    cards = [c for c in cards if c]

    if cards:
        content = Div(*cards)
    else:
        content = Div(
            "No dismissed items.",
            cls="text-center py-12 text-slate-400"
        )

    return Div(
        section_header("Dismissed", f"{counts['rejected']} items dismissed"),
        content,
        cls="space-y-6"
    )


def render_photos_section(counts: dict, registry, crop_files: set,
                          filter_source: str = "", sort_by: str = "newest") -> Div:
    """
    Render the Photos section - a grid view of all photos.

    This is the photo-centric workflow, complementing the face-centric inbox.

    Args:
        counts: Sidebar counts dict
        registry: Identity registry
        crop_files: Set of available crop filenames
        filter_source: Filter to show only this collection (empty = all)
        sort_by: Sort order (newest, oldest, most_faces, collection)
    """
    _build_caches()
    if not _photo_cache:
        return Div(
            section_header("Photos", "0 photos"),
            Div(
                "No photos uploaded yet.",
                cls="text-center py-12 text-slate-400"
            ),
            cls="space-y-6"
        )

    # Get all photos with metadata
    photos = []
    sources_set = set()
    for photo_id, photo_data in _photo_cache.items():
        source = photo_data.get("source", "")
        if source:
            sources_set.add(source)

        # Get identified faces in this photo
        identified_faces = []
        for face in photo_data.get("faces", []):
            face_id = face["face_id"]
            identity = get_identity_for_face(registry, face_id)
            if identity and identity.get("name"):
                identified_faces.append({
                    "name": identity.get("name"),
                    "face_id": face_id,
                    "identity_id": identity.get("identity_id"),
                })

        photos.append({
            "photo_id": photo_id,
            "filename": photo_data.get("filename", "unknown"),
            "filepath": photo_data.get("filepath", ""),
            "source": source,
            "face_count": len(photo_data.get("faces", [])),
            "identified_count": len(identified_faces),
            "identified_faces": identified_faces[:4],  # Max 4 for display
        })

    sources = sorted(sources_set)

    # Apply filter
    if filter_source:
        photos = [p for p in photos if p["source"] == filter_source]

    # Apply sorting
    if sort_by == "oldest":
        photos = sorted(photos, key=lambda p: p["filename"])
    elif sort_by == "newest":
        photos = sorted(photos, key=lambda p: p["filename"], reverse=True)
    elif sort_by == "most_faces":
        photos = sorted(photos, key=lambda p: p["face_count"], reverse=True)
    elif sort_by == "collection":
        photos = sorted(photos, key=lambda p: (p["source"] or "zzz", p["filename"]))

    # Build subtitle
    subtitle_parts = [f"{len(photos)} photos"]
    if sources:
        subtitle_parts.append(f"{len(sources)} collections")
    subtitle = " \u2022 ".join(subtitle_parts)

    # Build filter/sort options
    source_options = [Option("All Collections", value="", selected=not filter_source)]
    for s in sources:
        source_options.append(Option(s, value=s, selected=(filter_source == s)))

    sort_options = [
        Option("Newest First", value="newest", selected=(sort_by == "newest")),
        Option("Oldest First", value="oldest", selected=(sort_by == "oldest")),
        Option("Most Faces", value="most_faces", selected=(sort_by == "most_faces")),
        Option("By Collection", value="collection", selected=(sort_by == "collection")),
    ]

    # Filter/sort controls
    from urllib.parse import quote
    filter_bar = Div(
        # Collection filter
        Div(
            Label("Collection:", cls="text-sm text-slate-400 mr-2"),
            Select(
                *source_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                    "focus:ring-2 focus:ring-indigo-500",
                onchange=f"window.location.href='/?section=photos&filter_source=' + encodeURIComponent(this.value) + '&sort_by={sort_by}'"
            ),
            cls="flex items-center"
        ),
        # Sort
        Div(
            Label("Sort:", cls="text-sm text-slate-400 mr-2"),
            Select(
                *sort_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                    "focus:ring-2 focus:ring-indigo-500",
                onchange=f"window.location.href='/?section=photos&filter_source={quote(filter_source)}&sort_by=' + this.value"
            ),
            cls="flex items-center"
        ),
        # Result count
        Span(f"{len(photos)} photos", cls="text-sm text-slate-500 ml-auto"),
        cls="flex flex-wrap items-center gap-4 bg-slate-800 rounded-lg p-3 border border-slate-700 mb-4"
    )

    # Photo grid
    photo_cards = []
    for photo in photos:
        # Face avatars for identified people
        face_avatars = []
        for i, face in enumerate(photo["identified_faces"][:3]):
            crop_file = f"{face['face_id']}.jpg"
            if crop_file in crop_files:
                face_avatars.append(
                    Div(
                        Img(
                            src=storage.get_crop_url_by_filename(crop_file),
                            cls="w-full h-full object-cover",
                            title=face["name"]
                        ),
                        cls="w-6 h-6 rounded-full border-2 border-slate-800 overflow-hidden",
                        style=f"margin-left: {-4 if i > 0 else 0}px; z-index: {10-i};"
                    )
                )

        if photo["identified_count"] > 3:
            face_avatars.append(
                Div(
                    f"+{photo['identified_count'] - 3}",
                    cls="w-6 h-6 rounded-full border-2 border-slate-800 bg-slate-700 "
                        "flex items-center justify-center text-xs text-slate-300",
                    style="margin-left: -4px;"
                )
            )

        card = Div(
            # Photo thumbnail
            Div(
                Img(
                    src=photo_url(photo["filename"]),
                    cls="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300",
                    loading="lazy"
                ),
                # Face count badge
                Div(
                    f"{photo['face_count']} faces",
                    cls="absolute top-2 right-2 bg-black/70 text-white text-xs font-data "
                        "px-2 py-1 rounded-full backdrop-blur-sm"
                ),
                # Identified faces indicator
                Div(
                    *face_avatars,
                    cls="absolute bottom-2 left-2 flex"
                ) if face_avatars else None,
                cls="aspect-[4/3] overflow-hidden relative"
            ),
            # Photo info
            Div(
                P(photo["filename"], cls="text-sm text-white truncate font-data"),
                P(
                    f"\U0001F4C1 {photo['source']}",
                    cls="text-xs text-slate-500 truncate mt-0.5"
                ) if photo["source"] else None,
                cls="p-3"
            ),
            cls="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden "
                "hover:border-slate-500 transition-colors cursor-pointer group",
            hx_get=f"/photo/{photo['photo_id']}/partial",
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            # Show modal on load
            **{"_": "on htmx:afterOnLoad remove .hidden from #photo-modal"}
        )
        photo_cards.append(card)

    # Photo grid layout
    grid = Div(
        *photo_cards,
        cls="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"
    )

    return Div(
        section_header("Photos", subtitle),
        filter_bar,
        grid if photo_cards else Div(
            "No photos found." + (" Clear filter to see all." if filter_source else ""),
            cls="text-center py-12 text-slate-400"
        ),
        cls="space-y-6"
    )


def get_next_focus_card(exclude_id: str = None):
    """
    Get the next identity card for focus mode review.

    Returns an expanded identity card for the top priority item in to_review,
    or an empty state if no items remain.

    IMPORTANT: This must use the same sorting as render_to_review_section to ensure
    the "Up Next" queue matches what appears after an action.
    """
    registry = load_registry()
    crop_files = get_crop_files()

    # Get all to_review items
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    to_review = inbox + proposed

    # Filter out the just-actioned item
    if exclude_id:
        to_review = [i for i in to_review if i["identity_id"] != exclude_id]

    # Sort by priority: PRIMARY = face count (desc), SECONDARY = created_at (desc, for tie-breaking)
    # This matches the sorting in render_to_review_section which receives to_review pre-sorted by created_at
    # and then applies a stable sort by face count.
    to_review.sort(key=lambda x: x.get("created_at", ""), reverse=True)  # Secondary: by date
    to_review.sort(
        key=lambda x: len(x.get("anchor_ids", []) + x.get("candidate_ids", [])),
        reverse=True
    )  # Primary: by face count (stable sort preserves date order for ties)

    if to_review:
        return identity_card_expanded(to_review[0], crop_files)
    else:
        # Empty state
        return Div(
            Div("🎉", cls="text-4xl mb-4"),
            H3("All caught up!", cls="text-lg font-medium text-white"),
            P("No more items to review.", cls="text-slate-400 mt-1"),
            A(
                "Upload more photos →",
                href="/upload",
                cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium"
            ),
            cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-12 text-center",
            id="focus-card"
        )


def upload_area(existing_sources: list[str] = None) -> Div:
    """
    Drag-and-drop file upload area with source/collection field.
    UX Intent: Easy bulk ingestion into inbox with provenance tracking.

    Args:
        existing_sources: List of existing source labels for autocomplete
    """
    if existing_sources is None:
        existing_sources = []

    return Div(
        # Source/Collection input field
        Div(
            Label(
                "Collection / Source",
                cls="block text-sm font-medium text-slate-300 mb-2"
            ),
            Input(
                type="text",
                name="source",
                id="upload-source",
                placeholder="e.g., Betty Capeluto Miami Collection, Ancestry, Newspapers.com",
                list="source-suggestions",
                cls="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg "
                    "text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 "
                    "focus:border-transparent"
            ),
            Datalist(
                *[Option(value=s) for s in existing_sources],
                id="source-suggestions"
            ) if existing_sources else None,
            P(
                "Where did these photos come from? This helps track provenance.",
                cls="text-xs text-slate-500 mt-1"
            ),
            cls="mb-4"
        ),
        # File upload area
        Form(
            Div(
                Span("\u2191", cls="text-4xl text-slate-500"),
                P("Drop photos here or click to upload (multiple allowed)", cls="text-slate-400 mt-2"),
                P("Faces will be added to your Inbox for review", cls="text-xs text-slate-500 mt-1"),
                cls="text-center py-8"
            ),
            Input(
                type="file",
                name="files",
                accept="image/*,.zip",
                multiple=True,
                cls="absolute inset-0 opacity-0 cursor-pointer",
                hx_post="/upload",
                hx_encoding="multipart/form-data",
                hx_target="#upload-status",
                hx_swap="innerHTML",
                hx_include="#upload-source",  # Include source field with upload
            ),
            cls="relative",
            enctype="multipart/form-data",
        ),
        Div(id="upload-status", cls="mt-2"),
        cls="border-2 border-dashed border-slate-600 rounded-lg p-4 hover:border-slate-500 hover:bg-slate-800 transition-colors mb-4",
    )


def inbox_badge(count: int) -> A:
    """
    Inbox badge showing count of items awaiting review.
    """
    if count == 0:
        return A(
            Span("\U0001F4E5", cls="mr-2"),
            "Inbox",
            Span("(0)", cls="text-slate-500 ml-1"),
            href="#inbox-lane",
            cls="text-slate-400 hover:text-slate-300 text-sm"
        )
    return A(
        Span("\U0001F4E5", cls="mr-2"),
        "Inbox",
        Span(
            f"({count})",
            cls="bg-blue-600 text-white text-xs px-1.5 py-0.5 rounded-full ml-1"
        ),
        href="#inbox-lane",
        cls="text-slate-300 hover:text-blue-400 text-sm font-medium"
    )


def review_action_buttons(identity_id: str, state: str, is_admin: bool = True) -> Div:
    """
    Unified action buttons based on identity state.
    Only rendered for admin users.
    """
    if not is_admin:
        return Div()  # No buttons for non-admins

    buttons = []

    # Confirm button - available for reviewable and skipped states
    if state in ("INBOX", "PROPOSED", "SKIPPED"):
        # Use different endpoint for INBOX vs PROPOSED/SKIPPED
        confirm_url = f"/inbox/{identity_id}/confirm" if state == "INBOX" else f"/confirm/{identity_id}"
        buttons.append(Button(
            "\u2713 Confirm",
            cls="px-3 py-1.5 text-sm font-bold bg-emerald-600 text-white rounded hover:bg-emerald-700 transition-colors",
            hx_post=confirm_url,
            hx_target=f"#identity-{identity_id}",
            hx_swap="outerHTML",
            hx_indicator=f"#loading-{identity_id}",
            aria_label="Confirm this identity",
            type="button",
        ))

    # Skip button - available for reviewable states only
    if state in ("INBOX", "PROPOSED"):
        buttons.append(Button(
            "\u23f8 Skip",
            cls="px-3 py-1.5 text-sm font-bold bg-amber-500 text-white rounded hover:bg-amber-600 transition-colors",
            hx_post=f"/identity/{identity_id}/skip",
            hx_target=f"#identity-{identity_id}",
            hx_swap="outerHTML",
            hx_indicator=f"#loading-{identity_id}",
            aria_label="Skip for later",
            type="button",
        ))

    # Reject button - available for reviewable and skipped states
    if state in ("INBOX", "PROPOSED", "SKIPPED"):
        # Use different endpoint for INBOX vs PROPOSED/SKIPPED
        reject_url = f"/inbox/{identity_id}/reject" if state == "INBOX" else f"/reject/{identity_id}"
        buttons.append(Button(
            "\u2717 Reject",
            cls="px-3 py-1.5 text-sm font-bold border-2 border-red-500 text-red-500 rounded hover:bg-red-500/20 transition-colors",
            hx_post=reject_url,
            hx_target=f"#identity-{identity_id}",
            hx_swap="outerHTML",
            hx_indicator=f"#loading-{identity_id}",
            aria_label="Reject this identity",
            type="button",
        ))

    # Reset button - available for terminal states
    if state in ("CONFIRMED", "SKIPPED", "REJECTED", "CONTESTED"):
        buttons.append(Button(
            "\u21a9 Return to Inbox",
            cls="px-3 py-1.5 text-sm font-bold border border-slate-500 text-slate-400 rounded hover:bg-slate-700 transition-colors",
            hx_post=f"/identity/{identity_id}/reset",
            hx_target=f"#identity-{identity_id}",
            hx_swap="outerHTML",
            hx_indicator=f"#loading-{identity_id}",
            aria_label="Return to Inbox",
            type="button",
        ))

    # Loading indicator
    buttons.append(Span(
        "...",
        id=f"loading-{identity_id}",
        cls="htmx-indicator ml-2 text-slate-400 animate-pulse",
        aria_hidden="true",
    ))

    return Div(
        *buttons,
        cls="flex gap-2 items-center flex-wrap mt-3",
    )


def state_badge(state: str) -> Span:
    """
    Render state as a colored badge.
    UX Intent: Instant state recognition via color coding.
    """
    colors = {
        "INBOX": "bg-blue-600 text-white",
        "CONFIRMED": "bg-emerald-600 text-white",
        "PROPOSED": "bg-amber-500 text-white",
        "CONTESTED": "bg-red-600 text-white",
        "REJECTED": "bg-rose-700 text-white",
        "SKIPPED": "bg-stone-500 text-white",
    }
    return Span(
        state,
        cls=f"text-xs font-bold px-2 py-1 rounded {colors.get(state, 'bg-gray-500 text-white')}"
    )


def era_badge(era: str) -> Span:
    """
    Render era classification as a subtle badge.
    UX Intent: Temporal context without visual dominance.
    """
    if not era:
        return None
    return Span(
        era,
        cls="absolute top-2 right-2 bg-stone-700/80 text-white text-xs px-2 py-1 font-mono"
    )


def face_card(
    face_id: str,
    crop_url: str,
    quality: float = None,
    era: str = None,
    identity_id: str = None,
    photo_id: str = None,
    show_actions: bool = False,
    show_detach: bool = False,
) -> Div:
    """
    Single face card with optional action buttons.
    UX Intent: Face-first display with metadata secondary.

    Args:
        face_id: Canonical face identifier (for alt text)
        crop_url: Resolved URL path to the crop image (from backend)
        quality: Quality score (extracted from URL if not provided)
        era: Era classification for badge display
        identity_id: Parent identity ID
        photo_id: Photo ID for "View Photo" button
        show_actions: Whether to show action buttons
        show_detach: Whether to show "Detach" button (only when identity has > 1 face)
    """
    if quality is None:
        # Extract quality from URL: /crops/{name}_{quality}_{idx}.jpg
        quality = parse_quality_from_filename(crop_url)

    # View Photo button (only if photo_id is available)
    view_photo_btn = None
    if photo_id:
        view_photo_btn = Button(
            "View Photo",
            cls="text-xs text-slate-400 hover:text-slate-300 underline mt-1",
            hx_get=f"/photo/{photo_id}/partial?face={face_id}",
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            # Show the modal when clicked
            **{"_": "on click remove .hidden from #photo-modal"},
            type="button",
        )

    # Detach button (only if show_detach is True)
    detach_btn = None
    if show_detach:
        # Generate safe DOM ID for targeting
        safe_dom_id = make_css_id(face_id)

        detach_btn = Button(
            "Detach",
            cls="text-xs text-red-400 hover:text-red-300 underline mt-1 ml-2",
            # Fix: URL Encode the face_id so spaces don't break the path
            hx_post=f"/api/face/{quote(face_id)}/detach",
            # Fix: Use the safe CSS ID selector
            hx_target=f"#{safe_dom_id}",
            hx_swap="outerHTML",
            hx_confirm="Detach this face into a new identity?",
            type="button",
        )

    return Div(
        # Image container with era badge
        Div(
            Img(
                src=crop_url,
                alt=face_id,
                cls="w-full h-auto sepia-[.3] hover:sepia-0 transition-all duration-300"
            ),
            era_badge(era) if era else None,
            cls="relative border border-slate-600 bg-slate-700"
        ),
        # Metadata and actions
        Div(
            P(
                f"Quality: {quality:.2f}",
                cls="text-xs font-data text-slate-400"
            ),
            Div(
                view_photo_btn,
                detach_btn,
                cls="flex items-center"
            ) if view_photo_btn or detach_btn else None,
            cls="mt-2"
        ),
        cls="bg-slate-700 border border-slate-600 p-2 rounded shadow-md hover:shadow-lg transition-shadow",
        # Fix: Apply the safe ID to the container
        id=make_css_id(face_id)
    )


def neighbor_card(neighbor: dict, target_identity_id: str, crop_files: set) -> Div:
    neighbor_id = neighbor["identity_id"]
    # UI BOUNDARY: sanitize name for safe rendering
    name = ensure_utf8_display(neighbor["name"])
    # Get values directly (no more negative scaling)
    distance = neighbor["distance"]
    percentile = neighbor.get("percentile", 1.0)

    can_merge = neighbor["can_merge"]
    face_count = neighbor.get("face_count", 0)

    # --- CALIBRATION: THE LEON STANDARD (ADR 007) ---
    # Thresholds from core.config (derived from forensic evaluation)
    if distance < MATCH_THRESHOLD_HIGH:
        similarity_class = "bg-emerald-500/20 text-emerald-400"
        similarity_label = "High"
    elif distance < MATCH_THRESHOLD_MEDIUM:
        similarity_class = "bg-amber-500/20 text-amber-400"
        similarity_label = "Medium"
    else:
        similarity_class = "bg-slate-600 text-slate-400"
        similarity_label = "Low"
    # -----------------------------------------------

    # Merge button
    merge_btn = Button("Merge", cls="px-3 py-1 text-sm font-bold bg-blue-600 text-white rounded hover:bg-blue-500",
                       hx_post=f"/api/identity/{target_identity_id}/merge/{neighbor_id}", hx_target=f"#identity-{target_identity_id}",
                       hx_swap="outerHTML", hx_confirm=f"Merge '{name}'? This cannot be undone.") if can_merge else \
                Button("Blocked", cls="px-3 py-1 text-sm font-bold bg-slate-600 text-slate-400 rounded cursor-not-allowed", disabled=True, title=neighbor.get("merge_blocked_reason_display"))

    # Thumbnail logic
    thumbnail_img = Div(cls="w-12 h-12 bg-slate-600 rounded")
    anchor_face_ids = neighbor.get("anchor_face_ids", []) + neighbor.get("candidate_face_ids", [])
    for fid in anchor_face_ids:
        crop_url = resolve_face_image_url(fid, crop_files)
        if crop_url:
            thumbnail_img = Img(src=crop_url, alt=name, cls="w-12 h-12 object-cover rounded border border-slate-600")
            break

    # Navigation script: try to scroll if element exists, otherwise navigate to browse mode
    nav_script = f"on click set target to #identity-{neighbor_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-blue-400 to target then wait 1.5s then remove .ring-2 .ring-blue-400 from target else go to url '/?section=to_review&view=browse#identity-{neighbor_id}'"

    return Div(
        Div(A(thumbnail_img, href=f"/?section=to_review&view=browse#identity-{neighbor_id}", cls="flex-shrink-0 cursor-pointer hover:opacity-80", **{"_": nav_script}),
            Div(Div(A(name, href=f"/?section=to_review&view=browse#identity-{neighbor_id}", cls="font-medium text-slate-200 truncate hover:text-blue-400 hover:underline cursor-pointer", **{"_": nav_script}),
                    Span(similarity_label, cls=f"text-xs px-2 py-0.5 rounded ml-2 {similarity_class}"), cls="flex items-center"),
                # EXPLAINABILITY: We show both. Distance tells you "Is it him?", Percentile tells you "Is it the best we have?"
                Div(Span(f"Dist: {distance:.2f} (p={percentile:.2f})", cls="text-xs font-data text-slate-400 ml-2 bg-slate-700 px-1 rounded"), cls="flex items-center"),
                cls="flex-1 min-w-0 ml-3"),
            Div(merge_btn, Button("Not Same", cls="px-2 py-1 text-xs font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20",
                                  hx_post=f"/api/identity/{target_identity_id}/reject/{neighbor_id}", hx_target=f"#neighbor-{neighbor_id}", hx_swap="outerHTML"),
                cls="flex items-center gap-2 flex-shrink-0 ml-2"),
            cls="flex items-center"),
        id=f"neighbor-{neighbor_id}", cls="p-3 bg-slate-700 border border-slate-600 rounded shadow-md mb-2 hover:shadow-lg"
    )

def search_result_card(result: dict, target_identity_id: str, crop_files: set) -> Div:
    """
    Card for a manual search result.
    Similar styling to neighbor_card but simpler (no distance/percentile).
    """
    result_id = result["identity_id"]
    # UI BOUNDARY: sanitize name for safe rendering
    raw_name = ensure_utf8_display(result["name"])
    name = raw_name or f"Identity {result_id[:8]}..."
    face_count = result.get("face_count", 0)
    preview_face_id = result.get("preview_face_id")

    # Thumbnail from preview_face_id
    thumbnail_img = Div(cls="w-10 h-10 bg-slate-600 rounded")
    if preview_face_id:
        crop_url = resolve_face_image_url(preview_face_id, crop_files)
        if crop_url:
            thumbnail_img = Img(
                src=crop_url,
                alt=name,
                cls="w-10 h-10 object-cover rounded border border-slate-600"
            )

    # Merge button with manual_search source
    merge_btn = Button(
        "Merge",
        cls="px-2 py-1 text-xs font-bold bg-blue-600 text-white rounded hover:bg-blue-500",
        hx_post=f"/api/identity/{target_identity_id}/merge/{result_id}?source=manual_search",
        hx_target=f"#identity-{target_identity_id}",
        hx_swap="outerHTML",
        hx_confirm=f"Merge '{name}'? This cannot be undone.",
    )

    # Navigation hyperscript (same as neighbor_card)
    nav_script = f"on click set target to #identity-{result_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-blue-400 to target then wait 1.5s then remove .ring-2 .ring-blue-400 from target"

    return Div(
        Div(
            A(thumbnail_img, href=f"#identity-{result_id}", cls="flex-shrink-0 cursor-pointer hover:opacity-80", **{"_": nav_script}),
            Div(
                A(name, href=f"#identity-{result_id}", cls="font-medium text-slate-200 truncate text-sm hover:text-blue-400 hover:underline cursor-pointer", **{"_": nav_script}),
                Span(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-xs text-slate-400 ml-2"),
                cls="flex items-center ml-2 flex-1 min-w-0"
            ),
            merge_btn,
            cls="flex items-center"
        ),
        id=f"search-result-{result_id}",
        cls="p-2 bg-slate-700 border border-slate-600 rounded shadow-md mb-2 hover:shadow-lg"
    )


def search_results_panel(results: list, target_identity_id: str, crop_files: set) -> Div:
    """Panel showing manual search results."""
    if not results:
        return Div(
            P("No matching identities found.", cls="text-slate-400 italic text-sm"),
            id=f"search-results-{target_identity_id}"
        )

    cards = [search_result_card(r, target_identity_id, crop_files) for r in results]
    return Div(
        *cards,
        id=f"search-results-{target_identity_id}"
    )


def manual_search_section(identity_id: str) -> Div:
    """
    Manual search input and results container.
    Positioned in neighbors sidebar after Load More, before Rejected section.
    """
    return Div(
        H5("Manual Search", cls="text-sm font-semibold text-slate-300 mb-2"),
        Input(
            type="text",
            name="q",
            placeholder="Search by name...",
            cls="w-full px-3 py-2 text-sm bg-slate-800 border border-slate-600 text-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent placeholder-slate-500",
            hx_get=f"/api/identity/{identity_id}/search",
            hx_trigger="keyup changed delay:300ms",
            hx_target=f"#search-results-{identity_id}",
            hx_include="this",
        ),
        Div(id=f"search-results-{identity_id}", cls="mt-2"),
        cls="mt-4 pt-3 border-t border-slate-600"
    )


def neighbors_sidebar(identity_id: str, neighbors: list, crop_files: set, offset: int = 0, has_more: bool = False, rejected_count: int = 0) -> Div:
    close_btn = Button("Close", cls="text-sm text-slate-400 hover:text-slate-300", hx_get=f"/api/identity/{identity_id}/neighbors/close", hx_target=f"#neighbors-{identity_id}", hx_swap="innerHTML")
    if not neighbors: return Div(Div(P("No similar identities.", cls="text-slate-400 italic"), close_btn, cls="flex items-center justify-between"), manual_search_section(identity_id), cls="neighbors-sidebar p-4 bg-slate-700 rounded border border-slate-600")

    cards = [neighbor_card(n, identity_id, crop_files) for n in neighbors]
    load_more = Button("Load More", cls="w-full text-sm text-indigo-400 hover:text-indigo-300 py-2 border border-indigo-500/50 rounded hover:bg-indigo-500/20",
                       hx_get=f"/api/identity/{identity_id}/neighbors?offset={offset+len(neighbors)}", hx_target=f"#neighbors-{identity_id}", hx_swap="innerHTML") if has_more else None

    # Manual search section - between Load More and Rejected
    manual_search = manual_search_section(identity_id)

    rejected = Div(Div(Span(f"{rejected_count} hidden matches", cls="text-xs text-slate-400 italic"),
                       Button("Review", cls="text-xs text-indigo-400 hover:text-indigo-300 ml-2", hx_get=f"/api/identity/{identity_id}/rejected", hx_target=f"#rejected-list-{identity_id}", hx_swap="innerHTML"),
                       cls="flex items-center justify-between"), Div(id=f"rejected-list-{identity_id}"), cls="mt-4 pt-3 border-t border-slate-600") if rejected_count > 0 else None

    return Div(Div(H4("Similar Identities", cls="text-lg font-serif font-bold text-white"), close_btn, cls="flex items-center justify-between mb-3"),
               Div(*cards), Div(load_more, cls="mt-3") if load_more else None, manual_search, rejected, cls="neighbors-sidebar p-4 bg-slate-700 rounded border border-slate-600")


def name_display(identity_id: str, name: str, is_admin: bool = True) -> Div:
    """
    Identity name display with edit button (admin only).
    Returns the name header component that can be swapped for inline editing.
    """
    # UI BOUNDARY: sanitize name for safe rendering
    safe_name = ensure_utf8_display(name)
    display_name = safe_name or f"Identity {identity_id[:8]}..."
    edit_btn = Button(
        "Edit",
        hx_get=f"/api/identity/{identity_id}/rename-form",
        hx_target=f"#name-{identity_id}",
        hx_swap="outerHTML",
        cls="ml-2 text-xs text-slate-400 hover:text-slate-300 underline",
        type="button",
    ) if is_admin else None
    return Div(
        H3(display_name, cls="text-lg font-serif font-bold text-white"),
        edit_btn,
        id=f"name-{identity_id}",
        cls="flex items-center"
    )


def identity_card(
    identity: dict,
    crop_files: set,
    lane_color: str = "stone",
    show_actions: bool = False,
    is_admin: bool = True,
) -> Div:
    """
    Identity group card showing all faces (anchors + candidates).
    UX Intent: Group context with individual face visibility.
    Action buttons only shown for admin users.
    """
    identity_id = identity["identity_id"]
    # UI BOUNDARY: sanitize name for safe rendering
    raw_name = ensure_utf8_display(identity.get("name"))
    name = raw_name or f"Identity {identity_id[:8]}..."
    state = identity["state"]

    # Combine anchors (confirmed) and candidates (proposed) for display
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])

    # Show detach button only if identity has more than one face AND user is admin
    can_detach = len(all_face_ids) > 1 and is_admin

    # Build face cards for each face
    face_cards = []
    for face_entry in all_face_ids:
        if isinstance(face_entry, str):
            face_id = face_entry
            era = None
        else:
            face_id = face_entry.get("face_id", "")
            era = face_entry.get("era_bin")

        crop_url = resolve_face_image_url(face_id, crop_files)
        if crop_url:
            # Look up photo_id for "View Photo" button
            photo_id = get_photo_id_for_face(face_id)
            face_cards.append(face_card(
                face_id=face_id,
                crop_url=crop_url,
                era=era,
                identity_id=identity_id,
                photo_id=photo_id,
                show_detach=can_detach,
            ))
        else:
            # Placeholder for faces with missing crop files
            face_cards.append(Div(
                Div(
                    Span("?", cls="text-4xl text-slate-500"),
                    cls="w-full aspect-square bg-slate-700 border border-slate-600 flex items-center justify-center"
                ),
                P("Image unavailable", cls="text-xs text-slate-400 mt-1"),
                P(f"ID: {face_id[:12]}...", cls="text-xs font-data text-slate-500"),
                cls="face-card",
                id=make_css_id(face_id),
            ))

    if not face_cards:
        return None

    border_colors = {
        "blue": "border-l-blue-500",
        "emerald": "border-l-emerald-500",
        "amber": "border-l-amber-500",
        "red": "border-l-red-500",
        "stone": "border-l-stone-400",
        "rose": "border-l-rose-500",
    }

    # Sort dropdown for face ordering
    sort_dropdown = Select(
        Option("Sort by Date", value="date", selected=True),
        Option("Sort by Outlier", value="outlier"),
        cls="text-xs border border-slate-600 bg-slate-700 text-slate-300 rounded px-2 py-1",
        hx_get=f"/api/identity/{identity_id}/faces",
        hx_target=f"#faces-{identity_id}",
        hx_swap="innerHTML",
        name="sort",
        hx_trigger="change",
    )

    # Find Similar button (loads neighbors via HTMX)
    find_similar_btn = Button(
        "Find Similar",
        cls="text-sm text-indigo-400 hover:text-indigo-300 underline",
        hx_get=f"/api/identity/{identity_id}/neighbors",
        hx_target=f"#neighbors-{identity_id}",
        hx_swap="innerHTML",
        hx_indicator=f"#neighbors-loading-{identity_id}",
        type="button",
    )

    # Neighbors container (populated by HTMX)
    neighbors_container = Div(
        Span(
            "Loading...",
            id=f"neighbors-loading-{identity_id}",
            cls="htmx-indicator text-slate-400 text-sm",
        ),
        id=f"neighbors-{identity_id}",
        cls="mt-4"
    )

    return Div(
        # Header with name, state, and controls
        Div(
            Div(
                name_display(identity_id, identity.get("name"), is_admin=is_admin),
                state_badge(state),
                Span(
                    f"{len(face_cards)} face{'s' if len(face_cards) != 1 else ''}",
                    cls="text-xs text-slate-400 ml-2"
                ),
                cls="flex items-center gap-3"
            ),
            Div(
                sort_dropdown,
                find_similar_btn,
                cls="flex items-center gap-3"
            ),
            cls="flex items-center justify-between mb-3"
        ),
        # Face grid
        Div(
            *face_cards,
            cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3",
            id=f"faces-{identity_id}",
        ),
        # Action buttons based on state (admin only)
        review_action_buttons(identity_id, state, is_admin=is_admin),
        # Neighbors container (shown when "Find Similar" is clicked)
        neighbors_container,
        cls=f"identity-card bg-slate-800 border border-slate-700 border-l-4 {border_colors.get(lane_color, '')} p-4 rounded-r shadow-lg mb-4",
        id=f"identity-{identity_id}"
    )


def photo_modal() -> Div:
    """
    Modal container for photo context viewer.
    Hidden by default, shown via HTMX when "View Photo" is clicked.

    Z-index hierarchy:
    - Modal container: z-[9999] (above everything including toasts at z-50)
    - Backdrop: absolute, no z-index (first child, renders behind content)
    - Content: relative, no z-index (second child, renders above backdrop)
    """
    return Div(
        # Backdrop - absolute within the fixed parent, click to close
        Div(
            cls="absolute inset-0 bg-black/80",
            **{"_": "on click add .hidden to #photo-modal"},
        ),
        # Modal content - relative positioning to sit above backdrop
        Div(
            # Header with close button
            Div(
                H2("Photo Context", cls="text-xl font-serif font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click add .hidden to #photo-modal"},
                    type="button",
                    aria_label="Close modal",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700"
            ),
            # Content area (populated by HTMX)
            Div(
                P("Loading...", cls="text-slate-400 text-center py-8"),
                id="photo-modal-content",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-auto p-6 relative border border-slate-700"
        ),
        id="photo-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[9999]"
    )


def login_modal() -> Div:
    """Login modal for unauthenticated HTMX action attempts.
    Shown by htmx:beforeSwap handler when server returns 401."""
    google_url = get_oauth_url("google")
    return Div(
        Div(cls="absolute inset-0 bg-black/80",
            **{"_": "on click add .hidden to #login-modal"}),
        Div(
            Div(
                H2("Sign in to continue", cls="text-xl font-bold text-white"),
                Button("X", cls="text-slate-400 hover:text-white text-xl font-bold",
                       **{"_": "on click add .hidden to #login-modal"},
                       type="button", aria_label="Close"),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700"
            ),
            P("Sign in to confirm identities and make changes.", cls="text-slate-400 mb-6 text-sm"),
            Form(
                Div(
                    Label("Email", fr="modal-email", cls="block text-sm mb-1 text-slate-300"),
                    Input(type="email", name="email", id="modal-email", required=True,
                          cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600"),
                    cls="mb-4"
                ),
                Div(
                    Label("Password", fr="modal-password", cls="block text-sm mb-1 text-slate-300"),
                    Input(type="password", name="password", id="modal-password", required=True,
                          cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600"),
                    cls="mb-4"
                ),
                Button("Sign In", type="submit",
                       cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"),
                Div(id="login-modal-error", cls="text-red-400 text-sm mt-2"),
                hx_post="/login/modal", hx_target="#login-modal-error", hx_swap="innerHTML",
            ),
            # Google OAuth divider + button
            Div(
                Div(cls="flex-grow border-t border-slate-600"),
                Span("or", cls="px-4 text-slate-500 text-sm"),
                Div(cls="flex-grow border-t border-slate-600"),
                cls="flex items-center my-4"
            ) if google_url else None,
            A(
                NotStr('<svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>'),
                Span("Sign in with Google"),
                href=google_url or "#",
                style="display: flex; align-items: center; gap: 12px; padding: 0 16px; height: 40px; "
                      "background: white; border: 1px solid #dadce0; border-radius: 4px; cursor: pointer; "
                      "font-family: 'Roboto', Arial, sans-serif; font-size: 14px; color: #3c4043; "
                      "font-weight: 500; text-decoration: none; justify-content: center; width: 100%;",
            ) if google_url else None,
            P(
                A("Forgot password?", href="/forgot-password", cls="text-blue-400 hover:underline"),
                cls="mt-4 text-center text-sm"
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md p-8 relative border border-slate-700"
        ),
        id="login-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[9998]"
    )


def confirm_modal() -> Div:
    """Styled confirmation modal replacing native browser confirm().
    Shown by htmx:confirm event handler."""
    return Div(
        Div(cls="absolute inset-0 bg-black/80",
            **{"_": "on click add .hidden to #confirm-modal"}),
        Div(
            P("", id="confirm-modal-message", cls="text-white text-lg mb-6"),
            Div(
                Button("Cancel", id="confirm-modal-no", type="button",
                       cls="px-4 py-2 bg-slate-600 text-white rounded hover:bg-slate-500"),
                Button("Confirm", id="confirm-modal-yes", type="button",
                       cls="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-500 font-bold"),
                cls="flex justify-end gap-3"
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md p-6 relative border border-slate-700"
        ),
        id="confirm-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[9997]"
    )


def lane_section(
    title: str,
    identities: list,
    crop_files: set,
    color: str,
    icon: str,
    show_actions: bool = False,
    lane_id: str = None,
) -> Div:
    """
    A swimlane for a specific identity state.
    UX Intent: Clear separation of epistemic states.
    """
    cards = []
    for identity in identities:
        card = identity_card(identity, crop_files, lane_color=color, show_actions=show_actions)
        if card:
            cards.append(card)

    bg_colors = {
        "blue": "bg-blue-900/20",
        "emerald": "bg-emerald-900/20",
        "amber": "bg-amber-900/20",
        "red": "bg-red-900/20",
        "stone": "bg-slate-800/50",
        "rose": "bg-rose-900/20",
    }

    # Fix: Always render the container ID even if empty, so OOB swaps have a target.
    content_area = Div(*cards, id=lane_id, cls="min-h-[50px]") if cards else Div(
        P(
            f"No {title.lower()} identities",
            cls="text-slate-400 italic text-center py-8"
        ),
        id=lane_id,
        cls="min-h-[50px]"
    )

    return Div(
        # Lane header
        Div(
            Span(icon, cls="text-2xl"),
            H2(title, cls="text-xl font-serif font-bold text-white"),
            Span(
                f"({len(cards)})",
                cls="text-sm text-slate-400"
            ),
            cls="flex items-center gap-3 mb-4 pb-2 border-b border-slate-700"
        ),
        # Cards or empty state
        content_area,
        cls=f"mb-8 p-4 rounded {bg_colors.get(color, '')}"
    )


# =============================================================================
# ROUTES - HEALTH CHECK
# =============================================================================


@rt("/health")
def health():
    """Health check endpoint for Railway deployment."""
    registry = load_registry()

    # Count photos from photo_index.json
    photo_count = 0
    photo_index_path = data_path / "photo_index.json"
    if photo_index_path.exists():
        with open(photo_index_path) as f:
            index = json.load(f)
            photo_count = len(index.get("photos", {}))

    return {
        "status": "ok",
        "identities": len(registry.list_identities()),
        "photos": photo_count,
        "processing_enabled": PROCESSING_ENABLED,
    }


# =============================================================================
# ROUTES - PHASE 2: TEACH MODE
# =============================================================================

def _compute_landing_stats() -> dict:
    """Compute live stats for the landing page."""
    registry = load_registry()
    _build_caches()
    all_identities = registry.list_identities()
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    total_faces = sum(
        len(i.get("anchor_ids", [])) + len(i.get("candidate_ids", []))
        for i in all_identities
    )
    needs_help = sum(
        len(i.get("anchor_ids", [])) + len(i.get("candidate_ids", []))
        for i in inbox + proposed
    )
    return {
        "photo_count": len(_photo_cache) if _photo_cache else 0,
        "named_count": len(confirmed),
        "total_faces": total_faces,
        "needs_help": needs_help,
    }


def _get_featured_photos(limit: int = 8) -> list:
    """Pick photos that have confirmed/named identities for the landing page hero."""
    registry = load_registry()
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    _build_caches()
    if not _photo_cache:
        return []
    # Collect photo IDs that contain faces from confirmed identities
    confirmed_face_ids = set()
    for identity in confirmed:
        confirmed_face_ids.update(identity.get("anchor_ids", []))
        confirmed_face_ids.update(identity.get("candidate_ids", []))
    featured_photo_ids = []
    for photo_id, photo_data in _photo_cache.items():
        for face in photo_data.get("faces", []):
            if face.get("face_id") in confirmed_face_ids:
                featured_photo_ids.append(photo_id)
                break
    # If not enough confirmed photos, fill with any photos
    if len(featured_photo_ids) < limit:
        for photo_id in _photo_cache:
            if photo_id not in featured_photo_ids:
                featured_photo_ids.append(photo_id)
                if len(featured_photo_ids) >= limit:
                    break
    return [
        {"id": pid, "url": photo_url(_photo_cache[pid]["filename"])}
        for pid in featured_photo_ids[:limit]
        if pid in _photo_cache
    ]


def landing_page(user, stats, featured_photos):
    """Render the public landing page for the family heritage archive."""
    auth_enabled = is_auth_enabled()
    logged_in = user is not None

    # Hero photo grid
    hero_images = [
        Img(
            src=p["url"], alt="Rhodes-Capeluto family photo",
            loading="lazy",
            cls="w-full h-full object-cover"
        )
        for p in featured_photos
    ]

    # CTA buttons based on auth state
    if logged_in:
        cta_buttons = Div(
            A("Continue Reviewing", href="/?section=to_review",
              cls="inline-block px-8 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-500 transition-colors text-lg"),
            A("Browse Photos", href="/?section=photos",
              cls="inline-block px-8 py-3 border border-slate-500 text-slate-300 font-semibold rounded-lg hover:bg-slate-700 transition-colors text-lg ml-4"),
            cls="mt-8 flex flex-wrap gap-4 justify-center"
        )
    elif auth_enabled:
        cta_buttons = Div(
            A("Start Exploring", href="/?section=photos",
              cls="inline-block px-8 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-500 transition-colors text-lg"),
            A("Join the Project", href="/signup",
              cls="inline-block px-8 py-3 border border-slate-500 text-slate-300 font-semibold rounded-lg hover:bg-slate-700 transition-colors text-lg ml-4"),
            cls="mt-8 flex flex-wrap gap-4 justify-center"
        )
    else:
        cta_buttons = Div(
            A("Start Exploring", href="/?section=photos",
              cls="inline-block px-8 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-500 transition-colors text-lg"),
            cls="mt-8 flex flex-wrap gap-4 justify-center"
        )

    # Navigation bar
    nav_items = [
        A("Photos", href="/?section=photos", cls="text-slate-300 hover:text-white transition-colors"),
        A("People", href="/?section=confirmed", cls="text-slate-300 hover:text-white transition-colors"),
        A("Help Identify", href="/?section=to_review", cls="text-slate-300 hover:text-white transition-colors"),
    ]
    if auth_enabled and not logged_in:
        nav_items.append(
            A("Sign In", href="/login", cls="text-indigo-400 hover:text-indigo-300 font-medium transition-colors")
        )

    landing_style = Style("""
        html, body { height: 100%; margin: 0; }
        body { background-color: #0f172a; }
        .hero-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            grid-template-rows: repeat(2, 180px);
            gap: 4px;
        }
        @media (max-width: 767px) {
            .hero-grid {
                grid-template-columns: repeat(2, 1fr);
                grid-template-rows: repeat(4, 120px);
            }
        }
        @media (min-width: 768px) and (max-width: 1023px) {
            .hero-grid {
                grid-template-rows: repeat(2, 150px);
            }
        }
        @media (min-width: 1024px) {
            .hero-grid {
                grid-template-rows: repeat(2, 200px);
            }
        }
        .stat-card {
            text-align: center;
            padding: 1.5rem;
        }
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            color: #e2e8f0;
            line-height: 1;
        }
        .stat-label {
            font-size: 0.875rem;
            color: #94a3b8;
            margin-top: 0.5rem;
        }
        @keyframes fade-in {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in { animation: fade-in 0.6s ease-out; }
    """)

    return Title("Rhodesli — Rhodes-Capeluto Family Archive"), landing_style, Div(
        # Navigation
        Nav(
            Div(
                A("Rhodesli", href="/", cls="text-xl font-bold text-white"),
                Div(*nav_items, cls="flex items-center gap-6"),
                cls="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between flex-wrap gap-4"
            ),
            cls="border-b border-slate-800"
        ),
        # Hero section
        Section(
            Div(
                Div(
                    H1("Preserving the faces and stories of the Rhodes-Capeluto family",
                       cls="text-3xl md:text-5xl font-bold text-white leading-tight max-w-3xl mx-auto"),
                    P("A community effort to identify and connect generations of family history through archival photographs.",
                      cls="text-lg text-slate-400 mt-4 max-w-2xl mx-auto"),
                    cta_buttons,
                    cls="text-center py-12 px-6"
                ),
                # Photo mosaic
                Div(*hero_images, cls="hero-grid mt-4 rounded-xl overflow-hidden opacity-90") if hero_images else None,
                cls="max-w-6xl mx-auto"
            ),
            id="hero", cls="pt-8 pb-12"
        ),
        # Stats section
        Section(
            Div(
                Div(
                    Div(str(stats["photo_count"]), cls="stat-number"),
                    Div("photos preserved", cls="stat-label"),
                    cls="stat-card"
                ),
                Div(
                    Div(str(stats["named_count"]), cls="stat-number"),
                    Div("people identified", cls="stat-label"),
                    cls="stat-card"
                ),
                Div(
                    Div(str(stats["total_faces"]), cls="stat-number"),
                    Div("faces detected", cls="stat-label"),
                    cls="stat-card"
                ),
                Div(
                    Div(str(stats["needs_help"]), cls="stat-number"),
                    Div("faces need your help", cls="stat-label"),
                    cls="stat-card"
                ),
                cls="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto"
            ),
            id="stats", cls="py-16 px-6 bg-slate-800/50"
        ),
        # How it works
        Section(
            Div(
                H2("How You Can Help", cls="text-2xl font-bold text-white text-center mb-10"),
                Div(
                    Div(
                        Div("1", cls="w-12 h-12 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xl font-bold mx-auto mb-4"),
                        H3("Browse Photos", cls="text-lg font-semibold text-white mb-2 text-center"),
                        P("Explore archival photographs from family collections spanning generations.",
                          cls="text-slate-400 text-center text-sm"),
                        cls="flex-1 p-6"
                    ),
                    Div(
                        Div("2", cls="w-12 h-12 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xl font-bold mx-auto mb-4"),
                        H3("Identify People", cls="text-lg font-semibold text-white mb-2 text-center"),
                        P("Help name faces our system has detected. Your knowledge preserves family history.",
                          cls="text-slate-400 text-center text-sm"),
                        cls="flex-1 p-6"
                    ),
                    Div(
                        Div("3", cls="w-12 h-12 rounded-full bg-indigo-600 text-white flex items-center justify-center text-xl font-bold mx-auto mb-4"),
                        H3("Connect History", cls="text-lg font-semibold text-white mb-2 text-center"),
                        P("See how family members appear across photos and help piece together our shared story.",
                          cls="text-slate-400 text-center text-sm"),
                        cls="flex-1 p-6"
                    ),
                    cls="grid grid-cols-1 md:grid-cols-3 gap-6"
                ),
                cls="max-w-5xl mx-auto"
            ),
            id="how-it-works", cls="py-16 px-6"
        ),
        # About section
        Section(
            Div(
                H2("About This Project", cls="text-2xl font-bold text-white text-center mb-6"),
                P("Rhodesli is a community project dedicated to preserving the photographic heritage of the Rhodes-Capeluto family. "
                  "Using face recognition technology, we are building a searchable archive that connects faces across generations of photographs. "
                  "Every identification you make helps future generations understand where they came from.",
                  cls="text-slate-400 text-center max-w-3xl mx-auto leading-relaxed"),
                cls="max-w-5xl mx-auto"
            ),
            id="about", cls="py-16 px-6 bg-slate-800/30"
        ),
        # Bottom CTA
        Section(
            Div(
                H2("Ready to explore?", cls="text-2xl font-bold text-white text-center mb-4"),
                P(f"{stats['needs_help']} faces are waiting to be identified.",
                  cls="text-slate-400 text-center mb-8"),
                cta_buttons,
                cls="max-w-3xl mx-auto text-center"
            ),
            id="cta", cls="py-16 px-6"
        ),
        # Footer
        Footer(
            Div(
                P("Rhodesli — Preserving family history, one face at a time.",
                  cls="text-slate-500 text-sm text-center"),
                cls="max-w-6xl mx-auto px-6 py-8"
            ),
            cls="border-t border-slate-800"
        ),
        cls="min-h-screen bg-slate-900"
    )


@rt("/")
def get(section: str = None, view: str = "focus", current: str = None,
        filter_source: str = "", sort_by: str = "newest", sess=None):
    """
    Landing page (no section) or Command Center (with section parameter).
    Public access — anyone can view. Action buttons shown only to admins.
    """
    user = get_current_user(sess or {})

    # If no section specified, show the landing page
    if section is None:
        stats = _compute_landing_stats()
        featured_photos = _get_featured_photos(8)
        return landing_page(user, stats, featured_photos)

    user_is_admin = user.is_admin if user else False

    registry = load_registry()
    crop_files = get_crop_files()

    # Fetch all identity states
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    confirmed_list = registry.list_identities(state=IdentityState.CONFIRMED)
    skipped_list = registry.list_identities(state=IdentityState.SKIPPED)
    rejected = registry.list_identities(state=IdentityState.REJECTED)
    contested = registry.list_identities(state=IdentityState.CONTESTED)

    # Combine into 4 workflow sections
    to_review = inbox + proposed  # Items needing attention
    dismissed = rejected + contested  # Items explicitly dismissed

    # Sort each section
    to_review.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    confirmed_list.sort(key=lambda x: (x.get("name") or "", x.get("updated_at", "")))
    skipped_list.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    dismissed.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    # Get photo count for sidebar
    _build_caches()
    photo_count = len(_photo_cache) if _photo_cache else 0

    # Calculate counts for sidebar
    counts = {
        "to_review": len(to_review),
        "confirmed": len(confirmed_list),
        "skipped": len(skipped_list),
        "rejected": len(dismissed),
        "photos": photo_count,
    }

    # Validate section parameter
    valid_sections = ("to_review", "confirmed", "skipped", "rejected", "photos")
    if section not in valid_sections:
        section = "to_review"

    # Validate view parameter
    if view not in ("focus", "browse"):
        view = "focus"

    # Render the appropriate section
    if section == "to_review":
        main_content = render_to_review_section(to_review, crop_files, view, counts, current_id=current, is_admin=user_is_admin)
    elif section == "confirmed":
        main_content = render_confirmed_section(confirmed_list, crop_files, counts, is_admin=user_is_admin)
    elif section == "skipped":
        main_content = render_skipped_section(skipped_list, crop_files, counts, is_admin=user_is_admin)
    elif section == "photos":
        main_content = render_photos_section(counts, registry, crop_files, filter_source, sort_by)
    else:  # rejected
        main_content = render_rejected_section(dismissed, crop_files, counts, is_admin=user_is_admin)

    style = Style("""
        html, body {
            height: 100%;
            margin: 0;
        }
        body {
            background-color: #0f172a;
        }
        @keyframes fade-in {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slide-out-right {
            from { opacity: 1; transform: translateX(0); }
            to { opacity: 0; transform: translateX(100px); }
        }
        .animate-fade-in {
            animation: fade-in 0.3s ease-out;
        }
        .animate-slide-out {
            animation: slide-out-right 0.3s ease-in forwards;
        }
        .htmx-indicator {
            display: none;
        }
        .htmx-request .htmx-indicator {
            display: inline;
        }
        /* Keyboard focus states */
        button:focus-visible {
            outline: 2px solid #0ea5e9;
            outline-offset: 2px;
        }
        /* Card state transitions */
        .identity-card {
            transition: all 0.2s ease-out;
        }
        .identity-card:hover {
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        }
        /* Darkroom theme - monospace for data */
        .font-data {
            font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
        }
        /* Mobile responsive sidebar */
        @media (max-width: 767px) {
            #sidebar {
                transform: translateX(-100%);
                transition: transform 0.3s ease;
            }
            #sidebar.open {
                transform: translateX(0);
            }
            .main-content {
                margin-left: 0 !important;
            }
        }
        @media (min-width: 768px) {
            #sidebar { transform: translateX(0); }
        }
        @media (min-width: 1024px) {
            .main-content { margin-left: 16rem; }
        }
    """)

    # Mobile header (shown only on small screens)
    mobile_header = Div(
        Button(
            # Hamburger icon
            Svg(
                Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2",
                     d="M4 6h16M4 12h16M4 18h16"),
                cls="w-6 h-6", fill="none", stroke="currentColor", viewBox="0 0 24 24"
            ),
            onclick="toggleSidebar()",
            cls="p-2 text-slate-300 hover:text-white min-h-[44px] min-w-[44px] flex items-center justify-center"
        ),
        Span("Rhodesli", cls="text-lg font-bold text-white"),
        cls="mobile-header lg:hidden flex items-center gap-3 px-4 py-3 bg-slate-800 border-b border-slate-700 sticky top-0 z-30"
    )

    # Sidebar overlay for mobile
    sidebar_overlay = Div(
        onclick="closeSidebar()",
        cls="sidebar-overlay fixed inset-0 bg-black/50 z-30 hidden lg:hidden"
    )

    # Sidebar toggle script
    sidebar_script = Script("""
        function toggleSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.toggle('open');
            sb.classList.toggle('-translate-x-full');
            ov.classList.toggle('hidden');
        }
        function closeSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.remove('open');
            sb.classList.add('-translate-x-full');
            ov.classList.add('hidden');
        }
    """)

    return Title("Rhodesli Identity System"), style, Div(
        # Toast container for notifications
        toast_container(),
        # Mobile header
        mobile_header,
        # Sidebar overlay (mobile backdrop)
        sidebar_overlay,
        # Sidebar (fixed)
        sidebar(counts, section, user=user),
        # Main content (offset for sidebar)
        Main(
            Div(
                main_content,
                cls="max-w-6xl mx-auto px-4 sm:px-8 py-6"
            ),
            cls="main-content ml-0 lg:ml-64 min-h-screen"
        ),
        # Photo context modal (hidden by default)
        photo_modal(),
        # Login modal (shown when unauthenticated user triggers protected action)
        login_modal(),
        # Styled confirmation modal (replaces native browser confirm())
        confirm_modal(),
        sidebar_script,
        cls="h-full"
    )


@rt("/confirm/{identity_id}")
def post(identity_id: str, from_focus: bool = False, sess=None):
    """
    Confirm an identity (move from PROPOSED to CONFIRMED).
    Requires admin.
    """
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        # Lock contention or file access error
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Confirm the identity
    try:
        registry.confirm_identity(identity_id, user_source="web")
        save_registry(registry)
    except Exception as e:
        # Could be variance explosion or other error
        return Response(
            to_xml(toast(f"Cannot confirm: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            get_next_focus_card(exclude_id=identity_id),
            toast("Identity confirmed.", "success"),
        )

    # Return updated card (now CONFIRMED, no action buttons)
    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return the card plus a success toast
    return (
        identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        toast("Identity confirmed.", "success"),
    )


@rt("/reject/{identity_id}")
def post(identity_id: str, from_focus: bool = False, sess=None):
    """Contest/reject an identity (move to CONTESTED). Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.contest_identity(identity_id, user_source="web", reason="Rejected via UI")
        save_registry(registry)
    except Exception as e:
        return Response(
            to_xml(toast(f"Cannot reject: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            get_next_focus_card(exclude_id=identity_id),
            toast("Identity contested.", "warning"),
        )

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    return (
        identity_card(updated_identity, crop_files, lane_color="red", show_actions=False),
        toast("Identity contested.", "warning"),
    )


# =============================================================================
# ROUTES - PHOTO CONTEXT NAVIGATOR (LIGHT TABLE)
# =============================================================================

@rt("/api/photo/{photo_id}")
def get(photo_id: str):
    """
    Get photo metadata with face bounding boxes.

    Returns JSON with:
    - photo_url: Static path to the photo
    - image_width, image_height: Original dimensions
    - faces: List of face objects with bbox, face_id, display_name, identity_id
    """
    photo = get_photo_metadata(photo_id)
    if not photo:
        return JSONResponse(
            {"error": "Photo not found", "photo_id": photo_id},
            status_code=404,
        )

    # Get image dimensions - use filepath if available (for inbox uploads)
    width, height = get_photo_dimensions(photo.get("filepath") or photo["filename"])
    if width == 0 or height == 0:
        return JSONResponse(
            {"error": "Could not read photo dimensions", "photo_id": photo_id},
            status_code=404,
        )

    # Build face list with identity information
    registry = load_registry()
    faces = []

    for face_data in photo["faces"]:
        face_id = face_data["face_id"]
        bbox = face_data["bbox"]  # [x1, y1, x2, y2]

        # Find identity for this face
        identity = get_identity_for_face(registry, face_id)

        # Convert bbox from [x1, y1, x2, y2] to {x, y, w, h}
        x1, y1, x2, y2 = bbox
        # UI BOUNDARY: sanitize display_name for safe JSON rendering
        raw_display_name = identity.get("name", "Unidentified") if identity else "Unidentified"
        face_obj = {
            "face_id": face_id,
            "bbox": {
                "x": x1,
                "y": y1,
                "w": x2 - x1,
                "h": y2 - y1,
            },
            "display_name": ensure_utf8_display(raw_display_name),
            "identity_id": identity["identity_id"] if identity else None,
            "is_selected": False,
        }
        faces.append(face_obj)

    return JSONResponse({
        "photo_url": photo_url(photo["filename"]),
        "image_width": width,
        "image_height": height,
        "faces": faces,
    })


def photo_view_content(
    photo_id: str,
    selected_face_id: str = None,
    is_partial: bool = False,
) -> tuple:
    """
    Build the photo view content with face overlays.

    Returns FastHTML elements for the photo viewer.
    """
    photo = get_photo_metadata(photo_id)
    if not photo:
        error_content = Div(
            P("Photo not found", cls="text-red-400 font-bold"),
            P(f"ID: {photo_id}", cls="text-slate-400 text-sm font-data"),
            cls="text-center p-8"
        )
        return (error_content,) if is_partial else (Title("Photo Not Found"), error_content)

    # Use filepath (absolute) if available, otherwise fall back to filename
    # This handles inbox uploads which are stored outside raw_photos/
    width, height = get_photo_dimensions(photo.get("filepath") or photo["filename"])

    # If dimensions aren't available (e.g., R2 mode without cached dimensions),
    # we can still show the photo - just without face overlays
    has_dimensions = width > 0 and height > 0

    registry = load_registry()

    # Build face overlays with CSS percentages for responsive scaling
    # Only if we have dimensions (needed for percentage calculations)
    face_overlays = []
    if has_dimensions:
        for face_data in photo["faces"]:
            face_id = face_data["face_id"]
            bbox = face_data["bbox"]  # [x1, y1, x2, y2]
            x1, y1, x2, y2 = bbox

            # Convert to percentages for responsive positioning
            left_pct = (x1 / width) * 100
            top_pct = (y1 / height) * 100
            width_pct = ((x2 - x1) / width) * 100
            height_pct = ((y2 - y1) / height) * 100

            # Get identity info
            identity = get_identity_for_face(registry, face_id)
            # UI BOUNDARY: sanitize display_name for safe rendering
            raw_name = identity.get("name", "Unidentified") if identity else "Unidentified"
            display_name = ensure_utf8_display(raw_name)
            identity_id = identity["identity_id"] if identity else None

            # Determine section based on identity state for navigation
            if identity:
                state = identity.get("state", "INBOX")
                if state == "CONFIRMED":
                    nav_section = "confirmed"
                elif state == "SKIPPED":
                    nav_section = "skipped"
                elif state in ("REJECTED", "CONTESTED"):
                    nav_section = "rejected"
                else:  # INBOX, PROPOSED
                    nav_section = "to_review"
            else:
                nav_section = "to_review"

            # Determine if this face is selected
            is_selected = face_id == selected_face_id

            # Build the overlay div
            overlay_classes = "face-overlay absolute border-2 cursor-pointer transition-all hover:border-amber-400"
            if is_selected:
                overlay_classes += " border-amber-500 bg-amber-500/20"
            else:
                overlay_classes += " border-emerald-500 bg-emerald-500/10 hover:bg-emerald-500/20"

            # Navigation script: close modal, try scroll if on page, else navigate to section
            nav_script = f"on click add .hidden to #photo-modal then set target to #identity-{identity_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-blue-400 to target then wait 1.5s then remove .ring-2 .ring-blue-400 from target else go to url '/?section={nav_section}&view=browse#identity-{identity_id}'"

            overlay = Div(
                # Tooltip on hover
                Span(
                    display_name,
                    cls="absolute -top-8 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none"
                ),
                cls=f"{overlay_classes} group",
                style=f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;",
                title=display_name,
                data_face_id=face_id,
                data_identity_id=identity_id or "",
                # Click closes modal and navigates to identity
                **{"_": nav_script} if identity_id else {},
            )
            face_overlays.append(overlay)

    # Main content
    content = Div(
        # Photo container with overlays
        Div(
            Img(
                src=photo_url(photo["filename"]),
                alt=photo["filename"],
                cls="max-w-full h-auto"
            ),
            *face_overlays,
            cls="relative inline-block"
        ),
        # Photo info
        Div(
            P(
                photo["filename"],
                cls="text-slate-300 text-sm font-data font-medium"
            ),
            P(
                f"{len(photo['faces'])} face{'s' if len(photo['faces']) != 1 else ''} detected",
                cls="text-slate-400 text-sm"
            ),
            P(
                f"{width} x {height} px" if has_dimensions else "Dimensions unavailable",
                cls="text-slate-500 text-xs font-data"
            ),
            P(
                "(Face overlays require cached dimensions)",
                cls="text-slate-600 text-xs italic"
            ) if not has_dimensions and photo["faces"] else None,
            # Source/collection info (if available)
            P(
                f"Source: {photo.get('source', 'Unknown')}",
                cls="text-slate-400 text-xs mt-1"
            ) if photo.get("source") else None,
            cls="mt-4"
        ),
        cls="photo-viewer p-4"
    )

    if is_partial:
        return (content,)

    # Full page with styling
    style = Style("""
        .face-overlay {
            box-sizing: border-box;
        }
        .face-overlay:hover {
            z-index: 10;
        }
    """)

    return (
        Title(f"Photo - {photo['filename']}"),
        style,
        Main(
            # Back button
            A(
                "< Back to Workstation",
                href="/",
                cls="text-slate-400 hover:text-slate-300 mb-4 inline-block"
            ),
            H1(
                "Photo Context",
                cls="text-2xl font-serif font-bold text-white mb-4"
            ),
            content,
            cls="p-4 md:p-8 max-w-6xl mx-auto bg-slate-900 min-h-screen"
        ),
    )


@rt("/photo/{photo_id}")
def get(photo_id: str, face: str = None):
    """
    Render photo view with face overlays.

    Query params:
    - face: Optional face_id to highlight
    """
    return photo_view_content(photo_id, selected_face_id=face)


@rt("/photo/{photo_id}/partial")
def get(photo_id: str, face: str = None):
    """
    Render photo view partial for HTMX modal injection.
    """
    return photo_view_content(photo_id, selected_face_id=face, is_partial=True)


# =============================================================================
# ROUTES - PHASE 3: DISCOVERY & ACTION
# =============================================================================

@rt("/api/identity/{identity_id}/neighbors")
def get(identity_id: str, limit: int = 5, offset: int = 0):
    """
    Get nearest neighbor identities for potential merge.

    Args:
        identity_id: Identity to find neighbors for
        limit: Number of neighbors per page (default 5)
        offset: Number of neighbors already shown (for Load More)

    Returns HTML partial with neighbor cards and merge buttons.
    Implements D3 (Load More pagination).
    """
    try:
        registry = load_registry()
        registry.get_identity(identity_id)
    except KeyError:
        return Div(
            P("Identity not found.", cls="text-red-600 text-center py-4"),
            cls="neighbors-sidebar"
        )

    # Load required data
    face_data = get_face_data()
    photo_registry = load_photo_registry()

    # Request one extra to determine if more exist (B3: pagination)
    try:
        from core.neighbors import find_nearest_neighbors
        total_to_fetch = offset + limit + 1
        all_neighbors = find_nearest_neighbors(
            identity_id, registry, photo_registry, face_data, limit=total_to_fetch
        )
    except ImportError as e:
        print(f"[neighbors] Missing dependency: {e}")
        return Div(
            P("Find Similar requires scipy. Check server dependencies.", cls="text-amber-500 text-center py-4"),
            cls="neighbors-sidebar"
        )
    except Exception as e:
        print(f"[neighbors] Error computing neighbors: {e}")
        return Div(
            P("Could not compute similar identities.", cls="text-red-500 text-center py-4"),
            cls="neighbors-sidebar"
        )

    # Determine if more neighbors exist beyond current page
    has_more = len(all_neighbors) > offset + limit

    # Return only neighbors up to current offset + limit
    neighbors = all_neighbors[:offset + limit]

    # Enhance neighbor data with additional info for UI
    crop_files = get_crop_files()
    for n in neighbors:
        # Add face IDs for thumbnail resolution (B2-REPAIR)
        # First try anchors, then fallback to candidates for PROPOSED identities
        n["anchor_face_ids"] = registry.get_anchor_face_ids(n["identity_id"])
        n["candidate_face_ids"] = registry.get_candidate_face_ids(n["identity_id"])

        # Enhance blocked merge reason with photo filename
        if not n["can_merge"] and n["merge_blocked_reason"] == "co_occurrence":
            filename = find_shared_photo_filename(
                identity_id, n["identity_id"], registry, photo_registry
            )
            if filename:
                n["merge_blocked_reason_display"] = f"Appear together in {filename}"
            else:
                n["merge_blocked_reason_display"] = "Appear together in a photo"

    # Count rejected identities for contextual recovery indicator
    identity = registry.get_identity(identity_id)
    rejected_count = sum(
        1 for neg in identity.get("negative_ids", [])
        if neg.startswith("identity:")
    )

    return neighbors_sidebar(
        identity_id, neighbors, crop_files,
        offset=offset + limit,  # Next offset for Load More
        has_more=has_more,
        rejected_count=rejected_count,
    )


@rt("/api/identity/{identity_id}/neighbors/close")
def get(identity_id: str):
    """
    Close the neighbors sidebar (B1: explicit exit from Find Similar mode).

    Returns empty content to clear the sidebar.
    """
    return Div(
        # Return just the loading indicator (hidden by default)
        Span(
            "Loading...",
            id=f"neighbors-loading-{identity_id}",
            cls="htmx-indicator text-slate-400 text-sm",
        ),
    )


@rt("/api/identity/{identity_id}/search")
def get(identity_id: str, q: str = ""):
    """
    Search for identities by name for manual merge.

    Phase 3B: Manual Search & Human-Authorized Merge Tools

    Args:
        identity_id: Current identity (excluded from results)
        q: Search query (minimum 2 characters)

    Returns HTMX partial with search result cards.
    """
    # Minimum query length
    if len(q.strip()) < 2:
        return Div(id=f"search-results-{identity_id}")

    try:
        registry = load_registry()
    except Exception:
        return Div(
            P("Search unavailable.", cls="text-slate-400 italic text-sm"),
            id=f"search-results-{identity_id}"
        )

    # Search for matching identities
    results = registry.search_identities(q, exclude_id=identity_id)

    crop_files = get_crop_files()
    return search_results_panel(results, identity_id, crop_files)


@rt("/api/identity/{identity_id}/rejected")
def get(identity_id: str):
    """
    Get list of rejected identities for contextual recovery.

    Returns a lightweight list within the sidebar showing blocked identities
    with thumbnail, name, and Unblock button.
    """
    try:
        registry = load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Div(
            P("Identity not found.", cls="text-red-600 text-sm"),
        )

    # Extract rejected identity IDs
    rejected_ids = [
        neg.replace("identity:", "")
        for neg in identity.get("negative_ids", [])
        if neg.startswith("identity:")
    ]

    if not rejected_ids:
        return Div(
            P("No hidden matches.", cls="text-slate-400 text-xs italic"),
        )

    crop_files = get_crop_files()
    items = []

    for rejected_id in rejected_ids:
        try:
            rejected_identity = registry.get_identity(rejected_id)
        except KeyError:
            continue

        # UI BOUNDARY: sanitize name for safe rendering
        raw_name = ensure_utf8_display(rejected_identity.get("name"))
        name = raw_name or f"Identity {rejected_id[:8]}..."

        # Resolve thumbnail using anchor faces, then candidates
        thumbnail_img = None
        anchor_face_ids = registry.get_anchor_face_ids(rejected_id)
        for face_id in anchor_face_ids:
            crop_url = resolve_face_image_url(face_id, crop_files)
            if crop_url:
                thumbnail_img = Img(
                    src=crop_url,
                    alt=name,
                    cls="w-8 h-8 object-cover rounded border border-slate-600"
                )
                break

        if thumbnail_img is None:
            candidate_face_ids = registry.get_candidate_face_ids(rejected_id)
            for face_id in candidate_face_ids:
                crop_url = resolve_face_image_url(face_id, crop_files)
                if crop_url:
                    thumbnail_img = Img(
                        src=crop_url,
                        alt=name,
                        cls="w-8 h-8 object-cover rounded border border-slate-600"
                    )
                    break

        if thumbnail_img is None:
            thumbnail_img = Div(cls="w-8 h-8 bg-slate-600 rounded")

        unblock_btn = Button(
            "Unblock",
            cls="px-2 py-0.5 text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/50 rounded hover:bg-indigo-500/20",
            hx_post=f"/api/identity/{identity_id}/unreject/{rejected_id}",
            hx_target=f"#rejected-item-{rejected_id}",
            hx_swap="outerHTML",
            type="button",
        )

        items.append(
            Div(
                thumbnail_img,
                Span(name, cls="text-xs text-slate-300 truncate flex-1 mx-2"),
                unblock_btn,
                id=f"rejected-item-{rejected_id}",
                cls="flex items-center py-1.5 border-b border-slate-700 last:border-0",
            )
        )

    close_list_btn = Button(
        "Hide",
        cls="text-xs text-slate-400 hover:text-slate-300",
        hx_get=f"/api/identity/{identity_id}/rejected/close",
        hx_target=f"#rejected-list-{identity_id}",
        hx_swap="innerHTML",
        type="button",
    )

    return Div(
        Div(
            Span("Hidden Matches", cls="text-xs font-medium text-slate-400"),
            close_list_btn,
            cls="flex items-center justify-between mb-2",
        ),
        Div(*items),
        cls="mt-2 bg-slate-700 rounded border border-slate-600 p-2",
    )


@rt("/api/identity/{identity_id}/rejected/close")
def get(identity_id: str):
    """Close the rejected identities list."""
    return ""


@rt("/api/identity/{source_id}/reject/{target_id}")
def post(source_id: str, target_id: str, sess=None):
    """
    Record that two identities are NOT the same person (D2, D4). Requires admin.
    """
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Validate both identities exist
    try:
        registry.get_identity(source_id)
        registry.get_identity(target_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Record rejection
    registry.reject_identity_pair(source_id, target_id, user_source="web")
    save_registry(registry)

    # Log the action
    log_user_action(
        "REJECT_IDENTITY",
        source_identity_id=source_id,
        target_identity_id=target_id,
    )

    # Return empty div to replace the neighbor card + toast with undo (D5)
    # The neighbor card will be removed via hx-swap="outerHTML"
    return (
        Div(),  # Empty replacement - card disappears
        toast_with_undo("Marked as 'Not Same Person'", source_id, target_id, "info"),
    )


@rt("/api/identity/{source_id}/unreject/{target_id}")
def post(source_id: str, target_id: str, sess=None):
    """Undo "Not Same Person" rejection (D5). Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Validate both identities exist
    try:
        registry.get_identity(source_id)
        registry.get_identity(target_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Remove rejection
    registry.unreject_identity_pair(source_id, target_id, user_source="web")
    save_registry(registry)

    # Log the action
    log_user_action(
        "UNREJECT_IDENTITY",
        source_identity_id=source_id,
        target_identity_id=target_id,
    )

    # Return empty div to replace target + OOB toast
    # This handles both: undo from toast (replaces toast) and unblock from list (removes item)
    oob_toast = Div(
        toast("Rejection undone. Identity will reappear in Find Similar.", "success"),
        hx_swap_oob="beforeend:#toast-container",
    )
    return (Div(), oob_toast)


@rt("/api/identity/{target_id}/merge/{source_id}")
def post(target_id: str, source_id: str, source: str = "web", sess=None):
    """
    Merge source identity into target identity. Requires admin.

    Args:
        target_id: Identity to merge into
        source_id: Identity to be absorbed
        source: Origin of merge request ("web" or "manual_search")
    """
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Validate both identities exist
    try:
        registry.get_identity(target_id)
        registry.get_identity(source_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Load photo registry for validation
    photo_registry = load_photo_registry()

    # Determine user_source from merge origin
    user_source = source if source in ("web", "manual_search") else "web"

    # Attempt merge
    result = registry.merge_identities(
        source_id=source_id,
        target_id=target_id,
        user_source=user_source,
        photo_registry=photo_registry,
    )

    if not result["success"]:
        error_messages = {
            "co_occurrence": "Cannot merge: these identities appear in the same photo.",
            "already_merged": "Cannot merge: source identity was already merged.",
        }
        message = error_messages.get(result["reason"], f"Merge failed: {result['reason']}")

        return Response(
            to_xml(toast(message, "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Save and return success
    save_registry(registry)

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(target_id)

    # Return updated target card + OOB removal of source card
    return (
        identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        # OOB: Remove source card from DOM (it's been absorbed)
        Div(id=f"identity-{source_id}", hx_swap_oob="delete"),
        toast(f"Merged {result['faces_merged']} face(s) successfully.", "success"),
    )


@rt("/api/identity/{identity_id}/faces")
def get(identity_id: str, sort: str = "date"):
    """
    Get faces for an identity with optional sorting.

    Query params:
    - sort: "date" (default) or "outlier"

    Returns HTML partial with face cards.
    """
    try:
        registry = load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    crop_files = get_crop_files()
    face_data = get_face_data()

    # Get faces in requested order
    if sort == "outlier":
        from core.neighbors import sort_faces_by_outlier_score
        sorted_faces = sort_faces_by_outlier_score(identity_id, registry, face_data)
        face_ids = [face_id for face_id, _ in sorted_faces]
    else:
        # Default: preserve original order
        all_entries = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        face_ids = []
        for entry in all_entries:
            if isinstance(entry, str):
                face_ids.append(entry)
            else:
                face_ids.append(entry.get("face_id"))

    # Build face cards
    cards = []
    for face_id in face_ids:
        crop_url = resolve_face_image_url(face_id, crop_files)
        if crop_url:
            photo_id = get_photo_id_for_face(face_id)
            cards.append(face_card(
                face_id=face_id,
                crop_url=crop_url,
                photo_id=photo_id,
            ))
        else:
            # Placeholder for faces with missing crop files
            cards.append(Div(
                Div(
                    Span("?", cls="text-4xl text-slate-500"),
                    cls="w-full aspect-square bg-slate-700 border border-slate-600 flex items-center justify-center"
                ),
                P("Image unavailable", cls="text-xs text-slate-400 mt-1"),
                P(f"ID: {face_id[:12]}...", cls="text-xs font-data text-slate-500"),
                cls="face-card",
                id=make_css_id(face_id),
            ))

    return Div(
        *cards,
        cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3",
        id=f"faces-{identity_id}",
    )


# =============================================================================
# ROUTES - RENAME IDENTITY
# =============================================================================

@rt("/api/identity/{identity_id}/rename-form")
def get(identity_id: str):
    """
    Return inline edit form for renaming an identity.
    Replaces the name display via HTMX.
    """
    try:
        registry = load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    # UI BOUNDARY: sanitize name for safe rendering in input value
    current_name = ensure_utf8_display(identity.get("name")) or ""

    return Form(
        Input(
            name="name",
            value=current_name,
            placeholder="Enter name...",
            cls="border border-slate-600 bg-slate-700 text-slate-200 rounded px-2 py-1 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-400",
            autofocus=True,
        ),
        Button(
            "Save",
            type="submit",
            cls="ml-2 bg-emerald-600 text-white px-2 py-1 rounded text-sm hover:bg-emerald-500",
        ),
        Button(
            "Cancel",
            type="button",
            hx_get=f"/api/identity/{identity_id}/name-display",
            hx_target=f"#name-{identity_id}",
            hx_swap="outerHTML",
            cls="ml-1 text-slate-400 hover:text-slate-300 text-sm underline",
        ),
        hx_post=f"/api/identity/{identity_id}/rename",
        hx_target=f"#name-{identity_id}",
        hx_swap="outerHTML",
        id=f"name-{identity_id}",
        cls="flex items-center",
    )


@rt("/api/identity/{identity_id}/name-display")
def get(identity_id: str):
    """
    Return the name display component (for cancel button).
    """
    try:
        registry = load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    return name_display(identity_id, identity.get("name"))


@rt("/api/identity/{identity_id}/rename")
def post(identity_id: str, name: str = "", sess=None):
    """Rename an identity. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Validate name
    name = name.strip() if name else ""
    if not name:
        return Response(
            to_xml(toast("Name cannot be empty.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        previous_name = registry.rename_identity(identity_id, name, user_source="web")
        save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )
    except Exception as e:
        return Response(
            to_xml(toast(f"Rename failed: {str(e)}", "error")),
            status_code=500,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Return updated name display + success toast
    return (
        name_display(identity_id, name),
        toast(f"Renamed to '{name}'", "success"),
    )


# =============================================================================
# ROUTES - DETACH FACE
# =============================================================================

@rt("/api/face/{face_id:path}/detach")
def post(face_id: str, sess=None):
    """Detach a face from its identity into a new identity. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Find identity containing this face
    identity = get_identity_for_face(registry, face_id)
    if not identity:
        return Response(
            to_xml(toast("Face not found in any identity.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    identity_id = identity["identity_id"]

    # Attempt detach
    result = registry.detach_face(
        identity_id=identity_id,
        face_id=face_id,
        user_source="web",
    )

    if not result["success"]:
        error_messages = {
            "only_face": "Cannot detach: this is the only face in the identity.",
            "face_not_found": "Face not found in identity.",
        }
        message = error_messages.get(result["reason"], f"Detach failed: {result['reason']}")

        return Response(
            to_xml(toast(message, "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Save registry
    save_registry(registry)

    # Log the action
    log_user_action(
        "DETACH",
        face_id=face_id,
        from_identity_id=identity_id,
        to_identity_id=result["to_identity_id"],
    )

    # 1. Get crop files for rendering
    crop_files = get_crop_files()

    # 2. Render the NEW identity card (detached face's new home)
    new_identity = registry.get_identity(result["to_identity_id"])
    new_card_html = identity_card(
        new_identity,
        crop_files,
        lane_color="amber", # New identities are PROPOSED
        show_actions=True
    )

    # 3. Render the UPDATED old identity card (with correct face count)
    old_identity = registry.get_identity(identity_id)
    state_colors = {
        "INBOX": "blue",
        "PROPOSED": "amber",
        "CONFIRMED": "emerald",
        "CONTESTED": "red",
    }
    old_lane_color = state_colors.get(old_identity["state"], "stone")
    old_card_html = identity_card(
        old_identity,
        crop_files,
        lane_color=old_lane_color,
        show_actions=old_identity["state"] in ("INBOX", "PROPOSED"),
    )

    return (
        # A. Replace OLD identity card with updated face count
        Div(old_card_html, id=f"identity-{identity_id}", hx_swap_oob="outerHTML"),

        # B. Insert the new identity card at the top of the Proposed lane
        Div(new_card_html, hx_swap_oob="afterbegin:#proposed-lane"),

        # C. Success toast
        toast(f"Face detached into new identity.", "success"),
    )


# --- INSTRUMENTATION SKIP ENDPOINT ---
@rt("/api/identity/{id}/skip")
def post(id: str, sess=None):
    """Log the skip action. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    get_event_recorder().record("SKIP", {"identity_id": id})
    # No return needed as this is fire-and-forget for logging
    # The UI handles the DOM move client-side
    return Response(status_code=200)
# -------------------------------------


# =============================================================================
# ROUTES - INBOX INGESTION
# =============================================================================

@rt("/upload")
def get(sess=None):
    """
    Render the upload page. Requires admin when auth is enabled.
    # TODO: Revert to _check_login when upload moderation queue is built (Phase D)
    """
    denied = _check_admin(sess)
    if denied:
        return denied
    user = get_current_user(sess or {})
    style = Style("""
        html, body {
            height: 100%;
            margin: 0;
        }
        body {
            background-color: #0f172a;
        }
    """)

    # Get counts for sidebar
    registry = load_registry()
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    confirmed_list = registry.list_identities(state=IdentityState.CONFIRMED)
    skipped_list = registry.list_identities(state=IdentityState.SKIPPED)
    rejected = registry.list_identities(state=IdentityState.REJECTED)
    contested = registry.list_identities(state=IdentityState.CONTESTED)

    to_review = inbox + proposed
    dismissed = rejected + contested

    # Get photo count
    _build_caches()
    photo_count = len(_photo_cache) if _photo_cache else 0

    counts = {
        "to_review": len(to_review),
        "confirmed": len(confirmed_list),
        "skipped": len(skipped_list),
        "rejected": len(dismissed),
        "photos": photo_count,
    }

    # Load existing sources for autocomplete
    existing_sources = []
    try:
        from core.photo_registry import PhotoRegistry
        photo_registry = PhotoRegistry.load(data_path / "photo_index.json")
        sources_set = set()
        for photo_id in photo_registry._photos:
            source = photo_registry.get_source(photo_id)
            if source:
                sources_set.add(source)
        existing_sources = sorted(sources_set)
    except FileNotFoundError:
        pass  # No photos yet

    upload_style = Style("""
        @media (max-width: 767px) {
            #sidebar { transform: translateX(-100%); transition: transform 0.3s ease; }
            #sidebar.open { transform: translateX(0); }
            .main-content { margin-left: 0 !important; }
        }
        @media (min-width: 768px) { #sidebar { transform: translateX(0); } }
        @media (min-width: 1024px) { .main-content { margin-left: 16rem; } }
    """)
    mobile_header = Div(
        Button(
            Svg(Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2",
                     d="M4 6h16M4 12h16M4 18h16"),
                cls="w-6 h-6", fill="none", stroke="currentColor", viewBox="0 0 24 24"),
            onclick="toggleSidebar()",
            cls="p-2 text-slate-300 hover:text-white min-h-[44px] min-w-[44px] flex items-center justify-center"
        ),
        Span("Upload Photos", cls="text-lg font-bold text-white"),
        cls="mobile-header lg:hidden flex items-center gap-3 px-4 py-3 bg-slate-800 border-b border-slate-700 sticky top-0 z-30"
    )
    sidebar_overlay = Div(onclick="closeSidebar()",
                          cls="sidebar-overlay fixed inset-0 bg-black/50 z-30 hidden lg:hidden")
    sidebar_script = Script("""
        function toggleSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.toggle('open');
            sb.classList.toggle('-translate-x-full');
            ov.classList.toggle('hidden');
        }
        function closeSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.remove('open');
            sb.classList.add('-translate-x-full');
            ov.classList.add('hidden');
        }
    """)

    return Title("Upload Photos - Rhodesli"), style, upload_style, Div(
        toast_container(),
        mobile_header,
        sidebar_overlay,
        sidebar(counts, current_section=None, user=user),
        Main(
            Div(
                # Header
                Div(
                    H2("Upload Photos", cls="text-2xl font-bold text-white"),
                    P("Add new photos for identity analysis", cls="text-sm text-slate-400 mt-1"),
                    cls="mb-6"
                ),
                # Upload form
                upload_area(existing_sources=existing_sources),
                cls="max-w-3xl mx-auto px-4 sm:px-8 py-6"
            ),
            cls="main-content ml-0 lg:ml-64 min-h-screen"
        ),
        sidebar_script,
        cls="h-full"
    )


@rt("/upload")
async def post(files: list[UploadFile], source: str = "", sess=None):
    """
    Accept file upload(s) and optionally spawn subprocess for processing.
    Requires admin.
    # TODO: Revert to _check_login when upload moderation queue is built (Phase D)

    Handles multiple files (images and/or ZIPs) in a single batch job.
    All files are saved to a job directory.

    When PROCESSING_ENABLED=True (local dev):
        - Files go to data/uploads/{job_id}/
        - Subprocess spawned to run core/ingest_inbox.py
        - Real-time status polling

    When PROCESSING_ENABLED=False (production):
        - Files go to data/staging/{job_id}/
        - No subprocess spawned (ML deps not available)
        - Shows "pending admin review" message

    Args:
        files: Uploaded image files or ZIPs
        source: Collection/provenance label (e.g., "Betty Capeluto Miami Collection")

    Returns HTML partial with upload status.
    """
    denied = _check_admin(sess)
    if denied:
        return denied

    import json
    import uuid
    from datetime import datetime, timezone

    # Filter out empty uploads
    valid_files = [f for f in files if f and f.filename]

    if not valid_files:
        return Div(
            P("No files selected.", cls="text-red-600 text-sm"),
            cls="p-2"
        )

    # Generate unique job ID
    job_id = str(uuid.uuid4())[:8]

    # Choose destination based on processing mode
    if PROCESSING_ENABLED:
        job_dir = data_path / "uploads" / job_id
    else:
        job_dir = data_path / "staging" / job_id

    job_dir.mkdir(parents=True, exist_ok=True)

    # Save all files to job directory
    saved_files = []
    for f in valid_files:
        # Sanitize filename
        safe_filename = f.filename.replace(" ", "_").replace("/", "_")
        upload_path = job_dir / safe_filename

        # Write file content
        content = await f.read()
        with open(upload_path, "wb") as out:
            out.write(content)
        saved_files.append(safe_filename)

    # Save metadata for staged uploads (helps admin know context)
    metadata = {
        "job_id": job_id,
        "source": source or "Unknown",
        "files": saved_files,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "processing_enabled": PROCESSING_ENABLED,
    }
    metadata_path = job_dir / "_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # If processing is disabled (production), return staged message
    if not PROCESSING_ENABLED:
        file_count = len(saved_files)
        if file_count == 1:
            file_msg = f"1 photo"
        else:
            file_msg = f"{file_count} photos"

        return Div(
            Div(
                Span("✓", cls="text-green-400 text-lg"),
                P(f"Received {file_msg}", cls="text-slate-200 font-medium"),
                cls="flex items-center gap-2"
            ),
            P(
                "Pending admin review and processing. "
                "Photos will appear after the next data sync.",
                cls="text-slate-400 text-sm mt-1"
            ),
            P(f"Reference: {job_id}", cls="text-slate-500 text-xs mt-2 font-mono"),
            cls="p-3 bg-green-900/20 border border-green-500/30 rounded"
        )

    # Processing enabled: spawn subprocess for ML processing
    import os
    import subprocess

    # INVARIANT: All subprocesses must run from PROJECT_ROOT with cwd AND PYTHONPATH set
    subprocess_env = os.environ.copy()
    # Explicitly set PYTHONPATH to ensure core imports work in all environments
    existing_pythonpath = subprocess_env.get("PYTHONPATH", "")
    if existing_pythonpath:
        subprocess_env["PYTHONPATH"] = f"{project_root}{os.pathsep}{existing_pythonpath}"
    else:
        subprocess_env["PYTHONPATH"] = str(project_root)

    # Build subprocess arguments
    subprocess_args = [
        sys.executable,
        "-m",
        "core.ingest_inbox",
        "--directory",
        str(job_dir),
        "--job-id",
        job_id,
    ]
    if source:
        subprocess_args.extend(["--source", source])

    subprocess.Popen(
        subprocess_args,
        cwd=project_root,
        env=subprocess_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Build initial status message
    file_count = len(saved_files)
    if file_count == 1:
        msg = f"Processing {saved_files[0]}..."
    else:
        msg = f"Processing {file_count} files..."

    # Return status component that polls for completion
    return Div(
        P(msg, cls="text-slate-300 text-sm"),
        Span("\u23f3", cls="animate-pulse"),
        hx_get=f"/upload/status/{job_id}",
        hx_trigger="every 2s",
        hx_swap="outerHTML",
        cls="p-2 bg-blue-900/30 border border-blue-500/30 rounded flex items-center gap-2"
    )


@rt("/upload/status/{job_id}")
def get(job_id: str):
    """
    Poll job status for upload processing.

    Returns HTML partial with current status driven by backend job state.
    Shows real progress (% complete, files processed) and error counts.
    """
    import json

    status_path = data_path / "inbox" / f"{job_id}.status.json"

    if not status_path.exists():
        # Status file not yet created - job just started
        return Div(
            P("Starting...", cls="text-slate-300 text-sm"),
            Span("\u23f3", cls="animate-pulse"),
            hx_get=f"/upload/status/{job_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            cls="p-2 bg-blue-900/30 border border-blue-500/30 rounded flex items-center gap-2"
        )

    with open(status_path) as f:
        status = json.load(f)

    if status["status"] == "processing":
        # Show real progress from job state
        total = status.get("total_files")
        succeeded = status.get("files_succeeded", 0)
        failed = status.get("files_failed", 0)
        current_file = status.get("current_file")
        faces = status.get("faces_extracted", 0)

        # Build progress message driven by actual job state
        if total and total > 0:
            processed = succeeded + failed
            pct = int((processed / total) * 100)
            progress_text = f"Processing {processed}/{total} ({pct}%)"
            if current_file:
                progress_text = f"{progress_text}: {current_file}"
            progress_elements = [
                P(progress_text, cls="text-slate-300 text-sm"),
                # Real progress bar based on actual completion
                Div(
                    Div(cls=f"h-1 bg-blue-500 rounded", style=f"width: {pct}%"),
                    cls="w-full bg-slate-700 rounded h-1 mt-1"
                ),
            ]
            if faces > 0:
                progress_elements.append(
                    P(f"{faces} face(s) found so far", cls="text-slate-400 text-xs mt-1")
                )
        else:
            progress_elements = [
                P("Processing...", cls="text-slate-300 text-sm"),
                Span("\u23f3", cls="animate-pulse"),
            ]

        return Div(
            *progress_elements,
            hx_get=f"/upload/status/{job_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            cls="p-2 bg-blue-900/30 border border-blue-500/30 rounded"
        )

    if status["status"] == "error":
        # Total failure
        error_msg = status.get("error", "Unknown error")
        errors = status.get("errors", [])

        elements = [P(f"Error: {error_msg}", cls="text-red-400 text-sm font-medium")]

        # Show per-file errors if available
        if errors:
            # UI BOUNDARY: sanitize filenames for safe rendering
            error_list = Ul(
                *[Li(f"{ensure_utf8_display(e['filename'])}: {ensure_utf8_display(e['error'])}", cls="text-xs") for e in errors[:5]],
                cls="text-red-400 mt-1 ml-4 list-disc"
            )
            elements.append(error_list)
            if len(errors) > 5:
                elements.append(P(f"... and {len(errors) - 5} more errors", cls="text-red-500 text-xs"))

        return Div(*elements, cls="p-2 bg-red-900/30 border border-red-500/30 rounded")

    if status["status"] == "partial":
        # Some files succeeded, some failed
        faces = status.get("faces_extracted", 0)
        identities = len(status.get("identities_created", []))
        total = status.get("total_files", 0)
        succeeded = status.get("files_succeeded", 0)
        failed = status.get("files_failed", 0)
        errors = status.get("errors", [])

        elements = [
            P(
                f"\u2713 {faces} face(s) extracted from {succeeded}/{total} images",
                cls="text-amber-600 text-sm font-medium"
            ),
        ]

        # Show failure summary
        if failed > 0:
            elements.append(
                P(f"\u26a0 {failed} image(s) failed", cls="text-red-400 text-sm")
            )
            # Show first few errors
            if errors:
                # UI BOUNDARY: sanitize filenames for safe rendering
                error_summary = ", ".join(ensure_utf8_display(e["filename"]) for e in errors[:3])
                if len(errors) > 3:
                    error_summary += f", +{len(errors) - 3} more"
                elements.append(P(f"Failed: {error_summary}", cls="text-red-500 text-xs"))

        elements.append(
            A("Refresh to see inbox", href="/", cls="text-indigo-400 hover:underline text-xs mt-1 block")
        )

        return Div(*elements, cls="p-2 bg-amber-900/30 border border-amber-500/30 rounded")

    # Success (all files processed successfully)
    faces = status.get("faces_extracted", 0)
    identities = len(status.get("identities_created", []))
    total = status.get("total_files")

    success_text = f"\u2713 {faces} face(s) extracted"
    if total and total > 1:
        success_text = f"\u2713 {faces} face(s) extracted from {total} images"
    success_text += f", {identities} added to Inbox"

    return Div(
        P(success_text, cls="text-emerald-400 text-sm font-medium"),
        A("Refresh to see inbox", href="/", cls="text-indigo-400 hover:underline text-xs ml-2"),
        cls="p-2 bg-emerald-900/30 border border-emerald-500/30 rounded flex items-center"
    )


@rt("/inbox/{identity_id}/review")
def post(identity_id: str, sess=None):
    """Move identity from INBOX to PROPOSED state. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.move_to_proposed(identity_id, user_source="web")
        save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now PROPOSED, with full action buttons)
    return (
        identity_card(updated_identity, crop_files, lane_color="amber", show_actions=True),
        toast("Moved to Proposed for review.", "success"),
    )


@rt("/inbox/{identity_id}/confirm")
def post(identity_id: str, from_focus: bool = False, sess=None):
    """Confirm identity from INBOX state (INBOX -> CONFIRMED). Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.confirm_identity(identity_id, user_source="web_review")
        save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            get_next_focus_card(exclude_id=identity_id),
            toast("Identity confirmed.", "success"),
        )

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now CONFIRMED)
    return (
        identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        toast("Identity confirmed.", "success"),
    )


@rt("/inbox/{identity_id}/reject")
def post(identity_id: str, from_focus: bool = False, sess=None):
    """Reject identity from INBOX state (INBOX -> REJECTED). Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.reject_identity(identity_id, user_source="web_review")
        save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            get_next_focus_card(exclude_id=identity_id),
            toast("Identity rejected.", "success"),
        )

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now REJECTED)
    return (
        identity_card(updated_identity, crop_files, lane_color="rose", show_actions=False),
        toast("Identity rejected.", "success"),
    )


@rt("/identity/{identity_id}/skip")
def post(identity_id: str, from_focus: bool = False, sess=None):
    """
    Skip identity (defer for later review). Requires admin.

    Works from INBOX or PROPOSED state -> SKIPPED.
    """
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.skip_identity(identity_id, user_source="web_review")
        save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            get_next_focus_card(exclude_id=identity_id),
            toast("Skipped for later.", "info"),
        )

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    return (
        identity_card(updated_identity, crop_files, lane_color="stone", show_actions=False),
        toast("Skipped for later.", "info"),
    )


@rt("/identity/{identity_id}/reset")
def post(identity_id: str, sess=None):
    """Reset identity back to Inbox. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied
    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.reset_identity(identity_id, user_source="web_review")
        save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    return (
        identity_card(updated_identity, crop_files, lane_color="blue", show_actions=True),
        toast("Returned to Inbox.", "info"),
    )


# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================

@rt("/login")
def get(sess):
    """Login page. Redirects to home if already authenticated or auth disabled."""
    if not is_auth_enabled():
        return RedirectResponse('/', status_code=303)
    if sess.get('auth'):
        return RedirectResponse('/', status_code=303)

    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Login - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
        ),
        Body(
            Div(
                H1("Rhodesli", cls="text-2xl font-bold mb-2"),
                P("Family Heritage Archive", cls="text-gray-400 mb-8"),
                Form(
                    Div(
                        Label("Email", fr="email", cls="block text-sm mb-1"),
                        Input(type="email", name="email", id="email", required=True,
                              cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"),
                        cls="mb-4"
                    ),
                    Div(
                        Label("Password", fr="password", cls="block text-sm mb-1"),
                        Input(type="password", name="password", id="password", required=True,
                              cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"),
                        cls="mb-4"
                    ),
                    Button("Sign In", type="submit",
                           cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"),
                    method="post", action="/login", cls="space-y-2"
                ),
                Div(
                    Div(cls="flex-grow border-t border-gray-600"),
                    Span("or", cls="px-4 text-gray-500 text-sm"),
                    Div(cls="flex-grow border-t border-gray-600"),
                    cls="flex items-center my-6"
                ) if get_oauth_url("google") else None,
                A(
                    NotStr('<svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>'),
                    Span("Sign in with Google"),
                    href=get_oauth_url("google") or "#",
                    style="display: flex; align-items: center; gap: 12px; padding: 0 16px; height: 40px; "
                          "background: white; border: 1px solid #dadce0; border-radius: 4px; cursor: pointer; "
                          "font-family: 'Roboto', Arial, sans-serif; font-size: 14px; color: #3c4043; "
                          "font-weight: 500; text-decoration: none; justify-content: center; width: 100%;",
                ) if get_oauth_url("google") else None,
                P(
                    A("Forgot password?", href="/forgot-password", cls="text-blue-400 hover:underline"),
                    cls="mt-4 text-center text-sm"
                ),
                P(
                    "Need an account? ",
                    A("Sign up with invite code", href="/signup", cls="text-blue-400 hover:underline"),
                    cls="mt-2 text-gray-400 text-sm"
                ),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
            ),
            cls="min-h-screen bg-gray-900 text-white"
        ),
    )


@rt("/login")
async def post(email: str, password: str, sess):
    """Handle login form submission."""
    user, error = await login_with_supabase(email, password)
    if error:
        return Html(
            Head(Meta(name="viewport", content="width=device-width, initial-scale=1"), Title("Login - Rhodesli"), Script(src="https://cdn.tailwindcss.com")),
            Body(
                Div(
                    H1("Rhodesli", cls="text-2xl font-bold mb-2"),
                    P(error, cls="text-red-400 mb-4 text-sm"),
                    Form(
                        Div(Label("Email", fr="email", cls="block text-sm mb-1"),
                            Input(type="email", name="email", id="email", value=email, required=True,
                                  cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"), cls="mb-4"),
                        Div(Label("Password", fr="password", cls="block text-sm mb-1"),
                            Input(type="password", name="password", id="password", required=True,
                                  cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"), cls="mb-4"),
                        Button("Sign In", type="submit", cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"),
                        method="post", action="/login",
                    ),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
                ),
                cls="min-h-screen bg-gray-900 text-white"
            ),
        )
    sess['auth'] = user
    return RedirectResponse('/', status_code=303)


@rt("/login/modal")
async def post(email: str, password: str, sess):
    """Handle login from the modal context. Returns error text or HX-Refresh on success."""
    user, error = await login_with_supabase(email, password)
    if error:
        return error
    sess['auth'] = user
    return Response("", headers={"HX-Refresh": "true"})


@rt("/signup")
def get(sess):
    """Signup page with invite code."""
    if not is_auth_enabled():
        return RedirectResponse('/', status_code=303)
    if sess.get('auth'):
        return RedirectResponse('/', status_code=303)

    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Sign Up - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
        ),
        Body(
            Div(
                H1("Join Rhodesli", cls="text-2xl font-bold mb-2"),
                P("Invite-only registration", cls="text-gray-400 mb-8"),
                Form(
                    Div(
                        Label("Invite Code", fr="invite_code", cls="block text-sm mb-1"),
                        Input(type="text", name="invite_code", id="invite_code", required=True,
                              cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"),
                        cls="mb-4"
                    ),
                    Div(
                        Label("Email", fr="email", cls="block text-sm mb-1"),
                        Input(type="email", name="email", id="email", required=True,
                              cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"),
                        cls="mb-4"
                    ),
                    Div(
                        Label("Password", fr="password", cls="block text-sm mb-1"),
                        Input(type="password", name="password", id="password", required=True, minlength="8",
                              cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"),
                        P("Minimum 8 characters", cls="text-gray-500 text-xs mt-1"),
                        cls="mb-4"
                    ),
                    Button("Create Account", type="submit",
                           cls="w-full p-2 bg-green-600 hover:bg-green-700 rounded text-white font-medium"),
                    method="post", action="/signup",
                ),
                P(
                    "Already have an account? ",
                    A("Sign in", href="/login", cls="text-blue-400 hover:underline"),
                    cls="mt-4 text-gray-400 text-sm"
                ),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
            ),
            cls="min-h-screen bg-gray-900 text-white"
        ),
    )


@rt("/signup")
async def post(email: str, password: str, invite_code: str, sess):
    """Handle signup form submission."""
    if not validate_invite_code(invite_code):
        error = "Invalid invite code"
        user = None
    else:
        user, error = await signup_with_supabase(email, password)
    if error:
        return Html(
            Head(Meta(name="viewport", content="width=device-width, initial-scale=1"), Title("Sign Up - Rhodesli"), Script(src="https://cdn.tailwindcss.com")),
            Body(
                Div(
                    H1("Join Rhodesli", cls="text-2xl font-bold mb-2"),
                    P(error, cls="text-red-400 mb-4 text-sm"),
                    Form(
                        Div(Label("Invite Code", fr="invite_code", cls="block text-sm mb-1"),
                            Input(type="text", name="invite_code", id="invite_code", value=invite_code, required=True,
                                  cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"), cls="mb-4"),
                        Div(Label("Email", fr="email", cls="block text-sm mb-1"),
                            Input(type="email", name="email", id="email", value=email, required=True,
                                  cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"), cls="mb-4"),
                        Div(Label("Password", fr="password", cls="block text-sm mb-1"),
                            Input(type="password", name="password", id="password", required=True, minlength="8",
                                  cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"), cls="mb-4"),
                        Button("Create Account", type="submit",
                               cls="w-full p-2 bg-green-600 hover:bg-green-700 rounded text-white font-medium"),
                        method="post", action="/signup",
                    ),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
                ),
                cls="min-h-screen bg-gray-900 text-white"
            ),
        )
    sess['auth'] = user
    return RedirectResponse('/', status_code=303)


@rt("/forgot-password")
def get(sess):
    """Forgot password page."""
    if not is_auth_enabled():
        return RedirectResponse('/', status_code=303)

    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Reset Password - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
        ),
        Body(
            Div(
                H1("Reset Password", cls="text-2xl font-bold mb-2"),
                P("Enter your email to receive a reset link", cls="text-gray-400 mb-6"),
                Form(
                    Div(
                        Label("Email", fr="email", cls="block text-sm mb-1"),
                        Input(type="email", name="email", id="email", required=True,
                              cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"),
                        cls="mb-4"
                    ),
                    Button("Send Reset Link", type="submit",
                           cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"),
                    method="post", action="/forgot-password",
                ),
                P(
                    A("← Back to Login", href="/login", cls="text-blue-400 hover:underline"),
                    cls="mt-6 text-center"
                ),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
            ),
            cls="min-h-screen bg-gray-900 text-white"
        ),
    )


@rt("/forgot-password")
async def post(email: str, sess):
    """Handle forgot password form."""
    success, error = await send_password_reset(email)

    # Always show success message to avoid email enumeration
    msg = "If an account exists with that email, you'll receive a reset link."
    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Reset Password - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
        ),
        Body(
            Div(
                H1("Reset Password", cls="text-2xl font-bold mb-2"),
                P(msg, cls="text-green-400 mb-6 text-sm"),
                P(
                    A("← Back to Login", href="/login", cls="text-blue-400 hover:underline"),
                    cls="mt-6 text-center"
                ),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
            ),
            cls="min-h-screen bg-gray-900 text-white"
        ),
    )


@rt("/reset-password")
def get(sess):
    """Handle reset password callback from email link. Tokens are in URL fragment."""
    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Set New Password - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
            Script("""
                document.addEventListener('DOMContentLoaded', function() {
                    // Check for PKCE code in query params (Supabase email flow)
                    const urlParams = new URLSearchParams(window.location.search);
                    const code = urlParams.get('code');

                    if (code) {
                        // Exchange PKCE code server-side for access token
                        document.getElementById('error-msg').textContent = 'Verifying your link...';
                        fetch('/auth/exchange-code', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({code: code})
                        }).then(r => r.json()).then(data => {
                            if (data.access_token) {
                                document.getElementById('access_token').value = data.access_token;
                                document.getElementById('reset-form').style.display = 'block';
                                document.getElementById('error-msg').style.display = 'none';
                            } else {
                                document.getElementById('error-msg').textContent = data.error || 'This link has expired. Please request a new one.';
                            }
                        }).catch(function() {
                            document.getElementById('error-msg').textContent = 'Something went wrong. Please request a new reset link.';
                        });
                        return;
                    }

                    // Legacy: check for access_token in URL hash fragment
                    const hash = window.location.hash.substring(1);
                    const params = new URLSearchParams(hash);
                    const accessToken = params.get('access_token');
                    const type = params.get('type');

                    if (accessToken && type === 'recovery') {
                        document.getElementById('access_token').value = accessToken;
                        document.getElementById('reset-form').style.display = 'block';
                        document.getElementById('error-msg').style.display = 'none';
                    } else if (!accessToken && !code) {
                        document.getElementById('error-msg').textContent = 'Invalid or expired reset link. Please request a new one.';
                    }
                });
            """),
        ),
        Body(
            Div(
                H1("Set New Password", cls="text-2xl font-bold mb-6"),
                P("Invalid or expired reset link.", id="error-msg", cls="text-red-400 mb-4 text-sm"),
                Form(
                    Input(type="hidden", name="access_token", id="access_token"),
                    Div(
                        Label("New Password", fr="password", cls="block text-sm mb-1"),
                        Input(type="password", name="password", id="password", required=True, minlength="8",
                              cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"),
                        P("Minimum 8 characters", cls="text-gray-500 text-xs mt-1"),
                        cls="mb-4"
                    ),
                    Div(
                        Label("Confirm Password", fr="password_confirm", cls="block text-sm mb-1"),
                        Input(type="password", name="password_confirm", id="password_confirm", required=True, minlength="8",
                              cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600"),
                        cls="mb-4"
                    ),
                    Button("Update Password", type="submit",
                           cls="w-full p-2 bg-green-600 hover:bg-green-700 rounded text-white font-medium"),
                    method="post", action="/reset-password",
                    id="reset-form", style="display:none",
                ),
                P(
                    A("← Back to Login", href="/login", cls="text-blue-400 hover:underline"),
                    cls="mt-6 text-center"
                ),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
            ),
            cls="min-h-screen bg-gray-900 text-white"
        ),
    )


@rt("/reset-password")
async def post(access_token: str, password: str, password_confirm: str, sess):
    """Handle password reset form submission."""
    error = None
    if not access_token:
        error = "Invalid reset link. Please request a new one."
    elif password != password_confirm:
        error = "Passwords do not match."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."

    if error:
        return Html(
            Head(Meta(name="viewport", content="width=device-width, initial-scale=1"), Title("Set New Password - Rhodesli"), Script(src="https://cdn.tailwindcss.com")),
            Body(
                Div(
                    H1("Set New Password", cls="text-2xl font-bold mb-6"),
                    P(error, cls="text-red-400 mb-4 text-sm"),
                    P(A("← Request a new reset link", href="/forgot-password", cls="text-blue-400 hover:underline"), cls="mt-4"),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
                ),
                cls="min-h-screen bg-gray-900 text-white"
            ),
        )

    success, err = await update_password(access_token, password)

    if success:
        return Html(
            Head(Meta(name="viewport", content="width=device-width, initial-scale=1"), Title("Password Updated - Rhodesli"), Script(src="https://cdn.tailwindcss.com")),
            Body(
                Div(
                    H1("Password Updated", cls="text-2xl font-bold mb-4"),
                    P("Your password has been updated successfully.", cls="text-green-400 mb-6"),
                    A("Sign in with your new password", href="/login",
                      cls="block w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium text-center"),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
                ),
                cls="min-h-screen bg-gray-900 text-white"
            ),
        )
    else:
        return Html(
            Head(Meta(name="viewport", content="width=device-width, initial-scale=1"), Title("Set New Password - Rhodesli"), Script(src="https://cdn.tailwindcss.com")),
            Body(
                Div(
                    H1("Set New Password", cls="text-2xl font-bold mb-6"),
                    P(err or "Failed to update password.", cls="text-red-400 mb-4 text-sm"),
                    P(A("← Request a new reset link", href="/forgot-password", cls="text-blue-400 hover:underline"), cls="mt-4"),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg"
                ),
                cls="min-h-screen bg-gray-900 text-white"
            ),
        )


@rt("/auth/callback")
def get(sess):
    """Handle OAuth callback from social providers. Tokens are in URL fragment."""
    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Logging in..."),
            Script(src="https://cdn.tailwindcss.com"),
            Script("""
                document.addEventListener('DOMContentLoaded', function() {
                    const hash = window.location.hash.substring(1);
                    const params = new URLSearchParams(hash);
                    const accessToken = params.get('access_token');

                    if (accessToken) {
                        fetch('/auth/session', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({access_token: accessToken})
                        }).then(r => r.json()).then(data => {
                            if (data.success) {
                                window.location.href = '/';
                            } else {
                                window.location.href = '/login?error=oauth_failed';
                            }
                        }).catch(() => {
                            window.location.href = '/login?error=oauth_failed';
                        });
                    } else {
                        window.location.href = '/login?error=oauth_failed';
                    }
                });
            """),
        ),
        Body(
            Div(
                P("Completing login...", cls="text-gray-400"),
                cls="flex items-center justify-center min-h-screen bg-gray-900"
            ),
        ),
    )


@rt("/auth/session")
async def post(request, sess):
    """Create session from OAuth access token."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request"}, status_code=400)

    access_token = data.get("access_token")
    if not access_token:
        return JSONResponse({"error": "No token"}, status_code=400)

    user, error = await get_user_from_token(access_token)
    if user:
        sess['auth'] = user
        return JSONResponse({"success": True})
    else:
        return JSONResponse({"error": error or "Failed to get user"}, status_code=401)


@rt("/auth/exchange-code")
async def post(request, sess):
    """Exchange a PKCE auth code for an access token (used by password recovery)."""
    from starlette.responses import JSONResponse

    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request"}, status_code=400)

    code = data.get("code")
    if not code:
        return JSONResponse({"error": "No code provided"}, status_code=400)

    result, error = await exchange_code_for_session(code)
    if result:
        return JSONResponse({"access_token": result["access_token"]})
    else:
        return JSONResponse({"error": error or "Code exchange failed"}, status_code=400)


@rt("/logout")
def get(sess):
    """Log out and redirect to home."""
    sess.clear()
    return RedirectResponse('/', status_code=303)


# --- Admin Data Export Endpoints ---

@rt("/admin/export/identities")
def get(sess=None):
    """Download identities.json. Admin-only."""
    block = _check_admin(sess)
    if block:
        return block
    fpath = data_path / "identities.json"
    if not fpath.exists():
        return Response("File not found", status_code=404)
    return FileResponse(
        str(fpath),
        media_type="application/json",
        filename="identities.json",
    )


@rt("/admin/export/photo-index")
def get(sess=None):
    """Download photo_index.json. Admin-only."""
    block = _check_admin(sess)
    if block:
        return block
    fpath = data_path / "photo_index.json"
    if not fpath.exists():
        return Response("File not found", status_code=404)
    return FileResponse(
        str(fpath),
        media_type="application/json",
        filename="photo_index.json",
    )


@rt("/admin/export/all")
def get(sess=None):
    """Download a ZIP of all data files. Admin-only."""
    block = _check_admin(sess)
    if block:
        return block
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("identities.json", "photo_index.json"):
            fpath = data_path / name
            if fpath.exists():
                zf.write(str(fpath), arcname=name)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=rhodesli-data-export.zip"},
    )


if __name__ == "__main__":
    # Startup diagnostics
    print("=" * 60)
    print("RHODESLI STARTUP")
    print("=" * 60)
    print(f"[config] Host: {HOST}")
    print(f"[config] Port: {PORT}")
    print(f"[config] Debug: {DEBUG}")
    print(f"[config] Processing enabled: {PROCESSING_ENABLED}")
    print(f"[config] Auth enabled: {is_auth_enabled()}")
    print(f"[paths] Data directory: {data_path.resolve()}")
    print(f"[paths] Photos directory: {photos_path.resolve()}")

    # Check photos directory
    if photos_path.exists():
        photo_count = len(list(photos_path.iterdir()))
        print(f"[data] Photos found: {photo_count}")
    else:
        print("[data] WARNING: raw_photos directory does not exist")

    # Check data files
    registry = load_registry()
    print(f"[data] Identities loaded: {len(registry.list_identities())}")

    # Count photos from photo_index.json
    photo_index_path = data_path / "photo_index.json"
    if photo_index_path.exists():
        with open(photo_index_path) as f:
            index = json.load(f)
            photo_count = len(index.get("photos", {}))
        print(f"[data] Photos indexed: {photo_count}")
    else:
        print("[data] WARNING: photo_index.json not found")

    # Ensure staging directory exists for production uploads
    staging_dir = data_path / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"Server starting at http://{HOST}:{PORT}")
    print("=" * 60)

    serve(host=HOST, port=PORT, reload=DEBUG)