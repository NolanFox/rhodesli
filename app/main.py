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
import os
import random
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
    MATCH_THRESHOLD_LOW,
    MATCH_THRESHOLD_MEDIUM,
    MATCH_THRESHOLD_MODERATE,
    MATCH_THRESHOLD_VERY_HIGH,
    HOST,
    PORT,
    DEBUG,
    PROCESSING_ENABLED,
    DATA_DIR,
    PHOTOS_DIR,
    SYNC_API_TOKEN,
)
from core.ui_safety import ensure_utf8_display
from core import storage
from app.auth import (
    is_auth_enabled, SESSION_SECRET, INVITE_CODES,
    get_current_user, User, ADMIN_EMAILS,
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

# Canonical site URL for Open Graph tags and sharing
SITE_URL = os.getenv("SITE_URL", "https://rhodesli.nolanandrewfox.com")

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
                    if (modal) {
                        // Update the modal message based on the triggering element
                        var trigger = evt.detail.elt;
                        var msgEl = document.getElementById('login-modal-message');
                        if (msgEl && trigger) {
                            var action = trigger.getAttribute('data-auth-action') ||
                                         trigger.innerText.trim() || 'do that';
                            msgEl.textContent = 'You need to sign in to ' + action.toLowerCase() + '.';
                        }
                        modal.classList.remove('hidden');
                    }
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
        # Mobile sidebar toggle
        Script("""
            function toggleSidebar() {
                var sidebar = document.getElementById('sidebar');
                var overlay = document.getElementById('sidebar-overlay');
                if (sidebar && overlay) {
                    sidebar.classList.toggle('-translate-x-full');
                    overlay.classList.toggle('hidden');
                }
            }
            function closeSidebar() {
                var sidebar = document.getElementById('sidebar');
                var overlay = document.getElementById('sidebar-overlay');
                if (sidebar && overlay) {
                    sidebar.classList.add('-translate-x-full');
                    overlay.classList.add('hidden');
                }
            }
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
        data_path / "staging",
        data_path / "inbox",
        data_path / "cleanup_backups",
        static_path / "crops",
        Path(__file__).resolve().parent.parent / "logs",
    ]
    for dir_path in required_dirs:
        dir_path.mkdir(parents=True, exist_ok=True)

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

@app.get("/photos/{filename:path}")
async def serve_photo(filename: str):
    """
    Serve photos from raw_photos/.

    All photos (original and uploaded) live in a single directory.
    """
    photo_path = photos_path / filename
    if photo_path.exists() and photo_path.is_file():
        return FileResponse(photo_path)

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
    """Load the identity registry (backend authority).

    Returns an empty registry if the file is missing or corrupted,
    so the server never crashes on bad data.
    """
    if REGISTRY_PATH.exists():
        try:
            return IdentityRegistry.load(REGISTRY_PATH)
        except (ValueError, OSError) as e:
            logging.error(f"Failed to load identity registry from {REGISTRY_PATH}: {e}")
            return IdentityRegistry()
    return IdentityRegistry()


def save_registry(registry):
    """Save registry with atomic write (backend handles locking)."""
    registry.save(REGISTRY_PATH)


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def _pl(count, singular, plural=None):
    """Pluralize: _pl(3, 'face') -> '3 faces', _pl(1, 'face') -> '1 face'."""
    plural = plural or f"{singular}s"
    return f"{count} {singular}" if count == 1 else f"{count} {plural}"


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


def _get_user_role(sess) -> str:
    """Get the user's role string for UI rendering. Returns 'admin' when auth disabled."""
    if not is_auth_enabled():
        return "admin"
    user = get_current_user(sess or {})
    if not user:
        return "viewer"
    return user.role


def _check_contributor(sess) -> Response | None:
    """ROLE-002: Return 401/403 if user is not at least a contributor, else None.
    Allows admin and contributor roles. Rejects viewers and anonymous users.
    When auth is disabled, always allows access."""
    if not is_auth_enabled():
        return None
    user = get_current_user(sess or {})
    if not user:
        return Response("", status_code=401)
    if user.role in ("admin", "contributor"):
        return None
    return Response(
        to_xml(toast("Contributor access required.", "error")),
        status_code=403,
        headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
    )


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
# PENDING UPLOADS REGISTRY
# =============================================================================

def _load_pending_uploads() -> dict:
    """Load pending uploads registry."""
    path = data_path / "pending_uploads.json"
    if not path.exists():
        return {"uploads": {}}
    with open(path) as f:
        return json.load(f)


def _save_pending_uploads(data: dict) -> None:
    """Save pending uploads registry (atomic write)."""
    path = data_path / "pending_uploads.json"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.rename(path)


def _count_pending_uploads() -> int:
    """Count pending uploads awaiting review or processing."""
    data = _load_pending_uploads()
    return sum(1 for u in data["uploads"].values() if u["status"] in ("pending", "staged"))


# =============================================================================
# CLUSTERING PROPOSALS (from data/proposals.json)
# =============================================================================

_proposals_cache = None


def _load_proposals() -> dict:
    """Load clustering proposals generated by cluster_new_faces.py."""
    global _proposals_cache
    if _proposals_cache is not None:
        return _proposals_cache
    path = data_path / "proposals.json"
    if not path.exists():
        _proposals_cache = {"proposals": [], "generated_at": ""}
        return _proposals_cache
    with open(path) as f:
        _proposals_cache = json.load(f)
    return _proposals_cache


def _get_proposals_for_identity(identity_id: str) -> list[dict]:
    """Get all clustering proposals where this identity is the source."""
    data = _load_proposals()
    return [p for p in data.get("proposals", [])
            if p.get("source_identity_id") == identity_id]


def _get_proposal_targets_for_identity(identity_id: str) -> list[dict]:
    """Get all clustering proposals where this identity is the target."""
    data = _load_proposals()
    return [p for p in data.get("proposals", [])
            if p.get("target_identity_id") == identity_id]


def _get_identities_with_proposals() -> set[str]:
    """Get set of source identity IDs that have clustering proposals."""
    data = _load_proposals()
    return {p["source_identity_id"] for p in data.get("proposals", [])}


def _get_best_proposal_for_identity(identity_id: str) -> dict | None:
    """Get the highest-confidence proposal for an identity."""
    proposals = _get_proposals_for_identity(identity_id)
    if not proposals:
        return None
    return min(proposals, key=lambda p: p.get("distance", float("inf")))


def _compute_triage_counts(to_review: list) -> dict:
    """Categorize inbox identities by actionability for the triage bar.

    Returns:
        {
            "ready_to_confirm": int,  # Has Very High or High proposal to confirmed
            "rediscovered": int,      # Promoted from SKIPPED (has promoted_from field)
            "unmatched": int,         # No proposals, no promotion
        }
    """
    ids_with_proposals = _get_identities_with_proposals()
    ready = 0
    rediscovered = 0
    unmatched = 0

    for identity in to_review:
        iid = identity.get("identity_id", "")
        has_promotion = identity.get("promoted_from") is not None

        if iid in ids_with_proposals:
            best = _get_best_proposal_for_identity(iid)
            if best and best.get("confidence") in ("VERY HIGH", "HIGH"):
                ready += 1
                continue

        if has_promotion:
            rediscovered += 1
        elif iid in ids_with_proposals:
            # Has proposals but not high-confidence
            ready += 1
        else:
            unmatched += 1

    return {
        "ready_to_confirm": ready,
        "rediscovered": rediscovered,
        "unmatched": unmatched,
    }


def _triage_category(identity: dict) -> str:
    """Determine triage category for a single identity.

    Returns: "ready", "rediscovered", or "unmatched"
    """
    iid = identity.get("identity_id", "")
    ids_with_proposals = _get_identities_with_proposals()

    if iid in ids_with_proposals:
        return "ready"

    if identity.get("promoted_from") is not None:
        return "rediscovered"

    return "unmatched"


def _build_triage_bar(to_review: list, view_mode: str) -> Div:
    """Build the triage summary bar for the inbox."""
    counts = _compute_triage_counts(to_review)

    items = []
    categories = [
        ("ready", "Ready to Confirm", counts["ready_to_confirm"],
         "bg-emerald-900/40 border-emerald-600/40 text-emerald-300 hover:bg-emerald-900/60"),
        ("rediscovered", "Rediscovered", counts["rediscovered"],
         "bg-amber-900/40 border-amber-600/40 text-amber-300 hover:bg-amber-900/60"),
        ("unmatched", "Unmatched", counts["unmatched"],
         "bg-slate-700/40 border-slate-600/40 text-slate-300 hover:bg-slate-700/60"),
    ]

    for filter_val, label, count, color_cls in categories:
        if count == 0:
            continue
        items.append(
            A(
                Span(str(count), cls="text-lg font-bold"),
                Span(label, cls="text-xs opacity-80"),
                href=f"/?section=to_review&view={view_mode}&filter={filter_val}",
                cls=f"flex flex-col items-center px-4 py-2 rounded-lg border transition-colors {color_cls}",
            )
        )

    if not items:
        return None

    return Div(
        *items,
        cls="flex gap-3 mb-4 flex-wrap",
    )


def _promotion_badge(identity: dict):
    """Badge for promoted (rediscovered) identities in browse view."""
    if not identity.get("promoted_from"):
        return None
    reason = identity.get("promotion_reason", "")
    if reason == "confirmed_match":
        return Span(
            "Suggested ID",
            cls="text-xs px-2 py-0.5 rounded border bg-emerald-600/30 text-emerald-300 border-emerald-500/30",
            title="Previously skipped — now matches a confirmed identity",
        )
    else:
        return Span(
            "Rediscovered",
            cls="text-xs px-2 py-0.5 rounded border bg-amber-600/30 text-amber-300 border-amber-500/30",
            title="Previously skipped — new match evidence found",
        )


def _promotion_banner(identity: dict):
    """Banner for promoted faces shown above expanded cards in Focus mode."""
    if not identity.get("promoted_from"):
        return None
    reason = identity.get("promotion_reason", "")
    context = identity.get("promotion_context", "")

    if reason == "confirmed_match":
        title = "Identity Suggested"
        desc = context or "This previously skipped face now matches a confirmed identity with high confidence."
        icon_cls = "text-emerald-400"
        border_cls = "border-emerald-600/40 bg-emerald-900/20"
    elif reason == "new_face_match":
        title = "New Context Available"
        desc = context or "A newly uploaded photo matches this previously skipped face."
        icon_cls = "text-amber-400"
        border_cls = "border-amber-600/40 bg-amber-900/20"
    else:  # group_discovery
        title = "Rediscovered"
        desc = context or "This face now groups with another face from a different batch."
        icon_cls = "text-amber-400"
        border_cls = "border-amber-600/40 bg-amber-900/20"

    return Div(
        Div(
            Span("*", cls=f"text-lg font-bold {icon_cls}"),
            Div(
                Strong(title, cls="text-white text-sm"),
                P(desc, cls="text-slate-400 text-xs mt-0.5"),
                cls="ml-2",
            ),
            cls="flex items-start",
        ),
        cls=f"rounded-lg border p-3 mb-3 {border_cls}",
    )


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


def _compute_sidebar_counts(registry) -> dict:
    """Compute sidebar navigation counts from a loaded registry.

    This is the SINGLE canonical source for sidebar counts.
    All pages with a sidebar MUST call this instead of computing counts inline.
    """
    _build_caches()
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    confirmed_list = registry.list_identities(state=IdentityState.CONFIRMED)
    skipped_list = registry.list_identities(state=IdentityState.SKIPPED)
    rejected = registry.list_identities(state=IdentityState.REJECTED)
    contested = registry.list_identities(state=IdentityState.CONTESTED)

    to_review = inbox + proposed
    dismissed = rejected + contested
    photo_count = len(_photo_cache) if _photo_cache else 0
    proposal_count = len(registry.list_proposed_matches()) if hasattr(registry, 'list_proposed_matches') else 0

    # Count pending user annotations (for admin approvals badge)
    pending_annotations = 0
    try:
        annotations_data = _load_annotations()
        for ann in annotations_data.get("annotations", []):
            if ann.get("status") in ("pending", "pending_unverified"):
                pending_annotations += 1
    except Exception:
        pass

    return {
        "to_review": len(to_review),
        "confirmed": len(confirmed_list),
        "skipped": len(skipped_list),
        "rejected": len(dismissed),
        "photos": photo_count,
        "pending_uploads": _count_pending_uploads(),
        "proposals": proposal_count,
        "pending_annotations": pending_annotations,
    }


async def _notify_admin_upload(uploader_email: str, job_id: str, file_count: int, source: str) -> None:
    """Send email notification to admins about a new pending upload.

    Uses Resend API if RESEND_API_KEY is set. Fire-and-forget — does not
    block the upload response on email delivery.
    """
    import os
    resend_api_key = os.getenv("RESEND_API_KEY", "")
    if not resend_api_key:
        logging.info(f"[upload] No RESEND_API_KEY set, skipping email notification for job {job_id}")
        return

    if not ADMIN_EMAILS:
        logging.info(f"[upload] No ADMIN_EMAILS configured, skipping email notification for job {job_id}")
        return

    import httpx

    site_url = os.getenv("SITE_URL", "https://rhodesli.nolanandrewfox.com")
    from_email = os.getenv("NOTIFICATION_FROM_EMAIL", "noreply@nolanandrewfox.com")
    subject = f"New photo upload pending review ({file_count} file{'s' if file_count != 1 else ''})"
    html_body = f"""
    <div style="font-family: sans-serif; max-width: 480px;">
        <h2 style="color: #1e293b;">New Upload Pending Review</h2>
        <p><strong>Uploader:</strong> {uploader_email}</p>
        <p><strong>Files:</strong> {file_count}</p>
        <p><strong>Source:</strong> {source or 'Not specified'}</p>
        <p><strong>Job ID:</strong> <code>{job_id}</code></p>
        <p style="margin-top: 20px;">
            <a href="{site_url}/admin/pending"
               style="display: inline-block; background-color: #2563eb; color: #ffffff !important;
                      padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold;">
                Review Uploads
            </a>
        </p>
    </div>
    """

    try:
        async with httpx.AsyncClient() as client:
            for admin_email in ADMIN_EMAILS:
                await client.post(
                    "https://api.resend.com/emails",
                    json={
                        "from": f"Rhodesli <{from_email}>",
                        "to": [admin_email],
                        "subject": subject,
                        "html": html_body,
                    },
                    headers={
                        "Authorization": f"Bearer {resend_api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
        logging.info(f"[upload] Email notification sent for job {job_id}")
    except Exception as e:
        logging.warning(f"[upload] Failed to send email notification for job {job_id}: {e}")


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
    """Load the photo registry for merge validation.

    Returns an empty registry if the file is missing or corrupted,
    so the server never crashes on bad data.
    """
    global _photo_registry_cache
    if _photo_registry_cache is None:
        from core.photo_registry import PhotoRegistry
        photo_index_path = data_path / "photo_index.json"
        if photo_index_path.exists():
            try:
                _photo_registry_cache = PhotoRegistry.load(photo_index_path)
            except (ValueError, OSError) as e:
                logging.error(f"Failed to load photo registry from {photo_index_path}: {e}")
                _photo_registry_cache = PhotoRegistry()
        else:
            _photo_registry_cache = PhotoRegistry()
    return _photo_registry_cache


def save_photo_registry(registry):
    """Save photo registry to disk and invalidate cache."""
    global _photo_registry_cache
    photo_index_path = data_path / "photo_index.json"
    registry.save(photo_index_path)
    _photo_registry_cache = registry


# =============================================================================
# PHOTO CONTEXT HELPERS
# =============================================================================

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


def get_photo_dimensions(filename: str) -> tuple:
    """
    Get image dimensions for a photo.

    Args:
        filename: Photo filename (looked up in raw_photos/).

    Returns:
        (width, height) tuple or (0, 0) if file not found
    """
    basename = Path(filename).name

    # In R2 mode, photos aren't stored locally, so use cached dimensions
    # from photo_index.json instead of reading from filesystem
    if storage.is_r2_mode():
        cache = _load_photo_dimensions_cache()
        if basename in cache:
            return cache[basename]
        return (0, 0)

    # Local mode: read from filesystem
    filepath = photos_path / basename
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


def _compute_co_occurrence(
    identity_a_id: str,
    identity_b_id: str,
    registry,
    photo_registry,
) -> int:
    """
    Count how many photos two identities appear in together.

    Strong evidence they are different people (or family members in the same photo).
    Uses anchor + candidate face IDs for both identities.

    Returns:
        Number of shared photos (0 if none).
    """
    faces_a = (
        registry.get_anchor_face_ids(identity_a_id)
        + registry.get_candidate_face_ids(identity_a_id)
    )
    faces_b = (
        registry.get_anchor_face_ids(identity_b_id)
        + registry.get_candidate_face_ids(identity_b_id)
    )

    photos_a = photo_registry.get_photos_for_faces(faces_a)
    photos_b = photo_registry.get_photos_for_faces(faces_b)

    return len(photos_a & photos_b)


def get_first_anchor_face_id(identity_id: str, registry) -> str | None:
    """
    Get the best-quality anchor face ID for an identity.

    Used for showing thumbnails in neighbor cards.
    Falls back to the first anchor if quality data is unavailable.

    Returns:
        Best anchor face ID, or None if identity has no anchors.
    """
    try:
        anchor_ids = registry.get_anchor_face_ids(identity_id)
        if not anchor_ids:
            return None
        return get_best_face_id(anchor_ids)
    except KeyError:
        return None


# Photo metadata cache (rebuilt on each request for simplicity)
_photo_cache = None
_face_to_photo_cache = None


def _build_caches():
    """Build photo and face-to-photo caches.

    Loads raw detections from embeddings.npy, then filters each photo's
    face list to only include faces registered in photo_index.json.
    This removes noise detections (e.g., a newspaper photo might have
    63 raw detections but only 21 real registered faces).
    """
    global _photo_cache, _face_to_photo_cache
    if _photo_cache is None:
        _photo_cache = load_embeddings_for_photos()

        # Merge source data and filter faces using photo_index.json
        try:
            from core.photo_registry import PhotoRegistry
            photo_registry = PhotoRegistry.load(data_path / "photo_index.json")

            # Build filename-based fallback maps for photos with mismatched IDs
            # (e.g., inbox_* IDs in photo_index.json vs SHA256 IDs in _photo_cache)
            filename_to_source = {}
            filename_to_collection = {}
            filename_to_source_url = {}
            filename_to_face_ids = {}
            for pid in photo_registry._photos:
                path = photo_registry.get_photo_path(pid)
                source = photo_registry.get_source(pid)
                collection = photo_registry.get_collection(pid)
                source_url = photo_registry.get_source_url(pid)
                face_ids = photo_registry.get_faces_in_photo(pid)
                if path:
                    fname = Path(path).name
                    if source:
                        filename_to_source[fname] = source
                    if collection:
                        filename_to_collection[fname] = collection
                    if source_url:
                        filename_to_source_url[fname] = source_url
                    filename_to_face_ids[fname] = face_ids

            for photo_id in _photo_cache:
                filename = _photo_cache[photo_id].get("filename", "")
                fname = Path(filename).name

                # Filter faces to only registered ones from photo_index
                registered_ids = filename_to_face_ids.get(fname)
                if registered_ids:
                    _photo_cache[photo_id]["faces"] = [
                        f for f in _photo_cache[photo_id]["faces"]
                        if f["face_id"] in registered_ids
                    ]

                # Set source (provenance)
                source = photo_registry.get_source(photo_id)
                if not source:
                    source = filename_to_source.get(fname, "")
                _photo_cache[photo_id]["source"] = source

                # Set collection (classification)
                collection = photo_registry.get_collection(photo_id)
                if not collection:
                    collection = filename_to_collection.get(fname, "")
                _photo_cache[photo_id]["collection"] = collection

                # Set source_url (citation)
                source_url = photo_registry.get_source_url(photo_id)
                if not source_url:
                    source_url = filename_to_source_url.get(fname, "")
                _photo_cache[photo_id]["source_url"] = source_url

                # Merge photo metadata (BE-012)
                metadata = photo_registry.get_metadata(photo_id)
                if metadata:
                    _photo_cache[photo_id].update(metadata)
        except FileNotFoundError:
            # No photo_index.json yet, set empty sources
            for photo_id in _photo_cache:
                _photo_cache[photo_id]["source"] = ""

        # Build reverse mapping AFTER filtering: face_id -> photo_id
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


def get_face_quality(face_id: str) -> float:
    """Look up face quality score from embeddings cache.

    Returns the quality score stored in embeddings.npy for this face,
    or None if not found. This is needed because inbox-style crop
    filenames don't encode quality in the filename.
    """
    photo_id = get_photo_id_for_face(face_id)
    if not photo_id:
        return None
    photo = _photo_cache.get(photo_id)
    if not photo:
        return None
    for face in photo.get("faces", []):
        if face.get("face_id") == face_id:
            q = face.get("quality", 0)
            return q if q > 0 else None
    return None


def _get_face_cache_entry(face_id: str) -> dict | None:
    """Look up full face data (bbox, det_score, quality) from embeddings cache."""
    _build_caches()
    photo_id = get_photo_id_for_face(face_id)
    if not photo_id:
        return None
    photo = _photo_cache.get(photo_id)
    if not photo:
        return None
    for face in photo.get("faces", []):
        if face.get("face_id") == face_id:
            return face
    return None


def compute_face_quality_score(face_id: str) -> float:
    """Compute composite quality score (0-100) for a face.

    Components:
    - Detection confidence (0-30 pts): InsightFace SCRFD det_score
    - Face crop size (0-35 pts): pixel area from bounding box
    - Embedding norm (0-35 pts): proxy for image quality (MagFace principle)

    Returns 0 if face data is not found.
    """
    face = _get_face_cache_entry(face_id)
    if not face:
        return 0.0

    score = 0.0

    # 1. Detection confidence — 0-30 pts
    det_score = face.get("det_score", 0.5)
    score += det_score * 30

    # 2. Face crop size from bbox — 0-35 pts
    # Good faces are 150+ pixels on a side (~22500 area)
    bbox = face.get("bbox", [0, 0, 0, 0])
    if len(bbox) == 4:
        face_width = abs(bbox[2] - bbox[0])
        face_height = abs(bbox[3] - bbox[1])
        face_area = face_width * face_height
        # Scale: 0=tiny, 1=good (22500px²=150×150)
        area_factor = min(face_area / 22500.0, 1.0)
        score += area_factor * 35

    # 3. Embedding norm — 0-35 pts
    # Raw quality is the embedding L2 norm (~15-30 range typically)
    raw_quality = face.get("quality", 0)
    if raw_quality > 0:
        # Normalize: 15 = low, 30 = high quality
        norm_factor = max(min((raw_quality - 15) / 15.0, 1.0), 0.0)
        score += norm_factor * 35

    return round(score, 1)


def get_best_face_id(face_ids: list) -> str | None:
    """Pick the highest-quality face from a list of face IDs.

    Returns the face_id with the highest composite quality score,
    or the first one if scores can't be computed.
    """
    if not face_ids:
        return None

    # Normalize: face_ids can be strings or dicts
    ids = []
    for f in face_ids:
        if isinstance(f, str):
            ids.append(f)
        elif isinstance(f, dict):
            ids.append(f.get("face_id", ""))
        else:
            ids.append(str(f))

    if len(ids) == 1:
        return ids[0]

    best_id = ids[0]
    best_score = -1
    for fid in ids:
        s = compute_face_quality_score(fid)
        if s > best_score:
            best_score = s
            best_id = fid
    return best_id


def _highlight_match(name: str, query: str):
    """Return FastHTML elements with the matched portion highlighted.

    Case-insensitive substring match. When the exact query doesn't match,
    tries surname variant terms (e.g., query "Capelluto" highlights "Capeluto"
    in "Leon Capeluto").
    """
    if not query:
        return name
    idx = name.lower().find(query.lower())
    if idx == -1:
        # Try variant terms — if query word maps to a variant group,
        # highlight whichever variant appears in the name
        from core.registry import _load_surname_variants
        variant_lookup = _load_surname_variants()
        for word in query.lower().split():
            if word in variant_lookup:
                for variant in variant_lookup[word]:
                    vidx = name.lower().find(variant)
                    if vidx != -1:
                        before = name[:vidx]
                        match = name[vidx:vidx + len(variant)]
                        after = name[vidx + len(variant):]
                        return (
                            Span(before) if before else None,
                            Span(match, cls="text-amber-300 font-semibold"),
                            Span(after) if after else None,
                        )
        return name
    before = name[:idx]
    match = name[idx:idx + len(query)]
    after = name[idx + len(query):]
    return (
        Span(before) if before else None,
        Span(match, cls="text-amber-300 font-semibold"),
        Span(after) if after else None,
    )


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
        cls="fixed top-4 right-4 z-[10001] flex flex-col gap-2"
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


def _admin_dashboard_banner(counts: dict, current_section: str) -> Div:
    """Admin-only dashboard summary banner at the top of the workstation.

    Shows inbox count, skipped count, and quick links.
    Focus/Browse toggle lives in each section's header instead.
    Only rendered when user is admin.
    """
    to_review = counts.get("to_review", 0)
    skipped = counts.get("skipped", 0)
    confirmed = counts.get("confirmed", 0)
    proposals = counts.get("proposals", 0)
    photo_count = counts.get("photo_count", 0)

    stat_items = [
        ("To Review", to_review, "/?section=to_review&view=focus", "text-amber-400"),
        ("People", confirmed, "/?section=confirmed", "text-emerald-400"),
        ("Help Identify", skipped, "/?section=skipped", "text-yellow-400"),
    ]
    if proposals > 0:
        stat_items.append(("Proposals", proposals, "/admin/proposals", "text-blue-400"))

    stats_row = [
        A(
            Span(str(count), cls=f"font-bold text-lg {color}"),
            Span(f" {label}", cls="text-slate-400 text-xs"),
            href=link,
            cls="hover:bg-slate-700/50 px-3 py-1 rounded transition-colors",
        )
        for label, count, link, color in stat_items
    ]

    return Div(
        Div(
            *stats_row,
            cls="max-w-6xl mx-auto px-4 sm:px-8 flex items-center gap-4 flex-wrap",
        ),
        id="admin-dashboard-banner",
        cls="py-2 border-b border-slate-700/50 bg-slate-800/30",
    )


def mobile_header() -> Div:
    """
    Mobile top bar with hamburger menu button.
    Hidden on desktop (lg+), shown on smaller screens.
    """
    return Div(
        Button(
            NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>'),
            cls="text-white p-2 -ml-2",
            onclick="toggleSidebar()",
            type="button",
            aria_label="Open menu",
        ),
        Span("Rhodesli", cls="text-lg font-bold text-white"),
        cls="mobile-header fixed top-0 left-0 right-0 h-14 bg-slate-800 border-b border-slate-700 "
            "flex items-center gap-3 px-4 z-20",
        id="mobile-header",
    )


def sidebar(counts: dict, current_section: str = "to_review", user: "User | None" = None) -> Aside:
    """
    Collapsible sidebar navigation for the Command Center.

    Supports expanded (full labels + counts) and collapsed (icons only) states.
    Default: collapsed on mobile (< 768px), expanded on desktop.
    Collapse state persisted in localStorage.

    Args:
        counts: Dict with keys: to_review, confirmed, skipped, rejected
        current_section: Currently active section
        user: Current user (None if anonymous)
    """
    def nav_item(href: str, icon: str, label: str, count: int, section_key: str, color: str):
        """Single navigation item with badge. Adapts to collapsed state."""
        is_active = current_section == section_key

        # Dark theme: Active vs inactive styling
        if is_active:
            container_cls = f"bg-slate-700 text-white"
            badge_cls = f"bg-{color}-500 text-white"
        else:
            container_cls = "text-slate-300 hover:bg-slate-700/50"
            badge_cls = f"bg-{color}-500/20 text-{color}-400"

        return A(
            # Icon always visible
            Span(icon, cls="sidebar-icon text-base flex-shrink-0 w-5 text-center"),
            # Label shown when expanded
            Span(label, cls="sidebar-label ml-2 whitespace-nowrap"),
            # Badge shown when expanded
            Span(
                str(count),
                cls=f"sidebar-label ml-auto px-2 py-0.5 text-xs font-bold rounded-full {badge_cls}"
            ),
            href=href,
            title=f"{label} ({count})",
            onclick="closeSidebar()",
            cls=f"sidebar-nav-item flex items-center px-3 py-2 rounded-lg text-sm font-medium min-h-[44px] {container_cls}"
        )

    return Aside(
        # Header with collapse toggle
        Div(
            A(
                H1("Rhodesli", cls="sidebar-label text-lg font-bold text-white leading-tight"),
                P("Identity System", cls="sidebar-label text-xs text-slate-400 mt-0.5"),
                href="/",
                cls="flex-1 min-w-0 no-underline hover:opacity-80 transition-opacity"
            ),
            Button(
                Svg(
                    Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2",
                         d="M15 19l-7-7 7-7"),
                    cls="sidebar-chevron w-4 h-4 transition-transform duration-200",
                    fill="none", stroke="currentColor", viewBox="0 0 24 24"
                ),
                onclick="toggleSidebarCollapse()",
                cls="sidebar-collapse-btn hidden lg:flex items-center justify-center p-1 rounded text-slate-400 hover:text-white hover:bg-slate-700 transition-colors",
                title="Toggle sidebar"
            ),
            cls="flex items-center px-3 py-3 border-b border-slate-700/50"
        ),
        # Search input
        Div(
            Div(
                Svg(
                    Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2",
                         d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"),
                    cls="w-4 h-4 text-slate-400 flex-shrink-0",
                    fill="none", stroke="currentColor", viewBox="0 0 24 24"
                ),
                Input(type="text", name="q", placeholder="Search names...", autocomplete="off",
                      cls="sidebar-label bg-transparent border-none outline-none text-sm text-slate-200 placeholder-slate-500 w-full ml-2",
                      id="sidebar-search-input",
                      hx_get="/api/search", hx_trigger="keyup changed delay:300ms",
                      hx_target="#sidebar-search-results", hx_swap="innerHTML"),
                cls="flex items-center bg-slate-700/50 rounded-lg px-3 py-2"
            ),
            Div(id="sidebar-search-results", cls="sidebar-search-results"),
            cls="sidebar-search px-3 pt-3 pb-1 relative"
        ),
        # Upload Button (any logged-in user can upload; non-admin uploads go to moderation queue)
        Div(
            A(
                Svg(
                    Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2",
                         d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"),
                    cls="w-4 h-4 flex-shrink-0", fill="none", stroke="currentColor", viewBox="0 0 24 24"
                ),
                Span("Upload", cls="sidebar-label ml-2"),
                href="/upload", title="Upload photos",
                cls="flex items-center justify-center gap-0 w-full px-3 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-500 transition-colors"
            ) if user else None,
            cls="px-3 py-2"
        ),
        # Navigation
        Nav(
            # Review Section
            Div(
                P(
                    "Review",
                    cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1"
                ),
                nav_item("/?section=to_review", "📥", "New Matches", counts["to_review"], "to_review", "blue"),
                nav_item("/?section=skipped", "❓", "Help Identify", counts["skipped"], "skipped", "amber"),
                cls="mb-3"
            ),
            # Library Section
            Div(
                P(
                    "Library",
                    cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1"
                ),
                nav_item("/?section=confirmed", "✓", "People", counts["confirmed"], "confirmed", "green"),
                nav_item("/?section=rejected", "🗑️", "Dismissed", counts["rejected"], "rejected", "gray"),
                cls="mb-3"
            ),
            # Browse Section (photo-centric)
            Div(
                P(
                    "Browse",
                    cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1"
                ),
                nav_item("/?section=photos", "📷", "Photos", counts.get("photos", 0), "photos", "slate"),
                A(
                    Span("📖", cls="text-base leading-none flex-shrink-0 w-5 text-center"),
                    Span("About", cls="sidebar-label ml-2"),
                    href="/about",
                    cls="flex items-center px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded-lg transition-colors"
                ),
                cls="mb-3"
            ),
            # Admin Section (admin-only, with pending uploads badge)
            Div(
                P(
                    "Admin",
                    cls="sidebar-label px-3 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1"
                ),
                nav_item("/admin/pending", "📋", "Uploads", counts.get("pending_uploads", 0), "pending_uploads", "amber"),
                nav_item("/admin/approvals", "✅", "Approvals", counts.get("pending_annotations", 0), "approvals", "emerald"),
                nav_item("/admin/proposals", "🔗", "Proposals", counts.get("proposals", 0), "proposals", "indigo"),
                cls="mb-3"
            ) if (user and user.is_admin) else None,
            cls="flex-1 px-2 py-2 space-y-0 overflow-y-auto"
        ),
        # Footer with user info and stats
        Div(
            Div(
                Div(
                    Span(user.email, cls="sidebar-label text-xs text-slate-400 truncate"),
                    Span(" (admin)" if user.is_admin else "", cls="sidebar-label text-xs text-indigo-400"),
                    cls="flex items-center gap-1 min-w-0"
                ),
                A("Sign out", href="/logout", cls="sidebar-label text-xs text-slate-500 hover:text-slate-300 underline flex-shrink-0"),
                cls="flex items-center justify-between mb-1 gap-2"
            ) if user else Div(
                A("Sign in", href="/login", cls="sidebar-label text-xs text-slate-400 hover:text-slate-300 underline"),
                cls="mb-1"
            ),
            Div(
                f"{counts['confirmed']} of {counts['to_review'] + counts['confirmed'] + counts['skipped']} identified",
                cls="sidebar-label text-xs text-slate-500 font-data"
            ),
            Div("v0.6.0", cls="sidebar-label text-xs text-slate-600 mt-0.5"),
            cls="px-3 py-2 border-t border-slate-700/50"
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
        cls="sidebar-container fixed left-0 top-0 h-screen bg-slate-800 border-r border-slate-700/50 flex flex-col z-40 -translate-x-full lg:translate-x-0 transition-all duration-200"
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

    # Add view toggle for sections that support it
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
            A(
                "Match",
                href="/?section=to_review&view=match",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg {'bg-amber-500 text-white' if view_mode == 'match' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
            ),
            cls="flex items-center gap-2"
        )
        header_content.append(toggle)
    elif section == "skipped" and view_mode is not None:
        toggle = Div(
            A(
                "Focus",
                href="/?section=skipped&view=focus",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg {'bg-white text-slate-900' if view_mode == 'focus' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
            ),
            A(
                "View All",
                href="/?section=skipped&view=browse",
                cls=f"px-3 py-1.5 text-sm font-medium rounded-lg {'bg-white text-slate-900' if view_mode == 'browse' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}"
            ),
            cls="flex items-center gap-2"
        )
        header_content.append(toggle)

    return Div(
        *header_content,
        cls="section-header flex items-center justify-between mb-6"
    )


def _proposal_banner(identity_id: str):
    """Show a proposal banner if ML found a match for this identity."""
    best = _get_best_proposal_for_identity(identity_id)
    if not best:
        return None
    confidence = best.get("confidence", "")
    target_name = best.get("target_identity_name", "Unknown")
    distance = best.get("distance", 0)
    confidence_pct = max(0, min(100, int((1 - distance / 2.0) * 100)))

    color_cls = {
        "VERY HIGH": "bg-emerald-900/30 border-emerald-500/50 text-emerald-300",
        "HIGH": "bg-blue-900/30 border-blue-500/50 text-blue-300",
        "MODERATE": "bg-amber-900/30 border-amber-500/50 text-amber-300",
    }.get(confidence, "bg-slate-700/30 border-slate-500/50 text-slate-300")

    all_proposals = _get_proposals_for_identity(identity_id)
    count_text = f" (+{len(all_proposals) - 1} more)" if len(all_proposals) > 1 else ""

    return Div(
        Span(f"ML Match: {confidence}", cls="text-xs font-bold uppercase"),
        Span(" — ", cls="text-xs opacity-50"),
        Span(f"Likely {target_name}", cls="text-sm font-medium"),
        Span(f" ({confidence_pct}%)", cls="text-xs opacity-70"),
        Span(count_text, cls="text-xs opacity-50") if count_text else None,
        cls=f"mt-2 px-3 py-2 rounded-lg border text-sm {color_cls}",
    )


def _proposal_badge_inline(identity_id: str):
    """Compact inline badge showing ML match count for browse view cards."""
    proposals = _get_proposals_for_identity(identity_id)
    if not proposals:
        return None
    best = min(proposals, key=lambda p: p.get("distance", 999))
    confidence = best.get("confidence", "")
    count = len(proposals)
    label = f"{count} match{'es' if count > 1 else ''}"

    color_cls = {
        "VERY HIGH": "bg-emerald-600/30 text-emerald-300 border-emerald-500/30",
        "HIGH": "bg-blue-600/30 text-blue-300 border-blue-500/30",
        "MODERATE": "bg-amber-600/30 text-amber-300 border-amber-500/30",
    }.get(confidence, "bg-slate-600/30 text-slate-300 border-slate-500/30")

    return Span(
        f"{label}",
        cls=f"text-xs px-2 py-0.5 rounded border {color_cls}",
        title=f"ML: Likely {best.get('target_identity_name', '?')} ({confidence})",
    )


def identity_card_expanded(identity: dict, crop_files: set, is_admin: bool = True, triage_filter: str = "") -> Div:
    """
    Expanded identity card for Focus Mode review.
    Shows larger thumbnail and prominent actions (admin only).

    Args:
        triage_filter: Active triage filter to preserve in action URLs
    """
    identity_id = identity["identity_id"]
    raw_name = ensure_utf8_display(identity.get("name"))
    name = raw_name or f"Unidentified Person"
    state = identity["state"]

    # Get all faces
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_count = len(all_face_ids)

    # Get best-quality face for main thumbnail
    main_crop_url = None
    main_photo_id = None
    best_face_id = get_best_face_id(all_face_ids)
    if best_face_id:
        main_crop_url = resolve_face_image_url(best_face_id, crop_files)
        main_photo_id = get_photo_id_for_face(best_face_id)

    # Build face grid for additional faces (skip best since it's shown as main thumbnail)
    face_previews = []
    for face_entry in all_face_ids[:6]:  # Show up to 6, skip the best one
        if isinstance(face_entry, str):
            face_id = face_entry
        else:
            face_id = face_entry.get("face_id", "")
        if face_id == best_face_id:
            continue  # Already shown as main thumbnail
        crop_url = resolve_face_image_url(face_id, crop_files)
        if crop_url:
            # Get photo_id for this face to make it clickable
            face_photo_id = get_photo_id_for_face(face_id)
            if face_photo_id:
                face_previews.append(
                    Button(
                        Img(
                            src=crop_url,
                            cls="w-16 h-16 rounded object-cover border border-slate-600 hover:border-indigo-400 hover:scale-110 transition-all",
                            alt=f"Face {face_id[:8]}"
                        ),
                        cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded transition-all",
                        hx_get=f"/photo/{face_photo_id}/partial?face={face_id}&identity_id={identity_id}",
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
        _filter_suffix = f"&filter={triage_filter}" if triage_filter else ""
        confirm_url = f"{base_confirm_url}?from_focus=true{_filter_suffix}"
        reject_url = f"{base_reject_url}?from_focus=true{_filter_suffix}"
        skip_url = f"/identity/{identity_id}/skip?from_focus=true{_filter_suffix}"

        actions = Div(
            Button(
                "✓ Confirm",
                cls="px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors min-h-[44px]",
                hx_post=confirm_url,
                hx_target="#focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-confirm",
            ),
            Button(
                "⏸ Skip",
                cls="px-4 py-2 bg-yellow-500 text-white font-medium rounded-lg hover:bg-yellow-600 transition-colors min-h-[44px]",
                hx_post=skip_url,
                hx_target="#focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-skip",
            ),
            Button(
                "✗ Reject",
                cls="px-4 py-2 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-colors min-h-[44px]",
                hx_post=reject_url,
                hx_target="#focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-reject",
            ),
            Button(
                "Find Similar",
                cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors ml-auto min-h-[44px]",
                hx_get=f"/api/identity/{identity_id}/neighbors?from_focus=true",
                hx_target=f"#neighbors-{identity_id}",
                hx_swap="innerHTML",
                type="button",
                id="focus-btn-similar",
                **{"hx-on::after-swap": f"document.getElementById('neighbors-{identity_id}').scrollIntoView({{behavior: 'smooth', block: 'start'}})"},
            ),
            Span(
                "Keyboard: C S R F",
                cls="text-xs text-slate-600 hidden sm:inline ml-2",
                title="C=Confirm, S=Skip, R=Reject, F=Find Similar"
            ),
            cls="flex flex-wrap items-center gap-3 mt-6"
        )
    else:
        actions = Div(
            Button(
                "Find Similar",
                cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors",
                hx_get=f"/api/identity/{identity_id}/neighbors?from_focus=true",
                hx_target=f"#neighbors-{identity_id}",
                hx_swap="innerHTML",
                type="button",
                **{"hx-on::after-swap": f"document.getElementById('neighbors-{identity_id}').scrollIntoView({{behavior: 'smooth', block: 'start'}})"},
            ),
            Button(
                "I Know This Person",
                cls="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors",
                **{"_": f"on click toggle .hidden on #suggest-name-{identity_id}"},
                type="button",
            ),
            cls="flex items-center gap-3 mt-6"
        )

    return Div(
        Div(
            # Left: Main Face (clickable to open photo)
            Div(
                Button(
                    Div(
                        Img(
                            src=main_crop_url or "",
                            alt=name,
                            cls="w-full h-full object-cover"
                        ) if main_crop_url else Span("?", cls="text-6xl text-slate-500"),
                        cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center"
                    ),
                    cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-lg transition-all",
                    hx_get=f"/photo/{main_photo_id}/partial?face={face_id}&identity_id={identity_id}" if main_photo_id else None,
                    hx_target="#photo-modal-content",
                    **{"_": "on click remove .hidden from #photo-modal"} if main_photo_id else {},
                    type="button",
                    title="Click to view photo",
                ) if main_photo_id else Div(
                    Img(
                        src=main_crop_url,
                        alt=name,
                        cls="w-full h-full object-cover"
                    ) if main_crop_url else Span("?", cls="text-6xl text-slate-500"),
                    cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center"
                ),
                cls="flex-shrink-0"
            ),
            # Right: Details + Actions
            Div(
                H3(name, cls="text-xl font-semibold text-white"),
                P(
                    f"{face_count} face{'s' if face_count != 1 else ''}",
                    cls="text-sm text-slate-400 mt-1"
                ),
                # Proposal banner — shows ML match suggestion if one exists
                _proposal_banner(identity_id),
                # Face grid preview
                Div(
                    *face_previews,
                    cls="flex gap-2 mt-4 flex-wrap"
                ) if len(face_previews) > 1 else None,
                # Neighbors container — auto-load if proposals exist
                Div(
                    id=f"neighbors-{identity_id}", cls="mt-4",
                    **({"hx_get": f"/api/identity/{identity_id}/neighbors?from_focus=true",
                        "hx_trigger": "load",
                        "hx_swap": "innerHTML"}
                       if identity_id in _get_identities_with_proposals() else {}),
                ),
                actions,
                # Suggest Name form (hidden by default, shown via Hyperscript toggle)
                _suggest_name_form(identity_id),
                # Identity metadata (AN-012)
                _identity_metadata_display(identity, is_admin=is_admin),
                # Identity annotations (AN-013/AN-014)
                _identity_annotations_section(identity_id, is_admin=is_admin),
                # Notes section (loads via HTMX)
                Div(
                    Button(
                        "Notes",
                        cls="text-xs text-slate-400 hover:text-slate-300 underline",
                        hx_get=f"/api/identity/{identity_id}/notes",
                        hx_target=f"#notes-{identity_id}",
                        hx_swap="innerHTML",
                        type="button",
                    ),
                    Div(id=f"notes-{identity_id}", cls="mt-2"),
                    cls="mt-4 pt-3 border-t border-slate-700"
                ),
                cls="flex-1 min-w-0"
            ),
            cls="flex flex-col sm:flex-row gap-4 sm:gap-6"
        ),
        cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-4 sm:p-6",
        id="focus-card"
    )


def _suggest_name_form(identity_id: str) -> Div:
    """Hidden form for suggesting a name for an unidentified person."""
    return Div(
        H4("I Know This Person", cls="text-sm font-medium text-white mb-2"),
        Form(
            Input(type="hidden", name="target_type", value="identity"),
            Input(type="hidden", name="target_id", value=identity_id),
            Input(type="hidden", name="annotation_type", value="name_suggestion"),
            Input(
                name="value", placeholder="Enter name...",
                cls="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-white placeholder-slate-400",
                required=True,
            ),
            Select(
                Option("I'm certain", value="certain"),
                Option("Likely", value="likely", selected=True),
                Option("Just a guess", value="guess"),
                name="confidence",
                cls="w-full mt-2 bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white",
            ),
            Input(
                name="reason", placeholder="How do you know? (optional)",
                cls="w-full mt-2 bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-white placeholder-slate-400",
            ),
            Button(
                "Submit Suggestion",
                type="submit",
                cls="mt-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded hover:bg-indigo-500",
            ),
            hx_post="/api/annotations/submit",
            hx_swap="beforeend",
            hx_target="#toast-container",
            cls="space-y-0"
        ),
        cls="hidden mt-4 p-4 bg-slate-900/50 border border-indigo-500/30 rounded-lg",
        id=f"suggest-name-{identity_id}",
    )


def identity_card_mini(identity: dict, crop_files: set, clickable: bool = False, triage_filter: str = "") -> Div:
    """
    Mini identity card for queue preview in Focus Mode.

    Args:
        identity: Identity dict
        crop_files: Set of available crop files
        clickable: If True, clicking loads this identity in focus mode
        triage_filter: Active filter to preserve in navigation links
    """
    identity_id = identity["identity_id"]

    # Get best-quality face for thumbnail
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    crop_url = None
    best_fid = get_best_face_id(all_face_ids)
    if best_fid:
        crop_url = resolve_face_image_url(best_fid, crop_files)

    img_element = Img(
        src=crop_url or "",
        cls="w-full h-full object-cover"
    ) if crop_url else Span("?", cls="text-2xl text-slate-500")

    if clickable:
        # Wrap in a link that loads this identity in focus mode (correct section)
        section = _section_for_state(identity.get("state", "INBOX"))
        filter_suffix = f"&filter={triage_filter}" if triage_filter else ""
        return A(
            Div(
                img_element,
                cls="w-full aspect-square rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center hover:ring-2 hover:ring-indigo-400 transition-all"
            ),
            href=f"/?section={section}&view=focus&current={identity_id}{filter_suffix}",
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
    sort_by: str = "newest",
    triage_filter: str = "",
) -> Div:
    """Render the To Review section with Focus or Browse mode."""

    # Build triage bar (shown above all views)
    triage_bar = _build_triage_bar(to_review, view_mode)

    # Apply triage filter if set
    if triage_filter in ("ready", "rediscovered", "unmatched"):
        to_review = [i for i in to_review if _triage_category(i) == triage_filter]

    # For focus mode, prioritize by actionability:
    # 1. Confirmed match promotions (one-click merge available)
    # 2. Faces with Very High proposals to confirmed identities
    # 3. Faces with new_face_match or group_discovery promotion
    # 4. Faces with High proposals
    # 5. Remaining inbox faces
    ids_with_proposals = _get_identities_with_proposals()

    def _focus_sort_key(x):
        iid = x.get("identity_id", "")
        has_proposal = iid in ids_with_proposals
        best = _get_best_proposal_for_identity(iid) if has_proposal else None
        has_promotion = x.get("promoted_from") is not None
        promotion_reason = x.get("promotion_reason", "")

        # Priority tiers (lower = higher priority):
        # 0: confirmed_match promotion (highest value)
        # 1: Very High confidence proposal
        # 2: new_face_match / group_discovery promotion
        # 3: High confidence proposal
        # 4: Other proposals (Moderate/Low)
        # 5: No proposals, no promotion (unmatched)
        if has_promotion and promotion_reason == "confirmed_match":
            tier = 0
        elif has_proposal and best and best.get("confidence") == "VERY HIGH":
            tier = 1
        elif has_promotion:
            tier = 2
        elif has_proposal and best and best.get("confidence") == "HIGH":
            tier = 3
        elif has_proposal:
            tier = 4
        else:
            tier = 5

        # Quality tiebreaker — clear faces first within same tier
        quality = _identity_quality_score(x)

        return (
            tier,
            best["distance"] if best else 999,
            -quality,
            -len(x.get("anchor_ids", []) + x.get("candidate_ids", [])),
        )

    high_confidence = sorted(to_review, key=_focus_sort_key)[:10]

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
            # Build Up Next carousel
            up_next = None
            if len(high_confidence) > 1:
                up_next = Div(
                    H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                    Div(
                        *[identity_card_mini(i, crop_files, clickable=True, triage_filter=triage_filter) for i in high_confidence[1:6]],
                        Div(
                            f"+{len(high_confidence) - 6} more",
                            cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square"
                        ) if len(high_confidence) > 6 else None,
                        cls="flex gap-3 overflow-x-auto pb-2"
                    ),
                    cls="mt-6"
                )
            # Show promotion banner above the expanded card if applicable
            banner = _promotion_banner(high_confidence[0])
            # Show one item expanded + queue preview, wrapped in focus-container for HTMX swap.
            # Keyboard shortcuts (C/S/R/F) are handled by the global keydown handler
            # in the page layout — no per-swap re-registration needed.
            content = Div(
                banner,
                identity_card_expanded(high_confidence[0], crop_files, is_admin=is_admin, triage_filter=triage_filter),
                up_next,
                id="focus-container"
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
    elif view_mode == "match":
        # Match mode - gamified side-by-side pairing
        match_url = f"/api/match/next-pair?filter={triage_filter}" if triage_filter else "/api/match/next-pair"
        content = Div(
            Div(
                Div(
                    Span("Matched: ", cls="text-slate-400"),
                    Span("0", id="match-counter", cls="text-white font-bold"),
                    Span(" pairs today", cls="text-slate-400"),
                    cls="text-sm"
                ),
                cls="flex items-center justify-between mb-4"
            ),
            Div(
                P("Loading next pair...", cls="text-slate-400 text-center py-8"),
                id="match-pair-container",
                hx_get=match_url,
                hx_trigger="load",
                hx_swap="innerHTML",
            ),
            Script("""
                // Match counter persistence via cookie
                function getMatchCount() {
                    var today = new Date().toISOString().slice(0, 10);
                    var stored = document.cookie.split(';').find(c => c.trim().startsWith('match_count_' + today + '='));
                    return stored ? parseInt(stored.split('=')[1]) : 0;
                }
                function incrementMatchCount() {
                    var today = new Date().toISOString().slice(0, 10);
                    var count = getMatchCount() + 1;
                    document.cookie = 'match_count_' + today + '=' + count + '; path=/; max-age=86400';
                    var el = document.getElementById('match-counter');
                    if (el) el.textContent = count;
                }
                // Initialize counter on load
                document.addEventListener('DOMContentLoaded', function() {
                    var el = document.getElementById('match-counter');
                    if (el) el.textContent = getMatchCount();
                });
            """),
            cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-6",
        )
    else:
        # Browse mode - apply sorting
        if sort_by == "faces":
            to_review = sorted(to_review, key=lambda x: len(x.get("anchor_ids", []) + x.get("candidate_ids", [])), reverse=True)
        elif sort_by == "name":
            to_review = sorted(to_review, key=lambda x: (x.get("name") or "").lower())
        # default: newest (already sorted by created_at desc above)

        cards = [
            identity_card(identity, crop_files, lane_color="blue", show_actions=True, is_admin=is_admin)
            for identity in to_review
        ]
        cards = [c for c in cards if c]  # Filter None

        if cards:
            content = Div(*cards)
        else:
            content = Div(
                "All caught up! No new faces to review right now.",
                cls="text-center py-12 text-slate-400"
            )

    # Build header with optional sort controls (browse mode only)
    header = section_header(
        "New Matches",
        f"{counts['to_review']} faces the AI matched \u2014 confirm or correct",
        view_mode=view_mode,
        section="to_review"
    )
    if view_mode == "browse":
        return Div(
            Div(header, _sort_control("to_review", sort_by), cls="flex items-center justify-between flex-wrap gap-2 mb-6"),
            triage_bar,
            content,
            cls="space-y-4"
        )
    return Div(header, triage_bar, content, cls="space-y-6")


def _sort_control(section: str, current_sort: str) -> Div:
    """Render sort control buttons for a section."""
    options = [
        ("name", "A-Z"),
        ("faces", "Faces"),
        ("newest", "Newest"),
    ]
    buttons = []
    for value, label in options:
        is_active = current_sort == value
        cls = "px-2 py-1 text-xs font-medium rounded transition-colors "
        if is_active:
            cls += "bg-slate-600 text-white"
        else:
            cls += "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50"
        buttons.append(
            A(label, href=f"/?section={section}&sort_by={value}", cls=cls)
        )
    return Div(
        Span("Sort:", cls="text-xs text-slate-500 mr-1"),
        *buttons,
        cls="flex items-center gap-1"
    )


def render_confirmed_section(confirmed: list, crop_files: set, counts: dict, is_admin: bool = True, sort_by: str = "name") -> Div:
    """Render the Confirmed section with optional sorting."""
    # Apply sorting
    if sort_by == "faces":
        confirmed = sorted(confirmed, key=lambda x: len(x.get("anchor_ids", []) + x.get("candidate_ids", [])), reverse=True)
    elif sort_by == "newest":
        confirmed = sorted(confirmed, key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)
    else:  # default: name (A-Z)
        confirmed = sorted(confirmed, key=lambda x: (x.get("name") or "").lower())

    cards = [
        identity_card(identity, crop_files, lane_color="emerald", show_actions=False, is_admin=is_admin)
        for identity in confirmed
    ]
    cards = [c for c in cards if c]

    if cards:
        content = Div(*cards)
    else:
        content = Div(
            "No confirmed identities yet. Browse the inbox to help identify faces.",
            cls="text-center py-12 text-slate-400"
        )

    return Div(
        Div(
            section_header("People", f"{counts['confirmed']} identified \u2014 click anyone to see all their photos"),
            _sort_control("confirmed", sort_by),
            cls="flex items-center justify-between flex-wrap gap-2 mb-6"
        ),
        content,
        cls="space-y-4"
    )


def render_skipped_section(skipped: list, crop_files: set, counts: dict,
                           is_admin: bool = True, view_mode: str = "focus",
                           current_id: str = None) -> Div:
    """Render the Skipped section with Focus or Browse mode.

    Focus mode: guided one-at-a-time review with photo context and ML suggestions.
    Browse mode: grid of identity cards with lazy-loaded ML hints.
    """
    header = section_header(
        "Help Identify",
        f"{counts['skipped']} face{'s' if counts['skipped'] != 1 else ''} we need your help with \u2014 your family knowledge could be the key",
        view_mode=view_mode,
        section="skipped",
    )

    if view_mode == "focus":
        # Sort by actionability for focus mode
        sorted_skipped = _sort_skipped_by_actionability(skipped)

        # If a specific identity was requested, move it to the front
        if current_id:
            current_identity = None
            remaining = []
            for item in sorted_skipped:
                if item["identity_id"] == current_id:
                    current_identity = item
                else:
                    remaining.append(item)
            if not current_identity:
                for item in skipped:
                    if item["identity_id"] == current_id:
                        current_identity = item
                        break
            if current_identity:
                sorted_skipped = [current_identity] + remaining[:9]

        if sorted_skipped:
            # Build Up Next carousel
            up_next = None
            if len(sorted_skipped) > 1:
                up_next = Div(
                    H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                    Div(
                        *[identity_card_mini(i, crop_files, clickable=True) for i in sorted_skipped[1:6]],
                        Div(
                            f"+{len(sorted_skipped) - 6} more",
                            cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square"
                        ) if len(sorted_skipped) > 6 else None,
                        cls="flex gap-3 overflow-x-auto pb-2"
                    ),
                    cls="mt-6"
                )

            # Progress counter
            total = counts["skipped"]
            progress = _skipped_focus_progress()

            content = Div(
                progress,
                skipped_card_expanded(sorted_skipped[0], crop_files, is_admin=is_admin),
                up_next,
                id="skipped-focus-container",
                data_focus_mode="skipped",
            )
        else:
            content = Div(
                Div("🎉", cls="text-4xl mb-4"),
                H3("All caught up!", cls="text-lg font-medium text-white"),
                P("No faces need help right now.", cls="text-slate-400 mt-1"),
                A(
                    "← Back to Inbox",
                    href="/?section=to_review",
                    cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium"
                ),
                cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-12 text-center",
                id="skipped-focus-container",
            )

        return Div(header, content, cls="space-y-6")

    # Browse mode (default fallback) — sort by actionability (best leads first)
    sorted_browse = _sort_skipped_by_actionability(skipped)
    ids_with_proposals = _get_identities_with_proposals()
    cards = []
    for identity in sorted_browse:
        card = identity_card(identity, crop_files, lane_color="stone", show_actions=False, is_admin=is_admin)
        if card:
            # Add lazy-loaded ML hint below each skipped card
            identity_id = identity["identity_id"]
            # Add actionability badge
            badge = _actionability_badge(identity_id, ids_with_proposals)
            hint = Div(
                id=f"skip-hint-{identity_id}",
                hx_get=f"/api/identity/{identity_id}/skip-hints",
                hx_trigger="revealed",
                hx_swap="innerHTML",
                cls="ml-4 mt-1 mb-3",
            )
            # Wrapper carries data-name so sidebar filter hides card+hint together
            raw_name = (identity.get("name") or "").lower()
            cards.append(Div(badge, card, hint, cls="identity-card-wrapper", data_name=raw_name))

    if cards:
        content = Div(*cards)
    else:
        content = Div(
            "No unresolved faces right now. Check the inbox for new arrivals.",
            cls="text-center py-12 text-slate-400"
        )

    return Div(header, content, cls="space-y-6")


_skipped_neighbor_cache = None
_skipped_neighbor_cache_key = None


def _get_skipped_neighbor_distances(skipped: list) -> dict:
    """Get best-neighbor distances for all skipped identities.

    Uses proposals first, falls back to batch neighbor computation.
    Results are cached for the lifetime of the process (invalidated on data reload).
    """
    global _skipped_neighbor_cache, _skipped_neighbor_cache_key
    cache_key = len(skipped)  # Simple cache invalidation
    if _skipped_neighbor_cache is not None and _skipped_neighbor_cache_key == cache_key:
        return _skipped_neighbor_cache

    ids_with_proposals = _get_identities_with_proposals()
    result = {}

    # First, use proposals for any identities that have them
    for identity in skipped:
        iid = identity.get("identity_id", "")
        if iid in ids_with_proposals:
            best = _get_best_proposal_for_identity(iid)
            if best:
                target_name = best.get("target_name", best.get("name", ""))
                result[iid] = (best.get("distance", 999), best.get("confidence", "LOW"), target_name)

    # For identities without proposals, compute batch neighbors
    needs_computation = [i["identity_id"] for i in skipped if i["identity_id"] not in result]
    if needs_computation:
        try:
            from core.neighbors import batch_best_neighbor_distances
            registry = load_registry()
            face_data = get_face_data()
            batch_results = batch_best_neighbor_distances(needs_computation, registry, face_data)
            for iid, (dist, neighbor_id, neighbor_name) in batch_results.items():
                if dist < 999:
                    if dist < 0.80:
                        confidence = "VERY HIGH"
                    elif dist < 1.00:
                        confidence = "HIGH"
                    elif dist < 1.20:
                        confidence = "MODERATE"
                    else:
                        confidence = "LOW"
                    result[iid] = (dist, confidence, neighbor_name or "")
        except (ImportError, Exception) as e:
            print(f"[sort] Batch neighbor computation failed: {e}")

    _skipped_neighbor_cache = result
    _skipped_neighbor_cache_key = cache_key
    return result


def _identity_quality_score(identity: dict) -> float:
    """Get the best face quality score for an identity (0-100).

    Used for ordering — clear, high-quality faces should appear before
    blurry or small ones within the same confidence tier.
    """
    face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    if not face_ids:
        return 0.0
    best_id = get_best_face_id(face_ids)
    if best_id:
        return compute_face_quality_score(best_id)
    return 0.0


def _sort_skipped_by_actionability(skipped: list) -> list:
    """Sort skipped identities by actionability — best leads first.

    Priority tiers (lower = higher priority):
      0: Has VERY HIGH confidence match (near-certain)
      1: Has HIGH confidence match
      2: Has MODERATE or lower match
      3: No matches found

    Within each tier, sort by:
      1. Named match target bonus (named targets like "Rica Moussafer" before "Unidentified Person 310")
      2. Distance ascending (closest match first)
      3. Face quality descending (clear faces before blurry ones)

    Uses proposals when available, falls back to real-time neighbor computation.
    """
    neighbor_data = _get_skipped_neighbor_distances(skipped)

    def _actionability_key(x):
        iid = x.get("identity_id", "")
        match = neighbor_data.get(iid)

        if match:
            dist, confidence, target_name = match
            if confidence == "VERY HIGH":
                tier = 0
            elif confidence == "HIGH":
                tier = 1
            elif confidence == "MODERATE":
                tier = 2
            else:
                tier = 3

            # Named match bonus: 0 if target is named, 1 if unidentified
            is_unidentified = 1 if (not target_name or target_name.startswith("Unidentified")) else 0

            # Quality penalty (negative so higher quality sorts first)
            quality = _identity_quality_score(x)

            return (tier, is_unidentified, dist, -quality)
        else:
            quality = _identity_quality_score(x)
            return (4, 1, 999, -quality)

    return sorted(skipped, key=_actionability_key)


def _actionability_badge(identity_id: str, ids_with_proposals: set = None):
    """Return a visual badge for an identity's actionability level.

    Uses cached neighbor data from _get_skipped_neighbor_distances() when available,
    falls back to proposals. Returns None if the identity has no leads.
    """
    # Try cached neighbor distances first
    if _skipped_neighbor_cache and identity_id in _skipped_neighbor_cache:
        cached = _skipped_neighbor_cache[identity_id]
        confidence = cached[1]  # (distance, confidence, target_name)
    else:
        # Fallback to proposals
        if ids_with_proposals and identity_id not in ids_with_proposals:
            return None
        best = _get_best_proposal_for_identity(identity_id)
        if not best:
            return None
        confidence = best.get("confidence", "")

    if confidence in ("VERY HIGH", "HIGH"):
        return Div(
            Span("Strong lead", cls="text-xs font-bold text-emerald-300"),
            Span(" — ML found a likely match", cls="text-xs text-slate-400"),
            cls="px-3 py-1 bg-emerald-900/30 border border-emerald-500/30 rounded-lg mb-1",
        )
    elif confidence == "MODERATE":
        return Div(
            Span("Good lead", cls="text-xs font-bold text-amber-300"),
            Span(" — possible match found", cls="text-xs text-slate-400"),
            cls="px-3 py-1 bg-amber-900/30 border border-amber-500/30 rounded-lg mb-1",
        )
    return None


def _skipped_focus_progress() -> Div:
    """Build progress counter for skipped focus mode.

    Uses client-side cookie to persist count across HTMX swaps.
    """
    return Div(
        Div(
            Span("Reviewed: ", cls="text-slate-400"),
            Span("0", id="skipped-reviewed-count", cls="text-white font-bold"),
            Span(" this session", cls="text-slate-400"),
            cls="text-sm"
        ),
        A(
            "← Exit Focus Mode",
            href="/?section=skipped&view=browse",
            cls="text-sm text-slate-400 hover:text-white transition-colors"
        ),
        Script("""
            (function() {
                var key = 'skipped_focus_count';
                function getCount() {
                    var stored = document.cookie.split(';').find(function(c) { return c.trim().startsWith(key + '='); });
                    return stored ? parseInt(stored.split('=')[1]) : 0;
                }
                function setCount(n) {
                    document.cookie = key + '=' + n + '; path=/; max-age=86400';
                    var el = document.getElementById('skipped-reviewed-count');
                    if (el) el.textContent = n;
                }
                // Initialize on load
                var el = document.getElementById('skipped-reviewed-count');
                if (el) el.textContent = getCount();
                // Increment when the focus container is swapped (action was taken)
                document.body.addEventListener('htmx:afterSwap', function(evt) {
                    if (evt.detail.target && evt.detail.target.id === 'skipped-focus-container') {
                        setCount(getCount() + 1);
                    }
                });
            })();
        """),
        cls="flex items-center justify-between mb-4",
        id="skipped-focus-progress",
    )


def skipped_card_expanded(identity: dict, crop_files: set, is_admin: bool = True) -> Div:
    """
    Expanded identity card for Needs Help Focus Mode.

    Shows the face prominently, the best ML suggestion side-by-side,
    photo context (full photo with collection info), and action buttons:
    - Same Person (Y): merge with top suggestion
    - Not Same (N): reject top suggestion
    - I Know Them (Enter): name input + confirm
    - Skip (S): advance without action
    """
    identity_id = identity["identity_id"]
    raw_name = ensure_utf8_display(identity.get("name"))
    name = raw_name or "Unidentified Person"
    state = identity["state"]

    # Get all faces
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_count = len(all_face_ids)

    # Get best-quality face for main display
    main_crop_url = None
    main_photo_id = None
    main_face_id = get_best_face_id(all_face_ids)
    if main_face_id:
        main_crop_url = resolve_face_image_url(main_face_id, crop_files)
        main_photo_id = get_photo_id_for_face(main_face_id)

    # Get photo context (collection, other identified people)
    photo_context_el = _build_skipped_photo_context(main_face_id, main_photo_id, identity_id)

    # Get top ML suggestions for side-by-side display + strip
    suggestion_el, other_matches_strip = _build_skipped_suggestion_with_strip(identity_id, crop_files)

    # Action buttons
    if is_admin:
        actions = _build_skipped_focus_actions(identity_id, state)
    else:
        actions = Div(
            Button(
                "I Know This Person",
                cls="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors min-h-[44px]",
                **{"_": f"on click toggle .hidden on #skipped-name-form-{identity_id}"},
                type="button",
            ),
            cls="flex items-center gap-3 mt-6"
        )

    # Inline name form (hidden by default)
    name_form = Div(
        Form(
            Input(
                type="text",
                name="name",
                placeholder="Type their name...",
                cls="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent min-h-[44px]",
                autofocus=True,
            ),
            Button(
                "Confirm Identity",
                cls="px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors min-h-[44px]",
                type="submit",
            ),
            Button(
                "Cancel",
                cls="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors min-h-[44px]",
                type="button",
                **{"_": f"on click add .hidden to #skipped-name-form-{identity_id}"},
            ),
            hx_post=f"/api/skipped/{identity_id}/name-and-confirm",
            hx_target="#skipped-focus-container",
            hx_swap="outerHTML",
            cls="flex gap-3 items-center",
        ),
        cls="mt-4 hidden",
        id=f"skipped-name-form-{identity_id}",
    )

    # Additional faces preview
    face_previews = []
    for face_entry in all_face_ids[1:4]:
        fid = face_entry if isinstance(face_entry, str) else face_entry.get("face_id", "")
        crop_url = resolve_face_image_url(fid, crop_files)
        if crop_url:
            face_photo_id = get_photo_id_for_face(fid)
            if face_photo_id:
                face_previews.append(
                    Button(
                        Img(src=crop_url, cls="w-20 h-20 rounded-lg object-cover border border-slate-600 hover:border-indigo-400 transition-colors", alt=f"Face"),
                        cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-lg transition-all",
                        hx_get=f"/photo/{face_photo_id}/partial?face={fid}&identity_id={identity_id}",
                        hx_target="#photo-modal-content",
                        **{"_": "on click remove .hidden from #photo-modal"},
                        type="button",
                        title="Click to view photo",
                    )
                )

    return Div(
        # Top row: This Person + Best Match side by side (large faces ~300px)
        Div(
            # Left: This Person
            Div(
                Div("Who is this?", cls="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wide"),
                Button(
                    Div(
                        Img(
                            src=main_crop_url or "",
                            alt=name,
                            cls="w-full h-full object-cover"
                        ) if main_crop_url else Span("?", cls="text-6xl text-slate-500"),
                        cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center"
                    ),
                    cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-lg transition-all",
                    hx_get=f"/photo/{main_photo_id}/partial?face={main_face_id}&identity_id={identity_id}" if main_photo_id else None,
                    hx_target="#photo-modal-content",
                    **{"_": "on click remove .hidden from #photo-modal"} if main_photo_id else {},
                    type="button",
                    title="Click to view full photo",
                ) if main_photo_id else Div(
                    Img(src=main_crop_url, alt=name, cls="w-full h-full object-cover") if main_crop_url else Span("?", cls="text-6xl text-slate-500"),
                    cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center"
                ),
                Div(
                    P(name, cls="text-lg font-semibold text-white mt-2"),
                    P(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-xs text-slate-400"),
                ),
                Div(
                    A("View Photo", href="#", cls="text-xs text-indigo-400 hover:text-indigo-300 inline-block",
                      hx_get=f"/photo/{main_photo_id}/partial?face={main_face_id}&identity_id={identity_id}",
                      hx_target="#photo-modal-content",
                      **{"_": "on click remove .hidden from #photo-modal"},
                    ),
                    share_button(main_photo_id, style="link", label="Share"),
                    cls="flex items-center gap-3 mt-1",
                ) if main_photo_id else None,
                # Additional faces
                Div(*face_previews, cls="flex gap-2 mt-3") if face_previews else None,
                cls="flex-1 flex flex-col items-center sm:items-start"
            ),
            # Right: Best Match suggestion
            suggestion_el,
            cls="flex flex-col sm:flex-row gap-8 items-start justify-center"
        ),
        # Other matches strip (horizontal scroll)
        other_matches_strip,
        # Photo context
        photo_context_el,
        # Neighbors container — always auto-loads ML suggestions
        Div(
            id=f"neighbors-{identity_id}", cls="mt-4",
            hx_get=f"/api/identity/{identity_id}/neighbors?from_focus=true&focus_section=skipped",
            hx_trigger="load",
            hx_swap="innerHTML",
        ),
        # Name form (inline, hidden by default)
        name_form,
        # Sticky action bar at bottom
        actions,
        cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-4 sm:p-6 pb-24 sm:pb-6",
        id="skipped-focus-card",
        **{"data-focus-mode": "skipped"},
    )


def _build_skipped_photo_context(face_id: str, photo_id: str, identity_id: str):
    """Build photo context panel showing collection info and co-identified faces."""
    if not photo_id:
        return None

    _build_caches()
    photo = _photo_cache.get(photo_id)
    if not photo:
        return None

    collection = photo.get("collection") or photo.get("source") or ""
    photo_url = storage.get_photo_url(photo.get("path") or photo.get("filename") or "")

    # Find other identified faces in this photo
    registry = load_registry()
    other_people = []
    for fid in photo.get("face_ids", []):
        if fid == face_id:
            continue
        # Look up which identity this face belongs to
        for state_name in ["CONFIRMED", "PROPOSED", "INBOX", "SKIPPED"]:
            try:
                state_enum = IdentityState[state_name]
                identities = registry.list_identities(state=state_enum)
                for ident in identities:
                    if ident["identity_id"] == identity_id:
                        continue
                    all_faces = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
                    face_strs = [f if isinstance(f, str) else f.get("face_id", "") for f in all_faces]
                    if fid in face_strs:
                        ident_name = ensure_utf8_display(ident.get("name") or "")
                        if ident_name and not ident_name.startswith("Unidentified"):
                            other_people.append(ident_name)
                        break
            except (KeyError, AttributeError):
                continue

    other_people = list(set(other_people))[:5]  # Deduplicate, limit

    context_items = []
    if collection:
        context_items.append(Span(f"Collection: {collection}", cls="text-xs text-slate-400"))
    if other_people:
        context_items.append(Span(f"Also in photo: {', '.join(other_people)}", cls="text-xs text-slate-300"))

    if not context_items and not photo_url:
        return None

    return Div(
        Div(
            Span("Photo Context", cls="text-xs font-medium text-slate-400 uppercase tracking-wide"),
            share_button(photo_id, style="link", label="Share"),
            cls="flex items-center justify-between mb-2",
        ),
        Div(
            # Small photo thumbnail
            Button(
                Img(
                    src=photo_url,
                    cls="w-20 h-14 object-cover rounded border border-slate-600 hover:border-indigo-400 transition-colors",
                    alt="Source photo",
                ),
                cls="p-0 bg-transparent cursor-pointer flex-shrink-0",
                hx_get=f"/photo/{photo_id}/partial?face={face_id}&identity_id={identity_id}",
                hx_target="#photo-modal-content",
                **{"_": "on click remove .hidden from #photo-modal"},
                type="button",
                title="View full photo",
            ),
            Div(*context_items, cls="flex flex-col gap-1") if context_items else None,
            cls="flex items-center gap-3"
        ),
        cls="mt-4 bg-slate-700/30 rounded-lg p-3 border border-slate-700/50"
    )


def _compute_best_neighbor(identity_id: str):
    """Compute best neighbor for an identity using real-time embedding distance.

    Returns a dict with keys matching proposal format:
      target_identity_id, target_identity_name, distance, confidence
    or None if no neighbor found.
    """
    try:
        from core.neighbors import find_nearest_neighbors
        registry = load_registry()
        photo_registry = load_photo_registry()
        face_data = get_face_data()
        neighbors = find_nearest_neighbors(
            identity_id, registry, photo_registry, face_data, limit=1
        )
        if not neighbors:
            return None
        n = neighbors[0]
        dist = n.get("distance", 999)
        # Map distance to confidence tier (same thresholds as clustering)
        if dist < 0.80:
            confidence = "VERY HIGH"
        elif dist < 1.00:
            confidence = "HIGH"
        elif dist < 1.20:
            confidence = "MODERATE"
        else:
            confidence = "LOW"
        return {
            "target_identity_id": n["identity_id"],
            "target_identity_name": n.get("name", "Unknown"),
            "distance": dist,
            "confidence": confidence,
        }
    except (ImportError, Exception):
        return None


def _compute_top_neighbors(identity_id: str, limit: int = 5):
    """Compute top N neighbors for an identity using real-time embedding distance.

    Returns a list of dicts with keys: target_identity_id, target_identity_name, distance, confidence.
    """
    try:
        from core.neighbors import find_nearest_neighbors
        registry = load_registry()
        photo_registry = load_photo_registry()
        face_data = get_face_data()
        neighbors = find_nearest_neighbors(
            identity_id, registry, photo_registry, face_data, limit=limit
        )
        results = []
        for n in neighbors:
            dist = n.get("distance", 999)
            if dist < 0.80:
                confidence = "VERY HIGH"
            elif dist < 1.00:
                confidence = "HIGH"
            elif dist < 1.20:
                confidence = "MODERATE"
            else:
                confidence = "LOW"
            results.append({
                "target_identity_id": n["identity_id"],
                "target_identity_name": n.get("name", "Unknown"),
                "distance": dist,
                "confidence": confidence,
            })
        return results
    except (ImportError, Exception):
        return []


def _get_best_match_for_identity(identity_id: str):
    """Get best match: first from proposals, then from real-time neighbors."""
    best = _get_best_proposal_for_identity(identity_id)
    if best:
        return best
    return _compute_best_neighbor(identity_id)


def _build_skipped_suggestion(identity_id: str, crop_files: set):
    """Build the 'Best Match' side-by-side panel for a skipped identity.

    Returns a single element (for backward compat with any callers).
    """
    el, _ = _build_skipped_suggestion_with_strip(identity_id, crop_files)
    return el


def _resolve_match_crop(target_id: str, crop_files: set):
    """Resolve the first available face crop URL for an identity."""
    try:
        registry = load_registry()
        target_identity = registry.get_identity(target_id)
        target_faces = target_identity.get("anchor_ids", []) + target_identity.get("candidate_ids", [])
        for f in target_faces:
            fid = f if isinstance(f, str) else f.get("face_id", "")
            url = resolve_face_image_url(fid, crop_files)
            if url:
                return url
    except (KeyError, Exception):
        pass
    return None


def _confidence_tier(distance: float) -> str:
    """Map embedding distance to confidence tier."""
    if distance < 0.80:
        return "VERY HIGH"
    elif distance < 1.00:
        return "HIGH"
    elif distance < 1.20:
        return "MODERATE"
    return "LOW"


_CONFIDENCE_RING = {"VERY HIGH": "ring-emerald-400", "HIGH": "ring-blue-400", "MODERATE": "ring-amber-400"}
_CONFIDENCE_COLOR = {"VERY HIGH": "text-emerald-300", "HIGH": "text-blue-300", "MODERATE": "text-amber-300"}
_CONFIDENCE_LABEL = {"VERY HIGH": "Strong match", "HIGH": "Good match", "MODERATE": "Possible match", "LOW": "Weak match"}


def _build_skipped_suggestion_with_strip(identity_id: str, crop_files: set):
    """Build 'Best Match' panel + horizontal strip of other matches.

    Returns (suggestion_el, other_matches_strip_el).
    """
    # Fetch up to 5 neighbors
    top_matches = _compute_top_neighbors(identity_id, limit=5)

    # Also check proposals
    best_proposal = _get_best_proposal_for_identity(identity_id)
    if best_proposal:
        # Merge proposal into top of list if not already present
        proposal_id = best_proposal.get("target_identity_id", "")
        if not any(m.get("target_identity_id") == proposal_id for m in top_matches):
            top_matches.insert(0, best_proposal)

    if not top_matches:
        no_match_el = Div(
            Div("Best Match", cls="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wide"),
            P("No ML suggestions yet", cls="text-sm text-slate-500 italic"),
            P("Try 'I Know Them' to name this person", cls="text-xs text-slate-500 mt-1"),
            cls="flex-1 flex flex-col items-center sm:items-start"
        )
        return no_match_el, None

    # Best match (primary comparison)
    best = top_matches[0]
    target_id = best.get("target_identity_id", "")
    target_name = ensure_utf8_display(best.get("target_identity_name", "Unknown"))
    confidence = best.get("confidence", "")
    ring_cls = _CONFIDENCE_RING.get(confidence, "ring-slate-500")
    color_cls = _CONFIDENCE_COLOR.get(confidence, "text-slate-300")
    confidence_label = _CONFIDENCE_LABEL.get(confidence, "Match")
    suggestion_crop_url = _resolve_match_crop(target_id, crop_files)

    suggestion_el = Div(
        Div("Best Match", cls="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wide"),
        Div(
            Img(
                src=suggestion_crop_url or "",
                alt=target_name,
                cls="w-full h-full object-cover"
            ) if suggestion_crop_url else Span("?", cls="text-4xl text-slate-500"),
            cls=f"w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center ring-3 {ring_cls}"
        ),
        Div(
            P(target_name, cls="text-lg font-semibold text-white mt-2"),
            P(
                Span(confidence_label, cls=f"font-bold {color_cls}"),
                cls="text-sm mt-1"
            ),
        ),
        cls="flex-1 flex flex-col items-center sm:items-start"
    )

    # Other matches strip (2nd through 5th)
    other_matches_strip = None
    other_matches = top_matches[1:]
    if other_matches:
        strip_items = []
        for match in other_matches:
            m_id = match.get("target_identity_id", "")
            m_name = ensure_utf8_display(match.get("target_identity_name", "Unknown"))
            m_conf = match.get("confidence", "LOW")
            m_ring = _CONFIDENCE_RING.get(m_conf, "ring-slate-500")
            m_crop = _resolve_match_crop(m_id, crop_files)
            m_label = _CONFIDENCE_LABEL.get(m_conf, "Match")
            strip_items.append(
                Div(
                    Div(
                        Img(src=m_crop or "", alt=m_name, cls="w-full h-full object-cover") if m_crop else Span("?", cls="text-lg text-slate-500"),
                        cls=f"w-20 h-20 sm:w-24 sm:h-24 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center ring-2 {m_ring} hover:scale-105 transition-transform"
                    ),
                    P(m_name[:20] + ("..." if len(m_name) > 20 else ""), cls="text-xs text-slate-300 mt-1 text-center truncate max-w-[80px]"),
                    P(m_label, cls=f"text-[10px] {_CONFIDENCE_COLOR.get(m_conf, 'text-slate-400')} text-center"),
                    cls="flex flex-col items-center flex-shrink-0 cursor-pointer hover:bg-slate-700/50 rounded-lg p-1 transition-colors",
                    title=f"{m_name} — {m_label}",
                )
            )
        other_matches_strip = Div(
            Div("More matches", cls="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wide"),
            Div(*strip_items, cls="flex gap-3 overflow-x-auto pb-2"),
            cls="mt-5 pt-4 border-t border-slate-700/50"
        )

    return suggestion_el, other_matches_strip


def _build_skipped_focus_actions(identity_id: str, state: str) -> Div:
    """Build action buttons for skipped focus mode."""
    best = _get_best_match_for_identity(identity_id)
    has_suggestion = best is not None

    buttons = []

    if has_suggestion:
        target_id = best.get("target_identity_id", "")
        target_name = ensure_utf8_display(best.get("target_identity_name", ""))
        buttons.append(
            Button(
                "✓ Same Person",
                cls="px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors min-h-[44px]",
                hx_post=f"/api/identity/{target_id}/merge/{identity_id}?from_focus=true&focus_section=skipped",
                hx_target="#skipped-focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-confirm",
                title=f"Merge with {target_name}" if target_name else "Merge with suggestion",
                **{"data-undo-url": f"/api/identity/{target_id}/undo-merge", "data-undo-type": "merge",
                   "data-undo-identity": identity_id},
            )
        )
        buttons.append(
            Button(
                "✗ Not Same",
                cls="px-4 py-2 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-colors min-h-[44px]",
                hx_post=f"/api/skipped/{identity_id}/reject-suggestion?suggestion_id={target_id}",
                hx_target="#skipped-focus-container",
                hx_swap="outerHTML",
                type="button",
                id="focus-btn-reject",
                title="Not the same person — reject this suggestion",
                **{"data-undo-url": f"/api/identity/{identity_id}/unreject/{target_id}", "data-undo-type": "reject",
                   "data-undo-identity": identity_id},
            )
        )

    buttons.append(
        Button(
            "I Know Them",
            cls="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors min-h-[44px]",
            type="button",
            id="focus-btn-name",
            **{"_": f"on click remove .hidden from #skipped-name-form-{identity_id} then set focus to the first <input/> in #skipped-name-form-{identity_id}"},
            title="I recognize this person — enter their name",
        )
    )
    buttons.append(
        Button(
            "→ Skip",
            cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors min-h-[44px]",
            hx_post=f"/api/skipped/{identity_id}/focus-skip",
            hx_target="#skipped-focus-container",
            hx_swap="outerHTML",
            type="button",
            id="focus-btn-skip",
            title="Skip — come back later",
            **{"data-undo-type": "skip", "data-undo-identity": identity_id},
        )
    )

    shortcut_text = "Y Same · N Different · Enter Name · S Skip · Z Undo" if has_suggestion else "Enter Name · S Skip"

    return Div(
        Div(*buttons, cls="flex flex-wrap items-center gap-3"),
        Div(shortcut_text, cls="text-xs text-slate-500 mt-2 hidden sm:block"),
        # Undo toast (hidden by default, shown after undo-able action)
        Div(
            id="undo-toast",
            cls="hidden fixed bottom-20 left-1/2 -translate-x-1/2 bg-slate-700 text-white px-4 py-2 rounded-lg shadow-lg z-50 text-sm flex items-center gap-3",
        ),
        cls="sticky bottom-0 bg-slate-800/95 backdrop-blur-sm border-t border-slate-700 p-4 -mx-4 sm:-mx-6 -mb-24 sm:-mb-6 mt-6 rounded-b-xl z-10",
    )


def get_next_skipped_focus_card(exclude_id: str = None) -> Div:
    """
    Get the next skipped identity card for focus mode review.

    Returns an expanded identity card + Up Next carousel for skipped identities,
    sorted by actionability. Returns empty state if no items remain.
    """
    registry = load_registry()
    crop_files = get_crop_files()

    skipped = registry.list_identities(state=IdentityState.SKIPPED)

    # Filter out the just-actioned item
    if exclude_id:
        skipped = [i for i in skipped if i["identity_id"] != exclude_id]

    # Sort by actionability
    sorted_skipped = _sort_skipped_by_actionability(skipped)

    if sorted_skipped:
        # Build Up Next carousel
        up_next = None
        if len(sorted_skipped) > 1:
            up_next = Div(
                H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                Div(
                    *[identity_card_mini(i, crop_files, clickable=True) for i in sorted_skipped[1:6]],
                    Div(
                        f"+{len(sorted_skipped) - 6} more",
                        cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square"
                    ) if len(sorted_skipped) > 6 else None,
                    cls="flex gap-3 overflow-x-auto pb-2"
                ),
                cls="mt-6"
            )

        progress = _skipped_focus_progress()

        return Div(
            progress,
            skipped_card_expanded(sorted_skipped[0], crop_files, is_admin=True),
            up_next,
            id="skipped-focus-container",
            data_focus_mode="skipped",
        )
    else:
        return Div(
            Div("🎉", cls="text-4xl mb-4"),
            H3("All caught up!", cls="text-lg font-medium text-white"),
            P("You've reviewed all the faces that need help.", cls="text-slate-400 mt-1"),
            A(
                "← Back to Inbox",
                href="/?section=to_review",
                cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium"
            ),
            cls="bg-slate-800 rounded-xl shadow-lg border border-slate-700 p-12 text-center",
            id="skipped-focus-container",
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
            "No dismissed items. Rejected matches will appear here.",
            cls="text-center py-12 text-slate-400"
        )

    return Div(
        section_header("Dismissed", f"{counts['rejected']} items dismissed"),
        content,
        cls="space-y-6"
    )


def _photo_nav_url(photo_id: str, index: int, photos: list, total: int) -> str:
    """Build /photo/{id}/partial URL with prev/next navigation context."""
    from urllib.parse import urlencode
    params = {"nav_idx": str(index), "nav_total": str(total)}
    if index > 0:
        params["prev_id"] = photos[index - 1]["photo_id"]
    if index < total - 1:
        params["next_id"] = photos[index + 1]["photo_id"]
    return f"/photo/{photo_id}/partial?{urlencode(params)}"


def render_photos_section(counts: dict, registry, crop_files: set,
                          filter_source: str = "", sort_by: str = "newest",
                          filter_collection: str = "") -> Div:
    """
    Render the Photos section - a grid view of all photos.

    This is the photo-centric workflow, complementing the face-centric inbox.

    Args:
        counts: Sidebar counts dict
        registry: Identity registry
        crop_files: Set of available crop filenames
        filter_source: Filter by source/provenance (empty = all)
        sort_by: Sort order (newest, oldest, most_faces, collection)
        filter_collection: Filter by collection/classification (empty = all)
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
    collections_set = set()
    for photo_id, photo_data in _photo_cache.items():
        source = photo_data.get("source", "")
        collection = photo_data.get("collection", "")
        if source:
            sources_set.add(source)
        if collection:
            collections_set.add(collection)

        # Get identified faces in this photo
        identified_faces = []
        confirmed_count = 0
        for face in photo_data.get("faces", []):
            face_id = face["face_id"]
            identity = get_identity_for_face(registry, face_id)
            if identity and identity.get("name"):
                identified_faces.append({
                    "name": identity.get("name"),
                    "face_id": face_id,
                    "identity_id": identity.get("identity_id"),
                })
                if identity.get("state") == "CONFIRMED":
                    confirmed_count += 1

        face_count = len(photo_data.get("faces", []))
        photos.append({
            "photo_id": photo_id,
            "filename": photo_data.get("filename", "unknown"),
            "source": source,
            "collection": collection,
            "face_count": face_count,
            "identified_count": len(identified_faces),
            "confirmed_count": confirmed_count,
            "identified_faces": identified_faces[:4],  # Max 4 for display
        })

    sources = sorted(sources_set)
    collections = sorted(collections_set)

    # Apply filters
    if filter_source:
        photos = [p for p in photos if p["source"] == filter_source]
    if filter_collection:
        photos = [p for p in photos if p["collection"] == filter_collection]

    # Apply sorting
    if sort_by == "oldest":
        photos = sorted(photos, key=lambda p: p["filename"])
    elif sort_by == "newest":
        photos = sorted(photos, key=lambda p: p["filename"], reverse=True)
    elif sort_by == "most_faces":
        photos = sorted(photos, key=lambda p: p["face_count"], reverse=True)
    elif sort_by == "collection":
        photos = sorted(photos, key=lambda p: (p["collection"] or p["source"] or "zzz", p["filename"]))

    # Build per-collection stats
    collection_stats = {}
    for p in photos:
        coll = p["collection"] or p["source"] or "Uncategorized"
        if coll not in collection_stats:
            collection_stats[coll] = {"photo_count": 0, "face_count": 0, "identified_count": 0}
        collection_stats[coll]["photo_count"] += 1
        collection_stats[coll]["face_count"] += p["face_count"]
        collection_stats[coll]["identified_count"] += p["identified_count"]

    # Build subtitle — scoped to current view
    active_filters = []
    if filter_collection:
        active_filters.append(filter_collection)
    if filter_source:
        active_filters.append(f"from {filter_source}")
    if active_filters:
        subtitle = f"{' '.join(active_filters)} \u2014 {len(photos)} photo{'s' if len(photos) != 1 else ''}"
    else:
        subtitle_parts = [f"{len(photos)} photo{'s' if len(photos) != 1 else ''}"]
        if len(collections) > 1:
            subtitle_parts.append(f"{len(collections)} collections")
        subtitle = " \u2022 ".join(subtitle_parts)

    # Build filter/sort options
    from urllib.parse import quote
    _fc = quote(filter_collection)
    _fs = quote(filter_source)

    collection_options = [Option("All Collections", value="", selected=not filter_collection)]
    for c in collections:
        collection_options.append(Option(c, value=c, selected=(filter_collection == c)))

    source_options = [Option("All Sources", value="", selected=not filter_source)]
    for s in sources:
        source_options.append(Option(s, value=s, selected=(filter_source == s)))

    sort_options = [
        Option("Newest First", value="newest", selected=(sort_by == "newest")),
        Option("Oldest First", value="oldest", selected=(sort_by == "oldest")),
        Option("Most Faces", value="most_faces", selected=(sort_by == "most_faces")),
        Option("By Collection", value="collection", selected=(sort_by == "collection")),
    ]

    # Filter/sort controls
    filter_bar = Div(
        # Collection filter
        Div(
            Label("Collection:", cls="text-sm text-slate-400 mr-2 flex-shrink-0"),
            Select(
                *collection_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                    "focus:ring-2 focus:ring-indigo-500 min-w-0 max-w-[10rem] sm:max-w-none truncate",
                onchange=f"window.location.href='/?section=photos&filter_collection=' + encodeURIComponent(this.value) + '&filter_source={_fs}&sort_by={sort_by}'"
            ),
            cls="flex items-center min-w-0"
        ),
        # Source filter
        Div(
            Label("Source:", cls="text-sm text-slate-400 mr-2 flex-shrink-0"),
            Select(
                *source_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                    "focus:ring-2 focus:ring-indigo-500 min-w-0 max-w-[10rem] sm:max-w-none truncate",
                onchange=f"window.location.href='/?section=photos&filter_collection={_fc}&filter_source=' + encodeURIComponent(this.value) + '&sort_by={sort_by}'"
            ),
            cls="flex items-center min-w-0"
        ),
        # Sort
        Div(
            Label("Sort:", cls="text-sm text-slate-400 mr-2 flex-shrink-0"),
            Select(
                *sort_options,
                cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5 "
                    "focus:ring-2 focus:ring-indigo-500 min-w-0",
                onchange=f"window.location.href='/?section=photos&filter_collection={_fc}&filter_source={_fs}&sort_by=' + this.value"
            ),
            cls="flex items-center min-w-0"
        ),
        # Select toggle button
        Button(
            "Select",
            id="photo-select-toggle",
            cls="px-3 py-1.5 text-sm border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors",
            type="button",
            data_action="toggle-photo-select",
        ),
        # Result count
        Span(f"{len(photos)} photo{'s' if len(photos) != 1 else ''}", cls="text-sm text-slate-500 ml-auto"),
        cls="filter-bar flex flex-wrap items-center gap-4 bg-slate-800 rounded-lg p-3 border border-slate-700 mb-4"
    )

    # Photo grid — build with navigation context
    total_photos = len(photos)
    photo_cards = []
    for pi, photo in enumerate(photos):
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
                # Select mode checkbox (hidden by default)
                Div(
                    Input(
                        type="checkbox",
                        name="photo_ids",
                        value=photo["photo_id"],
                        cls="w-5 h-5 rounded border-slate-500 bg-slate-700/80 text-indigo-500 focus:ring-indigo-500 cursor-pointer",
                        data_action="photo-select-check",
                    ),
                    cls="photo-select-checkbox absolute top-2 left-2 z-10 hidden",
                ),
                # Face count badge with completion indicator
                Div(
                    Span("\u2713 ", cls="text-emerald-400") if photo["face_count"] > 0 and photo["confirmed_count"] == photo["face_count"] else None,
                    f"{photo['confirmed_count']}/{photo['face_count']}" if photo["confirmed_count"] > 0 else f"{photo['face_count']} face{'s' if photo['face_count'] != 1 else ''}",
                    cls="absolute top-2 right-2 text-white text-xs font-data "
                        "px-2 py-1 rounded-full backdrop-blur-sm "
                        + ("bg-emerald-600/80" if photo["face_count"] > 0 and photo["confirmed_count"] == photo["face_count"]
                           else "bg-black/70" if photo["confirmed_count"] == 0
                           else "bg-indigo-600/70")
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
                Div(
                    P(
                        f"\U0001F4C1 {photo['source']}",
                        cls="text-xs text-slate-500 truncate"
                    ) if photo["source"] else None,
                    Span(
                        share_button(photo['photo_id'], style="icon"),
                        A(
                            "Open",
                            href=f"/photo/{photo['photo_id']}",
                            cls="text-[10px] text-indigo-400 hover:text-indigo-300 underline ml-1",
                            target="_blank",
                        ),
                        cls="flex items-center gap-0.5 flex-shrink-0",
                        **{"_": "on click halt the event's bubbling"},
                    ),
                    cls="flex items-center justify-between mt-0.5"
                ),
                cls="p-3"
            ),
            cls="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden "
                "hover:border-slate-500 transition-colors cursor-pointer group",
            hx_get=_photo_nav_url(photo['photo_id'], pi, photos, total_photos),
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            # Show modal and set navigation index
            **{"_": f"on htmx:afterOnLoad remove .hidden from #photo-modal then js window._photoNavIdx={pi} end"}
        )
        photo_cards.append(card)

    # Build ordered photo ID list for client-side navigation
    import json as _json
    photo_id_list = [p["photo_id"] for p in photos]
    photo_nav_script = Script(f"""
        window._photoNavIds = {_json.dumps(photo_id_list)};
        window._photoNavIdx = -1;
        function photoNavTo(idx) {{
            var ids = window._photoNavIds;
            if (idx < 0 || idx >= ids.length) return;
            window._photoNavIdx = idx;
            var prevId = idx > 0 ? ids[idx-1] : '';
            var nextId = idx < ids.length-1 ? ids[idx+1] : '';
            var url = '/photo/' + ids[idx] + '/partial?nav_idx=' + idx + '&nav_total=' + ids.length;
            if (prevId) url += '&prev_id=' + prevId;
            if (nextId) url += '&next_id=' + nextId;
            htmx.ajax('GET', url, {{target:'#photo-modal-content', swap:'innerHTML'}});
        }}
        // NOTE: Keyboard navigation is handled by the global event delegation
        // handler (data-action dispatch on document). Do NOT add a per-script
        // keydown listener here — it would double-fire with the global one,
        // causing 2 navigations per key press. (BUG-006 fix)
        // Touch swipe for photo modal navigation
        (function() {{
            var mc = document.getElementById('photo-modal-content');
            if (!mc) return;
            var sx = 0, sy = 0;
            mc.addEventListener('touchstart', function(e) {{ sx = e.touches[0].clientX; sy = e.touches[0].clientY; }}, {{passive: true}});
            mc.addEventListener('touchend', function(e) {{
                var dx = e.changedTouches[0].clientX - sx;
                var dy = e.changedTouches[0].clientY - sy;
                if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {{
                    if (dx > 0) photoNavTo(window._photoNavIdx - 1);
                    else photoNavTo(window._photoNavIdx + 1);
                }}
            }});
        }})();
    """)

    # Photo grid layout
    grid = Div(
        *photo_cards,
        photo_nav_script,
        cls="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"
    )

    # Collection stats cards (shown when viewing all collections, not filtered)
    collection_cards = None
    if not filter_collection and not filter_source and len(collection_stats) > 1:
        stat_cards = []
        for coll_name in sorted(collection_stats.keys()):
            stats = collection_stats[coll_name]
            stat_cards.append(
                Div(
                    Div(
                        P(coll_name, cls="text-sm font-medium text-white truncate"),
                        cls="mb-2"
                    ),
                    Div(
                        Span(f"{stats['photo_count']} photo{'s' if stats['photo_count'] != 1 else ''}", cls="text-xs text-slate-400"),
                        Span(" \u2022 ", cls="text-xs text-slate-600"),
                        Span(f"{stats['face_count']} face{'s' if stats['face_count'] != 1 else ''}", cls="text-xs text-slate-400"),
                        Span(" \u2022 ", cls="text-xs text-slate-600"),
                        Span(f"{stats['identified_count']} identified", cls="text-xs text-emerald-400"),
                    ),
                    cls="bg-slate-800/50 border border-slate-700 rounded-lg p-3 cursor-pointer "
                        "hover:border-indigo-500/50 transition-colors",
                    onclick=f"window.location.href='/?section=photos&filter_collection={quote(coll_name)}&sort_by={sort_by}'"
                )
            )
        # Use horizontal scroll for 5+ collections, grid for fewer
        if len(stat_cards) >= 5:
            # Make cards fixed-width for horizontal scrolling
            for card in stat_cards:
                card.attrs["class"] = card.attrs.get("class", "") + " min-w-[180px] flex-shrink-0"
            collection_cards = Div(
                *stat_cards,
                cls="flex gap-3 mb-4 overflow-x-auto pb-2 scrollbar-thin"
            )
        else:
            collection_cards = Div(
                *stat_cards,
                cls="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4"
            )

    # Bulk action bar (hidden until selections exist)
    collection_options_bulk = [Option("Set collection...", value="", disabled=True, selected=True)]
    for c in collections:
        collection_options_bulk.append(Option(c, value=c))

    source_options_bulk = [Option("Set source...", value="", disabled=True, selected=True)]
    for s in sources:
        source_options_bulk.append(Option(s, value=s))

    bulk_action_bar = Div(
        Div(
            Span("0 selected", id="photo-select-count", cls="text-sm font-medium text-white"),
            Button("Select All", type="button", data_action="photo-select-all",
                   cls="px-3 py-1 text-xs border border-slate-600 text-slate-300 rounded hover:bg-slate-700"),
            Button("Clear", type="button", data_action="photo-select-clear",
                   cls="px-3 py-1 text-xs border border-slate-600 text-slate-300 rounded hover:bg-slate-700"),
            Div(
                Select(
                    *collection_options_bulk,
                    id="bulk-move-collection",
                    cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-2 py-1.5",
                ),
                Select(
                    *source_options_bulk,
                    id="bulk-move-source",
                    cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-2 py-1.5",
                ),
                Input(
                    type="url",
                    id="bulk-source-url",
                    placeholder="Source URL...",
                    cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-2 py-1.5 w-40",
                ),
                Button("Apply", type="button", data_action="photo-bulk-move",
                       cls="px-4 py-1.5 text-sm font-bold bg-indigo-600 text-white rounded hover:bg-indigo-500"),
                cls="flex items-center gap-2 flex-wrap",
            ),
            Button("Cancel", type="button", data_action="toggle-photo-select",
                   cls="px-3 py-1 text-xs text-slate-400 hover:text-white"),
            cls="flex items-center gap-4 max-w-5xl mx-auto px-4 flex-wrap"
        ),
        id="photo-bulk-bar",
        cls="hidden fixed bottom-0 left-0 right-0 bg-slate-800 border-t border-slate-700 py-3 z-40",
    )

    # Select mode script using event delegation (CLAUDE.md rule #12)
    select_script = Script("""
        (function() {
            var selectMode = false;

            document.addEventListener('click', function(e) {
                var action = e.target.closest('[data-action]');
                if (!action) return;
                var act = action.getAttribute('data-action');

                if (act === 'toggle-photo-select') {
                    selectMode = !selectMode;
                    var cbs = document.querySelectorAll('.photo-select-checkbox');
                    var bar = document.getElementById('photo-bulk-bar');
                    var toggle = document.getElementById('photo-select-toggle');
                    cbs.forEach(function(cb) { cb.classList.toggle('hidden', !selectMode); });
                    if (bar) bar.classList.toggle('hidden', !selectMode);
                    if (toggle) {
                        toggle.textContent = selectMode ? 'Cancel' : 'Select';
                        toggle.classList.toggle('bg-indigo-600', selectMode);
                        toggle.classList.toggle('text-white', selectMode);
                        toggle.classList.toggle('border-indigo-600', selectMode);
                    }
                    if (!selectMode) {
                        cbs.forEach(function(cb) { var inp = cb.querySelector('input'); if (inp) inp.checked = false; });
                        updateSelectCount();
                    }
                }
                else if (act === 'photo-select-check') {
                    updateSelectCount();
                }
                else if (act === 'photo-select-all') {
                    document.querySelectorAll('.photo-select-checkbox input').forEach(function(cb) { cb.checked = true; });
                    updateSelectCount();
                }
                else if (act === 'photo-select-clear') {
                    document.querySelectorAll('.photo-select-checkbox input').forEach(function(cb) { cb.checked = false; });
                    updateSelectCount();
                }
                else if (act === 'photo-bulk-move') {
                    var collSel = document.getElementById('bulk-move-collection');
                    var srcSel = document.getElementById('bulk-move-source');
                    var urlInp = document.getElementById('bulk-source-url');
                    var collection = collSel ? collSel.value : '';
                    var source = srcSel ? srcSel.value : '';
                    var sourceUrl = urlInp ? urlInp.value : '';
                    if (!collection && !source && !sourceUrl) { alert('Please set at least one field.'); return; }
                    var ids = [];
                    document.querySelectorAll('.photo-select-checkbox input:checked').forEach(function(cb) { ids.push(cb.value); });
                    if (ids.length === 0) { alert('No photos selected.'); return; }
                    htmx.ajax('POST', '/api/photos/bulk-update-source', {
                        values: { photo_ids: JSON.stringify(ids), collection: collection, source: source, source_url: sourceUrl },
                        target: '#toast-container',
                        swap: 'beforeend'
                    });
                }
            });

            // Also handle change events for checkboxes
            document.addEventListener('change', function(e) {
                if (e.target.closest('[data-action="photo-select-check"]')) {
                    updateSelectCount();
                }
            });

            function updateSelectCount() {
                var count = document.querySelectorAll('.photo-select-checkbox input:checked').length;
                var el = document.getElementById('photo-select-count');
                if (el) el.textContent = count + ' selected';
            }
        })();
    """)

    return Div(
        section_header("Photos", subtitle),
        filter_bar,
        collection_cards,
        grid if photo_cards else Div(
            "No photos found." + (" Clear filter to see all." if (filter_source or filter_collection) else ""),
            cls="text-center py-12 text-slate-400"
        ),
        bulk_action_bar,
        select_script,
        cls="space-y-6"
    )


def get_next_focus_card(exclude_id: str = None, triage_filter: str = ""):
    """
    Get the next identity card for focus mode review.

    Returns an expanded identity card + Up Next carousel for the top priority items,
    or an empty state if no items remain.

    Args:
        exclude_id: Identity ID to exclude (just-actioned item)
        triage_filter: Active triage filter to preserve through navigation

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

    # Apply triage filter if set (must match render_to_review_section logic)
    if triage_filter in ("ready", "rediscovered", "unmatched"):
        to_review = [i for i in to_review if _triage_category(i) == triage_filter]

    # Sort by actionability priority (matches render_to_review_section's _focus_sort_key)
    ids_with_proposals = _get_identities_with_proposals()

    def _focus_sort_key(x):
        iid = x.get("identity_id", "")
        has_proposal = iid in ids_with_proposals
        best = _get_best_proposal_for_identity(iid) if has_proposal else None
        has_promotion = x.get("promoted_from") is not None
        promotion_reason = x.get("promotion_reason", "")

        if has_promotion and promotion_reason == "confirmed_match":
            tier = 0
        elif has_proposal and best and best.get("confidence") == "VERY HIGH":
            tier = 1
        elif has_promotion:
            tier = 2
        elif has_proposal and best and best.get("confidence") == "HIGH":
            tier = 3
        elif has_proposal:
            tier = 4
        else:
            tier = 5

        # Quality tiebreaker — clear faces first within same tier
        quality = _identity_quality_score(x)

        return (
            tier,
            best["distance"] if best else 999,
            -quality,
            -len(x.get("anchor_ids", []) + x.get("candidate_ids", [])),
        )

    high_confidence = sorted(to_review, key=_focus_sort_key)[:10]

    if high_confidence:
        user_is_admin = True  # get_next_focus_card is only called from admin action routes
        # Build Up Next carousel
        up_next = None
        if len(high_confidence) > 1:
            up_next = Div(
                H3("Up Next", cls="text-sm font-medium text-slate-400 mb-3"),
                Div(
                    *[identity_card_mini(i, crop_files, clickable=True, triage_filter=triage_filter) for i in high_confidence[1:6]],
                    Div(
                        f"+{len(high_confidence) - 6} more",
                        cls="w-24 flex-shrink-0 flex items-center justify-center bg-slate-700 rounded-lg text-sm text-slate-400 aspect-square"
                    ) if len(high_confidence) > 6 else None,
                    cls="flex gap-3 overflow-x-auto pb-2"
                ),
                cls="mt-6"
            )

        # Show promotion banner above the expanded card if applicable
        banner = _promotion_banner(high_confidence[0])
        return Div(
            banner,
            identity_card_expanded(high_confidence[0], crop_files, is_admin=user_is_admin, triage_filter=triage_filter),
            up_next,
            id="focus-container"
        )
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
            id="focus-container"
        )


def upload_area(existing_sources: list[str] = None, existing_collections: list[str] = None) -> Div:
    """
    Drag-and-drop file upload area with separate collection, source, and source URL fields.
    UX Intent: Easy bulk ingestion into inbox with provenance tracking.

    Args:
        existing_sources: List of existing source labels for autocomplete
        existing_collections: List of existing collection labels for autocomplete
    """
    if existing_sources is None:
        existing_sources = []
    if existing_collections is None:
        existing_collections = []

    return Div(
        # Metadata fields — optional, can be filled before or after upload
        Div(
            P("Categorize your photos (optional — you can do this later)",
              cls="text-sm text-slate-400 mb-3"),
            # Collection field
            Div(
                Label("Collection", cls="block text-xs font-medium text-slate-400 mb-1"),
                Input(
                    type="text",
                    name="collection",
                    id="upload-collection",
                    placeholder="e.g., Immigration Records, Wedding Photos",
                    list="collection-suggestions",
                    cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg "
                        "text-white placeholder-slate-400 text-sm focus:ring-2 focus:ring-indigo-500 "
                        "focus:border-transparent"
                ),
                Datalist(
                    *[Option(value=c) for c in existing_collections],
                    id="collection-suggestions"
                ) if existing_collections else None,
                P("How you want to organize these in the archive",
                  cls="text-xs text-slate-500 mt-0.5"),
                cls="mb-3"
            ),
            # Source field
            Div(
                Label("Source", cls="block text-xs font-medium text-slate-400 mb-1"),
                Input(
                    type="text",
                    name="source",
                    id="upload-source",
                    placeholder="e.g., Newspapers.com, Betty's Album, Rhodes Facebook Group",
                    list="source-suggestions",
                    cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg "
                        "text-white placeholder-slate-400 text-sm focus:ring-2 focus:ring-indigo-500 "
                        "focus:border-transparent"
                ),
                Datalist(
                    *[Option(value=s) for s in existing_sources],
                    id="source-suggestions"
                ) if existing_sources else None,
                P("Where did these photos come from?",
                  cls="text-xs text-slate-500 mt-0.5"),
                cls="mb-3"
            ),
            # Source URL field
            Div(
                Label("Source URL", cls="block text-xs font-medium text-slate-400 mb-1"),
                Input(
                    type="url",
                    name="source_url",
                    id="upload-source-url",
                    placeholder="https://...",
                    cls="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg "
                        "text-white placeholder-slate-400 text-sm focus:ring-2 focus:ring-indigo-500 "
                        "focus:border-transparent"
                ),
                P("Link to the original (for citation)",
                  cls="text-xs text-slate-500 mt-0.5"),
                cls="mb-3"
            ),
            cls="mb-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700"
        ),
        # File upload area
        Form(
            Div(
                Span("\u2191", cls="text-4xl text-slate-500"),
                P("Drop photos here or click to upload", cls="text-slate-300 mt-2 font-medium"),
                P("Multiple files allowed \u2022 JPG, PNG, or ZIP", cls="text-xs text-slate-500 mt-1"),
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
                hx_include="#upload-source,#upload-collection,#upload-source-url",
            ),
            cls="relative",
            enctype="multipart/form-data",
        ),
        Div(id="upload-status", cls="mt-2"),
        cls="border-2 border-dashed border-slate-600 rounded-lg p-4 hover:border-slate-500 hover:bg-slate-800/50 transition-colors mb-4",
    )


def inbox_badge(count: int) -> A:
    """
    New Matches badge showing count of items awaiting review.
    """
    if count == 0:
        return A(
            Span("\U0001F4E5", cls="mr-2"),
            "New Matches",
            Span("(0)", cls="text-slate-500 ml-1"),
            href="#inbox-lane",
            cls="text-slate-400 hover:text-slate-300 text-sm"
        )
    return A(
        Span("\U0001F4E5", cls="mr-2"),
        "New Matches",
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
            cls="px-3 py-1.5 text-sm font-bold bg-emerald-600 text-white rounded hover:bg-emerald-700 transition-colors min-h-[44px]",
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
            cls="px-3 py-1.5 text-sm font-bold bg-amber-500 text-white rounded hover:bg-amber-600 transition-colors min-h-[44px]",
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
            cls="px-3 py-1.5 text-sm font-bold border-2 border-red-500 text-red-500 rounded hover:bg-red-500/20 transition-colors min-h-[44px]",
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
            cls="px-3 py-1.5 text-sm font-bold border border-slate-500 text-slate-400 rounded hover:bg-slate-700 transition-colors min-h-[44px]",
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


# Share icon SVG (three connected dots) — used everywhere for consistency
_SHARE_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'


def share_button(photo_id: str, style: str = "icon", label: str = "Share"):
    """
    Reusable share button that copies the public photo URL.
    Uses data-action="share-photo" for global event delegation.

    style: "icon" (compact icon-only), "button" (icon + text), "link" (text link style)
    """
    url = f"/photo/{photo_id}"
    if style == "button":
        return Button(
            NotStr(f'<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'),
            label,
            cls="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center",
            type="button",
            data_action="share-photo",
            data_share_url=url,
        )
    elif style == "link":
        return Button(
            NotStr(_SHARE_ICON_SVG),
            f" {label}",
            cls="text-xs text-indigo-400 hover:text-indigo-300 underline inline-flex items-center gap-1",
            type="button",
            data_action="share-photo",
            data_share_url=url,
        )
    else:  # "icon" — compact, for grid overlays and card corners
        return Button(
            NotStr(_SHARE_ICON_SVG),
            cls="p-1.5 bg-black/60 hover:bg-indigo-600 text-white rounded transition-colors",
            type="button",
            data_action="share-photo",
            data_share_url=url,
            title="Share this photo",
        )


def parse_transform_to_css(transform_str: str) -> str:
    """Convert a transform string like 'rotate:90,flipH' to CSS transform value.

    Supported transforms:
    - rotate:90, rotate:180, rotate:270 — clockwise rotation
    - flipH — horizontal mirror (scaleX(-1))
    - flipV — vertical mirror (scaleY(-1))
    - invert — handled separately via CSS filter, not transform

    Returns CSS transform property value (e.g., 'rotate(90deg) scaleX(-1)').
    """
    if not transform_str or not transform_str.strip():
        return ""

    parts = [p.strip() for p in transform_str.split(",") if p.strip()]
    css_parts = []
    for part in parts:
        if part.startswith("rotate:"):
            degrees = part.split(":")[1]
            css_parts.append(f"rotate({degrees}deg)")
        elif part == "flipH":
            css_parts.append("scaleX(-1)")
        elif part == "flipV":
            css_parts.append("scaleY(-1)")
        # 'invert' is handled via CSS filter, not transform
    return " ".join(css_parts)


def parse_transform_to_filter(transform_str: str) -> str:
    """Extract CSS filter from transform string (for 'invert')."""
    if not transform_str or "invert" not in transform_str:
        return ""
    return "invert(1)"


def image_transform_toolbar(photo_id: str, target: str = "front") -> Div:
    """Admin toolbar for non-destructive image orientation.

    target: 'front' or 'back' — which image side to transform.
    """
    field_name = "transform" if target == "front" else "back_transform"
    label = "Front orientation" if target == "front" else "Back orientation"

    def _btn(icon_label, transform_val, danger=False):
        cls_base = "px-2 py-1 text-xs rounded transition-colors"
        cls_color = "bg-red-900/50 hover:bg-red-800/50 text-red-300" if danger else "bg-slate-700 hover:bg-slate-600 text-slate-300"
        return Button(
            icon_label,
            cls=f"{cls_base} {cls_color}",
            type="button",
            hx_post=f"/api/photo/{photo_id}/transform?transform={transform_val}&field={field_name}",
            hx_target="#transform-result",
            hx_swap="innerHTML",
        )

    return Div(
        P(label, cls="text-xs text-slate-400 font-medium mb-1"),
        Div(
            _btn("\u21bb 90\u00b0", "rotate:90"),
            _btn("\u21ba -90\u00b0", "rotate:270"),
            _btn("\u2194 Flip H", "flipH"),
            _btn("\u2195 Flip V", "flipV"),
            _btn("\u25d0 Invert", "invert"),
            _btn("\u21a9 Reset", "reset", danger=True),
            cls="flex flex-wrap gap-1",
        ),
        cls="mt-2",
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
    is_admin: bool = True,
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
        is_admin: Whether to show admin-only info (quality score)
    """
    if quality is None:
        # Extract quality from URL: /crops/{name}_{quality}_{idx}.jpg
        quality = parse_quality_from_filename(crop_url)
    if quality == 0.0:
        # Inbox crops don't encode quality in filename — look up from embeddings
        emb_quality = get_face_quality(face_id)
        if emb_quality is not None:
            quality = emb_quality

    # View Photo button (only if photo_id is available)
    # Pass identity_id for navigation context between identity's photos
    view_photo_btn = None
    if photo_id:
        _vp_url = f"/photo/{photo_id}/partial?face={face_id}"
        if identity_id:
            _vp_url += f"&identity_id={identity_id}"
        view_photo_btn = Button(
            "View Photo",
            cls="text-xs text-slate-400 hover:text-slate-300 underline mt-1",
            hx_get=_vp_url,
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            # Show the modal when clicked
            **{"_": "on click remove .hidden from #photo-modal"},
            type="button",
        )

    # Share button for public photo viewer
    full_page_link = None
    if photo_id:
        full_page_link = Span(
            share_button(photo_id, style="link", label="Share"),
            cls="mt-1 ml-2",
        )

    # Detach button (only if show_detach is True)
    detach_btn = None
    if show_detach:
        # Generate safe DOM ID for targeting
        safe_dom_id = make_css_id(face_id)

        detach_btn = Button(
            "Detach",
            cls="text-xs text-slate-400 hover:text-slate-300 underline mt-1 ml-2",
            hx_post=f"/api/face/{quote(face_id)}/detach",
            hx_target=f"#{safe_dom_id}",
            hx_swap="outerHTML",
            hx_confirm="Move this face to its own identity? (You can merge it back later.)",
            type="button",
        )

    return Div(
        # Image container with era badge
        Div(
            Img(
                src=crop_url,
                alt=face_id,
                cls="w-full aspect-square object-cover sepia-[.3] hover:sepia-0 transition-all duration-300"
            ),
            era_badge(era) if era else None,
            cls="relative border border-slate-600 bg-slate-700"
        ),
        # Metadata and actions
        Div(
            P(
                f"Quality: {quality:.2f}",
                cls="text-xs font-data text-slate-500"
            ) if is_admin and quality > 0 else None,
            Div(
                view_photo_btn,
                full_page_link,
                detach_btn,
                cls="flex items-center"
            ) if view_photo_btn or detach_btn or full_page_link else None,
            cls="mt-2"
        ),
        cls="bg-slate-700 border border-slate-600 p-2 rounded shadow-md hover:shadow-lg transition-shadow",
        # Fix: Apply the safe ID to the container
        id=make_css_id(face_id)
    )


def neighbor_card(neighbor: dict, target_identity_id: str, crop_files: set, show_checkbox: bool = True, user_role: str = "admin", from_focus: bool = False, triage_filter: str = "", focus_section: str = "") -> Div:
    neighbor_id = neighbor["identity_id"]
    # UI BOUNDARY: sanitize name for safe rendering
    name = ensure_utf8_display(neighbor["name"])
    # Get values directly (no more negative scaling)
    distance = neighbor["distance"]
    percentile = neighbor.get("percentile", 1.0)
    confidence_gap = neighbor.get("confidence_gap", 0.0)

    can_merge = neighbor["can_merge"]
    face_count = neighbor.get("face_count", 0)
    co_occurrence = neighbor.get("co_occurrence", 0)

    # --- CALIBRATION: AD-013 Evidence-Based Thresholds (2026-02-09) ---
    if distance < MATCH_THRESHOLD_VERY_HIGH:
        similarity_class = "bg-emerald-500/30 text-emerald-300"
        similarity_label = "Very High"
    elif distance < MATCH_THRESHOLD_HIGH:
        similarity_class = "bg-emerald-500/20 text-emerald-400"
        similarity_label = "High"
    elif distance < MATCH_THRESHOLD_MODERATE:
        similarity_class = "bg-amber-500/20 text-amber-400"
        similarity_label = "Moderate"
    elif distance < MATCH_THRESHOLD_MEDIUM:
        similarity_class = "bg-amber-500/15 text-amber-500"
        similarity_label = "Medium"
    else:
        similarity_class = "bg-slate-600 text-slate-400"
        similarity_label = "Low"
    # -----------------------------------------------

    # Merge button -- role-aware: admin merges directly, contributor suggests
    # In focus mode, target #focus-container and append from_focus=true so the merge
    # endpoint advances to the next identity instead of returning a browse-mode card.
    _focus_filter = f"&filter={triage_filter}" if triage_filter else ""
    _focus_section = f"&focus_section={focus_section}" if focus_section else ""
    focus_suffix = f"&from_focus=true{_focus_filter}{_focus_section}" if from_focus else ""
    if from_focus and focus_section == "skipped":
        merge_target = "#skipped-focus-container"
    elif from_focus:
        merge_target = "#focus-container"
    else:
        merge_target = f"#identity-{target_identity_id}"
    merge_swap = "outerHTML"
    if not can_merge:
        merge_btn = Button("Blocked", cls="px-3 py-1 text-sm font-bold bg-slate-600 text-slate-400 rounded cursor-not-allowed", disabled=True, title=neighbor.get("merge_blocked_reason_display"))
    elif user_role == "contributor":
        merge_btn = Button("Suggest Merge", cls="px-3 py-1 text-sm font-bold bg-purple-600 text-white rounded hover:bg-purple-500",
                           hx_post=f"/api/identity/{target_identity_id}/suggest-merge/{neighbor_id}", hx_target=f"#neighbor-{neighbor_id}",
                           hx_swap="outerHTML", data_auth_action="suggest a merge")
    else:
        merge_btn = Button("Merge", cls="px-3 py-1 text-sm font-bold bg-blue-600 text-white rounded hover:bg-blue-500",
                           hx_post=f"/api/identity/{target_identity_id}/merge/{neighbor_id}{focus_suffix}", hx_target=merge_target,
                           hx_swap=merge_swap, data_auth_action="merge these identities")

    # Compare button -- opens side-by-side comparison modal
    _compare_filter = f"?filter={triage_filter}" if triage_filter else ""
    compare_btn = Button(
        "Compare",
        cls="px-2 py-1 text-xs font-bold border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20",
        hx_get=f"/api/identity/{target_identity_id}/compare/{neighbor_id}{_compare_filter}",
        hx_target="#compare-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #compare-modal"},
        type="button",
    )

    # Thumbnail logic — prefer best quality, fall back to any available crop
    thumbnail_img = Div(cls="w-16 h-16 bg-slate-600 rounded")
    anchor_face_ids = neighbor.get("anchor_face_ids", []) + neighbor.get("candidate_face_ids", [])
    crop_url = None
    best_fid = get_best_face_id(anchor_face_ids) if anchor_face_ids else None
    if best_fid:
        crop_url = resolve_face_image_url(best_fid, crop_files)
    if not crop_url:
        for fid in anchor_face_ids:
            crop_url = resolve_face_image_url(fid, crop_files)
            if crop_url:
                break
    if crop_url:
        thumbnail_img = Img(src=crop_url, alt=name, cls="w-16 h-16 object-cover rounded border border-slate-600 hover:scale-105 transition-transform")

    # Checkbox for bulk selection (linked to bulk form via hyperscript)
    # Uses property assignment (not attribute toggle) so FormData picks it up
    checkbox = Input(
        type="checkbox",
        cls="w-4 h-4 rounded border-slate-500 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer flex-shrink-0",
        **{"_": f"on change set #bulk-{neighbor_id}.checked to my.checked"},
    ) if (show_checkbox and can_merge) else None

    # Determine the correct section for this neighbor based on its state
    neighbor_section = _section_for_state(neighbor.get("state", "INBOX"))

    # Navigation script: try to scroll if element exists, otherwise navigate to browse mode
    nav_script = f"on click set target to #identity-{neighbor_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-blue-400 to target then wait 1.5s then remove .ring-2 .ring-blue-400 from target else go to url '/?section={neighbor_section}&view=browse#identity-{neighbor_id}'"

    return Div(
        Div(checkbox,
            A(thumbnail_img, href=f"/?section={neighbor_section}&view=browse#identity-{neighbor_id}", cls="flex-shrink-0 cursor-pointer hover:opacity-80", **{"_": nav_script}),
            Div(Div(A(name, href=f"/?section={neighbor_section}&view=browse#identity-{neighbor_id}", cls="font-medium text-slate-200 truncate hover:text-blue-400 hover:underline cursor-pointer", **{"_": nav_script}),
                    Span(similarity_label, cls=f"text-xs px-2 py-0.5 rounded ml-2 {similarity_class}"), cls="flex items-center"),
                # EXPLAINABILITY: Distance + confidence gap (how much closer than next-best)
                Div(Span(f"Dist: {distance:.2f}", cls="text-xs font-data text-slate-400 ml-2 bg-slate-700 px-1 rounded"),
                    Span(f"+{confidence_gap}% gap", cls="text-xs font-data text-emerald-400/70 ml-1 bg-emerald-900/30 px-1 rounded") if confidence_gap > 0 else None,
                    Span(f"Seen together in {co_occurrence} photo{'s' if co_occurrence != 1 else ''}", cls="text-[10px] text-amber-400 italic ml-1") if co_occurrence > 0 else None,
                    cls="flex items-center flex-wrap"),
                cls="flex-1 min-w-0 ml-3"),
            Div(compare_btn, merge_btn, Button("Not Same", cls="px-2 py-1 text-xs font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20",
                                  hx_post=f"/api/identity/{target_identity_id}/reject/{neighbor_id}", hx_target=f"#neighbor-{neighbor_id}", hx_swap="outerHTML"),
                cls="flex items-center gap-1 sm:gap-2 flex-shrink-0 sm:ml-2 mt-2 sm:mt-0"),
            cls="flex flex-wrap sm:flex-nowrap items-center gap-2"),
        id=f"neighbor-{neighbor_id}", cls="p-3 bg-slate-700 border border-slate-600 rounded shadow-md mb-2 hover:shadow-lg overflow-hidden"
    )

def search_result_card(result: dict, target_identity_id: str, crop_files: set, user_role: str = "admin") -> Div:
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
                cls="w-12 h-12 object-cover rounded border border-slate-600"
            )

    # Compare button -- opens side-by-side comparison modal (same pattern as neighbor_card)
    compare_btn = Button(
        "Compare",
        cls="px-2 py-1 text-xs font-bold border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20",
        hx_get=f"/api/identity/{target_identity_id}/compare/{result_id}",
        hx_target="#compare-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #compare-modal"},
        type="button",
    )

    # Merge button -- role-aware: admin merges directly, contributor suggests
    if user_role == "contributor":
        merge_btn = Button(
            "Suggest Merge",
            cls="px-2 py-1 text-xs font-bold bg-purple-600 text-white rounded hover:bg-purple-500",
            hx_post=f"/api/identity/{target_identity_id}/suggest-merge/{result_id}",
            hx_target=f"#search-result-{result_id}",
            hx_swap="outerHTML",
            data_auth_action="suggest a merge",
        )
    else:
        merge_btn = Button(
            "Merge",
            cls="px-2 py-1 text-xs font-bold border border-blue-500/50 text-blue-400 rounded hover:bg-blue-500/20",
            hx_post=f"/api/identity/{target_identity_id}/merge/{result_id}?source=manual_search",
            hx_target=f"#identity-{target_identity_id}",
            hx_swap="outerHTML",
            data_auth_action="merge these identities",
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
            Div(compare_btn, merge_btn, cls="flex items-center gap-1 flex-shrink-0 ml-2"),
            cls="flex items-center"
        ),
        id=f"search-result-{result_id}",
        cls="p-2 bg-slate-700 border border-slate-600 rounded shadow-md mb-2 hover:shadow-lg"
    )


def search_results_panel(results: list, target_identity_id: str, crop_files: set, user_role: str = "admin") -> Div:
    """Panel showing manual search results."""
    if not results:
        return Div(
            P("No matching identities found.", cls="text-slate-400 italic text-sm"),
            id=f"search-results-{target_identity_id}"
        )

    cards = [search_result_card(r, target_identity_id, crop_files, user_role=user_role) for r in results]
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


def neighbors_sidebar(identity_id: str, neighbors: list, crop_files: set, offset: int = 0, has_more: bool = False, rejected_count: int = 0, user_role: str = "admin", from_focus: bool = False, focus_section: str = "") -> Div:
    toggle_btn = Button(
        "▾ Collapse",
        cls="text-sm text-slate-400 hover:text-slate-300",
        id=f"neighbors-toggle-{identity_id}",
        type="button",
        **{"_": f"on click toggle .hidden on #neighbors-body-{identity_id} then if my.textContent == '▸ Expand' set my.textContent to '▾ Collapse' else set my.textContent to '▸ Expand'"},
    )
    if not neighbors: return Div(Div(P("No similar identities.", cls="text-slate-400 italic"), toggle_btn, cls="flex items-center justify-between"), manual_search_section(identity_id), cls="neighbors-sidebar p-4 bg-slate-700 rounded border border-slate-600 overflow-hidden")

    # Mergeable neighbors get checkboxes for bulk operations
    mergeable = [n for n in neighbors if n.get("can_merge")]
    cards = [neighbor_card(n, identity_id, crop_files, user_role=user_role, from_focus=from_focus, focus_section=focus_section) for n in neighbors]
    _focus_section_param = f"&focus_section={focus_section}" if focus_section else ""
    focus_param = f"&from_focus=true{_focus_section_param}" if from_focus else ""
    load_more = Button("Load More", cls="w-full text-sm text-indigo-400 hover:text-indigo-300 py-2 border border-indigo-500/50 rounded hover:bg-indigo-500/20",
                       hx_get=f"/api/identity/{identity_id}/neighbors?offset={offset+len(neighbors)}{focus_param}", hx_target=f"#neighbors-{identity_id}", hx_swap="innerHTML") if has_more else None

    # Bulk actions (only if there are mergeable neighbors)
    bulk_actions = None
    if len(mergeable) > 1:
        select_all_script = (
            "on click "
            "set cbs to <input[name='bulk_ids']/> in closest <form/> "
            "repeat for cb in cbs set cb.checked to my.checked end"
        )
        bulk_actions = Form(
            # Hidden inputs for each mergeable neighbor (checkboxes)
            Div(
                Label(
                    Input(type="checkbox", cls="mr-2 accent-blue-500",
                          **{"_": select_all_script}),
                    Span("Select All", cls="text-xs text-slate-400"),
                    cls="flex items-center cursor-pointer mb-2",
                ),
                *[Div(
                    Input(type="checkbox", name="bulk_ids", value=n["identity_id"],
                          cls="hidden bulk-checkbox",
                          id=f"bulk-{n['identity_id']}"),
                    cls="hidden",
                ) for n in mergeable],
                cls="",
            ),
            Div(
                Button("Merge Selected", type="button",
                       hx_post=f"/api/identity/{identity_id}/bulk-merge",
                       hx_include="closest form",
                       hx_target=f"#neighbors-{identity_id}",
                       hx_swap="innerHTML",
                       cls="px-3 py-1.5 text-xs font-bold bg-blue-600 text-white rounded hover:bg-blue-500"),
                Button("Not Same Selected", type="button",
                       hx_post=f"/api/identity/{identity_id}/bulk-reject",
                       hx_include="closest form",
                       hx_target=f"#neighbors-{identity_id}",
                       hx_swap="innerHTML",
                       cls="px-3 py-1.5 text-xs font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20"),
                cls="flex gap-2",
            ),
            cls="mb-3 p-2 bg-slate-600/50 rounded border border-slate-600",
        )

    # Manual search section - between Load More and Rejected
    manual_search = manual_search_section(identity_id)

    rejected = Div(Div(Span(f"{rejected_count} hidden matches", cls="text-xs text-slate-400 italic"),
                       Button("Review", cls="text-xs text-indigo-400 hover:text-indigo-300 ml-2", hx_get=f"/api/identity/{identity_id}/rejected", hx_target=f"#rejected-list-{identity_id}", hx_swap="innerHTML"),
                       cls="flex items-center justify-between"), Div(id=f"rejected-list-{identity_id}"), cls="mt-4 pt-3 border-t border-slate-600") if rejected_count > 0 else None

    return Div(
        Div(H4("Similar Identities", cls="text-lg font-serif font-bold text-white"), toggle_btn, cls="flex items-center justify-between mb-3"),
        Div(
            bulk_actions,
            Div(*cards), Div(load_more, cls="mt-3") if load_more else None, manual_search, rejected,
            id=f"neighbors-body-{identity_id}",
        ),
        cls="neighbors-sidebar p-4 bg-slate-700 rounded border border-slate-600 overflow-hidden",
    )


def name_display(identity_id: str, name: str, is_admin: bool = True,
                  generation_qualifier: str = "") -> Div:
    """
    Identity name display with edit button (admin only).
    Returns the name header component that can be swapped for inline editing.
    """
    # UI BOUNDARY: sanitize name for safe rendering
    safe_name = ensure_utf8_display(name)
    display_name = safe_name or f"Identity {identity_id[:8]}..."
    if generation_qualifier:
        display_name = f"{display_name} {generation_qualifier}"
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


FACES_PER_PAGE = 8


def _build_face_cards_for_entries(face_entries, crop_files, identity_id, can_detach, is_admin=True):
    """Build face card elements from a list of face entries."""
    cards = []
    for face_entry in face_entries:
        if isinstance(face_entry, str):
            face_id = face_entry
            era = None
        else:
            face_id = face_entry.get("face_id", "")
            era = face_entry.get("era_bin")

        crop_url = resolve_face_image_url(face_id, crop_files)
        if crop_url:
            photo_id = get_photo_id_for_face(face_id)
            cards.append(face_card(
                face_id=face_id,
                crop_url=crop_url,
                era=era,
                identity_id=identity_id,
                photo_id=photo_id,
                show_detach=can_detach,
                is_admin=is_admin,
            ))
        else:
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
    return cards


def _face_pagination_controls(identity_id: str, page: int, total_faces: int, sort: str = "date"):
    """Build pagination controls for face grid carousel."""
    total_pages = (total_faces + FACES_PER_PAGE - 1) // FACES_PER_PAGE
    if total_pages <= 1:
        return None

    start = page * FACES_PER_PAGE + 1
    end = min((page + 1) * FACES_PER_PAGE, total_faces)

    prev_btn = Button(
        Span("<", cls="text-lg"),
        cls="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded transition-colors",
        hx_get=f"/api/identity/{identity_id}/faces?page={page - 1}&sort={sort}",
        hx_target=f"#faces-{identity_id}",
        hx_swap="outerHTML",
        type="button",
    ) if page > 0 else Button(
        Span("<", cls="text-lg"),
        cls="px-2 py-1 text-slate-400 opacity-30 cursor-not-allowed rounded",
        type="button",
        disabled=True,
    )

    next_btn = Button(
        Span(">", cls="text-lg"),
        cls="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded transition-colors",
        hx_get=f"/api/identity/{identity_id}/faces?page={page + 1}&sort={sort}",
        hx_target=f"#faces-{identity_id}",
        hx_swap="outerHTML",
        type="button",
    ) if page < total_pages - 1 else Button(
        Span(">", cls="text-lg"),
        cls="px-2 py-1 text-slate-400 opacity-30 cursor-not-allowed rounded",
        type="button",
        disabled=True,
    )

    return Div(
        prev_btn,
        Span(f"{start}-{end} of {total_faces}", cls="text-xs text-slate-400 mx-2"),
        next_btn,
        cls="flex items-center justify-center gap-1 mt-3"
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
    Shows first page of faces (max FACES_PER_PAGE) with pagination if more exist.
    """
    identity_id = identity["identity_id"]
    # UI BOUNDARY: sanitize name for safe rendering
    raw_name = ensure_utf8_display(identity.get("name"))
    name = raw_name or f"Identity {identity_id[:8]}..."
    state = identity["state"]

    # Combine anchors (confirmed) and candidates (proposed) for display
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    total_faces = len(all_face_ids)

    # Show detach button only if identity has more than one face AND user is admin
    can_detach = total_faces > 1 and is_admin

    # Show only first page of faces
    page_entries = all_face_ids[:FACES_PER_PAGE]
    face_cards = _build_face_cards_for_entries(page_entries, crop_files, identity_id, can_detach, is_admin=is_admin)

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
        hx_swap="outerHTML",
        name="sort",
        hx_trigger="change",
    )

    # View All Photos button (opens photo modal)
    view_all_photos_btn = Button(
        "\U0001f4f7 View All Photos",
        cls="px-3 py-1.5 text-sm font-medium bg-amber-600/20 text-amber-300 border border-amber-500/30 rounded-lg hover:bg-amber-600/30 hover:border-amber-400/50 transition-colors",
        hx_get=f"/api/identity/{identity_id}/photos?index=0",
        hx_target="#photo-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #photo-modal"},
        type="button",
    ) if total_faces > 0 else None

    # View Public Page link (for confirmed identities with real names)
    view_public_link = None
    if state == "CONFIRMED" and not name.startswith("Unidentified") and not name.startswith("Identity "):
        view_public_link = A(
            "\U0001f517 Public Page",
            href=f"/person/{identity_id}",
            cls="px-3 py-1.5 text-sm font-medium text-slate-400 border border-slate-600 rounded-lg hover:text-indigo-300 hover:border-indigo-500/30 transition-colors",
            target="_blank",
        )

    # Find Similar button (loads neighbors via HTMX) -- scrolls into view after swap
    find_similar_btn = Button(
        "\U0001f50d Find Similar",
        cls="px-3 py-1.5 text-sm font-medium bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 rounded-lg hover:bg-indigo-600/30 hover:border-indigo-400/50 transition-colors",
        hx_get=f"/api/identity/{identity_id}/neighbors",
        hx_target=f"#neighbors-{identity_id}",
        hx_swap="innerHTML",
        hx_indicator=f"#neighbors-loading-{identity_id}",
        type="button",
        **{"hx-on::after-swap": f"document.getElementById('neighbors-{identity_id}').scrollIntoView({{behavior: 'smooth', block: 'start'}})"},
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

    # Pagination controls
    pagination = _face_pagination_controls(identity_id, 0, total_faces, "date")

    # Badge for merged-unnamed identities (multiple faces but no human name)
    grouped_badge = None
    if total_faces > 1 and (name.startswith("Unidentified") or name.startswith("Identity ")):
        grouped_badge = Span(
            f"Grouped ({total_faces} faces)",
            cls="text-xs px-2 py-0.5 rounded bg-purple-600/20 text-purple-300 border border-purple-500/30 ml-2",
        )

    return Div(
        # Header with name, state, and controls
        Div(
            Div(
                name_display(identity_id, identity.get("name"), is_admin=is_admin,
                             generation_qualifier=identity.get("generation_qualifier", "")),
                state_badge(state),
                _proposal_badge_inline(identity_id),
                _promotion_badge(identity),
                grouped_badge,
                Span(
                    f"{total_faces} face{'s' if total_faces != 1 else ''}",
                    cls="text-xs text-slate-400 ml-2"
                ),
                cls="flex items-center gap-3 flex-wrap"
            ),
            Div(
                sort_dropdown,
                view_all_photos_btn,
                find_similar_btn,
                view_public_link,
                cls="flex items-center gap-3"
            ),
            cls="identity-card-header flex items-center justify-between mb-3"
        ),
        # Face grid (paginated)
        Div(
            Div(
                *face_cards,
                cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3",
            ),
            pagination,
            id=f"faces-{identity_id}",
        ),
        # Identity metadata (AN-012)
        _identity_metadata_display(identity, is_admin=is_admin),
        # Action buttons based on state (admin only)
        review_action_buttons(identity_id, state, is_admin=is_admin),
        # Neighbors container (shown when "Find Similar" is clicked)
        neighbors_container,
        cls=f"identity-card bg-slate-800 border border-slate-700 border-l-4 {border_colors.get(lane_color, '')} p-4 rounded-r shadow-lg mb-4",
        id=f"identity-{identity_id}",
        data_name=(raw_name or "").lower()
    )


def photo_modal() -> Div:
    """
    Modal container for photo context viewer.
    Hidden by default, shown via HTMX when "View Photo" is clicked.

    Z-index hierarchy:
    - Toast container: z-[10001] (above all modals — always visible)
    - Modal container: z-[9999] (above page content)
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
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-full sm:max-w-5xl max-h-[90vh] overflow-auto p-3 sm:p-6 relative border border-slate-700"
        ),
        id="photo-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-2 sm:p-4 z-[9999]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
        tabindex="-1",
    )



def compare_modal() -> Div:
    """
    Side-by-side comparison modal for evaluating merge candidates.
    Shows the source identity's best face alongside the neighbor's best face.
    """
    return Div(
        # Backdrop
        Div(
            cls="absolute inset-0 bg-black/85",
            **{"_": "on click add .hidden to #compare-modal"},
        ),
        # Content
        Div(
            # Header
            Div(
                H2("Compare Faces", cls="text-xl font-serif font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click add .hidden to #compare-modal"},
                    type="button",
                    aria_label="Close comparison",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700"
            ),
            # Comparison content (populated by HTMX)
            Div(
                P("Loading...", cls="text-slate-400 text-center py-8"),
                id="compare-modal-content",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-full sm:max-w-[90vw] lg:max-w-7xl max-h-[90vh] overflow-auto p-3 sm:p-6 relative border border-slate-700"
        ),
        id="compare-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-2 sm:p-4 z-[10000]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
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
            P("Sign in to contribute to the archive.", id="login-modal-message", cls="text-slate-400 mb-6 text-sm"),
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
            Div(
                P(
                    A("Forgot password?", href="/forgot-password", cls="text-blue-400 hover:underline"),
                    cls="text-sm"
                ),
                P(
                    "No account? ",
                    A("Sign up with invite code", href="/signup", cls="text-blue-400 hover:underline"),
                    cls="text-sm text-slate-400"
                ),
                cls="mt-4 text-center space-y-1"
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-8 relative border border-slate-700"
        ),
        id="login-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[9998]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
    )


def _guest_or_login_modal(form_data: dict) -> Div:
    """Modal offering anonymous guest submission or sign-in to save.

    form_data: dict of original annotation form fields to preserve.
    Returns a modal Div that replaces #guest-or-login-modal.
    """
    # Build hidden inputs from original form data
    hidden_fields = []
    for key, val in form_data.items():
        if val is not None:
            hidden_fields.append(Input(type="hidden", name=key, value=str(val)))

    google_url = get_oauth_url("google")

    return Div(
        Div(cls="absolute inset-0 bg-black/80",
            **{"_": "on click remove #guest-or-login-modal's children"}),
        Div(
            Div(
                H2("Save your suggestion", cls="text-xl font-bold text-white"),
                Button("X", cls="text-slate-400 hover:text-white text-xl font-bold",
                       **{"_": "on click remove #guest-or-login-modal's children"},
                       type="button", aria_label="Close"),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700"
            ),
            P("Your suggestion will be reviewed by a family member.",
              cls="text-slate-400 mb-6 text-sm"),
            # Option 1: Continue as guest
            Form(
                *hidden_fields,
                Button("Continue as guest",
                       type="submit",
                       cls="w-full p-2 bg-emerald-600 hover:bg-emerald-700 rounded text-white font-medium"),
                P("Your suggestion will be saved anonymously.",
                  cls="text-xs text-slate-500 mt-1 text-center"),
                hx_post="/api/annotations/guest-submit",
                hx_target="#guest-or-login-modal",
                hx_swap="innerHTML",
            ),
            # Divider
            Div(
                Div(cls="flex-grow border-t border-slate-600"),
                Span("or", cls="px-4 text-slate-500 text-sm"),
                Div(cls="flex-grow border-t border-slate-600"),
                cls="flex items-center my-4"
            ),
            # Option 2: Sign in to save
            Form(
                *[Input(type="hidden", name=k, value=str(v))
                  for k, v in form_data.items() if v is not None],
                Button("Sign in to save",
                       type="submit",
                       cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"),
                P("Track your contributions with your account.",
                  cls="text-xs text-slate-500 mt-1 text-center"),
                hx_post="/api/annotations/stash-and-login",
                hx_target="#guest-or-login-modal",
                hx_swap="innerHTML",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-8 relative border border-slate-700"
        ),
        id="guest-or-login-modal",
        cls="fixed inset-0 flex items-center justify-center p-4 z-[10000]",
        **{"_": "on keydown[key=='Escape'] remove my children"},
    )


def _get_onboarding_surnames() -> list[str]:
    """Get canonical surname list from surname_variants.json for the onboarding grid."""
    variants_path = Path(__file__).resolve().parent.parent / "data" / "surname_variants.json"
    if not variants_path.exists():
        return []
    try:
        with open(variants_path) as f:
            data = json.load(f)
        return [g["canonical"] for g in data.get("variant_groups", []) if g.get("canonical")]
    except Exception:
        return []


def _welcome_banner() -> Div:
    """
    Dismissible welcome banner for first-time visitors (replaces modal wall).

    Shows a non-blocking top bar with context about the archive.
    Dismissed via X button; uses rhodesli_welcomed cookie (1 year).
    Content is immediately visible underneath — no overlay, no blocking.
    """
    return Div(
        Div(
            Div(
                Span("Welcome to Rhodesli", cls="font-semibold text-amber-100"),
                Span(" — ", cls="text-amber-300/60 hidden sm:inline"),
                Span("a heritage photo archive for the Jewish community of Rhodes. ",
                     cls="text-amber-200/80 hidden sm:inline"),
                Span("Know someone in these photos? Tap their face to help identify them.",
                     cls="text-amber-200/80 hidden sm:inline"),
                # Mobile: shorter copy
                Span(" — Tap a face to help identify someone.",
                     cls="text-amber-200/80 sm:hidden"),
                cls="flex-1 text-sm",
            ),
            Button(
                Svg(
                    Path(d="M6 18L18 6M6 6l12 12"),
                    cls="w-4 h-4", fill="none", stroke="currentColor", viewBox="0 0 24 24",
                    stroke_width="2", stroke_linecap="round", stroke_linejoin="round",
                ),
                type="button",
                cls="text-amber-300/60 hover:text-white ml-3 p-1 min-w-[28px] min-h-[28px] flex items-center justify-center",
                data_action="welcome-banner-dismiss",
                aria_label="Dismiss welcome banner",
            ),
            cls="max-w-6xl mx-auto px-4 sm:px-8 flex items-center",
        ),
        Script("""
            (function() {
                var welcomed = document.cookie.split(';').some(function(c) {
                    return c.trim().startsWith('rhodesli_welcomed=');
                });
                if (welcomed) {
                    var el = document.getElementById('welcome-banner');
                    if (el) el.remove();
                }
                document.addEventListener('click', function(e) {
                    var action = e.target.closest('[data-action="welcome-banner-dismiss"]');
                    if (action) {
                        document.cookie = 'rhodesli_welcomed=1; path=/; max-age=31536000; SameSite=Lax';
                        var banner = document.getElementById('welcome-banner');
                        if (banner) banner.remove();
                    }
                });
            })();
        """),
        id="welcome-banner",
        cls="bg-amber-900/40 border-b border-amber-700/30 py-2",
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
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-6 relative border border-slate-700"
        ),
        id="confirm-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[9997]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
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
# LANDING PAGE
# =============================================================================


def _compute_landing_stats() -> dict:
    """Compute live stats for the landing page from actual data."""
    registry = load_registry()
    photo_count = 0
    total_faces = 0
    photo_index_path = data_path / "photo_index.json"
    if photo_index_path.exists():
        with open(photo_index_path) as f:
            pi = json.load(f)
        photo_count = len(pi.get("photos", {}))
        for p in pi.get("photos", {}).values():
            total_faces += len(p.get("face_ids", []))
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    named_count = len([i for i in confirmed if not i.get("name", "").startswith("Unidentified")])
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    needs_help = len([i for i in (inbox + proposed) if not i.get("merged_into")])
    return {"photo_count": photo_count, "named_count": named_count,
            "needs_help": needs_help, "total_faces": total_faces}


LANDING_HERO_PHOTOS = [
    "Image 930_compress.jpg",
    "Image 931_compress.jpg",
    "Image 924_compress.jpg",
    "Image 964_compress.jpg",
    "Image 001_compress.jpg",
    "Image 013_compress.jpg",
    "Image 006_compress.jpg",
    "Image 046_compress.jpg",
]


def landing_page(user=None) -> tuple:
    """Welcoming landing page for the Rhodes-Capeluto family archive."""
    stats = _compute_landing_stats()
    hero_photos = []
    for i, filename in enumerate(LANDING_HERO_PHOTOS):
        size_cls = "col-span-2 row-span-2" if i in (0, 3, 5) else "col-span-1 row-span-1"
        hero_photos.append(Div(Img(src=photo_url(filename), alt="Rhodes-Capeluto family photo", cls="w-full h-full object-cover", loading="lazy"), cls=f"{size_cls} overflow-hidden rounded-lg"))
    if user:
        primary_cta = A("Continue Reviewing", href="/?section=to_review", cls="inline-block px-8 py-4 bg-indigo-600 text-white text-lg font-semibold rounded-xl hover:bg-indigo-500 transition-colors shadow-lg hover:shadow-xl")
        secondary_cta = A("Browse Photos", href="/?section=photos", cls="inline-block px-8 py-4 border-2 border-slate-500 text-slate-200 text-lg font-semibold rounded-xl hover:border-slate-300 hover:text-white transition-colors")
    else:
        primary_cta = A("Start Exploring", href="/?section=photos", cls="inline-block px-8 py-4 bg-indigo-600 text-white text-lg font-semibold rounded-xl hover:bg-indigo-500 transition-colors shadow-lg hover:shadow-xl")
        secondary_cta = A("Join the Project", href="/signup", cls="inline-block px-8 py-4 border-2 border-slate-500 text-slate-200 text-lg font-semibold rounded-xl hover:border-slate-300 hover:text-white transition-colors") if is_auth_enabled() else A("Browse People", href="/?section=confirmed", cls="inline-block px-8 py-4 border-2 border-slate-500 text-slate-200 text-lg font-semibold rounded-xl hover:border-slate-300 hover:text-white transition-colors")
    def step_card(icon_svg, title, description):
        return Div(Div(NotStr(icon_svg), cls="w-16 h-16 mx-auto mb-4 rounded-full bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400"), H3(title, cls="text-lg font-semibold text-white mb-2"), P(description, cls="text-slate-400 text-sm leading-relaxed"), cls="text-center px-4")
    browse_icon = '<svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"/></svg>'
    identify_icon = '<svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/></svg>'
    connect_icon = '<svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"/></svg>'
    arrow_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>'
    style = Style("html, body { height: 100%; margin: 0; } body { background-color: #0f172a; } .hero-grid { display: grid; grid-template-columns: repeat(4, 1fr); grid-auto-rows: 120px; gap: 0.5rem; } @media (min-width: 768px) { .hero-grid { grid-auto-rows: 140px; } } @media (min-width: 1024px) { .hero-grid { grid-auto-rows: 160px; } } .hero-overlay { background: linear-gradient(to bottom, rgba(15,23,42,0.3) 0%, rgba(15,23,42,0.6) 50%, rgba(15,23,42,0.95) 100%); } .stat-card { transition: transform 0.2s ease; } .stat-card:hover { transform: translateY(-2px); } @keyframes landing-fade-in { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } } .landing-animate { animation: landing-fade-in 0.6s ease-out both; } .landing-animate-delay-1 { animation-delay: 0.1s; } .landing-animate-delay-2 { animation-delay: 0.2s; }")
    nav_links = [
        A("Photos", href="/?section=photos", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
        A("People", href="/?section=confirmed", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
        A("Review", href="/?section=to_review", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
    ]
    if is_auth_enabled() and not user:
        nav_links.append(A("Sign In", href="/login", cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors ml-4"))
    if user:
        nav_links.append(Span(user.email.split("@")[0], cls="text-xs text-slate-500 ml-4"))
    # Pick a hero image URL for OG (first available featured photo)
    _og_hero_url = f"{SITE_URL}/static/crops/landing-hero.jpg"
    _featured = _get_featured_photos(limit=1)
    if _featured:
        _hero_url = _featured[0].get("url", "")
        _og_hero_url = _hero_url if _hero_url.startswith("http") else f"{SITE_URL}{_hero_url}"
    _og_landing_desc = f"A living archive of {stats['photo_count']} photographs and {stats['named_count']} identified people from the Rhodes-Capeluto family. Help us preserve our shared heritage."
    return (
        Title("Rhodesli — Rhodes-Capeluto Family Archive"),
        Meta(property="og:title", content="Rhodesli — Rhodes-Capeluto Family Archive"),
        Meta(property="og:description", content=_og_landing_desc),
        Meta(property="og:image", content=_og_hero_url),
        Meta(property="og:url", content=SITE_URL),
        Meta(property="og:type", content="website"),
        Meta(property="og:site_name", content="Rhodesli — Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image"),
        Meta(name="twitter:title", content="Rhodesli — Rhodes-Capeluto Family Archive"),
        Meta(name="twitter:description", content=_og_landing_desc),
        Meta(name="twitter:image", content=_og_hero_url),
        Meta(name="description", content=_og_landing_desc),
        style,
        Div(
        Nav(Div(A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"), Div(*nav_links, cls="hidden sm:flex items-center gap-6"), cls="max-w-6xl mx-auto px-6 flex items-center justify-between"), cls="fixed top-0 left-0 right-0 h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 z-50", id="landing-nav"),
        Section(Div(*hero_photos, cls="hero-grid"), Div(cls="hero-overlay absolute inset-0"), Div(H1("Preserving the faces and stories of the Rhodes-Capeluto family", cls="text-3xl md:text-4xl lg:text-5xl font-bold text-white leading-tight mb-6 landing-animate max-w-3xl"), P("A living archive of our shared history, brought together by family and powered by careful research. Every photo tells a story. Every face is a connection.", cls="text-lg md:text-xl text-slate-300 mb-10 max-w-2xl landing-animate landing-animate-delay-1"), Div(primary_cta, secondary_cta, cls="flex flex-wrap gap-4 landing-animate landing-animate-delay-2"), cls="absolute inset-0 flex flex-col justify-end px-6 md:px-12 lg:px-16 pb-12 md:pb-16"), cls="relative overflow-hidden pt-16", id="hero"),
        Section(Div(P("The archive so far", cls="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-8 text-center"), Div(Div(Div(str(stats["photo_count"]), cls="text-4xl md:text-5xl font-bold text-white mb-1"), Div("photos preserved", cls="text-sm text-slate-400"), cls="stat-card text-center p-6 bg-slate-800/50 rounded-xl border border-slate-700/50"), Div(Div(str(stats["named_count"]), cls="text-4xl md:text-5xl font-bold text-emerald-400 mb-1"), Div("people identified", cls="text-sm text-slate-400"), cls="stat-card text-center p-6 bg-slate-800/50 rounded-xl border border-slate-700/50"), Div(Div(str(stats["total_faces"]), cls="text-4xl md:text-5xl font-bold text-amber-400 mb-1"), Div("faces detected", cls="text-sm text-slate-400"), cls="stat-card text-center p-6 bg-slate-800/50 rounded-xl border border-slate-700/50"), A(Div(str(stats["needs_help"]), cls="text-4xl md:text-5xl font-bold text-blue-400 mb-1"), Div("faces need your help", cls="text-sm text-slate-400"), href="/?section=to_review", cls="stat-card text-center p-6 bg-slate-800/50 rounded-xl border border-slate-700/50 hover:border-blue-500/50 transition-colors block"), cls="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6"), cls="max-w-4xl mx-auto px-6"), cls="py-16 md:py-20", id="stats"),
        Section(Div(P("How it works", cls="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-4 text-center"), H2("Help us piece together our family history", cls="text-2xl md:text-3xl font-bold text-white text-center mb-12"), Div(step_card(browse_icon, "Browse Photos", "Explore our growing collection of family photographs spanning generations and continents -- from Rhodes to New York and beyond."), Div(NotStr(arrow_svg), cls="hidden md:flex items-center justify-center"), step_card(identify_icon, "Help Identify People", "Do you recognize someone? Your knowledge of the family is invaluable. Confirm names, suggest identifications, or note who you remember."), Div(NotStr(arrow_svg), cls="hidden md:flex items-center justify-center"), step_card(connect_icon, "Connect with History", "Each identification connects a face to a story, strengthening our family tree and preserving memories for future generations."), cls="grid grid-cols-1 md:grid-cols-5 gap-8 md:gap-4 items-start"), cls="max-w-5xl mx-auto px-6"), cls="py-16 md:py-20 border-t border-slate-800", id="how-it-works"),
        Section(Div(H2(f"{stats['needs_help']} faces are waiting to be recognized", cls="text-2xl md:text-3xl font-bold text-white mb-4"), P("If you grew up hearing stories about the family, you might be the one who can put a name to a face. Every identification helps.", cls="text-slate-300 mb-8 max-w-xl mx-auto"), Div(primary_cta, A("Help Identify Faces", href="/?section=to_review", cls="inline-block px-8 py-4 border-2 border-blue-500 text-blue-300 text-lg font-semibold rounded-xl hover:border-blue-300 hover:text-white transition-colors"), cls="flex flex-wrap justify-center gap-4"), cls="text-center max-w-3xl mx-auto px-6"), cls="py-16 md:py-20 bg-gradient-to-b from-slate-800/50 to-transparent border-t border-slate-800", id="cta"),
        Section(Div(H2("About this project", cls="text-xl font-bold text-white mb-4"), P("Rhodesli is a community effort to preserve the photographic heritage of the Rhodes-Capeluto family and the broader Sephardic community of Rhodes. These photos, spanning decades of family life across continents, represent irreplaceable memories that connect us to our shared roots.", cls="text-slate-400 leading-relaxed mb-4"), P("Using careful face detection technology, we have begun the work of identifying the people in these photographs. But technology can only do so much -- we need family members who remember these faces and their stories to help complete the picture.", cls="text-slate-400 leading-relaxed"), cls="max-w-3xl mx-auto px-6"), cls="py-16 md:py-20 border-t border-slate-800", id="about"),
        Footer(Div(Div(Span("Rhodesli", cls="text-lg font-bold text-white"), Span(" -- A family heritage project", cls="text-sm text-slate-500"), cls="flex items-baseline gap-1 flex-wrap"), Div(A("Photos", href="/?section=photos", cls="text-xs text-slate-500 hover:text-slate-300"), Span("|", cls="text-slate-700"), A("People", href="/?section=confirmed", cls="text-xs text-slate-500 hover:text-slate-300"), Span("|", cls="text-slate-700"), A("Review Inbox", href="/?section=to_review", cls="text-xs text-slate-500 hover:text-slate-300"), cls="flex items-center gap-2"), cls="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4"), cls="py-8 border-t border-slate-800"),
        cls="min-h-screen bg-slate-900"),
    )


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
    skipped = registry.list_identities(state=IdentityState.SKIPPED)
    needs_help = sum(
        len(i.get("anchor_ids", [])) + len(i.get("candidate_ids", []))
        for i in inbox + proposed + skipped
    )
    # Collect confirmed names for display
    named_people = [
        i["name"] for i in confirmed
        if not i["name"].startswith("Unidentified")
    ]
    # Collect a few unidentified faces for the "Can you help?" teaser
    crop_files = get_crop_files()
    unidentified_faces = []
    unid_identities = [
        i for i in inbox + proposed
        if not i.get("merged_into")
    ]
    random.shuffle(unid_identities)
    for identity in unid_identities[:6]:
        face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        if face_ids:
            url = resolve_face_image_url(face_ids[0], crop_files)
            if url:
                unidentified_faces.append({
                    "identity_id": identity["identity_id"],
                    "crop_url": url,
                })
        if len(unidentified_faces) >= 4:
            break
    # Source collections
    sources = set()
    if _photo_cache:
        for pd in _photo_cache.values():
            src = pd.get("source", "")
            if src:
                sources.add(src)
    return {
        "photo_count": len(_photo_cache) if _photo_cache else 0,
        "named_count": len(confirmed),
        "total_faces": total_faces,
        "needs_help": needs_help,
        "named_people": named_people,
        "unidentified_faces": unidentified_faces,
        "sources": sorted(sources),
    }


def _get_featured_photos(limit: int = 8) -> list:
    """Pick photos that have confirmed/named identities for the landing page hero.

    Returns richer data including face bounding boxes and photo dimensions
    for the interactive hover effect on the landing page.
    """
    registry = load_registry()
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    _build_caches()
    if not _photo_cache:
        return []

    dim_cache = _load_photo_dimensions_cache()

    # Build map of face_id -> identity name
    face_to_name = {}
    confirmed_face_ids = set()
    for identity in confirmed:
        name = identity.get("name", "")
        if name.startswith("Unidentified"):
            name = ""
        for fid in identity.get("anchor_ids", []) + identity.get("candidate_ids", []):
            confirmed_face_ids.add(fid)
            if name:
                face_to_name[fid] = name

    # Prefer landscape photos with many faces and confirmed identities
    scored_photos = []
    for photo_id, photo_data in _photo_cache.items():
        faces = photo_data.get("faces", [])
        num_faces = len(faces)
        confirmed_count = sum(1 for f in faces if f.get("face_id") in confirmed_face_ids)
        filename = photo_data["filename"]
        dims = dim_cache.get(filename) or dim_cache.get(Path(filename).name)
        w, h = dims if dims else (0, 0)
        is_landscape = w > h if w and h else False
        # Skip photos without cached dimensions (can't render face boxes)
        if w == 0 or h == 0:
            continue
        # Score: prefer landscape, more faces, more confirmed
        score = (confirmed_count * 3) + num_faces + (2 if is_landscape else 0)
        if num_faces >= 2:  # Only show photos with multiple people
            scored_photos.append((score, photo_id))

    scored_photos.sort(key=lambda x: x[0], reverse=True)
    featured_photo_ids = [pid for _, pid in scored_photos[:limit]]

    # If not enough, fill with any multi-face photos
    if len(featured_photo_ids) < limit:
        for photo_id in _photo_cache:
            if photo_id not in featured_photo_ids:
                faces = _photo_cache[photo_id].get("faces", [])
                if len(faces) >= 1:
                    featured_photo_ids.append(photo_id)
                    if len(featured_photo_ids) >= limit:
                        break

    results = []
    for pid in featured_photo_ids[:limit]:
        if pid not in _photo_cache:
            continue
        pdata = _photo_cache[pid]
        filename = pdata["filename"]
        dims = dim_cache.get(filename) or dim_cache.get(Path(filename).name)
        w, h = dims if dims else (0, 0)
        faces = pdata.get("faces", [])

        face_boxes = []
        for face in faces:
            fid = face.get("face_id", "")
            bbox = face.get("bbox", [])
            if bbox and w > 0 and h > 0:
                # Convert bbox from pixel coords to percentages
                x1, y1, x2, y2 = bbox
                face_boxes.append({
                    "left": round(x1 / w * 100, 2),
                    "top": round(y1 / h * 100, 2),
                    "width": round((x2 - x1) / w * 100, 2),
                    "height": round((y2 - y1) / h * 100, 2),
                    "name": face_to_name.get(fid, ""),
                })

        results.append({
            "id": pid,
            "url": photo_url(filename),
            "width": w,
            "height": h,
            "face_count": len(face_boxes),
            "face_boxes": face_boxes,
        })
    return results


def landing_page(stats, featured_photos):
    """Render the public landing page for the Rhodesli heritage archive.

    This page is only shown to anonymous visitors. Logged-in users are
    redirected to the dashboard by the GET / route handler.
    """
    auth_enabled = is_auth_enabled()

    # Build hero photo cards with face detection overlay data
    hero_cards = []
    for i, p in enumerate(featured_photos[:6]):
        # Build face detection overlay boxes (shown on hover)
        face_overlays = []
        for box in p.get("face_boxes", []):
            name = box.get("name", "")
            face_overlays.append(
                Div(
                    Span(name, cls="face-label") if name else None,
                    cls="face-box",
                    style=f"left:{box['left']}%;top:{box['top']}%;width:{box['width']}%;height:{box['height']}%;"
                )
            )
        # Determine grid span for visual variety
        span_cls = ""
        if i == 0:
            span_cls = "md:col-span-2 md:row-span-2"

        hero_cards.append(
            Div(
                Img(
                    src=p["url"],
                    alt="Archival photograph from the Jewish community of Rhodes",
                    loading="eager" if i < 2 else "lazy",
                    cls="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105",
                    onerror="this.closest('.hero-card').style.display='none'"
                ),
                # Face detection overlay
                Div(
                    *face_overlays,
                    cls="face-overlay"
                ) if face_overlays else None,
                # Face count badge
                Div(
                    Span(f"{p['face_count']} faces detected", cls="text-xs"),
                    cls="absolute bottom-2 right-2 bg-black/70 text-amber-200 px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                ) if p.get("face_count", 0) > 0 else None,
                cls=f"hero-card group relative overflow-hidden {span_cls}",
            )
        )

    # "Can you help?" mystery faces
    mystery_faces = []
    for face in stats.get("unidentified_faces", []):
        mystery_faces.append(
            A(
                Img(
                    src=face["crop_url"],
                    alt="Unidentified person from the Rhodes archive",
                    loading="lazy",
                    cls="w-full h-full object-cover rounded-full border-2 border-amber-400/50 hover:border-amber-300 transition-all duration-300 hover:scale-110"
                ),
                href=f"/?section=to_review&current={face['identity_id']}",
                cls="block w-20 h-20 md:w-24 md:h-24 rounded-full overflow-hidden flex-shrink-0"
            )
        )

    # Navigation bar
    nav_items = [
        A("Photos", href="/?section=photos", cls="text-slate-300 hover:text-amber-200 transition-colors text-sm md:text-base"),
        A("People", href="/?section=confirmed", cls="text-slate-300 hover:text-amber-200 transition-colors text-sm md:text-base"),
        A("Help Identify", href="/?section=skipped", cls="text-slate-300 hover:text-amber-200 transition-colors text-sm md:text-base"),
        A("About", href="/about", cls="text-slate-300 hover:text-amber-200 transition-colors text-sm md:text-base"),
    ]
    if auth_enabled:
        nav_items.append(
            A("Sign In", href="/login", cls="text-amber-300 hover:text-amber-200 font-medium transition-colors text-sm md:text-base")
        )

    # Named people for the ticker / display
    named_people = stats.get("named_people", [])

    landing_style = Style("""
        /* ============ LANDING PAGE STYLES ============ */
        html, body { height: 100%; margin: 0; }
        body { background-color: #1a1511; }

        /* Warm sepia/archival color palette */
        .landing-bg { background: linear-gradient(180deg, #1a1511 0%, #1e1a15 40%, #1a1511 100%); }

        /* Hero mosaic grid */
        .hero-mosaic {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            grid-template-rows: repeat(2, 200px);
            gap: 3px;
        }
        @media (max-width: 767px) {
            .hero-mosaic {
                grid-template-columns: repeat(2, 1fr);
                grid-template-rows: repeat(3, 160px);
            }
            .hero-mosaic .md\\:col-span-2 { grid-column: span 2; }
            .hero-mosaic .md\\:row-span-2 { grid-row: span 1; }
        }
        @media (min-width: 768px) {
            .hero-mosaic {
                grid-template-rows: repeat(2, 220px);
            }
        }
        @media (min-width: 1024px) {
            .hero-mosaic {
                grid-template-rows: repeat(2, 260px);
            }
        }

        .hero-card {
            position: relative;
            overflow: hidden;
            background: #2a241e;
        }
        .hero-card::after {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to bottom, transparent 60%, rgba(26, 21, 17, 0.6) 100%);
            pointer-events: none;
        }

        /* Face detection overlay */
        .face-overlay {
            position: absolute;
            inset: 0;
            opacity: 0;
            transition: opacity 0.4s ease;
            z-index: 5;
        }
        .hero-card:hover .face-overlay {
            opacity: 1;
        }
        .face-box {
            position: absolute;
            border: 2px solid rgba(251, 191, 36, 0.8);
            border-radius: 3px;
            box-shadow: 0 0 8px rgba(251, 191, 36, 0.3);
        }
        .face-label {
            position: absolute;
            bottom: -22px;
            left: 50%;
            transform: translateX(-50%);
            white-space: nowrap;
            font-size: 11px;
            color: #fbbf24;
            background: rgba(0, 0, 0, 0.8);
            padding: 1px 6px;
            border-radius: 3px;
        }

        /* Sepia film border on hero */
        .hero-frame {
            border: 3px solid #3d3428;
            border-radius: 4px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5), inset 0 0 40px rgba(0, 0, 0, 0.2);
            position: relative;
        }
        .hero-frame::before {
            content: '';
            position: absolute;
            inset: -1px;
            border: 1px solid rgba(251, 191, 36, 0.1);
            border-radius: 5px;
            pointer-events: none;
            z-index: 10;
        }

        /* Stat counter animation */
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            color: #f5e6d3;
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }
        .stat-label {
            font-size: 0.8rem;
            color: #a09080;
            margin-top: 0.5rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }
        .stat-card {
            text-align: center;
            padding: 1.5rem 1rem;
            background: rgba(61, 52, 40, 0.3);
            border: 1px solid rgba(61, 52, 40, 0.5);
            border-radius: 8px;
            transition: transform 0.2s, border-color 0.2s;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            border-color: rgba(251, 191, 36, 0.3);
        }

        /* Name ticker / scroll */
        .names-scroll {
            display: flex;
            gap: 2rem;
            animation: scroll-names 30s linear infinite;
            width: max-content;
        }
        @keyframes scroll-names {
            from { transform: translateX(0); }
            to { transform: translateX(-50%); }
        }
        .names-track {
            overflow: hidden;
            mask-image: linear-gradient(to right, transparent 0%, black 10%, black 90%, transparent 100%);
            -webkit-mask-image: linear-gradient(to right, transparent 0%, black 10%, black 90%, transparent 100%);
        }

        /* Animations */
        @keyframes fade-in-up {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in-up { animation: fade-in-up 0.8s ease-out both; }
        .delay-1 { animation-delay: 0.15s; }
        .delay-2 { animation-delay: 0.3s; }
        .delay-3 { animation-delay: 0.45s; }
        .delay-4 { animation-delay: 0.6s; }

        @keyframes gentle-pulse {
            0%, 100% { opacity: 0.7; }
            50% { opacity: 1; }
        }
        .animate-gentle-pulse { animation: gentle-pulse 3s ease-in-out infinite; }

        /* CTA buttons */
        .btn-primary {
            display: inline-block;
            padding: 0.875rem 2rem;
            background: linear-gradient(135deg, #b45309 0%, #d97706 100%);
            color: #fff;
            font-weight: 600;
            border-radius: 8px;
            transition: all 0.3s;
            text-decoration: none;
            font-size: 1rem;
            box-shadow: 0 2px 10px rgba(180, 83, 9, 0.3);
        }
        .btn-primary:hover {
            background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
            box-shadow: 0 4px 20px rgba(180, 83, 9, 0.4);
            transform: translateY(-1px);
        }
        .btn-secondary {
            display: inline-block;
            padding: 0.875rem 2rem;
            border: 1px solid #5d4e3c;
            color: #d4c4a8;
            font-weight: 600;
            border-radius: 8px;
            transition: all 0.3s;
            text-decoration: none;
            font-size: 1rem;
        }
        .btn-secondary:hover {
            border-color: #a08c6e;
            background: rgba(61, 52, 40, 0.4);
            color: #f5e6d3;
        }

        /* About section separator */
        .ornament {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin: 0 auto;
            max-width: 200px;
        }
        .ornament::before, .ornament::after {
            content: '';
            flex: 1;
            height: 1px;
            background: linear-gradient(to right, transparent, #5d4e3c, transparent);
        }

        /* Mystery face glow */
        .mystery-face-ring {
            position: relative;
        }
        .mystery-face-ring::before {
            content: '';
            position: absolute;
            inset: -3px;
            border-radius: 50%;
            background: conic-gradient(from 0deg, #fbbf24, #b45309, #fbbf24);
            opacity: 0;
            transition: opacity 0.3s;
            z-index: -1;
        }
        .mystery-face-ring:hover::before {
            opacity: 0.6;
            animation: gentle-pulse 2s ease-in-out infinite;
        }

        /* Responsive adjustments */
        @media (max-width: 640px) {
            .stat-number { font-size: 1.75rem; }
            .stat-card { padding: 1rem 0.5rem; }
        }

        /* ============================================================
           MOBILE RESPONSIVE STYLES
           ============================================================ */
        @media (max-width: 767px) {
            .main-content {
                margin-left: 0 !important;
                padding-top: 56px;
            }
            .main-content .main-inner {
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 1rem;
            }
            .focus-card-layout {
                flex-direction: column !important;
                gap: 1rem !important;
            }
            .focus-card-layout .focus-thumbnail {
                width: 100% !important;
            }
            .focus-card-layout .focus-thumbnail > div {
                width: 100% !important;
                height: auto !important;
                aspect-ratio: 1 / 1;
                max-width: 200px;
                margin: 0 auto;
            }
            .focus-actions {
                flex-wrap: wrap !important;
            }
            .focus-actions button {
                flex: 1 1 auto;
                min-width: 80px;
            }
            .section-header {
                flex-direction: column !important;
                align-items: flex-start !important;
                gap: 0.75rem;
            }
            .filter-bar {
                flex-direction: column !important;
                align-items: stretch !important;
                gap: 0.5rem !important;
            }
            .filter-bar .ml-auto {
                margin-left: 0;
            }
            .identity-card-header {
                flex-direction: column !important;
                align-items: flex-start !important;
                gap: 0.5rem;
            }
            .neighbors-sidebar .flex.items-center {
                flex-wrap: wrap;
            }
            #toast-container {
                left: 1rem;
                right: 1rem;
                max-width: none;
            }
        }
        @media (min-width: 768px) and (max-width: 1023px) {
            .main-content {
                margin-left: 0 !important;
                padding-top: 56px;
            }
            .main-content .main-inner {
                padding-left: 2rem;
                padding-right: 2rem;
            }
        }
        @media (max-width: 1023px) {
            .mobile-header {
                display: flex !important;
            }
        }
        @media (min-width: 1024px) {
            .mobile-header {
                display: none !important;
            }
            .main-content {
                margin-left: 16rem;
            }
        }
    """)

    landing_script = Script("""
        // Animated counter for stats
        document.addEventListener('DOMContentLoaded', function() {
            var counters = document.querySelectorAll('[data-count]');
            var observer = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        var el = entry.target;
                        var target = parseInt(el.getAttribute('data-count'));
                        var duration = 1500;
                        var start = 0;
                        var startTime = null;
                        function step(timestamp) {
                            if (!startTime) startTime = timestamp;
                            var progress = Math.min((timestamp - startTime) / duration, 1);
                            // Ease out cubic
                            var eased = 1 - Math.pow(1 - progress, 3);
                            el.textContent = Math.floor(eased * target).toLocaleString();
                            if (progress < 1) {
                                requestAnimationFrame(step);
                            } else {
                                el.textContent = target.toLocaleString();
                            }
                        }
                        requestAnimationFrame(step);
                        observer.unobserve(el);
                    }
                });
            }, {threshold: 0.3});
            counters.forEach(function(c) { observer.observe(c); });
        });
    """)

    # Duplicate names list for seamless scroll effect
    names_display = named_people + named_people if named_people else []

    # OG meta tags for social sharing
    _og_hero_url = f"{SITE_URL}/static/crops/landing-hero.jpg"
    if featured_photos:
        _hero_url = featured_photos[0].get("url", "")
        _og_hero_url = _hero_url if _hero_url.startswith("http") else f"{SITE_URL}{_hero_url}"
    _og_desc = f"A living archive of {stats['photo_count']} photographs and {stats['named_count']} identified people from the Jewish community of Rhodes. Help us preserve our shared heritage."

    return (
        Title("Rhodesli -- Jewish Community of Rhodes Photo Archive"),
        Meta(property="og:title", content="Rhodesli -- Jewish Community of Rhodes Photo Archive"),
        Meta(property="og:description", content=_og_desc),
        Meta(property="og:image", content=_og_hero_url),
        Meta(property="og:url", content=SITE_URL),
        Meta(property="og:type", content="website"),
        Meta(property="og:site_name", content="Rhodesli -- Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image"),
        Meta(name="twitter:title", content="Rhodesli -- Jewish Community of Rhodes Photo Archive"),
        Meta(name="twitter:description", content=_og_desc),
        Meta(name="twitter:image", content=_og_hero_url),
        Meta(name="description", content=_og_desc),
        landing_style,
        landing_script,
    Div(
        # Navigation
        Nav(
            Div(
                Div(
                    Span("Rhodesli", cls="text-xl md:text-2xl font-bold text-amber-100 tracking-wide"),
                    Span("Photo Archive", cls="text-xs text-amber-400/60 ml-2 hidden md:inline tracking-widest uppercase"),
                    cls="flex items-baseline"
                ),
                Div(*nav_items, cls="hidden sm:flex items-center gap-4 md:gap-6"),
                cls="max-w-6xl mx-auto px-4 md:px-6 py-4 flex items-center justify-between flex-wrap gap-3"
            ),
            cls="border-b border-amber-900/30 bg-black/20 backdrop-blur-sm sticky top-0 z-50"
        ),

        # Hero section
        Section(
            Div(
                # Headline area
                Div(
                    Div(
                        Div(cls="ornament mb-6"),
                        H1(
                            Span("Preserving the faces and stories", cls="block"),
                            Span("of the Jewish Community of Rhodes", cls="block text-amber-200"),
                            cls="text-3xl md:text-5xl lg:text-6xl font-bold text-amber-50 leading-tight tracking-tight"
                        ),
                        P("A digital archive using face recognition to reconnect generations of a Ladino-speaking "
                          "Sephardic community scattered by history. Browse photographs, identify faces, and help "
                          "preserve a living record.",
                          cls="text-base md:text-lg text-amber-100/60 mt-6 max-w-2xl mx-auto leading-relaxed"),
                        # CTA buttons
                        Div(
                            A("Start Exploring", href="/?section=photos", cls="btn-primary"),
                            A("Help Identify", href="/?section=skipped", cls="btn-secondary"),
                            cls="mt-8 flex flex-wrap gap-4 justify-center"
                        ),
                        cls="text-center animate-fade-in-up"
                    ),
                    cls="py-10 md:py-16 px-4 md:px-6"
                ),

                # Photo mosaic with face detection hover
                Div(
                    Div(
                        *hero_cards,
                        cls="hero-mosaic"
                    ),
                    # Instruction hint
                    P("Hover over photos to reveal face detection",
                      cls="text-center text-amber-400/40 text-xs mt-3 tracking-wide uppercase animate-gentle-pulse"),
                    cls="hero-frame animate-fade-in-up delay-1"
                ) if hero_cards else None,

                cls="max-w-5xl mx-auto"
            ),
            id="hero", cls="pt-4 pb-8 md:pb-12"
        ),

        # Names ticker -- confirmed identities scrolling
        Section(
            Div(
                P("Identified so far", cls="text-center text-amber-400/50 text-xs tracking-widest uppercase mb-3"),
                Div(
                    Div(
                        *[Span(name, cls="text-amber-200/70 whitespace-nowrap text-sm md:text-base") for name in names_display],
                        cls="names-scroll"
                    ),
                    cls="names-track"
                ),
                cls="max-w-5xl mx-auto"
            ),
            cls="py-6 px-4 border-y border-amber-900/20"
        ) if named_people else None,

        # Progress dashboard (FE-053) — prominent identification progress
        Section(
            Div(
                # Progress headline
                Div(
                    H2(
                        Span(str(stats["named_count"]), cls="text-amber-200"),
                        " of ",
                        Span(str(stats["total_faces"]), cls="text-amber-100/80"),
                        " faces identified",
                        cls="text-xl md:text-2xl font-bold text-amber-50 text-center"
                    ),
                    P("Help us name the rest \u2014 every identification preserves irreplaceable history.",
                      cls="text-amber-100/40 text-center text-sm mt-2"),
                    cls="mb-6"
                ),
                # Progress bar
                Div(
                    Div(
                        cls="h-full bg-gradient-to-r from-amber-600 to-amber-400 rounded-full transition-all duration-1000",
                        style=f"width: {min(100, int(stats['named_count'] / max(1, stats['total_faces']) * 100))}%",
                    ),
                    cls="w-full max-w-lg mx-auto h-3 bg-amber-900/30 rounded-full overflow-hidden border border-amber-900/40"
                ),
                Div(
                    Span(f"{min(100, int(stats['named_count'] / max(1, stats['total_faces']) * 100))}% complete",
                         cls="text-amber-400/60 text-xs"),
                    cls="text-center mt-2"
                ),
                cls="max-w-4xl mx-auto animate-fade-in-up"
            ),
            cls="py-8 md:py-10 px-4 md:px-6"
        ),

        # Stats section
        Section(
            Div(
                Div(
                    Div(
                        Div("0", cls="stat-number", **{"data-count": str(stats["photo_count"])}),
                        Div("archival photos", cls="stat-label"),
                        cls="stat-card animate-fade-in-up"
                    ),
                    Div(
                        Div("0", cls="stat-number", **{"data-count": str(stats["named_count"])}),
                        Div("people identified", cls="stat-label"),
                        cls="stat-card animate-fade-in-up delay-1"
                    ),
                    Div(
                        Div("0", cls="stat-number", **{"data-count": str(stats["total_faces"])}),
                        Div("faces detected by AI", cls="stat-label"),
                        cls="stat-card animate-fade-in-up delay-2"
                    ),
                    Div(
                        Div("0", cls="stat-number", **{"data-count": str(stats["needs_help"])}),
                        Div("awaiting identification", cls="stat-label"),
                        cls="stat-card animate-fade-in-up delay-3"
                    ),
                    cls="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4"
                ),
                cls="max-w-4xl mx-auto"
            ),
            id="stats", cls="py-12 md:py-16 px-4 md:px-6"
        ),

        # "Can you help?" mystery faces section
        Section(
            Div(
                Div(
                    H2("Can you identify these faces?",
                       cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-3"),
                    P("Our AI has detected these faces across the archive, but we do not know who they are. "
                      "If you recognize anyone, your knowledge is priceless.",
                      cls="text-amber-100/50 text-center max-w-xl mx-auto text-sm md:text-base"),
                    cls="mb-8"
                ),
                # Mystery face circles
                Div(
                    *[Div(face, cls="mystery-face-ring") for face in mystery_faces],
                    cls="flex justify-center gap-5 md:gap-8 flex-wrap"
                ) if mystery_faces else None,
                Div(
                    A("Help Identify People", href="/?section=skipped",
                      cls="btn-primary mt-8 inline-block"),
                    cls="text-center"
                ),
                cls="max-w-3xl mx-auto"
            ),
            id="identify", cls="py-12 md:py-16 px-4 md:px-6 bg-gradient-to-b from-transparent via-amber-900/10 to-transparent"
        ) if mystery_faces else None,

        # How it works
        Section(
            Div(
                Div(cls="ornament mb-8"),
                H2("How It Works", cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-10"),
                Div(
                    Div(
                        Div(
                            Span("01", cls="text-3xl font-bold text-amber-500/30"),
                            cls="mb-3"
                        ),
                        H3("Scan & Detect", cls="text-lg font-semibold text-amber-100 mb-2"),
                        P("Advanced face detection AI scans archival photographs, finding and isolating every face "
                          "across decades of family photos.",
                          cls="text-amber-100/50 text-sm leading-relaxed"),
                        cls="p-6 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-700/30 transition-colors"
                    ),
                    Div(
                        Div(
                            Span("02", cls="text-3xl font-bold text-amber-500/30"),
                            cls="mb-3"
                        ),
                        H3("Match & Group", cls="text-lg font-semibold text-amber-100 mb-2"),
                        P("Facial embeddings connect the same person across different photos, even spanning decades. "
                          "The system proposes identity clusters for human review.",
                          cls="text-amber-100/50 text-sm leading-relaxed"),
                        cls="p-6 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-700/30 transition-colors"
                    ),
                    Div(
                        Div(
                            Span("03", cls="text-3xl font-bold text-amber-500/30"),
                            cls="mb-3"
                        ),
                        H3("Name & Preserve", cls="text-lg font-semibold text-amber-100 mb-2"),
                        P("Community members who recognize a face can name them, adding irreplaceable human knowledge. "
                          "Every identification is preserved for future generations.",
                          cls="text-amber-100/50 text-sm leading-relaxed"),
                        cls="p-6 bg-amber-900/10 rounded-lg border border-amber-900/20 hover:border-amber-700/30 transition-colors"
                    ),
                    cls="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6"
                ),
                cls="max-w-5xl mx-auto"
            ),
            id="how-it-works", cls="py-12 md:py-16 px-4 md:px-6"
        ),

        # About section
        Section(
            Div(
                Div(cls="ornament mb-8"),
                H2("About This Archive", cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-6"),
                Div(
                    P("For over two thousand years, a Jewish community flourished on the island of Rhodes, "
                      "at the crossroads of the Aegean. After the expulsion from Spain in 1492, Sephardic families "
                      "settled in the walled quarter known as ",
                      Em("La Juderia"),
                      ", bringing with them the Ladino language, rabbinical traditions, and a vibrant culture of "
                      "merchants, craftsmen, and scholars. By the late 19th century, the community numbered several "
                      "thousand. Six synagogues stood in La Juderia, and the narrow arched streets rang with "
                      "Judeo-Spanish songs and the bustle of the ",
                      Em("cortijos"),
                      ", the shared courtyards where families gathered.",
                      cls="text-amber-100/60 leading-relaxed mb-4"),
                    P("Beginning in the early 20th century, Rhodesli Jews emigrated in waves \u2014 first to nearby "
                      "communities, then further abroad as the Italian occupation of 1912 and later the racial laws "
                      "of 1938 uprooted families. Chain migration carried them to specific cities worldwide: Seattle "
                      "and Los Angeles, Montgomery, Atlanta, and New York, Buenos Aires and S\u00e3o Paulo, "
                      "communities in Africa, the Middle East, and beyond. The Holocaust of July 1944 devastated "
                      "those who remained \u2014 of the 1,673 Jews deported from Rhodes and Kos to Auschwitz, "
                      "only 151 survived.",
                      cls="text-amber-100/60 leading-relaxed mb-4"),
                    P("Rhodesli is a digital preservation project that uses machine learning to reconnect faces "
                      "and stories scattered across family collections worldwide. The photographs come from "
                      "descendants around the world. Every identification you make \u2014 every name you recognize, "
                      "every story you share \u2014 helps preserve this heritage.",
                      cls="text-amber-100/60 leading-relaxed mb-4"),
                    A("Read more about the project \u2192", href="/about",
                      cls="text-amber-300/70 hover:text-amber-200 text-sm inline-block"),
                    cls="max-w-2xl mx-auto text-center"
                ),
                cls="max-w-5xl mx-auto"
            ),
            id="about", cls="py-12 md:py-16 px-4 md:px-6 bg-gradient-to-b from-transparent via-amber-950/20 to-transparent"
        ),

        # Bottom CTA
        Section(
            Div(
                H2("Every name matters",
                   cls="text-2xl md:text-3xl font-bold text-amber-50 text-center mb-3"),
                P(f"{stats['needs_help']} faces are awaiting identification. Your family knowledge can bring them home.",
                  cls="text-amber-100/50 text-center mb-8 max-w-lg mx-auto"),
                Div(
                    A("Start Exploring", href="/?section=photos", cls="btn-primary"),
                    A("Browse People", href="/?section=confirmed", cls="btn-secondary"),
                    cls="flex flex-wrap gap-4 justify-center"
                ),
                cls="max-w-3xl mx-auto text-center"
            ),
            id="cta", cls="py-12 md:py-16 px-4 md:px-6"
        ),

        # Footer
        Footer(
            Div(
                Div(cls="ornament mb-4"),
                P("Rhodesli",
                  cls="text-amber-200/40 text-sm text-center font-semibold tracking-wide"),
                P("Preserving the photographic heritage of the Jewish Community of Rhodes",
                  cls="text-amber-100/25 text-xs text-center mt-1"),
                P(A("About Rhodesli", href="/about", cls="text-amber-200/40 hover:text-amber-200 underline"),
                  " · Built with care. No generative AI -- only forensic face matching.",
                  cls="text-amber-100/20 text-xs text-center mt-3"),
                cls="max-w-6xl mx-auto px-6 py-8"
            ),
            cls="border-t border-amber-900/20"
        ),
        cls="min-h-screen landing-bg"
    ),
    )


@rt("/about")
def get():
    """About page: history, how to help, how it works, roles, dynamic stats."""
    stats = _compute_landing_stats()

    return (
        Title("About Rhodesli"),
        Style("""
            .about-bg { background: linear-gradient(180deg, #1a1511 0%, #1e1a15 40%, #1a1511 100%); }
            .about-section { max-width: 48rem; margin: 0 auto; }
            .faq-q { cursor: pointer; }
            .faq-q:hover { color: #fbbf24; }
        """),
        Main(
            # Back nav
            Div(
                A("\u2190 Back to Archive", href="/", cls="text-amber-300/70 hover:text-amber-200 text-sm"),
                cls="max-w-3xl mx-auto px-6 pt-8"
            ),
            # Title
            Div(
                H1("About Rhodesli", cls="text-3xl font-serif font-bold text-amber-100 mb-2"),
                Div(cls="w-16 h-0.5 bg-amber-400/40 mb-6"),
                cls="max-w-3xl mx-auto px-6 pt-4"
            ),
            # The Community
            Div(
                H2("The Community", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                P(
                    "For over two thousand years, a Jewish community flourished on the island of Rhodes, "
                    "at the crossroads of the Aegean. After the expulsion from Spain in 1492, Sephardic families "
                    "settled in the walled quarter known as ",
                    Em("La Juderia"),
                    ", bringing with them the Ladino language, rabbinical traditions, and a vibrant culture of "
                    "merchants, craftsmen, and scholars. By the late 19th century, the community numbered several "
                    "thousand \u2014 the second largest religious group on the island. Six synagogues stood in "
                    "La Juderia, and the narrow arched streets rang with Judeo-Spanish songs and the bustle "
                    "of the ",
                    Em("cortijos"),
                    ", the shared courtyards where families gathered.",
                    cls="text-slate-300 leading-relaxed mb-4"
                ),
                cls="about-section px-6 mb-10"
            ),
            # The Diaspora
            Div(
                H2("The Diaspora", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                P(
                    "Beginning in the early 20th century, Rhodesli Jews emigrated in waves \u2014 first to the "
                    "nearby communities of Kos, Milas, and Bodrum, then further abroad as the Italian occupation "
                    "of 1912 and later the racial laws of 1938 uprooted families. Chain migration carried them "
                    "to specific cities worldwide: Seattle and Los Angeles on the American West Coast; Montgomery, "
                    "Atlanta, and New York in the East; Buenos Aires and S\u00e3o Paulo in South America; "
                    "Elizabethville and Salisbury in Central and Southern Africa; Alexandria and Cairo; and "
                    "communities in Havana, Asheville, Israel, Brussels, and Miami.",
                    cls="text-slate-300 leading-relaxed mb-4"
                ),
                P(
                    "The Holocaust of July 1944 devastated those who remained \u2014 of the 1,673 Jews deported "
                    "from Rhodes and Kos to Auschwitz, only 151 survived.",
                    cls="text-slate-300 leading-relaxed"
                ),
                cls="about-section px-6 mb-10"
            ),
            # The Project
            Div(
                H2("The Project", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                P(
                    "Rhodesli is a digital preservation project that uses machine learning to reconnect faces "
                    "and stories scattered across family collections worldwide. By combining AI face detection "
                    "with the living memory of community descendants, we are building a searchable archive that "
                    "bridges generations. Every identification you make \u2014 every name you recognize, every "
                    "story you share \u2014 helps preserve this heritage.",
                    cls="text-slate-300 leading-relaxed mb-4"
                ),
                P(
                    f"The archive currently contains {stats['photo_count']} photographs with "
                    f"{stats['total_faces']} faces detected by AI. {stats['named_count']} people have "
                    f"been positively identified so far, with {stats['needs_help']} faces still awaiting "
                    f"identification.",
                    cls="text-slate-400 leading-relaxed italic"
                ),
                cls="about-section px-6 mb-10"
            ),
            # How to Help
            Div(
                H2("How to Help", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                Div(
                    Div(
                        Span("1", cls="text-amber-400 font-bold text-lg mr-3"),
                        Div(
                            Span("Browse and identify", cls="text-slate-200 font-medium"),
                            P("Look through the photo archive. If you recognize a face, suggest a name. "
                              "Your family knowledge is irreplaceable.",
                              cls="text-slate-400 text-sm mt-1"),
                        ),
                        cls="flex items-start mb-4"
                    ),
                    Div(
                        Span("2", cls="text-amber-400 font-bold text-lg mr-3"),
                        Div(
                            Span("Suggest names", cls="text-slate-200 font-medium"),
                            P("Use the 'Suggest Name' button on any unidentified face. Even partial "
                              "information helps \u2014 a last name, a family branch, or a generation.",
                              cls="text-slate-400 text-sm mt-1"),
                        ),
                        cls="flex items-start mb-4"
                    ),
                    Div(
                        Span("3", cls="text-amber-400 font-bold text-lg mr-3"),
                        Div(
                            Span("Upload family photos", cls="text-slate-200 font-medium"),
                            P("If you have photographs from the Rhodesli community, upload them to grow "
                              "the archive. All uploads are reviewed before being added.",
                              cls="text-slate-400 text-sm mt-1"),
                        ),
                        cls="flex items-start mb-4"
                    ),
                    Div(
                        Span("4", cls="text-amber-400 font-bold text-lg mr-3"),
                        Div(
                            Span("Add context", cls="text-slate-200 font-medium"),
                            P("Add dates, locations, occasions, and stories to photographs and identities. "
                              "Context turns a photograph into a piece of history.",
                              cls="text-slate-400 text-sm mt-1"),
                        ),
                        cls="flex items-start mb-4"
                    ),
                ),
                cls="about-section px-6 mb-10"
            ),
            # How It Works
            Div(
                H2("How It Works", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                Div(
                    Div(
                        Span("Detect", cls="text-amber-400 font-semibold"),
                        P(" \u2014 AI scans uploaded photographs and detects every face, creating a "
                          "mathematical fingerprint for each one.",
                          cls="text-slate-400 text-sm inline"),
                        cls="mb-3"
                    ),
                    Div(
                        Span("Group", cls="text-amber-400 font-semibold"),
                        P(" \u2014 The system compares fingerprints across all photos and proposes "
                          "clusters: faces that likely belong to the same person.",
                          cls="text-slate-400 text-sm inline"),
                        cls="mb-3"
                    ),
                    Div(
                        Span("Verify", cls="text-amber-400 font-semibold"),
                        P(" \u2014 Community members review these proposals. Confirmations strengthen "
                          "the system. Corrections help it learn. Nothing is permanent \u2014 every "
                          "decision can be undone.",
                          cls="text-slate-400 text-sm inline"),
                        cls="mb-3"
                    ),
                ),
                cls="about-section px-6 mb-10"
            ),
            # Roles
            Div(
                H2("Roles", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                Div(
                    Div(
                        Span("Visitors", cls="text-slate-200 font-medium"),
                        P(" can browse the entire archive freely without an account \u2014 every photograph, "
                          "every identified person, every face detection.",
                          cls="text-slate-400 text-sm inline"),
                        cls="mb-3"
                    ),
                    Div(
                        Span("Contributors", cls="text-slate-200 font-medium"),
                        P(" can suggest names, upload photos, and add annotations. All suggestions "
                          "are reviewed by an admin before being applied.",
                          cls="text-slate-400 text-sm inline"),
                        cls="mb-3"
                    ),
                    Div(
                        Span("Admins", cls="text-slate-200 font-medium"),
                        P(" review community suggestions, confirm identities, merge duplicates, "
                          "and manage the archive.",
                          cls="text-slate-400 text-sm inline"),
                        cls="mb-3"
                    ),
                ),
                cls="about-section px-6 mb-10"
            ),
            # FAQ
            Div(
                H2("Frequently Asked Questions", cls="text-xl font-serif font-semibold text-amber-200 mb-4"),
                Div(
                    Div(
                        H3("Is this generative AI?", cls="text-slate-200 font-medium faq-q mb-1"),
                        P("No. Rhodesli uses forensic face matching only \u2014 it compares mathematical "
                          "fingerprints of real faces. It never generates, invents, or fabricates anything.",
                          cls="text-slate-400 text-sm mb-4"),
                    ),
                    Div(
                        H3("Can I undo mistakes?", cls="text-slate-200 font-medium faq-q mb-1"),
                        P("Yes. Confirmations, rejections, and merges can all be undone. The system keeps "
                          "full history. No data is ever permanently deleted.",
                          cls="text-slate-400 text-sm mb-4"),
                    ),
                    Div(
                        H3("Do I need an account to browse?", cls="text-slate-200 font-medium faq-q mb-1"),
                        P("No. The entire archive is publicly browsable. An account is only needed to "
                          "submit suggestions, upload photos, or add annotations.",
                          cls="text-slate-400 text-sm mb-4"),
                    ),
                    Div(
                        H3("How can I contribute photos?", cls="text-slate-200 font-medium faq-q mb-1"),
                        P("Sign up with an invite code, then use the Upload page to add photographs. "
                          "All uploads are reviewed before being added to the archive.",
                          cls="text-slate-400 text-sm mb-4"),
                    ),
                ),
                cls="about-section px-6 mb-10"
            ),
            # Footer
            Div(
                P("Built with care. No generative AI \u2014 only forensic face matching.",
                  cls="text-amber-100/30 text-xs text-center"),
                A("\u2190 Back to Archive", href="/",
                  cls="text-amber-300/60 hover:text-amber-200 text-sm block text-center mt-3"),
                cls="about-section px-6 py-8 border-t border-amber-900/20"
            ),
            cls="min-h-screen about-bg"
        ),
    )


def _personalized_discovery_banner(interest_surnames: list[str], confirmed_list: list,
                                    crop_files: set, counts: dict) -> Div:
    """Render a personalized discovery banner showing people matching user's interest surnames.

    Shown at top of Needs Help section when user selected surnames during onboarding.
    """
    from core.registry import _load_surname_variants
    variant_lookup = _load_surname_variants()

    # Expand surnames to include variants
    target_names = set()
    for surname in interest_surnames:
        target_names.add(surname.lower())
        variants = variant_lookup.get(surname.lower(), [])
        target_names.update(variants)

    # Find matching confirmed identities
    matches = []
    for identity in confirmed_list:
        name = (identity.get("name") or "").strip()
        if not name or name.startswith("Unidentified"):
            continue
        name_words = [w.lower() for w in name.split()]
        if any(w in target_names for w in name_words):
            face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            crop_url = resolve_face_image_url(face_ids[0], crop_files) if face_ids else None
            if crop_url:
                matches.append({
                    "name": name,
                    "crop_url": crop_url,
                    "identity_id": identity["identity_id"],
                })

    if not matches:
        return Div()  # Empty — no banner

    # Show up to 5 matching people as a horizontal strip
    people_thumbs = []
    for m in matches[:5]:
        people_thumbs.append(
            A(
                Div(
                    Img(src=m["crop_url"], alt=m["name"],
                        cls="w-12 h-12 rounded-full object-cover border-2 border-amber-400/50"),
                    Span(m["name"].split()[0], cls="text-xs text-slate-400 mt-1 truncate w-14 text-center"),
                    cls="flex flex-col items-center",
                ),
                href=f"/?section=confirmed&current={m['identity_id']}",
                cls="hover:opacity-80 transition-opacity",
            )
        )

    surnames_display = " & ".join(interest_surnames[:3])
    more = f" +{len(interest_surnames) - 3}" if len(interest_surnames) > 3 else ""

    return Div(
        Div(
            Div(
                P(f"People from the {surnames_display}{more} families",
                  cls="text-sm font-medium text-amber-200"),
                P(f"{len(matches)} identified \u2014 can you help find more?",
                  cls="text-xs text-slate-400"),
                cls="flex-1",
            ),
            Div(*people_thumbs, cls="flex gap-3"),
            cls="flex items-center gap-4",
        ),
        A("View all \u2192", href=f"/?section=confirmed",
          cls="text-xs text-amber-400 hover:text-amber-300 mt-2 inline-block"),
        cls="bg-amber-900/20 border border-amber-700/30 rounded-lg p-4 mb-4",
    )


@rt("/")
def get(section: str = None, view: str = "focus", current: str = None,
        filter_source: str = "", filter_collection: str = "",
        sort_by: str = "newest", filter: str = "", request=None, sess=None):
    """
    Landing page (no section) or Command Center (with section parameter).
    Public access -- anyone can view. Action buttons shown only to admins.
    Logged-in users with no section go to the triage dashboard.
    """
    user = get_current_user(sess or {})

    # Read interest surnames from cookie for personalization
    interest_surnames = []
    if request:
        raw = request.cookies.get("rhodesli_interest_surnames", "")
        if raw:
            from urllib.parse import unquote
            interest_surnames = [s.strip() for s in unquote(raw).split(",") if s.strip()]

    # If no section specified:
    # - Logged-in users: go to inbox if items exist, otherwise Needs Help
    # - Anonymous users see the public landing page
    if section is None:
        if user is not None:
            # Smart redirect: skip empty inbox, go to Needs Help
            registry_check = load_registry()
            inbox_count = len(registry_check.list_identities(state=IdentityState.INBOX))
            proposed_count = len(registry_check.list_identities(state=IdentityState.PROPOSED))
            if inbox_count + proposed_count > 0:
                section = "to_review"
            else:
                section = "skipped"  # Needs Help — always has items to review
        else:
            stats = _compute_landing_stats()
            featured_photos = _get_featured_photos(8)
            return landing_page(stats, featured_photos)


    user_is_admin = (user.is_admin if user else False) if is_auth_enabled() else True

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

    # Canonical sidebar counts (single source of truth)
    counts = _compute_sidebar_counts(registry)

    # Validate section parameter
    valid_sections = ("to_review", "confirmed", "skipped", "rejected", "photos")
    if section not in valid_sections:
        section = "to_review"

    # Validate view parameter
    if view not in ("focus", "browse", "match"):
        view = "focus"

    # Personalized discovery banner when user has interest surnames
    discovery_banner = None
    if interest_surnames and section == "skipped":
        discovery_banner = _personalized_discovery_banner(interest_surnames, confirmed_list, crop_files, counts)

    # Render the appropriate section
    if section == "to_review":
        main_content = render_to_review_section(to_review, crop_files, view, counts, current_id=current, is_admin=user_is_admin, sort_by=sort_by, triage_filter=filter)
    elif section == "confirmed":
        main_content = render_confirmed_section(confirmed_list, crop_files, counts, is_admin=user_is_admin, sort_by=sort_by)
    elif section == "skipped":
        skipped_view = view if view in ("focus", "browse") else "focus"
        main_content = render_skipped_section(skipped_list, crop_files, counts, is_admin=user_is_admin, view_mode=skipped_view, current_id=current)
    elif section == "photos":
        main_content = render_photos_section(counts, registry, crop_files, filter_source, sort_by, filter_collection)
    else:  # rejected
        main_content = render_rejected_section(dismissed, crop_files, counts, is_admin=user_is_admin)

    # Prepend discovery banner to main content if present
    if discovery_banner:
        main_content = Div(discovery_banner, main_content)

    style = Style("""
        html, body {
            height: 100%;
            margin: 0;
            overflow-x: hidden;
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
        @keyframes card-enter {
            from { opacity: 0; transform: scale(0.97) translateY(8px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes card-exit {
            from { opacity: 1; transform: scale(1); }
            to { opacity: 0; transform: scale(0.97) translateY(-8px); }
        }
        .animate-fade-in {
            animation: fade-in 0.3s ease-out;
        }
        .animate-slide-out {
            animation: slide-out-right 0.3s ease-in forwards;
        }
        .animate-card-enter {
            animation: card-enter 0.35s ease-out;
        }
        /* HTMX swap transitions for focus card */
        #focus-card {
            animation: card-enter 0.35s ease-out;
        }
        /* Match mode pair transition */
        .match-pair {
            animation: card-enter 0.35s ease-out;
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
        /* Collapsible sidebar */
        .sidebar-container {
            width: 15rem;
            transition: width 0.2s ease, transform 0.3s ease;
        }
        .sidebar-container.collapsed {
            width: 3.5rem;
        }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results {
            display: none;
        }
        .sidebar-container.collapsed .sidebar-nav-item {
            justify-content: center;
            padding-left: 0;
            padding-right: 0;
        }
        .sidebar-container.collapsed .sidebar-icon {
            margin: 0;
        }
        .sidebar-container.collapsed .sidebar-chevron {
            transform: rotate(180deg);
        }
        .sidebar-container.collapsed .sidebar-collapse-btn {
            margin: 0 auto;
        }
        .sidebar-search-results:not(:empty) {
            position: absolute;
            left: 0.75rem;
            right: 0.75rem;
            top: 100%;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.5rem;
            max-height: 300px;
            overflow-y: auto;
            z-index: 50;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }
        /* Mobile responsive sidebar */
        @media (max-width: 767px) {
            #sidebar {
                width: 15rem !important;
                transform: translateX(-100%);
                transition: transform 0.3s ease;
            }
            #sidebar.open {
                transform: translateX(0);
            }
            #sidebar .sidebar-label { display: inline !important; }
            #sidebar .sidebar-search { display: block !important; }
            .main-content {
                margin-left: 0 !important;
            }
        }
        @media (min-width: 768px) {
            #sidebar { transform: translateX(0); }
        }
        @media (min-width: 1024px) {
            .main-content {
                margin-left: 15rem;
                transition: margin-left 0.2s ease;
            }
            .main-content.sidebar-collapsed {
                margin-left: 3.5rem;
            }
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

    # Sidebar toggle script (mobile open/close + desktop collapse/expand)
    sidebar_script = Script("""
        // Mobile: open/close sidebar
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
        // Desktop: collapse/expand sidebar
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
        // Restore sidebar state from localStorage on page load
        (function() {
            try {
                var collapsed = localStorage.getItem('sidebar_collapsed') === 'true';
                if (collapsed && window.innerWidth >= 1024) {
                    var sb = document.getElementById('sidebar');
                    var mc = document.querySelector('.main-content');
                    if (sb) sb.classList.add('collapsed');
                    if (mc) mc.classList.add('sidebar-collapsed');
                }
            } catch(e) {}
            // Close search results when clicking outside
            document.addEventListener('click', function(e) {
                var search = document.querySelector('.sidebar-search');
                var results = document.getElementById('sidebar-search-results');
                if (search && results && !search.contains(e.target)) {
                    results.innerHTML = '';
                }
            });
        })();
    """)

    # Mobile bottom tab navigation (lg:hidden)
    mobile_tabs = Nav(
        A(
            Svg(
                Path(d="M4 6h16M4 10h16M4 14h16M4 18h16"),
                cls="w-5 h-5", fill="none", stroke="currentColor", viewBox="0 0 24 24",
                stroke_width="2", stroke_linecap="round",
            ),
            Span("Photos", cls="text-[10px]"),
            href="/?section=photos",
            cls=f"flex flex-col items-center justify-center gap-0.5 min-h-[44px] min-w-[44px] "
                f"{'text-indigo-400' if section == 'photos' else 'text-slate-400 hover:text-slate-200'}",
        ),
        A(
            Svg(
                Path(d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"),
                cls="w-5 h-5", fill="none", stroke="currentColor", viewBox="0 0 24 24",
                stroke_width="2", stroke_linecap="round", stroke_linejoin="round",
            ),
            Span("People", cls="text-[10px]"),
            href="/?section=confirmed&view=browse",
            cls=f"flex flex-col items-center justify-center gap-0.5 min-h-[44px] min-w-[44px] "
                f"{'text-emerald-400' if section == 'confirmed' else 'text-slate-400 hover:text-slate-200'}",
        ),
        A(
            Svg(
                Path(d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"),
                cls="w-5 h-5", fill="none", stroke="currentColor", viewBox="0 0 24 24",
                stroke_width="2", stroke_linecap="round", stroke_linejoin="round",
            ),
            Span("Matches", cls="text-[10px]"),
            href="/?section=to_review&view=focus",
            cls=f"flex flex-col items-center justify-center gap-0.5 min-h-[44px] min-w-[44px] "
                f"{'text-amber-400' if section == 'to_review' else 'text-slate-400 hover:text-slate-200'}",
        ),
        A(
            Svg(
                Path(d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"),
                cls="w-5 h-5", fill="none", stroke="currentColor", viewBox="0 0 24 24",
                stroke_width="2", stroke_linecap="round", stroke_linejoin="round",
            ),
            Span("Search", cls="text-[10px]"),
            href="/?section=confirmed&view=browse",
            cls="flex flex-col items-center justify-center gap-0.5 min-h-[44px] min-w-[44px] text-slate-400 hover:text-slate-200",
            onclick="toggleSidebar(); setTimeout(function() { var s = document.querySelector('#sidebar input[type=search]'); if (s) s.focus(); }, 300); return false;",
        ),
        cls="fixed bottom-0 left-0 right-0 bg-slate-800 border-t border-slate-700 flex items-center justify-around py-1 z-40 lg:hidden",
        id="mobile-tabs",
    )

    return Title("Rhodesli Identity System"), style, Div(
        # Toast container for notifications
        toast_container(),
        # Mobile header
        mobile_header,
        # Sidebar overlay (mobile backdrop)
        sidebar_overlay,
        # Sidebar (fixed)
        sidebar(counts, section, user=user),
        # Main content (offset for sidebar, bottom padding for mobile tabs)
        Main(
            # First-time welcome banner (non-blocking, dismissible)
            _welcome_banner() if not user else None,
            # Admin dashboard banner (only for admins)
            _admin_dashboard_banner(counts, section) if user_is_admin else None,
            Div(
                main_content,
                cls="max-w-6xl mx-auto px-4 sm:px-8 py-6 pb-20 lg:pb-6"
            ),
            cls="main-content min-h-screen overflow-x-hidden"
        ),
        # Mobile bottom tabs
        mobile_tabs,
        # Photo modal (unified lightbox for all photo viewing)
        photo_modal(),
        # Side-by-side comparison modal for merge evaluation
        compare_modal(),
        # Login modal (shown when unauthenticated user triggers protected action)
        login_modal(),
        # Guest-or-login modal container (swapped in by annotation submit)
        Div(id="guest-or-login-modal"),
        # Styled confirmation modal (replaces native browser confirm())
        confirm_modal(),
        sidebar_script,
        # Client-side instant name filter with fuzzy matching (FE-030/FE-031/FE-033)
        Script("""
            (function() {
                // Levenshtein edit distance for fuzzy name matching
                function levenshtein(a, b) {
                    if (a.length < b.length) return levenshtein(b, a);
                    if (b.length === 0) return a.length;
                    var prev = [];
                    for (var j = 0; j <= b.length; j++) prev[j] = j;
                    for (var i = 1; i <= a.length; i++) {
                        var curr = [i];
                        for (var j = 1; j <= b.length; j++) {
                            var cost = a[i-1] === b[j-1] ? 0 : 1;
                            curr[j] = Math.min(curr[j-1] + 1, prev[j] + 1, prev[j-1] + cost);
                        }
                        prev = curr;
                    }
                    return prev[b.length];
                }
                // Fuzzy match: exact substring OR Levenshtein distance <= threshold per word
                function fuzzyMatch(query, name) {
                    if (!query) return true;
                    if (name.indexOf(query) !== -1) return true;
                    var words = name.split(/\\s+/);
                    var maxDist = query.length <= 8 ? 2 : 3;
                    for (var w = 0; w < words.length; w++) {
                        if (levenshtein(query, words[w]) <= maxDist) return true;
                    }
                    return false;
                }
                var filterTimer = null;
                function sidebarFilterCards(query) {
                    // Filter both standalone cards and wrapper divs (Needs Help has card+hint wrappers)
                    var cards = document.querySelectorAll('.identity-card, .identity-card-wrapper');
                    var q = (query || '').toLowerCase().trim();
                    for (var i = 0; i < cards.length; i++) {
                        var name = cards[i].getAttribute('data-name') || '';
                        if (fuzzyMatch(q, name)) {
                            cards[i].style.display = '';
                        } else {
                            cards[i].style.display = 'none';
                        }
                    }
                }
                var input = document.getElementById('sidebar-search-input');
                if (input) {
                    input.addEventListener('input', function() {
                        var val = this.value;
                        clearTimeout(filterTimer);
                        filterTimer = setTimeout(function() {
                            sidebarFilterCards(val);
                        }, 150);
                    });
                }
                // Expose for testing
                window.sidebarFilterCards = sidebarFilterCards;
            })();
        """),
        # Hash-based scroll + highlight for search result navigation
        Script("""
            (function() {
                if (window.location.hash) {
                    var target = document.querySelector(window.location.hash);
                    if (target) {
                        target.scrollIntoView({behavior: 'smooth', block: 'center'});
                        target.classList.add('ring-2', 'ring-blue-400');
                        setTimeout(function() {
                            target.classList.remove('ring-2', 'ring-blue-400');
                        }, 2000);
                    }
                }
            })();
        """),
        # Global share utility functions (used by share buttons on all pages)
        Script("""
            function _sharePhotoUrl(url) {
                // Always copy to clipboard first (desktop-friendly).
                // On mobile, also offer native share sheet after copying.
                _copyAndToast(url);
                var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                if (isMobile && navigator.share) {
                    navigator.share({ title: 'Rhodesli Photo', url: url }).catch(function() {});
                }
            }
            function _copyAndToast(url) {
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(url).then(function() {
                        _showShareToast('Link copied!');
                    }).catch(function() { _showShareToast('Could not copy link'); });
                } else {
                    var input = document.createElement('input');
                    input.value = url;
                    document.body.appendChild(input);
                    input.select();
                    document.execCommand('copy');
                    document.body.removeChild(input);
                    _showShareToast('Link copied!');
                }
            }
            function _showShareToast(message) {
                var existing = document.getElementById('share-toast');
                if (existing) existing.remove();
                var toast = document.createElement('div');
                toast.id = 'share-toast';
                toast.textContent = message;
                toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#334155;color:#e2e8f0;padding:10px 20px;border-radius:8px;font-size:14px;z-index:9999;transition:opacity 0.3s;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
                document.body.appendChild(toast);
                setTimeout(function() { toast.style.opacity = '0'; }, 2000);
                setTimeout(function() { toast.remove(); }, 2500);
            }
        """),
        # Global event delegation for lightbox/photo navigation (BUG-001 fix).
        # ONE listener on document handles all nav clicks and keyboard events.
        # This never needs rebinding because it's on document, not swapped DOM.
        Script("""
            // --- Global event delegation for photo/lightbox navigation ---
            // Click delegation: dispatch based on data-action attribute
            document.addEventListener('click', function(e) {
                var btn = e.target.closest('[data-action]');
                if (!btn) return;
                var action = btn.getAttribute('data-action');

                // Share photo (used across all surfaces)
                if (action === 'share-photo') {
                    var url = btn.getAttribute('data-share-url') || '';
                    if (url && !url.startsWith('http')) {
                        url = window.location.origin + url;
                    }
                    _sharePhotoUrl(url || window.location.href);
                    return;
                }

                // Photo modal prev/next (Photos grid browsing)
                if (action === 'photo-nav-prev' || action === 'photo-nav-next') {
                    e.preventDefault();
                    var idx = parseInt(btn.getAttribute('data-nav-idx'), 10);
                    if (typeof photoNavTo === 'function' && !isNaN(idx)) {
                        photoNavTo(idx);
                    } else {
                        var url = btn.getAttribute('data-nav-url');
                        if (url) htmx.ajax('GET', url, {target:'#photo-modal-content', swap:'innerHTML'});
                    }
                    return;
                }

                // Identity photo lightbox prev/next — HTMX handles these via
                // hx-get. data-action is for keyboard delegation below.
            });

            // Keyboard delegation: one global listener, reads DOM for current state.
            // Priority: modals first, then suppress in text fields, then mode shortcuts.

            // Undo stack: stores last 10 actions for Z-key undo
            if (!window._undoStack) window._undoStack = [];

            // Capture undo data before HTMX actions fire
            document.addEventListener('click', function(e) {
                var btn = e.target.closest('[data-undo-type]');
                if (btn) {
                    var undoInfo = {
                        type: btn.getAttribute('data-undo-type'),
                        url: btn.getAttribute('data-undo-url') || '',
                        identity: btn.getAttribute('data-undo-identity') || '',
                        ts: Date.now()
                    };
                    window._undoStack.push(undoInfo);
                    if (window._undoStack.length > 10) window._undoStack.shift();
                }
            }, true);

            document.addEventListener('keydown', function(e) {
                // --- Modal navigation (highest priority) ---
                // Unified photo modal (handles both photo grid browsing and identity photo browsing)
                var photoModal = document.getElementById('photo-modal');
                if (photoModal && !photoModal.classList.contains('hidden')) {
                    if (e.key === 'ArrowLeft') {
                        // Try photo grid nav first, then identity lightbox nav
                        var prev = document.querySelector('[data-action="photo-nav-prev"]');
                        if (prev) { prev.click(); e.preventDefault(); }
                        else {
                            var lbPrev = document.querySelector('[data-action="lightbox-prev"]');
                            if (lbPrev) { lbPrev.click(); e.preventDefault(); }
                            else if (typeof photoNavTo === 'function' && window._photoNavIdx > 0) {
                                photoNavTo(window._photoNavIdx - 1); e.preventDefault();
                            }
                        }
                    } else if (e.key === 'ArrowRight') {
                        var next = document.querySelector('[data-action="photo-nav-next"]');
                        if (next) { next.click(); e.preventDefault(); }
                        else {
                            var lbNext = document.querySelector('[data-action="lightbox-next"]');
                            if (lbNext) { lbNext.click(); e.preventDefault(); }
                            else if (typeof photoNavTo === 'function' && window._photoNavIdx < (window._photoNavIds||[]).length - 1) {
                                photoNavTo(window._photoNavIdx + 1); e.preventDefault();
                            }
                        }
                    } else if (e.key === 'Escape') {
                        photoModal.classList.add('hidden'); e.preventDefault();
                    }
                    return;
                }

                // --- Suppress shortcuts when typing in INPUT or TEXTAREA ---
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

                // --- Ignore when modifier keys are held (Cmd+R, Ctrl+S, etc.) ---
                if (e.metaKey || e.ctrlKey || e.altKey) return;

                // --- Z = Undo last action (works in all focus modes) ---
                if (e.key === 'z' || e.key === 'Z') {
                    e.preventDefault();
                    if (!window._undoStack || window._undoStack.length === 0) return;
                    var last = window._undoStack.pop();
                    if (last.type === 'skip') {
                        // Skip undo: navigate back to the skipped identity
                        window.location.href = '/?section=skipped&view=focus&current=' + last.identity;
                    } else if (last.url) {
                        // Merge/reject undo: POST to undo endpoint, then reload focus on that identity
                        fetch(last.url, {method: 'POST', headers: {'HX-Request': 'true'}}).then(function() {
                            window.location.href = '/?section=skipped&view=focus&current=' + last.identity;
                        });
                    }
                    return;
                }

                // --- Match mode shortcuts: Y=Same, N=Different, S=Skip ---
                var matchBtn = null;
                if (e.key === 'y' || e.key === 'Y') matchBtn = document.getElementById('match-btn-same');
                else if (e.key === 'n' || e.key === 'N') matchBtn = document.getElementById('match-btn-diff');
                else if (e.key === 's' || e.key === 'S') matchBtn = document.getElementById('match-btn-skip');
                if (matchBtn) { e.preventDefault(); matchBtn.click(); return; }

                // --- Focus mode shortcuts ---
                // Skipped focus mode: Y=Same Person, N=Not Same, Enter=I Know Them, S=Skip, Z=Undo
                // Inbox focus mode: C=Confirm, S=Skip, R=Reject, F=Find Similar
                var focusBtn = null;
                var isSkippedFocus = document.querySelector('[data-focus-mode="skipped"]');
                if (isSkippedFocus) {
                    if (e.key === 'y' || e.key === 'Y') focusBtn = document.getElementById('focus-btn-confirm');
                    else if (e.key === 'n' || e.key === 'N') focusBtn = document.getElementById('focus-btn-reject');
                    else if (e.key === 'Enter') focusBtn = document.getElementById('focus-btn-name');
                    else if (e.key === 's' || e.key === 'S') focusBtn = document.getElementById('focus-btn-skip');
                } else {
                    if (e.key === 'c' || e.key === 'C') focusBtn = document.getElementById('focus-btn-confirm');
                    else if (e.key === 's' || e.key === 'S') focusBtn = document.getElementById('focus-btn-skip');
                    else if (e.key === 'r' || e.key === 'R') focusBtn = document.getElementById('focus-btn-reject');
                    else if (e.key === 'f' || e.key === 'F') focusBtn = document.getElementById('focus-btn-similar');
                }
                if (focusBtn) { e.preventDefault(); focusBtn.click(); return; }
            });
        """),
        cls="h-full"
    )


@rt("/confirm/{identity_id}")
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
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
            get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
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
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
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
            get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
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

    # Get image dimensions for face overlay positioning
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


@rt("/api/photo/{photo_id}/collection")
def post(photo_id: str, sess, collection: str = ""):
    """
    Update a photo's collection (classification) label.

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = load_photo_registry()
    photo_path = photo_reg.get_photo_path(photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    photo_reg.set_collection(photo_id, collection.strip())
    save_photo_registry(photo_reg)
    global _photo_cache
    _photo_cache = None
    return Div(
        Span(f"Collection updated to: {collection.strip() or '(none)'}",
             cls="text-sm text-emerald-400"),
        id=f"collection-status-{photo_id}",
    )


@rt("/api/photo/{photo_id}/source")
def post(photo_id: str, sess, source: str = ""):
    """
    Update a photo's source (provenance/origin) label.

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = load_photo_registry()
    photo_path = photo_reg.get_photo_path(photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    photo_reg.set_source(photo_id, source.strip())
    save_photo_registry(photo_reg)
    global _photo_cache
    _photo_cache = None
    return Div(
        Span(f"Source updated to: {source.strip() or '(none)'}",
             cls="text-sm text-emerald-400"),
        id=f"source-status-{photo_id}",
    )


@rt("/api/photo/{photo_id}/source-url")
def post(photo_id: str, sess, source_url: str = ""):
    """
    Update a photo's source URL (citation link).

    Admin-only. Updates photo_index.json and invalidates caches.
    """
    admin_err = _check_admin(sess)
    if admin_err:
        return admin_err
    photo_reg = load_photo_registry()
    photo_path = photo_reg.get_photo_path(photo_id)
    if not photo_path:
        return Response("Photo not found", status_code=404)
    photo_reg.set_source_url(photo_id, source_url.strip())
    save_photo_registry(photo_reg)
    global _photo_cache
    _photo_cache = None
    if source_url.strip():
        return Div(
            Span("Source URL: ", cls="text-slate-500 text-sm"),
            A(source_url.strip(), href=source_url.strip(), target="_blank",
              rel="noopener", cls="text-indigo-400 hover:text-indigo-300 underline text-sm"),
            id=f"source-url-status-{photo_id}",
        )
    return Div(
        Span("Source URL cleared", cls="text-sm text-emerald-400"),
        id=f"source-url-status-{photo_id}",
    )


def photo_view_content(
    photo_id: str,
    selected_face_id: str = None,
    is_partial: bool = False,
    prev_id: str = None,
    next_id: str = None,
    nav_idx: int = -1,
    nav_total: int = 0,
    identity_id: str = None,
    is_admin: bool = False,
    from_compare: bool = False,
) -> tuple:
    """
    Build the photo view content with face overlays.

    Optional navigation context for prev/next arrows:
    - prev_id/next_id: Photo IDs for adjacent photos
    - nav_idx/nav_total: Position counter for "X of Y" display
    - identity_id: Compute navigation from identity's unique photos

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

    # Get image dimensions for face overlay positioning
    # This handles inbox uploads which are stored outside raw_photos/
    width, height = get_photo_dimensions(photo["filename"])

    # If dimensions aren't available (e.g., R2 mode without cached dimensions),
    # we can still show the photo - just without face overlays
    has_dimensions = width > 0 and height > 0

    registry = load_registry()

    # Identity-based navigation: when identity_id is provided and no explicit
    # prev/next, compute navigation from the identity's unique photo list.
    if identity_id and not prev_id and not next_id:
        try:
            identity_nav = registry.get_identity(identity_id)
            all_faces = identity_nav.get("anchor_ids", []) + identity_nav.get("candidate_ids", [])
            # Build ordered list of unique photo IDs from identity's faces
            seen_pids = []
            for f in all_faces:
                fid = f if isinstance(f, str) else f.get("face_id", "")
                pid = get_photo_id_for_face(fid)
                if pid and pid not in seen_pids:
                    seen_pids.append(pid)
            if photo_id in seen_pids:
                idx = seen_pids.index(photo_id)
                if idx > 0:
                    prev_id = seen_pids[idx - 1]
                if idx < len(seen_pids) - 1:
                    next_id = seen_pids[idx + 1]
                nav_idx = idx
                nav_total = len(seen_pids)
        except KeyError:
            pass

    # Build face overlays with CSS percentages for responsive scaling
    # Only if we have dimensions (needed for percentage calculations)
    from urllib.parse import quote as _url_quote
    face_overlays = []
    if has_dimensions:
        for face_data in photo["faces"]:
            face_id = face_data["face_id"]
            face_id_encoded = _url_quote(face_id, safe="")
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
                nav_section = _section_for_state(state)
            else:
                state = None
                nav_section = "to_review"

            # Determine if this face is selected
            is_selected = face_id == selected_face_id

            # Build the overlay div with status-based colors
            overlay_classes = "face-overlay absolute cursor-pointer transition-all"
            status_badge = None
            if is_selected:
                overlay_classes += " border-2 border-amber-500 bg-amber-500/20"
            elif state == "CONFIRMED":
                overlay_classes += " border-2 border-emerald-500 bg-emerald-500/10 hover:bg-emerald-500/20 hover:border-emerald-300"
                status_badge = Span("\u2713", cls="absolute -top-1.5 -right-1.5 w-4 h-4 bg-emerald-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center pointer-events-none")
            elif state == "SKIPPED":
                overlay_classes += " border-2 border-amber-500 bg-amber-500/10 hover:bg-amber-500/20 hover:border-amber-300"
                status_badge = Span("\u23ed", cls="absolute -top-1.5 -right-1.5 w-4 h-4 bg-amber-500 text-white text-[8px] rounded-full flex items-center justify-center pointer-events-none")
            elif state in ("REJECTED", "CONTESTED"):
                overlay_classes += " border-2 border-red-500 bg-red-500/10 hover:bg-red-500/20 hover:border-red-300"
                status_badge = Span("\u2717", cls="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center pointer-events-none")
            elif state == "PROPOSED":
                overlay_classes += " border-2 border-indigo-400 bg-indigo-400/10 hover:bg-indigo-400/20 hover:border-indigo-300"
            else:
                # INBOX or unassigned — dashed border signals "needs attention"
                overlay_classes += " border-2 border-dashed border-slate-400 bg-slate-400/5 hover:bg-slate-400/15 hover:border-white"

            # Tag dropdown for this face (hidden by default)
            tag_dropdown_id = f"tag-dropdown-{face_id.replace(':', '-').replace(' ', '_')}"
            tag_results_id = f"tag-results-{face_id.replace(':', '-').replace(' ', '_')}"

            # Click handler: confirmed faces navigate to identity card;
            # all other faces open the tag dropdown.
            if state == "CONFIRMED" and identity_id:
                tag_script = (
                    f"on click halt the event's bubbling "
                    f"then add .hidden to #photo-modal "
                    f"then go to url '/?section={nav_section}&view=browse#identity-{identity_id}'"
                )
            else:
                tag_script = (
                    f"on click halt the event's bubbling "
                    f"then set dropdowns to <div.tag-dropdown/> in closest .photo-viewer "
                    f"then for dd in dropdowns "
                    f"  if dd.id is not '{tag_dropdown_id}' add .hidden to dd end "
                    f"end "
                    f"then toggle .hidden on #{tag_dropdown_id} "
                    f"then set el to first <input/> in #{tag_dropdown_id} "
                    f"then if el call el.focus()"
                )

            tag_placeholder = "Type name to tag..." if is_admin else "Who is this person?"
            tag_dropdown = Div(
                # Search input
                Input(
                    type="text",
                    placeholder=tag_placeholder,
                    cls="w-full px-2 py-1.5 text-sm bg-slate-800 border border-slate-600 text-white rounded "
                        "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500",
                    hx_get=f"/api/face/tag-search?face_id={face_id_encoded}",
                    hx_trigger="keyup changed delay:300ms",
                    hx_target=f"#{tag_results_id}",
                    hx_include="this",
                    name="q",
                    autocomplete="off",
                ),
                # Results container
                Div(id=tag_results_id, cls="mt-1 max-h-48 overflow-y-auto"),
                # Bottom actions
                Div(
                    Button(
                        "Go to Face Card",
                        cls="text-xs text-indigo-400 hover:text-indigo-300",
                        **{"_": f"on click add .hidden to #photo-modal then go to url '/?section={nav_section}&view=browse#identity-{identity_id}'"} if identity_id else {},
                        type="button",
                    ) if identity_id else None,
                    Button(
                        "Close",
                        cls="text-xs text-slate-400 hover:text-slate-300 ml-auto",
                        **{"_": f"on click add .hidden to #{tag_dropdown_id}"},
                        type="button",
                    ),
                    cls="flex items-center justify-between mt-2 pt-1 border-t border-slate-700"
                ),
                id=tag_dropdown_id,
                cls="hidden tag-dropdown absolute top-full left-0 mt-1 w-56 sm:w-64 bg-slate-800 border border-slate-600 "
                    "rounded-lg shadow-xl p-2 z-20",
                **{"_": "on click halt the event's bubbling"},  # Prevent clicks inside from closing
            )

            # Build inline quick-action buttons for admin users
            # Only for actionable states (INBOX, PROPOSED, SKIPPED)
            quick_actions = None
            if is_admin and identity_id and state in ("INBOX", "PROPOSED", "SKIPPED"):
                action_btns = []
                # Confirm button
                action_btns.append(Button(
                    "\u2713",
                    cls="w-6 h-6 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs "
                        "flex items-center justify-center",
                    hx_post=f"/api/face/quick-action?identity_id={identity_id}&action=confirm&photo_id={photo_id}",
                    hx_target="#photo-modal-content",
                    hx_swap="innerHTML",
                    title="Confirm",
                    type="button",
                    **{"_": "on click halt the event's bubbling"},
                ))
                # Skip button (not for SKIPPED state)
                if state in ("INBOX", "PROPOSED"):
                    action_btns.append(Button(
                        "\u23f8",
                        cls="w-6 h-6 rounded-full bg-amber-500 hover:bg-amber-400 text-white text-xs "
                            "flex items-center justify-center",
                        hx_post=f"/api/face/quick-action?identity_id={identity_id}&action=skip&photo_id={photo_id}",
                        hx_target="#photo-modal-content",
                        hx_swap="innerHTML",
                        title="Skip",
                        type="button",
                        **{"_": "on click halt the event's bubbling"},
                    ))
                # Reject button
                action_btns.append(Button(
                    "\u2717",
                    cls="w-6 h-6 rounded-full bg-red-600 hover:bg-red-500 text-white text-xs "
                        "flex items-center justify-center",
                    hx_post=f"/api/face/quick-action?identity_id={identity_id}&action=reject&photo_id={photo_id}",
                    hx_target="#photo-modal-content",
                    hx_swap="innerHTML",
                    title="Reject",
                    type="button",
                    **{"_": "on click halt the event's bubbling"},
                ))
                quick_actions = Div(
                    *action_btns,
                    cls="quick-actions absolute bottom-1 left-1/2 -translate-x-1/2 flex gap-1 "
                        "opacity-0 group-hover:opacity-100 transition-opacity z-10",
                )

            # Name label: always visible for confirmed, hover for others
            if state == "CONFIRMED":
                # Always-visible name label below the face box
                name_label = Span(
                    display_name,
                    cls="absolute -bottom-5 left-1/2 -translate-x-1/2 bg-black/70 text-white text-[11px] px-1.5 py-0.5 rounded whitespace-nowrap pointer-events-none max-w-[150%] truncate"
                )
                hover_tooltip = None
            else:
                # Hover tooltip for non-confirmed
                name_label = None
                hover_tooltip = Span(
                    display_name,
                    cls="absolute -top-8 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none"
                )

            overlay = Div(
                hover_tooltip,
                name_label,
                status_badge,
                quick_actions,
                tag_dropdown,
                cls=f"{overlay_classes} group",
                style=f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;",
                title=display_name,
                data_face_id=face_id,
                data_identity_id=identity_id or "",
                **{"_": tag_script},
            )
            face_overlays.append(overlay)

    # Build navigation buttons (for Photos section browsing)
    nav_prev = None
    nav_next = None
    nav_counter = None
    nav_keyboard_script = None

    if prev_id or next_id or (nav_total > 0):
        # Build navigation buttons with data-action attributes for event delegation.
        # The global delegation handler (in the page layout) reads data-action,
        # data-nav-idx, and data-nav-url to dispatch navigation. This pattern
        # survives HTMX content swaps because the listener is on document, not
        # on the swapped DOM nodes.
        # Build URL suffix for identity context continuity
        _id_suffix = f"&identity_id={identity_id}" if identity_id else ""
        if prev_id:
            prev_url = f"/photo/{prev_id}/partial?nav_idx={nav_idx - 1}&nav_total={nav_total}{_id_suffix}"
            nav_prev = Button(
                Span("\u25C0", cls="text-xl"),
                cls="absolute left-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white "
                    "w-12 h-12 rounded-full flex items-center justify-center transition-colors z-10",
                type="button",
                title="Previous photo",
                id="photo-nav-prev",
                data_action="photo-nav-prev",
                data_nav_idx=str(nav_idx - 1),
                data_nav_url=prev_url,
            )
        if next_id:
            next_url = f"/photo/{next_id}/partial?nav_idx={nav_idx + 1}&nav_total={nav_total}{_id_suffix}"
            nav_next = Button(
                Span("\u25B6", cls="text-xl"),
                cls="absolute right-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white "
                    "w-12 h-12 rounded-full flex items-center justify-center transition-colors z-10",
                type="button",
                title="Next photo",
                id="photo-nav-next",
                data_action="photo-nav-next",
                data_nav_idx=str(nav_idx + 1),
                data_nav_url=next_url,
            )
        # Boundary indicators for first/last photo
        if not prev_id and nav_total > 1:
            nav_prev = Div(
                Span("\u25C0", cls="text-xl opacity-30"),
                cls="absolute left-2 top-1/2 -translate-y-1/2 bg-black/30 text-white/30 "
                    "w-12 h-12 rounded-full flex items-center justify-center z-10 cursor-default",
                title="First photo",
            )
        if not next_id and nav_total > 1:
            nav_next = Div(
                Span("\u25B6", cls="text-xl opacity-30"),
                cls="absolute right-2 top-1/2 -translate-y-1/2 bg-black/30 text-white/30 "
                    "w-12 h-12 rounded-full flex items-center justify-center z-10 cursor-default",
                title="Last photo",
            )
        if nav_idx >= 0 and nav_total > 0:
            nav_counter = Span(
                f"{nav_idx + 1} / {nav_total}",
                cls="text-slate-400 text-sm ml-auto"
            )
        # No per-swap keyboard script needed — the global event delegation
        # handler in the page layout handles ArrowLeft/ArrowRight/Escape.

    # "Back to Compare" button when opened from compare modal
    back_to_compare = None
    if from_compare:
        back_to_compare = Div(
            Button(
                "\u2190 Back to Compare",
                cls="text-sm text-indigo-400 hover:text-indigo-300 px-3 py-1.5 rounded border border-indigo-500/30 hover:border-indigo-400/50 transition-colors",
                **{"_": "on click add .hidden to #photo-modal then remove .hidden from #compare-modal"},
                type="button",
            ),
            cls="mb-3"
        )

    # Main content
    content = Div(
        back_to_compare,
        # Photo container with overlays and nav arrows
        Div(
            Img(
                src=photo_url(photo["filename"]),
                alt=photo["filename"],
                cls="max-w-full h-auto"
            ),
            *face_overlays,
            # Face overlay legend
            Div(
                Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-emerald-500 mr-0.5"),
                Span("Identified", cls="text-slate-400 mr-2"),
                Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-amber-500 mr-0.5"),
                Span("Help Identify", cls="text-slate-400 mr-2"),
                Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-dashed border-slate-400 mr-0.5"),
                Span("New", cls="text-slate-400"),
                cls="absolute bottom-1 right-1 bg-black/60 rounded px-2 py-0.5 flex items-center gap-0.5 text-[10px]",
            ) if face_overlays else None,
            nav_prev,
            nav_next,
            cls="relative inline-block max-w-full"
        ),
        # Photo info
        Div(
            Div(
                P(
                    photo["filename"],
                    cls="text-slate-300 text-sm font-data font-medium"
                ),
                nav_counter,
                Span(
                    share_button(photo_id, style="link", label="Share"),
                    A(
                        "Open",
                        href=f"/photo/{photo_id}",
                        cls="text-xs text-indigo-400 hover:text-indigo-300 underline",
                        target="_blank",
                        rel="noopener",
                    ),
                    cls="ml-auto flex items-center gap-3",
                ),
                cls="flex items-center gap-2"
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
            # Collection / Source / Source URL display
            Div(
                P(
                    Span("Collection: ", cls="text-slate-500"),
                    Span(photo.get("collection", ""), cls="text-slate-300"),
                    cls="text-xs"
                ) if photo.get("collection") else None,
                P(
                    Span("Source: ", cls="text-slate-500"),
                    Span(photo.get("source", ""), cls="text-slate-300"),
                    cls="text-xs"
                ) if photo.get("source") else None,
                P(
                    Span("Source URL: ", cls="text-slate-500"),
                    A(photo.get("source_url", ""), href=photo.get("source_url", ""),
                      target="_blank", rel="noopener",
                      cls="text-indigo-400 hover:text-indigo-300 underline"),
                    cls="text-xs"
                ) if photo.get("source_url") else None,
                cls="mt-1 space-y-0.5"
            ) if photo.get("collection") or photo.get("source") or photo.get("source_url") else None,
            # Stored photo metadata (BE-012)
            _photo_metadata_display(photo),
            # Photo annotations display + form (AN-002–AN-006)
            _photo_annotations_section(photo_id, is_admin),
            cls="mt-4"
        ),
        nav_keyboard_script,
        cls="photo-viewer p-2 sm:p-4 overflow-x-hidden"
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


def public_person_page(
    person_id: str,
    view: str = "faces",
    user=None,
    is_admin: bool = False,
) -> tuple:
    """
    Build the public shareable person page.

    Shows all photos of a specific identified person — the page you share
    when you want to say "Look at all these photos of Aunt Selma!"
    No authentication required.
    """
    registry = load_registry()
    try:
        identity = registry.get_identity(person_id)
    except KeyError:
        identity = None

    # Check for merged identities
    if identity and identity.get("merged_into"):
        identity = None

    if not identity:
        style_404 = Style("html, body { margin: 0; } body { background-color: #0f172a; }")
        return (
            Title("Person Not Found - Rhodesli"),
            style_404,
            Main(
                Nav(
                    Div(
                        A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                        cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16"
                    ),
                    cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800"
                ),
                Div(
                    Div(
                        Span("404", cls="text-6xl font-bold text-slate-700 block mb-4"),
                        H1("Person not found", cls="text-2xl font-serif font-bold text-white mb-3"),
                        P("This person hasn't been identified in our archive yet.", cls="text-slate-400 mb-8"),
                        A("Explore the Archive", href="/?section=photos",
                          cls="inline-block px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors"),
                        cls="text-center"
                    ),
                    cls="flex items-center justify-center min-h-[60vh]"
                ),
                cls="min-h-screen bg-slate-900"
            ),
        )

    raw_name = ensure_utf8_display(identity.get("name"))
    display_name = raw_name or f"Person {person_id[:8]}"
    state = identity.get("state", "INBOX")
    is_confirmed = state == "CONFIRMED" and not display_name.startswith("Unidentified")
    from urllib.parse import quote as _url_quote

    # Get all face IDs for this person
    anchor_ids = identity.get("anchor_ids", [])
    candidate_ids = identity.get("candidate_ids", [])
    all_face_ids = anchor_ids + candidate_ids
    face_id_strings = [f if isinstance(f, str) else f.get("face_id", "") for f in all_face_ids]

    # Get photos where this person appears
    photo_reg = load_photo_registry()
    photo_ids = photo_reg.get_photos_for_faces(face_id_strings)
    crop_files = get_crop_files()

    # Get best face crop for avatar
    best_face_id = get_best_face_id(all_face_ids)
    avatar_url = resolve_face_image_url(best_face_id, crop_files) if best_face_id and crop_files else None

    # Get collections this person appears in
    collections = set()
    for pid in photo_ids:
        pm = get_photo_metadata(pid)
        if pm and pm.get("collection"):
            collections.add(pm["collection"])

    # --- Build face gallery items ---
    face_gallery_items = []
    for face_id_entry in all_face_ids:
        fid = face_id_entry if isinstance(face_id_entry, str) else face_id_entry.get("face_id", "")
        crop_url = resolve_face_image_url(fid, crop_files) if crop_files else None
        if not crop_url:
            continue
        # Find the photo for this face
        face_photo_id = get_photo_id_for_face(fid)
        face_photo = get_photo_metadata(face_photo_id) if face_photo_id else None
        source_label = ""
        if face_photo:
            source_label = face_photo.get("collection", "") or face_photo.get("source", "") or ""

        face_gallery_items.append(
            A(
                Img(
                    src=crop_url,
                    alt=f"{display_name}",
                    cls="w-28 h-28 sm:w-32 sm:h-32 rounded-lg object-cover border-2 border-slate-700 hover:border-emerald-500/50 transition-colors",
                    onerror="this.style.display='none'",
                ),
                P(source_label, cls="text-[10px] text-slate-500 mt-1 text-center truncate max-w-[120px]") if source_label else None,
                href=f"/photo/{face_photo_id}" if face_photo_id else "#",
                cls="flex flex-col items-center group",
                title=f"View photo of {display_name}",
            )
        )

    # --- Build photo gallery items ---
    photo_gallery_items = []
    for pid in sorted(photo_ids):
        pm = get_photo_metadata(pid)
        if not pm:
            continue
        filename = pm["filename"]
        collection_label = pm.get("collection", "") or ""
        photo_gallery_items.append(
            A(
                Div(
                    Img(
                        src=photo_url(filename),
                        alt=f"Photo featuring {display_name}",
                        cls="w-full h-48 sm:h-56 object-cover rounded-lg",
                        loading="lazy",
                    ),
                    cls="relative overflow-hidden rounded-lg",
                ),
                P(collection_label, cls="text-[10px] text-slate-500 mt-1 text-center truncate") if collection_label else None,
                href=f"/photo/{pid}",
                cls="flex flex-col group",
                title=f"View photo of {display_name}",
            )
        )

    # --- Build "Appears with" section ---
    appears_with = []
    for pid in photo_ids:
        pm = get_photo_metadata(pid)
        if not pm:
            continue
        for face_data in pm.get("faces", []):
            other_fid = face_data.get("face_id", "")
            if other_fid in face_id_strings:
                continue  # skip self
            other_identity = get_identity_for_face(registry, other_fid)
            if not other_identity:
                continue
            other_id = other_identity["identity_id"]
            other_state = other_identity.get("state", "")
            other_name = ensure_utf8_display(other_identity.get("name", ""))
            if other_state != "CONFIRMED" or other_name.startswith("Unidentified"):
                continue
            if other_id == person_id:
                continue
            # Avoid duplicates
            if any(a["id"] == other_id for a in appears_with):
                continue
            other_best_face = get_best_face_id(
                other_identity.get("anchor_ids", []) + other_identity.get("candidate_ids", [])
            )
            other_crop = resolve_face_image_url(other_best_face, crop_files) if other_best_face and crop_files else None
            appears_with.append({
                "id": other_id,
                "name": other_name,
                "crop_url": other_crop,
            })

    appears_with_section = None
    if appears_with:
        companion_cards = []
        shown = appears_with[:8]
        for companion in shown:
            crop_el = Img(
                src=companion["crop_url"],
                alt=companion["name"],
                cls="w-12 h-12 rounded-full object-cover border-2 border-slate-700",
                onerror="this.style.display='none'",
            ) if companion["crop_url"] else Div(
                Span("?", cls="text-lg text-slate-500"),
                cls="w-12 h-12 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center",
            )
            companion_cards.append(
                A(
                    crop_el,
                    Span(companion["name"], cls="text-xs text-slate-400 mt-1 text-center truncate max-w-[80px]"),
                    href=f"/person/{companion['id']}",
                    cls="flex flex-col items-center gap-1 hover:opacity-80 transition-opacity",
                    title=f"View {companion['name']}",
                )
            )
        if len(appears_with) > 8:
            companion_cards.append(
                Span(f"+{len(appears_with) - 8} more", cls="text-xs text-slate-500 self-center ml-2")
            )
        appears_with_section = Div(
            H3("Often appears with", cls="text-lg font-serif font-semibold text-slate-300 mb-4"),
            Div(*companion_cards, cls="flex flex-wrap gap-4 items-start"),
            cls="mt-10 pt-8 border-t border-slate-800",
        )

    # --- Open Graph meta tags ---
    og_title = f"{display_name} — Rhodesli Heritage Archive"
    photo_count = len(photo_ids)
    collection_count = len(collections)
    if photo_count > 0:
        og_description = f"Appears in {photo_count} {'photo' if photo_count == 1 else 'photos'} across {collection_count} {'collection' if collection_count == 1 else 'collections'}. Help identify more photos of {display_name}."
    else:
        og_description = f"{display_name} in the Rhodesli Heritage Archive. Explore photographs from the Jewish community of Rhodes."

    og_image_url = avatar_url or ""
    if og_image_url and not og_image_url.startswith("http"):
        og_image_url = f"{SITE_URL}{og_image_url}"
    og_page_url = f"{SITE_URL}/person/{person_id}"

    og_meta_tags = (
        Meta(property="og:title", content=og_title),
        Meta(property="og:description", content=og_description),
        Meta(property="og:image", content=og_image_url),
        Meta(property="og:url", content=og_page_url),
        Meta(property="og:type", content="profile"),
        Meta(property="og:site_name", content="Rhodesli — Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary"),
        Meta(name="twitter:title", content=og_title),
        Meta(name="twitter:description", content=og_description),
        Meta(name="twitter:image", content=og_image_url),
        Meta(name="description", content=og_description),
    )

    # --- Navigation ---
    nav_links = [
        A("Photos", href="/photos", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
        A("People", href="/people", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
    ]
    if is_auth_enabled() and not user:
        nav_links.append(A("Sign In", href="/login", cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors"))

    # --- View toggle ---
    faces_active = view != "photos"
    toggle = Div(
        A(
            "Faces",
            href=f"/person/{person_id}?view=faces",
            cls="px-4 py-2 text-sm font-medium rounded-lg transition-colors " + (
                "bg-indigo-600 text-white" if faces_active else "text-slate-400 hover:text-white hover:bg-slate-700/50"
            ),
        ),
        A(
            "Photos",
            href=f"/person/{person_id}?view=photos",
            cls="px-4 py-2 text-sm font-medium rounded-lg transition-colors " + (
                "bg-indigo-600 text-white" if not faces_active else "text-slate-400 hover:text-white hover:bg-slate-700/50"
            ),
        ),
        cls="flex gap-1 bg-slate-800/50 p-1 rounded-xl",
    )

    # --- Gallery content ---
    gallery_items = face_gallery_items if faces_active else photo_gallery_items
    gallery_count = len(gallery_items)
    gallery_grid_cls = "grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3 sm:gap-4" if faces_active else "grid grid-cols-2 sm:grid-cols-3 gap-4"

    if gallery_items:
        gallery_content = Div(*gallery_items, cls=gallery_grid_cls)
    else:
        gallery_content = Div(
            P("No photos available yet.", cls="text-slate-500 text-center py-8"),
        )

    # --- Status badge ---
    if is_confirmed:
        badge = Span("Identified", cls="text-xs text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20")
    else:
        badge = Span("Under Review", cls="text-xs text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20")

    # --- Stats line ---
    stats_parts = []
    if photo_count > 0:
        stats_parts.append(f"Appears in {photo_count} {'photo' if photo_count == 1 else 'photos'}")
    if collection_count > 0:
        stats_parts.append(f"{collection_count} {'collection' if collection_count == 1 else 'collections'}")
    stats_line = " · ".join(stats_parts) if stats_parts else None

    # --- Page style ---
    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
    """)

    # --- Share button ---
    share_btn = Button(
        NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'),
        "Share",
        cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center",
        type="button",
        data_action="share-photo",
        data_share_url=og_page_url,
    )

    return (
        Title(f"{display_name} — Rhodesli Heritage Archive"),
        *og_meta_tags,
        page_style,
        Main(
            # Top navigation bar
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(
                        *nav_links,
                        A("Explore More Photos", href="/photos",
                          cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors ml-4"),
                        cls="hidden sm:flex items-center gap-6"
                    ),
                    cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16"
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50"
            ),

            # Hero section
            Section(
                Div(
                    # Avatar
                    Div(
                        Img(
                            src=avatar_url,
                            alt=display_name,
                            cls="w-32 h-32 rounded-full object-cover border-4 border-emerald-500/30 shadow-lg shadow-emerald-500/10",
                            onerror="this.style.display='none'",
                        ) if avatar_url else Div(
                            Span(display_name[0].upper() if display_name else "?", cls="text-4xl font-serif text-slate-400"),
                            cls="w-32 h-32 rounded-full bg-slate-800 border-4 border-slate-700 flex items-center justify-center",
                        ),
                        cls="flex justify-center mb-6",
                    ),
                    # Name + badge
                    Div(
                        H1(display_name, cls="text-3xl sm:text-4xl font-serif font-bold text-white mb-3"),
                        badge,
                        cls="text-center mb-3",
                    ),
                    # Stats line
                    P(stats_line, cls="text-slate-400 text-sm text-center mb-6") if stats_line else None,
                    # Action buttons
                    Div(
                        share_btn,
                        cls="flex justify-center gap-3 mb-8",
                    ),
                    cls="max-w-3xl mx-auto pt-12 pb-8 px-6",
                ),
                cls="border-b border-slate-800",
            ),

            # Gallery section
            Section(
                Div(
                    # Section header with toggle
                    Div(
                        H2(
                            f"{'Faces' if faces_active else 'Photos'} of {display_name}",
                            cls="text-xl font-serif font-semibold text-white",
                        ),
                        Div(
                            toggle,
                            Span(f"{gallery_count} {'face' if gallery_count == 1 else 'faces'}" if faces_active else f"{gallery_count} {'photo' if gallery_count == 1 else 'photos'}", cls="text-xs text-slate-500 ml-3 self-center"),
                            cls="flex items-center",
                        ),
                        cls="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6",
                    ),
                    gallery_content,

                    # Appears with section
                    appears_with_section if appears_with_section else None,

                    cls="max-w-5xl mx-auto px-6 py-10",
                ),
            ),

            # CTA section
            Section(
                Div(
                    H3(f"Do you have more photos of {display_name}?", cls="text-lg font-serif text-white mb-2"),
                    P("Upload your family photos to help us build a more complete picture.", cls="text-slate-400 text-sm mb-4"),
                    A("Upload Photos", href="/?section=upload",
                      cls="inline-block px-5 py-2.5 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded-lg transition-colors"),
                    cls="text-center",
                ),
                cls="py-12 border-t border-slate-800",
            ),

            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-xs text-slate-500 mb-1 font-serif"),
                    P("Preserving the memory of the Jewish community of Rhodes", cls="text-[10px] text-slate-600 italic"),
                    Div(
                        A("Photos", href="/photos", cls="text-xs text-slate-500 hover:text-slate-300"),
                        Span("·", cls="text-slate-700"),
                        A("People", href="/people", cls="text-xs text-slate-500 hover:text-slate-300"),
                        cls="flex items-center gap-2 mt-2"
                    ),
                    cls="max-w-5xl mx-auto px-6 flex flex-col items-center"
                ),
                cls="py-8 border-t border-slate-800",
            ),

            # Share JS (standalone page needs its own)
            Script("""
                function _sharePhotoUrl(url) {
                    _copyAndToast(url);
                    var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                    if (isMobile && navigator.share) {
                        navigator.share({ title: 'Rhodesli', url: url }).catch(function() {});
                    }
                }
                function _copyAndToast(url) {
                    if (navigator.clipboard) {
                        navigator.clipboard.writeText(url).then(function() {
                            _showShareToast('Link copied!');
                        }).catch(function() { _showShareToast('Could not copy link'); });
                    } else {
                        var input = document.createElement('input');
                        input.value = url;
                        document.body.appendChild(input);
                        input.select();
                        document.execCommand('copy');
                        document.body.removeChild(input);
                        _showShareToast('Link copied!');
                    }
                }
                function _showShareToast(message) {
                    var existing = document.getElementById('share-toast');
                    if (existing) existing.remove();
                    var toast = document.createElement('div');
                    toast.id = 'share-toast';
                    toast.textContent = message;
                    toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#334155;color:#e2e8f0;padding:10px 20px;border-radius:8px;font-size:14px;z-index:9999;transition:opacity 0.3s;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
                    document.body.appendChild(toast);
                    setTimeout(function() { toast.style.opacity = '0'; }, 2000);
                    setTimeout(function() { toast.remove(); }, 2500);
                }
                document.addEventListener('click', function(e) {
                    var shareBtn = e.target.closest('[data-action="share-photo"]');
                    if (shareBtn) {
                        var url = shareBtn.getAttribute('data-share-url') || window.location.href;
                        _sharePhotoUrl(url);
                        return;
                    }
                });
            """),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/person/{person_id}")
def get(person_id: str, view: str = "faces", sess=None):
    """
    Public shareable person page showing all photos of a specific person.

    No authentication required — anyone can view.

    Query params:
    - view: "faces" (default) or "photos" — gallery view mode
    """
    user = get_current_user(sess or {}) if is_auth_enabled() else None
    user_is_admin = (user.is_admin if user else False) if is_auth_enabled() else True
    return public_person_page(person_id, view=view, user=user, is_admin=user_is_admin)


@rt("/photos")
def get(filter_collection: str = "", sort_by: str = "newest", sess=None):
    """
    Public photos browsing page — grid of all archive photos.

    No authentication required. Each photo links to /photo/{id}.
    No admin actions visible.
    """
    user = get_current_user(sess or {}) if is_auth_enabled() else None

    _build_caches()
    registry = load_registry()
    crop_files = get_crop_files()

    # Gather photos with metadata
    photos = []
    collections_set = set()
    for photo_id_val, photo_data in (_photo_cache or {}).items():
        collection = photo_data.get("collection", "")
        if collection:
            collections_set.add(collection)
        # Apply collection filter
        if filter_collection and collection != filter_collection:
            continue

        face_count = len(photo_data.get("faces", []))
        confirmed_count = 0
        for face in photo_data.get("faces", []):
            identity = get_identity_for_face(registry, face.get("face_id", ""))
            if identity and identity.get("state") == "CONFIRMED":
                confirmed_count += 1

        photos.append({
            "photo_id": photo_id_val,
            "filename": photo_data.get("filename", "unknown"),
            "collection": collection,
            "face_count": face_count,
            "confirmed_count": confirmed_count,
        })

    collections = sorted(collections_set)

    # Sort
    if sort_by == "oldest":
        photos.sort(key=lambda p: p["filename"])
    elif sort_by == "most_faces":
        photos.sort(key=lambda p: p["face_count"], reverse=True)
    else:  # newest
        photos.sort(key=lambda p: p["filename"], reverse=True)

    # Build photo cards
    photo_cards = []
    for photo in photos:
        badge_cls = "bg-emerald-600/80" if photo["confirmed_count"] == photo["face_count"] and photo["face_count"] > 0 else "bg-black/70"
        photo_cards.append(
            A(
                Div(
                    Img(
                        src=photo_url(photo["filename"]),
                        cls="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300",
                        loading="lazy",
                    ),
                    Div(
                        f"{photo['confirmed_count']}/{photo['face_count']}" if photo["confirmed_count"] > 0 else f"{photo['face_count']} face{'s' if photo['face_count'] != 1 else ''}",
                        cls=f"absolute top-2 right-2 text-white text-xs px-2 py-1 rounded-full backdrop-blur-sm {badge_cls}",
                    ) if photo["face_count"] > 0 else None,
                    cls="aspect-[4/3] overflow-hidden relative",
                ),
                Div(
                    P(photo["collection"] or "", cls="text-xs text-slate-500 truncate"),
                    cls="p-2",
                ) if photo["collection"] else None,
                href=f"/photo/{photo['photo_id']}",
                cls="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden hover:border-slate-500 transition-colors group block",
            )
        )

    # Collection filter
    from urllib.parse import quote as _url_quote
    collection_options = [Option("All Collections", value="")]
    for c in collections:
        collection_options.append(Option(c, value=c, selected=(filter_collection == c)))

    sort_options = [
        Option("Newest First", value="newest", selected=(sort_by == "newest")),
        Option("Oldest First", value="oldest", selected=(sort_by == "oldest")),
        Option("Most Faces", value="most_faces", selected=(sort_by == "most_faces")),
    ]

    nav_links = [
        A("Photos", href="/photos", cls="text-white text-sm font-medium"),
        A("People", href="/people", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
    ]
    if is_auth_enabled() and not user:
        nav_links.append(A("Sign In", href="/login", cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors"))

    page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")

    return (
        Title("Photos — Rhodesli Heritage Archive"),
        Meta(property="og:title", content="Photos — Rhodesli Heritage Archive"),
        Meta(property="og:description", content=f"{len(photos)} historical photographs from the Jewish community of Rhodes."),
        Meta(name="description", content=f"Browse {len(photos)} historical photographs from the Jewish community of Rhodes."),
        page_style,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            Section(
                Div(
                    H1("Photos", cls="text-3xl font-serif font-bold text-white mb-2"),
                    P(f"{len(photos)} historical photograph{'s' if len(photos) != 1 else ''} from the Rhodes diaspora", cls="text-slate-400 text-sm"),
                    cls="max-w-6xl mx-auto px-6 pt-10 pb-6",
                ),
            ),
            Section(
                Div(
                    # Filter/sort bar
                    Div(
                        Select(
                            *collection_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5",
                            onchange=f"window.location.href='/photos?filter_collection=' + encodeURIComponent(this.value) + '&sort_by={sort_by}'",
                        ),
                        Select(
                            *sort_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5",
                            onchange=f"window.location.href='/photos?filter_collection={_url_quote(filter_collection)}&sort_by=' + this.value",
                        ),
                        cls="flex flex-wrap gap-3 mb-6",
                    ),
                    # Photo grid
                    Div(*photo_cards, cls="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4") if photo_cards else Div(
                        P("No photos match your filters.", cls="text-slate-500 text-center py-12"),
                    ),
                    cls="max-w-6xl mx-auto px-6 pb-10",
                ),
            ),
            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-xs text-slate-500 mb-1 font-serif"),
                    P("Preserving the memory of the Jewish community of Rhodes", cls="text-[10px] text-slate-600 italic"),
                    cls="max-w-6xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/people")
def get(sort_by: str = "name", sess=None):
    """
    Public people browsing page — grid of identified people.

    No authentication required. Each person links to /person/{id}.
    No admin actions visible.
    """
    user = get_current_user(sess or {}) if is_auth_enabled() else None

    registry = load_registry()
    crop_files = get_crop_files()

    # Get confirmed identities with real names
    confirmed = [
        i for i in registry.list_identities(state=IdentityState.CONFIRMED)
        if not i.get("name", "").startswith("Unidentified") and not i.get("merged_into")
    ]

    # Sort
    if sort_by == "photos":
        photo_reg = load_photo_registry()
        def photo_count(identity):
            face_ids = [f if isinstance(f, str) else f.get("face_id", "") for f in identity.get("anchor_ids", []) + identity.get("candidate_ids", [])]
            return len(photo_reg.get_photos_for_faces(face_ids))
        confirmed.sort(key=photo_count, reverse=True)
    elif sort_by == "newest":
        confirmed.sort(key=lambda x: x.get("updated_at", x.get("created_at", "")), reverse=True)
    else:  # name
        confirmed.sort(key=lambda x: (x.get("name") or "").lower())

    # Build person cards
    person_cards = []
    for identity in confirmed:
        identity_id = identity["identity_id"]
        name = ensure_utf8_display(identity.get("name", ""))
        all_faces = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        best_face = get_best_face_id(all_faces)
        crop_url = resolve_face_image_url(best_face, crop_files) if best_face and crop_files else None
        face_count = len(all_faces)

        avatar = Img(
            src=crop_url,
            alt=name,
            cls="w-24 h-24 rounded-full object-cover border-3 border-emerald-500/30",
            onerror="this.style.display='none'",
        ) if crop_url else Div(
            Span(name[0].upper() if name else "?", cls="text-2xl font-serif text-slate-400"),
            cls="w-24 h-24 rounded-full bg-slate-800 border-3 border-slate-700 flex items-center justify-center",
        )

        person_cards.append(
            A(
                avatar,
                P(name, cls="text-sm font-medium text-white mt-3 text-center"),
                P(f"{face_count} {'photo' if face_count == 1 else 'photos'}", cls="text-[10px] text-slate-500 mt-1"),
                href=f"/person/{identity_id}",
                cls="flex flex-col items-center p-4 bg-slate-800/50 rounded-xl border border-slate-700 hover:border-emerald-500/30 transition-colors group block",
            )
        )

    sort_options = [
        Option("A-Z", value="name", selected=(sort_by == "name")),
        Option("Most Photos", value="photos", selected=(sort_by == "photos")),
        Option("Newest", value="newest", selected=(sort_by == "newest")),
    ]

    nav_links = [
        A("Photos", href="/photos", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
        A("People", href="/people", cls="text-white text-sm font-medium"),
    ]
    if is_auth_enabled() and not user:
        nav_links.append(A("Sign In", href="/login", cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors"))

    page_style = Style("html, body { margin: 0; } body { background-color: #0f172a; }")

    return (
        Title("People — Rhodesli Heritage Archive"),
        Meta(property="og:title", content="People — Rhodesli Heritage Archive"),
        Meta(property="og:description", content=f"{len(confirmed)} identified people in the Rhodes heritage archive."),
        Meta(name="description", content=f"Browse {len(confirmed)} identified people in the Rhodes heritage archive."),
        page_style,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-6xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            Section(
                Div(
                    H1("People", cls="text-3xl font-serif font-bold text-white mb-2"),
                    P(f"{len(confirmed)} identified {'person' if len(confirmed) == 1 else 'people'} in the archive", cls="text-slate-400 text-sm"),
                    cls="max-w-6xl mx-auto px-6 pt-10 pb-6",
                ),
            ),
            Section(
                Div(
                    Div(
                        Span("Sort:", cls="text-sm text-slate-400 mr-2"),
                        Select(
                            *sort_options,
                            cls="bg-slate-700 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-1.5",
                            onchange="window.location.href='/people?sort_by=' + this.value",
                        ),
                        cls="flex items-center gap-2 mb-6",
                    ),
                    Div(
                        *person_cards,
                        cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4",
                    ) if person_cards else Div(
                        P("No identified people yet. Help us identify faces in the archive!", cls="text-slate-500 text-center py-12"),
                    ),
                    cls="max-w-6xl mx-auto px-6 pb-10",
                ),
            ),
            # CTA
            Section(
                Div(
                    H3("Can you help identify someone?", cls="text-lg font-serif text-white mb-2"),
                    P("Browse the photos and let us know if you recognize anyone.", cls="text-slate-400 text-sm mb-4"),
                    A("Browse Photos", href="/photos",
                      cls="inline-block px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors"),
                    cls="text-center",
                ),
                cls="py-12 border-t border-slate-800",
            ),
            # Footer
            Div(
                Div(
                    P("Rhodesli Heritage Archive", cls="text-xs text-slate-500 mb-1 font-serif"),
                    P("Preserving the memory of the Jewish community of Rhodes", cls="text-[10px] text-slate-600 italic"),
                    cls="max-w-6xl mx-auto px-6 flex flex-col items-center",
                ),
                cls="py-8 border-t border-slate-800",
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


def public_photo_page(
    photo_id: str,
    selected_face_id: str = None,
    user=None,
    is_admin: bool = False,
) -> tuple:
    """
    Build the public shareable photo page.

    This is the beautiful, museum-like page that gets shared on social media.
    Shows the photo with face overlays, person cards, and a call to action.
    No authentication required.
    """
    photo = get_photo_metadata(photo_id)
    if not photo:
        # Gentle 404 page
        style_404 = Style("html, body { margin: 0; } body { background-color: #0f172a; }")
        return (
            Title("Photo Not Found - Rhodesli"),
            style_404,
            Main(
                Nav(
                    Div(
                        A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                        cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16"
                    ),
                    cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800"
                ),
                Div(
                    Div(
                        Span("404", cls="text-6xl font-bold text-slate-700 block mb-4"),
                        H1("Photo not found", cls="text-2xl font-serif font-bold text-white mb-3"),
                        P("This photo hasn't been added to the archive yet.", cls="text-slate-400 mb-8"),
                        A("Explore the Archive", href="/?section=photos",
                          cls="inline-block px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors"),
                        cls="text-center"
                    ),
                    cls="flex items-center justify-center min-h-[60vh]"
                ),
                cls="min-h-screen bg-slate-900"
            ),
        )

    filename = photo["filename"]
    width, height = get_photo_dimensions(filename)
    has_dimensions = width > 0 and height > 0
    registry = load_registry()
    from urllib.parse import quote as _url_quote

    # Check for back image (front/back flip feature)
    back_image = photo.get("back_image", "")
    back_transcription = photo.get("back_transcription", "")
    has_back = bool(back_image)

    # Non-destructive transforms (CSS-based, never modifies original)
    front_transform = photo.get("transform", "")
    back_transform_str = photo.get("back_transform", "")
    front_css_transform = parse_transform_to_css(front_transform)
    front_css_filter = parse_transform_to_filter(front_transform)
    back_css_transform = parse_transform_to_css(back_transform_str)
    back_css_filter = parse_transform_to_filter(back_transform_str)

    # Collect face info for overlays and person cards
    face_info_list = []
    identified_names = []
    unidentified_count = 0
    crop_files = get_crop_files()

    for face_data in photo.get("faces", []):
        face_id = face_data["face_id"]
        bbox = face_data.get("bbox", [])
        identity = get_identity_for_face(registry, face_id)
        raw_name = identity.get("name", "Unidentified") if identity else "Unidentified"
        display_name = ensure_utf8_display(raw_name)
        identity_id = identity["identity_id"] if identity else None
        state = identity.get("state", "INBOX") if identity else None
        is_identified = state == "CONFIRMED" and not display_name.startswith("Unidentified")

        # Get crop URL for person card
        crop_url = resolve_face_image_url(face_id, crop_files) if crop_files else None

        if is_identified:
            identified_names.append(display_name)
        else:
            unidentified_count += 1

        face_info_list.append({
            "face_id": face_id,
            "bbox": bbox,
            "display_name": display_name,
            "identity_id": identity_id,
            "state": state,
            "is_identified": is_identified,
            "crop_url": crop_url,
        })

    # First unidentified face from this photo — for contextual "Help Identify" CTA
    first_unidentified_id = next(
        (fi["identity_id"] for fi in face_info_list if not fi["is_identified"] and fi["identity_id"]),
        None)

    # --- Build face overlays (simplified for public view — no admin actions) ---
    face_overlays = []
    if has_dimensions:
        for fi in face_info_list:
            bbox = fi["bbox"]
            if not bbox or len(bbox) < 4:
                continue
            x1, y1, x2, y2 = bbox
            left_pct = (x1 / width) * 100
            top_pct = (y1 / height) * 100
            width_pct = ((x2 - x1) / width) * 100
            height_pct = ((y2 - y1) / height) * 100

            # Name label positioning: below box if face is near top (avoids clipping),
            # above box if face is lower (more natural reading position)
            name_above = top_pct > 15  # Face is below top 15% — put name above
            name_pos_cls = "-top-6" if name_above else "-bottom-6"

            if fi["is_identified"]:
                overlay_cls = "face-overlay-box absolute border-2 border-emerald-400/70 bg-emerald-400/5 hover:bg-emerald-400/15 transition-all cursor-pointer group"
                name_el = Span(
                    fi["display_name"],
                    cls=f"absolute {name_pos_cls} left-1/2 -translate-x-1/2 bg-black/80 text-emerald-300 text-[11px] px-2 py-0.5 rounded whitespace-nowrap pointer-events-none max-w-[200%] truncate"
                )
            else:
                overlay_cls = "face-overlay-box absolute border-2 border-dashed border-amber-400/50 bg-amber-400/5 hover:bg-amber-400/15 transition-all cursor-pointer group"
                name_el = Span(
                    "Unidentified",
                    cls=f"absolute {name_pos_cls} left-1/2 -translate-x-1/2 bg-black/80 text-amber-300/70 text-[11px] px-2 py-0.5 rounded whitespace-nowrap pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity"
                )

            # Click scrolls to person card
            scroll_target = f"person-{fi['identity_id']}" if fi["identity_id"] else ""
            scroll_script = f"on click go to #{scroll_target} smoothly" if scroll_target else ""

            overlay = Div(
                name_el,
                cls=overlay_cls,
                style=f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;",
                title=fi["display_name"],
                id=f"overlay-{fi['identity_id']}" if fi["identity_id"] else None,
                **{"_": scroll_script} if scroll_script else {},
            )
            face_overlays.append(overlay)

    # --- Build person cards strip ---
    person_cards = []
    for fi in face_info_list:
        card_border = "border-emerald-500/30" if fi["is_identified"] else "border-slate-600/50"
        badge = Span("Identified", cls="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded-full") if fi["is_identified"] else Span("Unidentified", cls="text-[10px] text-amber-400/70 bg-amber-500/10 px-1.5 py-0.5 rounded-full")

        crop_el = Img(
            src=fi["crop_url"],
            alt=fi["display_name"],
            cls="w-20 h-20 rounded-full object-cover border-2 " + ("border-emerald-500/50" if fi["is_identified"] else "border-slate-600"),
            onerror="this.style.display='none'"
        ) if fi["crop_url"] else Div(
            Span("?", cls="text-2xl text-slate-500"),
            cls="w-20 h-20 rounded-full bg-slate-800 border-2 border-slate-600 flex items-center justify-center"
        )

        # Link to person page for identified people
        name_el = fi["display_name"]
        see_all_link = None
        if fi["is_identified"] and fi["identity_id"]:
            name_el = A(
                fi["display_name"],
                href=f"/person/{fi['identity_id']}",
                cls="text-white hover:text-emerald-300 transition-colors"
            )
            see_all_link = A(
                "See all photos \u2192",
                href=f"/person/{fi['identity_id']}",
                cls="text-[10px] text-indigo-400 hover:text-indigo-300 mt-1 transition-colors",
            )

        # Click handler: scroll to face overlay and pulse highlight
        overlay_id = f"overlay-{fi['identity_id']}" if fi["identity_id"] else ""
        click_script = f"""on click
            set el to #{overlay_id}
            if el
                go to el smoothly
                add .ring-2 .ring-yellow-400 to el
                wait 1.5s
                remove .ring-2 .ring-yellow-400 from el
            end""" if overlay_id else ""

        person_cards.append(
            Div(
                crop_el,
                Div(
                    P(name_el, cls="text-sm font-medium text-white mt-2 text-center") if isinstance(name_el, str) else Div(name_el, cls="text-sm font-medium mt-2 text-center"),
                    badge,
                    see_all_link,
                    cls="flex flex-col items-center"
                ),
                id=f"person-{fi['identity_id']}" if fi["identity_id"] else None,
                cls=f"flex flex-col items-center p-4 bg-slate-800/50 rounded-xl border {card_border} min-w-[140px] flex-shrink-0 cursor-pointer hover:bg-slate-700/50 transition-colors",
                **{"_": click_script} if click_script else {},
                title="Click to highlight in photo" if overlay_id else None,
            )
        )

    # --- Photo metadata line ---
    meta_parts = []
    if photo.get("collection"):
        meta_parts.append(photo["collection"])
    if photo.get("source"):
        meta_parts.append(photo["source"])
    meta_line = " · ".join(meta_parts) if meta_parts else None

    # --- Open Graph meta tag data ---
    total_faces = len(face_info_list)
    identified_count = len(identified_names)

    # Build OG title and description
    page_title = photo.get("collection") or "Historical Photo"
    og_title = f"{page_title} — Rhodesli Heritage Archive"

    if identified_count > 0:
        names_preview = ", ".join(identified_names[:3])
        if len(identified_names) > 3:
            names_preview += f", and {len(identified_names) - 3} more"
        if unidentified_count > 0:
            og_description = f"{identified_count} {'person' if identified_count == 1 else 'people'} identified: {names_preview}. Help identify the remaining {unidentified_count}."
        else:
            og_description = f"All {identified_count} {'person' if identified_count == 1 else 'people'} identified: {names_preview}."
    elif total_faces > 0:
        og_description = f"{total_faces} {'face' if total_faces == 1 else 'faces'} detected. Can you help identify anyone in this historical photo?"
    else:
        og_description = "A photograph from the Jewish heritage of Rhodes. Explore the archive."

    # Photo URL for og:image (must be publicly accessible)
    og_image_url = photo_url(filename)
    if not og_image_url.startswith("http"):
        og_image_url = f"{SITE_URL}{og_image_url}"
    og_page_url = f"{SITE_URL}/photo/{photo_id}"

    og_meta_tags = (
        Meta(property="og:title", content=og_title),
        Meta(property="og:description", content=og_description),
        Meta(property="og:image", content=og_image_url),
        Meta(property="og:url", content=og_page_url),
        Meta(property="og:type", content="article"),
        Meta(property="og:site_name", content="Rhodesli — Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image"),
        Meta(name="twitter:title", content=og_title),
        Meta(name="twitter:description", content=og_description),
        Meta(name="twitter:image", content=og_image_url),
        Meta(name="description", content=og_description),
    )
    if has_dimensions:
        og_meta_tags = og_meta_tags + (
            Meta(property="og:image:width", content=str(width)),
            Meta(property="og:image:height", content=str(height)),
        )

    # Navigation
    nav_links = [
        A("Photos", href="/photos", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
        A("People", href="/people", cls="text-slate-300 hover:text-white text-sm font-medium transition-colors"),
    ]
    if is_auth_enabled() and not user:
        nav_links.append(A("Sign In", href="/login", cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors"))

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        .photo-hero-container {
            position: relative;
            display: inline-block;
            max-width: 100%;
            /* Padding for face overlay name labels that extend beyond photo edges */
            padding-top: 1.5rem;
            overflow: visible;
        }
        .photo-hero-container img.photo-hero {
            max-width: 100%;
            height: auto;
            display: block;
            border-radius: 0.5rem;
        }
        .photo-hero-container .face-overlay-public {
            box-sizing: border-box;
        }
        .photo-hero-container .face-overlay-public:hover {
            z-index: 10;
        }
        .person-strip {
            display: flex;
            gap: 1rem;
            overflow-x: auto;
            padding: 0.5rem 0;
            scrollbar-width: thin;
            scrollbar-color: #475569 transparent;
        }
        .person-strip::-webkit-scrollbar {
            height: 6px;
        }
        .person-strip::-webkit-scrollbar-thumb {
            background: #475569;
            border-radius: 3px;
        }
        /* CSS 3D Flip Animation — Premium "turning over a real photo" feel */
        .photo-flip-container {
            perspective: 1200px;
            perspective-origin: center center;
        }
        .photo-flip-inner {
            position: relative;
            transition: transform 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                        box-shadow 0.9s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            transform-style: preserve-3d;
            /* Resting shadow — subtle, like a photo lying on a surface */
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            border-radius: 2px;
        }
        .photo-flip-inner.is-flipped {
            transform: rotateY(180deg) scale(1.02);
            /* Lifted shadow — photo appears to hover while flipping */
            box-shadow: 0 15px 40px rgba(0,0,0,0.35);
        }
        .photo-flip-front {
            backface-visibility: hidden;
            position: relative;
        }
        .photo-flip-back {
            backface-visibility: hidden;
            transform: rotateY(180deg);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            /* Back of a real photo — warm, slightly textured */
            background-color: #f5f0e8;
            background-image:
                repeating-linear-gradient(
                    0deg,
                    transparent,
                    transparent 2px,
                    rgba(0,0,0,0.008) 2px,
                    rgba(0,0,0,0.008) 3px
                );
            /* Edge shadow suggesting photo thickness */
            box-shadow: inset 0 0 30px rgba(0,0,0,0.06);
            border-radius: 2px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 1.5rem;
        }
        .photo-flip-back img {
            border-radius: 2px;
        }
        .photo-flip-inner:not(.is-flipped) .photo-flip-back {
            pointer-events: none;
        }
        .photo-flip-inner.is-flipped .photo-flip-front {
            pointer-events: none;
        }
        /* Face overlays fade out during flip */
        .photo-flip-inner .face-overlay-box {
            transition: opacity 0.3s ease;
        }
        .photo-flip-inner.is-flipped .face-overlay-box {
            opacity: 0;
            pointer-events: none;
        }
    """)

    return (
        Title(f"{page_title} — Rhodesli Heritage Archive"),
        *og_meta_tags,
        page_style,
        Main(
            # Top navigation bar
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-xl font-bold text-white"), href="/", cls="hover:opacity-90"),
                    Div(
                        *nav_links,
                        A("Explore More Photos", href="/photos",
                          cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors ml-4"),
                        cls="hidden sm:flex items-center gap-6"
                    ),
                    cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16"
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50"
            ),

            # Hero photo section
            Section(
                Div(
                    # Photo with overlays (with optional flip animation)
                    Div(
                        Div(
                            # Front side
                            Div(
                                Img(
                                    src=photo_url(filename),
                                    alt=f"Historical photograph from {photo.get('collection', 'the Rhodes diaspora')}",
                                    cls="photo-hero max-w-full h-auto rounded-lg",
                                    style=f"transform: {front_css_transform}; filter: {front_css_filter};" if (front_css_transform or front_css_filter) else None,
                                ),
                                *face_overlays,
                                # Overlay legend
                                Div(
                                    Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-emerald-400 mr-1"),
                                    Span("Identified", cls="text-slate-300 mr-3"),
                                    Span(cls="inline-block w-2.5 h-2.5 rounded-sm border-2 border-dashed border-amber-400 mr-1"),
                                    Span("Unidentified", cls="text-slate-300"),
                                    cls="absolute bottom-3 right-3 bg-black/70 rounded-lg px-3 py-1.5 flex items-center gap-1 text-xs backdrop-blur-sm",
                                ) if face_overlays else None,
                                cls="photo-flip-front" if has_back else "",
                            ),
                            # Back side (only rendered if back image exists)
                            Div(
                                Img(
                                    src=photo_url(back_image),
                                    alt="Back of photograph",
                                    cls="max-w-full h-auto rounded-lg",
                                    style=f"transform: {back_css_transform}; filter: {back_css_filter};" if (back_css_transform or back_css_filter) else None,
                                ),
                                P("Back of photograph", cls="text-amber-700/60 text-xs text-center mt-2 italic font-serif"),
                                P(
                                    back_transcription,
                                    cls="text-amber-900/80 text-sm mt-3 bg-amber-50/50 rounded-lg p-3 border border-amber-200/30 italic font-serif leading-relaxed"
                                ) if back_transcription else None,
                                cls="photo-flip-back",
                            ) if has_back else None,
                            id="photo-flip-inner",
                            cls="photo-flip-inner" if has_back else "",
                        ),
                        cls="photo-flip-container photo-hero-container relative mx-auto" if has_back else "photo-hero-container relative mx-auto",
                    ),
                    # Action bar: Share, Download, Flip (if back image)
                    Div(
                        Button(
                            NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'),
                            "Share This Photo",
                            cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors",
                            type="button",
                            data_action="share-photo",
                            id="share-photo-btn",
                            data_share_title=og_title,
                            data_share_text=og_description,
                            data_share_url=og_page_url,
                        ),
                        A(
                            NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>'),
                            "Download",
                            href=f"/photo/{photo_id}/download",
                            cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors inline-flex items-center",
                            download=True,
                        ),
                        # Flip button (only when back image exists)
                        Button(
                            NotStr('<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>'),
                            Span("Turn Over", id="flip-btn-text"),
                            cls="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded-lg transition-colors",
                            type="button",
                            data_action="flip-photo",
                            id="flip-photo-btn",
                        ) if has_back else None,
                        cls="flex flex-wrap items-center justify-center gap-3 mt-4"
                    ),
                    Span(
                        "This photograph has writing on the back" if back_transcription else "Turn over to see the back of this photograph",
                        cls="text-slate-500 text-xs text-center block mt-2"
                    ) if has_back else None,
                    # Admin: Upload back image (only shown to admin when no back image)
                    Div(
                        Div(
                            P("Admin: Add a back image", cls="text-slate-400 text-xs font-medium mb-2"),
                            Form(
                                Input(type="file", name="file", accept=".jpg,.jpeg,.png,.webp",
                                      cls="text-xs text-slate-300 file:mr-2 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-sm file:bg-slate-600 file:text-white hover:file:bg-slate-500"),
                                Div(
                                    Input(type="text", name="back_transcription", placeholder="Transcribe writing on back (optional)...",
                                          cls="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-500"),
                                    Button("Upload", type="submit",
                                           cls="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg"),
                                    cls="flex gap-2 mt-2",
                                ),
                                hx_post=f"/api/photo/{photo_id}/back-image",
                                hx_target="#back-upload-result",
                                hx_swap="innerHTML",
                                hx_encoding="multipart/form-data",
                            ),
                            Div(id="back-upload-result", cls="mt-2"),
                        ),
                        cls="mt-4 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50"
                    ) if is_admin and not has_back else None,
                    # Admin: Update transcription (when back exists but no transcription)
                    Div(
                        Form(
                            Input(type="text", name="back_transcription",
                                  placeholder="Transcribe writing on back...",
                                  value=back_transcription or "",
                                  cls="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-500"),
                            Button("Save", type="submit",
                                   cls="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg"),
                            hx_post=f"/api/photo/{photo_id}/back-transcription",
                            hx_target="#transcription-result",
                            hx_swap="innerHTML",
                            cls="flex gap-2",
                        ),
                        Div(id="transcription-result", cls="mt-1"),
                        cls="mt-3 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50"
                    ) if is_admin and has_back else None,
                    # Admin: Image orientation toolbar
                    Div(
                        image_transform_toolbar(photo_id, target="front"),
                        image_transform_toolbar(photo_id, target="back") if has_back else None,
                        Div(id="transform-result", cls="mt-1"),
                        P(f"Current: {front_transform}", cls="text-xs text-slate-500 mt-1") if front_transform else None,
                        cls="mt-3 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50"
                    ) if is_admin else None,
                    # Photo metadata
                    Div(
                        P(meta_line, cls="text-slate-400 text-sm") if meta_line else None,
                        P(
                            f"{total_faces} {'person' if total_faces == 1 else 'people'} detected · "
                            f"{identified_count} identified",
                            cls="text-slate-500 text-xs mt-1"
                        ),
                        P(
                            A(photo.get("source_url", ""), href=photo.get("source_url", ""),
                              target="_blank", rel="noopener",
                              cls="text-indigo-400/70 hover:text-indigo-300 text-xs underline"),
                            cls="mt-1"
                        ) if photo.get("source_url") else None,
                        cls="mt-4 text-center"
                    ),
                    cls="max-w-[900px] mx-auto"
                ),
                cls="px-4 sm:px-6 pt-8 pb-6"
            ),

            # People in this photo
            Section(
                Div(
                    H2(
                        f"{'People' if total_faces != 1 else 'Person'} in this photo",
                        cls="text-lg font-serif font-semibold text-white mb-4"
                    ),
                    Div(
                        *person_cards,
                        cls="person-strip"
                    ) if person_cards else P("No faces detected in this photo.", cls="text-slate-500 text-sm"),
                    cls="max-w-[900px] mx-auto"
                ),
                cls="px-4 sm:px-6 py-6 border-t border-slate-800/50"
            ) if face_info_list else None,

            # Call to action — link to first unidentified face from this photo
            Section(
                Div(
                    H2(
                        "Do you recognize someone?",
                        cls="text-xl font-serif font-bold text-white mb-3"
                    ),
                    P(
                        "Help us identify the people in this photograph. Your family knowledge could be the key to preserving our shared history.",
                        cls="text-slate-400 leading-relaxed mb-6 max-w-lg mx-auto"
                    ),
                    Div(
                        A(
                            "I Can Help Identify",
                            href=(f"/?section=skipped&current={first_unidentified_id}"
                                  if first_unidentified_id else "/?section=skipped"),
                            cls="inline-block px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors"
                        ),
                        A(
                            "Browse All Photos",
                            href="/photos",
                            cls="inline-block px-6 py-3 border border-slate-600 text-slate-300 font-medium rounded-lg hover:border-slate-400 hover:text-white transition-colors"
                        ),
                        cls="flex flex-wrap justify-center gap-4"
                    ),
                    cls="text-center max-w-2xl mx-auto"
                ),
                cls="px-4 sm:px-6 py-12 border-t border-slate-800/50"
            ) if unidentified_count > 0 else None,

            # Footer
            Footer(
                Div(
                    P(
                        Span("Rhodesli", cls="font-bold text-white"),
                        " — Preserving the visual heritage of the Jews of Rhodes",
                        cls="text-slate-500 text-sm"
                    ),
                    Div(
                        A("Home", href="/", cls="text-xs text-slate-500 hover:text-slate-300"),
                        Span("·", cls="text-slate-700"),
                        A("Photos", href="/photos", cls="text-xs text-slate-500 hover:text-slate-300"),
                        Span("·", cls="text-slate-700"),
                        A("People", href="/people", cls="text-xs text-slate-500 hover:text-slate-300"),
                        cls="flex items-center gap-2"
                    ),
                    cls="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3"
                ),
                cls="py-8 border-t border-slate-800"
            ),
            # Action button event handlers (standalone page — needs its own share/flip JS)
            Script("""
                function _sharePhotoUrl(url) {
                    _copyAndToast(url);
                    var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
                    if (isMobile && navigator.share) {
                        navigator.share({ title: 'Rhodesli Photo', url: url }).catch(function() {});
                    }
                }
                function _copyAndToast(url) {
                    if (navigator.clipboard) {
                        navigator.clipboard.writeText(url).then(function() {
                            _showShareToast('Link copied!');
                        }).catch(function() { _showShareToast('Could not copy link'); });
                    } else {
                        var input = document.createElement('input');
                        input.value = url;
                        document.body.appendChild(input);
                        input.select();
                        document.execCommand('copy');
                        document.body.removeChild(input);
                        _showShareToast('Link copied!');
                    }
                }
                function _showShareToast(message) {
                    var existing = document.getElementById('share-toast');
                    if (existing) existing.remove();
                    var toast = document.createElement('div');
                    toast.id = 'share-toast';
                    toast.textContent = message;
                    toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#334155;color:#e2e8f0;padding:10px 20px;border-radius:8px;font-size:14px;z-index:9999;transition:opacity 0.3s;box-shadow:0 4px 12px rgba(0,0,0,0.3);';
                    document.body.appendChild(toast);
                    setTimeout(function() { toast.style.opacity = '0'; }, 2000);
                    setTimeout(function() { toast.remove(); }, 2500);
                }
                document.addEventListener('click', function(e) {
                    var shareBtn = e.target.closest('[data-action="share-photo"]');
                    if (shareBtn) {
                        var url = shareBtn.getAttribute('data-share-url') || window.location.href;
                        _sharePhotoUrl(url);
                        return;
                    }
                    var flipBtn = e.target.closest('[data-action="flip-photo"]');
                    if (flipBtn) {
                        var inner = document.getElementById('photo-flip-inner');
                        if (!inner) return;
                        inner.classList.toggle('is-flipped');
                        var textEl = document.getElementById('flip-btn-text');
                        if (textEl) {
                            textEl.textContent = inner.classList.contains('is-flipped') ? 'View Front' : 'Turn Over';
                        }
                        return;
                    }
                });
            """),
            cls="min-h-screen bg-slate-900"
        ),
    )


@rt("/photo/{photo_id}")
def get(photo_id: str, face: str = None, sess=None):
    """
    Public shareable photo page with face overlays and person cards.

    This is the page people share on Facebook, WhatsApp, email, etc.
    No authentication required — anyone can view.

    Query params:
    - face: Optional face_id to highlight
    """
    user = get_current_user(sess or {}) if is_auth_enabled() else None
    user_is_admin = (user.is_admin if user else False) if is_auth_enabled() else True
    return public_photo_page(photo_id, selected_face_id=face, user=user, is_admin=user_is_admin)


@rt("/photo/{photo_id}/partial")
def get(photo_id: str, face: str = None, prev_id: str = None, next_id: str = None,
        nav_idx: int = -1, nav_total: int = 0, identity_id: str = None,
        from_compare: bool = False, sess=None):
    """
    Render photo view partial for HTMX modal injection.

    Optional navigation context:
    - prev_id/next_id: Adjacent photo IDs for prev/next buttons
    - nav_idx/nav_total: Current position for "X of Y" display
    - identity_id: Identity context for computing prev/next from identity's photos
    - from_compare: If True, show "Back to Compare" button (opened via compare modal)
    """
    user_is_admin = (get_current_user(sess or {}).is_admin if get_current_user(sess or {}) else False) if is_auth_enabled() else True
    return photo_view_content(
        photo_id, selected_face_id=face, is_partial=True,
        prev_id=prev_id, next_id=next_id,
        nav_idx=nav_idx, nav_total=nav_total,
        identity_id=identity_id,
        is_admin=user_is_admin,
        from_compare=from_compare,
    )


@rt("/photo/{photo_id}/download")
def get(photo_id: str):
    """
    Download the original full-resolution photo.

    Public endpoint — no auth required.
    Returns the photo file with Content-Disposition: attachment header.
    """
    photo = get_photo_metadata(photo_id)
    if not photo:
        return Response("Photo not found", status_code=404)

    filename = photo["filename"]
    basename = Path(filename).name

    # In R2 mode, redirect to the R2 URL (can't serve local file)
    if storage.is_r2_mode():
        download_url = photo_url(filename)
        return Response(
            status_code=302,
            headers={"Location": download_url}
        )

    # Local mode: serve from filesystem
    photo_path = photos_path / basename
    if not photo_path.exists():
        return Response("Photo file not found", status_code=404)

    return FileResponse(
        str(photo_path),
        filename=basename,
        headers={"Content-Disposition": f'attachment; filename="{basename}"'},
    )


# =============================================================================
# ROUTES - PHASE 3: DISCOVERY & ACTION
# =============================================================================

@rt("/api/identity/{identity_id}/neighbors")
def get(identity_id: str, limit: int = 5, offset: int = 0, from_focus: bool = False, focus_section: str = "", sess=None):
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
        # Add state for correct section routing in neighbor_card links
        try:
            n_identity = registry.get_identity(n["identity_id"])
            n["state"] = n_identity.get("state", "INBOX")
        except KeyError:
            n["state"] = "INBOX"

        # Compute co-occurrence: how many photos these two identities share
        n["co_occurrence"] = _compute_co_occurrence(
            identity_id, n["identity_id"], registry, photo_registry
        )

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
        user_role=_get_user_role(sess),
        from_focus=from_focus,
        focus_section=focus_section,
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


@rt("/api/identity/{identity_id}/skip-hints")
def get(identity_id: str):
    """
    Lazy-loaded ML hints for skipped identities.

    Shows top 3 similar confirmed/named identities to help re-evaluate.
    """
    try:
        registry = load_registry()
        registry.get_identity(identity_id)
    except KeyError:
        return Span()

    face_data = get_face_data()
    photo_registry = load_photo_registry()

    try:
        from core.neighbors import find_nearest_neighbors
        # Fetch up to 5 candidates, then trim based on confidence
        neighbors = find_nearest_neighbors(
            identity_id, registry, photo_registry, face_data, limit=5
        )
    except Exception:
        return Span()

    if not neighbors:
        return Span("No similar identities found.", cls="text-xs text-slate-500 italic")

    # Variable suggestion count: show more when top match is confident,
    # fewer when uncertain. If best match is strong, show up to 3;
    # if weak, show only 1 to avoid decision fatigue.
    best_dist = neighbors[0]["distance"] if neighbors else float("inf")
    if best_dist < MATCH_THRESHOLD_HIGH:
        max_show = 3  # Strong match — show alternatives for comparison
    elif best_dist < MATCH_THRESHOLD_LOW:
        max_show = 2  # Moderate — show a couple
    else:
        max_show = 1  # Weak — just show the best guess
    neighbors = neighbors[:max_show]

    # Enrich neighbor data with face IDs for thumbnail resolution
    # (find_nearest_neighbors returns raw results without face IDs)
    for n in neighbors:
        n["anchor_face_ids"] = registry.get_anchor_face_ids(n["identity_id"])
        n["candidate_face_ids"] = registry.get_candidate_face_ids(n["identity_id"])

    # Map distance to confidence tier for visual display
    # Uses config constants for consistency with neighbor_card (AD-013)
    def _confidence_tier(dist):
        if dist < MATCH_THRESHOLD_VERY_HIGH:
            return ("Very High", "bg-emerald-500", 5)
        elif dist < MATCH_THRESHOLD_HIGH:
            return ("High", "bg-green-500", 4)
        elif dist < MATCH_THRESHOLD_MODERATE:
            return ("Moderate", "bg-amber-500", 3)
        elif dist < MATCH_THRESHOLD_LOW:
            return ("Low", "bg-orange-500", 2)
        else:
            return ("Very Low", "bg-red-500", 1)

    # Build suggestion cards with visual confidence and action buttons
    crop_files = get_crop_files()
    suggestion_items = []
    for n in neighbors:
        name = ensure_utf8_display(n.get("name", "Unknown"))
        dist = n.get("distance", 0)
        neighbor_id = n.get("identity_id", "")
        tier_label, tier_color, tier_dots = _confidence_tier(dist)

        # Face thumbnail — use enriched anchor/candidate face IDs (same pattern as neighbor_card)
        thumb = Div(cls="w-10 h-10 rounded-full bg-slate-600 flex-shrink-0")
        all_face_ids = n.get("anchor_face_ids", []) + n.get("candidate_face_ids", [])
        for fid in all_face_ids:
            face_url = resolve_face_image_url(fid, crop_files)
            if face_url:
                thumb = Img(src=face_url, cls="w-10 h-10 rounded-full object-cover flex-shrink-0 border border-slate-600")
                break

        # Confidence dots (filled vs empty)
        dots = Span(
            *[Span(cls=f"inline-block w-1.5 h-1.5 rounded-full {'bg-current' if i < tier_dots else 'bg-slate-600'}")
              for i in range(5)],
            cls=f"flex gap-0.5 items-center {tier_color.replace('bg-', 'text-')}",
        )

        # State badge for named vs unidentified
        is_named = not name.startswith("Unidentified Person")
        name_cls = "text-sm text-white font-medium truncate" if is_named else "text-sm text-slate-300 truncate"

        # Action buttons
        compare_btn = Button(
            "Compare",
            cls="text-[10px] px-2 py-0.5 bg-slate-600 hover:bg-slate-500 text-slate-300 rounded transition-colors",
            hx_get=f"/api/identity/{identity_id}/compare/{neighbor_id}",
            hx_target="#compare-modal-content",
            hx_swap="innerHTML",
            type="button",
            **{"_": "on click remove .hidden from #compare-modal"},
        )
        merge_btn = Button(
            "Merge",
            cls="text-[10px] px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors",
            hx_post=f"/api/identity/{neighbor_id}/merge/{identity_id}",
            hx_target="#focus-container",
            hx_swap="outerHTML",
            type="button",
        ) if tier_dots >= 3 else None  # Only show merge for Moderate+ confidence

        suggestion_items.append(Div(
            thumb,
            Div(
                Span(name, cls=name_cls),
                Div(dots, Span(tier_label, cls=f"text-[10px] {tier_color.replace('bg-', 'text-')}"), cls="flex items-center gap-1.5"),
                cls="flex-1 min-w-0 flex flex-col",
            ),
            Div(compare_btn, merge_btn, cls="flex gap-1 flex-shrink-0"),
            cls="flex items-center gap-2 p-2 rounded hover:bg-slate-700/50 transition-colors",
        ))

    return Div(
        Div(
            Span("AI suggestions", cls="text-xs text-slate-400 font-medium"),
            cls="mb-1",
        ),
        *suggestion_items,
        cls="mt-2 bg-slate-800/50 rounded-lg border border-slate-700/50 p-1",
    )


@rt("/api/identity/{identity_id}/search")
def get(identity_id: str, q: str = "", sess=None):
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
    return search_results_panel(results, identity_id, crop_files, user_role=_get_user_role(sess))


@rt("/api/search")
def get(q: str = ""):
    """
    Global search for identities by name. Used by the sidebar search input.

    Args:
        q: Search query (minimum 2 characters, case-insensitive partial match)

    Returns HTMX partial with matching identity results (limit 10).
    Each result links to the correct section based on identity state.
    """
    if len(q.strip()) < 2:
        return ""

    try:
        registry = load_registry()
    except Exception:
        return Div(
            P("Search unavailable.", cls="text-slate-400 italic text-sm p-2"),
        )

    # Search all non-merged identities by name
    results = registry.search_identities(q)
    if not results:
        return Div(
            P("No matches found.", cls="text-slate-400 italic text-sm p-3"),
        )

    crop_files = get_crop_files()
    items = []
    query_stripped = q.strip()
    for r in results[:10]:
        face_url = resolve_face_image_url(r["preview_face_id"], crop_files) if r.get("preview_face_id") else None
        thumb = Img(src=face_url, cls="w-8 h-8 rounded-full object-cover flex-shrink-0") if face_url else Div(cls="w-8 h-8 rounded-full bg-slate-600 flex-shrink-0")
        name = ensure_utf8_display(r["name"]) or "Unnamed"

        # Highlight matched portion in name (case-insensitive)
        name_display = _highlight_match(name, query_stripped)

        # Route to correct section based on identity state
        section = _section_for_state(r.get("state", "INBOX"))

        # State badge for non-confirmed results
        state = r.get("state", "INBOX")
        state_indicator = None
        if state != "CONFIRMED":
            state_colors = {
                "PROPOSED": "bg-indigo-500/20 text-indigo-300",
                "INBOX": "bg-slate-500/20 text-slate-300",
                "SKIPPED": "bg-amber-500/20 text-amber-300",
            }
            badge_cls = state_colors.get(state, "bg-slate-500/20 text-slate-300")
            state_label = "Help Identify" if state == "SKIPPED" else state.title()
            state_indicator = Span(state_label, cls=f"text-[10px] px-1.5 py-0.5 rounded {badge_cls}")

        items.append(
            A(
                thumb,
                Div(
                    Div(
                        Span(name_display, cls="text-sm text-slate-200 truncate"),
                        state_indicator,
                        cls="flex items-center gap-1.5"
                    ),
                    Span(f"{r['face_count']} {'face' if r['face_count'] == 1 else 'faces'}", cls="text-xs text-slate-500"),
                    cls="flex flex-col min-w-0"
                ),
                href=f"/?section={section}#identity-{r['identity_id']}",
                cls="flex items-center gap-2 px-3 py-2 hover:bg-slate-700 transition-colors cursor-pointer"
            )
        )
    return Div(*items)


@rt("/api/face/tag-search")
def get(face_id: str, q: str = "", sess=None):
    """
    Search for identities to tag a face with (Instagram-style tagging).

    Admin: returns merge buttons (direct action).
    Non-admin: returns suggestion buttons (creates annotation for review).
    """
    import json as _json
    from urllib.parse import quote as _url_quote
    safe_face_id = face_id.replace(":", "-").replace(" ", "_")
    face_id_encoded = _url_quote(face_id, safe="")
    results_id = f"tag-results-{safe_face_id}"

    if len(q.strip()) < 2:
        return Div(id=results_id)

    try:
        registry = load_registry()
    except Exception:
        return Div(
            P("Search unavailable.", cls="text-slate-400 italic text-xs"),
            id=results_id
        )

    # Determine user role for rendering appropriate action buttons
    user_is_admin = False
    if not is_auth_enabled():
        user_is_admin = True
    else:
        user = get_current_user(sess or {})
        if user and user.is_admin:
            user_is_admin = True

    # Find the identity this face belongs to (to exclude from results)
    source_identity = get_identity_for_face(registry, face_id)
    exclude_id = source_identity["identity_id"] if source_identity else None
    source_identity_id = source_identity["identity_id"] if source_identity else ""

    # Search all identities (confirmed get priority in search_identities)
    results = registry.search_identities(q, exclude_id=exclude_id)

    crop_files = get_crop_files()
    items = []
    for r in results[:8]:
        face_url = resolve_face_image_url(r["preview_face_id"], crop_files) if r.get("preview_face_id") else None
        thumb = Img(src=face_url, cls="w-8 h-8 rounded-full object-cover flex-shrink-0") if face_url else Div(cls="w-8 h-8 rounded-full bg-slate-600 flex-shrink-0")
        name = ensure_utf8_display(r["name"]) or "Unnamed"

        if user_is_admin:
            # Admin: direct merge
            btn = Button(
                thumb,
                Div(
                    Span(name, cls="text-sm text-slate-200 truncate"),
                    Span(f"{r['face_count']} faces", cls="text-xs text-slate-500"),
                    cls="flex flex-col min-w-0 text-left"
                ),
                cls="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer",
                hx_post=f"/api/face/tag?face_id={face_id_encoded}&target_id={r['identity_id']}",
                hx_target="#photo-modal-content",
                hx_swap="innerHTML",
                type="button",
            )
        else:
            # Non-admin: submit name suggestion annotation
            btn = Button(
                thumb,
                Div(
                    Span(name, cls="text-sm text-slate-200 truncate"),
                    Span("Suggest match", cls="text-xs text-indigo-400"),
                    cls="flex flex-col min-w-0 text-left"
                ),
                cls="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer",
                hx_post="/api/annotations/submit",
                hx_vals=_json.dumps({
                    "target_type": "identity",
                    "target_id": source_identity_id,
                    "annotation_type": "name_suggestion",
                    "value": name,
                    "confidence": "likely",
                    "reason": f"face_tag:{face_id}:matched_to:{r['identity_id']}",
                }),
                hx_target="#toast-container",
                hx_swap="beforeend",
                type="button",
            )
        items.append(btn)

    # Bottom option: create new identity (admin) or suggest new name (non-admin)
    from urllib.parse import quote as _url_quote
    if user_is_admin:
        create_btn = Button(
            Div("+", cls="w-8 h-8 rounded-full bg-indigo-600 flex-shrink-0 flex items-center justify-center text-white font-bold text-lg"),
            Div(
                Span(f'Create "{q.strip()}"', cls="text-sm text-indigo-300 truncate"),
                Span("New identity", cls="text-xs text-slate-500"),
                cls="flex flex-col min-w-0 text-left"
            ),
            cls="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer "
                "border-t border-slate-700 mt-1 pt-1",
            hx_post=f"/api/face/create-identity?face_id={face_id_encoded}&name={_url_quote(q.strip())}",
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            type="button",
        )
    else:
        create_btn = Button(
            Div("+", cls="w-8 h-8 rounded-full bg-indigo-600 flex-shrink-0 flex items-center justify-center text-white font-bold text-lg"),
            Div(
                Span(f'Suggest "{q.strip()}"', cls="text-sm text-indigo-300 truncate"),
                Span("Submit for review", cls="text-xs text-slate-500"),
                cls="flex flex-col min-w-0 text-left"
            ),
            cls="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer "
                "border-t border-slate-700 mt-1 pt-1",
            hx_post="/api/annotations/submit",
            hx_vals=_json.dumps({
                "target_type": "identity",
                "target_id": source_identity_id,
                "annotation_type": "name_suggestion",
                "value": q.strip(),
                "confidence": "likely",
                "reason": f"face_tag:{face_id}:new_name",
            }),
            hx_target="#toast-container",
            hx_swap="beforeend",
            type="button",
        )
    items.append(create_btn)

    if not results:
        # Show only the create/suggest button with a "no matches" message
        return Div(
            P("No existing matches.", cls="text-slate-500 italic text-xs p-1"),
            create_btn,
            id=results_id,
        )

    return Div(*items, id=results_id)


@rt("/api/face/tag")
def post(face_id: str, target_id: str, sess=None):
    """
    Tag a face with an identity by merging the face's current identity into target.

    This is the one-click merge for Instagram-style face tagging.
    Returns the updated photo view with a success toast.
    """
    denied = _check_admin(sess)
    if denied:
        return denied

    try:
        registry = load_registry()
        photo_registry = load_photo_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Find the source identity (the one the face currently belongs to)
    source_identity = get_identity_for_face(registry, face_id)
    if not source_identity:
        return Response(
            to_xml(toast("Face not found in any identity.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    source_id = source_identity["identity_id"]
    if source_id == target_id:
        return Response(
            to_xml(toast("Face already belongs to this identity.", "info")),
            status_code=200,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Get target name for toast
    try:
        target = registry.get_identity(target_id)
        target_name = ensure_utf8_display(target.get("name")) or f"Identity {target_id[:8]}..."
    except KeyError:
        target_name = f"Identity {target_id[:8]}..."

    # Merge
    result = registry.merge_identities(
        source_id=source_id,
        target_id=target_id,
        user_source="face_tag",
        photo_registry=photo_registry,
    )

    if result["success"]:
        save_registry(registry)

        # Find the photo this face is in to re-render the photo view
        photo_id = get_photo_id_for_face(face_id)
        if photo_id:
            # Re-render the photo view to reflect the merge
            photo_content = photo_view_content(photo_id, selected_face_id=face_id, is_partial=True, is_admin=True)
            oob_toast = Div(
                toast(f"Tagged as {target_name}!", "success"),
                hx_swap_oob="beforeend:#toast-container",
            )
            return (*photo_content, oob_toast)
        else:
            return toast(f"Tagged as {target_name}!", "success")
    else:
        return Response(
            to_xml(toast(f"Cannot tag: {result['reason']}", "warning")),
            status_code=200,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )


@rt("/api/face/quick-action")
def post(identity_id: str, action: str, photo_id: str, sess=None):
    """
    Quick inline action on a face overlay: confirm, skip, or reject.

    Returns a refreshed photo view with updated overlay colors.
    Admin-only.
    """
    denied = _check_admin(sess)
    if denied:
        return denied

    if action not in ("confirm", "skip", "reject"):
        return Response("Invalid action. Must be confirm, skip, or reject.", status_code=400)

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

    state = identity.get("state", "INBOX")
    action_name = action.capitalize()

    try:
        if action == "confirm":
            registry.confirm_identity(identity_id, user_source="quick_action")
        elif action == "skip":
            registry.skip_identity(identity_id, user_source="quick_action")
        elif action == "reject":
            registry.contest_identity(identity_id, user_source="quick_action", reason="Rejected via quick action")
        save_registry(registry)
    except (ValueError, Exception) as e:
        return Response(
            to_xml(toast(f"Cannot {action}: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Re-render the photo view with updated overlay colors
    photo_content = photo_view_content(photo_id, is_partial=True, is_admin=True)
    oob_toast = Div(
        toast(f"{action_name}ed identity!", "success"),
        hx_swap_oob="beforeend:#toast-container",
    )
    return (*photo_content, oob_toast)


@rt("/api/face/create-identity")
def post(face_id: str, name: str, sess=None):
    """
    Create a named identity for a face by renaming its current identity.

    Used from the tag dropdown "+ Create" button. Renames the face's current
    identity (typically an INBOX singleton) to the user-provided name.
    """
    denied = _check_admin(sess)
    if denied:
        return denied

    name = name.strip()
    if not name:
        return Response(
            to_xml(toast("Name cannot be empty.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    source_identity = get_identity_for_face(registry, face_id)
    if not source_identity:
        return Response(
            to_xml(toast("Face not found in any identity.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    identity_id = source_identity["identity_id"]
    registry.rename_identity(identity_id, name)
    # Auto-confirm when naming from tag dropdown (tagging = "this IS that person")
    current_state = source_identity.get("state", "INBOX")
    if current_state in ("INBOX", "PROPOSED", "SKIPPED"):
        try:
            registry.confirm_identity(identity_id, user_source="face_tag")
        except Exception:
            pass  # Already confirmed, or other benign error
    save_registry(registry)

    # Re-render the photo view to show the new name
    photo_id = get_photo_id_for_face(face_id)
    if photo_id:
        photo_content = photo_view_content(photo_id, selected_face_id=face_id, is_partial=True, is_admin=True)
        oob_toast = Div(
            toast(f'Named as "{name}"!', "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (*photo_content, oob_toast)
    else:
        return toast(f'Named as "{name}"!', "success")


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


def _name_conflict_modal(target_id: str, source_id: str, details: dict, merge_source: str) -> Div:
    """Render a name conflict resolution modal for two-named merges."""
    a = details["identity_a"]
    b = details["identity_b"]
    return Div(
        Div(cls="absolute inset-0 bg-black/80",
            **{"_": "on click remove closest .fixed"}),
        Div(
            H3("Name Conflict", cls="text-lg font-bold text-white mb-4"),
            P("Both identities have names. Choose which name to keep:",
              cls="text-slate-300 mb-4 text-sm"),
            Form(
                Input(type="hidden", name="source", value=merge_source),
                Div(
                    Label(
                        Input(type="radio", name="resolved_name", value=a["name"],
                              cls="mr-2", checked=True),
                        Span(a["name"], cls="font-semibold text-white"),
                        Span(f" ({a['face_count']} faces, {a['state']})",
                             cls="text-slate-400 text-sm"),
                        cls="flex items-center cursor-pointer hover:bg-slate-700 p-2 rounded",
                    ),
                    cls="mb-2",
                ),
                Div(
                    Label(
                        Input(type="radio", name="resolved_name", value=b["name"],
                              cls="mr-2"),
                        Span(b["name"], cls="font-semibold text-white"),
                        Span(f" ({b['face_count']} faces, {b['state']})",
                             cls="text-slate-400 text-sm"),
                        cls="flex items-center cursor-pointer hover:bg-slate-700 p-2 rounded",
                    ),
                    cls="mb-2",
                ),
                Div(
                    Label(
                        Input(type="radio", name="resolved_name", value="__custom__",
                              cls="mr-2",
                              **{"_": "on change show #custom-name-input"}),
                        Span("Custom name", cls="text-slate-300"),
                        cls="flex items-center cursor-pointer hover:bg-slate-700 p-2 rounded",
                    ),
                    Input(type="text", name="custom_name", id="custom-name-input",
                          placeholder="Enter custom name...",
                          cls="hidden mt-2 w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm"),
                    cls="mb-4",
                ),
                Div(
                    Button("Cancel", type="button",
                           cls="px-4 py-2 text-sm text-slate-400 hover:text-white",
                           **{"_": "on click remove closest .fixed"}),
                    Button("Merge", type="submit",
                           cls="px-4 py-2 text-sm font-bold bg-blue-600 text-white rounded hover:bg-blue-500"),
                    cls="flex justify-end gap-3",
                ),
                hx_post=f"/api/identity/{target_id}/merge/{source_id}",
                hx_target=f"#identity-{target_id}",
                hx_swap="outerHTML",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-md p-6 relative border border-slate-700",
        ),
        cls="fixed inset-0 flex items-center justify-center p-4 z-[9999]",
    )


def toast_with_merge_undo(message: str, target_id: str) -> Div:
    """Toast notification with Undo button for merge actions."""
    return Div(
        Span("\u2713", cls="mr-2"),
        Span(message, cls="flex-1"),
        Button(
            "Undo",
            cls="ml-3 px-2 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"/api/identity/{target_id}/undo-merge",
            hx_swap="outerHTML",
            hx_target="closest div",
            type="button",
        ),
        cls="px-4 py-3 rounded shadow-lg flex items-center bg-emerald-600 text-white animate-fade-in",
        **{"_": "on load wait 8s then remove me"},
    )


@rt("/api/identity/{target_id}/merge/{source_id}")
def post(target_id: str, source_id: str, source: str = "web",
         resolved_name: str = None, custom_name: str = None, from_focus: bool = False, filter: str = "", focus_section: str = "", sess=None):
    """
    Merge source identity into target identity. Requires admin.

    Enhanced behavior:
    - Auto-corrects merge direction (named identity always survives)
    - Detects name conflicts (both named) and shows resolution modal
    - Records merge_history on target for undo capability
    - Promotes target state if source had higher-trust state
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

    # Handle custom name from conflict resolution form
    actual_resolved_name = resolved_name
    if resolved_name == "__custom__" and custom_name:
        actual_resolved_name = custom_name.strip()
    elif resolved_name == "__custom__":
        actual_resolved_name = None  # No custom name, will re-trigger conflict

    # Attempt merge (with auto-correction)
    result = registry.merge_identities(
        source_id=source_id,
        target_id=target_id,
        user_source=user_source,
        photo_registry=photo_registry,
        resolved_name=actual_resolved_name,
    )

    if not result["success"]:
        # Handle name conflict -- show resolution modal
        if result["reason"] == "name_conflict":
            return _name_conflict_modal(
                target_id, source_id,
                result["name_conflict_details"],
                merge_source=source,
            )

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

    # Use the actual target/source from the result (may have been swapped)
    actual_target_id = result["target_id"]
    actual_source_id = result["source_id"]

    # BE-006: Retarget annotations from source to target
    _merge_annotations(actual_source_id, actual_target_id)

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(actual_target_id)
    target_name = ensure_utf8_display(updated_identity.get("name")) or "identity"
    is_unnamed = target_name.startswith("Unidentified") or target_name.startswith("identity")

    # Log the action
    log_user_action(
        "MERGE",
        source_identity_id=actual_source_id,
        target_identity_id=actual_target_id,
        faces_merged=result["faces_merged"],
        direction_swapped=result.get("direction_swapped", False),
    )

    # Build OOB elements to remove absorbed identity from DOM
    oob_elements = [
        Div(id=f"identity-{actual_source_id}", hx_swap_oob="delete"),
        Div(id=f"neighbor-{actual_source_id}", hx_swap_oob="delete"),
        Div(id=f"search-result-{actual_source_id}", hx_swap_oob="delete"),
    ]

    # If direction was swapped, also clean up the original identity cards
    if result.get("direction_swapped"):
        oob_elements.extend([
            Div(id=f"neighbor-{actual_target_id}", hx_swap_oob="delete"),
            Div(id=f"search-result-{actual_target_id}", hx_swap_oob="delete"),
        ])

    # Toast with undo
    merge_toast = toast_with_merge_undo(
        f"Merged {_pl(result['faces_merged'], 'face')} into {target_name}.",
        actual_target_id,
    )

    # Post-merge re-evaluation: suggest nearby unmatched faces (ML-005)
    suggestion_panel = _post_merge_suggestions(actual_target_id, registry, crop_files)

    # Post-merge guidance banner — encourage naming unnamed identities
    if is_unnamed:
        faces_merged = result["faces_merged"]
        merge_guidance = Div(
            Div(
                Span("Grouped!", cls="font-bold text-emerald-300"),
                Span(f" {_pl(faces_merged, 'face')} are now linked together.", cls="text-slate-300"),
                cls="text-sm",
            ),
            Button(
                "Add a name \u2192",
                cls="text-xs text-indigo-400 hover:text-indigo-300 underline mt-1",
                hx_get=f"/api/identity/{actual_target_id}/rename-form",
                hx_target=f"#name-{actual_target_id}",
                hx_swap="outerHTML",
                type="button",
            ),
            cls="bg-emerald-900/20 border border-emerald-500/30 rounded-lg px-4 py-3 mb-3",
            id=f"merge-guidance-{actual_target_id}",
            hx_swap_oob=f"afterbegin:#identity-{actual_target_id}",
        )
    else:
        total_faces = len(updated_identity.get("anchor_ids", [])) + len(updated_identity.get("candidate_ids", []))
        merge_guidance = Div(
            Div(
                Span("Merge complete!", cls="font-bold text-emerald-300"),
                Span(f" {_pl(total_faces, 'face')} now confirmed as ", cls="text-slate-300"),
                Span(target_name, cls="font-semibold text-white"),
                Span(".", cls="text-slate-300"),
                cls="text-sm",
            ),
            cls="bg-emerald-900/20 border border-emerald-500/30 rounded-lg px-4 py-3 mb-3",
            id=f"merge-guidance-{actual_target_id}",
            hx_swap_oob=f"afterbegin:#identity-{actual_target_id}",
            **{"_": "on load wait 6s then transition opacity to 0 over 1s then remove me"},
        )

    # If from focus mode, advance to next identity instead of showing browse card
    if from_focus:
        if focus_section == "skipped":
            return (
                get_next_skipped_focus_card(exclude_id=actual_target_id),
                merge_toast,
            )
        return (
            get_next_focus_card(exclude_id=actual_target_id, triage_filter=filter),
            merge_toast,
        )

    return (
        identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        merge_guidance,
        *oob_elements,
        merge_toast,
        suggestion_panel,
    )


def _post_merge_suggestions(target_id: str, registry, crop_files: set, max_suggestions: int = 3):
    """
    After a merge, find nearby unmatched faces and suggest them for review.
    Uses multi-anchor best-linkage (AD-001 compliant). Only shows HIGH+ matches.
    """
    try:
        from core.neighbors import find_nearest_neighbors
        face_data = get_face_data()
        photo_registry = load_photo_registry()
        neighbors = find_nearest_neighbors(
            target_id, registry, photo_registry, face_data, limit=max_suggestions
        )
    except Exception:
        return Span()

    # Filter to HIGH confidence or better
    high_matches = [n for n in neighbors if n["distance"] < MATCH_THRESHOLD_HIGH]
    if not high_matches:
        return Span()

    cards = []
    for n in high_matches:
        cards.append(neighbor_card(n, target_id, crop_files, show_checkbox=False))

    return Div(
        Div(
            H4("You might also want to review:", cls="text-sm font-medium text-amber-400"),
            P(f"{_pl(len(high_matches), 'similar face')} found after merge", cls="text-xs text-slate-400"),
            cls="mb-2"
        ),
        Div(*cards, cls="space-y-2"),
        cls="mt-4 p-4 bg-slate-800/50 border border-amber-500/30 rounded-lg",
        id="post-merge-suggestions",
        hx_swap_oob="beforeend:#toast-container",
    )


@rt("/api/identity/{target_id}/suggest-merge/{source_id}")
def post(target_id: str, source_id: str, confidence: str = "likely", reason: str = "", sess=None):
    """
    Contributor endpoint: suggest merging source into target. Creates a
    merge_suggestion annotation for admin review instead of executing the merge.
    """
    denied = _check_contributor(sess)
    if denied:
        return denied

    user = get_current_user(sess)
    submitted_by = user.email if user else "anonymous"

    # Validate both identities exist
    try:
        registry = load_registry()
        registry.get_identity(target_id)
        registry.get_identity(source_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    _create_merge_suggestion(
        target_id=target_id, source_id=source_id,
        submitted_by=submitted_by,
        confidence=confidence,
        reason=reason,
    )

    log_user_action("SUGGEST_MERGE", target=target_id, source=source_id, user=submitted_by)

    return Response(
        to_xml(toast("Merge suggestion submitted for admin review.", "success")),
        headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
    )


@rt("/api/identity/{identity_id}/undo-merge")
def post(identity_id: str, sess=None):
    """
    Undo the most recent merge on an identity. Requires admin.

    Reads merge_history, restores the source identity, removes
    merged faces from target.
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

    # Validate identity exists
    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    # Attempt undo
    result = registry.undo_merge(identity_id, user_source="web")

    if not result["success"]:
        error_messages = {
            "no_merge_history": "Nothing to undo.",
            "source_not_found": "Cannot undo: source identity no longer exists.",
            "target_is_merged": "Cannot undo: this identity has been merged into another.",
        }
        message = error_messages.get(result["reason"], f"Undo failed: {result['reason']}")
        return Response(
            to_xml(toast(message, "warning")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    save_registry(registry)

    log_user_action(
        "UNDO_MERGE",
        target_identity_id=identity_id,
        restored_source_id=result["source_id"],
        faces_removed=result["faces_removed"],
    )

    return toast(f"Merge undone. {_pl(result['faces_removed'], 'face')} restored.", "success")


@rt("/api/identity/{identity_id}/bulk-merge")
def post(identity_id: str, bulk_ids: list[str] = None, sess=None):
    """
    Bulk merge multiple identities into one target. Requires admin.

    Merges each selected identity into the target one by one.
    """
    denied = _check_admin(sess)
    if denied:
        return denied

    if not bulk_ids:
        return toast("No identities selected.", "warning")

    # Ensure bulk_ids is a list (single value comes as string)
    if isinstance(bulk_ids, str):
        bulk_ids = [bulk_ids]

    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    photo_registry = load_photo_registry()

    merged_count = 0
    total_faces = 0
    errors = []

    for source_id in bulk_ids:
        try:
            result = registry.merge_identities(
                source_id=source_id,
                target_id=identity_id,
                user_source="web",
                photo_registry=photo_registry,
            )
            if result["success"]:
                merged_count += 1
                total_faces += result["faces_merged"]
            else:
                errors.append(f"{source_id[:8]}: {result['reason']}")
        except Exception as e:
            errors.append(f"{source_id[:8]}: {str(e)}")

    if merged_count > 0:
        save_registry(registry)

    if errors:
        return toast(f"Merged {merged_count} identities ({total_faces} faces). {len(errors)} failed.", "warning")

    return toast(f"Merged {merged_count} identities ({total_faces} faces).", "success")


@rt("/api/identity/{identity_id}/bulk-reject")
def post(identity_id: str, bulk_ids: list[str] = None, sess=None):
    """
    Bulk mark multiple identities as Not Same. Requires admin.
    """
    denied = _check_admin(sess)
    if denied:
        return denied

    if not bulk_ids:
        return toast("No identities selected.", "warning")

    # Ensure bulk_ids is a list
    if isinstance(bulk_ids, str):
        bulk_ids = [bulk_ids]

    try:
        registry = load_registry()
    except Exception:
        return Response(
            to_xml(toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    rejected_count = 0
    for target_id in bulk_ids:
        try:
            registry.reject_identity_pair(identity_id, target_id, user_source="web")
            rejected_count += 1
        except Exception:
            pass

    if rejected_count > 0:
        save_registry(registry)

    return toast(f"Marked {rejected_count} identities as 'Not Same'.", "info")


@rt("/api/identity/{identity_id}/faces")
def get(identity_id: str, sort: str = "date", page: int = 0):
    """
    Get faces for an identity with optional sorting and pagination.

    Query params:
    - sort: "date" (default) or "outlier"
    - page: 0-indexed page number (FACES_PER_PAGE items per page)

    Returns HTML partial with face cards and pagination controls.
    """
    try:
        registry = load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    crop_files = get_crop_files()
    face_data = get_face_data()

    # Get all face entries in requested order
    if sort == "outlier":
        from core.neighbors import sort_faces_by_outlier_score
        sorted_faces = sort_faces_by_outlier_score(identity_id, registry, face_data)
        all_entries = [face_id for face_id, _ in sorted_faces]
    else:
        all_entries = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])

    total_faces = len(all_entries)
    can_detach = total_faces > 1

    # Paginate
    start = page * FACES_PER_PAGE
    end = start + FACES_PER_PAGE
    page_entries = all_entries[start:end]

    # Build face cards
    if sort == "outlier":
        # For outlier sort, entries are plain face_id strings
        cards = []
        for face_id in page_entries:
            crop_url = resolve_face_image_url(face_id, crop_files)
            if crop_url:
                photo_id = get_photo_id_for_face(face_id)
                cards.append(face_card(
                    face_id=face_id,
                    crop_url=crop_url,
                    photo_id=photo_id,
                    identity_id=identity_id,
                    show_detach=can_detach,
                ))
            else:
                cards.append(Div(
                    Div(Span("?", cls="text-4xl text-slate-500"),
                        cls="w-full aspect-square bg-slate-700 border border-slate-600 flex items-center justify-center"),
                    P("Image unavailable", cls="text-xs text-slate-400 mt-1"),
                    P(f"ID: {face_id[:12]}...", cls="text-xs font-data text-slate-500"),
                    cls="face-card", id=make_css_id(face_id),
                ))
    else:
        cards = _build_face_cards_for_entries(page_entries, crop_files, identity_id, can_detach)

    pagination = _face_pagination_controls(identity_id, page, total_faces, sort)

    return Div(
        Div(
            *cards,
            cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3",
        ),
        pagination,
        id=f"faces-{identity_id}",
    )


# =============================================================================
# ROUTES - RENAME IDENTITY
# =============================================================================

@rt("/api/identity/{identity_id}/photos")
def get(identity_id: str, index: int = 0):
    """Get a single photo for the lightbox, with face overlays and navigation."""
    try:
        registry = load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return P("Identity not found", cls="text-red-400")

    all_face_entries = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    if not all_face_entries:
        return P("No faces for this identity", cls="text-slate-400")

    index = max(0, min(index, len(all_face_entries) - 1))
    total = len(all_face_entries)

    face_entry = all_face_entries[index]
    face_id = face_entry if isinstance(face_entry, str) else face_entry.get("face_id", "")

    pid = get_photo_id_for_face(face_id)
    if not pid:
        return P("Photo not found for this face", cls="text-slate-400")
    photo = get_photo_metadata(pid)
    if not photo:
        return P("Photo metadata not found", cls="text-slate-400")

    width, height = get_photo_dimensions(photo["filename"])
    has_dimensions = width > 0 and height > 0

    face_overlays = []
    identity_name = ensure_utf8_display(identity.get("name")) or "Unknown"
    if has_dimensions:
        for fd in photo["faces"]:
            fid = fd["face_id"]
            x1, y1, x2, y2 = fd["bbox"]
            lp = (x1 / width) * 100
            tp = (y1 / height) * 100
            wp = ((x2 - x1) / width) * 100
            hp = ((y2 - y1) / height) * 100
            fi = get_identity_for_face(registry, fid)
            is_t = fi and fi["identity_id"] == identity_id
            if is_t:
                oc = "absolute border-2 border-amber-500 bg-amber-500/20 cursor-pointer"
                lb = Span(identity_name, cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-amber-600 text-white text-xs px-2 py-0.5 rounded whitespace-nowrap pointer-events-none")
            else:
                dn = ensure_utf8_display(fi.get("name", "")) if fi else ""
                oc = "absolute border border-emerald-500/50 bg-emerald-500/5 group cursor-pointer hover:bg-emerald-500/15"
                lb = Span(dn or "Unknown", cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-xs px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none") if dn else None

            # Determine the correct section for navigation based on identity state
            fi_id = fi["identity_id"] if fi else None
            fi_section = _section_for_state(fi.get("state", "INBOX")) if fi else "to_review"

            # Click handler: navigate to the identity's face card in the correct section
            click_script = None
            if fi_id:
                click_script = (
                    f"on click halt the event's bubbling "
                    f"then add .hidden to #photo-modal "
                    f"then go to url '/?section={fi_section}&view=browse#identity-{fi_id}'"
                )

            face_overlays.append(Div(
                lb, cls=oc,
                style=f"left: {lp:.2f}%; top: {tp:.2f}%; width: {wp:.2f}%; height: {hp:.2f}%;",
                **{"_": click_script} if click_script else {},
            ))

    # Lightbox prev/next buttons use data-action for event delegation.
    # The global handler reads data-action and hx-get to dispatch navigation.
    prev_btn = Button(Span("\u25C0", cls="text-xl"), cls="absolute left-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white w-12 h-12 rounded-full flex items-center justify-center transition-colors z-10",
        hx_get=f"/api/identity/{identity_id}/photos?index={index - 1}", hx_target="#photo-modal-content", hx_swap="innerHTML",
        type="button", data_action="lightbox-prev") if index > 0 else None
    next_btn = Button(Span("\u25B6", cls="text-xl"), cls="absolute right-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white w-12 h-12 rounded-full flex items-center justify-center transition-colors z-10",
        hx_get=f"/api/identity/{identity_id}/photos?index={index + 1}", hx_target="#photo-modal-content", hx_swap="innerHTML",
        type="button", data_action="lightbox-next") if index < total - 1 else None

    # Touch swipe script only — keyboard is handled by global event delegation
    nav_script = Script(f"""(function(){{var el=document.getElementById('lightbox-photo-container');if(!el)return;var sx=0;el.addEventListener('touchstart',function(e){{sx=e.touches[0].clientX}});el.addEventListener('touchend',function(e){{var d=e.changedTouches[0].clientX-sx;if(Math.abs(d)>50){{if(d>0&&{index}>0)htmx.ajax('GET','/api/identity/{identity_id}/photos?index={index-1}',{{target:'#photo-modal-content',swap:'innerHTML'}});else if(d<0&&{index}<{total-1})htmx.ajax('GET','/api/identity/{identity_id}/photos?index={index+1}',{{target:'#photo-modal-content',swap:'innerHTML'}})}}}});}})();""")

    return Div(
        Div(Img(src=photo_url(photo["filename"]), alt=photo["filename"], cls="max-h-[80vh] max-w-full object-contain"),
            *face_overlays, prev_btn, next_btn, cls="relative inline-block", id="lightbox-photo-container"),
        Div(Span(f"{index + 1} / {total}", cls="text-white font-medium"),
            Span(f" -- {photo['filename']}", cls="text-slate-400 text-sm ml-2"),
            Span(identity_name, cls="text-amber-400 text-sm ml-4"), cls="mt-3 text-center"),
        nav_script, cls="flex flex-col items-center")


def _compare_photo_with_overlays(photo_url_str: str, photo_id: str, highlight_face_id: str, registry, img_height_cls: str) -> Div:
    """Render a photo with face bounding box overlays for the compare modal.

    Shows all faces in the photo with state-based colors. The face being
    compared (highlight_face_id) gets a bright amber highlight.
    """
    photo = get_photo_metadata(photo_id) if photo_id else None
    if not photo or not photo_url_str:
        return Div(
            Img(src=photo_url_str or "", cls=f"max-w-full {img_height_cls} object-contain rounded") if photo_url_str else Div(
                Span("?", cls="text-6xl text-slate-500"),
                cls="w-48 h-48 bg-slate-700 rounded flex items-center justify-center"),
            cls="flex justify-center bg-slate-700/50 rounded p-2")

    width, height = get_photo_dimensions(photo["filename"])
    has_dimensions = width > 0 and height > 0

    face_overlays = []
    if has_dimensions:
        for face_data in photo.get("faces", []):
            face_id = face_data["face_id"]
            bbox = face_data.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox

            left_pct = (x1 / width) * 100
            top_pct = (y1 / height) * 100
            width_pct = ((x2 - x1) / width) * 100
            height_pct = ((y2 - y1) / height) * 100

            identity = get_identity_for_face(registry, face_id)
            raw_name = identity.get("name", "Unidentified") if identity else "Unidentified"
            display_name = ensure_utf8_display(raw_name)
            identity_id = identity["identity_id"] if identity else None

            is_highlighted = face_id == highlight_face_id

            if is_highlighted:
                overlay_cls = "border-2 border-amber-400 bg-amber-400/25"
            elif identity:
                state = identity.get("state", "INBOX")
                if state == "CONFIRMED":
                    overlay_cls = "border-2 border-emerald-500/60 bg-emerald-500/10"
                elif state == "PROPOSED":
                    overlay_cls = "border-2 border-indigo-400/60 bg-indigo-400/10"
                else:
                    overlay_cls = "border-2 border-slate-400/60 bg-slate-400/5"
            else:
                overlay_cls = "border-2 border-dashed border-slate-400/40 bg-slate-400/5"

            # Click handler: navigate to identity card, closing the modal
            nav_section = _section_for_state(identity.get("state", "INBOX")) if identity else "to_review"
            click_script = (
                f"on click halt the event's bubbling "
                f"then add .hidden to #compare-modal "
                f"then go to url '/?section={nav_section}&view=browse#identity-{identity_id}'"
            ) if identity_id else ""

            overlay = Div(
                Span(
                    display_name,
                    cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10"
                ),
                cls=f"absolute cursor-pointer transition-all group {overlay_cls}",
                style=f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;",
                title=display_name,
                data_face_id=face_id,
                **{"_": click_script} if click_script else {},
            )
            face_overlays.append(overlay)

    return Div(
        Div(
            Img(src=photo_url_str, cls=f"max-w-full {img_height_cls} object-contain rounded"),
            *face_overlays,
            cls="relative inline-block max-w-full"),
        cls="flex justify-center bg-slate-700/50 rounded p-2")


@rt("/api/identity/{target_id}/compare/{neighbor_id}")
def get(target_id: str, neighbor_id: str, target_idx: int = 0, neighbor_idx: int = 0, view: str = "faces", filter: str = "", sess=None):
    """Side-by-side comparison view for evaluating merge candidates."""
    try:
        registry = load_registry()
        tgt = registry.get_identity(target_id)
        nbr = registry.get_identity(neighbor_id)
    except KeyError:
        return P("Identity not found", cls="text-red-400")
    crop_files = get_crop_files()
    tf = tgt.get("anchor_ids", []) + tgt.get("candidate_ids", [])
    nf = nbr.get("anchor_ids", []) + nbr.get("candidate_ids", [])
    if not tf or not nf:
        return P("No faces available for comparison", cls="text-slate-400")
    target_idx = max(0, min(target_idx, len(tf) - 1))
    neighbor_idx = max(0, min(neighbor_idx, len(nf) - 1))

    def _rf(entries, idx):
        e = entries[idx]
        fid = e if isinstance(e, str) else e.get("face_id", "")
        return fid, resolve_face_image_url(fid, crop_files)

    t_fid, t_url = _rf(tf, target_idx)
    n_fid, n_url = _rf(nf, neighbor_idx)
    t_name = ensure_utf8_display(tgt.get("name")) or f"Identity {target_id[:8]}..."
    n_name = ensure_utf8_display(nbr.get("name")) or f"Identity {neighbor_id[:8]}..."

    # Resolve photo IDs (always needed for View Photo links) and photo URLs (for photos view)
    t_photo_url = None
    n_photo_url = None
    _build_caches()
    t_photo_id = _face_to_photo_cache.get(t_fid, "")
    n_photo_id = _face_to_photo_cache.get(n_fid, "")
    if view == "photos":
        if t_photo_id and _photo_cache and t_photo_id in _photo_cache:
            t_photo_url = storage.get_photo_url(_photo_cache[t_photo_id].get("filename", ""))
        if n_photo_id and _photo_cache and n_photo_id in _photo_cache:
            n_photo_url = storage.get_photo_url(_photo_cache[n_photo_id].get("filename", ""))

    # Determine which image URLs to show
    t_display_url = t_photo_url if view == "photos" and t_photo_url else t_url
    n_display_url = n_photo_url if view == "photos" and n_photo_url else n_url

    # Section routing for clickable names
    t_section = _section_for_state(tgt.get("state", "INBOX"))
    n_section = _section_for_state(nbr.get("state", "INBOX"))
    _filter_suffix = f"&filter={filter}" if filter else ""

    def _cn(side, cur, tot, oth):
        if tot <= 1:
            return None
        b = f"/api/identity/{target_id}/compare/{neighbor_id}"
        if side == "t":
            pu = f"{b}?target_idx={cur-1}&neighbor_idx={oth}&view={view}{_filter_suffix}"
            nu = f"{b}?target_idx={cur+1}&neighbor_idx={oth}&view={view}{_filter_suffix}"
        else:
            pu = f"{b}?target_idx={oth}&neighbor_idx={cur-1}&view={view}{_filter_suffix}"
            nu = f"{b}?target_idx={oth}&neighbor_idx={cur+1}&view={view}{_filter_suffix}"
        pb = Button("\u2190", cls="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded text-sm",
                    hx_get=pu, hx_target="#compare-modal-content", hx_swap="innerHTML",
                    type="button") if cur > 0 else Button(
                    "\u2190", cls="px-2 py-1 text-slate-500 opacity-30 rounded text-sm", disabled=True, type="button")
        nb = Button("\u2192", cls="px-2 py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded text-sm",
                    hx_get=nu, hx_target="#compare-modal-content", hx_swap="innerHTML",
                    type="button") if cur < tot - 1 else Button(
                    "\u2192", cls="px-2 py-1 text-slate-500 opacity-30 rounded text-sm", disabled=True, type="button")
        return Div(pb, Span(f"{cur+1} of {tot}", cls="text-xs text-slate-400 mx-2"), nb,
                   cls="flex items-center justify-center gap-1 mt-2")

    # Face/Photo toggle
    base_url = f"/api/identity/{target_id}/compare/{neighbor_id}?target_idx={target_idx}&neighbor_idx={neighbor_idx}{_filter_suffix}"
    toggle = Div(
        Button("Faces",
               cls=f"px-3 py-1 text-xs font-medium rounded-l {'bg-amber-600 text-white' if view == 'faces' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}",
               hx_get=f"{base_url}&view=faces", hx_target="#compare-modal-content", hx_swap="innerHTML", type="button"),
        Button("Photos",
               cls=f"px-3 py-1 text-xs font-medium rounded-r {'bg-amber-600 text-white' if view == 'photos' else 'bg-slate-700 text-slate-300 hover:bg-slate-600'}",
               hx_get=f"{base_url}&view=photos", hx_target="#compare-modal-content", hx_swap="innerHTML", type="button"),
        cls="flex justify-center mb-4"
    )

    # Action buttons -- role-aware
    _role = _get_user_role(sess)
    if _role == "contributor":
        m_btn = Button("Suggest Merge", cls="px-4 py-2 text-sm font-bold bg-purple-600 text-white rounded hover:bg-purple-500",
            hx_post=f"/api/identity/{target_id}/suggest-merge/{neighbor_id}", hx_target=f"#neighbor-{neighbor_id}", hx_swap="outerHTML",
            **{"_": "on htmx:afterRequest add .hidden to #compare-modal"}, type="button")
    else:
        m_btn = Button("Merge", cls="px-4 py-2 text-sm font-bold bg-blue-600 text-white rounded hover:bg-blue-500",
            hx_post=f"/api/identity/{target_id}/merge/{neighbor_id}", hx_target=f"#identity-{target_id}", hx_swap="outerHTML",
            **{"_": "on htmx:afterRequest add .hidden to #compare-modal"}, type="button")
    ns_btn = Button("Not Same", cls="px-4 py-2 text-sm font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20",
        hx_post=f"/api/identity/{target_id}/reject/{neighbor_id}", hx_target=f"#neighbor-{neighbor_id}", hx_swap="outerHTML",
        **{"_": "on htmx:afterRequest add .hidden to #compare-modal"}, type="button")
    cl_btn = Button("Close", cls="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-600 rounded",
        **{"_": "on click add .hidden to #compare-modal"}, type="button")

    img_h = "max-h-[60vh]" if view == "photos" else "max-h-[50vh]"

    # Hyperscript for click-to-zoom on face crop images in compare modal
    _zoom_script = (
        "on click toggle .compare-crop-zoomed on me "
        "then if I match .compare-crop-zoomed "
        "set my style.transform to 'scale(2)' "
        "then set my style.cursor to 'zoom-out' "
        "else "
        "set my style.transform to 'scale(1)' "
        "then set my style.cursor to 'zoom-in' "
        "end"
    )

    # Build photo containers — with face overlays when in photos view
    if view == "photos" and t_photo_url:
        t_photo_div = _compare_photo_with_overlays(t_photo_url, t_photo_id, t_fid, registry, img_h)
    else:
        t_photo_div = Div(
            Img(src=t_display_url or "", alt=t_name,
                cls=f"max-w-full {img_h} object-contain rounded cursor-zoom-in transition-transform duration-200",
                data_compare_zoom="true",
                **{"_": _zoom_script}) if t_display_url else Div(
                Span("?", cls="text-6xl text-slate-500"),
                cls="w-48 h-48 bg-slate-700 rounded flex items-center justify-center"),
            cls="flex justify-center bg-slate-700/50 rounded p-2 overflow-hidden")

    if view == "photos" and n_photo_url:
        n_photo_div = _compare_photo_with_overlays(n_photo_url, n_photo_id, n_fid, registry, img_h)
    else:
        n_photo_div = Div(
            Img(src=n_display_url or "", alt=n_name,
                cls=f"max-w-full {img_h} object-contain rounded cursor-zoom-in transition-transform duration-200",
                data_compare_zoom="true",
                **{"_": _zoom_script}) if n_display_url else Div(
                Span("?", cls="text-6xl text-slate-500"),
                cls="w-48 h-48 bg-slate-700 rounded flex items-center justify-center"),
            cls="flex justify-center bg-slate-700/50 rounded p-2 overflow-hidden")

    # View Photo links — open the full photo lightbox from compare modal
    # Pass from_compare=1 so the photo view shows a "Back to Compare" button
    t_view_photo = Button(
        "View Photo \u2192",
        cls="text-xs text-amber-400/70 hover:text-amber-400 mt-1",
        hx_get=f"/photo/{t_photo_id}/partial?face={t_fid}&from_compare=1",
        hx_target="#photo-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #photo-modal then add .hidden to #compare-modal"},
        type="button",
    ) if t_photo_id else None
    n_view_photo = Button(
        "View Photo \u2192",
        cls="text-xs text-indigo-400/70 hover:text-indigo-400 mt-1",
        hx_get=f"/photo/{n_photo_id}/partial?face={n_fid}&from_compare=1",
        hx_target="#photo-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #photo-modal then add .hidden to #compare-modal"},
        type="button",
    ) if n_photo_id else None

    return Div(
        toggle,
        Div(
            Div(
                A(t_name, href=f"/?section={t_section}&current={target_id}{_filter_suffix}",
                  cls="text-sm font-medium text-amber-400 mb-2 text-center truncate block hover:underline",
                  **{"_": "on click add .hidden to #compare-modal"}),
                t_photo_div,
                t_view_photo,
                _cn("t", target_idx, len(tf), neighbor_idx),
                cls="flex-1 min-w-0"),
            Div(Span("vs", cls="text-slate-500 text-sm font-bold"), cls="flex items-center px-4"),
            Div(
                A(n_name, href=f"/?section={n_section}&current={neighbor_id}{_filter_suffix}",
                  cls="text-sm font-medium text-indigo-400 mb-2 text-center truncate block hover:underline",
                  **{"_": "on click add .hidden to #compare-modal"}),
                n_photo_div,
                n_view_photo,
                _cn("n", neighbor_idx, len(nf), target_idx),
                cls="flex-1 min-w-0"),
            cls="flex flex-col sm:flex-row gap-4 items-center sm:items-start"),
        Div(m_btn, ns_btn, cl_btn,
            cls="flex flex-wrap items-center justify-center gap-3 mt-6 pt-4 border-t border-slate-700"))


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
# ROUTES - IDENTITY NOTES
# =============================================================================

@rt("/api/identity/{identity_id}/notes")
def get(identity_id: str):
    """Get notes for an identity and show the notes panel."""
    try:
        registry = load_registry()
        notes = registry.get_notes(identity_id)
    except KeyError:
        return P("Identity not found.", cls="text-red-400 text-sm")

    note_items = [
        Div(
            P(n["text"], cls="text-sm text-slate-200"),
            Div(
                Span(n.get("author", ""), cls="text-xs text-slate-500"),
                Span(n.get("timestamp", "")[:10], cls="text-xs text-slate-500 ml-2"),
                cls="flex items-center mt-1"
            ),
            cls="p-2 bg-slate-700 rounded mb-1"
        )
        for n in reversed(notes)  # Newest first
    ]

    return Div(
        H5("Notes", cls="text-sm font-semibold text-slate-300 mb-2"),
        Div(*note_items) if note_items else P("No notes yet.", cls="text-xs text-slate-500 italic"),
        # Add note form
        Form(
            Input(
                type="text", name="text",
                placeholder="Add a note...",
                cls="w-full px-2 py-1.5 text-sm bg-slate-800 border border-slate-600 text-white rounded "
                    "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500",
                required=True,
            ),
            Button(
                "Add",
                type="submit",
                cls="mt-1 px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
            ),
            hx_post=f"/api/identity/{identity_id}/notes",
            hx_target=f"#notes-{identity_id}",
            hx_swap="innerHTML",
            cls="mt-2",
        ),
        id=f"notes-{identity_id}",
    )


@rt("/api/identity/{identity_id}/notes")
def post(identity_id: str, text: str = "", sess=None):
    """Add a note to an identity. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied

    text = text.strip()
    if not text:
        return toast("Note cannot be empty.", "warning")

    user_email = ""
    if sess:
        user = get_current_user(sess)
        if user:
            user_email = user.email

    try:
        registry = load_registry()
        registry.add_note(identity_id, text, author=user_email)
        save_registry(registry)
    except KeyError:
        return toast("Identity not found.", "error")
    except Exception as e:
        return toast(f"Failed to add note: {e}", "error")

    # Re-render the notes panel
    notes = registry.get_notes(identity_id)
    note_items = [
        Div(
            P(n["text"], cls="text-sm text-slate-200"),
            Div(
                Span(n.get("author", ""), cls="text-xs text-slate-500"),
                Span(n.get("timestamp", "")[:10], cls="text-xs text-slate-500 ml-2"),
                cls="flex items-center mt-1"
            ),
            cls="p-2 bg-slate-700 rounded mb-1"
        )
        for n in reversed(notes)
    ]

    return Div(
        H5("Notes", cls="text-sm font-semibold text-slate-300 mb-2"),
        Div(*note_items),
        Form(
            Input(
                type="text", name="text",
                placeholder="Add a note...",
                cls="w-full px-2 py-1.5 text-sm bg-slate-800 border border-slate-600 text-white rounded "
                    "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500",
                required=True,
            ),
            Button(
                "Add",
                type="submit",
                cls="mt-1 px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
            ),
            hx_post=f"/api/identity/{identity_id}/notes",
            hx_target=f"#notes-{identity_id}",
            hx_swap="innerHTML",
            cls="mt-2",
        ),
        id=f"notes-{identity_id}",
    )


@rt("/api/identity/{identity_id}/metadata-form")
def get(identity_id: str, sess=None):
    """Return an inline metadata edit form for an identity."""
    denied = _check_admin(sess)
    if denied:
        return denied

    try:
        registry = load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return toast("Identity not found.", "error")

    _input_cls = ("w-full px-2 py-1.5 text-sm bg-slate-700 border border-slate-600 text-white rounded "
                  "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500")

    return Div(
        Form(
            Div(
                Div(
                    Label("Maiden Name", cls="text-xs text-slate-400"),
                    Input(type="text", name="maiden_name", value=identity.get("maiden_name", ""),
                          placeholder="née ...", cls=_input_cls),
                    cls="flex-1"
                ),
                Div(
                    Label("Qualifier", cls="text-xs text-slate-400"),
                    Input(type="text", name="generation_qualifier", value=identity.get("generation_qualifier", ""),
                          placeholder="e.g. Sr., Jr.", cls=_input_cls),
                    cls="w-24"
                ),
                cls="flex gap-2"
            ),
            Div(
                Div(
                    Label("Birth Year", cls="text-xs text-slate-400"),
                    Input(type="text", name="birth_year", value=str(identity.get("birth_year", "")),
                          placeholder="e.g. 1920", cls=_input_cls),
                    cls="w-24"
                ),
                Div(
                    Label("Death Year", cls="text-xs text-slate-400"),
                    Input(type="text", name="death_year", value=str(identity.get("death_year", "")),
                          placeholder="e.g. 1995", cls=_input_cls),
                    cls="w-24"
                ),
                Div(
                    Label("Birthplace", cls="text-xs text-slate-400"),
                    Input(type="text", name="birth_place", value=identity.get("birth_place", ""),
                          placeholder="e.g. Rhodes, Greece", cls=_input_cls),
                    cls="flex-1"
                ),
                Div(
                    Label("Death Place", cls="text-xs text-slate-400"),
                    Input(type="text", name="death_place", value=identity.get("death_place", ""),
                          placeholder="e.g. Auschwitz", cls=_input_cls),
                    cls="flex-1"
                ),
                cls="flex gap-2 flex-wrap"
            ),
            Div(
                Label("Relationships", cls="text-xs text-slate-400"),
                Input(type="text", name="relationship_notes", value=identity.get("relationship_notes", ""),
                      placeholder="e.g. Daughter of X & Y, married to Z", cls=_input_cls),
            ),
            Div(
                Label("Bio", cls="text-xs text-slate-400"),
                Textarea(
                    identity.get("bio", ""),
                    name="bio", rows="2",
                    placeholder="Biographical notes...",
                    cls=_input_cls + " resize-y",
                ),
            ),
            Div(
                Button("Save", type="submit",
                       cls="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500"),
                Button("Cancel", type="button",
                       cls="px-3 py-1.5 text-xs bg-slate-600 text-slate-300 rounded hover:bg-slate-500",
                       hx_get=f"/api/identity/{identity_id}/metadata-display",
                       hx_target=f"#metadata-{identity_id}",
                       hx_swap="innerHTML"),
                cls="flex gap-2 mt-1"
            ),
            hx_post=f"/api/identity/{identity_id}/metadata",
            hx_target=f"#metadata-{identity_id}",
            hx_swap="innerHTML",
            cls="space-y-2",
        ),
        id=f"metadata-{identity_id}",
    )


@rt("/api/identity/{identity_id}/metadata-display")
def get(identity_id: str, sess=None):
    """Return the metadata display (non-form) for an identity."""
    try:
        registry = load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Span()
    is_admin = not _check_admin(sess)
    return _identity_metadata_display(identity, is_admin=is_admin)


@rt("/api/identity/{identity_id}/metadata")
def post(identity_id: str, birth_year: str = "", death_year: str = "",
         birth_place: str = "", death_place: str = "", maiden_name: str = "",
         generation_qualifier: str = "",
         relationship_notes: str = "", bio: str = "", sess=None):
    """Update identity metadata. Admin-only (BE-011)."""
    denied = _check_admin(sess)
    if denied:
        return denied

    metadata = {}
    if birth_year.strip():
        try:
            metadata["birth_year"] = int(birth_year.strip())
        except ValueError:
            pass
    if death_year.strip():
        try:
            metadata["death_year"] = int(death_year.strip())
        except ValueError:
            pass
    if birth_place.strip():
        metadata["birth_place"] = birth_place.strip()
    if death_place.strip():
        metadata["death_place"] = death_place.strip()
    if maiden_name.strip():
        metadata["maiden_name"] = maiden_name.strip()
    if generation_qualifier.strip():
        metadata["generation_qualifier"] = generation_qualifier.strip()
    if relationship_notes.strip():
        metadata["relationship_notes"] = relationship_notes.strip()
    if bio.strip():
        metadata["bio"] = bio.strip()

    if not metadata:
        return toast("No metadata provided.", "warning")

    try:
        registry = load_registry()
        registry.set_metadata(identity_id, metadata, user_source="admin_web")
        save_registry(registry)
        # Return updated display with success toast
        identity = registry.get_identity(identity_id)
        display = _identity_metadata_display(identity, is_admin=True)
        oob_toast = Div(
            toast(f"Metadata updated ({len(metadata)} field(s)).", "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (display, oob_toast)
    except KeyError:
        return toast("Identity not found.", "error")


@rt("/api/photo/{photo_id}/metadata")
def post(photo_id: str, date_taken: str = "", location: str = "",
         caption: str = "", occasion: str = "", donor: str = "",
         notes: str = "", back_image: str = "", back_transcription: str = "",
         sess=None):
    """Update photo metadata. Admin-only (BE-012)."""
    denied = _check_admin(sess)
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
        return toast("No metadata provided.", "warning")

    photo_registry = load_photo_registry()
    if not photo_registry.set_metadata(photo_id, metadata):
        return toast("Photo not found.", "error")
    save_photo_registry(photo_registry)

    return toast(f"Photo metadata updated ({len(metadata)} field(s)).", "success")


@rt("/api/photo/{photo_id}/back-image")
async def post(photo_id: str, file: UploadFile = None, back_transcription: str = "", sess=None):
    """Upload a back image for a photo and optionally add transcription. Admin-only."""
    denied = _check_admin(sess)
    if denied:
        return denied

    if not file or not file.filename:
        return toast("No file selected.", "warning")

    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return toast(f"File type '{ext}' not allowed. Use .jpg, .png, or .webp.", "error")

    # Read file content
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        return toast("File too large. Maximum is 50 MB.", "error")

    # Generate back image filename: {original_stem}_back{ext}
    photo_registry = load_photo_registry()
    photo = photo_registry.get_photo(photo_id)
    if not photo:
        return toast("Photo not found.", "error")

    original_path = photo.get("path", photo.get("filename", ""))
    original_stem = Path(original_path).stem
    back_filename = f"{original_stem}_back{ext}"

    # Save to raw_photos/ (local dev) or staging (production)
    raw_photos_dir = Path("raw_photos")
    if raw_photos_dir.exists():
        save_path = raw_photos_dir / back_filename
        save_path.write_bytes(content)
    else:
        # Staging for production upload
        staging_dir = data_path / "staging" / "back_images"
        staging_dir.mkdir(parents=True, exist_ok=True)
        save_path = staging_dir / back_filename
        save_path.write_bytes(content)

    # Update photo metadata
    metadata = {"back_image": back_filename}
    if back_transcription.strip():
        metadata["back_transcription"] = back_transcription.strip()
    photo_registry.set_metadata(photo_id, metadata)
    save_photo_registry(photo_registry)

    return Div(
        P(f"Back image uploaded: {back_filename}", cls="text-emerald-400 text-sm"),
        P("The 'Turn Over' button is now available on this photo.", cls="text-slate-400 text-xs mt-1"),
        cls="p-2",
    )


@rt("/api/photo/{photo_id}/back-transcription")
def post(photo_id: str, back_transcription: str = "", sess=None):
    """Update the back transcription for a photo. Admin-only."""
    denied = _check_admin(sess)
    if denied:
        return denied

    if not back_transcription.strip():
        return toast("No transcription provided.", "warning")

    photo_registry = load_photo_registry()
    if not photo_registry.set_metadata(photo_id, {"back_transcription": back_transcription.strip()}):
        return toast("Photo not found.", "error")
    save_photo_registry(photo_registry)

    return toast("Transcription saved.", "success")


@rt("/api/photo/{photo_id}/transform")
def post(photo_id: str, transform: str = "", field: str = "transform", sess=None):
    """Set non-destructive image transformation. Admin-only.

    transform: The transform to apply (e.g., 'rotate:90', 'flipH', 'reset')
    field: 'transform' (front image) or 'back_transform' (back image)
    """
    denied = _check_admin(sess)
    if denied:
        return denied

    if field not in {"transform", "back_transform"}:
        return toast("Invalid field.", "error")

    photo_registry = load_photo_registry()
    photo = photo_registry.get_photo(photo_id)
    if not photo:
        return toast("Photo not found.", "error")

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
    save_photo_registry(photo_registry)

    # Return the CSS transform for live preview
    css_transform = parse_transform_to_css(new_transform)
    css_filter = parse_transform_to_filter(new_transform)
    return Div(
        P(f"Transform: {new_transform}" if new_transform else "Transform reset.", cls="text-xs text-slate-400"),
        Script(f"""
            var img = document.querySelector('.photo-hero, .photo-flip-front img');
            if (img) {{
                img.style.transform = '{css_transform}';
                img.style.filter = '{css_filter}';
            }}
        """) if css_transform or css_filter or transform == "reset" else None,
        cls="mt-1",
    )


@rt("/api/onboarding/discover")
def get(surnames: str = ""):
    """Return HTML fragment showing confirmed identities matching selected surnames.

    Public endpoint — no auth required. Used by the onboarding modal.
    """
    if not surnames.strip():
        return Div(P("No surnames selected.", cls="text-sm text-slate-400"))

    surname_list = [s.strip() for s in surnames.split(",") if s.strip()]

    # Load surname variants for matching
    from core.registry import _load_surname_variants
    variant_lookup = _load_surname_variants()

    # Expand each surname to its variant group
    target_names = set()
    for surname in surname_list:
        target_names.add(surname.lower())
        variants = variant_lookup.get(surname.lower(), [])
        target_names.update(variants)

    # Find confirmed identities whose last name matches
    registry = load_registry()
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    crop_files = get_crop_files()

    matches = []
    for identity in confirmed:
        name = (identity.get("name") or "").strip()
        if not name or name.startswith("Unidentified"):
            continue
        # Check last name or any word in name
        name_words = [w.lower() for w in name.split()]
        if any(w in target_names for w in name_words):
            face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            crop_url = resolve_face_image_url(face_ids[0], crop_files) if face_ids else None
            if crop_url:
                matches.append({
                    "name": name,
                    "crop_url": crop_url,
                    "identity_id": identity["identity_id"],
                    "photo_count": len(face_ids),
                })

    if not matches:
        return Div(
            H3("No matches yet", cls="text-lg font-bold text-white mb-2"),
            P("We don't have confirmed identities with those surnames yet, "
              "but you can still help identify unknown faces!",
              cls="text-sm text-slate-400 mb-4"),
            Button("Continue", type="button", data_action="onboarding-continue",
                   cls="px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-500 w-full"),
        )

    # Show up to 6 matching people
    people_cards = []
    for m in matches[:6]:
        people_cards.append(
            A(
                Div(
                    Img(src=m["crop_url"], alt=m["name"],
                        cls="w-16 h-16 rounded-full object-cover border-2 border-amber-400/50"),
                    Div(
                        Span(m["name"], cls="text-sm font-medium text-white"),
                        Span(f"{m['photo_count']} photo{'s' if m['photo_count'] != 1 else ''}",
                             cls="text-xs text-slate-400"),
                        cls="flex flex-col",
                    ),
                    cls="flex items-center gap-3",
                ),
                href=f"/?section=confirmed&current={m['identity_id']}",
                cls="block p-2 rounded-lg hover:bg-slate-700/50 transition-colors",
                data_action="onboarding-close",
            )
        )

    return Div(
        H3(f"We found {len(matches)} {'person' if len(matches) == 1 else 'people'} "
           f"with those family names!",
           cls="text-lg font-bold text-white mb-3"),
        Div(*people_cards, cls="space-y-1 mb-4 max-h-64 overflow-y-auto"),
        P(f"{len(matches)} identified so far — can you help find more?",
          cls="text-xs text-slate-500 mb-3") if len(matches) > 6 else None,
        Button("Continue", type="button", data_action="onboarding-continue",
               cls="px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-500 w-full"),
    )


@rt("/api/photos/bulk-update-source")
def post(photo_ids: str = "[]", collection: str = "", source: str = "",
         source_url: str = "", sess=None):
    """Bulk update collection/source/source_url for multiple photos. Admin-only."""
    denied = _check_admin(sess)
    if denied:
        return denied

    if not collection.strip() and not source.strip() and not source_url.strip():
        return toast("Please provide collection, source, or source URL.", "warning")

    try:
        ids = json.loads(photo_ids)
    except (json.JSONDecodeError, TypeError):
        return toast("Invalid photo selection.", "error")

    if not ids:
        return toast("No photos selected.", "warning")

    photo_registry = load_photo_registry()
    updated = 0
    for pid in ids:
        if collection.strip():
            photo_registry.set_collection(pid, collection.strip())
        if source.strip():
            photo_registry.set_source(pid, source.strip())
        if source_url.strip():
            photo_registry.set_source_url(pid, source_url.strip())
        updated += 1
    save_photo_registry(photo_registry)

    # Invalidate photo cache so grid reflects changes
    global _photo_cache
    _photo_cache = None

    fields = []
    if collection.strip():
        fields.append(f"collection={collection.strip()}")
    if source.strip():
        fields.append(f"source={source.strip()}")
    if source_url.strip():
        fields.append("source_url")

    log_user_action("BULK_UPDATE_METADATA", count=updated, fields=", ".join(fields))

    return toast(f"Updated {updated} photo(s): {', '.join(fields)}.", "success")


# =============================================================================
# ROUTES - PROPOSED MATCHES
# =============================================================================

@rt("/api/identity/{identity_id}/propose-match")
def post(identity_id: str, target_id: str, note: str = "", sess=None):
    """Propose a match between two identities without executing it. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied

    user_email = ""
    if sess:
        user = get_current_user(sess)
        if user:
            user_email = user.email

    try:
        registry = load_registry()
        proposal = registry.add_proposed_match(identity_id, target_id, note=note, author=user_email)
        save_registry(registry)
    except KeyError:
        return toast("Identity not found.", "error")
    except Exception as e:
        return toast(f"Failed to propose match: {e}", "error")

    return toast(f"Match proposed!", "success")


@rt("/api/proposed-matches")
def get():
    """List all pending proposed matches."""
    try:
        registry = load_registry()
    except Exception:
        return P("Unable to load proposals.", cls="text-red-400")

    proposals = registry.list_proposed_matches()
    if not proposals:
        return Div(
            P("No pending proposals.", cls="text-slate-400 italic text-sm"),
            cls="text-center py-8"
        )

    crop_files = get_crop_files()
    items = []
    for p in proposals:
        source_name = ensure_utf8_display(p.get("source_name")) or f"Identity {p['source_id'][:8]}..."
        target_name = ensure_utf8_display(p.get("target_name")) or f"Identity {p['target_id'][:8]}..."

        items.append(Div(
            Div(
                Span(source_name, cls="text-sm font-medium text-slate-200"),
                Span(" → ", cls="text-slate-500"),
                Span(target_name, cls="text-sm font-medium text-slate-200"),
                cls="flex items-center gap-1"
            ),
            P(p.get("note", ""), cls="text-xs text-slate-400 mt-1") if p.get("note") else None,
            Div(
                Span(f"by {p.get('author', 'unknown')}", cls="text-xs text-slate-500"),
                Span(p.get("timestamp", "")[:10], cls="text-xs text-slate-500 ml-2"),
                cls="flex items-center mt-1"
            ),
            Div(
                Button(
                    "Accept (Merge)",
                    cls="px-2 py-1 text-xs bg-emerald-600 text-white rounded hover:bg-emerald-500",
                    hx_post=f"/api/proposed-matches/{p['source_id']}/{p['id']}/accept",
                    hx_target="#proposed-matches-list",
                    hx_swap="innerHTML",
                    type="button",
                ),
                Button(
                    "Reject",
                    cls="px-2 py-1 text-xs border border-red-400 text-red-400 rounded hover:bg-red-500/20",
                    hx_post=f"/api/proposed-matches/{p['source_id']}/{p['id']}/reject",
                    hx_target="#proposed-matches-list",
                    hx_swap="innerHTML",
                    type="button",
                ),
                cls="flex gap-2 mt-2"
            ),
            cls="p-3 bg-slate-800 border border-slate-700 rounded-lg mb-2"
        ))

    return Div(*items, id="proposed-matches-list")


@rt("/api/proposed-matches/{source_id}/{proposal_id}/accept")
def post(source_id: str, proposal_id: str, sess=None):
    """Accept a proposed match — execute the merge."""
    denied = _check_admin(sess)
    if denied:
        return denied

    try:
        registry = load_registry()
        photo_registry = load_photo_registry()

        # Get the proposal to find target_id
        identity = registry.get_identity(source_id)
        proposal = None
        for pm in identity.get("proposed_matches", []):
            if pm["id"] == proposal_id:
                proposal = pm
                break

        if not proposal:
            return toast("Proposal not found.", "error")

        target_id = proposal["target_id"]

        # Execute the merge
        result = registry.merge_identities(
            source_id=source_id,
            target_id=target_id,
            user_source="proposed_match",
            photo_registry=photo_registry,
        )

        if result["success"]:
            registry.resolve_proposed_match(source_id, proposal_id, "accepted")
            save_registry(registry)
            oob_toast = Div(
                toast(f"Merged! {_pl(result['faces_merged'], 'face')} combined.", "success"),
                hx_swap_oob="beforeend:#toast-container",
            )
        else:
            oob_toast = Div(
                toast(f"Cannot merge: {result['reason']}", "warning"),
                hx_swap_oob="beforeend:#toast-container",
            )
    except Exception as e:
        oob_toast = Div(
            toast(f"Error: {e}", "error"),
            hx_swap_oob="beforeend:#toast-container",
        )

    # Re-render the proposals list
    proposals = registry.list_proposed_matches()
    if not proposals:
        return (Div(
            P("No pending proposals.", cls="text-slate-400 italic text-sm"),
            cls="text-center py-8", id="proposed-matches-list"
        ), oob_toast)

    # Return a placeholder that triggers reload of the proposals list
    return (Div(
        P("Refreshing...", cls="text-slate-400"),
        hx_get="/api/proposed-matches",
        hx_trigger="load",
        hx_swap="outerHTML",
        id="proposed-matches-list"
    ), oob_toast)


@rt("/api/proposed-matches/{source_id}/{proposal_id}/reject")
def post(source_id: str, proposal_id: str, sess=None):
    """Reject a proposed match."""
    denied = _check_admin(sess)
    if denied:
        return denied

    try:
        registry = load_registry()
        registry.resolve_proposed_match(source_id, proposal_id, "rejected")
        save_registry(registry)
    except Exception as e:
        return toast(f"Error: {e}", "error")

    # Re-render with reload trigger
    return Div(
        P("Refreshing...", cls="text-slate-400"),
        hx_get="/api/proposed-matches",
        hx_trigger="load",
        hx_swap="outerHTML",
        id="proposed-matches-list"
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
        toast("Face moved to its own identity. Use Merge to combine them back.", "success"),
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
    Render the upload page. Requires login when auth is enabled.
    Non-admin uploads go through the moderation queue (pending_uploads.json).
    """
    denied = _check_login(sess)
    if denied:
        return denied
    user = get_current_user(sess or {})
    style = Style("""
        html, body {
            height: 100%;
            margin: 0;
            overflow-x: hidden;
        }
        body {
            background-color: #0f172a;
        }
        /* Mobile responsive layout */
        @media (max-width: 767px) {
            .mobile-header { display: flex !important; }
            .main-content { margin-left: 0 !important; padding-top: 3.5rem; }
            .main-content .main-inner { padding: 1rem; }
        }
        @media (min-width: 768px) and (max-width: 1023px) {
            .mobile-header { display: flex !important; }
            .main-content { margin-left: 0 !important; padding-top: 3.5rem; }
            .main-content .main-inner { padding: 1.5rem; }
        }
        @media (min-width: 1024px) {
            .mobile-header { display: none !important; }
            .main-content { margin-left: 16rem; }
        }
    """)

    # Canonical sidebar counts
    registry = load_registry()
    counts = _compute_sidebar_counts(registry)

    # Load existing sources and collections for autocomplete
    existing_sources = []
    existing_collections = []
    try:
        from core.photo_registry import PhotoRegistry
        photo_registry = PhotoRegistry.load(data_path / "photo_index.json")
        sources_set = set()
        collections_set = set()
        for photo_id in photo_registry._photos:
            source = photo_registry.get_source(photo_id)
            if source:
                sources_set.add(source)
            collection = photo_registry.get_collection(photo_id)
            if collection:
                collections_set.add(collection)
        existing_sources = sorted(sources_set)
        existing_collections = sorted(collections_set)
    except FileNotFoundError:
        pass  # No photos yet

    upload_style = Style("""
        .sidebar-container { width: 15rem; transition: width 0.2s ease, transform 0.3s ease; }
        .sidebar-container.collapsed { width: 3.5rem; }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results { display: none; }
        .sidebar-container.collapsed .sidebar-nav-item { justify-content: center; padding-left: 0; padding-right: 0; }
        .sidebar-container.collapsed .sidebar-icon { margin: 0; }
        .sidebar-container.collapsed .sidebar-chevron { transform: rotate(180deg); }
        .sidebar-container.collapsed .sidebar-collapse-btn { margin: 0 auto; }
        .sidebar-search-results:not(:empty) { position: absolute; left: 0.75rem; right: 0.75rem; top: 100%; background: #1e293b; border: 1px solid #334155; border-radius: 0.5rem; max-height: 300px; overflow-y: auto; z-index: 50; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        @media (max-width: 767px) {
            #sidebar { width: 15rem !important; transform: translateX(-100%); transition: transform 0.3s ease; }
            #sidebar.open { transform: translateX(0); }
            #sidebar .sidebar-label { display: inline !important; }
            #sidebar .sidebar-search { display: block !important; }
            .main-content { margin-left: 0 !important; }
        }
        @media (min-width: 768px) { #sidebar { transform: translateX(0); } }
        @media (min-width: 1024px) { .main-content { margin-left: 15rem; transition: margin-left 0.2s ease; } .main-content.sidebar-collapsed { margin-left: 3.5rem; } }
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
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
        (function() {
            try {
                var collapsed = localStorage.getItem('sidebar_collapsed') === 'true';
                if (collapsed && window.innerWidth >= 1024) {
                    var sb = document.getElementById('sidebar');
                    var mc = document.querySelector('.main-content');
                    if (sb) sb.classList.add('collapsed');
                    if (mc) mc.classList.add('sidebar-collapsed');
                }
            } catch(e) {}
        })();
    """)

    return Title("Upload Photos - Rhodesli"), style, upload_style, Div(
        toast_container(),
        mobile_header,
        sidebar_overlay,
        sidebar(counts, current_section=None, user=user),
        # Sidebar overlay for mobile
        Div(
            cls="fixed inset-0 bg-black bg-opacity-50 z-30 hidden",
            id="sidebar-overlay",
            onclick="closeSidebar()",
        ),
        Main(
            Div(
                # Header
                Div(
                    H2("Upload Photos", cls="text-2xl font-bold text-white"),
                    P("Add new photos for identity analysis", cls="text-sm text-slate-400 mt-1"),
                    cls="mb-6"
                ),
                # Upload form
                upload_area(existing_sources=existing_sources, existing_collections=existing_collections),
                cls="max-w-3xl mx-auto px-4 sm:px-8 py-6"
            ),
            cls="main-content min-h-screen overflow-x-hidden"
        ),
        sidebar_script,
        cls="h-full"
    )


@rt("/upload")
async def post(files: list[UploadFile], source: str = "", collection: str = "",
               source_url: str = "", sess=None):
    """
    Accept file upload(s) and optionally spawn subprocess for processing.
    Requires login. Non-admin uploads go to moderation queue.

    Handles multiple files (images and/or ZIPs) in a single batch job.
    All files are saved to a job directory.

    All uploads go to data/staging/{job_id}/.

    Admin flow:
        When PROCESSING_ENABLED=True (local dev):
            - Subprocess spawned to run core/ingest_inbox.py
            - Real-time status polling
        When PROCESSING_ENABLED=False (production):
            - No subprocess spawned (ML deps not available)
            - Shows "pending admin review" message

    Non-admin flow:
        - Pending upload record created in pending_uploads.json
        - Admin email notification sent (if RESEND_API_KEY configured)
        - Shows "submitted for review" message

    Args:
        files: Uploaded image files or ZIPs
        source: Provenance/origin label (e.g., "Newspapers.com")
        collection: Classification label (e.g., "Immigration Records")
        source_url: Citation URL (e.g., "https://newspapers.com/article/123")

    Returns HTML partial with upload status.
    """
    denied = _check_login(sess)
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

    # --- Upload safety checks ---
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file
    MAX_BATCH_SIZE = 500 * 1024 * 1024  # 500 MB per batch
    MAX_FILES_PER_UPLOAD = 50
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".zip"}

    if len(valid_files) > MAX_FILES_PER_UPLOAD:
        return Div(
            P(f"Too many files. Maximum {MAX_FILES_PER_UPLOAD} per upload.", cls="text-red-400 text-sm"),
            cls="p-2"
        )

    # Validate file extensions before reading content
    for f in valid_files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Div(
                P(f"File type '{ext}' not allowed. Accepted: images and .zip archives.", cls="text-red-400 text-sm"),
                cls="p-2"
            )

    # Determine if current user is admin
    user = get_current_user(sess or {})
    user_is_admin = user and user.is_admin if is_auth_enabled() else True
    uploader_email = user.email if user else "unknown"

    # Generate unique job ID
    job_id = str(uuid.uuid4())[:8]

    # All uploads go to staging first (processing or moderation)
    job_dir = data_path / "staging" / job_id

    job_dir.mkdir(parents=True, exist_ok=True)

    # Save all files to job directory with size checks
    saved_files = []
    total_size = 0
    for f in valid_files:
        # Sanitize filename
        safe_filename = f.filename.replace(" ", "_").replace("/", "_")
        upload_path = job_dir / safe_filename

        # Read and check file size
        content = await f.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE:
            # Clean up job dir on failure
            import shutil
            shutil.rmtree(job_dir, ignore_errors=True)
            mb = file_size / (1024 * 1024)
            return Div(
                P(f"File '{safe_filename}' is too large ({mb:.1f} MB). Maximum is 50 MB per file.", cls="text-red-400 text-sm"),
                cls="p-2"
            )

        total_size += file_size
        if total_size > MAX_BATCH_SIZE:
            import shutil
            shutil.rmtree(job_dir, ignore_errors=True)
            return Div(
                P("Total batch size exceeds 500 MB limit.", cls="text-red-400 text-sm"),
                cls="p-2"
            )

        with open(upload_path, "wb") as out:
            out.write(content)
        saved_files.append(safe_filename)

    # Save metadata for staged uploads (helps admin know context)
    metadata = {
        "job_id": job_id,
        "source": source or "Unknown",
        "collection": collection or "",
        "source_url": source_url or "",
        "files": saved_files,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "processing_enabled": PROCESSING_ENABLED,
        "uploader_email": uploader_email,
    }
    metadata_path = job_dir / "_metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Non-admin flow: create pending upload record and notify admin
    if not user_is_admin:
        pending = _load_pending_uploads()
        pending["uploads"][job_id] = {
            "job_id": job_id,
            "uploader_email": uploader_email,
            "source": source or "Unknown",
            "collection": collection or "",
            "source_url": source_url or "",
            "files": saved_files,
            "file_count": len(saved_files),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        _save_pending_uploads(pending)

        # Fire-and-forget email notification to admin
        try:
            await _notify_admin_upload(uploader_email, job_id, len(saved_files), source)
        except Exception:
            pass  # Email notification failure should never block upload

        file_count = len(saved_files)
        file_msg = f"1 photo" if file_count == 1 else f"{file_count} photos"

        return Div(
            Div(
                Span("✓", cls="text-green-400 text-lg"),
                P(f"Submitted {file_msg} for review", cls="text-slate-200 font-medium"),
                cls="flex items-center gap-2"
            ),
            P(
                "Your upload has been submitted for admin review. "
                "You'll see the photos once they are approved and processed.",
                cls="text-slate-400 text-sm mt-1"
            ),
            P(f"Reference: {job_id}", cls="text-slate-500 text-xs mt-2 font-mono"),
            cls="p-3 bg-green-900/20 border border-green-500/30 rounded"
        )

    # Admin flow: If processing is disabled (production), stage for local processing
    if not PROCESSING_ENABLED:
        file_count = len(saved_files)
        file_msg = f"1 photo" if file_count == 1 else f"{file_count} photos"

        # Create a pending upload record so it appears on the admin pending page
        pending = _load_pending_uploads()
        pending["uploads"][job_id] = {
            "job_id": job_id,
            "uploader_email": uploader_email,
            "source": source or "Unknown",
            "collection": collection or "",
            "source_url": source_url or "",
            "files": saved_files,
            "file_count": file_count,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "staged",
        }
        _save_pending_uploads(pending)

        # Build metadata detail line
        detail_parts = []
        if collection:
            detail_parts.append(f"Collection: {collection}")
        if source:
            detail_parts.append(f"Source: {source}")
        detail_line = " · ".join(detail_parts) if detail_parts else ""

        return Div(
            Div(
                Span("✓", cls="text-green-400 text-lg"),
                P(f"{file_msg} uploaded successfully", cls="text-slate-200 font-medium"),
                cls="flex items-center gap-2"
            ),
            P(detail_line, cls="text-slate-300 text-sm mt-1") if detail_line else None,
            P(
                "Staged for processing. Run the local pipeline to detect faces and push to production.",
                cls="text-slate-400 text-sm mt-1"
            ),
            A(
                "View in Pending Uploads →",
                href="/admin/pending",
                cls="inline-block text-blue-400 hover:text-blue-300 text-sm mt-2 underline"
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
    if collection:
        subprocess_args.extend(["--collection", collection])

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
                    P(f"{_pl(faces, 'face')} found so far", cls="text-slate-400 text-xs mt-1")
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
                f"\u2713 {_pl(faces, 'face')} extracted from {succeeded}/{total} images",
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

    success_text = f"\u2713 {_pl(faces, 'face')} extracted"
    if total and total > 1:
        success_text = f"\u2713 {_pl(faces, 'face')} extracted from {_pl(total, 'image')}"
    success_text += f", {identities} added to Inbox"

    return Div(
        P(success_text, cls="text-emerald-400 text-sm font-medium"),
        A("Refresh to see inbox", href="/", cls="text-indigo-400 hover:underline text-xs ml-2"),
        cls="p-2 bg-emerald-900/30 border border-emerald-500/30 rounded flex items-center"
    )


# =============================================================================
# ROUTES - ADMIN PENDING UPLOADS REVIEW
# =============================================================================


@rt("/admin/pending")
def get(sess=None):
    """
    Admin page to review pending uploads from non-admin users.
    Requires admin when auth is enabled.
    """
    denied = _check_admin(sess)
    if denied:
        return denied
    user = get_current_user(sess or {})

    style = Style("""
        html, body { height: 100%; margin: 0; }
        body { background-color: #0f172a; }
    """)

    # Canonical sidebar counts
    registry = load_registry()
    counts = _compute_sidebar_counts(registry)

    # Load pending uploads (both contributor "pending" and admin "staged")
    pending = _load_pending_uploads()
    pending_items = [u for u in pending["uploads"].values() if u["status"] in ("pending", "staged")]
    # Sort by submitted_at descending (newest first)
    pending_items.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)

    # Also show recently reviewed items
    reviewed_items = [u for u in pending["uploads"].values() if u["status"] in ("approved", "rejected")]
    reviewed_items.sort(key=lambda x: x.get("reviewed_at", x.get("submitted_at", "")), reverse=True)
    reviewed_items = reviewed_items[:10]  # Show last 10

    # Build pending cards
    if pending_items:
        pending_cards = []
        for item in pending_items:
            job_id = item["job_id"]
            file_count = item.get("file_count", len(item.get("files", [])))
            file_msg = f"1 file" if file_count == 1 else f"{file_count} files"
            is_staged = item.get("status") == "staged"
            collection_label = item.get("collection", "")
            source_label = item.get("source", "Unknown")
            detail_parts = [file_msg]
            if collection_label:
                detail_parts.append(f"Collection: {collection_label}")
            if source_label and source_label != "Unknown":
                detail_parts.append(f"Source: {source_label}")
            detail_line = " · ".join(detail_parts)

            # Staged items (admin uploads) show status badge, no approve/reject
            # Pending items (contributor uploads) show approve/reject buttons
            if is_staged:
                actions = Div(
                    Span("Staged", cls="px-2 py-1 bg-blue-600/30 text-blue-300 text-xs font-bold rounded uppercase"),
                    Button(
                        "Mark Processed",
                        hx_post=f"/admin/pending/{job_id}/mark-processed",
                        hx_target=f"#pending-card-{job_id}",
                        hx_swap="outerHTML",
                        cls="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded hover:bg-green-500 transition-colors"
                    ),
                    cls="flex gap-2 items-start"
                )
            else:
                actions = Div(
                    Button(
                        "Approve",
                        hx_post=f"/admin/pending/{job_id}/approve",
                        hx_target=f"#pending-card-{job_id}",
                        hx_swap="outerHTML",
                        cls="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded hover:bg-green-500 transition-colors"
                    ),
                    Button(
                        "Reject",
                        hx_post=f"/admin/pending/{job_id}/reject",
                        hx_target=f"#pending-card-{job_id}",
                        hx_swap="outerHTML",
                        cls="px-3 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-500 transition-colors"
                    ),
                    cls="flex gap-2 items-start"
                )

            # Photo preview thumbnails (served via admin-authenticated endpoint)
            preview_thumbs = []
            upload_files = item.get("files", [])
            from urllib.parse import quote
            for fname in upload_files[:6]:
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    thumb_url = f"/admin/staging-preview/{quote(job_id)}/{quote(fname)}"
                    # Graceful fallback: show filename label if image fails to load
                    preview_thumbs.append(
                        Div(
                            Img(src=thumb_url, alt=fname, loading="lazy",
                                cls="w-16 h-16 object-cover rounded border border-slate-600",
                                title=fname,
                                onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'"),
                            Div(fname[:12], cls="w-16 h-16 bg-slate-700 border border-slate-600 rounded text-[8px] text-slate-400 items-center justify-center text-center p-1 hidden"),
                            cls="flex-shrink-0"
                        )
                    )
            remaining = len(upload_files) - 6
            if remaining > 0:
                preview_thumbs.append(
                    Div(f"+{remaining}", cls="w-16 h-16 flex items-center justify-center rounded border border-slate-600 text-slate-400 text-sm bg-slate-800")
                )
            preview_row = Div(*preview_thumbs, cls="flex gap-2 mt-3 flex-wrap") if preview_thumbs else None

            pending_cards.append(
                Div(
                    Div(
                        Div(
                            P(item.get("uploader_email", "Unknown"), cls="text-slate-200 font-medium text-sm"),
                            P(detail_line, cls="text-slate-400 text-xs"),
                            P(f"Submitted: {item.get('submitted_at', 'Unknown')[:19].replace('T', ' ')}", cls="text-slate-500 text-xs mt-0.5"),
                            P(f"Job ID: {job_id}", cls="text-slate-600 text-xs font-mono"),
                            cls="flex-1"
                        ),
                        actions,
                        cls="flex items-start justify-between gap-4"
                    ),
                    preview_row,
                    id=f"pending-card-{job_id}",
                    cls="p-4 bg-slate-800 border border-slate-700 rounded-lg"
                )
            )
        pending_section = Div(*pending_cards, cls="space-y-3")
    else:
        pending_section = Div(
            P("No pending uploads.", cls="text-slate-500 text-sm"),
            cls="p-4 bg-slate-800/50 border border-slate-700/50 rounded-lg"
        )

    # Build reviewed history cards
    if reviewed_items:
        reviewed_cards = []
        for item in reviewed_items:
            status_color = "green" if item["status"] == "approved" else "red"
            status_label = "Approved" if item["status"] == "approved" else "Rejected"
            file_count = item.get("file_count", len(item.get("files", [])))
            file_msg = f"1 file" if file_count == 1 else f"{file_count} files"
            reviewed_cards.append(
                Div(
                    Div(
                        Span(status_label, cls=f"text-{status_color}-400 text-xs font-bold uppercase"),
                        Span(" | ", cls="text-slate-600"),
                        Span(item.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
                        Span(f" | {file_msg}", cls="text-slate-500 text-xs"),
                        cls="flex items-center gap-1"
                    ),
                    cls="px-3 py-2 bg-slate-800/30 border border-slate-700/30 rounded"
                )
            )
        reviewed_section = Div(
            H3("Recently Reviewed", cls="text-lg font-semibold text-slate-300 mb-3 mt-6"),
            *reviewed_cards,
            cls="space-y-2"
        )
    else:
        reviewed_section = None

    # Sidebar styles (same as upload page)
    page_style = Style("""
        .sidebar-container { width: 15rem; transition: width 0.2s ease, transform 0.3s ease; }
        .sidebar-container.collapsed { width: 3.5rem; }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results { display: none; }
        .sidebar-container.collapsed .sidebar-nav-item { justify-content: center; padding-left: 0; padding-right: 0; }
        .sidebar-container.collapsed .sidebar-icon { margin: 0; }
        .sidebar-container.collapsed .sidebar-chevron { transform: rotate(180deg); }
        .sidebar-container.collapsed .sidebar-collapse-btn { margin: 0 auto; }
        .sidebar-search-results:not(:empty) { position: absolute; left: 0.75rem; right: 0.75rem; top: 100%; background: #1e293b; border: 1px solid #334155; border-radius: 0.5rem; max-height: 300px; overflow-y: auto; z-index: 50; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        @media (max-width: 767px) {
            #sidebar { width: 15rem !important; transform: translateX(-100%); transition: transform 0.3s ease; }
            #sidebar.open { transform: translateX(0); }
            #sidebar .sidebar-label { display: inline !important; }
            #sidebar .sidebar-search { display: block !important; }
            .main-content { margin-left: 0 !important; }
        }
        @media (min-width: 768px) { #sidebar { transform: translateX(0); } }
        @media (min-width: 1024px) { .main-content { margin-left: 15rem; transition: margin-left 0.2s ease; } .main-content.sidebar-collapsed { margin-left: 3.5rem; } }
    """)
    mobile_header = Div(
        Button(
            Svg(Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2",
                     d="M4 6h16M4 12h16M4 18h16"),
                cls="w-6 h-6", fill="none", stroke="currentColor", viewBox="0 0 24 24"),
            onclick="toggleSidebar()",
            cls="p-2 text-slate-300 hover:text-white min-h-[44px] min-w-[44px] flex items-center justify-center"
        ),
        Span("Pending Uploads", cls="text-lg font-bold text-white"),
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
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
        (function() {
            try {
                var collapsed = localStorage.getItem('sidebar_collapsed') === 'true';
                if (collapsed && window.innerWidth >= 1024) {
                    var sb = document.getElementById('sidebar');
                    var mc = document.querySelector('.main-content');
                    if (sb) sb.classList.add('collapsed');
                    if (mc) mc.classList.add('sidebar-collapsed');
                }
            } catch(e) {}
        })();
    """)

    return Title("Pending Uploads - Rhodesli"), style, page_style, Div(
        toast_container(),
        mobile_header,
        sidebar_overlay,
        sidebar(counts, current_section="pending_uploads", user=user),
        Main(
            Div(
                # Header
                Div(
                    H2("Pending Uploads", cls="text-2xl font-bold text-white"),
                    P(f"{len(pending_items)} upload{'s' if len(pending_items) != 1 else ''} awaiting review", cls="text-sm text-slate-400 mt-1"),
                    cls="mb-6"
                ),
                pending_section,
                reviewed_section if reviewed_section else "",
                cls="max-w-3xl mx-auto px-4 sm:px-8 py-6"
            ),
            cls="main-content min-h-screen overflow-x-hidden"
        ),
        sidebar_script,
        cls="h-full"
    )


@rt("/admin/proposals")
def get(sess=None):
    """
    Admin page to review proposed identity matches.
    Requires admin when auth is enabled.
    """
    denied = _check_admin(sess)
    if denied:
        return denied
    user = get_current_user(sess or {})

    style = Style("""
        html, body { height: 100%; margin: 0; }
        body { background-color: #0f172a; }
    """)

    # Canonical sidebar counts
    registry = load_registry()
    counts = _compute_sidebar_counts(registry)

    # Sidebar styles (reuse)
    page_style = Style("""
        .sidebar-container { width: 15rem; transition: width 0.2s ease, transform 0.3s ease; }
        .sidebar-container.collapsed { width: 3.5rem; }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results { display: none; }
        .sidebar-container.collapsed .sidebar-nav-item { justify-content: center; padding-left: 0; padding-right: 0; }
        .sidebar-container.collapsed .sidebar-icon { margin: 0; }
        .sidebar-container.collapsed .sidebar-chevron { transform: rotate(180deg); }
        .sidebar-container.collapsed .sidebar-collapse-btn { margin: 0 auto; }
        .sidebar-search-results:not(:empty) { position: absolute; left: 0.75rem; right: 0.75rem; top: 100%; background: #1e293b; border: 1px solid #334155; border-radius: 0.5rem; max-height: 300px; overflow-y: auto; z-index: 50; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        @media (max-width: 767px) {
            #sidebar { width: 15rem !important; transform: translateX(-100%); transition: transform 0.3s ease; }
            #sidebar.open { transform: translateX(0); }
            #sidebar .sidebar-label { display: inline !important; }
            #sidebar .sidebar-search { display: block !important; }
            .main-content { margin-left: 0 !important; }
        }
        @media (min-width: 768px) { #sidebar { transform: translateX(0); } }
        @media (min-width: 1024px) { .main-content { margin-left: 15rem; transition: margin-left 0.2s ease; } .main-content.sidebar-collapsed { margin-left: 3.5rem; } }
    """)
    mobile_header = Div(
        Button(
            Svg(Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2",
                     d="M4 6h16M4 12h16M4 18h16"),
                cls="w-6 h-6", fill="none", stroke="currentColor", viewBox="0 0 24 24"),
            onclick="toggleSidebar()",
            cls="p-2 text-slate-300 hover:text-white min-h-[44px] min-w-[44px] flex items-center justify-center"
        ),
        Span("Proposals", cls="text-lg font-bold text-white"),
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
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
        (function() {
            try {
                var collapsed = localStorage.getItem('sidebar_collapsed') === 'true';
                if (collapsed && window.innerWidth >= 1024) {
                    var sb = document.getElementById('sidebar');
                    var mc = document.querySelector('.main-content');
                    if (sb) sb.classList.add('collapsed');
                    if (mc) mc.classList.add('sidebar-collapsed');
                }
            } catch(e) {}
        })();
    """)

    return Title("Proposals - Rhodesli"), style, page_style, Div(
        toast_container(),
        mobile_header,
        sidebar_overlay,
        sidebar(counts, current_section="proposals", user=user),
        Main(
            Div(
                Div(
                    H2("Proposed Matches", cls="text-2xl font-bold text-white"),
                    P(f"{counts['proposals']} pending proposal{'s' if counts['proposals'] != 1 else ''}", cls="text-sm text-slate-400 mt-1"),
                    cls="mb-6"
                ),
                # Load proposals list via HTMX on page load
                Div(
                    id="proposed-matches-list",
                    hx_get="/api/proposed-matches",
                    hx_trigger="load",
                    hx_swap="innerHTML",
                ),
                cls="max-w-3xl mx-auto px-4 sm:px-8 py-6"
            ),
            cls="main-content min-h-screen overflow-x-hidden"
        ),
        sidebar_script,
        cls="h-full"
    )


@rt("/admin/pending/{job_id}/approve")
def post(job_id: str, sess=None):
    """Approve a pending upload. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied

    pending = _load_pending_uploads()
    if job_id not in pending["uploads"]:
        return Div(
            P("Upload not found.", cls="text-red-400 text-sm"),
            cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg"
        )

    upload = pending["uploads"][job_id]
    if upload["status"] != "pending":
        return Div(
            P(f"Upload already {upload['status']}.", cls="text-slate-400 text-sm"),
            cls="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg"
        )

    # Update status to approved
    upload["status"] = "approved"
    upload["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    user = get_current_user(sess or {})
    upload["reviewed_by"] = user.email if user else "unknown"
    _save_pending_uploads(pending)

    # If PROCESSING_ENABLED, move files from staging to uploads and spawn processing
    if PROCESSING_ENABLED:
        import shutil
        staging_dir = data_path / "staging" / job_id
        uploads_dir = data_path / "uploads" / job_id
        if staging_dir.exists():
            uploads_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staging_dir, uploads_dir, dirs_exist_ok=True)

            # Spawn processing subprocess (same as admin upload flow)
            import os
            import subprocess
            subprocess_env = os.environ.copy()
            existing_pythonpath = subprocess_env.get("PYTHONPATH", "")
            if existing_pythonpath:
                subprocess_env["PYTHONPATH"] = f"{project_root}{os.pathsep}{existing_pythonpath}"
            else:
                subprocess_env["PYTHONPATH"] = str(project_root)

            source = upload.get("source", "")
            upload_collection = upload.get("collection", "")
            subprocess_args = [
                sys.executable, "-m", "core.ingest_inbox",
                "--directory", str(uploads_dir),
                "--job-id", job_id,
            ]
            if source:
                subprocess_args.extend(["--source", source])
            if upload_collection:
                subprocess_args.extend(["--collection", upload_collection])

            subprocess.Popen(
                subprocess_args,
                cwd=project_root,
                env=subprocess_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    file_count = upload.get("file_count", len(upload.get("files", [])))
    return Div(
        Div(
            Span("Approved", cls="text-green-400 text-xs font-bold uppercase"),
            Span(" | ", cls="text-slate-600"),
            Span(upload.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
            Span(f" | {file_count} file{'s' if file_count != 1 else ''}", cls="text-slate-500 text-xs"),
            cls="flex items-center gap-1"
        ),
        cls="p-3 bg-green-900/20 border border-green-500/30 rounded-lg"
    )


@rt("/admin/pending/{job_id}/reject")
def post(job_id: str, sess=None):
    """Reject a pending upload. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied

    pending = _load_pending_uploads()
    if job_id not in pending["uploads"]:
        return Div(
            P("Upload not found.", cls="text-red-400 text-sm"),
            cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg"
        )

    upload = pending["uploads"][job_id]
    if upload["status"] != "pending":
        return Div(
            P(f"Upload already {upload['status']}.", cls="text-slate-400 text-sm"),
            cls="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg"
        )

    # Update status to rejected
    upload["status"] = "rejected"
    upload["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    user = get_current_user(sess or {})
    upload["reviewed_by"] = user.email if user else "unknown"
    _save_pending_uploads(pending)

    # Optionally clean up staging files
    import shutil
    staging_dir = data_path / "staging" / job_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)

    file_count = upload.get("file_count", len(upload.get("files", [])))
    return Div(
        Div(
            Span("Rejected", cls="text-red-400 text-xs font-bold uppercase"),
            Span(" | ", cls="text-slate-600"),
            Span(upload.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
            Span(f" | {file_count} file{'s' if file_count != 1 else ''}", cls="text-slate-500 text-xs"),
            cls="flex items-center gap-1"
        ),
        cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg"
    )


@rt("/admin/pending/{job_id}/mark-processed")
def post(job_id: str, sess=None):
    """Mark a staged upload as processed. Requires admin."""
    denied = _check_admin(sess)
    if denied:
        return denied

    pending = _load_pending_uploads()
    if job_id not in pending["uploads"]:
        return Div(
            P("Upload not found.", cls="text-red-400 text-sm"),
            cls="p-3 bg-red-900/20 border border-red-500/30 rounded-lg"
        )

    upload = pending["uploads"][job_id]
    if upload["status"] != "staged":
        return Div(
            P(f"Upload already {upload['status']}.", cls="text-slate-400 text-sm"),
            cls="p-3 bg-slate-800/50 border border-slate-700/50 rounded-lg"
        )

    upload["status"] = "processed"
    upload["processed_at"] = datetime.now(timezone.utc).isoformat()
    user = get_current_user(sess or {})
    upload["processed_by"] = user.email if user else "unknown"
    _save_pending_uploads(pending)

    file_count = upload.get("file_count", len(upload.get("files", [])))
    return Div(
        Div(
            Span("Processed", cls="text-green-400 text-xs font-bold uppercase"),
            Span(" | ", cls="text-slate-600"),
            Span(upload.get("uploader_email", "Unknown"), cls="text-slate-400 text-xs"),
            Span(f" | {file_count} file{'s' if file_count != 1 else ''}", cls="text-slate-500 text-xs"),
            cls="flex items-center gap-1"
        ),
        cls="p-3 bg-green-900/20 border border-green-500/30 rounded-lg"
    )


@app.get("/admin/staging-preview/{job_id}/{filename:path}")
async def admin_staging_preview(job_id: str, filename: str, sess=None):
    """Serve staged upload photos for admin preview. Session-authenticated."""
    denied = _check_admin(sess)
    if denied:
        return Response("Unauthorized", status_code=401)

    # Security: block path traversal
    if ".." in job_id or ".." in filename or job_id.startswith("/") or filename.startswith("/"):
        return Response("Invalid path", status_code=400)

    staging_dir = data_path / "staging"
    target = (staging_dir / job_id / filename).resolve()

    # Ensure resolved path is still inside staging dir
    if not str(target).startswith(str(staging_dir.resolve())):
        return Response("Invalid path", status_code=400)

    if not target.exists() or not target.is_file():
        return Response("File not found", status_code=404)

    # Determine content type from extension
    ext = target.suffix.lower()
    content_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    content_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(str(target), media_type=content_type)

# Move staging preview route before FastHTML's catch-all static route
for i, route in enumerate(app.routes):
    if getattr(route, "path", None) == "/admin/staging-preview/{job_id}/{filename:path}":
        _staging_route = app.routes.pop(i)
        app.routes.insert(0, _staging_route)
        break


# =============================================================================
# ROUTES - INBOX REVIEW (existing)
# =============================================================================


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
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
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
            get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
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
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
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
            get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
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
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
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
            get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
            toast("Skipped for later.", "info"),
        )

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    return (
        identity_card(updated_identity, crop_files, lane_color="stone", show_actions=False),
        toast("Skipped for later.", "info"),
    )


# =============================================================================
# ROUTES — SKIPPED FOCUS MODE ACTIONS
# =============================================================================

@rt("/api/skipped/{identity_id}/focus-skip")
def post(identity_id: str, sess=None):
    """Advance to next identity in skipped focus mode without taking action."""
    denied = _check_admin(sess)
    if denied:
        return denied
    return (
        get_next_skipped_focus_card(exclude_id=identity_id),
        toast("Skipped for now.", "info"),
    )


@rt("/api/skipped/{identity_id}/reject-suggestion")
def post(identity_id: str, suggestion_id: str = "", sess=None):
    """Reject a suggestion for a skipped identity and advance to next."""
    denied = _check_admin(sess)
    if denied:
        return denied

    if suggestion_id:
        try:
            registry = load_registry()
            registry.reject_identity_pair(identity_id, suggestion_id, user_source="skipped_focus")
            save_registry(registry)
        except (KeyError, ValueError):
            # If reject fails, just advance — don't block the user
            pass

    # Toast with undo for reject action
    reject_toast = Div(
        Span("✗", cls="mr-2"),
        Span("Suggestion rejected. Moving to next.", cls="flex-1"),
        Button(
            "Undo",
            cls="ml-3 px-2 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"/api/identity/{identity_id}/unreject/{suggestion_id}",
            hx_swap="outerHTML",
            hx_target="closest div",
            type="button",
        ) if suggestion_id else None,
        cls="px-4 py-3 rounded shadow-lg flex items-center bg-amber-600 text-white animate-fade-in",
        **{"_": "on load wait 8s then remove me"},
    )

    return (
        get_next_skipped_focus_card(exclude_id=identity_id),
        reject_toast,
    )


@rt("/api/skipped/{identity_id}/name-and-confirm")
def post(identity_id: str, name: str = "", sess=None):
    """Name a skipped identity and confirm it, then advance to next in focus mode."""
    denied = _check_admin(sess)
    if denied:
        return denied

    name = name.strip()
    if not name:
        return Response(
            to_xml(toast("Please enter a name.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry = load_registry()
        registry.rename_identity(identity_id, name, user_source="web_review")
        registry.confirm_identity(identity_id, user_source="web_review")
        save_registry(registry)
    except (KeyError, ValueError) as e:
        return Response(
            to_xml(toast(f"Cannot confirm: {str(e)}", "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    log_user_action("CONFIRM_NAMED", identity_id=identity_id, name=name)

    return (
        get_next_skipped_focus_card(exclude_id=identity_id),
        toast(f"Confirmed as {name}!", "success"),
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
def get(sess, next: str = ""):
    """Login page. Redirects to home if already authenticated or auth disabled."""
    if not is_auth_enabled():
        return RedirectResponse('/', status_code=303)
    if sess.get('auth'):
        return RedirectResponse(next or '/', status_code=303)

    # Build POST action with ?next= if provided
    post_action = "/login"
    if next:
        post_action = f"/login?next={next}"

    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Login - Rhodesli"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
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
                    method="post", action=post_action, cls="space-y-2"
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
async def post(email: str, password: str, sess, next: str = ""):
    """Handle login form submission."""
    user, error = await login_with_supabase(email, password)
    if error:
        return Html(
            Head(
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Title("Login - Rhodesli"),
                Script(src="https://cdn.tailwindcss.com"),
            ),
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
    # Redirect to the page they were trying to reach, or home
    redirect_to = next if next and next.startswith('/') else '/'
    return RedirectResponse(redirect_to, status_code=303)


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
        # Submit any pending annotation stashed before OAuth login
        _submit_pending_annotation(sess, user)
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


# =============================================================================
# ML EVALUATION DASHBOARD (admin-only)
# =============================================================================

@rt("/admin/ml-dashboard")
def get(sess=None):
    """ML evaluation dashboard. Shows golden set stats, thresholds, identity counts."""
    denied = _check_admin(sess)
    if denied:
        return denied

    registry = load_registry()

    # Identity stats by state
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    skipped = registry.list_identities(state=IdentityState.SKIPPED)
    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    rejected = registry.list_identities(state=IdentityState.REJECTED)

    total_identities = len(confirmed) + len(skipped) + len(inbox) + len(proposed) + len(rejected)
    total_faces = sum(
        len(i.get("anchor_ids", [])) + len(i.get("candidate_ids", []))
        for i in confirmed + skipped + inbox + proposed
    )

    # Golden set stats
    gs_stats = _load_golden_set_stats()
    eval_stats = _load_evaluation_stats()

    # Recent actions from event log
    recent_actions = _load_recent_actions(limit=10)

    # Build stat cards
    stat_cards = Div(
        _stat_card("Confirmed", str(len(confirmed)), "emerald"),
        _stat_card("Skipped", str(len(skipped)), "amber"),
        _stat_card("New Matches", str(len(inbox) + len(proposed)), "blue"),
        _stat_card("Rejected", str(len(rejected)), "red"),
        _stat_card("Total Faces", str(total_faces), "slate"),
        _stat_card("Identities", str(total_identities), "indigo"),
        cls="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8"
    )

    # Golden set section
    if gs_stats:
        gs_section = Div(
            H3("Golden Set", cls="text-lg font-semibold text-white mb-3"),
            Div(
                _stat_card("Mappings", str(gs_stats.get("total_mappings", 0)), "purple"),
                _stat_card("Identities", str(gs_stats.get("unique_identities", 0)), "purple"),
                _stat_card("Photos", str(gs_stats.get("unique_photos", 0)), "purple"),
                cls="grid grid-cols-3 gap-4"
            ),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
        )
    else:
        gs_section = Div(
            H3("Golden Set", cls="text-lg font-semibold text-white mb-3"),
            P("No golden set data available. Run: python scripts/build_golden_set.py",
              cls="text-slate-400 text-sm"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
        )

    # Golden set diversity section (ML-011)
    diversity_path = data_path / "golden_set_diversity.json"
    if diversity_path.exists():
        try:
            import json as _json
            with open(diversity_path) as f:
                diversity = _json.load(f)
            diversity_section = Div(
                H3("Golden Set Diversity (ML-011)", cls="text-lg font-semibold text-white mb-3"),
                Div(
                    _stat_card("Multi-face", str(diversity.get("multi_face_identities", 0)), "blue"),
                    _stat_card("Single-face", str(diversity.get("single_face_identities", 0)), "amber"),
                    _stat_card("Same Pairs", str(diversity.get("same_person_pairs", 0)), "green"),
                    _stat_card("Collections", str(diversity.get("collections", 0)), "purple"),
                    cls="grid grid-cols-4 gap-4"
                ),
                P(f"Same-person pairs: {diversity.get('same_person_pairs', 0)} | "
                  f"Different-person pairs: {diversity.get('different_person_pairs', 0)}",
                  cls="text-xs text-slate-400 mt-2"),
                cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
            )
        except Exception:
            diversity_section = Span()
    else:
        diversity_section = Div(
            H3("Golden Set Diversity", cls="text-lg font-semibold text-white mb-3"),
            P("Run: python scripts/analyze_golden_set.py", cls="text-slate-400 text-sm"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
        )

    # Threshold section
    threshold_section = Div(
        H3("Calibrated Thresholds (AD-013)", cls="text-lg font-semibold text-white mb-3"),
        Div(
            _threshold_row("VERY HIGH", MATCH_THRESHOLD_VERY_HIGH, "100%", "~13%", "emerald"),
            _threshold_row("HIGH", MATCH_THRESHOLD_HIGH, "100%", "~63%", "green"),
            _threshold_row("MODERATE", MATCH_THRESHOLD_MODERATE, "~94%", "~81%", "amber"),
            _threshold_row("MEDIUM", MATCH_THRESHOLD_MEDIUM, "~87%", "~87%", "orange"),
            cls="space-y-2"
        ),
        cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
    )

    # Evaluation results
    if eval_stats:
        eval_section = Div(
            H3("Last Evaluation", cls="text-lg font-semibold text-white mb-3"),
            P(f"Zero-FP ceiling: {eval_stats.get('zero_fp_ceiling', 'N/A')}",
              cls="text-sm text-slate-300"),
            P(f"Optimal F1 threshold: {eval_stats.get('optimal_f1_threshold', 'N/A')}",
              cls="text-sm text-slate-300"),
            P(eval_stats.get("statistical_note", ""), cls="text-xs text-slate-400 mt-2"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
        )
    else:
        eval_section = Div(
            H3("Evaluation", cls="text-lg font-semibold text-white mb-3"),
            P("No evaluation data. Run: python scripts/evaluate_golden_set.py",
              cls="text-slate-400 text-sm"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
        )

    # Recent actions
    if recent_actions:
        action_rows = [
            Div(
                Span(a.get("action", "?"), cls="text-xs font-mono bg-slate-700 px-2 py-0.5 rounded text-slate-300"),
                Span(a.get("timestamp", "")[:19], cls="text-xs text-slate-500 ml-2"),
                Span(a.get("detail", ""), cls="text-xs text-slate-400 ml-2"),
                cls="flex items-center gap-1"
            )
            for a in recent_actions
        ]
        actions_section = Div(
            H3("Recent Actions", cls="text-lg font-semibold text-white mb-3"),
            Div(*action_rows, cls="space-y-1"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
        )
    else:
        actions_section = Div(
            H3("Recent Actions", cls="text-lg font-semibold text-white mb-3"),
            P("No recent actions logged.", cls="text-slate-400 text-sm"),
            cls="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6"
        )

    return Title("ML Dashboard — Rhodesli"), Div(
        Div(
            H1("ML Evaluation Dashboard", cls="text-2xl font-bold text-white"),
            A("Back to Dashboard", href="/?section=to_review",
              cls="text-sm text-indigo-400 hover:text-indigo-300"),
            cls="flex items-center justify-between mb-6"
        ),
        stat_cards,
        gs_section,
        diversity_section,
        threshold_section,
        eval_section,
        actions_section,
        cls="max-w-5xl mx-auto p-6"
    )


def _stat_card(label: str, value: str, color: str) -> Div:
    """Small stat card for the ML dashboard."""
    color_map = {
        "emerald": "border-emerald-500 text-emerald-400",
        "amber": "border-amber-500 text-amber-400",
        "blue": "border-blue-500 text-blue-400",
        "red": "border-red-500 text-red-400",
        "slate": "border-slate-500 text-slate-300",
        "indigo": "border-indigo-500 text-indigo-400",
        "purple": "border-purple-500 text-purple-400",
        "green": "border-green-500 text-green-400",
        "orange": "border-orange-500 text-orange-400",
    }
    cls = color_map.get(color, "border-slate-500 text-slate-300")
    return Div(
        Div(value, cls=f"text-2xl font-bold {cls.split()[-1]}"),
        Div(label, cls="text-xs text-slate-400 mt-1"),
        cls=f"bg-slate-800 rounded-lg p-4 border-l-4 {cls.split()[0]}"
    )


def _threshold_row(label: str, value: float, precision: str, recall: str, color: str) -> Div:
    """Single threshold row in the dashboard."""
    return Div(
        Span(label, cls=f"text-sm font-medium text-{color}-400 w-24"),
        Span(f"< {value}", cls="text-sm font-mono text-white w-16"),
        Span(f"Precision: {precision}", cls="text-xs text-slate-400 w-28"),
        Span(f"Recall: {recall}", cls="text-xs text-slate-400"),
        cls="flex items-center gap-4"
    )


def _load_golden_set_stats() -> dict:
    """Load golden set stats from data file."""
    gs_path = data_path / "golden_set.json"
    if not gs_path.exists():
        return {}
    try:
        import json as _json
        with open(gs_path) as f:
            gs = _json.load(f)
        return gs.get("stats", {})
    except Exception:
        return {}


def _load_evaluation_stats() -> dict:
    """Load the most recent evaluation results."""
    # Find the most recent evaluation file
    eval_files = sorted(data_path.glob("golden_set_evaluation_*.json"), reverse=True)
    if not eval_files:
        return {}
    try:
        import json as _json
        with open(eval_files[0]) as f:
            return _json.load(f)
    except Exception:
        return {}


def _load_recent_actions(limit: int = 10) -> list:
    """Load recent user actions from the event log."""
    log_path = data_path / "event_log.jsonl"
    if not log_path.exists():
        return []
    try:
        lines = log_path.read_text().strip().split("\n")
        recent = lines[-limit:] if len(lines) > limit else lines
        recent.reverse()  # Most recent first
        import json as _json
        actions = []
        for line in recent:
            if not line.strip():
                continue
            try:
                event = _json.load(io.StringIO(line))
                actions.append({
                    "action": event.get("event_type", event.get("action", "?")),
                    "timestamp": event.get("timestamp", ""),
                    "detail": event.get("identity_id", event.get("target_id", ""))[:12],
                })
            except Exception:
                continue
        return actions
    except Exception:
        return []


# =============================================================================
# ANNOTATION SYSTEM (contributor submissions + admin review)
# =============================================================================

# Annotation data stored in data/annotations.json
_annotations_cache = None

def _load_annotations() -> dict:
    """Load annotations from data file.

    Returns default empty structure if file is missing or corrupted,
    so the server never crashes on bad annotation data.
    """
    global _annotations_cache
    if _annotations_cache is not None:
        return _annotations_cache
    ann_path = data_path / "annotations.json"
    default = {"schema_version": 1, "annotations": {}}
    if ann_path.exists():
        import json as _json
        try:
            with open(ann_path) as f:
                _annotations_cache = _json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f"Failed to load annotations from {ann_path}: {e}")
            _annotations_cache = default
    else:
        _annotations_cache = default
    return _annotations_cache


def _save_annotations(data: dict):
    """Save annotations atomically."""
    global _annotations_cache
    ann_path = data_path / "annotations.json"
    import json as _json
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(data_path), suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(ann_path))
        _annotations_cache = data
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _invalidate_annotations_cache():
    """Clear annotations cache after write."""
    global _annotations_cache
    _annotations_cache = None


def _create_merge_suggestion(target_id: str, source_id: str, submitted_by: str,
                             confidence: str = "likely", reason: str = "") -> str:
    """Create a merge_suggestion annotation. Returns the annotation ID."""
    import uuid
    from datetime import datetime, timezone
    ann_id = str(uuid.uuid4())
    annotations = _load_annotations()
    annotations["annotations"][ann_id] = {
        "annotation_id": ann_id,
        "type": "merge_suggestion",
        "target_type": "identity",
        "target_id": target_id,
        "value": json.dumps({"source_id": source_id, "target_id": target_id}),
        "confidence": confidence,
        "reason": reason,
        "submitted_by": submitted_by,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    _save_annotations(annotations)
    return ann_id


def _photo_metadata_display(photo: dict):
    """Display stored photo metadata fields (BE-012)."""
    metadata_fields = {
        "date_taken": "Date",
        "location": "Location",
        "caption": "Caption",
        "occasion": "Occasion",
        "donor": "Donor",
        "camera": "Camera",
    }
    items = []
    for key, label in metadata_fields.items():
        value = photo.get(key)
        if value:
            items.append(P(
                Span(f"{label}: ", cls="text-slate-500"),
                Span(str(value), cls="text-slate-300"),
                cls="text-xs"
            ))
    if not items:
        return Span()
    return Div(*items, cls="mt-2 space-y-0.5")


def _photo_annotations_section(photo_id: str, is_admin: bool = False):
    """
    AN-002–AN-006: Show approved photo annotations and a form to add new ones.
    Displays captions, dates, locations, stories, source attributions.
    """
    try:
        annotations = _load_annotations()
    except Exception:
        annotations = {"annotations": {}}

    # Get approved annotations for this photo
    photo_anns = [
        ann for ann in annotations.get("annotations", {}).values()
        if ann.get("target_type") == "photo"
        and ann.get("target_id") == photo_id
        and ann.get("status") == "approved"
    ]

    # Also get pending count for admin badge (includes guest submissions)
    pending_count = sum(
        1 for ann in annotations.get("annotations", {}).values()
        if ann.get("target_type") == "photo"
        and ann.get("target_id") == photo_id
        and ann.get("status") in ("pending", "pending_unverified")
    )

    # Display approved annotations grouped by type
    type_labels = {
        "caption": "Caption",
        "date": "Date",
        "location": "Location",
        "story": "Story",
        "source": "Source",
    }
    ann_items = []
    for ann in sorted(photo_anns, key=lambda a: a.get("submitted_at", "")):
        label = type_labels.get(ann["type"], ann["type"].title())
        ann_items.append(Div(
            Span(f"{label}: ", cls="text-slate-400 text-xs font-medium"),
            Span(ann["value"], cls="text-slate-300 text-xs"),
            cls="py-1"
        ))

    # Annotation submission form (available to any logged-in user)
    form = Div(
        Details(
            Summary("Add annotation", cls="text-xs text-indigo-400 hover:text-indigo-300 cursor-pointer"),
            Form(
                Input(type="hidden", name="target_type", value="photo"),
                Input(type="hidden", name="target_id", value=photo_id),
                Div(
                    Select(
                        Option("Caption", value="caption"),
                        Option("Date", value="date"),
                        Option("Location", value="location"),
                        Option("Story", value="story"),
                        Option("Source/Donor", value="source"),
                        name="annotation_type",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1 w-full",
                    ),
                    cls="mt-2"
                ),
                Div(
                    Textarea(
                        name="value",
                        placeholder="Enter annotation...",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1 w-full h-16 resize-none",
                        required=True,
                    ),
                    cls="mt-1"
                ),
                Div(
                    Select(
                        Option("Certain", value="certain"),
                        Option("Likely", value="likely", selected=True),
                        Option("Guess", value="guess"),
                        name="confidence",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1",
                    ),
                    Button(
                        "Submit",
                        type="submit",
                        cls="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1 rounded",
                    ),
                    cls="mt-1 flex gap-2 items-center"
                ),
                hx_post="/api/annotations/submit",
                hx_target=f"#photo-annotations-{photo_id}",
                hx_swap="outerHTML",
                cls="mt-2",
            ),
            cls="mt-2",
        ),
        cls="mt-2"
    )

    pending_badge = Span(
        f" ({pending_count} pending)",
        cls="text-amber-400 text-xs"
    ) if pending_count and is_admin else None

    return Div(
        *ann_items,
        form,
        pending_badge,
        id=f"photo-annotations-{photo_id}",
        cls="mt-3 border-t border-slate-700 pt-2" if ann_items else "mt-2",
    )


def _identity_metadata_display(identity: dict, is_admin: bool = False):
    """AN-012: Display identity metadata fields (bio, birth/death, relationships)."""
    identity_id = identity.get("identity_id", "")

    # Build compact summary line: "~1890–1944 · Rhodes → Auschwitz"
    summary_parts = []
    birth_year = identity.get("birth_year")
    death_year = identity.get("death_year")
    if birth_year and death_year:
        summary_parts.append(f"{birth_year}–{death_year}")
    elif birth_year:
        summary_parts.append(f"b. {birth_year}")
    elif death_year:
        summary_parts.append(f"d. {death_year}")

    birth_place = identity.get("birth_place")
    death_place = identity.get("death_place")
    if birth_place and death_place:
        summary_parts.append(f"{birth_place} \u2192 {death_place}")
    elif birth_place:
        summary_parts.append(birth_place)
    elif death_place:
        summary_parts.append(death_place)

    maiden_name = identity.get("maiden_name")
    if maiden_name:
        summary_parts.append(f"n\u00e9e {maiden_name}")

    items = []
    if summary_parts:
        items.append(P(
            " \u00b7 ".join(summary_parts),
            cls="text-xs text-slate-400 italic"
        ))

    # Additional fields shown below the summary
    detail_fields = {
        "relationship_notes": "Relationships",
        "bio": "Bio",
    }
    for key, label in detail_fields.items():
        value = identity.get(key)
        if value:
            items.append(P(
                Span(f"{label}: ", cls="text-slate-500"),
                Span(str(value), cls="text-slate-300"),
                cls="text-xs"
            ))

    # Edit button for admins
    edit_btn = None
    if is_admin and identity_id:
        edit_btn = Button(
            "Edit Details" if not items else "Edit",
            cls="text-xs text-indigo-400 hover:text-indigo-300 underline",
            hx_get=f"/api/identity/{identity_id}/metadata-form",
            hx_target=f"#metadata-{identity_id}",
            hx_swap="innerHTML",
            type="button",
        )

    if not items and not edit_btn:
        return Span()

    return Div(
        Div(*items, cls="space-y-0.5") if items else None,
        edit_btn,
        id=f"metadata-{identity_id}",
        cls="mt-2",
    )


def _identity_annotations_section(identity_id: str, is_admin: bool = False):
    """
    AN-013/AN-014: Show approved identity annotations and submission form.
    Displays bio, relationship, story, and other identity-level annotations.
    """
    try:
        annotations = _load_annotations()
    except Exception:
        annotations = {"annotations": {}}

    # Get approved annotations for this identity
    identity_anns = [
        ann for ann in annotations.get("annotations", {}).values()
        if ann.get("target_type") == "identity"
        and ann.get("target_id") == identity_id
        and ann.get("status") == "approved"
    ]

    # Pending count for admin badge (includes guest submissions)
    pending_count = sum(
        1 for ann in annotations.get("annotations", {}).values()
        if ann.get("target_type") == "identity"
        and ann.get("target_id") == identity_id
        and ann.get("status") in ("pending", "pending_unverified")
    )

    # Display approved annotations grouped by type
    type_labels = {
        "bio": "Bio",
        "relationship": "Relationship",
        "story": "Story",
        "name_suggestion": "Name Suggestion",
        "caption": "Caption",
    }
    ann_items = []
    for ann in sorted(identity_anns, key=lambda a: a.get("submitted_at", "")):
        label = type_labels.get(ann["type"], ann["type"].title())
        ann_items.append(Div(
            Span(f"{label}: ", cls="text-slate-400 text-xs font-medium"),
            Span(ann["value"], cls="text-slate-300 text-xs"),
            cls="py-1"
        ))

    # Annotation submission form
    form = Div(
        Details(
            Summary("Add annotation", cls="text-xs text-indigo-400 hover:text-indigo-300 cursor-pointer"),
            Form(
                Input(type="hidden", name="target_type", value="identity"),
                Input(type="hidden", name="target_id", value=identity_id),
                Div(
                    Select(
                        Option("Bio", value="bio"),
                        Option("Relationship", value="relationship"),
                        Option("Story", value="story"),
                        Option("Caption", value="caption"),
                        name="annotation_type",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1 w-full",
                    ),
                    cls="mt-2"
                ),
                Div(
                    Textarea(
                        name="value",
                        placeholder="Enter annotation...",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1 w-full h-16 resize-none",
                        required=True,
                    ),
                    cls="mt-1"
                ),
                Div(
                    Select(
                        Option("Certain", value="certain"),
                        Option("Likely", value="likely", selected=True),
                        Option("Guess", value="guess"),
                        name="confidence",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1",
                    ),
                    Button(
                        "Submit",
                        type="submit",
                        cls="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1 rounded",
                    ),
                    cls="mt-1 flex gap-2 items-center"
                ),
                hx_post="/api/annotations/submit",
                hx_target=f"#identity-annotations-{identity_id}",
                hx_swap="outerHTML",
                cls="mt-2",
            ),
            cls="mt-2",
        ),
        cls="mt-2"
    )

    pending_badge = Span(
        f" ({pending_count} pending)",
        cls="text-amber-400 text-xs"
    ) if pending_count and is_admin else None

    return Div(
        *ann_items,
        form,
        pending_badge,
        id=f"identity-annotations-{identity_id}",
        cls="mt-3 border-t border-slate-700 pt-2" if ann_items else "mt-2",
    )


def _merge_annotations(source_id: str, target_id: str):
    """
    BE-006: When identities merge, retarget annotations from source to target.
    Annotations that targeted the source identity are updated to point at the target.
    This preserves contributor work across merges.
    """
    try:
        annotations = _load_annotations()
        changed = False
        for ann in annotations.get("annotations", {}).values():
            if ann.get("target_type") == "identity" and ann.get("target_id") == source_id:
                ann["target_id"] = target_id
                changed = True
        if changed:
            _save_annotations(annotations)
    except Exception:
        # Non-critical — don't block the merge
        pass


@rt("/api/annotations/submit")
def post(target_type: str, target_id: str, annotation_type: str,
         value: str, confidence: str = "likely", reason: str = "", sess=None):
    """
    Submit an annotation. Saves directly for all users — no modal interruption.
    Anonymous users save as pending_unverified; logged-in users save as pending.
    Types: name_suggestion, caption, date, location, story, relationship
    """
    # Validate value BEFORE auth check — empty input is always 400
    if not value or not value.strip():
        return Response(
            to_xml(toast("Please provide a value.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    user = get_current_user(sess) if sess is not None else None

    import uuid
    from datetime import datetime, timezone
    ann_id = str(uuid.uuid4())

    # Determine status and submitter based on auth state
    if user:
        submitted_by = user.email
        status = "pending"
    elif is_auth_enabled():
        submitted_by = "anonymous"
        status = "pending_unverified"
    else:
        submitted_by = "local_dev"
        status = "pending"

    annotations = _load_annotations()
    annotations["annotations"][ann_id] = {
        "annotation_id": ann_id,
        "type": annotation_type,
        "target_type": target_type,  # "identity" or "photo"
        "target_id": target_id,
        "value": value.strip(),
        "confidence": confidence,
        "reason": reason.strip() if reason else "",
        "submitted_by": submitted_by,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reviewed_by": None,
        "reviewed_at": None,
    }
    _save_annotations(annotations)

    return Response(
        to_xml(toast("Thanks! Your suggestion has been submitted for review.", "success")),
        headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
    )


def _submit_pending_annotation(sess, user) -> bool:
    """Submit a stashed annotation from session. Returns True if submitted."""
    pending = sess.get("pending_annotation")
    if not pending:
        return False

    import uuid
    from datetime import datetime, timezone
    ann_id = str(uuid.uuid4())

    annotations = _load_annotations()
    annotations["annotations"][ann_id] = {
        "annotation_id": ann_id,
        "type": pending.get("annotation_type", "name_suggestion"),
        "target_type": pending.get("target_type", "identity"),
        "target_id": pending.get("target_id", ""),
        "value": pending.get("value", "").strip(),
        "confidence": pending.get("confidence", "likely"),
        "reason": pending.get("reason", "").strip(),
        "submitted_by": user.email,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    _save_annotations(annotations)
    del sess["pending_annotation"]
    return True


@rt("/api/annotations/guest-submit")
def post(target_type: str, target_id: str, annotation_type: str,
         value: str, confidence: str = "likely", reason: str = ""):
    """Save an annotation as anonymous guest. No auth required."""
    if not value or not value.strip():
        return Response(
            to_xml(toast("Please provide a value.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    import uuid
    from datetime import datetime, timezone
    ann_id = str(uuid.uuid4())

    annotations = _load_annotations()
    annotations["annotations"][ann_id] = {
        "annotation_id": ann_id,
        "type": annotation_type,
        "target_type": target_type,
        "target_id": target_id,
        "value": value.strip(),
        "confidence": confidence,
        "reason": reason.strip() if reason else "",
        "submitted_by": "anonymous",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_unverified",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    _save_annotations(annotations)

    # Clear the modal and show toast
    return Response(
        to_xml(Div(
            toast("Thanks! Your suggestion is pending admin review.", "success"),
            id="guest-or-login-modal",
            hx_swap_oob="true",
        )),
        headers={"HX-Retarget": "#guest-or-login-modal", "HX-Reswap": "innerHTML"}
    )


@rt("/api/annotations/stash-and-login")
def post(target_type: str, target_id: str, annotation_type: str,
         value: str, confidence: str = "likely", reason: str = "", sess=None):
    """Stash annotation in session and show login form."""
    if sess is not None:
        sess["pending_annotation"] = {
            "target_type": target_type,
            "target_id": target_id,
            "annotation_type": annotation_type,
            "value": value,
            "confidence": confidence,
            "reason": reason,
        }

    google_url = get_oauth_url("google")

    return Div(
        Div(
            H2("Sign in to save", cls="text-xl font-bold text-white"),
            Button("X", cls="text-slate-400 hover:text-white text-xl font-bold",
                   **{"_": "on click set #guest-or-login-modal's innerHTML to ''"},
                   type="button", aria_label="Close"),
            cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700"
        ),
        Div(
            P("Your suggestion:", cls="text-slate-500 text-xs"),
            P(f'"{value}"', cls="text-slate-300 text-sm font-medium"),
            cls="bg-slate-700/50 rounded p-3 mb-4"
        ),
        Form(
            Div(
                Label("Email", fr="guest-email", cls="block text-sm mb-1 text-slate-300"),
                Input(type="email", name="email", id="guest-email", required=True,
                      cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600"),
                cls="mb-4"
            ),
            Div(
                Label("Password", fr="guest-password", cls="block text-sm mb-1 text-slate-300"),
                Input(type="password", name="password", id="guest-password", required=True,
                      cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600"),
                cls="mb-4"
            ),
            Button("Sign in & submit", type="submit",
                   cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium"),
            Div(id="guest-login-error", cls="text-red-400 text-sm mt-2"),
            hx_post="/api/annotations/login-and-submit",
            hx_target="#guest-login-error",
            hx_swap="innerHTML",
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
        Div(
            P(
                "No account? ",
                A("Sign up with invite code", href="/signup", cls="text-blue-400 hover:underline"),
                cls="text-sm text-slate-400"
            ),
            cls="mt-4 text-center"
        ),
        cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-8 relative border border-slate-700"
    )


@rt("/api/annotations/login-and-submit")
async def post(email: str, password: str, sess):
    """Authenticate and submit the stashed annotation."""
    user, error = await login_with_supabase(email, password)
    if error:
        return error
    sess['auth'] = user
    _submit_pending_annotation(sess, user)
    return Response("", headers={"HX-Refresh": "true"})


@rt("/my-contributions")
def get(sess=None):
    """User's annotation history."""
    denied = _check_login(sess)
    if denied:
        return RedirectResponse("/login", status_code=303)

    user = get_current_user(sess)
    if not user:
        return RedirectResponse("/login", status_code=303)

    annotations = _load_annotations()
    my_anns = [
        a for a in annotations["annotations"].values()
        if a.get("submitted_by") == user.email
    ]
    my_anns.sort(key=lambda a: a.get("submitted_at", ""), reverse=True)

    rows = []
    for a in my_anns:
        status_cls = {
            "pending": "text-amber-400 bg-amber-900/30",
            "approved": "text-emerald-400 bg-emerald-900/30",
            "rejected": "text-red-400 bg-red-900/30",
        }.get(a["status"], "text-slate-400")

        rows.append(Div(
            Div(
                Span(a["type"].replace("_", " ").title(), cls="text-sm font-medium text-white"),
                Span(a["status"].upper(), cls=f"text-xs px-2 py-0.5 rounded ml-2 {status_cls}"),
                cls="flex items-center"
            ),
            P(f'"{a["value"]}"', cls="text-sm text-slate-300 mt-1"),
            P(f'Submitted {a["submitted_at"][:10]}', cls="text-xs text-slate-500"),
            cls="bg-slate-800 rounded-lg p-4 border border-slate-700"
        ))

    if not rows:
        rows = [Div(
            P("No contributions yet.", cls="text-slate-400"),
            P("Visit a photo or identity page to suggest names, dates, or stories.",
              cls="text-sm text-slate-500 mt-2"),
            cls="text-center py-12"
        )]

    return Title("My Contributions — Rhodesli"), Div(
        Div(
            H1("My Contributions", cls="text-2xl font-bold text-white"),
            A("Back to Dashboard", href="/?section=to_review",
              cls="text-sm text-indigo-400 hover:text-indigo-300"),
            cls="flex items-center justify-between mb-6"
        ),
        Div(*rows, cls="space-y-3"),
        cls="max-w-3xl mx-auto p-6"
    )


@rt("/admin/approvals")
def get(sess=None):
    """Admin page for reviewing pending annotations."""
    denied = _check_admin(sess)
    if denied:
        return denied

    annotations = _load_annotations()
    pending = [
        a for a in annotations["annotations"].values()
        if a.get("status") in ("pending", "pending_unverified")
    ]
    # Sort: authenticated ("pending") before guest ("pending_unverified"), newest first within each group
    pending.sort(key=lambda a: a.get("submitted_at", ""), reverse=True)
    pending.sort(key=lambda a: 0 if a.get("status") == "pending" else 1)

    rows = []
    crop_files = get_crop_files()
    registry = load_registry()
    for a in pending:
        ann_id = a["annotation_id"]
        is_guest = a.get("submitted_by") == "anonymous"
        guest_badge = Span(
            "Guest", cls="text-xs bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full ml-2"
        ) if is_guest else None

        # Merge suggestions get special rendering with face thumbnails
        if a["type"] == "merge_suggestion":
            try:
                merge_data = json.loads(a["value"])
                t_id = merge_data.get("target_id", a["target_id"])
                s_id = merge_data.get("source_id", "")
                t_identity = registry.get_identity(t_id)
                s_identity = registry.get_identity(s_id)
                t_name = ensure_utf8_display(t_identity.get("name", "")) or f"Identity {t_id[:8]}"
                s_name = ensure_utf8_display(s_identity.get("name", "")) or f"Identity {s_id[:8]}"
                # Get face thumbnails
                t_faces = t_identity.get("anchor_ids", []) + t_identity.get("candidate_ids", [])
                s_faces = s_identity.get("anchor_ids", []) + s_identity.get("candidate_ids", [])
                t_thumb = None
                s_thumb = None
                for fid in t_faces:
                    url = resolve_face_image_url(fid, crop_files)
                    if url:
                        t_thumb = Img(src=url, alt=t_name, cls="w-16 h-16 object-cover rounded border border-slate-600")
                        break
                for fid in s_faces:
                    url = resolve_face_image_url(fid, crop_files)
                    if url:
                        s_thumb = Img(src=url, alt=s_name, cls="w-16 h-16 object-cover rounded border border-slate-600")
                        break
                if not t_thumb:
                    t_thumb = Div(cls="w-16 h-16 bg-slate-600 rounded")
                if not s_thumb:
                    s_thumb = Div(cls="w-16 h-16 bg-slate-600 rounded")

                rows.append(Div(
                    Div(
                        Span("Merge Suggestion", cls="text-sm font-bold text-purple-400"),
                        Span(f"by {a['submitted_by']}", cls="text-xs text-slate-400 ml-2"),
                        guest_badge,
                        cls="flex items-center mb-3"
                    ),
                    # Side-by-side face comparison
                    Div(
                        Div(t_thumb, P(t_name, cls="text-xs text-slate-300 mt-1 text-center truncate w-16"), cls="flex flex-col items-center"),
                        Span("→", cls="text-slate-500 text-xl font-bold mx-4 self-center"),
                        Div(s_thumb, P(s_name, cls="text-xs text-slate-300 mt-1 text-center truncate w-16"), cls="flex flex-col items-center"),
                        cls="flex items-start justify-center mb-3"
                    ),
                    P(f'Confidence: {a["confidence"]}', cls="text-xs text-slate-500"),
                    P(f'Reason: {a.get("reason", "none")}', cls="text-xs text-slate-500") if a.get("reason") else None,
                    Div(
                        Button("Execute Merge",
                               hx_post=f"/admin/approvals/{ann_id}/approve",
                               hx_target=f"#annotation-{ann_id}",
                               hx_swap="outerHTML",
                               cls="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-500"),
                        Button("Compare",
                               hx_get=f"/api/identity/{t_id}/compare/{s_id}",
                               hx_target="#compare-modal-content",
                               hx_swap="innerHTML",
                               cls="px-3 py-1 text-sm border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20",
                               **{"_": "on click remove .hidden from #compare-modal"},
                               type="button"),
                        Button("Skip",
                               hx_post=f"/admin/approvals/{ann_id}/reject",
                               hx_target=f"#annotation-{ann_id}",
                               hx_swap="outerHTML",
                               cls="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-500"),
                        cls="flex gap-2 mt-3"
                    ),
                    cls="bg-slate-800 rounded-lg p-4 border border-purple-500/30",
                    id=f"annotation-{ann_id}"
                ))
                continue
            except (json.JSONDecodeError, KeyError):
                pass  # Fall through to generic rendering

        rows.append(Div(
            Div(
                Span(a["type"].replace("_", " ").title(), cls="text-sm font-bold text-white"),
                Span(f"for {a['target_type']} {a['target_id'][:12]}...",
                      cls="text-xs text-slate-400 ml-2"),
                guest_badge,
                cls="flex items-center"
            ),
            P(f'Suggestion: "{a["value"]}"', cls="text-sm text-slate-300 mt-1"),
            P(f'Confidence: {a["confidence"]} | By: {a["submitted_by"]}',
              cls="text-xs text-slate-500"),
            P(f'Reason: {a.get("reason", "none")}', cls="text-xs text-slate-500") if a.get("reason") else None,
            Div(
                Button("Approve",
                       hx_post=f"/admin/approvals/{ann_id}/approve",
                       hx_target=f"#annotation-{ann_id}",
                       hx_swap="outerHTML",
                       cls="px-3 py-1 text-sm bg-emerald-600 text-white rounded hover:bg-emerald-500"),
                Button("Reject",
                       hx_post=f"/admin/approvals/{ann_id}/reject",
                       hx_target=f"#annotation-{ann_id}",
                       hx_swap="outerHTML",
                       cls="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-500"),
                cls="flex gap-2 mt-3"
            ),
            cls="bg-slate-800 rounded-lg p-4 border border-slate-700",
            id=f"annotation-{ann_id}"
        ))

    if not rows:
        rows = [Div(
            P("No pending annotations to review.", cls="text-slate-400"),
            cls="text-center py-12"
        )]

    return Title("Annotation Approvals — Rhodesli"), Div(
        Div(
            H1("Pending Approvals", cls="text-2xl font-bold text-white"),
            A("Back to Dashboard", href="/?section=to_review",
              cls="text-sm text-indigo-400 hover:text-indigo-300"),
            cls="flex items-center justify-between mb-6"
        ),
        Div(f"{len(pending)} pending annotations", cls="text-sm text-slate-400 mb-4"),
        Div(*rows, cls="space-y-3"),
        cls="max-w-3xl mx-auto p-6"
    )


@rt("/admin/approvals/{ann_id}/approve")
def post(ann_id: str, sess=None):
    """Approve an annotation. Updates target record."""
    denied = _check_admin(sess)
    if denied:
        return denied

    user = get_current_user(sess)
    annotations = _load_annotations()
    ann = annotations["annotations"].get(ann_id)
    if not ann:
        return Response(to_xml(toast("Annotation not found.", "error")), status_code=404,
                        headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"})

    from datetime import datetime, timezone
    ann["status"] = "approved"
    ann["reviewed_by"] = user.email if user else "admin"
    ann["reviewed_at"] = datetime.now(timezone.utc).isoformat()

    # Apply the annotation to the target
    if ann["type"] == "name_suggestion" and ann["target_type"] == "identity":
        registry = load_registry()
        identity = registry._identities.get(ann["target_id"])
        if identity:
            identity["name"] = ann["value"]
            identity["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_registry(registry)
    elif ann["type"] == "merge_suggestion":
        # Execute the merge
        try:
            merge_data = json.loads(ann["value"])
            t_id = merge_data.get("target_id", ann["target_id"])
            s_id = merge_data.get("source_id", "")
            registry = load_registry()
            photo_registry = load_photo_registry()
            result = registry.merge_identities(
                source_id=s_id, target_id=t_id,
                user_source="approved_suggestion",
                photo_registry=photo_registry,
            )
            if result["success"]:
                save_registry(registry)
                actual_target = result.get("actual_target_id") or t_id
                _merge_annotations(s_id, actual_target)
                log_user_action("APPROVE_MERGE_SUGGESTION", target=t_id, source=s_id,
                                suggested_by=ann["submitted_by"],
                                admin=user.email if user else "admin")
            else:
                _save_annotations(annotations)
                return Div(
                    Span("MERGE FAILED", cls="text-sm font-bold text-red-400"),
                    Span(f' — {result["reason"]}', cls="text-sm text-slate-400"),
                    cls="bg-red-900/20 rounded-lg p-4 border border-red-700",
                    id=f"annotation-{ann_id}"
                )
        except (json.JSONDecodeError, KeyError) as e:
            _save_annotations(annotations)
            return Div(
                Span("ERROR", cls="text-sm font-bold text-red-400"),
                Span(f' — Invalid merge data: {e}', cls="text-sm text-slate-400"),
                cls="bg-red-900/20 rounded-lg p-4 border border-red-700",
                id=f"annotation-{ann_id}"
            )

    _save_annotations(annotations)

    merge_label = ""
    if ann["type"] == "merge_suggestion":
        try:
            merge_data = json.loads(ann["value"])
            merge_label = f"Merged {merge_data.get('source_id', '')[:8]} into {merge_data.get('target_id', '')[:8]}"
        except (json.JSONDecodeError, KeyError):
            merge_label = "Merge executed"

    return Div(
        Span("APPROVED" if ann["type"] != "merge_suggestion" else "MERGED", cls="text-sm font-bold text-emerald-400"),
        Span(f' — {merge_label or ann["value"]} (suggested by {ann["submitted_by"]})', cls="text-sm text-slate-400"),
        cls="bg-emerald-900/20 rounded-lg p-4 border border-emerald-700",
        id=f"annotation-{ann_id}"
    )


@rt("/activity")
def get(sess=None):
    """
    Public activity feed showing recent identifications and contributions.
    Shows what's happening in the archive — motivates contributors.
    """
    actions = _load_activity_feed(limit=50)

    rows = []
    for a in actions:
        icon = {
            "MERGE": "🔗",
            "CONFIRM": "✓",
            "RENAME": "✏️",
            "SKIP": "⏭",
            "annotation_approved": "📝",
        }.get(a["type"], "•")

        rows.append(Div(
            Span(icon, cls="text-lg mr-2"),
            Span(a["description"], cls="text-sm text-slate-300"),
            Span(a["timestamp"][:10], cls="text-xs text-slate-500 ml-auto"),
            cls="flex items-center gap-2 py-2 border-b border-slate-800"
        ))

    if not rows:
        rows = [Div(
            P("No activity yet. Be the first to identify someone!",
              cls="text-slate-400 text-center py-12"),
        )]

    return Title("Activity — Rhodesli"), Div(
        Div(
            H1("Recent Activity", cls="text-2xl font-bold text-white"),
            A("Back to Archive", href="/",
              cls="text-sm text-indigo-400 hover:text-indigo-300"),
            cls="flex items-center justify-between mb-6"
        ),
        Div(*rows, cls="space-y-0"),
        cls="max-w-3xl mx-auto p-6"
    )


def _load_activity_feed(limit: int = 50) -> list:
    """Load activity from user_actions.log and annotations."""
    activities = []

    # Load from user action log
    action_log = Path(__file__).resolve().parent.parent / "logs" / "user_actions.log"
    if action_log.exists():
        try:
            lines = action_log.read_text().strip().split("\n")
            for line in lines[-limit:]:
                parts = line.split(" | ", 2)
                if len(parts) >= 2:
                    timestamp = parts[0].strip()
                    action_type = parts[1].strip()
                    detail = parts[2].strip() if len(parts) > 2 else ""

                    # Skip internal actions
                    if action_type in ("SKIP",):
                        continue

                    desc_map = {
                        "MERGE": "Two identities were merged",
                        "CONFIRM": "An identity was confirmed",
                        "RENAME": "An identity was renamed",
                        "REJECT_IDENTITY": "A match was rejected",
                        "DETACH": "A face was detached",
                    }
                    description = desc_map.get(action_type, f"Action: {action_type}")
                    if "target_identity_id=" in detail:
                        # Extract a readable fragment
                        for kv in detail.split():
                            if kv.startswith("target_identity_id="):
                                description += f" ({kv.split('=')[1][:8]}...)"
                                break

                    activities.append({
                        "type": action_type,
                        "description": description,
                        "timestamp": timestamp,
                    })
        except Exception:
            pass

    # Load from approved annotations
    try:
        annotations = _load_annotations()
        for ann in annotations.get("annotations", {}).values():
            if ann.get("status") == "approved":
                activities.append({
                    "type": "annotation_approved",
                    "description": f'Name suggestion approved: "{ann["value"]}"',
                    "timestamp": ann.get("reviewed_at", ann.get("submitted_at", "")),
                })
    except Exception:
        pass

    # Sort by timestamp, newest first
    activities.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
    return activities[:limit]


@rt("/admin/approvals/{ann_id}/reject")
def post(ann_id: str, sess=None):
    """Reject an annotation. No data change."""
    denied = _check_admin(sess)
    if denied:
        return denied

    user = get_current_user(sess)
    annotations = _load_annotations()
    ann = annotations["annotations"].get(ann_id)
    if not ann:
        return Response(to_xml(toast("Annotation not found.", "error")), status_code=404,
                        headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"})

    from datetime import datetime, timezone
    ann["status"] = "rejected"
    ann["reviewed_by"] = user.email if user else "admin"
    ann["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _save_annotations(annotations)

    return Div(
        Span("REJECTED", cls="text-sm font-bold text-red-400"),
        Span(f' — "{ann["value"]}" by {ann["submitted_by"]}', cls="text-sm text-slate-400"),
        cls="bg-red-900/20 rounded-lg p-4 border border-red-700",
        id=f"annotation-{ann_id}"
    )


# --- Sync API Endpoints (token-authenticated, for scripts/sync_from_production.py) ---

def _check_sync_token(request):
    """Validate Bearer token for sync API. Returns None if valid, Response if not."""
    if not SYNC_API_TOKEN:
        return Response("Sync API not configured (RHODESLI_SYNC_TOKEN not set)", status_code=503)
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token != SYNC_API_TOKEN:
        return Response("Unauthorized", status_code=401)
    return None


@rt("/api/sync/status")
def get(request):
    """Public endpoint — shows data stats without requiring auth."""
    registry = load_registry()
    identities = registry.list_identities()
    confirmed = sum(1 for i in identities if i.get("state") == "CONFIRMED")
    proposed = sum(1 for i in identities if i.get("state") == "PROPOSED")
    inbox = sum(1 for i in identities if i.get("state") == "INBOX")

    photo_count = 0
    photo_index_path = data_path / "photo_index.json"
    if photo_index_path.exists():
        with open(photo_index_path) as f:
            index = json.load(f)
            photo_count = len(index.get("photos", {}))

    return {
        "identities": len(identities),
        "confirmed": confirmed,
        "proposed": proposed,
        "inbox": inbox,
        "photos": photo_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@rt("/api/sync/identities")
def get(request):
    """Download identities.json via sync token. For scripts/sync_from_production.py."""
    denied = _check_sync_token(request)
    if denied:
        return denied
    fpath = data_path / "identities.json"
    if not fpath.exists():
        return Response("File not found", status_code=404)
    with open(fpath) as f:
        data = json.load(f)
    return data


@rt("/api/sync/photo-index")
def get(request):
    """Download photo_index.json via sync token. For scripts/sync_from_production.py."""
    denied = _check_sync_token(request)
    if denied:
        return denied
    fpath = data_path / "photo_index.json"
    if not fpath.exists():
        return Response("File not found", status_code=404)
    with open(fpath) as f:
        data = json.load(f)
    return data


@rt("/api/sync/annotations")
def get(request):
    """Download annotations.json via sync token. For scripts/sync_from_production.py."""
    denied = _check_sync_token(request)
    if denied:
        return denied
    annotations = _load_annotations()
    return annotations


# --- Staged Files API (for downloading uploads from production to local ML) ---

@rt("/api/sync/staged")
def get(request):
    """List all staged upload files awaiting local ML processing."""
    denied = _check_sync_token(request)
    if denied:
        return denied

    staging_dir = data_path / "staging"
    if not staging_dir.exists():
        return {"files": [], "total_files": 0, "total_size_bytes": 0}

    files = []
    total_size = 0
    for fpath in staging_dir.rglob("*"):
        if not fpath.is_file():
            continue
        rel = fpath.relative_to(staging_dir)
        size = fpath.stat().st_size
        mtime = datetime.fromtimestamp(fpath.stat().st_mtime, tz=timezone.utc).isoformat()
        files.append({
            "filename": fpath.name,
            "path": str(rel),
            "size_bytes": size,
            "uploaded_at": mtime,
        })
        total_size += size

    return {"files": files, "total_files": len(files), "total_size_bytes": total_size}


@app.get("/api/sync/staged/download/{filepath:path}")
async def download_staged_file(request, filepath: str):
    """Download a single staged file. Path is relative to staging root."""
    denied = _check_sync_token(request)
    if denied:
        return denied

    # Security: block path traversal
    if ".." in filepath or filepath.startswith("/"):
        return Response("Invalid path", status_code=400)

    staging_dir = data_path / "staging"
    target = (staging_dir / filepath).resolve()

    # Ensure resolved path is still inside staging dir
    if not str(target).startswith(str(staging_dir.resolve())):
        return Response("Invalid path", status_code=400)

    if not target.exists() or not target.is_file():
        return Response("File not found", status_code=404)

    return FileResponse(
        str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )

# Move staged download route before FastHTML's catch-all static route
# (same issue as /photos/{filename:path} — the /{fname:path}.{ext:static}
# catch-all would intercept .jpg/.png paths before our handler)
for i, route in enumerate(app.routes):
    if getattr(route, "path", None) == "/api/sync/staged/download/{filepath:path}":
        _staged_route = app.routes.pop(i)
        app.routes.insert(0, _staged_route)
        break


@rt("/api/sync/staged/clear")
async def post(request):
    """Remove staged files after successful download and processing."""
    denied = _check_sync_token(request)
    if denied:
        return denied

    import shutil

    body = await request.json()
    staging_dir = data_path / "staging"

    if body.get("all"):
        # Clear entire staging directory
        removed = []
        if staging_dir.exists():
            for item in list(staging_dir.iterdir()):
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
                removed.append(str(item.relative_to(staging_dir)))
        return {"cleared": "all", "removed": removed, "count": len(removed)}

    file_list = body.get("files", [])
    if not file_list:
        return Response("No files specified", status_code=400)

    removed = []
    errors = []
    for rel_path in file_list:
        if ".." in rel_path or rel_path.startswith("/"):
            errors.append({"path": rel_path, "error": "invalid path"})
            continue
        target = (staging_dir / rel_path).resolve()
        if not str(target).startswith(str(staging_dir.resolve())):
            errors.append({"path": rel_path, "error": "invalid path"})
            continue
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
            removed.append(rel_path)
            # Clean up empty parent directories
            parent = target.parent
            while parent != staging_dir and parent.exists():
                if not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
        else:
            errors.append({"path": rel_path, "error": "not found"})

    return {"removed": removed, "errors": errors, "count": len(removed)}


@rt("/api/sync/staged/mark-processed")
async def post(request):
    """Mark staging jobs as processed in pending_uploads.json.

    Called by the pipeline after successful processing to remove jobs from
    the Pending Uploads admin page.

    Accepts JSON body with:
        job_ids: list of job IDs to mark as processed
        all: bool — mark ALL staged jobs as processed
    """
    denied = _check_sync_token(request)
    if denied:
        return denied

    body = await request.json()
    pending = _load_pending_uploads()

    marked = []
    if body.get("all"):
        for job_id, upload in pending["uploads"].items():
            if upload.get("status") == "staged":
                upload["status"] = "processed"
                upload["processed_at"] = datetime.now(timezone.utc).isoformat()
                marked.append(job_id)
    else:
        job_ids = body.get("job_ids", [])
        if not job_ids:
            return Response("Must provide 'job_ids' or 'all'", status_code=400)
        for job_id in job_ids:
            if job_id in pending["uploads"]:
                upload = pending["uploads"][job_id]
                if upload.get("status") in ("staged", "approved"):
                    upload["status"] = "processed"
                    upload["processed_at"] = datetime.now(timezone.utc).isoformat()
                    marked.append(job_id)

    if marked:
        _save_pending_uploads(pending)

    return {"marked_processed": marked, "count": len(marked)}


# --- Push API (for pushing locally-processed data back to production) ---


@rt("/api/sync/push")
async def post(request):
    """Push updated identities.json and/or photo_index.json to production.

    Accepts JSON body with keys:
        identities: full identities.json content (optional)
        photo_index: full photo_index.json content (optional)

    Creates timestamped backups before overwriting.
    Protected by sync token (same as pull endpoints).
    """
    denied = _check_sync_token(request)
    if denied:
        return denied

    import shutil
    import time

    body = await request.json()

    if not body.get("identities") and not body.get("photo_index") and not body.get("annotations"):
        return Response(
            "Must provide 'identities', 'photo_index', and/or 'annotations' in request body",
            status_code=400,
        )

    results = {}
    ts = int(time.time())

    # Push identities.json
    if body.get("identities"):
        identities_data = body["identities"]
        # Basic validation: must have identities key or be a dict of identities
        if not isinstance(identities_data, dict):
            return Response("identities must be a JSON object", status_code=400)

        fpath = data_path / "identities.json"
        backup_path = data_path / f"identities.json.bak.{ts}"

        if fpath.exists():
            shutil.copy2(fpath, backup_path)

        with open(fpath, "w") as f:
            json.dump(identities_data, f, indent=2)

        # Count what we received
        id_data = identities_data.get("identities", identities_data)
        results["identities"] = {
            "status": "written",
            "count": len(id_data),
            "backup": backup_path.name,
        }

    # Push photo_index.json
    if body.get("photo_index"):
        photo_data = body["photo_index"]
        if not isinstance(photo_data, dict):
            return Response("photo_index must be a JSON object", status_code=400)

        fpath = data_path / "photo_index.json"
        backup_path = data_path / f"photo_index.json.bak.{ts}"

        if fpath.exists():
            shutil.copy2(fpath, backup_path)

        with open(fpath, "w") as f:
            json.dump(photo_data, f, indent=2)

        photos = photo_data.get("photos", {})
        results["photo_index"] = {
            "status": "written",
            "count": len(photos),
            "backup": backup_path.name,
        }

    # Push annotations.json
    if body.get("annotations"):
        ann_data = body["annotations"]
        if not isinstance(ann_data, dict):
            return Response("annotations must be a JSON object", status_code=400)

        fpath = data_path / "annotations.json"
        backup_path = data_path / f"annotations.json.bak.{ts}"

        if fpath.exists():
            shutil.copy2(fpath, backup_path)

        with open(fpath, "w") as f:
            json.dump(ann_data, f, indent=2, ensure_ascii=False)

        ann_count = len(ann_data.get("annotations", {}))
        results["annotations"] = {
            "status": "written",
            "count": ann_count,
            "backup": backup_path.name,
        }

    # Invalidate ALL in-memory caches so subsequent requests see the new data
    global _photo_registry_cache, _face_data_cache, _proposals_cache, _skipped_neighbor_cache, _skipped_neighbor_cache_key, _photo_cache, _face_to_photo_cache, _annotations_cache
    _photo_registry_cache = None
    _face_data_cache = None
    _proposals_cache = None
    _skipped_neighbor_cache = None
    _skipped_neighbor_cache_key = None
    _photo_cache = None
    _face_to_photo_cache = None
    _annotations_cache = None

    return {"status": "ok", "results": results, "timestamp": ts}


# =============================================================================
# ROUTES - MATCH MODE (Gamified Pairing)
# =============================================================================


def _log_match_decision(identity_a: str, identity_b: str, decision: str,
                        confidence: int, sess=None):
    """
    Log a match decision for audit trail and future ML training.

    Appends to data/match_decisions.jsonl (one JSON object per line).
    """
    import json as _json
    from datetime import datetime, timezone

    user_email = ""
    if sess:
        user = get_current_user(sess)
        if user:
            user_email = user.email

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "identity_a": identity_a,
        "identity_b": identity_b,
        "decision": decision,
        "confidence_pct": confidence,
        "user": user_email,
    }

    log_path = Path(DATA_DIR) / "match_decisions.jsonl"
    try:
        with open(log_path, "a") as f:
            f.write(_json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[match] Failed to log decision: {e}")


def _get_best_match_pair(triage_filter: str = ""):
    """
    Find the best pair of identities to show in match mode.

    Returns (identity_a, identity_b, distance) or None if no pairs available.

    Args:
        triage_filter: Optional filter to scope pairs:
            - "ready": Only proposal pairs (skip NN fallback)
            - "rediscovered": Only pairs where source has promoted_from
            - "unmatched": Skip proposals, NN search only for non-proposal faces
            - "": All pairs (default behavior)

    Priority:
    1. Clustering proposals (pre-computed, highest confidence first)
    2. Live nearest-neighbor search (fallback when proposals exhausted)
    """
    registry = load_registry()
    face_data = get_face_data()
    photo_registry = load_photo_registry()

    ids_with_proposals = _get_identities_with_proposals()

    # Priority 1: Check clustering proposals (skip for "unmatched" filter)
    if triage_filter != "unmatched":
        proposals_data = _load_proposals()
        for proposal in proposals_data.get("proposals", []):
            source_id = proposal["source_identity_id"]
            target_id = proposal["target_identity_id"]
            source = registry.get_identity(source_id)
            target = registry.get_identity(target_id)
            if not source or not target:
                continue
            # Skip if already merged or resolved
            if source.get("merged_into") or target.get("merged_into"):
                continue
            # Skip confirmed-confirmed pairs (already resolved)
            if source.get("state") == "CONFIRMED" and target.get("state") == "CONFIRMED":
                continue
            # Apply rediscovered filter: source must have promoted_from
            if triage_filter == "rediscovered" and not source.get("promoted_from"):
                continue
            # Valid proposal — return as match pair
            neighbor_info = {
                "identity_id": target_id,
                "name": target.get("name", "Unknown"),
                "state": target.get("state", ""),
                "distance": proposal["distance"],
                "face_count": len(target.get("anchor_ids", []) + target.get("candidate_ids", [])),
                "confidence": proposal.get("confidence", ""),
                "from_proposal": True,
            }
            return (source, neighbor_info, proposal["distance"])

    # Priority 2: Fallback to live nearest-neighbor search
    # Skip for "ready" filter (only proposals matter)
    if triage_filter == "ready":
        return None

    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    to_review = inbox + proposed

    # Apply filter to NN candidates
    if triage_filter == "rediscovered":
        to_review = [i for i in to_review if i.get("promoted_from") is not None]
    elif triage_filter == "unmatched":
        to_review = [i for i in to_review
                     if i.get("identity_id", "") not in ids_with_proposals
                     and not i.get("promoted_from")]

    if len(to_review) < 2:
        return None

    best_pair = None
    best_distance = float('inf')

    to_review.sort(
        key=lambda x: len(x.get("anchor_ids", []) + x.get("candidate_ids", [])),
        reverse=True
    )

    for identity in to_review[:20]:
        try:
            from core.neighbors import find_nearest_neighbors
            neighbors = find_nearest_neighbors(
                identity["identity_id"], registry, photo_registry, face_data, limit=1
            )
            if neighbors and neighbors[0]["distance"] < best_distance:
                best_distance = neighbors[0]["distance"]
                best_pair = (identity, neighbors[0], best_distance)
        except Exception:
            continue

    return best_pair


@rt("/api/match/next-pair")
def get(filter: str = "", sess=None):
    """
    Get the next pair of faces to compare in Match mode.

    Returns an HTMX partial with two large face crops side by side,
    confidence bar, clickable photos, and action buttons.

    Args:
        filter: Triage filter (ready/rediscovered/unmatched) to scope pairs.
    """
    pair = _get_best_match_pair(triage_filter=filter)

    if pair is None:
        _back_url = f"/?section=to_review&view=focus&filter={filter}" if filter else "/?section=to_review&view=focus"
        return Div(
            H3("No more pairs to match!", cls="text-lg font-medium text-white"),
            P("All available identities have been reviewed.", cls="text-slate-400 mt-2"),
            A("Back to Focus mode", href=_back_url,
              cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium"),
            cls="text-center py-12"
        )

    identity_a, neighbor_b, distance = pair
    identity_id_a = identity_a["identity_id"]
    identity_id_b = neighbor_b["identity_id"]

    crop_files = get_crop_files()

    # Get face data for both identities
    def _get_face_info(identity_data):
        face_ids = identity_data.get("anchor_ids", []) + identity_data.get("candidate_ids", [])
        if not face_ids:
            return None, None, None
        first = face_ids[0]
        fid = first if isinstance(first, str) else first.get("face_id", "")
        crop_url = resolve_face_image_url(fid, crop_files)
        photo_id = get_photo_id_for_face(fid)
        return fid, crop_url, photo_id

    face_id_a, crop_url_a, photo_id_a = _get_face_info(identity_a)
    try:
        registry = load_registry()
        identity_b_full = registry.get_identity(identity_id_b)
        face_id_b, crop_url_b, photo_id_b = _get_face_info(identity_b_full)
    except KeyError:
        face_id_b, crop_url_b, photo_id_b = None, None, None

    name_a = ensure_utf8_display(identity_a.get("name")) or f"Person {identity_id_a[:8]}..."
    name_b = ensure_utf8_display(neighbor_b.get("name")) or f"Person {identity_id_b[:8]}..."
    faces_a = len(identity_a.get("anchor_ids", []) + identity_a.get("candidate_ids", []))
    faces_b = neighbor_b.get("face_count", 0)

    # Confidence calculation (inverse distance, clamped 0-100)
    # Distance 0.0 = 100% confidence, distance 2.0 = 0%
    confidence_pct = max(0, min(100, int((1 - distance / 2.0) * 100)))

    # Color based on confidence
    if confidence_pct >= 70:
        bar_color = "bg-emerald-500"
        conf_label = "High"
        conf_text_cls = "text-emerald-400"
    elif confidence_pct >= 40:
        bar_color = "bg-amber-500"
        conf_label = "Medium"
        conf_text_cls = "text-amber-400"
    else:
        bar_color = "bg-red-500"
        conf_label = "Low"
        conf_text_cls = "text-red-400"

    # Build clickable face card
    def _face_card(name, crop_url, face_id, photo_id, face_count, iid=None):
        img_el = Img(
            src=crop_url or "", alt=name,
            cls="w-full h-full object-cover"
        ) if crop_url else Span("?", cls="text-6xl text-slate-500")

        # Make clickable to view source photo (with identity nav context)
        if photo_id:
            _fc_url = f"/photo/{photo_id}/partial?face={face_id}" if face_id else f"/photo/{photo_id}/partial"
            if iid:
                _fc_url += f"&identity_id={iid}"
            face_el = Button(
                Div(
                    img_el,
                    cls="w-full aspect-square rounded-xl overflow-hidden bg-slate-700 flex items-center justify-center"
                ),
                cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-xl transition-all w-full",
                hx_get=_fc_url,
                hx_target="#photo-modal-content",
                **{"_": "on click remove .hidden from #photo-modal"},
                type="button",
                title="Click to view source photo",
            )
        else:
            face_el = Div(
                img_el,
                cls="w-full aspect-square rounded-xl overflow-hidden bg-slate-700 flex items-center justify-center"
            )

        return Div(
            face_el,
            P(name, cls="text-sm font-medium text-slate-200 mt-3 text-center truncate"),
            P(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-xs text-slate-500 text-center"),
            P("Click to view photo", cls="text-xs text-indigo-400 text-center mt-1") if photo_id else None,
            cls="flex-1 max-w-[280px]"
        )

    # Build filter query suffix for URL propagation
    filter_suffix = f"&filter={filter}" if filter else ""

    return Div(
        # Confidence bar
        Div(
            Div(
                Span(f"Match Confidence: {confidence_pct}%", cls=f"text-sm font-medium {conf_text_cls}"),
                Span(f"({conf_label})", cls=f"text-xs {conf_text_cls} ml-1"),
                Span(f"dist: {distance:.3f}", cls="text-xs font-data text-slate-500 ml-3"),
                cls="flex items-center justify-center mb-2"
            ),
            # Progress bar
            Div(
                Div(cls=f"{bar_color} h-full rounded-full transition-all", style=f"width: {confidence_pct}%"),
                cls="w-full max-w-md mx-auto h-2 bg-slate-700 rounded-full overflow-hidden"
            ),
            cls="mb-6"
        ),
        # Side by side faces — large display
        Div(
            _face_card(name_a, crop_url_a, face_id_a, photo_id_a, faces_a, iid=identity_id_a),
            # VS divider
            Div(
                Span("vs", cls="text-slate-500 text-xl font-bold"),
                cls="flex items-center justify-center px-6 pt-8"
            ),
            _face_card(name_b, crop_url_b, face_id_b, photo_id_b, faces_b, iid=identity_id_b),
            cls="flex flex-col sm:flex-row items-center sm:items-start justify-center gap-2"
        ),
        # Action buttons -- role-aware
        Div(
            Button(
                "Suggest Same" if _get_user_role(sess) == "contributor" else "Same Person",
                cls=f"px-8 py-3 text-sm font-bold {'bg-purple-600 hover:bg-purple-500' if _get_user_role(sess) == 'contributor' else 'bg-emerald-600 hover:bg-emerald-500'} text-white rounded-lg transition-colors min-h-[44px]",
                hx_post=f"/api/match/decide?identity_a={identity_id_a}&identity_b={identity_id_b}&decision=same&confidence={confidence_pct}{filter_suffix}",
                hx_target="#match-pair-container",
                hx_swap="innerHTML",
                type="button",
                id="match-btn-same",
                data_auth_action="identify these faces",
            ),
            Button(
                "Different People",
                cls="px-8 py-3 text-sm font-bold border-2 border-red-500 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors min-h-[44px]",
                hx_post=f"/api/match/decide?identity_a={identity_id_a}&identity_b={identity_id_b}&decision=different&confidence={confidence_pct}{filter_suffix}",
                hx_target="#match-pair-container",
                hx_swap="innerHTML",
                type="button",
                id="match-btn-diff",
            ),
            Button(
                "Skip",
                cls="px-4 py-3 text-sm text-slate-400 hover:text-slate-300 transition-colors min-h-[44px]",
                hx_get=f"/api/match/next-pair?filter={filter}" if filter else "/api/match/next-pair",
                hx_target="#match-pair-container",
                hx_swap="innerHTML",
                type="button",
                id="match-btn-skip",
            ),
            Span(
                "Keyboard: Y N S",
                cls="text-xs text-slate-600 hidden sm:inline",
                title="Y=Same Person, N=Different People, S=Skip"
            ),
            cls="flex flex-wrap items-center justify-center gap-4 mt-8 pt-4 border-t border-slate-700"
        ),
        cls="match-pair"
    )


@rt("/api/match/decide")
def post(identity_a: str, identity_b: str, decision: str, confidence: int = 0, filter: str = "", sess=None):
    """
    Record a match decision, log it, and return the next pair.

    Args:
        identity_a: First identity ID
        identity_b: Second identity ID
        decision: "same" (merge) or "different" (reject pair)
        confidence: Match confidence percentage at time of decision
    """
    # Allow contributors to suggest (they can't merge but can say "same")
    user_role = _get_user_role(sess)
    if user_role == "contributor":
        denied = _check_contributor(sess)
    else:
        denied = _check_admin(sess)
    if denied:
        return denied

    # Log the decision
    _log_match_decision(identity_a, identity_b, decision, confidence, sess)

    # Contributors create merge suggestions instead of executing merges
    if decision == "same" and user_role == "contributor":
        user = get_current_user(sess)
        _create_merge_suggestion(
            target_id=identity_a, source_id=identity_b,
            submitted_by=user.email if user else "contributor",
            confidence="certain" if confidence >= 80 else "likely" if confidence >= 50 else "guess",
            reason=f"Matched in match mode (confidence: {confidence}%)",
        )
        oob_toast = Div(
            toast("Suggestion recorded! An admin will review it.", "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        counter_script = Div(
            Script("if (typeof incrementMatchCount === 'function') incrementMatchCount();"),
            hx_swap_oob="beforeend:body",
        )
        pair = _get_best_match_pair(triage_filter=filter)
        if pair is None:
            return (Div(
                H3("No more pairs!", cls="text-lg font-medium text-white"),
                P("You have reviewed all available pairs.", cls="text-slate-400 mt-2"),
                cls="text-center py-12"
            ), oob_toast, counter_script)
        _next_url = f"/api/match/next-pair?filter={filter}" if filter else "/api/match/next-pair"
        next_pair_html = Div(
            P("Loading next pair...", cls="text-slate-400 text-center py-4"),
            hx_get=_next_url, hx_trigger="load", hx_swap="outerHTML",
        )
        return (next_pair_html, oob_toast, counter_script)

    if decision == "same":
        # Merge identity_b into identity_a
        try:
            registry = load_registry()
            photo_registry = load_photo_registry()
            result = registry.merge_identities(
                source_id=identity_b,
                target_id=identity_a,
                user_source="match_mode",
                photo_registry=photo_registry,
            )
            if result["success"]:
                save_registry(registry)
                oob_toast = Div(
                    toast(f"Merged! {_pl(result['faces_merged'], 'face')} combined.", "success"),
                    hx_swap_oob="beforeend:#toast-container",
                )
            else:
                oob_toast = Div(
                    toast(f"Cannot merge: {result['reason']}", "warning"),
                    hx_swap_oob="beforeend:#toast-container",
                )
        except Exception as e:
            oob_toast = Div(
                toast(f"Error: {str(e)}", "error"),
                hx_swap_oob="beforeend:#toast-container",
            )
    elif decision == "different":
        # Mark as not same person
        try:
            registry = load_registry()
            registry.reject_identity_pair(identity_a, identity_b, user_source="match_mode")
            save_registry(registry)
            oob_toast = Div(
                toast("Marked as different people.", "info"),
                hx_swap_oob="beforeend:#toast-container",
            )
        except Exception as e:
            oob_toast = Div(
                toast(f"Error: {str(e)}", "error"),
                hx_swap_oob="beforeend:#toast-container",
            )
    else:
        oob_toast = Div(
            toast("Invalid decision.", "error"),
            hx_swap_oob="beforeend:#toast-container",
        )

    # Increment counter script (OOB)
    counter_script = Div(
        Script("if (typeof incrementMatchCount === 'function') incrementMatchCount();"),
        hx_swap_oob="beforeend:body",
    )

    # Get next pair (respecting active filter)
    pair = _get_best_match_pair(triage_filter=filter)
    if pair is None:
        _back_url = f"/?section=to_review&view=focus&filter={filter}" if filter else "/?section=to_review&view=focus"
        next_content = Div(
            H3("No more pairs!", cls="text-lg font-medium text-white"),
            P("You have matched all available pairs.", cls="text-slate-400 mt-2"),
            A("Back to Focus mode", href=_back_url,
              cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium"),
            cls="text-center py-12"
        )
        return (next_content, oob_toast, counter_script)

    _next_url = f"/api/match/next-pair?filter={filter}" if filter else "/api/match/next-pair"
    next_pair_html = Div(
        P("Loading next pair...", cls="text-slate-400 text-center py-4"),
        hx_get=_next_url,
        hx_trigger="load",
        hx_swap="outerHTML",
    )
    return (next_pair_html, oob_toast, counter_script)


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