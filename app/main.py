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
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
from fasthtml.common import *
from PIL import Image
from starlette.datastructures import UploadFile

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.registry import IdentityRegistry, IdentityState
from core.config import MATCH_THRESHOLD_HIGH, MATCH_THRESHOLD_MEDIUM

# --- INSTRUMENTATION IMPORT ---
from core.event_recorder import get_event_recorder

static_path = Path(__file__).resolve().parent / "static"
data_path = Path(__file__).resolve().parent.parent / "data"
photos_path = Path(__file__).resolve().parent.parent / "raw_photos"

app, rt = fast_app(
    pico=False,
    hdrs=(
        Script(src="https://cdn.tailwindcss.com"),
        # Hyperscript required for _="on click..." modal interactions
        Script(src="https://unpkg.com/hyperscript.org@0.9.12"),
    ),
    static_path=str(static_path),
)

# --- INSTRUMENTATION LIFECYCLE HOOKS ---
@app.on_event("startup")
async def startup_event():
    """Log the start of a session/run."""
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

# Mount raw_photos as /photos/ static route
# IMPORTANT: Insert at position 0 so it takes precedence over FastHTML's
# catch-all static route (/{fname:path}.{ext:static})
from starlette.staticfiles import StaticFiles
from starlette.routing import Mount
photos_mount = Mount("/photos", StaticFiles(directory=str(photos_path)), name="photos")
app.routes.insert(0, photos_mount)

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

        face_id = generate_face_id(filename, face_index)

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
    Generate a stable, deterministic photo_id from filename.
    Must match the logic in scripts/seed_registry.py.
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

        photo_id = generate_photo_id(filename)
        face_id = generate_face_id(filename, face_index)

        # Parse bbox - it might be a string or list
        bbox = entry["bbox"]
        if isinstance(bbox, str):
            bbox = json.loads(bbox)
        elif hasattr(bbox, "tolist"):
            bbox = bbox.tolist()

        if photo_id not in photos:
            photos[photo_id] = {
                "filename": filename,
                "filepath": entry.get("filepath", f"raw_photos/{filename}"),
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


def get_photo_dimensions(filename: str) -> tuple:
    """
    Get image dimensions for a photo.

    Returns:
        (width, height) tuple or (0, 0) if file not found
    """
    filepath = photos_path / filename
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

    Encodes the filename to handle spaces and special characters.
    The encoding happens exactly once, at URL construction time.
    Uses default safe='/' to preserve dots in file extensions.
    """
    return f"/photos/{quote(filename)}"


def get_crop_files():
    """Get set of available crop files."""
    crops_dir = static_path / "crops"
    if crops_dir.exists():
        return {f.name for f in crops_dir.glob("*.jpg")}
    return set()


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

    Face IDs use the format: {filename_stem}:face{index}
    Crop files use the format: {sanitized_stem}_{quality}_{index}.jpg

    This function bridges the gap by sanitizing the stem and matching the index.

    Args:
        face_id: Canonical face identifier (e.g., "Image 992_compress:face0")
        crop_files: Set of available crop filenames

    Returns:
        URL path to the crop image (e.g., "/crops/image_992_compress_22.17_0.jpg")
        or None if no matching crop file is found.
    """
    # Parse face_id: extract stem and face index
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
            return f"/crops/{crop}"

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
        Span(message),
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


def upload_area() -> Div:
    """
    Drag-and-drop file upload area.
    UX Intent: Easy bulk ingestion into inbox.
    """
    return Div(
        Form(
            Div(
                Span("\u2191", cls="text-4xl text-stone-300"),
                P("Drop photos here or click to upload", cls="text-stone-500 mt-2"),
                P("Faces will be added to your Inbox for review", cls="text-xs text-stone-400 mt-1"),
                cls="text-center py-8"
            ),
            Input(
                type="file",
                name="file",
                accept="image/*,.zip",
                cls="absolute inset-0 opacity-0 cursor-pointer",
                hx_post="/upload",
                hx_encoding="multipart/form-data",
                hx_target="#upload-status",
                hx_swap="innerHTML",
            ),
            cls="relative",
            enctype="multipart/form-data",
        ),
        Div(id="upload-status", cls="mt-2"),
        cls="border-2 border-dashed border-stone-300 rounded-lg p-4 hover:border-stone-400 hover:bg-stone-50 transition-colors mb-4",
    )


def inbox_badge(count: int) -> A:
    """
    Inbox badge showing count of items awaiting review.
    """
    if count == 0:
        return A(
            Span("\ud83d\udce5", cls="mr-2"),
            "Inbox",
            Span("(0)", cls="text-stone-400 ml-1"),
            href="#inbox-lane",
            cls="text-stone-500 hover:text-stone-700 text-sm"
        )
    return A(
        Span("\ud83d\udce5", cls="mr-2"),
        "Inbox",
        Span(
            f"({count})",
            cls="bg-blue-600 text-white text-xs px-1.5 py-0.5 rounded-full ml-1"
        ),
        href="#inbox-lane",
        cls="text-stone-700 hover:text-blue-600 text-sm font-medium"
    )


def inbox_action_buttons(identity_id: str) -> Div:
    """
    Action buttons for INBOX identities.
    Confirm: Accept as real identity (INBOX → CONFIRMED)
    Reject: Explicitly reject (INBOX → REJECTED)
    """
    return Div(
        # Confirm button (green, solid)
        Button(
            "\u2713 Confirm",
            cls="px-3 py-1.5 text-sm font-bold bg-emerald-600 text-white rounded hover:bg-emerald-700 transition-colors",
            hx_post=f"/inbox/{identity_id}/confirm",
            hx_target=f"#identity-{identity_id}",
            hx_swap="outerHTML",
            hx_indicator=f"#loading-{identity_id}",
            aria_label="Confirm this identity",
            type="button",
        ),
        # Reject button (red, ghost)
        Button(
            "\u2717 Reject",
            cls="px-3 py-1.5 text-sm font-bold border-2 border-red-600 text-red-600 rounded hover:bg-red-50 transition-colors",
            hx_post=f"/inbox/{identity_id}/reject",
            hx_target=f"#identity-{identity_id}",
            hx_swap="outerHTML",
            hx_indicator=f"#loading-{identity_id}",
            aria_label="Reject this identity",
            type="button",
        ),
        # Loading indicator (hidden by default)
        Span(
            "...",
            id=f"loading-{identity_id}",
            cls="htmx-indicator ml-2 text-stone-400 animate-pulse",
            aria_hidden="true",
        ),
        cls="flex gap-2 items-center mt-3",
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


def action_buttons(identity_id: str) -> Div:
    """
    Action buttons for PROPOSED identities.
    UX Intent: Direct manipulation with clear consequences.
    Keyboard accessible: Tab to navigate, Enter/Space to activate.

    Both Skip and Restore buttons are rendered; visibility is toggled via CSS classes.
    """
    # Script to move card to skipped container and show restore button
    skip_script = f"""on click
        set card to #identity-{identity_id}
        set container to #skipped-container
        set details to #skipped-details
        remove .hidden from details
        add .hidden to #skipped-empty-msg
        put card at the end of container
        add .hidden to #skip-btn-{identity_id}
        remove .hidden from #restore-btn-{identity_id}
        set count to #skipped-container's children's length
        put '(' + count + ')' into #skipped-count"""

    # Script to restore card from skipped container
    restore_script = f"""on click
        set card to #identity-{identity_id}
        set lane to #proposed-lane
        put card at the start of lane
        add .hidden to #restore-btn-{identity_id}
        remove .hidden from #skip-btn-{identity_id}
        set count to #skipped-container's children's length
        put '(' + count + ')' into #skipped-count
        if count == 0 then
            add .hidden to #skipped-details
        end"""

    return Div(
        # Confirm button (green, solid)
        Button(
            "\u2713 Confirm",
            cls="px-3 py-1.5 text-sm font-bold bg-emerald-600 text-white rounded hover:bg-emerald-700 transition-colors",
            hx_post=f"/confirm/{identity_id}",
            hx_target=f"#identity-{identity_id}",
            hx_swap="outerHTML",
            hx_indicator=f"#loading-{identity_id}",
            aria_label="Confirm this identity match",
            type="button",
        ),
        # Reject button (red, ghost)
        Button(
            "\u2717 Reject",
            cls="px-3 py-1.5 text-sm font-bold border-2 border-red-600 text-red-600 rounded hover:bg-red-50 transition-colors",
            hx_post=f"/reject/{identity_id}",
            hx_target=f"#identity-{identity_id}",
            hx_swap="outerHTML",
            hx_indicator=f"#loading-{identity_id}",
            aria_label="Reject this identity match",
            type="button",
        ),
        # Skip button (neutral) - moves to skipped container
        Button(
            "? Skip",
            id=f"skip-btn-{identity_id}",
            cls="px-3 py-1.5 text-sm font-bold border border-stone-300 text-stone-500 rounded hover:bg-stone-100 transition-colors",
            aria_label="Skip this identity for now",
            type="button",
            **{"_": skip_script}
        ),
        # Restore button (hidden by default) - restores from skipped container
        Button(
            "\u21a9 Restore",
            id=f"restore-btn-{identity_id}",
            cls="hidden px-3 py-1.5 text-sm font-bold border border-blue-500 text-blue-600 rounded hover:bg-blue-50 transition-colors",
            aria_label="Restore this identity to review",
            type="button",
            **{"_": restore_script}
        ),
        # Loading indicator (hidden by default)
        Span(
            "...",
            id=f"loading-{identity_id}",
            cls="htmx-indicator ml-2 text-stone-400 animate-pulse",
            aria_hidden="true",
        ),
        cls="flex gap-2 items-center mt-3",
        role="group",
        aria_label="Identity actions",
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
            cls="text-xs text-stone-500 hover:text-stone-700 underline mt-1",
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
            cls="text-xs text-red-500 hover:text-red-700 underline mt-1 ml-2",
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
            cls="relative border border-stone-200 bg-white"
        ),
        # Metadata and actions
        Div(
            P(
                f"Quality: {quality:.2f}",
                cls="text-xs font-mono text-stone-500"
            ),
            Div(
                view_photo_btn,
                detach_btn,
                cls="flex items-center"
            ) if view_photo_btn or detach_btn else None,
            cls="mt-2"
        ),
        cls="bg-white border border-stone-200 p-2 rounded shadow-sm hover:shadow-md transition-shadow",
        # Fix: Apply the safe ID to the container
        id=make_css_id(face_id)
    )


def neighbor_card(neighbor: dict, target_identity_id: str, crop_files: set) -> Div:
    neighbor_id = neighbor["identity_id"]
    name = neighbor["name"]
    # Get values directly (no more negative scaling)
    distance = neighbor["distance"]
    percentile = neighbor.get("percentile", 1.0)
    
    can_merge = neighbor["can_merge"]
    face_count = neighbor.get("face_count", 0)

    # --- CALIBRATION: THE LEON STANDARD (ADR 007) ---
    # Thresholds from core.config (derived from forensic evaluation)
    if distance < MATCH_THRESHOLD_HIGH:
        similarity_class = "bg-emerald-100 text-emerald-700"
        similarity_label = "High"
    elif distance < MATCH_THRESHOLD_MEDIUM:
        similarity_class = "bg-amber-100 text-amber-700"
        similarity_label = "Medium"
    else:
        similarity_class = "bg-stone-100 text-stone-500"
        similarity_label = "Low"
    # -----------------------------------------------

    # Merge button
    merge_btn = Button("Merge", cls="px-3 py-1 text-sm font-bold bg-blue-600 text-white rounded hover:bg-blue-700",
                       hx_post=f"/api/identity/{target_identity_id}/merge/{neighbor_id}", hx_target=f"#identity-{target_identity_id}",
                       hx_swap="outerHTML", hx_confirm=f"Merge '{name}'? This cannot be undone.") if can_merge else \
                Button("Blocked", cls="px-3 py-1 text-sm font-bold bg-stone-300 text-stone-500 rounded cursor-not-allowed", disabled=True, title=neighbor.get("merge_blocked_reason_display"))

    # Thumbnail logic
    thumbnail_img = Div(cls="w-12 h-12 bg-stone-200 rounded")
    anchor_face_ids = neighbor.get("anchor_face_ids", []) + neighbor.get("candidate_face_ids", [])
    for fid in anchor_face_ids:
        crop_url = resolve_face_image_url(fid, crop_files)
        if crop_url:
            thumbnail_img = Img(src=crop_url, alt=name, cls="w-12 h-12 object-cover rounded border border-stone-200")
            break

    nav_script = f"on click set target to #identity-{neighbor_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-blue-400 to target then wait 1.5s then remove .ring-2 .ring-blue-400 from target"

    return Div(
        Div(A(thumbnail_img, href=f"#identity-{neighbor_id}", cls="flex-shrink-0 cursor-pointer hover:opacity-80", **{"_": nav_script}),
            Div(Div(A(name, href=f"#identity-{neighbor_id}", cls="font-medium text-stone-700 truncate hover:text-blue-600 hover:underline cursor-pointer", **{"_": nav_script}),
                    Span(similarity_label, cls=f"text-xs px-2 py-0.5 rounded ml-2 {similarity_class}"), cls="flex items-center"),
                # EXPLAINABILITY: We show both. Distance tells you "Is it him?", Percentile tells you "Is it the best we have?"
                Div(Span(f"Dist: {distance:.2f} (p={percentile:.2f})", cls="text-xs font-mono text-stone-400 ml-2 bg-stone-100 px-1 rounded"), cls="flex items-center"),
                cls="flex-1 min-w-0 ml-3"),
            Div(merge_btn, Button("Not Same", cls="px-2 py-1 text-xs font-bold border border-red-300 text-red-500 rounded hover:bg-red-50",
                                  hx_post=f"/api/identity/{target_identity_id}/reject/{neighbor_id}", hx_target=f"#neighbor-{neighbor_id}", hx_swap="outerHTML"),
                cls="flex items-center gap-2 flex-shrink-0 ml-2"),
            cls="flex items-center"),
        id=f"neighbor-{neighbor_id}", cls="p-3 bg-white border border-stone-200 rounded shadow-sm mb-2 hover:shadow-md"
    )

def search_result_card(result: dict, target_identity_id: str, crop_files: set) -> Div:
    """
    Card for a manual search result.
    Similar styling to neighbor_card but simpler (no distance/percentile).
    """
    result_id = result["identity_id"]
    name = result["name"] or f"Identity {result_id[:8]}..."
    face_count = result.get("face_count", 0)
    preview_face_id = result.get("preview_face_id")

    # Thumbnail from preview_face_id
    thumbnail_img = Div(cls="w-10 h-10 bg-stone-200 rounded")
    if preview_face_id:
        crop_url = resolve_face_image_url(preview_face_id, crop_files)
        if crop_url:
            thumbnail_img = Img(
                src=crop_url,
                alt=name,
                cls="w-10 h-10 object-cover rounded border border-stone-200"
            )

    # Merge button with manual_search source
    merge_btn = Button(
        "Merge",
        cls="px-2 py-1 text-xs font-bold bg-blue-600 text-white rounded hover:bg-blue-700",
        hx_post=f"/api/identity/{target_identity_id}/merge/{result_id}?source=manual_search",
        hx_target=f"#identity-{target_identity_id}",
        hx_swap="outerHTML",
        hx_confirm=f"Merge '{name}'? This cannot be undone.",
    )

    return Div(
        Div(
            thumbnail_img,
            Div(
                Span(name, cls="font-medium text-stone-700 truncate text-sm"),
                Span(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-xs text-stone-400 ml-2"),
                cls="flex items-center ml-2 flex-1 min-w-0"
            ),
            merge_btn,
            cls="flex items-center"
        ),
        id=f"search-result-{result_id}",
        cls="p-2 bg-white border border-stone-200 rounded shadow-sm mb-2 hover:shadow-md"
    )


def search_results_panel(results: list, target_identity_id: str, crop_files: set) -> Div:
    """Panel showing manual search results."""
    if not results:
        return Div(
            P("No matching identities found.", cls="text-stone-400 italic text-sm"),
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
        H5("Manual Search", cls="text-sm font-semibold text-stone-600 mb-2"),
        Input(
            type="text",
            name="q",
            placeholder="Search by name...",
            cls="w-full px-3 py-2 text-sm border border-stone-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent",
            hx_get=f"/api/identity/{identity_id}/search",
            hx_trigger="keyup changed delay:300ms",
            hx_target=f"#search-results-{identity_id}",
            hx_include="this",
        ),
        Div(id=f"search-results-{identity_id}", cls="mt-2"),
        cls="mt-4 pt-3 border-t border-stone-200"
    )


def neighbors_sidebar(identity_id: str, neighbors: list, crop_files: set, offset: int = 0, has_more: bool = False, rejected_count: int = 0) -> Div:
    close_btn = Button("Close", cls="text-sm text-stone-500 hover:text-stone-700", hx_get=f"/api/identity/{identity_id}/neighbors/close", hx_target=f"#neighbors-{identity_id}", hx_swap="innerHTML")
    if not neighbors: return Div(Div(P("No similar identities.", cls="text-stone-400 italic"), close_btn, cls="flex items-center justify-between"), manual_search_section(identity_id), cls="neighbors-sidebar p-4 bg-stone-50 rounded border border-stone-200")

    cards = [neighbor_card(n, identity_id, crop_files) for n in neighbors]
    load_more = Button("Load More", cls="w-full text-sm text-blue-600 hover:text-blue-800 py-2 border border-blue-200 rounded hover:bg-blue-50",
                       hx_get=f"/api/identity/{identity_id}/neighbors?offset={offset+len(neighbors)}", hx_target=f"#neighbors-{identity_id}", hx_swap="innerHTML") if has_more else None

    # Manual search section - between Load More and Rejected
    manual_search = manual_search_section(identity_id)

    rejected = Div(Div(Span(f"{rejected_count} hidden matches", cls="text-xs text-stone-400 italic"),
                       Button("Review", cls="text-xs text-blue-500 hover:text-blue-700 ml-2", hx_get=f"/api/identity/{identity_id}/rejected", hx_target=f"#rejected-list-{identity_id}", hx_swap="innerHTML"),
                       cls="flex items-center justify-between"), Div(id=f"rejected-list-{identity_id}"), cls="mt-4 pt-3 border-t border-stone-200") if rejected_count > 0 else None

    return Div(Div(H4("Similar Identities", cls="text-lg font-serif font-bold text-stone-700"), close_btn, cls="flex items-center justify-between mb-3"),
               Div(*cards), Div(load_more, cls="mt-3") if load_more else None, manual_search, rejected, cls="neighbors-sidebar p-4 bg-stone-50 rounded border border-stone-200")


def name_display(identity_id: str, name: str) -> Div:
    """
    Identity name display with edit button.
    Returns the name header component that can be swapped for inline editing.
    """
    display_name = name or f"Identity {identity_id[:8]}..."
    return Div(
        H3(display_name, cls="text-lg font-serif font-bold text-stone-800"),
        Button(
            "Edit",
            hx_get=f"/api/identity/{identity_id}/rename-form",
            hx_target=f"#name-{identity_id}",
            hx_swap="outerHTML",
            cls="ml-2 text-xs text-stone-400 hover:text-stone-600 underline",
            type="button",
        ),
        id=f"name-{identity_id}",
        cls="flex items-center"
    )


def identity_card(
    identity: dict,
    crop_files: set,
    lane_color: str = "stone",
    show_actions: bool = False,
) -> Div:
    """
    Identity group card showing all faces (anchors + candidates).
    UX Intent: Group context with individual face visibility.
    """
    identity_id = identity["identity_id"]
    name = identity.get("name") or f"Identity {identity_id[:8]}..."
    state = identity["state"]

    # Combine anchors (confirmed) and candidates (proposed) for display
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])

    # Show detach button only if identity has more than one face
    can_detach = len(all_face_ids) > 1

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

    if not face_cards:
        return None

    border_colors = {
        "blue": "border-l-blue-500",
        "emerald": "border-l-emerald-500",
        "amber": "border-l-amber-500",
        "red": "border-l-red-500",
    }

    # Sort dropdown for face ordering
    sort_dropdown = Select(
        Option("Sort by Date", value="date", selected=True),
        Option("Sort by Outlier", value="outlier"),
        cls="text-xs border border-stone-300 rounded px-2 py-1",
        hx_get=f"/api/identity/{identity_id}/faces",
        hx_target=f"#faces-{identity_id}",
        hx_swap="innerHTML",
        name="sort",
        hx_trigger="change",
    )

    # Find Similar button (loads neighbors via HTMX)
    find_similar_btn = Button(
        "Find Similar",
        cls="text-sm text-blue-600 hover:text-blue-800 underline",
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
            cls="htmx-indicator text-stone-400 text-sm",
        ),
        id=f"neighbors-{identity_id}",
        cls="mt-4"
    )

    return Div(
        # Header with name, state, and controls
        Div(
            Div(
                name_display(identity_id, identity.get("name")),
                state_badge(state),
                Span(
                    f"{len(face_cards)} face{'s' if len(face_cards) != 1 else ''}",
                    cls="text-xs text-stone-400 ml-2"
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
        # Action buttons based on state
        action_buttons(identity_id) if show_actions and state == "PROPOSED" else None,
        inbox_action_buttons(identity_id) if show_actions and state == "INBOX" else None,
        # Neighbors container (shown when "Find Similar" is clicked)
        neighbors_container,
        cls=f"identity-card bg-stone-50 border border-stone-200 border-l-4 {border_colors.get(lane_color, '')} p-4 rounded-r shadow-sm mb-4",
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
            cls="absolute inset-0 bg-black/50",
            **{"_": "on click add .hidden to #photo-modal"},
        ),
        # Modal content - relative positioning to sit above backdrop
        Div(
            # Header with close button
            Div(
                H2("Photo Context", cls="text-xl font-serif font-bold text-stone-800"),
                Button(
                    "X",
                    cls="text-stone-500 hover:text-stone-700 text-xl font-bold",
                    **{"_": "on click add .hidden to #photo-modal"},
                    type="button",
                    aria_label="Close modal",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-stone-200"
            ),
            # Content area (populated by HTMX)
            Div(
                P("Loading...", cls="text-stone-400 text-center py-8"),
                id="photo-modal-content",
            ),
            cls="bg-white rounded-lg shadow-xl max-w-5xl max-h-[90vh] overflow-auto p-6 relative"
        ),
        id="photo-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[9999]"
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
        "blue": "bg-blue-50/50",
        "emerald": "bg-emerald-50/50",
        "amber": "bg-amber-50/50",
        "red": "bg-red-50/50",
    }
    
    # Fix: Always render the container ID even if empty, so OOB swaps have a target.
    content_area = Div(*cards, id=lane_id, cls="min-h-[50px]") if cards else Div(
        P(
            f"No {title.lower()} identities",
            cls="text-stone-400 italic text-center py-8"
        ),
        id=lane_id,
        cls="min-h-[50px]"
    )

    return Div(
        # Lane header
        Div(
            Span(icon, cls="text-2xl"),
            H2(title, cls="text-xl font-serif font-bold text-stone-700"),
            Span(
                f"({len(cards)})",
                cls="text-sm text-stone-400"
            ),
            cls="flex items-center gap-3 mb-4 pb-2 border-b border-stone-300"
        ),
        # Cards or empty state
        content_area,
        cls=f"mb-8 p-4 rounded {bg_colors.get(color, '')}"
    )


def skipped_section() -> Div:
    """
    Collapsible section for skipped identities.
    Hidden by default, becomes visible when cards are skipped.
    UI-only state - not persisted.
    """
    return Details(
        Summary(
            Span("\u23f8", cls="text-xl"),
            Span("Skipped / Review Later", cls="text-lg font-serif font-bold text-stone-600 ml-2"),
            Span(
                "(0)",
                id="skipped-count",
                cls="text-sm text-stone-400 ml-2"
            ),
            cls="flex items-center cursor-pointer hover:bg-stone-100 p-2 rounded transition-colors"
        ),
        Div(
            P(
                "Cards skipped during this session will appear here.",
                cls="text-stone-400 italic text-center py-4",
                id="skipped-empty-msg"
            ),
            id="skipped-container",
            cls="mt-4"
        ),
        id="skipped-details",
        cls="hidden mb-8 p-4 rounded bg-stone-100/50 border border-stone-200"
    )


# =============================================================================
# ROUTES - PHASE 2: TEACH MODE
# =============================================================================

@rt("/")
def get():
    """
    Main workstation view.
    Renders identities in four lanes by state.
    """
    registry = load_registry()
    crop_files = get_crop_files()

    inbox = registry.list_identities(state=IdentityState.INBOX)
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    contested = registry.list_identities(state=IdentityState.CONTESTED)

    inbox.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    confirmed.sort(key=lambda x: (x.get("name") or "", x.get("updated_at", "")))
    proposed.sort(key=lambda x: x.get("version_id", 0), reverse=True)
    contested.sort(key=lambda x: x.get("version_id", 0), reverse=True)

    has_data = inbox or confirmed or proposed or contested

    if has_data:
        content = Div(
            # Upload area at top
            upload_area(),
            # Inbox lane (new faces awaiting review)
            lane_section("Inbox", inbox, crop_files, "blue", "\ud83d\udce5",
                         show_actions=True, lane_id="inbox-lane") if inbox else None,
            # Proposed lane has action buttons enabled
            lane_section("Proposed", proposed, crop_files, "amber", "?",
                         show_actions=True, lane_id="proposed-lane"),
            lane_section("Confirmed", confirmed, crop_files, "emerald", "\u2713",
                         lane_id="confirmed-lane"),
            lane_section("Contested", contested, crop_files, "red", "\u26a0",
                         lane_id="contested-lane"),
            # Skipped section (UI-only, hidden until cards are skipped)
            skipped_section(),
            cls="max-w-7xl mx-auto"
        )
    else:
        crops_dir = static_path / "crops"
        faces = []
        for f in crops_dir.glob("*.jpg"):
            quality = parse_quality_from_filename(f.name)
            faces.append((f.name, quality))
        faces.sort(key=lambda x: x[1], reverse=True)

        cards = [
            face_card(face_id=fn, crop_url=f"/crops/{fn}", quality=q)
            for fn, q in faces
        ]

        content = Div(
            Div(
                P(
                    "No identity registry found. Showing all faces as uncategorized.",
                    cls="text-amber-700 bg-amber-100 px-4 py-2 rounded text-sm mb-4"
                ),
                Div(
                    *cards,
                    cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4"
                ),
            ),
            cls="max-w-7xl mx-auto"
        )

    style = Style("""
        body {
            background-color: #fafaf9;
            margin: 0;
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
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
    """)

    return Title("Rhodesli Forensic Workstation"), style, Main(
        # Toast container for notifications
        toast_container(),
        Header(
            H1(
                "Rhodesli",
                cls="text-3xl font-serif font-bold text-stone-800 tracking-wide"
            ),
            P(
                "Forensic Identity Workstation",
                cls="text-sm font-mono text-stone-500 mt-1"
            ),
            cls="text-center border-b-2 border-stone-800 pb-4 mb-6"
        ),
        content,
        # Photo context modal (hidden by default)
        photo_modal(),
        cls="p-4 md:p-8"
    )


@rt("/confirm/{identity_id}")
def post(identity_id: str):
    """
    Confirm an identity (move from PROPOSED to CONFIRMED).

    Returns:
        200: Updated identity card
        404: Identity not found
        409: Variance explosion (would corrupt fusion)
        423: Lock contention
    """
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

    # Return updated card (now CONFIRMED, no action buttons)
    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return the card plus a success toast
    return (
        identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        toast("Identity confirmed.", "success"),
    )


@rt("/reject/{identity_id}")
def post(identity_id: str):
    """
    Contest/reject an identity (move to CONTESTED).

    Returns:
        200: Updated identity card (now contested)
        404: Identity not found
        423: Lock contention
    """
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

    # Get image dimensions
    width, height = get_photo_dimensions(photo["filename"])
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
        face_obj = {
            "face_id": face_id,
            "bbox": {
                "x": x1,
                "y": y1,
                "w": x2 - x1,
                "h": y2 - y1,
            },
            "display_name": identity.get("name", "Unidentified") if identity else "Unidentified",
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
            P("Photo not found", cls="text-red-600 font-bold"),
            P(f"ID: {photo_id}", cls="text-stone-500 text-sm font-mono"),
            cls="text-center p-8"
        )
        return (error_content,) if is_partial else (Title("Photo Not Found"), error_content)

    width, height = get_photo_dimensions(photo["filename"])
    if width == 0:
        error_content = Div(
            P("Could not load photo", cls="text-red-600 font-bold"),
            cls="text-center p-8"
        )
        return (error_content,) if is_partial else (Title("Photo Error"), error_content)

    registry = load_registry()

    # Build face overlays with CSS percentages for responsive scaling
    face_overlays = []
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
        display_name = identity.get("name", "Unidentified") if identity else "Unidentified"
        identity_id = identity["identity_id"] if identity else None

        # Determine if this face is selected
        is_selected = face_id == selected_face_id

        # Build the overlay div
        overlay_classes = "face-overlay absolute border-2 cursor-pointer transition-all hover:border-amber-400"
        if is_selected:
            overlay_classes += " border-amber-500 bg-amber-500/20"
        else:
            overlay_classes += " border-emerald-500 bg-emerald-500/10 hover:bg-emerald-500/20"

        overlay = Div(
            # Tooltip on hover
            Span(
                display_name,
                cls="absolute -top-8 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none"
            ),
            cls=f"{overlay_classes} group",
            style=f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;",
            title=display_name,
            # Click navigates to identity (if assigned)
            hx_get=f"/" if identity_id else None,
            hx_push_url="true" if identity_id else None,
            data_face_id=face_id,
            data_identity_id=identity_id or "",
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
                f"{len(photo['faces'])} face{'s' if len(photo['faces']) != 1 else ''} detected",
                cls="text-stone-500 text-sm"
            ),
            P(
                f"{width} x {height} px",
                cls="text-stone-400 text-xs font-mono"
            ),
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
                cls="text-stone-600 hover:text-stone-800 mb-4 inline-block"
            ),
            H1(
                "Photo Context",
                cls="text-2xl font-serif font-bold text-stone-800 mb-4"
            ),
            content,
            cls="p-4 md:p-8 max-w-6xl mx-auto"
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
    from core.neighbors import find_nearest_neighbors
    total_to_fetch = offset + limit + 1
    all_neighbors = find_nearest_neighbors(
        identity_id, registry, photo_registry, face_data, limit=total_to_fetch
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
            cls="htmx-indicator text-stone-400 text-sm",
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
            P("Search unavailable.", cls="text-stone-400 italic text-sm"),
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
            P("No hidden matches.", cls="text-stone-400 text-xs italic"),
        )

    crop_files = get_crop_files()
    items = []

    for rejected_id in rejected_ids:
        try:
            rejected_identity = registry.get_identity(rejected_id)
        except KeyError:
            continue

        name = rejected_identity.get("name") or f"Identity {rejected_id[:8]}..."

        # Resolve thumbnail using anchor faces, then candidates
        thumbnail_img = None
        anchor_face_ids = registry.get_anchor_face_ids(rejected_id)
        for face_id in anchor_face_ids:
            crop_url = resolve_face_image_url(face_id, crop_files)
            if crop_url:
                thumbnail_img = Img(
                    src=crop_url,
                    alt=name,
                    cls="w-8 h-8 object-cover rounded border border-stone-200"
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
                        cls="w-8 h-8 object-cover rounded border border-stone-200"
                    )
                    break

        if thumbnail_img is None:
            thumbnail_img = Div(cls="w-8 h-8 bg-stone-200 rounded")

        unblock_btn = Button(
            "Unblock",
            cls="px-2 py-0.5 text-xs text-blue-600 hover:text-blue-800 border border-blue-200 rounded hover:bg-blue-50",
            hx_post=f"/api/identity/{identity_id}/unreject/{rejected_id}",
            hx_target=f"#rejected-item-{rejected_id}",
            hx_swap="outerHTML",
            type="button",
        )

        items.append(
            Div(
                thumbnail_img,
                Span(name, cls="text-xs text-stone-600 truncate flex-1 mx-2"),
                unblock_btn,
                id=f"rejected-item-{rejected_id}",
                cls="flex items-center py-1.5 border-b border-stone-100 last:border-0",
            )
        )

    close_list_btn = Button(
        "Hide",
        cls="text-xs text-stone-400 hover:text-stone-600",
        hx_get=f"/api/identity/{identity_id}/rejected/close",
        hx_target=f"#rejected-list-{identity_id}",
        hx_swap="innerHTML",
        type="button",
    )

    return Div(
        Div(
            Span("Hidden Matches", cls="text-xs font-medium text-stone-500"),
            close_list_btn,
            cls="flex items-center justify-between mb-2",
        ),
        Div(*items),
        cls="mt-2 bg-white rounded border border-stone-200 p-2",
    )


@rt("/api/identity/{identity_id}/rejected/close")
def get(identity_id: str):
    """Close the rejected identities list."""
    return ""


@rt("/api/identity/{source_id}/reject/{target_id}")
def post(source_id: str, target_id: str):
    """
    Record that two identities are NOT the same person (D2, D4).

    This is the "Not Same Person" action from Find Similar mode.
    The rejected identity will no longer appear in Find Similar results.

    Returns:
        200: Success with empty div (triggers HTMX removal) + toast
        404: Identity not found
        423: Lock contention
    """
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
def post(source_id: str, target_id: str):
    """
    Undo "Not Same Person" rejection (D5).

    This reverses a previous reject_identity_pair, allowing the target
    identity to reappear in Find Similar results.

    Returns:
        200: Success toast
        404: Identity not found
        423: Lock contention
    """
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
def post(target_id: str, source_id: str, source: str = "web"):
    """
    Merge source identity into target identity.

    Args:
        target_id: Identity to merge into
        source_id: Identity to be absorbed
        source: Origin of merge request ("web" or "manual_search")

    Returns:
        200: Success with updated identity card
        404: Identity not found
        409: Merge blocked (co-occurrence or already merged)
        423: Lock contention
    """
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

    current_name = identity.get("name") or ""

    return Form(
        Input(
            name="name",
            value=current_name,
            placeholder="Enter name...",
            cls="border border-stone-300 rounded px-2 py-1 text-sm w-48",
            autofocus=True,
        ),
        Button(
            "Save",
            type="submit",
            cls="ml-2 bg-emerald-600 text-white px-2 py-1 rounded text-sm hover:bg-emerald-700",
        ),
        Button(
            "Cancel",
            type="button",
            hx_get=f"/api/identity/{identity_id}/name-display",
            hx_target=f"#name-{identity_id}",
            hx_swap="outerHTML",
            cls="ml-1 text-stone-500 hover:text-stone-700 text-sm underline",
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
def post(identity_id: str, name: str = ""):
    """
    Rename an identity.

    Form fields:
    - name: New name (required, max 100 chars)

    Returns:
        200: Updated name display component
        400: Empty name after stripping
        404: Identity not found
        423: Lock contention
    """
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
def post(face_id: str):
    """
    Detach a face from its identity into a new identity.

    Returns:
        200: OOB delete of face card + success toast
        404: Face or identity not found
        409: Cannot detach (only face in identity)
        423: Lock contention
    """
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

    # 1. Prepare safe ID for removing the OLD face card
    face_card_id = make_css_id(face_id)
    
    # 2. Render the NEW identity card
    new_identity = registry.get_identity(result["to_identity_id"])
    crop_files = get_crop_files()
    new_card_html = identity_card(
        new_identity, 
        crop_files, 
        lane_color="amber", # New identities are PROPOSED
        show_actions=True
    )

    return (
        # A. Delete the old face card from its current container
        Div(id=face_card_id, hx_swap_oob="delete"),
        
        # B. Insert the new identity card at the top of the Proposed lane
        Div(new_card_html, hx_swap_oob="afterbegin:#proposed-lane"),
        
        # C. Success toast
        toast(f"Face detached into new identity.", "success"),
    )


# --- INSTRUMENTATION SKIP ENDPOINT ---
@rt("/api/identity/{id}/skip")
def post(id: str):
    """
    Log the skip action (which is otherwise UI-only).
    """
    get_event_recorder().record("SKIP", {"identity_id": id})
    # No return needed as this is fire-and-forget for logging
    # The UI handles the DOM move client-side
    return Response(status_code=200)
# -------------------------------------


# =============================================================================
# ROUTES - INBOX INGESTION
# =============================================================================

@rt("/upload")
async def post(file: UploadFile):
    """
    Accept file upload and spawn subprocess for processing.

    Returns HTML partial with upload status and polling.
    """
    import subprocess
    import uuid

    if not file or not file.filename:
        return Div(
            P("No file selected.", cls="text-red-600 text-sm"),
            cls="p-2"
        )

    # Generate unique job ID
    job_id = str(uuid.uuid4())[:8]

    # Save uploaded file to temp location
    uploads_dir = data_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_filename = file.filename.replace(" ", "_").replace("/", "_")
    upload_path = uploads_dir / f"{job_id}_{safe_filename}"

    # Write file content
    content = await file.read()
    with open(upload_path, "wb") as f:
        f.write(content)

    # Spawn subprocess for processing
    # Use subprocess.Popen for non-blocking execution
    ingest_script = project_root / "core" / "ingest_inbox.py"
    subprocess.Popen(
        [sys.executable, str(ingest_script), "--file", str(upload_path), "--job-id", job_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Return status component that polls for completion
    return Div(
        P(f"Processing {file.filename}...", cls="text-stone-600 text-sm"),
        Span("\u23f3", cls="animate-pulse"),
        hx_get=f"/upload/status/{job_id}",
        hx_trigger="every 2s",
        hx_swap="outerHTML",
        cls="p-2 bg-blue-50 rounded flex items-center gap-2"
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
            P("Starting...", cls="text-stone-600 text-sm"),
            Span("\u23f3", cls="animate-pulse"),
            hx_get=f"/upload/status/{job_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            cls="p-2 bg-blue-50 rounded flex items-center gap-2"
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
                P(progress_text, cls="text-stone-600 text-sm"),
                # Real progress bar based on actual completion
                Div(
                    Div(cls=f"h-1 bg-blue-500 rounded", style=f"width: {pct}%"),
                    cls="w-full bg-stone-200 rounded h-1 mt-1"
                ),
            ]
            if faces > 0:
                progress_elements.append(
                    P(f"{faces} face(s) found so far", cls="text-stone-400 text-xs mt-1")
                )
        else:
            progress_elements = [
                P("Processing...", cls="text-stone-600 text-sm"),
                Span("\u23f3", cls="animate-pulse"),
            ]

        return Div(
            *progress_elements,
            hx_get=f"/upload/status/{job_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            cls="p-2 bg-blue-50 rounded"
        )

    if status["status"] == "error":
        # Total failure
        error_msg = status.get("error", "Unknown error")
        errors = status.get("errors", [])

        elements = [P(f"Error: {error_msg}", cls="text-red-600 text-sm font-medium")]

        # Show per-file errors if available
        if errors:
            error_list = Ul(
                *[Li(f"{e['filename']}: {e['error']}", cls="text-xs") for e in errors[:5]],
                cls="text-red-500 mt-1 ml-4 list-disc"
            )
            elements.append(error_list)
            if len(errors) > 5:
                elements.append(P(f"... and {len(errors) - 5} more errors", cls="text-red-400 text-xs"))

        return Div(*elements, cls="p-2 bg-red-50 rounded")

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
                P(f"\u26a0 {failed} image(s) failed", cls="text-red-500 text-sm")
            )
            # Show first few errors
            if errors:
                error_summary = ", ".join(e["filename"] for e in errors[:3])
                if len(errors) > 3:
                    error_summary += f", +{len(errors) - 3} more"
                elements.append(P(f"Failed: {error_summary}", cls="text-red-400 text-xs"))

        elements.append(
            A("Refresh to see inbox", href="/", cls="text-blue-600 hover:underline text-xs mt-1 block")
        )

        return Div(*elements, cls="p-2 bg-amber-50 rounded")

    # Success (all files processed successfully)
    faces = status.get("faces_extracted", 0)
    identities = len(status.get("identities_created", []))
    total = status.get("total_files")

    success_text = f"\u2713 {faces} face(s) extracted"
    if total and total > 1:
        success_text = f"\u2713 {faces} face(s) extracted from {total} images"
    success_text += f", {identities} added to Inbox"

    return Div(
        P(success_text, cls="text-emerald-600 text-sm font-medium"),
        A("Refresh to see inbox", href="/", cls="text-blue-600 hover:underline text-xs ml-2"),
        cls="p-2 bg-emerald-50 rounded flex items-center"
    )


@rt("/inbox/{identity_id}/review")
def post(identity_id: str):
    """
    Move identity from INBOX to PROPOSED state.

    Returns updated identity card in proposed lane.
    """
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
def post(identity_id: str):
    """
    Confirm identity from INBOX state (INBOX → CONFIRMED).

    Returns updated identity card in confirmed lane.
    """
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

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now CONFIRMED)
    return (
        identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        toast("Identity confirmed.", "success"),
    )


@rt("/inbox/{identity_id}/reject")
def post(identity_id: str):
    """
    Reject identity from INBOX state (INBOX → REJECTED).

    Returns updated identity card with REJECTED state.
    """
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

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now REJECTED)
    return (
        identity_card(updated_identity, crop_files, lane_color="rose", show_actions=False),
        toast("Identity rejected.", "success"),
    )


if __name__ == "__main__":
    # Startup diagnostics: log raw_photos directory info
    print(f"[startup] raw_photos directory: {photos_path.resolve()}")
    if photos_path.exists():
        files = list(photos_path.iterdir())[:3]
        print(f"[startup] first 3 files: {[f.name for f in files]}")
    else:
        print("[startup] WARNING: raw_photos directory does not exist")
    serve()