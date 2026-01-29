"""
Rhodesli Forensic Workstation.

A triage-focused interface for identity verification with epistemic humility.
The UI reflects backend state - it never calculates probabilities.

Error Semantics:
- 409 = Variance Explosion (faces too dissimilar)
- 423 = Lock Contention (another process is writing)
- 404 = Identity or face not found
"""

import re
import sys
from pathlib import Path

from fasthtml.common import *

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.registry import IdentityRegistry, IdentityState

static_path = Path(__file__).resolve().parent / "static"
data_path = Path(__file__).resolve().parent.parent / "data"

app, rt = fast_app(
    pico=False,
    hdrs=(
        Script(src="https://cdn.tailwindcss.com"),
    ),
    static_path=str(static_path),
)

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


def parse_quality_from_filename(filename: str) -> float:
    """Extract quality score from filename like 'brass_rail_21.98_0.jpg'."""
    match = re.search(r'_(\d+\.\d+)_\d+\.jpg$', filename)
    if match:
        return float(match.group(1))
    return 0.0


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


def state_badge(state: str) -> Span:
    """
    Render state as a colored badge.
    UX Intent: Instant state recognition via color coding.
    """
    colors = {
        "CONFIRMED": "bg-emerald-600 text-white",
        "PROPOSED": "bg-amber-500 text-white",
        "CONTESTED": "bg-red-600 text-white",
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
    """
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
        # Skip button (neutral) - client-side only
        Button(
            "? Skip",
            cls="px-3 py-1.5 text-sm font-bold border border-stone-300 text-stone-500 rounded hover:bg-stone-100 transition-colors",
            aria_label="Skip this identity for now",
            type="button",
            **{"_": f"on click add .hidden to #identity-{identity_id}"}
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
    show_actions: bool = False,
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
        show_actions: Whether to show action buttons
    """
    if quality is None:
        # Extract quality from URL: /crops/{name}_{quality}_{idx}.jpg
        quality = parse_quality_from_filename(crop_url)

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
        # Metadata
        P(
            f"Quality: {quality:.2f}",
            cls="mt-2 text-xs font-mono text-stone-500"
        ),
        cls="bg-white border border-stone-200 p-2 rounded shadow-sm hover:shadow-md transition-shadow"
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
            face_cards.append(face_card(
                face_id=face_id,
                crop_url=crop_url,
                era=era,
                identity_id=identity_id,
            ))

    if not face_cards:
        return None

    border_colors = {
        "emerald": "border-l-emerald-500",
        "amber": "border-l-amber-500",
        "red": "border-l-red-500",
    }

    return Div(
        # Header with name and state
        Div(
            H3(name, cls="text-lg font-serif font-bold text-stone-800"),
            state_badge(state),
            Span(
                f"{len(face_cards)} face{'s' if len(face_cards) != 1 else ''}",
                cls="text-xs text-stone-400 ml-2"
            ),
            cls="flex items-center gap-3 mb-3"
        ),
        # Face grid
        Div(
            *face_cards,
            cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3"
        ),
        # Action buttons for PROPOSED identities
        action_buttons(identity_id) if show_actions and state == "PROPOSED" else None,
        cls=f"identity-card bg-stone-50 border border-stone-200 border-l-4 {border_colors.get(lane_color, '')} p-4 rounded-r shadow-sm mb-4",
        id=f"identity-{identity_id}"
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
        "emerald": "bg-emerald-50/50",
        "amber": "bg-amber-50/50",
        "red": "bg-red-50/50",
    }

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
        Div(*cards, id=lane_id) if cards else P(
            f"No {title.lower()} identities",
            cls="text-stone-400 italic text-center py-8"
        ),
        cls=f"mb-8 p-4 rounded {bg_colors.get(color, '')}"
    )


# =============================================================================
# ROUTES - PHASE 2: TEACH MODE
# =============================================================================

@rt("/")
def get():
    """
    Main workstation view.
    Renders identities in three lanes by state.
    """
    registry = load_registry()
    crop_files = get_crop_files()

    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    contested = registry.list_identities(state=IdentityState.CONTESTED)

    confirmed.sort(key=lambda x: (x.get("name") or "", x.get("updated_at", "")))
    proposed.sort(key=lambda x: x.get("version_id", 0), reverse=True)
    contested.sort(key=lambda x: x.get("version_id", 0), reverse=True)

    has_data = confirmed or proposed or contested

    if has_data:
        content = Div(
            # Proposed lane has action buttons enabled
            lane_section("Proposed", proposed, crop_files, "amber", "?",
                        show_actions=True, lane_id="proposed-lane"),
            lane_section("Confirmed", confirmed, crop_files, "emerald", "\u2713",
                        lane_id="confirmed-lane"),
            lane_section("Contested", contested, crop_files, "red", "\u26a0",
                        lane_id="contested-lane"),
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
            toast("System busy. Please try again.", "warning"),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            toast("Identity not found.", "error"),
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
            toast(f"Cannot confirm: {str(e)}", "error"),
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
            toast("System busy. Please try again.", "warning"),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            toast("Identity not found.", "error"),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    try:
        registry.contest_identity(identity_id, user_source="web", reason="Rejected via UI")
        save_registry(registry)
    except Exception as e:
        return Response(
            toast(f"Cannot reject: {str(e)}", "error"),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"}
        )

    crop_files = get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    return (
        identity_card(updated_identity, crop_files, lane_color="red", show_actions=False),
        toast("Identity contested.", "warning"),
    )


if __name__ == "__main__":
    serve()
