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
import os
from datetime import datetime

from fasthtml.common import *
from starlette.responses import JSONResponse, Response

from app.auth import get_current_user, is_auth_enabled
from app.main import rt
from app.supabase_data import get_supabase_client

import app.main as _main_mod

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

# Narrow exception types for Supabase operations
try:
    import httpx
    from postgrest.exceptions import APIError as PostgRESTError

    _SUPABASE_ERRORS = (httpx.HTTPError, PostgRESTError, ConnectionError, TimeoutError, OSError)
except ImportError:
    _SUPABASE_ERRORS = (ConnectionError, TimeoutError, OSError)


# =============================================================================
# EMAIL NOTIFICATIONS (Resend API)
# =============================================================================


def _build_notification_email_html(title: str, body: str, link_url: str | None = None) -> str:
    """Build an HTML email body with inline CSS (Lesson 12: email clients strip style blocks).

    Returns a simple, mobile-friendly email with Rhodesli branding.
    """
    button_html = ""
    if link_url:
        # Ensure absolute URL
        if link_url.startswith("/"):
            link_url = f"{_main_mod.SITE_URL}{link_url}"
        button_html = (
            '<tr><td style="padding: 20px 0 0 0;">'
            f'<a href="{link_url}" style="display: inline-block; padding: 12px 24px; '
            "background-color: #4f46e5; color: #ffffff; text-decoration: none; "
            'border-radius: 6px; font-weight: 600; font-size: 14px;">View in Archive</a>'
            "</td></tr>"
        )

    unsubscribe_url = f"{_main_mod.SITE_URL}/notifications"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin: 0; padding: 0; background-color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color: #0f172a; padding: 20px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width: 600px; width: 100%; background-color: #1e293b; border-radius: 8px; overflow: hidden;">
<tr><td style="background-color: #1e293b; padding: 24px 30px; border-bottom: 1px solid #334155;">
<span style="font-size: 20px; font-weight: 700; color: #f8fafc; letter-spacing: -0.02em;">Rhodesli</span>
<span style="font-size: 12px; color: #94a3b8; margin-left: 8px;">Heritage Photo Archive</span>
</td></tr>
<tr><td style="padding: 30px;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td style="font-size: 18px; font-weight: 600; color: #f1f5f9; padding-bottom: 12px;">{title}</td></tr>
<tr><td style="font-size: 14px; color: #cbd5e1; line-height: 1.6;">{body}</td></tr>
{button_html}
</table>
</td></tr>
<tr><td style="padding: 20px 30px; border-top: 1px solid #334155; text-align: center;">
<span style="font-size: 12px; color: #64748b;">
<a href="{unsubscribe_url}" style="color: #64748b; text-decoration: underline;">Manage notification preferences</a>
</span>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


