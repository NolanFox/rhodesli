"""
Event routes for Life Events & Context Graph (PRD-011).

All /events/* and /api/events/* routes.
Shared helpers (caches, registries, UI builders) remain in app.main.
"""

import logging

from fasthtml.common import *
from starlette.responses import Response

from app.auth import get_current_user, is_auth_enabled
from app.supabase_data import get_supabase_client

# Import route decorator only (bound once, never reassigned)
from app.main import rt
from app.utils import photo_url

# All other main.py functions accessed via module reference
import app.main as _main_mod

logger = logging.getLogger(__name__)

# Valid event types
EVENT_TYPES = [
    "wedding",
    "funeral",
    "holiday",
    "reunion",
    "immigration",
    "graduation",
    "birthday",
    "military",
    "business",
    "other",
]

# Icons for event types (emoji)
EVENT_TYPE_ICONS = {
    "wedding": "💒",
    "funeral": "🕯️",
    "holiday": "🎉",
    "reunion": "👨‍👩‍👧‍👦",
    "immigration": "🚢",
    "graduation": "🎓",
    "birthday": "🎂",
    "military": "⚔️",
    "business": "💼",
    "other": "📌",
}


def _check_admin(sess) -> Response | None:
    """Return a 401/403 Response if user is not admin, else None."""
    return _main_mod._check_admin(sess)


# =============================================================================
# DATA ACCESS — Supabase-backed
# =============================================================================


def list_events(event_type=None, year_from=None, year_to=None, identity_id=None):
    """List all events, optionally filtered."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        query = client.table("life_events").select("*").order("event_year", desc=True)

        if event_type:
            query = query.eq("event_type", event_type)
        if year_from:
            query = query.gte("event_year", int(year_from))
        if year_to:
            query = query.lte("event_year", int(year_to))

        result = query.execute()
        events = result.data or []

        # If filtering by identity, get event IDs for that identity first
        if identity_id:
            ep_result = client.table("event_participants").select("event_id").eq("identity_id", identity_id).execute()
            event_ids = {ep["event_id"] for ep in (ep_result.data or [])}
            events = [e for e in events if e["id"] in event_ids]

        return events
    except Exception:
        logger.exception("Failed to list events")
        return []


def get_event(event_id):
    """Get a single event by ID."""
    client = get_supabase_client()
    if not client:
        return None

    try:
        result = client.table("life_events").select("*").eq("id", event_id).execute()
        return result.data[0] if result.data else None
    except Exception:
        logger.exception("Failed to get event %s", event_id)
        return None


def get_event_participants(event_id):
    """Get participants for an event."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        result = client.table("event_participants").select("*").eq("event_id", event_id).execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to get participants for event %s", event_id)
        return []


def get_event_photos(event_id):
    """Get photos linked to an event."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        result = client.table("event_photos").select("*").eq("event_id", event_id).execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to get photos for event %s", event_id)
        return []


def get_events_for_photo(photo_id):
    """Get all events linked to a specific photo."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        ep_result = client.table("event_photos").select("event_id").eq("photo_id", photo_id).execute()
        event_ids = [ep["event_id"] for ep in (ep_result.data or [])]
        if not event_ids:
            return []

        result = client.table("life_events").select("*").in_("id", event_ids).execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to get events for photo %s", photo_id)
        return []


def get_events_for_person(identity_id):
    """Get all events a person participated in."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        ep_result = client.table("event_participants").select("event_id").eq("identity_id", identity_id).execute()
        event_ids = [ep["event_id"] for ep in (ep_result.data or [])]
        if not event_ids:
            return []

        result = client.table("life_events").select("*").in_("id", event_ids).order("event_year", desc=True).execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to get events for person %s", identity_id)
        return []


def create_event(data: dict):
    """Create a new event. Returns the created event dict or None."""
    client = get_supabase_client()
    if not client:
        return None

    try:
        result = client.table("life_events").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception:
        logger.exception("Failed to create event")
        return None


def link_photo_to_event(event_id, photo_id):
    """Link a photo to an event."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("event_photos").insert({"event_id": event_id, "photo_id": photo_id}).execute()
        return True
    except Exception:
        logger.exception("Failed to link photo %s to event %s", photo_id, event_id)
        return False


