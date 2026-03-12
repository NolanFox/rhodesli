"""
Photo routes extracted from app/main.py.

All /photo/* and /api/photo/* routes plus photo-exclusive helpers.
Shared helpers (caches, registries, UI builders) remain in app.main.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fasthtml.common import *
from starlette.datastructures import UploadFile
from starlette.responses import FileResponse, JSONResponse

from core.ui_safety import ensure_utf8_display
from core import storage

# Import route decorator only (bound once, never reassigned)
from app.main import rt
from app.utils import photo_url

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod

logger = logging.getLogger(__name__)


# =============================================================================
# HELPERS — Photo-exclusive (not used outside photo routes)
# =============================================================================


def _load_corrections_log() -> dict:
    """Delegate to main module so test patches on app.main work."""
    return _main_mod._load_corrections_log()


def _save_corrections_log(data: dict):
    """Delegate to main module so test patches on app.main work."""
    return _main_mod._save_corrections_log(data)


def _load_photo_bytes(photo_id: str, filename: str) -> bytes | None:
    """Delegate to main module so test patches on app.main work."""
    return _main_mod._load_photo_bytes(photo_id, filename)


# =============================================================================
# ROUTES — Photo API (metadata, editing, alignment)
# =============================================================================


@rt("/api/photo/{photo_id}/ai-sections")
def get(photo_id: str, sess=None):
    """Return refreshed AI Analysis sections content (used after re-analyze)."""
    is_admin = not _main_mod._check_admin(sess)
    section = _main_mod._build_ai_analysis_section(photo_id, is_admin=is_admin)
    if not section:
        return Div()
    # The full section is a Section > Div > [header, reanalyze-result, sections-div, ...]
    # We just need to rebuild and return the sections.
    # Simplest: return the full section and let HTMX swap it in.
    # But our target is the inner sections div. Let's rebuild just sections.
    labels = _main_mod._load_date_labels()
    label = labels.get(photo_id)
    if not label:
        return Div()
    return _main_mod._build_ai_sections_list(photo_id, label, is_admin)


@rt("/api/photo/{photo_id}")
def get(photo_id: str):
    """
    Get photo metadata with face bounding boxes.

    Returns JSON with:
    - photo_url: Static path to the photo
    - image_width, image_height: Original dimensions
    - faces: List of face objects with bbox, face_id, display_name, identity_id
    """
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return JSONResponse(
            {"error": "Photo not found", "photo_id": photo_id},
            status_code=404,
        )

    # Get image dimensions for face overlay positioning
    width, height = _main_mod.get_photo_dimensions(photo["filename"])
    if width == 0 or height == 0:
        return JSONResponse(
            {"error": "Could not read photo dimensions", "photo_id": photo_id},
            status_code=404,
        )

    # Build face list with identity information
    registry = _main_mod.load_registry()
    faces = []

    for face_data in photo["faces"]:
        face_id = face_data["face_id"]
        if not _main_mod.has_displayable_face_bbox(face_data):
            continue
        bbox = face_data["bbox"]  # [x1, y1, x2, y2]

        # Find identity for this face
        identity = _main_mod.get_identity_for_face(registry, face_id)

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

    return JSONResponse(
        {
            "photo_url": photo_url(photo["filename"]),
            "image_width": width,
            "image_height": height,
            "faces": faces,
        }
    )


@rt("/api/photo/{photo_id}/collection")
def post(photo_id: str, sess, collection: str = ""):
    """
    Update a photo's collection (classification) label.

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _main_mod._check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = _main_mod.load_photo_registry()
    photo_path = photo_reg.get_photo_path(photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    photo_reg.set_collection(photo_id, collection.strip())
    _main_mod.save_photo_registry(photo_reg)
    _main_mod._photo_cache = None
    _main_mod._photo_id_aliases = None
    return Div(
        Span(f"Collection updated to: {collection.strip() or '(none)'}", cls="text-sm text-emerald-400"),
        id=f"collection-status-{photo_id}",
    )


@rt("/api/photo/{photo_id}/source")
def post(photo_id: str, sess, source: str = ""):
    """
    Update a photo's source (provenance/origin) label.

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _main_mod._check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = _main_mod.load_photo_registry()
    photo_path = photo_reg.get_photo_path(photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    photo_reg.set_source(photo_id, source.strip())
    _main_mod.save_photo_registry(photo_reg)
    _main_mod._photo_cache = None
    _main_mod._photo_id_aliases = None
    return Div(
        Span(f"Source updated to: {source.strip() or '(none)'}", cls="text-sm text-emerald-400"),
        id=f"source-status-{photo_id}",
    )


@rt("/api/photo/{photo_id}/source-url")
def post(photo_id: str, sess, source_url: str = ""):
    """
    Update a photo's source URL (citation link).

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _main_mod._check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = _main_mod.load_photo_registry()
    photo_path = photo_reg.get_photo_path(photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    photo_reg.set_source_url(photo_id, source_url.strip())
    _main_mod.save_photo_registry(photo_reg)
    _main_mod._photo_cache = None
    _main_mod._photo_id_aliases = None
    if source_url.strip():
        return Div(
            Span("Source URL: ", cls="text-slate-500 text-sm"),
            A(
                source_url.strip(),
                href=source_url.strip(),
                target="_blank",
                rel="noopener",
                cls="text-indigo-400 hover:text-indigo-300 underline text-sm",
            ),
            id=f"source-url-status-{photo_id}",
        )
    return Div(
        Span("Source URL cleared", cls="text-sm text-emerald-400"),
        id=f"source-url-status-{photo_id}",
    )


@rt("/api/photo/{photo_id}/correct-date")
async def post(photo_id: str, correction_year: int = None, sess=None):
    """Submit a date correction for a photo. Updates date labels and logs the correction.

    Auth: any logged-in user can correct (or admin when auth disabled).
    Returns updated date section HTML via HTMX swap.
    """
    if _main_mod.is_auth_enabled():
        user = _main_mod.get_current_user(sess or {})
        if not user:
            return Response("", status_code=401)
        contributor_email = user.email
        contributor_type = "admin" if user.is_admin else "registered"
    else:
        contributor_email = "local"
        contributor_type = "admin"

    if not correction_year or correction_year < 1850 or correction_year > 2030:
        return Div(
            Span("Invalid year (1850-2030)", cls="text-sm text-red-400"),
            id=f"date-section-{photo_id[:8]}",
        )

    # Load current label
    labels = _main_mod._load_date_labels()
    label = labels.get(photo_id)
    if not label:
        return Div(
            Span("No date label found", cls="text-sm text-red-400"),
            id=f"date-section-{photo_id[:8]}",
        )

    # Record correction
    old_decade = label.get("estimated_decade")
    old_year = label.get("best_year_estimate")
    new_decade = (correction_year // 10) * 10

    correction_entry = {
        "id": f"corr_{uuid.uuid4().hex[:12]}",
        "photo_id": photo_id,
        "field": "estimated_decade",
        "old_value": {"decade": old_decade, "year": old_year},
        "new_value": {"decade": new_decade, "year": correction_year},
        "old_source": label.get("source", "gemini"),
        "new_source": "human",
        "contributor_email": contributor_email,
        "contributor_type": contributor_type,
        "status": "applied",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Save correction log
    log = _load_corrections_log()
    log["corrections"].append(correction_entry)
    _save_corrections_log(log)

    # Update the in-memory label cache
    label["estimated_decade"] = new_decade
    label["best_year_estimate"] = correction_year
    label["confidence"] = "high"
    label["source"] = "human"
    label["probable_range"] = [correction_year - 2, correction_year + 2]

    # Return updated date section with verified styling
    return Div(
        Div(
            P(f"circa {correction_year}", cls="text-lg font-serif text-amber-200 mb-1 inline"),
            Span("\u2713 Verified", cls="text-[11px] text-emerald-400 ml-2"),
            cls="flex items-center",
        ),
        Div(
            Span(
                "Confidence: high",
                cls="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400",
            ),
            cls="flex items-center gap-2",
        ),
        P(
            "Thanks! Your correction helps improve our AI.",
            cls="text-[11px] text-emerald-400/70 mt-2 italic",
        ),
        id=f"date-section-{photo_id[:8]}",
        data_testid="verified-field",
    )


# --- Face Alignment API (PRD-015 coordinate bridging) ---


@rt("/api/face-alignment/{photo_id}")
async def post(photo_id: str, sess=None):
    """
    Run Gemini face alignment for a specific photo.
    Admin-only action (follows Gatekeeper pattern, Lesson 19).

    1. Load photo from R2/local storage
    2. Load InsightFace face detections from embeddings
    3. Normalize EXIF orientation
    4. Run coordinate bridging with Gemini
    5. Store results
    6. Return aligned descriptions
    """
    from starlette.responses import JSONResponse as _JSONResponse
    from app.face_alignment import (
        FaceDetection,
        cache_alignment,
        run_face_alignment,
        save_alignment,
    )

    admin_err = _main_mod._check_admin(sess)
    if admin_err:
        return admin_err

    # Load photo metadata
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return _JSONResponse(
            {"error": "Photo not found", "photo_id": photo_id},
            status_code=404,
        )

    # Build FaceDetection objects from embeddings
    faces = []
    registry = _main_mod.load_registry()
    for face_data in photo["faces"]:
        if not _main_mod.has_displayable_face_bbox(face_data):
            continue
        identity = _main_mod.get_identity_for_face(registry, face_data["face_id"])
        faces.append(
            FaceDetection(
                face_id=face_data["face_id"],
                bbox=face_data["bbox"],
                face_index=face_data.get("face_index", 0),
                det_score=face_data.get("det_score", 0),
                quality=face_data.get("quality", 0),
                identity_name=identity.get("name") if identity else None,
            )
        )

    if not faces:
        return _JSONResponse(
            {"error": "No faces detected in this photo", "photo_id": photo_id},
            status_code=400,
        )

    # Load image bytes
    image_bytes = _load_photo_bytes(photo_id, photo["filename"])
    if not image_bytes:
        return _JSONResponse(
            {"error": "Could not load photo image", "photo_id": photo_id},
            status_code=500,
        )

    # Run face alignment
    api_key = os.getenv("GEMINI_API_KEY", "")
    result = await run_face_alignment(
        photo_id=photo_id,
        image_bytes=image_bytes,
        faces=faces,
        api_key=api_key,
    )

    if result.error:
        return _JSONResponse(
            {"error": result.error, "photo_id": photo_id},
            status_code=500,
        )

    # Cache and save (Supabase-first, JSON fallback — AD-152)
    cache_alignment(result)
    try:
        save_alignment(result, output_dir=_main_mod.data_path)
    except Exception as e:
        logging.warning(f"Failed to save alignment: {e}")

    # Return rendered HTML for HTMX swap (the Detect Faces button uses hx_post)
    section = _main_mod._build_face_alignment_section(photo_id, is_admin=True)
    if section is not None:
        return section

    return _JSONResponse(result.to_dict())


@rt("/api/face-alignment/{photo_id}")
def get(photo_id: str):
    """
    Get stored face alignment results for a photo.
    Returns cached results if available, null if not yet aligned.
    Public endpoint (descriptions help with identification).
    """
    from starlette.responses import JSONResponse as _JSONResponse
    from app.face_alignment import get_cached_alignment, load_alignments

    # Check in-memory cache first
    cached = get_cached_alignment(photo_id)
    if cached:
        return _JSONResponse(cached.to_dict())

    # Check Supabase then JSON fallback
    alignments = load_alignments(_main_mod.data_path)
    if photo_id in alignments:
        return _JSONResponse(alignments[photo_id])

    return _JSONResponse(
        {"status": "not_aligned", "photo_id": photo_id},
        status_code=200,
    )


# =============================================================================
# ROUTES — Photo View & Download
# =============================================================================


@rt("/photo/{photo_id}")
def get(
    photo_id: str,
    face: str = None,
    identity_id: str = None,
    sort_by: str = "date_asc",
    seq: bool = False,
    sess=None,
    request=None,
):
    """
    Public shareable photo page with face overlays and person cards.

    This is the page people share on Facebook, WhatsApp, email, etc.
    No authentication required — anyone can view.

    Query params:
    - face: Optional face_id to highlight
    - identity_id: Optional person context for prev/next photo navigation
    - sort_by: Optional person-gallery sort mode for prev/next navigation
    - seq: If True for admins, enter the standalone speed-loop flow
    """
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    user_is_admin = (user.is_admin if user else False) if _main_mod.is_auth_enabled() else True
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    return _main_mod.public_photo_page(
        photo_id,
        selected_face_id=face,
        identity_id=identity_id,
        sort_by=sort_by,
        seq_mode=seq and user_is_admin,
        user=user,
        is_admin=user_is_admin,
        community_slug=community_slug,
    )


@rt("/photo/{photo_id}/partial")
def get(
    photo_id: str,
    face: str = None,
    prev_id: str = None,
    next_id: str = None,
    nav_idx: int = -1,
    nav_total: int = 0,
    identity_id: str = None,
    sort_by: str = "date_asc",
    from_compare: bool = False,
    seq: bool = False,
    sess=None,
    request=None,
):
    """
    Render photo view partial for HTMX modal injection.

    Optional navigation context:
    - prev_id/next_id: Adjacent photo IDs for prev/next buttons
    - nav_idx/nav_total: Current position for "X of Y" display
    - identity_id: Identity context for computing prev/next from identity's photos
    - from_compare: If True, show "Back to Compare" button (opened via compare modal)
    - seq: If True, activate "Name These Faces" sequential mode
    """
    user_is_admin = (
        (_main_mod.get_current_user(sess or {}).is_admin if _main_mod.get_current_user(sess or {}) else False)
        if _main_mod.is_auth_enabled()
        else True
    )
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    return _main_mod.photo_view_content(
        photo_id,
        selected_face_id=face,
        is_partial=True,
        prev_id=prev_id,
        next_id=next_id,
        nav_idx=nav_idx,
        nav_total=nav_total,
        identity_id=identity_id,
        sort_by=sort_by,
        is_admin=user_is_admin,
        from_compare=from_compare,
        seq_mode=seq and user_is_admin,
        community_slug=community_slug,
    )


@rt("/photo/{photo_id}/download")
def get(photo_id: str):
    """
    Download the original full-resolution photo.

    Public endpoint — no auth required.
    Returns the photo file with Content-Disposition: attachment header.
    """
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return Response("Photo not found", status_code=404)

    filename = photo["filename"]
    basename = Path(filename).name

    # In R2 mode, redirect to the R2 URL (can't serve local file)
    if storage.is_r2_mode():
        download_url = photo_url(filename)
        return Response(status_code=302, headers={"Location": download_url})

    # Local mode: serve from filesystem
    photo_path = _main_mod.photos_path / basename
    if not photo_path.exists():
        return Response("Photo file not found", status_code=404)

    return FileResponse(
        str(photo_path),
        filename=basename,
        headers={"Content-Disposition": f'attachment; filename="{basename}"'},
    )


# =============================================================================
# ROUTES — Photo Metadata (BE-012)
# =============================================================================


@rt("/api/photo/{photo_id}/metadata")
def post(
    photo_id: str,
    date_taken: str = "",
    location: str = "",
    caption: str = "",
    occasion: str = "",
    donor: str = "",
    notes: str = "",
    back_image: str = "",
    back_transcription: str = "",
    sess=None,
):
    """Update photo metadata. Admin-only (BE-012)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    metadata = {}
    if date_taken.strip():
        metadata["date_taken"] = date_taken.strip()
    if location.strip():
        metadata["location"] = location.strip()
    if caption.strip():
        metadata["caption"] = caption.strip()
    if occasion.strip():
        metadata["occasion"] = occasion.strip()
    if donor.strip():
        metadata["donor"] = donor.strip()
    if notes.strip():
        metadata["notes"] = notes.strip()
    if back_image.strip():
        metadata["back_image"] = back_image.strip()
    if back_transcription.strip():
        metadata["back_transcription"] = back_transcription.strip()

    if not metadata:
        return _main_mod.toast("No metadata provided.", "warning")

    photo_registry = _main_mod.load_photo_registry()
    if not photo_registry.set_metadata(photo_id, metadata):
        return _main_mod.toast("Photo not found.", "error")
    _main_mod.save_photo_registry(photo_registry)

    return _main_mod.toast(f"Photo metadata updated ({len(metadata)} field(s)).", "success")


@rt("/api/photo/{photo_id}/media-group")
def get(photo_id: str):
    """Return all related media for a photo's media group.

    Returns JSON with group_id and items list containing each member's
    photo_id, role (front/back), and URL.
    """
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return JSONResponse(
            {"error": "Photo not found", "photo_id": photo_id},
            status_code=404,
        )

    group_id = photo.get("media_group_id", photo_id)
    items = [
        {
            "photo_id": photo_id,
            "role": photo.get("media_role", "front"),
            "url": photo_url(photo.get("filename", "")),
        }
    ]

    # Add back image if it exists
    back_image = photo.get("back_image", "")
    if back_image:
        items.append(
            {
                "photo_id": f"{photo_id}_back",
                "role": "back",
                "url": photo_url(back_image),
            }
        )

    return JSONResponse({"group_id": group_id, "items": items})


@rt("/api/photo/{photo_id}/back-image")
async def post(photo_id: str, file: UploadFile = None, back_transcription: str = "", sess=None):
    """Upload a back image for a photo and optionally add transcription. Admin-only.

    Saves the file locally AND uploads to R2 if in R2 mode (production).
    Updates photo metadata with back_image filename and media_role fields.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not file or not file.filename:
        return _main_mod.toast("No file selected.", "warning")

    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return _main_mod.toast(f"File type '{ext}' not allowed. Use .jpg, .png, or .webp.", "error")

    # Read file content
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        return _main_mod.toast("File too large. Maximum is 50 MB.", "error")

    # Generate back image filename: {original_stem}_back{ext}
    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return _main_mod.toast("Photo not found.", "error")

    photo_registry = _main_mod.load_photo_registry()
    original_path = photo.get("path", photo.get("filename", ""))
    original_stem = Path(original_path).stem
    back_filename = f"{original_stem}_back{ext}"

    # Determine content type from extension
    content_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    content_type = content_types.get(ext, "image/jpeg")

    # Save to raw_photos/ (local dev) or staging (production)
    raw_photos_dir = Path("raw_photos")
    if raw_photos_dir.exists():
        save_path = raw_photos_dir / back_filename
        save_path.write_bytes(content)
    else:
        # Staging for production upload
        staging_dir = _main_mod.data_path / "staging" / "back_images"
        staging_dir.mkdir(parents=True, exist_ok=True)
        save_path = staging_dir / back_filename
        save_path.write_bytes(content)

    # Upload to R2 if in R2 mode (production) — uses storage helper
    if storage.is_r2_mode() and storage.can_write_r2():
        try:
            r2_key = f"raw_photos/{back_filename}"
            storage.upload_bytes_to_r2(r2_key, content, content_type)
            logger.info(f"Uploaded back image to R2: {r2_key}")
        except Exception as e:
            logger.error(f"Failed to upload back image to R2: {e}")
            return _main_mod.toast(f"File saved locally but R2 upload failed: {e}", "warning")
    elif storage.is_r2_mode():
        logger.warning("R2 credentials not configured — back image saved locally only")

    # Update photo metadata with back_image and media group fields
    metadata = {
        "back_image": back_filename,
        "media_role": "front",  # Mark the front photo explicitly
        "media_group_id": photo_id,  # Group ID is the front photo's ID
        "related_media": [{"photo_id": f"{photo_id}_back", "role": "back"}],
    }
    if back_transcription.strip():
        metadata["back_transcription"] = back_transcription.strip()
    photo_registry.set_metadata(photo_id, metadata)
    _main_mod.save_photo_registry(photo_registry)

    # Invalidate caches so the flip button appears immediately
    _main_mod._invalidate_all_caches()

    # Return success + reload page so flip button appears
    return Div(
        P("Back image uploaded successfully!", cls="text-emerald-400 text-sm font-medium"),
        P("Reloading to show the Turn Over button...", cls="text-slate-400 text-xs mt-1"),
        Script("setTimeout(function(){ window.location.reload(); }, 1200);"),
        cls="p-3 bg-emerald-900/20 rounded-lg border border-emerald-700/30",
    )


@rt("/api/photo/{photo_id}/back-transcription")
def post(photo_id: str, back_transcription: str = "", sess=None):
    """Update the back transcription for a photo. Admin-only."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not back_transcription.strip():
        return _main_mod.toast("No transcription provided.", "warning")

    photo_registry = _main_mod.load_photo_registry()
    if not photo_registry.set_metadata(photo_id, {"back_transcription": back_transcription.strip()}):
        return _main_mod.toast("Photo not found.", "error")
    _main_mod.save_photo_registry(photo_registry)

    return _main_mod.toast("Transcription saved.", "success")


@rt("/api/photo/{photo_id}/transform")
def post(photo_id: str, transform: str = "", field: str = "transform", sess=None):
    """Set non-destructive image transformation. Admin-only.

    transform: The transform to apply (e.g., 'rotate:90', 'flipH', 'reset')
    field: 'transform' (front image) or 'back_transform' (back image)
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if field not in {"transform", "back_transform"}:
        return _main_mod.toast("Invalid field.", "error")

    photo = _main_mod.get_photo_metadata(photo_id)
    if not photo:
        return _main_mod.toast("Photo not found.", "error")

    photo_registry = _main_mod.load_photo_registry()
    if transform == "reset":
        new_transform = ""
    else:
        # Append to existing transform (or start fresh)
        existing = photo.get(field, "")
        if existing:
            new_transform = f"{existing},{transform}"
        else:
            new_transform = transform

    photo_registry.set_metadata(photo_id, {field: new_transform})
    _main_mod.save_photo_registry(photo_registry)

    # Return the CSS transform for live preview
    css_transform = _main_mod.parse_transform_to_css(new_transform)
    css_filter = _main_mod.parse_transform_to_filter(new_transform)
    return Div(
        P(f"Transform: {new_transform}" if new_transform else "Transform reset.", cls="text-xs text-slate-400"),
        Script(f"""
            var img = document.querySelector('.photo-hero, .photo-flip-front img');
            if (img) {{
                img.style.transform = '{css_transform}';
                img.style.filter = '{css_filter}';
            }}
        """)
        if css_transform or css_filter or transform == "reset"
        else None,
        cls="mt-1",
    )


@rt("/api/photo/{photo_id}/confirm-date")
async def post(photo_id: str, sess=None):
    """Confirm AI date estimate — sets source to 'human' without changing the value."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    labels = _main_mod._load_date_labels()
    label = labels.get(photo_id)
    if not label:
        return Div(Span("Label not found", cls="text-red-400"), id=f"review-{photo_id[:8]}")

    # Log confirmation
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    correction_entry = {
        "id": f"corr_{uuid.uuid4().hex[:12]}",
        "photo_id": photo_id,
        "field": "estimated_decade",
        "old_value": {"decade": label.get("estimated_decade"), "year": label.get("best_year_estimate")},
        "new_value": {"decade": label.get("estimated_decade"), "year": label.get("best_year_estimate")},
        "old_source": label.get("source", "gemini"),
        "new_source": "human",
        "contributor_email": user.email if user else "local",
        "contributor_type": "admin",
        "status": "confirmed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log = _load_corrections_log()
    log["corrections"].append(correction_entry)
    _save_corrections_log(log)

    # Update in-memory label
    label["source"] = "human"

    return Div(
        Span("\u2713 Confirmed", cls="text-emerald-400 text-sm"),
        cls="p-3 bg-emerald-950/30 rounded-lg border border-emerald-700/30 text-center",
        id=f"review-{photo_id[:8]}",
    )
