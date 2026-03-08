"""Tests for PRD-028: Contributor Notifications P0.

Tests notification CRUD, bell icon rendering, pagination, mark-all-read,
and admin create endpoint.
"""

import uuid
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fasthtml.common import to_xml
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ADMIN_SESSION = {"auth": {"id": "admin-user-id-1234", "email": "NolanFox@gmail.com"}}
USER_SESSION = {"auth": {"id": "user-id-5678", "email": "contributor@example.com"}}
ANON_SESSION = {}


def _make_notification(
    *,
    notif_id=None,
    user_id="user-id-5678",
    notification_type="identity_confirmed",
    title="Test Notification",
    body="This is a test notification",
    is_read=False,
    photo_id=None,
    identity_id=None,
    created_at=None,
):
    return {
        "id": notif_id or str(uuid.uuid4()),
        "user_id": user_id,
        "notification_type": notification_type,
        "title": title,
        "body": body,
        "is_read": is_read,
        "photo_id": photo_id,
        "identity_id": identity_id,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for notification tests."""
    mock_client = MagicMock()
    with patch(
        "app.notification_routes.get_supabase_client",
        return_value=mock_client,
    ):
        yield mock_client


@pytest.fixture
def client():
    """Get a test client for the app."""
    from app.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Helper: render FastHTML to HTML string
# ---------------------------------------------------------------------------


def _to_html(element) -> str:
    """Convert a FastHTML element to an HTML string."""
    if hasattr(element, "__ft__"):
        element = element.__ft__()
    return to_xml(element) if not isinstance(element, str) else element


# ---------------------------------------------------------------------------
# Unit Tests: Notification helpers
# ---------------------------------------------------------------------------


class TestNotificationHelpers:
    """Test notification CRUD helper functions."""

    def test_get_notifications_returns_list(self, mock_supabase):
        """_get_notifications returns list of notification dicts."""
        from app.notification_routes import _get_notifications

        notifications = [_make_notification(), _make_notification()]
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = notifications

        result = _get_notifications("user-id-5678", limit=20, offset=0)
        assert len(result) == 2
        assert result[0]["title"] == "Test Notification"

    def test_get_notifications_no_supabase(self):
        """_get_notifications returns empty list when Supabase unavailable."""
        from app.notification_routes import _get_notifications

        with patch("app.notification_routes.get_supabase_client", return_value=None):
            result = _get_notifications("user-id-5678")
            assert result == []

    def test_get_unread_count(self, mock_supabase):
        """_get_unread_count returns integer count."""
        from app.notification_routes import _get_unread_count

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.count = 5

        result = _get_unread_count("user-id-5678")
        assert result == 5

    def test_get_unread_count_no_supabase(self):
        """_get_unread_count returns 0 when Supabase unavailable."""
        from app.notification_routes import _get_unread_count

        with patch("app.notification_routes.get_supabase_client", return_value=None):
            result = _get_unread_count("user-id-5678")
            assert result == 0

    def test_mark_read_success(self, mock_supabase):
        """_mark_read returns True on success."""
        from app.notification_routes import _mark_read

        result = _mark_read("notif-id-1", "user-id-5678")
        assert result is True

    def test_mark_read_no_supabase(self):
        """_mark_read returns False when Supabase unavailable."""
        from app.notification_routes import _mark_read

        with patch("app.notification_routes.get_supabase_client", return_value=None):
            result = _mark_read("notif-id-1", "user-id-5678")
            assert result is False

    def test_mark_all_read_success(self, mock_supabase):
        """_mark_all_read returns True on success."""
        from app.notification_routes import _mark_all_read

        result = _mark_all_read("user-id-5678")
        assert result is True

    def test_mark_all_read_no_supabase(self):
        """_mark_all_read returns False when Supabase unavailable."""
        from app.notification_routes import _mark_all_read

        with patch("app.notification_routes.get_supabase_client", return_value=None):
            result = _mark_all_read("user-id-5678")
            assert result is False

    def test_create_notification_success(self, mock_supabase):
        """_create_notification returns created row on success."""
        from app.notification_routes import _create_notification

        created = _make_notification()
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [created]

        result = _create_notification(
            user_id="user-id-5678",
            notification_type="identity_confirmed",
            title="Test",
            body="Body",
        )
        assert result is not None
        assert result["title"] == "Test Notification"

    def test_create_notification_no_supabase(self):
        """_create_notification returns None when Supabase unavailable."""
        from app.notification_routes import _create_notification

        with patch("app.notification_routes.get_supabase_client", return_value=None):
            result = _create_notification(
                user_id="user-id-5678",
                notification_type="test",
                title="Test",
            )
            assert result is None

    def test_create_identity_confirmed_notification(self, mock_supabase):
        """create_identity_confirmed_notification creates the right notification."""
        from app.notification_routes import create_identity_confirmed_notification

        created = _make_notification(
            notification_type="identity_confirmed",
            title="Identity Confirmed: Leon Capeluto",
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [created]

        result = create_identity_confirmed_notification(
            identity_id="id-123",
            identity_name="Leon Capeluto",
            photo_ids=["photo-1"],
        )
        assert result is not None

        # Verify insert was called with correct data
        insert_call = mock_supabase.table.return_value.insert.call_args
        row = insert_call[0][0]
        assert row["notification_type"] == "identity_confirmed"
        assert "Leon Capeluto" in row["title"]


# ---------------------------------------------------------------------------
# Unit Tests: UI Components
# ---------------------------------------------------------------------------


class TestNotificationUI:
    """Test notification UI rendering."""

    def test_notification_item_unread(self):
        """Unread notification has amber border and mark-read action."""
        from app.notification_routes import _notification_item

        notif = _make_notification(notif_id="abc123", is_read=False)
        html = _to_html(_notification_item(notif))
        assert "border-amber-500" in html
        assert "hx-post" in html
        assert "/api/notifications/abc123/read" in html

    def test_notification_item_read(self):
        """Read notification has no mark-read action."""
        from app.notification_routes import _notification_item

        notif = _make_notification(notif_id="abc123", is_read=True)
        html = _to_html(_notification_item(notif))
        assert "border-amber-500" not in html
        # Read notifications don't have hx-post for mark-read
        assert "/api/notifications/abc123/read" not in html

    def test_notification_item_with_identity_link(self):
        """Notification with identity_id links to person page."""
        from app.notification_routes import _notification_item

        notif = _make_notification(identity_id="person-uuid-123")
        html = _to_html(_notification_item(notif))
        assert "/person/person-uuid-123" in html

    def test_notification_item_with_photo_link(self):
        """Notification with photo_id links to photo page."""
        from app.notification_routes import _notification_item

        notif = _make_notification(photo_id="photo-abc")
        html = _to_html(_notification_item(notif))
        assert "/photo/photo-abc" in html

    def test_notifications_list_empty(self):
        """Empty notification list shows helpful message."""
        from app.notification_routes import _notifications_list

        html = _to_html(_notifications_list([]))
        assert "No notifications yet" in html
        assert "notified when identities" in html

    def test_notifications_list_with_items(self):
        """Notification list renders items."""
        from app.notification_routes import _notifications_list

        notifications = [_make_notification(notif_id=f"n{i}") for i in range(3)]
        html = _to_html(_notifications_list(notifications))
        assert "notifications-list" in html
        assert "Test Notification" in html

    def test_notifications_list_pagination(self):
        """Full page shows load-more button."""
        from app.notification_routes import _notifications_list

        # 20 items = full page
        notifications = [_make_notification(notif_id=f"n{i}") for i in range(20)]
        html = _to_html(_notifications_list(notifications, offset=0, page_size=20))
        assert "Load more" in html
        assert "offset=20" in html

    def test_notifications_list_no_pagination(self):
        """Partial page has no load-more button."""
        from app.notification_routes import _notifications_list

        # 5 items < 20 page size
        notifications = [_make_notification(notif_id=f"n{i}") for i in range(5)]
        html = _to_html(_notifications_list(notifications, offset=0, page_size=20))
        assert "Load more" not in html

    def test_time_ago_just_now(self):
        """Recent timestamp shows 'just now'."""
        from app.notification_routes import _time_ago

        now = datetime.now(timezone.utc).isoformat()
        assert _time_ago(now) == "just now"

    def test_time_ago_invalid(self):
        """Invalid timestamp returns empty string."""
        from app.notification_routes import _time_ago

        assert _time_ago("not-a-date") == ""
        assert _time_ago("") == ""

    def test_notification_icon_known_type(self):
        """Known notification types have specific icons."""
        from app.notification_routes import _notification_icon

        icon = _notification_icon("identity_confirmed")
        assert "emerald" in icon

    def test_notification_icon_unknown_type(self):
        """Unknown notification types get default bell icon."""
        from app.notification_routes import _notification_icon

        icon = _notification_icon("unknown_type")
        assert "slate" in icon


# ---------------------------------------------------------------------------
# Route Tests
# ---------------------------------------------------------------------------


class TestNotificationRoutes:
    """Test notification route endpoints."""

    def test_notifications_page_requires_login(self, client):
        """GET /notifications returns 401 for anonymous users."""
        with patch("app.notification_routes.is_auth_enabled", return_value=True):
            with patch("app.notification_routes.get_current_user", return_value=None):
                resp = client.get("/notifications")
                assert resp.status_code == 401

    def test_notifications_count_requires_login(self, client):
        """GET /api/notifications/count returns 401 for anonymous users."""
        with patch("app.notification_routes.is_auth_enabled", return_value=True):
            with patch("app.notification_routes.get_current_user", return_value=None):
                resp = client.get("/api/notifications/count")
                assert resp.status_code == 401

    def test_mark_read_requires_login(self, client):
        """POST /api/notifications/{id}/read returns 401 for anonymous users."""
        with patch("app.notification_routes.is_auth_enabled", return_value=True):
            with patch("app.notification_routes.get_current_user", return_value=None):
                resp = client.post("/api/notifications/test-id/read")
                assert resp.status_code == 401

    def test_mark_all_read_requires_login(self, client):
        """POST /api/notifications/mark-all-read returns 401 for anonymous users."""
        with patch("app.notification_routes.is_auth_enabled", return_value=True):
            with patch("app.notification_routes.get_current_user", return_value=None):
                resp = client.post("/api/notifications/mark-all-read")
                assert resp.status_code == 401

    def test_admin_create_requires_admin(self, client):
        """POST /api/notifications/create returns 403 for non-admin users."""
        from app.auth import User

        user = User(id="user-id", email="contributor@example.com", is_admin=False, role="viewer")
        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.is_auth_enabled", return_value=True))
            stack.enter_context(patch("app.notification_routes.get_current_user", return_value=user))
            resp = client.post(
                "/api/notifications/create",
                data={"user_id": "x", "title": "test"},
            )
            assert resp.status_code == 403

    def test_admin_create_missing_fields(self, client):
        """POST /api/notifications/create returns 400 if user_id or title missing."""
        from app.auth import User

        admin = User(id="admin-id", email="NolanFox@gmail.com", is_admin=True, role="admin")
        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.is_auth_enabled", return_value=True))
            stack.enter_context(patch("app.notification_routes.get_current_user", return_value=admin))
            # Missing title
            resp = client.post(
                "/api/notifications/create",
                data={"user_id": "x"},
            )
            assert resp.status_code == 400

    def test_admin_create_success(self, client, mock_supabase):
        """POST /api/notifications/create returns 201 on success."""
        from app.auth import User

        admin = User(id="admin-id", email="NolanFox@gmail.com", is_admin=True, role="admin")
        created = _make_notification(title="Admin test")
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [created]

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.is_auth_enabled", return_value=True))
            stack.enter_context(patch("app.notification_routes.get_current_user", return_value=admin))
            resp = client.post(
                "/api/notifications/create",
                data={
                    "user_id": "user-id-5678",
                    "notification_type": "default",
                    "title": "Test notification",
                    "body": "Test body",
                },
            )
            assert resp.status_code == 201

    def test_notifications_count_returns_badge(self, client, mock_supabase):
        """GET /api/notifications/count returns badge with count."""
        from app.auth import User

        user = User(
            id="user-id-5678",
            email="contributor@example.com",
            is_admin=False,
            role="viewer",
        )
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.count = 3

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.is_auth_enabled", return_value=True))
            stack.enter_context(patch("app.notification_routes.get_current_user", return_value=user))
            resp = client.get("/api/notifications/count")
            assert resp.status_code == 200
            assert "3" in resp.text
            assert "bg-red-500" in resp.text

    def test_notifications_count_zero_hidden(self, client, mock_supabase):
        """GET /api/notifications/count returns hidden badge when count is 0."""
        from app.auth import User

        user = User(
            id="user-id-5678",
            email="contributor@example.com",
            is_admin=False,
            role="viewer",
        )
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.count = 0

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.is_auth_enabled", return_value=True))
            stack.enter_context(patch("app.notification_routes.get_current_user", return_value=user))
            resp = client.get("/api/notifications/count")
            assert resp.status_code == 200
            assert "hidden" in resp.text


# ---------------------------------------------------------------------------
# Bell Icon Tests
# ---------------------------------------------------------------------------


class TestBellIcon:
    """Test bell icon rendering in the nav bar."""

    def test_bell_icon_visible_for_logged_in_user(self):
        """Bell icon appears in nav links for logged-in users."""
        from app.auth import User
        from app.main import _public_nav_links

        user = User(id="user-1", email="test@example.com", is_admin=False, role="viewer")
        links = _public_nav_links(active="photos", user=user)
        html = "".join(_to_html(link) for link in links)
        assert "/notifications" in html
        assert "notification-badge" in html

    def test_bell_icon_hidden_for_anonymous(self):
        """Bell icon does not appear for anonymous users."""
        from app.main import _public_nav_links

        links = _public_nav_links(active="photos", user=None)
        html = "".join(_to_html(link) for link in links)
        assert "notification-badge" not in html

    def test_bell_icon_has_polling(self):
        """Bell icon polls for unread count every 30s."""
        from app.auth import User
        from app.main import _public_nav_links

        user = User(id="user-1", email="test@example.com", is_admin=False, role="viewer")
        links = _public_nav_links(active="photos", user=user)
        html = "".join(_to_html(link) for link in links)
        assert "every 30s" in html
        assert "/api/notifications/count" in html

    def test_bell_icon_admin_also_sees_it(self):
        """Admin users also see the bell icon."""
        from app.auth import User
        from app.main import _public_nav_links

        admin = User(id="admin-1", email="NolanFox@gmail.com", is_admin=True, role="admin")
        links = _public_nav_links(active="photos", user=admin)
        html = "".join(_to_html(link) for link in links)
        assert "/notifications" in html


# ---------------------------------------------------------------------------
# Tests: Notification trigger wiring (save_registry integration)
# ---------------------------------------------------------------------------


class TestNotificationTriggers:
    """Test that confirm routes fire notifications via save_registry."""

    def test_save_registry_without_notification_info_works(self):
        """Backward compatibility: save_registry(registry) with no notification info."""
        from unittest.mock import MagicMock

        from app.main import save_registry

        mock_registry = MagicMock()
        mock_registry._identities = {}
        mock_registry.save = MagicMock()

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.DATA_SOURCE", "json"))
            stack.enter_context(
                patch("app.supabase_data.sync_identity_overrides", side_effect=Exception("no supabase"))
            )
            save_registry(mock_registry)

        # Should have called save without error
        mock_registry.save.assert_called_once()

    def test_save_registry_with_confirmed_identity_fires_notification(self):
        """save_registry with confirmed_identity_info fires notification in background."""
        import threading
        from unittest.mock import MagicMock

        from app.main import save_registry

        mock_registry = MagicMock()
        mock_registry._identities = {}
        mock_registry.save = MagicMock()
        mock_registry.get_identity.return_value = {"anchor_ids": ["f1"], "candidate_ids": []}

        mock_photo_reg = MagicMock()
        mock_photo_reg.face_to_photo = {"f1": "photo-1"}

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.DATA_SOURCE", "json"))
            stack.enter_context(
                patch("app.supabase_data.sync_identity_overrides", side_effect=Exception("no supabase"))
            )
            mock_create = stack.enter_context(
                patch("app.notification_routes.create_identity_confirmed_notification", return_value=None)
            )
            stack.enter_context(patch("app.main.load_photo_registry", return_value=mock_photo_reg))

            save_registry(
                mock_registry,
                confirmed_identity_info={
                    "identity_id": "id-123",
                    "identity_name": "Leon Capeluto",
                    "user_id": "admin-user-id",
                },
            )

            # Wait for background thread to complete
            for t in threading.enumerate():
                if t.name != "MainThread" and t.daemon:
                    t.join(timeout=2.0)

            mock_create.assert_called_once_with(
                identity_id="id-123",
                identity_name="Leon Capeluto",
                photo_ids=["photo-1"],
                user_id="admin-user-id",
                user_email=None,
            )

    def test_save_registry_notification_failure_does_not_block_save(self):
        """Notification failure must not prevent save from completing."""
        import threading
        from unittest.mock import MagicMock

        from app.main import save_registry

        mock_registry = MagicMock()
        mock_registry._identities = {}
        mock_registry.save = MagicMock()
        mock_registry.get_identity.side_effect = Exception("boom")

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.DATA_SOURCE", "json"))
            stack.enter_context(
                patch("app.supabase_data.sync_identity_overrides", side_effect=Exception("no supabase"))
            )
            stack.enter_context(
                patch(
                    "app.notification_routes.create_identity_confirmed_notification",
                    side_effect=Exception("notification failed"),
                )
            )

            # Should NOT raise — notification errors are swallowed
            save_registry(
                mock_registry,
                confirmed_identity_info={
                    "identity_id": "id-123",
                    "identity_name": "Test",
                    "user_id": None,
                },
            )

            # Wait for background threads
            for t in threading.enumerate():
                if t.name != "MainThread" and t.daemon:
                    t.join(timeout=2.0)

        mock_registry.save.assert_called_once()

    def test_create_identity_confirmed_notification_uses_provided_user_id(self, mock_supabase):
        """create_identity_confirmed_notification passes through user_id."""
        from app.notification_routes import create_identity_confirmed_notification

        created = _make_notification(notification_type="identity_confirmed")
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [created]

        create_identity_confirmed_notification(
            identity_id="id-456",
            identity_name="Nace Capeluto",
            photo_ids=["p1"],
            user_id="real-admin-uuid",
        )

        insert_call = mock_supabase.table.return_value.insert.call_args
        row = insert_call[0][0]
        assert row["user_id"] == "real-admin-uuid"
        assert row["notification_type"] == "identity_confirmed"
        assert "Nace Capeluto" in row["title"]

    def test_create_identity_confirmed_notification_falls_back_to_placeholder(self, mock_supabase):
        """Without user_id, falls back to placeholder UUID."""
        from app.notification_routes import create_identity_confirmed_notification

        created = _make_notification()
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [created]

        create_identity_confirmed_notification(
            identity_id="id-789",
            identity_name="Test Person",
        )

        insert_call = mock_supabase.table.return_value.insert.call_args
        row = insert_call[0][0]
        assert row["user_id"] == "00000000-0000-0000-0000-000000000000"

    def test_confirm_route_passes_notification_info(self, client):
        """POST /confirm/{id} passes confirmed_identity_info to save_registry."""
        from unittest.mock import MagicMock

        from app.auth import User

        admin = User(id="admin-uuid-1", email="NolanFox@gmail.com", is_admin=True, role="admin")
        mock_registry = MagicMock()
        identity_data = {
            "identity_id": "test-id",
            "name": "Betty Capeluto",
            "state": "PROPOSED",
            "anchor_ids": [],
            "candidate_ids": [],
        }
        mock_registry.get_identity.return_value = identity_data
        mock_registry._identities = {"test-id": identity_data}

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.is_auth_enabled", return_value=True))
            stack.enter_context(patch("app.main.get_current_user", return_value=admin))
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=mock_registry))
            stack.enter_context(patch("app.main._check_merged_identity", return_value=(False, None)))
            mock_save = stack.enter_context(patch("app.main.save_registry"))
            stack.enter_context(patch("app.main._fire_recalibration_hook"))

            resp = client.post("/confirm/test-id")

        # Verify save_registry was called with confirmed_identity_info
        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args
        notify_info = call_kwargs[1].get("confirmed_identity_info") or (
            call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
        )
        assert notify_info is not None
        assert notify_info["identity_id"] == "test-id"
        assert notify_info["identity_name"] == "Betty Capeluto"
        assert notify_info["user_id"] == "admin-uuid-1"

    def test_reject_action_does_not_create_notification(self, client):
        """POST /api/face/quick-action with action=reject does NOT fire notification."""
        from unittest.mock import MagicMock

        from app.auth import User

        admin = User(id="admin-uuid-1", email="NolanFox@gmail.com", is_admin=True, role="admin")
        mock_registry = MagicMock()
        identity_data = {
            "identity_id": "rej-id",
            "name": "Unknown Person",
            "state": "PROPOSED",
            "anchor_ids": [],
            "candidate_ids": [],
        }
        mock_registry.get_identity.return_value = identity_data
        mock_registry._identities = {"rej-id": identity_data}

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.is_auth_enabled", return_value=True))
            stack.enter_context(patch("app.main.get_current_user", return_value=admin))
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=mock_registry))
            mock_save = stack.enter_context(patch("app.main.save_registry"))
            stack.enter_context(patch("app.main.photo_view_content", return_value=(MagicMock(),)))

            resp = client.post(
                "/api/face/quick-action",
                data={"identity_id": "rej-id", "action": "reject", "photo_id": "photo-1"},
            )

        mock_save.assert_called_once()
        call_kwargs = mock_save.call_args
        notify_info = call_kwargs[1].get("confirmed_identity_info") if call_kwargs[1] else None
        assert notify_info is None