def unlink_photo_from_event(event_id, photo_id):
    """Unlink a photo from an event."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("event_photos").delete().eq("event_id", event_id).eq("photo_id", photo_id).execute()
        return True
    except Exception:
        logger.exception("Failed to unlink photo %s from event %s", photo_id, event_id)
        return False


def link_participant_to_event(event_id, identity_id, role="attendee"):
    """Link a person to an event."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("event_participants").insert(
            {"event_id": event_id, "identity_id": identity_id, "role": role}
        ).execute()
        return True
    except Exception:
        logger.exception("Failed to link participant %s to event %s", identity_id, event_id)
        return False


def unlink_participant_from_event(event_id, identity_id):
    """Unlink a person from an event."""
    client = get_supabase_client()
    if not client:
        return False

    try:
        client.table("event_participants").delete().eq("event_id", event_id).eq("identity_id", identity_id).execute()
        return True
    except Exception:
        logger.exception("Failed to unlink participant %s from event %s", identity_id, event_id)
        return False


# =============================================================================
# UI HELPERS
# =============================================================================


def _event_type_badge(event_type):
    """Render an event type badge with icon."""
    icon = EVENT_TYPE_ICONS.get(event_type, "📌")
    label = event_type.replace("_", " ").title()
    return Span(
        f"{icon} {label}",
        cls="inline-block px-2 py-0.5 bg-slate-700 text-slate-300 text-xs rounded-full",
    )


def _event_date_display(event):
    """Format event date for display."""
    precision = event.get("date_precision", "year")
    if event.get("event_date"):
        date_str = event["event_date"]
        if precision == "exact":
            return date_str
        elif precision == "month":
            return date_str[:7]  # YYYY-MM
        else:
            return str(event.get("event_year", date_str[:4]))
    elif event.get("event_year"):
        return str(event["event_year"])
    return "Date unknown"


def _event_card(event, show_photo_count=False, show_participant_count=False):
    """Render an event card for lists."""
    icon = EVENT_TYPE_ICONS.get(event.get("event_type", "other"), "📌")
    date_str = _event_date_display(event)

    meta_parts = [date_str]
    if event.get("location_name"):
        meta_parts.append(event["location_name"])

    return A(
        Div(
            Div(
                Span(icon, cls="text-lg mr-2"),
                Span(
                    event.get("title", "Untitled Event"),
                    cls="font-medium text-white truncate",
                ),
                cls="flex items-center",
            ),
            P(
                " · ".join(meta_parts),
                cls="text-xs text-slate-400 mt-1 truncate",
            ),
            cls="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:border-indigo-500/50 transition-colors",
        ),
        href=f"/events/{event['id']}",
        cls="block",
        data_testid=f"event-card-{event['id']}",
    )


def _event_form(event=None):
    """Render event creation/edit form."""
    event = event or {}

    type_options = [
        Option(
            t.replace("_", " ").title(),
            value=t,
            selected=(t == event.get("event_type")),
        )
        for t in EVENT_TYPES
    ]

    return Form(
        Div(
            Label("Event Type", cls="text-xs text-slate-400 block mb-1"),
            Select(
                *type_options,
                name="event_type",
                cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white",
                required=True,
            ),
            cls="mb-3",
        ),
        Div(
            Label("Title", cls="text-xs text-slate-400 block mb-1"),
            Input(
                type="text",
                name="title",
                value=event.get("title", ""),
                placeholder="e.g., Wedding of Selma & David",
                cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500",
                required=True,
            ),
            cls="mb-3",
        ),
        Div(
            Label("Description", cls="text-xs text-slate-400 block mb-1"),
            Textarea(
                event.get("description", ""),
                name="description",
                placeholder="Details about the event...",
                rows=3,
                cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 resize-none",
            ),
            cls="mb-3",
        ),
        Div(
            Div(
                Label("Date", cls="text-xs text-slate-400 block mb-1"),
                Input(
                    type="date",
                    name="event_date",
                    value=event.get("event_date", ""),
                    cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white",
                ),
                cls="flex-1",
            ),
            Div(
                Label("Year (if no exact date)", cls="text-xs text-slate-400 block mb-1"),
                Input(
                    type="number",
                    name="event_year",
                    value=event.get("event_year", ""),
                    placeholder="e.g., 1935",
                    cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500",
                    min=1800,
                    max=2100,
                ),
                cls="flex-1",
            ),
            Div(
                Label("Date Precision", cls="text-xs text-slate-400 block mb-1"),
                Select(
                    Option("Year", value="year", selected=event.get("date_precision", "year") == "year"),
                    Option("Month", value="month", selected=event.get("date_precision") == "month"),
                    Option("Exact", value="exact", selected=event.get("date_precision") == "exact"),
                    name="date_precision",
                    cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white",
                ),
                cls="flex-1",
            ),
            cls="flex gap-3 mb-3",
        ),
        Div(
            Label("Location", cls="text-xs text-slate-400 block mb-1"),
            Input(
                type="text",
                name="location_name",
                value=event.get("location_name", ""),
                placeholder="e.g., Rhodes, Greece",
                cls="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500",
            ),
            cls="mb-3",
        ),
        Button(
            "Create Event",
            type="submit",
            cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg transition-colors",
        ),
        hx_post="/api/events",
        hx_target="#event-form-result",
        hx_swap="innerHTML",
        data_testid="event-form",
    )


