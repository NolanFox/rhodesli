"""
Temporal analysis routes — event group timeline display.

Admin-only pages for viewing temporal event groupings from ML analysis.
"""

import json
import logging
from pathlib import Path

from fasthtml.common import *

from app.auth import get_current_user
from app.main import rt
import app.main as _main_mod

logger = logging.getLogger(__name__)

# Path to the event groups data file
EVENT_GROUPS_PATH = Path(__file__).parent.parent / "rhodesli_ml" / "data" / "event_groups.json"


def _load_event_groups() -> dict | None:
    """Load event groups JSON data. Returns None if file not found."""
    if not EVENT_GROUPS_PATH.exists():
        return None
    try:
        with open(EVENT_GROUPS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load event_groups.json: %s", e)
        return None


def _unique_identified_people(identified_faces: dict) -> list[dict]:
    """Deduplicate identified faces by identity_id, summing appearances."""
    by_id = {}
    for face_info in identified_faces.values():
        iid = face_info["identity_id"]
        if iid not in by_id:
            by_id[iid] = {
                "identity_id": iid,
                "name": face_info["name"],
                "total_appearances": 0,
            }
        by_id[iid]["total_appearances"] += face_info.get("appearances", 1)
    return sorted(by_id.values(), key=lambda x: x["total_appearances"], reverse=True)


def _event_group_card(group: dict, index: int, nav_prefix: str) -> Div:
    """Render a single event group as a timeline card."""
    date_range = group.get("date_range", [])
    date_label = f"{date_range[0]}--{date_range[1]}" if len(date_range) == 2 else "Unknown"

    num_photos = group.get("num_photos", 0)
    total_faces = group.get("total_faces", 0)
    identified_count = group.get("identified_count", 0)
    unidentified_count = group.get("unidentified_count", 0)
    contains_esther = group.get("contains_esther", False)
    contains_albert = group.get("contains_albert", False)

    # Key people badges
    key_people_badges = []
    if contains_esther:
        key_people_badges.append(
            Span(
                "Esther",
                cls="px-2 py-0.5 text-xs rounded-full bg-amber-900/50 text-amber-300 border border-amber-700/50",
            )
        )
    if contains_albert:
        key_people_badges.append(
            Span(
                "Albert",
                cls="px-2 py-0.5 text-xs rounded-full bg-indigo-900/50 text-indigo-300 border border-indigo-700/50",
            )
        )

    # Identified people list
    identified_faces = group.get("identified_faces", {})
    people = _unique_identified_people(identified_faces)
    people_items = []
    for p in people[:10]:  # Show up to 10
        people_items.append(
            A(
                p["name"],
                Span(f" ({p['total_appearances']}x)", cls="text-slate-500") if p["total_appearances"] > 1 else "",
                href=f"{nav_prefix}/person/{p['identity_id']}",
                cls="text-sm text-indigo-400 hover:text-indigo-300 transition-colors",
            )
        )

    people_section = (
        Div(
            Span("Identified: ", cls="text-xs text-slate-500 font-semibold uppercase tracking-wider"),
            Div(*[Div(item) for item in people_items], cls="mt-1 space-y-0.5"),
            cls="mt-3",
        )
        if people_items
        else ""
    )

    # Photo links
    photo_ids = group.get("photo_ids", [])
    photo_links = []
    for pid in photo_ids[:8]:  # Show up to 8
        photo_links.append(
            A(
                Span(cls="w-2 h-2 rounded-full bg-slate-500 inline-block mr-1"),
                pid[:30] + "..." if len(pid) > 30 else pid,
                href=f"{nav_prefix}/photo/{pid}",
                cls="text-xs text-slate-400 hover:text-slate-200 transition-colors block truncate",
            )
        )
    if len(photo_ids) > 8:
        photo_links.append(Span(f"+ {len(photo_ids) - 8} more", cls="text-xs text-slate-500"))

    photos_section = Div(
        Span("Photos: ", cls="text-xs text-slate-500 font-semibold uppercase tracking-wider"),
        Div(*photo_links, cls="mt-1 space-y-0.5"),
        cls="mt-3",
    )

    return Div(
        # Timeline dot and connector
        Div(
            Div(cls="w-3 h-3 rounded-full bg-indigo-500 border-2 border-slate-800 relative z-10"),
            Div(cls="absolute top-3 left-1.5 w-px h-full bg-slate-700 -translate-x-1/2")
            if index < 99  # Always show connector except we clip via CSS on last
            else "",
            cls="relative flex-shrink-0 w-6",
        ),
        # Card content
        Div(
            # Header
            Div(
                H3(date_label, cls="text-lg font-semibold text-white"),
                Div(*key_people_badges, cls="flex gap-2") if key_people_badges else "",
                cls="flex items-center justify-between flex-wrap gap-2",
            ),
            # Stats row
            Div(
                Span(f"{num_photos} photo{'s' if num_photos != 1 else ''}", cls="text-sm text-slate-300"),
                Span("  |  ", cls="text-slate-600"),
                Span(f"{identified_count} identified", cls="text-sm text-emerald-400"),
                Span("  |  ", cls="text-slate-600"),
                Span(f"{unidentified_count} unidentified", cls="text-sm text-amber-400"),
                Span("  |  ", cls="text-slate-600"),
                Span(f"{total_faces} total faces", cls="text-sm text-slate-400"),
                cls="mt-2 flex items-center flex-wrap gap-x-0",
            ),
            people_section,
            photos_section,
            cls="bg-slate-800 rounded-xl p-5 border border-slate-700 flex-1 ml-3",
        ),
        cls="flex items-start mb-4",
    )


def _companion_card(companion: dict, nav_prefix: str) -> Div:
    """Render a frequent companion card with age trajectory."""
    identity_id = companion.get("identity_id", "")
    identity_name = companion.get("identity_name", "Unknown")
    num_faces = companion.get("num_faces", 0)
    event_group_count = companion.get("event_group_count", 0)

    # Age trajectory entries
    trajectory = companion.get("age_trajectory", [])
    trajectory_rows = []
    for entry in trajectory:
        year = entry.get("year", "?")
        age = entry.get("estimated_age", "?")
        gender = entry.get("gender", "")
        description = entry.get("description", "")
        photo_id = entry.get("photo_id", "")

        photo_link = (
            A(
                "View photo",
                href=f"{nav_prefix}/photo/{photo_id}",
                cls="text-xs text-indigo-400 hover:text-indigo-300 ml-2",
            )
            if photo_id
            else ""
        )

        trajectory_rows.append(
            Div(
                Div(
                    Span(str(year), cls="text-sm font-semibold text-amber-400 w-12 inline-block"),
                    Span(f"~{age} yrs", cls="text-sm text-slate-300 w-16 inline-block"),
                    Span(gender, cls="text-xs text-slate-500 w-16 inline-block"),
                    photo_link,
                    cls="flex items-center gap-2",
                ),
                P(description, cls="text-xs text-slate-400 mt-0.5 ml-12 leading-relaxed") if description else "",
                cls="py-2 border-b border-slate-700/50 last:border-0",
            )
        )

    # Event details
    event_details = companion.get("event_details", [])
    event_chips = []
    for ev in event_details:
        dr = ev.get("date_range", [])
        label = f"{dr[0]}--{dr[1]}" if len(dr) == 2 else "?"
        with_e = ev.get("with_esther", False)
        with_a = ev.get("with_albert", False)
        context_parts = []
        if with_e:
            context_parts.append("w/ Esther")
        if with_a:
            context_parts.append("w/ Albert")
        context = f" ({', '.join(context_parts)})" if context_parts else ""
        event_chips.append(
            Span(
                f"{label}{context}",
                cls="px-2 py-0.5 text-xs rounded-full bg-slate-700 text-slate-300",
            )
        )

    return Div(
        Div(
            A(
                identity_name,
                href=f"{nav_prefix}/person/{identity_id}",
                cls="text-lg font-semibold text-indigo-400 hover:text-indigo-300 transition-colors",
            ),
            Div(
                Span(f"{num_faces} face{'s' if num_faces != 1 else ''}", cls="text-sm text-slate-400"),
                Span("  |  ", cls="text-slate-600"),
                Span(
                    f"Appears in {event_group_count} event group{'s' if event_group_count != 1 else ''}",
                    cls="text-sm text-slate-400",
                ),
                cls="mt-1",
            ),
            cls="mb-3",
        ),
        # Event group chips
        Div(
            Span("Event groups: ", cls="text-xs text-slate-500 font-semibold uppercase tracking-wider mr-2"),
            *event_chips,
            cls="flex items-center flex-wrap gap-2 mb-3",
        )
        if event_chips
        else "",
        # Age trajectory table
        Div(
            Span("Age trajectory: ", cls="text-xs text-slate-500 font-semibold uppercase tracking-wider"),
            Div(*trajectory_rows, cls="mt-2"),
            cls="mt-2",
        )
        if trajectory_rows
        else "",
        cls="bg-slate-800 rounded-xl p-5 border border-slate-700",
    )


@rt("/admin/event-groups")
def get(request, sess=None):
    """Admin page displaying temporal event groups as a timeline."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    user = get_current_user(sess or {})
    community = getattr(request.state, "community", None) if request else None
    community_name = community.get("name", "Rhodesli") if community else "Rhodesli"
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    data = _load_event_groups()

    if data is None:
        from app.admin_routes import _admin_nav_bar

        return Title(f"Event Groups — {community_name}"), Div(
            _admin_nav_bar("event-groups", request=request),
            Div(
                H1("Event Groups", cls="text-2xl font-bold text-white"),
                P(
                    "No event group data found. Run the temporal analysis pipeline to generate event_groups.json.",
                    cls="text-slate-400 mt-2",
                ),
                cls="max-w-5xl mx-auto p-6",
            ),
        )

    metadata = data.get("metadata", {})
    event_groups = data.get("event_groups", [])
    companions = data.get("frequent_companions", [])

    # Sort event groups by date range start
    event_groups_sorted = sorted(event_groups, key=lambda g: g.get("date_range", [0])[0])

    # Summary stats
    total_groups = len(event_groups)
    total_photos = sum(g.get("num_photos", 0) for g in event_groups)
    total_identified = sum(g.get("identified_count", 0) for g in event_groups)
    total_unidentified = sum(g.get("unidentified_count", 0) for g in event_groups)

    # Stat cards
    stat_cards = Div(
        _stat_card("Event Groups", str(total_groups), "indigo"),
        _stat_card("Photos", str(total_photos), "emerald"),
        _stat_card("Identified Faces", str(total_identified), "green"),
        _stat_card("Unidentified Faces", str(total_unidentified), "amber"),
        _stat_card("Companions", str(len(companions)), "purple"),
        cls="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-8",
    )

    # Metadata section
    meta_items = []
    if metadata.get("year_tolerance"):
        meta_items.append(Span(f"Year tolerance: {metadata['year_tolerance']}", cls="text-xs text-slate-400"))
    if metadata.get("frequent_companion_threshold"):
        meta_items.append(
            Span(
                f"Companion threshold: {metadata['frequent_companion_threshold']}+ groups", cls="text-xs text-slate-400"
            )
        )
    if metadata.get("total_dated_photos"):
        meta_items.append(Span(f"Total dated photos: {metadata['total_dated_photos']}", cls="text-xs text-slate-400"))

    meta_section = Div(*meta_items, cls="flex flex-wrap gap-4 mb-6 px-1") if meta_items else ""

    # Timeline
    timeline_cards = [_event_group_card(g, i, nav_prefix) for i, g in enumerate(event_groups_sorted)]

    timeline_section = Div(
        H2("Timeline", cls="text-xl font-semibold text-white mb-4"),
        Div(*timeline_cards, cls="relative"),
        cls="mb-10",
    )

    # Frequent companions section
    companion_cards = [_companion_card(c, nav_prefix) for c in companions]
    companions_section = (
        Div(
            H2("Frequent Companions", cls="text-xl font-semibold text-white mb-2"),
            P(
                "People who appear across multiple event groups alongside Esther and/or Albert.",
                cls="text-sm text-slate-400 mb-4",
            ),
            Div(*companion_cards, cls="space-y-4"),
            cls="mb-10",
        )
        if companion_cards
        else ""
    )

    from app.admin_routes import _admin_nav_bar

    return Title(f"Event Groups — {community_name}"), Div(
        _admin_nav_bar("event-groups", request=request),
        Div(H1("Event Groups", cls="text-2xl font-bold text-white"), cls="mb-6"),
        stat_cards,
        meta_section,
        timeline_section,
        companions_section,
        cls="max-w-5xl mx-auto p-6",
    )


def _stat_card(label: str, value: str, color: str) -> Div:
    """Small stat card."""
    color_map = {
        "emerald": "border-emerald-500 text-emerald-400",
        "amber": "border-amber-500 text-amber-400",
        "indigo": "border-indigo-500 text-indigo-400",
        "purple": "border-purple-500 text-purple-400",
        "green": "border-green-500 text-green-400",
        "slate": "border-slate-500 text-slate-300",
    }
    cls_str = color_map.get(color, "border-slate-500 text-slate-300")
    return Div(
        Div(value, cls=f"text-2xl font-bold {cls_str.split()[-1]}"),
        Div(label, cls="text-xs text-slate-400 mt-1"),
        cls=f"bg-slate-800 rounded-lg p-4 border-l-4 {cls_str.split()[0]}",
    )