async def send_notification_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via Resend API. Returns True on success, False otherwise.

    Silently skips if RESEND_API_KEY is not configured.
    """
    if not RESEND_API_KEY:
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": "Rhodesli <noreply@rhodesli.nolanandrewfox.com>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                },
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                logger.info(f"Notification email sent to {to_email}: {subject}")
                return True
            else:
                logger.warning(f"Resend API returned {resp.status_code}: {resp.text[:200]}")
                return False
    except Exception:
        logger.warning(f"Failed to send notification email to {to_email}", exc_info=True)
        return False


def _fire_notification_email(
    to_email: str,
    title: str,
    body: str,
    link_url: str | None = None,
) -> None:
    """Fire-and-forget email notification in a background thread.

    Does NOT block the calling thread. Errors are logged but swallowed.
    """
    if not RESEND_API_KEY:
        return

    import asyncio
    import threading

    html_body = _build_notification_email_html(title, body, link_url)
    subject = title

    def _send():
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(send_notification_email(to_email, subject, html_body))
            loop.close()
        except Exception:
            logger.warning("Background email send failed", exc_info=True)

    t = threading.Thread(target=_send, daemon=True)
    t.start()


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
    email: str | None = None,
) -> dict | None:
    """Create a notification in Supabase. Returns the created row or None.

    If ``email`` is provided and RESEND_API_KEY is set, also sends an email
    notification in a background thread.
    """
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
        created = result.data[0] if result.data else None

        # Fire email notification if email address is provided
        if created and email:
            link_url = None
            if identity_id:
                link_url = f"/person/{identity_id}"
            elif photo_id:
                link_url = f"/photo/{photo_id}"
            _fire_notification_email(
                to_email=email,
                title=title,
                body=body or "",
                link_url=link_url,
            )

        return created
    except _SUPABASE_ERRORS:
        logger.warning("Failed to create notification")
        return None


def create_identity_confirmed_notification(
    identity_id: str,
    identity_name: str,
    photo_ids: list[str] | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
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
        user_email: Email address for email notification delivery.

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
        email=user_email,
    )


def create_discovery_notification(
    identity_id: str,
    identity_name: str,
    match_name: str | None = None,
    confidence_label: str | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
) -> dict | None:
    """Create a notification when a potential match is discovered.

    Args:
        identity_id: UUID of the identity with a potential match
        identity_name: Display name of the identity
        match_name: Name of the potential match (if available)
        confidence_label: Confidence tier label (e.g., "Strong", "Possible")
        user_id: Supabase auth user ID to notify.
        user_email: Email for Resend delivery.

    Returns:
        The created notification row, or None if Supabase is unavailable.
    """
    target_user_id = user_id or "00000000-0000-0000-0000-000000000000"
    match_detail = f' for "{match_name}"' if match_name else ""
    conf_detail = f" ({confidence_label} match)" if confidence_label else ""
    return _create_notification(
        user_id=target_user_id,
        notification_type="discovery",
        title=f"Potential Match Found{match_detail}",
        body=f'A potential match was found for "{identity_name}"{conf_detail}. Review it in the archive.',
        identity_id=identity_id,
        email=user_email,
    )


def create_annotation_approved_notification(
    identity_id: str,
    identity_name: str,
    annotator_name: str | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
) -> dict | None:
    """Create a notification when an annotation/suggestion is approved.

    Args:
        identity_id: UUID of the identity that was annotated
        identity_name: Display name of the identity
        annotator_name: Name of the person who made the annotation
        user_id: Supabase auth user ID to notify (the annotator).
        user_email: Email for Resend delivery.

    Returns:
        The created notification row, or None if Supabase is unavailable.
    """
    target_user_id = user_id or "00000000-0000-0000-0000-000000000000"
    by_detail = f" (suggested by {annotator_name})" if annotator_name else ""
    return _create_notification(
        user_id=target_user_id,
        notification_type="annotation_approved",
        title=f"Your suggestion was approved: {identity_name}",
        body=f'The identification of "{identity_name}"{by_detail} has been approved by an admin.',
        identity_id=identity_id,
        email=user_email,
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
    "discovery": (
        '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-amber-400" fill="none" '
        'viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
        '<path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 '
        '11-14 0 7 7 0 0114 0z"/></svg>'
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


def _notification_item(notif: dict, nav_prefix: str = "") -> object:
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
        link_href = f"{nav_prefix}/person/{identity_id}"
    elif photo_id:
        link_href = f"{nav_prefix}/photo/{photo_id}"

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


def _notifications_list(
    notifications: list[dict], offset: int = 0, page_size: int = 20, nav_prefix: str = ""
) -> object:
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

    items = [_notification_item(n, nav_prefix=nav_prefix) for n in notifications]

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
def get(sess, offset: int = 0, partial: int = 0, request=None):
    """GET /notifications — Full notifications page or partial list for pagination."""
    denied = _check_login(sess)
    if denied:
        return denied

    user = get_current_user(sess or {})
    page_size = 20
    notifications = _get_notifications(user.id, limit=page_size, offset=offset)

    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    # Partial response for HTMX pagination
    if partial:
        items = [_notification_item(n, nav_prefix=nav_prefix) for n in notifications]
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
    nav_links = _main_mod._public_nav_links(active="notifications", user=user, community_slug=community_slug)
    nav = _main_mod._public_page_nav(nav_links, active="notifications", user=user, community_slug=community_slug)

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
        _notifications_list(notifications, offset=offset, page_size=page_size, nav_prefix=nav_prefix),
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
def post(sess, notification_id: str, request=None):
    """POST /api/notifications/{id}/read — Mark a single notification as read."""
    denied = _check_login(sess)
    if denied:
        return denied

    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    user = get_current_user(sess or {})
    _mark_read(notification_id, user.id)

    # Re-fetch the notification to render the updated item
    sb = get_supabase_client()
    if sb:
        try:
            result = sb.table("notifications").select("*").eq("id", notification_id).execute()
            if result.data:
                return _notification_item(result.data[0], nav_prefix=nav_prefix)
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
def get(sess, target: str = ""):
    """GET /api/notifications/count — Returns unread count for bell icon polling."""
    denied = _check_login(sess)
    if denied:
        return denied

    user = get_current_user(sess or {})
    count = _get_unread_count(user.id)

    # Sidebar variant: inline badge for sidebar nav item
    if target == "sidebar":
        if count > 0:
            return Span(
                str(count),
                cls="px-2 py-0.5 text-xs font-bold rounded-full bg-red-500 text-white",
                id="notification-badge-sidebar",
            )
        return Span(id="notification-badge-sidebar", cls="hidden")

    # Default: absolute-positioned badge for top nav bell icon
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