def photo_events_section(photo_id, is_admin=False):
    """Build the events section for a photo detail page."""
    events = get_events_for_photo(photo_id)

    event_items = [_event_card(e) for e in events]

    # Admin: add to event form
    add_to_event_form = None
    if is_admin:
        all_events = list_events()
        event_options = [Option("-- Select Event --", value="", disabled=True, selected=True)]
        event_options += [
            Option(
                f"{EVENT_TYPE_ICONS.get(e.get('event_type', 'other'), '📌')} {e.get('title', 'Untitled')} ({_event_date_display(e)})",
                value=e["id"],
            )
            for e in all_events
        ]
        event_options.append(Option("+ Create New Event...", value="__new__"))

        add_to_event_form = Div(
            Form(
                Select(
                    *event_options,
                    name="event_id",
                    cls="bg-slate-800 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white",
                    id=f"add-event-select-{photo_id}",
                ),
                Button(
                    "Link",
                    type="submit",
                    cls="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg ml-2",
                ),
                hx_post="/api/events/__target__/photos",
                hx_target=f"#photo-events-{photo_id}",
                hx_swap="innerHTML",
                hx_vals=f'{{"photo_id": "{photo_id}"}}',
                cls="flex items-center gap-2 mt-3",
                data_testid="add-to-event-form",
            ),
            Div(id="event-form-result"),
        )

    content = Div(
        *event_items if event_items else [P("No events linked to this photo yet.", cls="text-slate-500 text-sm")],
        add_to_event_form if add_to_event_form else None,
        id=f"photo-events-{photo_id}",
    )

    return Section(
        Div(
            H3(
                "Events",
                cls="text-lg font-serif font-semibold text-white mb-3",
            ),
            content,
            cls="max-w-[900px] mx-auto",
        ),
        cls="px-4 sm:px-6 py-6 border-t border-slate-800/50",
        data_testid="photo-events-section",
    )


def person_events_section(identity_id):
    """Build the life events section for a person detail page."""
    events = get_events_for_person(identity_id)

    if not events:
        return None

    event_items = [_event_card(e) for e in events]

    return Div(
        H3(
            "Life Events",
            cls="text-lg font-serif font-semibold text-white mb-4",
        ),
        Div(
            *event_items,
            cls="grid gap-2",
        ),
        cls="mt-8 pt-6 border-t border-slate-800",
        data_testid="person-events-section",
    )


# =============================================================================
# ROUTES — Events
# =============================================================================


