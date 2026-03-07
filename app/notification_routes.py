"""
Notification routes for PRD-028: Contributor Notifications P0.

Routes:
- GET /notifications — Full notifications page (logged-in users)
- POST /api/notifications/{id}/read — Mark single notification as read
- POST /api/notifications/mark-all-read — Mark all as read for user
- GET /api/notifications/count — Unread count for bell icon polling
- POST /api/notifications/create — Admin-only: create notification for testing
"""

import logging
from datetime import datetime

from fasthtml.common import *
from starlette.responses import JSONResponse, Response

from app.auth import get_current_user, is_auth_enabled
from app.main import rt
from app.supabase_data import get_supabase_client

import app.main as _main_mod

logger = logging.getLogger(__name__)

# Narrow exception types for Supabase operations
try:
    import httpx
    from postgrest.exceptions import APIError as PostgRESTError

    _SUPABASE_ERRORS = (httpx.HTTPError, PostgRESTError, ConnectionError, TimeoutError, OSError)
except ImportError:
    _SUPABASE_ERRORS = (ConnectionError, TimeoutError, OSError)


# =============================================================================
# HELPERS
# =============================================================================


def _check_login(sess) -> Response | None:
    """Return a 401 Response if user is not logged in, else None."""
    if not is_auth_enabled():
        return None
    user = get_current_user(sess or {})
    if not user:
        return Response("", status_code=401)
    return None


def _check_admin(sess) -> Response | None:
    """Return a 401/403 Response if user is not admin, else None."""
    if not is_auth_enabled():
        return None
    user = get_current_user(sess or {})
    if not user:
        return Response("", status_code=401)
    if not user.is_admin:
        return Response("Forbidden", status_code=403)
    return None


