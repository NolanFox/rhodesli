"""
Rhodesli Forensic Workstation.

A triage-focused interface for identity verification with epistemic humility.
The UI reflects backend state - it never calculates probabilities.
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


def find_crop_for_face(face_id: str, crop_files: set) -> str:
    """Find the crop file matching a face_id."""
    # Direct match
    if face_id in crop_files:
        return face_id
    # Try with .jpg extension
    if f"{face_id}.jpg" in crop_files:
        return f"{face_id}.jpg"
    # Fuzzy match by prefix
    for crop in crop_files:
        if crop.startswith(face_id.split("_")[0]):
            return crop
    return None


# =============================================================================
# UI COMPONENTS
# =============================================================================

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


def face_card(
    face_id: str,
    crop_filename: str,
    quality: float = None,
    era: str = None,
    identity_id: str = None,
    show_actions: bool = False,
) -> Div:
    """
    Single face card with optional action buttons.
    UX Intent: Face-first display with metadata secondary.
    """
    if quality is None:
        quality = parse_quality_from_filename(crop_filename)

    # Phase 1: No actions yet (read-only)
    # Phase 2 will add confirm/reject buttons via show_actions

    return Div(
        # Image container with era badge
        Div(
            Img(
                src=f"/crops/{crop_filename}",
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
) -> Div:
    """
    Identity group card showing all anchors.
    UX Intent: Group context with individual face visibility.
    """
    identity_id = identity["identity_id"]
    name = identity.get("name") or f"Identity {identity_id[:8]}..."
    state = identity["state"]
    anchor_ids = identity["anchor_ids"]

    # Build face cards for each anchor
    face_cards = []
    for anchor in anchor_ids:
        # Handle both string and dict anchor formats
        if isinstance(anchor, str):
            face_id = anchor
            era = None
        else:
            face_id = anchor.get("face_id", "")
            era = anchor.get("era_bin")

        crop = find_crop_for_face(face_id, crop_files)
        if crop:
            face_cards.append(face_card(
                face_id=face_id,
                crop_filename=crop,
                era=era,
                identity_id=identity_id,
            ))

    if not face_cards:
        return None

    # Lane-specific border colors
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
        cls=f"bg-stone-50 border border-stone-200 border-l-4 {border_colors.get(lane_color, '')} p-4 rounded-r shadow-sm mb-4",
        id=f"identity-{identity_id}"
    )


def lane_section(title: str, identities: list, crop_files: set, color: str, icon: str) -> Div:
    """
    A swimlane for a specific identity state.
    UX Intent: Clear separation of epistemic states.
    """
    if not identities:
        return Div(
            P(
                f"No {title.lower()} identities",
                cls="text-stone-400 italic text-center py-8"
            ),
            cls="mb-8"
        )

    cards = []
    for identity in identities:
        card = identity_card(identity, crop_files, lane_color=color)
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
        # Cards
        Div(*cards) if cards else P("No matching faces found", cls="text-stone-400 italic"),
        cls=f"mb-8 p-4 rounded {bg_colors.get(color, '')}"
    )


# =============================================================================
# ROUTES - PHASE 1: READ-ONLY
# =============================================================================

@rt("/")
def get():
    """
    Main workstation view.
    Renders identities in three lanes by state.
    """
    registry = load_registry()
    crop_files = get_crop_files()

    # Get identities grouped by state
    confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    contested = registry.list_identities(state=IdentityState.CONTESTED)

    # Sort by appropriate criteria
    # Confirmed: by name then by most recent update
    confirmed.sort(key=lambda x: (x.get("name") or "", x.get("updated_at", "")))

    # Proposed: by version_id descending (newest first, as proxy for uncertainty)
    proposed.sort(key=lambda x: x.get("version_id", 0), reverse=True)

    # Contested: by version_id descending (most active disputes first)
    contested.sort(key=lambda x: x.get("version_id", 0), reverse=True)

    # Build lanes
    has_data = confirmed or proposed or contested

    if has_data:
        content = Div(
            lane_section("Confirmed", confirmed, crop_files, "emerald", "\u2713"),
            lane_section("Proposed", proposed, crop_files, "amber", "?"),
            lane_section("Contested", contested, crop_files, "red", "\u26a0"),
            cls="max-w-7xl mx-auto"
        )
    else:
        # Fallback: show crops as uncategorized gallery
        # UX Intent: Graceful degradation when no registry exists
        crops_dir = static_path / "crops"
        faces = []
        for f in crops_dir.glob("*.jpg"):
            quality = parse_quality_from_filename(f.name)
            faces.append((f.name, quality))
        faces.sort(key=lambda x: x[1], reverse=True)

        cards = [
            face_card(face_id=fn, crop_filename=fn, quality=q)
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
    """)

    return Title("Rhodesli Forensic Workstation"), style, Main(
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


if __name__ == "__main__":
    serve()