@rt("/events")
def get(
    event_type: str = None,
    year_from: str = None,
    year_to: str = None,
    identity_id: str = None,
    sess=None,
):
    """Browse all events (admin view initially)."""
    user = get_current_user(sess or {}) if is_auth_enabled() else None
    user_is_admin = (user.is_admin if user else False) if is_auth_enabled() else True

    events = list_events(
        event_type=event_type,
        year_from=year_from,
        year_to=year_to,
        identity_id=identity_id,
    )

    # Build filter bar
    type_options = [Option("All Types", value="")]
    type_options += [
        Option(
            f"{EVENT_TYPE_ICONS.get(t, '📌')} {t.replace('_', ' ').title()}",
            value=t,
            selected=(t == event_type),
        )
        for t in EVENT_TYPES
    ]

    filter_bar = Div(
        Form(
            Select(
                *type_options,
                name="event_type",
                cls="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white",
            ),
            Input(
                type="number",
                name="year_from",
                placeholder="From year",
                value=year_from or "",
                cls="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-28",
                min=1800,
                max=2100,
            ),
            Input(
                type="number",
                name="year_to",
                placeholder="To year",
                value=year_to or "",
                cls="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 w-28",
                min=1800,
                max=2100,
            ),
            Button(
                "Filter",
                type="submit",
                cls="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg",
            ),
            cls="flex flex-wrap gap-3 items-center",
            method="get",
            action="/events",
        ),
        cls="mb-6",
    )

    # Event list
    event_cards = [_event_card(e) for e in events]

    # Create event section (admin only)
    create_section = None
    if user_is_admin:
        create_section = Div(
            Details(
                Summary(
                    "Create New Event",
                    cls="text-indigo-400 hover:text-indigo-300 cursor-pointer text-sm font-medium",
                ),
                Div(
                    _event_form(),
                    Div(id="event-form-result", cls="mt-3"),
                    cls="mt-4",
                ),
                cls="mt-6 bg-slate-800/50 rounded-lg p-4 border border-slate-700/50",
            ),
        )

    nav_links = _main_mod._public_nav_links(active="events", user=user)

    return (
        Title("Life Events — Rhodesli Heritage Archive"),
        Style("html, body { margin: 0; } body { background-color: #0f172a; }"),
        Main(
            _main_mod._public_page_nav(nav_links, active="events", user=user),
            Section(
                Div(
                    H1("Life Events", cls="text-2xl font-serif font-bold text-white mb-2"),
                    P(
                        f"{len(events)} event{'s' if len(events) != 1 else ''} in the archive",
                        cls="text-slate-400 text-sm mb-6",
                    ),
                    filter_bar,
                    Div(
                        *event_cards if event_cards else [P("No events found.", cls="text-slate-500 text-sm")],
                        cls="grid gap-3",
                    ),
                    create_section if create_section else None,
                    cls="max-w-3xl mx-auto",
                ),
                cls="px-4 sm:px-6 py-10",
            ),
            cls="min-h-screen bg-slate-900 text-white",
        ),
    )