def _get_notifications(user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    """Fetch notifications for a user from Supabase, ordered by created_at desc."""
    sb = get_supabase_client()
    if not sb:
        return []
    try:
        result = (
            sb.table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data or []
    except _SUPABASE_ERRORS:
        logger.warning("Failed to fetch notifications from Supabase")
        return []


def _get_unread_count(user_id: str) -> int:
    """Get the count of unread notifications for a user."""
    sb = get_supabase_client()
    if not sb:
        return 0
    try:
        result = (
            sb.table("notifications").select("id", count="exact").eq("user_id", user_id).eq("is_read", False).execute()
        )
        return result.count or 0
    except _SUPABASE_ERRORS:
        logger.warning("Failed to fetch unread count from Supabase")
        return 0


def _mark_read(notification_id: str, user_id: str) -> bool:
    """Mark a single notification as read. Returns True on success."""
    sb = get_supabase_client()
    if not sb:
        return False
    try:
        sb.table("notifications").update({"is_read": True}).eq("id", notification_id).eq("user_id", user_id).execute()
        return True
    except _SUPABASE_ERRORS:
        logger.warning(f"Failed to mark notification {notification_id} as read")
        return False


def _mark_all_read(user_id: str) -> bool:
    """Mark all notifications as read for a user. Returns True on success."""
    sb = get_supabase_client()
    if not sb:
        return False
    try:
        sb.table("notifications").update({"is_read": True}).eq("user_id", user_id).eq("is_read", False).execute()
        return True
    except _SUPABASE_ERRORS:
        logger.warning("Failed to mark all notifications as read")
        return False


def _create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    body: str | None = None,
    photo_id: str | None = None,
    identity_id: str | None = None,
) -> dict | None:
    """Create a notification in Supabase. Returns the created row or None."""
    sb = get_supabase_client()
    if not sb:
        return None
    try:
        row = {
            "user_id": user_id,
            "notification_type": notification_type,
            "title": title,
            "body": body,
            "photo_id": photo_id,
            "identity_id": identity_id,
        }
        result = sb.table("notifications").insert(row).execute()
        return result.data[0] if result.data else None
    except _SUPABASE_ERRORS:
        logger.warning("Failed to create notification")
        return None


def create_identity_confirmed_notification(
    identity_id: str,
    identity_name: str,
    photo_ids: list[str] | None = None,
    user_id: str | None = None,
) -> dict | None:
    """Create a notification when an identity is confirmed.

    This is a helper that can be called from save_registry flows.
    For now it creates a notification for the admin user. In the future,
    it should notify the contributor who originally suggested the identity.

    Args:
        identity_id: UUID of the confirmed identity
        identity_name: Display name of the identity
        photo_ids: List of photo IDs associated with the identity
        user_id: Supabase auth user ID of the admin who confirmed.
                 Falls back to a system placeholder if not provided.

    Returns:
        The created notification row, or None if Supabase is unavailable.
    """
    target_user_id = user_id or "00000000-0000-0000-0000-000000000000"
    return _create_notification(
        user_id=target_user_id,
        notification_type="identity_confirmed",
        title=f"Identity Confirmed: {identity_name}",
        body=f'The identity "{identity_name}" has been confirmed by an admin.',
        identity_id=identity_id,
        photo_id=photo_ids[0] if photo_ids else None,
    )


# =============================================================================
# NOTIFICATION TYPE ICONS (SVG)
# =============================================================================

_ICON_MAP = {
    "identity_confirmed": (
        '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-emerald-400" fill="none" '
        'viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 '
        '11-18 0 9 9 0 0118 0z"/></svg>'
    ),
    "annotation_approved": (
        '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-blue-400" fill="none" '
        'viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M7 8h10M7 12h4m1 8l-4-4H5a2 '
        '2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"/></svg>'
    ),
    "default": (
        '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-slate-400" fill="none" '
        'viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 '
        "2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 "
        '8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>'
        "</svg>"
    ),
}


def _notification_icon(notification_type: str) -> str:
    """Get the SVG icon for a notification type."""
    return _ICON_MAP.get(notification_type, _ICON_MAP["default"])


def _time_ago(created_at: str) -> str:
    """Format a timestamp as a relative time string."""
    try:
        # Parse ISO 8601 timestamp (Supabase returns with timezone)
        ts_str = created_at.replace("Z", "+00:00")
        if "+" not in ts_str and "-" not in ts_str[10:]:
            ts_str += "+00:00"
        dt = datetime.fromisoformat(ts_str)
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%b %d")
    except (ValueError, TypeError):
        return ""


# =============================================================================
# UI COMPONENTS
# =============================================================================


def _notification_item(notif: dict) -> object:
    """Render a single notification as a list item."""
    notif_id = notif.get("id", "")
    is_read = notif.get("is_read", False)
    notification_type = notif.get("notification_type", "default")
    title = notif.get("title", "")
    body = notif.get("body", "")
    created_at = notif.get("created_at", "")
    identity_id = notif.get("identity_id")
    photo_id = notif.get("photo_id")

    # Build link target
    link_href = "#"
    if identity_id:
        link_href = f"/person/{identity_id}"
    elif photo_id:
        link_href = f"/photo/{photo_id}"

    bg_cls = "bg-slate-800/30" if is_read else "bg-slate-800/80 border-l-2 border-amber-500"

    return Div(
        A(
            Div(
                Div(
                    NotStr(_notification_icon(notification_type)),
                    cls="flex-shrink-0 mt-0.5",
                ),
                Div(
                    P(title, cls="text-sm font-medium text-slate-200"),
                    P(body, cls="text-xs text-slate-400 mt-0.5 line-clamp-2") if body else None,
                    P(_time_ago(created_at), cls="text-xs text-slate-500 mt-1"),
                    cls="flex-1 min-w-0",
                ),
                cls="flex gap-3 items-start",
            ),
            href=link_href,
            hx_post=f"/api/notifications/{notif_id}/read" if not is_read else None,
            hx_swap="outerHTML" if not is_read else None,
            hx_target=f"#notif-{notif_id}" if not is_read else None,
            cls="block no-underline",
        ),
        cls=f"px-4 py-3 {bg_cls} hover:bg-slate-700/50 transition-colors rounded-lg",
        id=f"notif-{notif_id}",
    )


def _notifications_list(notifications: list[dict], offset: int = 0, page_size: int = 20) -> object:
    """Render the notification list with optional load-more button."""
    if not notifications:
        return Div(
            Div(
                NotStr(_ICON_MAP["default"]),
                P("No notifications yet", cls="text-slate-400 text-sm mt-2"),
                P(
                    "You'll be notified when identities you've helped with are confirmed.",
                    cls="text-slate-500 text-xs mt-1",
                ),
                cls="flex flex-col items-center py-12",
            ),
            id="notifications-list",
        )

    items = [_notification_item(n) for n in notifications]

    # Load more button if we got a full page
    load_more = None
    if len(notifications) >= page_size:
        next_offset = offset + page_size
        load_more = Button(
            "Load more",
            hx_get=f"/notifications?offset={next_offset}&partial=1",
            hx_target="#notifications-list",
            hx_swap="beforeend",
            cls="w-full py-2 text-sm text-slate-400 hover:text-white transition-colors mt-2",
        )

    return Div(*items, load_more, id="notifications-list", cls="space-y-1")


# =============================================================================
# ROUTES
# =============================================================================


@rt("/notifications")
def get(sess, offset: int = 0, partial: int = 0):
    """GET /notifications — Full notifications page or partial list for pagination."""
    denied = _check_login(sess)
    if denied:
        return denied

    user = get_current_user(sess or {})
    page_size = 20
    notifications = _get_notifications(user.id, limit=page_size, offset=offset)

    # Partial response for HTMX pagination
    if partial:
        items = [_notification_item(n) for n in notifications]
        load_more = None
        if len(notifications) >= page_size:
            next_offset = offset + page_size
            load_more = Button(
                "Load more",
                hx_get=f"/notifications?offset={next_offset}&partial=1",
                hx_target="#notifications-list",
                hx_swap="beforeend",
                cls="w-full py-2 text-sm text-slate-400 hover:text-white transition-colors mt-2",
            )
        return Div(*items, load_more)

    unread_count = _get_unread_count(user.id)
    nav_links = _main_mod._public_nav_links(active="notifications", user=user)
    nav = _main_mod._public_page_nav(nav_links, active="notifications", user=user)

    mark_all_btn = None
    if unread_count > 0:
        mark_all_btn = Button(
            "Mark all as read",
            hx_post="/api/notifications/mark-all-read",
            hx_target="#notifications-container",
            hx_swap="innerHTML",
            cls="text-sm text-amber-400 hover:text-amber-300 transition-colors",
        )

    content = Div(
        Div(
            Div(
                H1("Notifications", cls="text-xl font-display font-bold text-white"),
                Span(
                    f"{unread_count} unread",
                    cls="text-sm text-slate-400",
                )
                if unread_count > 0
                else None,
                cls="flex items-center gap-3",
            ),
            mark_all_btn,
            cls="flex items-center justify-between mb-6",
        ),
        _notifications_list(notifications, offset=offset, page_size=page_size),
        cls="max-w-2xl mx-auto px-6 py-8",
        id="notifications-container",
    )

    return (
        Title("Notifications — Rhodesli"),
        Main(
            nav,
            content,
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/api/notifications/{notification_id}/read")
def post(sess, notification_id: str):
    """POST /api/notifications/{id}/read — Mark a single notification as read."""
    denied = _check_login(sess)
    if denied:
        return denied

    user = get_current_user(sess or {})
    _mark_read(notification_id, user.id)

    # Re-fetch the notification to render the updated item
    sb = get_supabase_client()
    if sb:
        try:
            result = sb.table("notifications").select("*").eq("id", notification_id).execute()
            if result.data:
                return _notification_item(result.data[0])
        except _SUPABASE_ERRORS:
            pass

    # Fallback: just return a minimal read indicator
    return Div(
        P("Notification marked as read", cls="text-xs text-slate-500"),
        id=f"notif-{notification_id}",
    )


@rt("/api/notifications/mark-all-read")
def post(sess):
    """POST /api/notifications/mark-all-read — Mark all notifications as read."""
    denied = _check_login(sess)
    if denied:
        return denied

    user = get_current_user(sess or {})
    _mark_all_read(user.id)

    # Re-fetch all notifications (now marked read)
    notifications = _get_notifications(user.id, limit=20, offset=0)
    return _notifications_list(notifications, offset=0, page_size=20)


@rt("/api/notifications/count")
def get(sess):
    """GET /api/notifications/count — Returns unread count for bell icon polling."""
    denied = _check_login(sess)
    if denied:
        return denied

    user = get_current_user(sess or {})
    count = _get_unread_count(user.id)

    # Return just the badge element for HTMX swap
    if count > 0:
        return Span(
            str(count),
            cls="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold "
            "rounded-full w-4 h-4 flex items-center justify-center",
            id="notification-badge",
        )
    return Span(id="notification-badge", cls="hidden")


@rt("/api/notifications/create")
def post(sess, user_id: str = "", notification_type: str = "default", title: str = "", body: str = ""):
    """POST /api/notifications/create — Admin-only: create a notification for testing."""
    denied = _check_admin(sess)
    if denied:
        return denied

    if not user_id or not title:
        return Response("user_id and title are required", status_code=400)

    result = _create_notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        body=body,
    )

    if result:
        return JSONResponse(result, status_code=201)
    return Response("Failed to create notification", status_code=500)