@rt("/events/{event_id}")
def get(event_id: str, sess=None):
    """Event detail page."""
    user = get_current_user(sess or {}) if is_auth_enabled() else None
    user_is_admin = (user.is_admin if user else False) if is_auth_enabled() else True

    event = get_event(event_id)
    if not event:
        return Response("Event not found", status_code=404)

    participants = get_event_participants(event_id)
    photos = get_event_photos(event_id)

    # Resolve participant names
    registry = _main_mod.load_registry()
    participant_items = []
    for p in participants:
        identity_id = p.get("identity_id", "")
        try:
            identity = registry.get_identity(identity_id)
            name = identity.get("name", "Unknown")
        except (KeyError, AttributeError):
            name = "Unknown Person"

        participant_items.append(
            Div(
                A(
                    name,
                    href=f"/person/{identity_id}",
                    cls="text-indigo-400 hover:text-indigo-300 text-sm",
                ),
                Span(f" ({p.get('role', 'attendee')})", cls="text-slate-500 text-xs")
                if p.get("role") and p["role"] != "attendee"
                else None,
                # Admin: unlink button
                Button(
                    "Remove",
                    hx_delete=f"/api/events/{event_id}/participants/{identity_id}",
                    hx_target=f"#event-participants-{event_id}",
                    hx_swap="innerHTML",
                    hx_confirm="Remove this participant?",
                    cls="text-xs text-rose-400 hover:text-rose-300 ml-2",
                )
                if user_is_admin
                else None,
                cls="flex items-center py-1",
            )
        )

    # Resolve photo thumbnails
    photo_items = []
    for ep in photos:
        pid = ep.get("photo_id", "")
        photo_meta = _main_mod.get_photo_metadata(pid)
        if photo_meta:
            photo_items.append(
                Div(
                    A(
                        Img(
                            src=photo_url(photo_meta.get("filename", "")),
                            alt="Event photo",
                            cls="w-24 h-24 object-cover rounded-lg",
                        ),
                        href=f"/photo/{pid}",
                    ),
                    # Admin: unlink button
                    Button(
                        "x",
                        hx_delete=f"/api/events/{event_id}/photos/{pid}",
                        hx_target=f"#event-photos-{event_id}",
                        hx_swap="innerHTML",
                        hx_confirm="Unlink this photo?",
                        cls="absolute top-1 right-1 w-5 h-5 bg-black/60 text-white text-xs rounded-full hover:bg-rose-600",
                    )
                    if user_is_admin
                    else None,
                    cls="relative",
                )
            )

    # Admin: add participant form
    add_participant_form = None
    if user_is_admin:
        add_participant_form = Form(
            Input(
                type="text",
                name="identity_id",
                placeholder="Identity UUID",
                cls="bg-slate-800 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-500",
            ),
            Select(
                Option("Attendee", value="attendee"),
                Option("Bride", value="bride"),
                Option("Groom", value="groom"),
                Option("Organizer", value="organizer"),
                Option("Speaker", value="speaker"),
                Option("Other", value="other"),
                name="role",
                cls="bg-slate-800 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white",
            ),
            Button(
                "Add Participant",
                type="submit",
                cls="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg",
            ),
            hx_post=f"/api/events/{event_id}/participants",
            hx_target=f"#event-participants-{event_id}",
            hx_swap="innerHTML",
            cls="flex gap-2 mt-3",
            data_testid="add-participant-form",
        )

    # Admin: add photo form
    add_photo_form = None
    if user_is_admin:
        add_photo_form = Form(
            Input(
                type="text",
                name="photo_id",
                placeholder="Photo ID",
                cls="bg-slate-800 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-500",
            ),
            Button(
                "Add Photo",
                type="submit",
                cls="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg",
            ),
            hx_post=f"/api/events/{event_id}/photos",
            hx_target=f"#event-photos-{event_id}",
            hx_swap="innerHTML",
            cls="flex gap-2 mt-3",
            data_testid="add-photo-form",
        )

    icon = EVENT_TYPE_ICONS.get(event.get("event_type", "other"), "📌")
    date_str = _event_date_display(event)
    nav_links = _main_mod._public_nav_links(active="events", user=user)

    return (
        Title(f"{event.get('title', 'Event')} — Rhodesli Heritage Archive"),
        Style("html, body { margin: 0; } body { background-color: #0f172a; }"),
        Main(
            _main_mod._public_page_nav(nav_links, active="events", user=user),
            Section(
                Div(
                    # Back link
                    A(
                        "Back to Events",
                        href="/events",
                        cls="text-slate-400 hover:text-white text-sm mb-4 block",
                    ),
                    # Event header
                    Div(
                        Span(icon, cls="text-3xl mr-3"),
                        Div(
                            H1(
                                event.get("title", "Untitled Event"),
                                cls="text-2xl font-serif font-bold text-white",
                            ),
                            _event_type_badge(event.get("event_type", "other")),
                        ),
                        cls="flex items-start mb-4",
                    ),
                    # Date and location
                    Div(
                        P(f"Date: {date_str}", cls="text-slate-300 text-sm"),
                        P(
                            f"Location: {event.get('location_name', 'Unknown')}",
                            cls="text-slate-300 text-sm",
                        )
                        if event.get("location_name")
                        else None,
                        cls="mb-4",
                    ),
                    # Description
                    P(
                        event.get("description", ""),
                        cls="text-slate-400 leading-relaxed mb-6",
                    )
                    if event.get("description")
                    else None,
                    # Photos section
                    Div(
                        H2("Photos", cls="text-lg font-serif font-semibold text-white mb-3"),
                        Div(
                            *photo_items if photo_items else [P("No photos linked yet.", cls="text-slate-500 text-sm")],
                            cls="flex flex-wrap gap-3",
                            id=f"event-photos-{event_id}",
                        ),
                        add_photo_form if add_photo_form else None,
                        cls="mb-8",
                    ),
                    # Participants section
                    Div(
                        H2("Participants", cls="text-lg font-serif font-semibold text-white mb-3"),
                        Div(
                            *participant_items
                            if participant_items
                            else [P("No participants linked yet.", cls="text-slate-500 text-sm")],
                            id=f"event-participants-{event_id}",
                        ),
                        add_participant_form if add_participant_form else None,
                        cls="mb-8",
                    ),
                    cls="max-w-3xl mx-auto",
                ),
                cls="px-4 sm:px-6 py-10",
            ),
            cls="min-h-screen bg-slate-900 text-white",
        ),
    )


# =============================================================================
# API ROUTES — Event CRUD
# =============================================================================


@rt("/api/events")
def post(
    event_type: str,
    title: str,
    description: str = "",
    event_date: str = "",
    event_year: str = "",
    date_precision: str = "year",
    location_name: str = "",
    sess=None,
):
    """Create a new event (admin only)."""
    admin_check = _check_admin(sess)
    if admin_check:
        return admin_check

    if not title or not event_type:
        return Div(
            P("Title and event type are required.", cls="text-rose-400 text-sm"),
        )

    if event_type not in EVENT_TYPES:
        return Div(
            P(f"Invalid event type: {event_type}", cls="text-rose-400 text-sm"),
        )

    data = {
        "event_type": event_type,
        "title": title.strip(),
        "description": description.strip() if description else None,
        "location_name": location_name.strip() if location_name else None,
        "date_precision": date_precision,
    }

    if event_date:
        data["event_date"] = event_date
        # Extract year from date
        try:
            data["event_year"] = int(event_date[:4])
        except (ValueError, IndexError):
            pass
    elif event_year:
        try:
            data["event_year"] = int(event_year)
        except ValueError:
            return Div(
                P("Invalid year.", cls="text-rose-400 text-sm"),
            )

    user = get_current_user(sess or {}) if is_auth_enabled() else None
    if user:
        data["created_by"] = user.email

    event = create_event(data)
    if event:
        return Div(
            P(
                "Event created! ",
                A(
                    "View event",
                    href=f"/events/{event['id']}",
                    cls="text-indigo-400 hover:text-indigo-300 underline",
                ),
                cls="text-emerald-400 text-sm",
            ),
            data_testid="event-created",
        )
    else:
        return Div(
            P("Failed to create event. Check Supabase connection.", cls="text-rose-400 text-sm"),
        )


@rt("/api/events/{event_id}/photos")
def post(event_id: str, photo_id: str, sess=None):
    """Link a photo to an event (admin only)."""
    admin_check = _check_admin(sess)
    if admin_check:
        return admin_check

    if not photo_id:
        return P("Photo ID is required.", cls="text-rose-400 text-sm")

    success = link_photo_to_event(event_id, photo_id)
    if success:
        return P("Photo linked to event.", cls="text-emerald-400 text-sm")
    else:
        return P("Failed to link photo.", cls="text-rose-400 text-sm")


@rt("/api/events/{event_id}/participants")
def post(event_id: str, identity_id: str, role: str = "attendee", sess=None):
    """Link a person to an event (admin only)."""
    admin_check = _check_admin(sess)
    if admin_check:
        return admin_check

    if not identity_id:
        return P("Identity ID is required.", cls="text-rose-400 text-sm")

    success = link_participant_to_event(event_id, identity_id, role=role)
    if success:
        return P("Participant added to event.", cls="text-emerald-400 text-sm")
    else:
        return P("Failed to add participant.", cls="text-rose-400 text-sm")


@rt("/api/events/{event_id}/photos/{photo_id}")
def delete(event_id: str, photo_id: str, sess=None):
    """Unlink a photo from an event (admin only)."""
    admin_check = _check_admin(sess)
    if admin_check:
        return admin_check

    success = unlink_photo_from_event(event_id, photo_id)
    if success:
        return P("Photo unlinked.", cls="text-emerald-400 text-sm")
    else:
        return P("Failed to unlink photo.", cls="text-rose-400 text-sm")


@rt("/api/events/{event_id}/participants/{identity_id}")
def delete(event_id: str, identity_id: str, sess=None):
    """Unlink a person from an event (admin only)."""
    admin_check = _check_admin(sess)
    if admin_check:
        return admin_check

    success = unlink_participant_from_event(event_id, identity_id)
    if success:
        return P("Participant removed.", cls="text-emerald-400 text-sm")
    else:
        return P("Failed to remove participant.", cls="text-rose-400 text-sm")
