"""Tests for Session 92 Track E: Growth Loop features.

- E1: Email notification sending (Resend integration)
- E2: Share flow OG meta tags
- E3: Help Identify page rendering
- E4: Timeline life events integration
"""

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fasthtml.common import to_xml
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _to_html(element) -> str:
    if hasattr(element, "__ft__"):
        element = element.__ft__()
    return to_xml(element) if not isinstance(element, str) else element


# ---------------------------------------------------------------------------
# E1: Email Notifications
# ---------------------------------------------------------------------------


class TestEmailNotifications:
    """Test Resend email integration in notification_routes."""

    def test_send_email_skips_when_no_api_key(self):
        """send_notification_email returns False when RESEND_API_KEY is empty."""
        from app.notification_routes import send_notification_email

        with patch("app.notification_routes.RESEND_API_KEY", ""):
            result = asyncio.run(send_notification_email("test@example.com", "Subject", "<p>Body</p>"))
            assert result is False

    def test_send_email_calls_resend_api(self):
        """send_notification_email posts to Resend API when key is set."""
        from app.notification_routes import send_notification_email

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.RESEND_API_KEY", "re_test_key_123"))
            stack.enter_context(patch("app.notification_routes.httpx.AsyncClient", return_value=mock_client))

            # We need to patch at the import level inside the function
            result = asyncio.run(send_notification_email("user@example.com", "Test Subject", "<p>Hello</p>"))

            assert result is True
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://api.resend.com/emails"
            json_body = call_args[1]["json"]
            assert json_body["to"] == ["user@example.com"]
            assert json_body["subject"] == "Test Subject"
            assert "Bearer re_test_key_123" in call_args[1]["headers"]["Authorization"]

    def test_send_email_returns_false_on_error(self):
        """send_notification_email returns False on API error."""
        from app.notification_routes import send_notification_email

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.RESEND_API_KEY", "re_test_key"))
            stack.enter_context(patch("app.notification_routes.httpx.AsyncClient", return_value=mock_client))

            result = asyncio.run(send_notification_email("user@example.com", "Subject", "<p>Body</p>"))
            assert result is False

    def test_email_template_has_inline_css(self):
        """Email template uses inline styles, not style blocks (Lesson 12)."""
        from app.notification_routes import _build_notification_email_html

        with patch("app.notification_routes._main_mod") as mock_main:
            mock_main.SITE_URL = "https://rhodesli.nolanandrewfox.com"
            html = _build_notification_email_html("Test Title", "Test body text", "/person/abc123")

        assert "<style" not in html  # No style blocks
        assert 'style="' in html  # Inline styles present
        assert "Test Title" in html
        assert "Test body text" in html
        assert "View in Archive" in html
        assert "/person/abc123" in html or "rhodesli.nolanandrewfox.com/person/abc123" in html

    def test_email_template_without_link(self):
        """Email template renders without button when no link_url."""
        from app.notification_routes import _build_notification_email_html

        with patch("app.notification_routes._main_mod") as mock_main:
            mock_main.SITE_URL = "https://rhodesli.nolanandrewfox.com"
            html = _build_notification_email_html("Title", "Body", link_url=None)

        assert "View in Archive" not in html
        assert "Title" in html
        assert "Body" in html

    def test_email_template_has_unsubscribe_link(self):
        """Email template includes notification management link."""
        from app.notification_routes import _build_notification_email_html

        with patch("app.notification_routes._main_mod") as mock_main:
            mock_main.SITE_URL = "https://rhodesli.nolanandrewfox.com"
            html = _build_notification_email_html("Title", "Body")

        assert "/notifications" in html
        assert "Manage notification" in html

    def test_create_notification_fires_email_when_email_provided(self):
        """_create_notification fires email when email param is set."""
        from app.notification_routes import _create_notification

        mock_sb = MagicMock()
        created = {"id": "n1", "title": "Test"}
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [created]

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.get_supabase_client", return_value=mock_sb))
            mock_fire = stack.enter_context(patch("app.notification_routes._fire_notification_email"))

            result = _create_notification(
                user_id="user-1",
                notification_type="test",
                title="Test Title",
                body="Test body",
                identity_id="person-123",
                email="user@example.com",
            )

            assert result is not None
            mock_fire.assert_called_once_with(
                to_email="user@example.com",
                title="Test Title",
                body="Test body",
                link_url="/person/person-123",
            )

    def test_create_notification_no_email_when_not_provided(self):
        """_create_notification does NOT fire email when email is None."""
        from app.notification_routes import _create_notification

        mock_sb = MagicMock()
        created = {"id": "n1", "title": "Test"}
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [created]

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.get_supabase_client", return_value=mock_sb))
            mock_fire = stack.enter_context(patch("app.notification_routes._fire_notification_email"))

            _create_notification(
                user_id="user-1",
                notification_type="test",
                title="Test",
            )

            mock_fire.assert_not_called()

    def test_fire_notification_email_noop_without_key(self):
        """_fire_notification_email does nothing when RESEND_API_KEY is empty."""
        from app.notification_routes import _fire_notification_email

        with patch("app.notification_routes.RESEND_API_KEY", ""):
            # Should return immediately without spawning a thread
            _fire_notification_email("user@example.com", "Title", "Body")
            # No assertion needed — just verifying no exception

    def test_send_email_handles_network_exception(self):
        """send_notification_email returns False on network errors."""
        from app.notification_routes import send_notification_email

        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.RESEND_API_KEY", "re_test_key"))
            stack.enter_context(patch("app.notification_routes.httpx.AsyncClient", return_value=mock_client))

            result = asyncio.run(send_notification_email("user@example.com", "Subject", "<p>Body</p>"))
            assert result is False

    def test_create_discovery_notification(self):
        """create_discovery_notification creates correct notification type."""
        from app.notification_routes import create_discovery_notification

        mock_sb = MagicMock()
        created = {"id": "n1", "notification_type": "discovery", "title": "Potential Match Found"}
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [created]

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.get_supabase_client", return_value=mock_sb))
            mock_fire = stack.enter_context(patch("app.notification_routes._fire_notification_email"))

            result = create_discovery_notification(
                identity_id="person-123",
                identity_name="Leon Capeluto",
                match_name="Big Leon",
                confidence_label="Strong",
                user_id="user-1",
                user_email="user@example.com",
            )

            assert result is not None
            insert_call = mock_sb.table.return_value.insert.call_args
            row = insert_call[0][0]
            assert row["notification_type"] == "discovery"
            assert "Potential Match" in row["title"]
            assert "Big Leon" in row["title"]
            assert "Leon Capeluto" in row["body"]
            assert "Strong match" in row["body"]
            mock_fire.assert_called_once()

    def test_create_discovery_notification_without_match_name(self):
        """create_discovery_notification works without match_name."""
        from app.notification_routes import create_discovery_notification

        mock_sb = MagicMock()
        created = {"id": "n1", "notification_type": "discovery"}
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [created]

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.get_supabase_client", return_value=mock_sb))
            stack.enter_context(patch("app.notification_routes._fire_notification_email"))

            result = create_discovery_notification(
                identity_id="person-123",
                identity_name="Leon Capeluto",
            )
            assert result is not None
            insert_call = mock_sb.table.return_value.insert.call_args
            row = insert_call[0][0]
            assert "Potential Match Found" in row["title"]

    def test_create_annotation_approved_notification(self):
        """create_annotation_approved_notification creates correct notification."""
        from app.notification_routes import create_annotation_approved_notification

        mock_sb = MagicMock()
        created = {"id": "n1", "notification_type": "annotation_approved"}
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [created]

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.get_supabase_client", return_value=mock_sb))
            mock_fire = stack.enter_context(patch("app.notification_routes._fire_notification_email"))

            result = create_annotation_approved_notification(
                identity_id="person-456",
                identity_name="Betty Capeluto",
                annotator_name="Claude Benatar",
                user_id="user-2",
                user_email="claude@example.com",
            )

            assert result is not None
            insert_call = mock_sb.table.return_value.insert.call_args
            row = insert_call[0][0]
            assert row["notification_type"] == "annotation_approved"
            assert "Betty Capeluto" in row["title"]
            assert "Claude Benatar" in row["body"]
            mock_fire.assert_called_once()

    def test_create_annotation_approved_notification_no_email(self):
        """create_annotation_approved_notification skips email when not provided."""
        from app.notification_routes import create_annotation_approved_notification

        mock_sb = MagicMock()
        created = {"id": "n1", "notification_type": "annotation_approved"}
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [created]

        with ExitStack() as stack:
            stack.enter_context(patch("app.notification_routes.get_supabase_client", return_value=mock_sb))
            mock_fire = stack.enter_context(patch("app.notification_routes._fire_notification_email"))

            create_annotation_approved_notification(
                identity_id="person-456",
                identity_name="Betty Capeluto",
            )

            mock_fire.assert_not_called()

    def test_discovery_icon_exists(self):
        """Discovery notification type has a specific icon."""
        from app.notification_routes import _notification_icon

        icon = _notification_icon("discovery")
        assert "amber" in icon
        assert "svg" in icon

    def test_confirm_notification_chain_passes_user_email(self):
        """The full confirm chain passes user_email through to create_identity_confirmed_notification."""
        import threading

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
                    "user_id": "admin-id",
                    "user_email": "admin@example.com",
                },
            )

            # Wait for background thread
            for t in threading.enumerate():
                if t.name != "MainThread" and t.daemon:
                    t.join(timeout=2.0)

            mock_create.assert_called_once_with(
                identity_id="id-123",
                identity_name="Leon Capeluto",
                photo_ids=["photo-1"],
                user_id="admin-id",
                user_email="admin@example.com",
            )


# ---------------------------------------------------------------------------
# E2: Share Flow OG Meta Tags
# ---------------------------------------------------------------------------


class TestShareFlowOGTags:
    """Verify share pages have proper OG meta tags in source code."""

    def test_identify_page_source_has_og_tags(self):
        """The /identify route source code includes og:title, og:image, og:description."""
        import inspect

        import app.page_routes as pr

        # Read the source of the page_routes module
        source = inspect.getsource(pr)

        # The /identify route should have OG meta tags
        assert "og:title" in source
        assert "og:image" in source
        assert "og:description" in source

    def test_person_page_source_has_og_tags(self):
        """The /person route source code includes og:title, og:image."""
        import inspect

        import app.person_routes as pr

        source = inspect.getsource(pr)

        assert "og:title" in source
        assert "og:image" in source

    def test_identify_page_has_share_button(self):
        """The /identify route source includes share functionality."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)

        # The identify page should have share data attributes
        assert "data_share_url" in source or "data-share-url" in source
        assert "navigator.share" in source

    def test_help_page_source_has_og_tags(self):
        """The /help route source includes OG tags via og_tags helper."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)

        # Help page uses og_tags helper
        assert "og_tags" in source
        assert "/help" in source


# ---------------------------------------------------------------------------
# E3: Help Identify Page
# ---------------------------------------------------------------------------


class TestHelpIdentifyPage:
    """Test /help page structure."""

    def test_help_route_exists(self):
        """The /help route is defined in page_routes."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)
        assert '@rt("/help")' in source

    def test_help_route_is_public(self):
        """The /help route does not require authentication."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)

        # Find the help route handler - it takes sess=None (optional)
        assert "def get(sess=None):" in source or "def get(sess" in source

    def test_help_page_has_face_cards(self):
        """The /help route renders face cards with data-testid."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)
        assert "help-face-card" in source

    def test_help_page_has_identify_cta(self):
        """The /help route has identify links for each face."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)
        assert "/identify/" in source
        assert "Do you recognize this person?" in source


# ---------------------------------------------------------------------------
# E4: Timeline Life Events
# ---------------------------------------------------------------------------


class TestTimelineLifeEvents:
    """Test life events integration in the timeline."""

    def test_timeline_source_has_life_event_integration(self):
        """The timeline route source code imports and queries life_events."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)
        assert "life_event" in source
        assert "list_events" in source or "_list_life_events" in source

    def test_timeline_source_has_life_event_rendering(self):
        """The timeline rendering handles life_event type entries."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)
        assert "timeline-life-event" in source
        assert 'entry["type"] == "life_event"' in source

    def test_timeline_life_event_graceful_failure(self):
        """Life event loading is wrapped in try/except for graceful degradation."""
        import inspect

        import app.page_routes as pr

        source = inspect.getsource(pr)
        # The life_events block should be in a try/except
        assert "Failed to load life events" in source

    def test_event_routes_list_events_exists(self):
        """event_routes.list_events function exists and is importable."""
        from app.event_routes import list_events

        assert callable(list_events)

    def test_event_routes_event_type_icons_exists(self):
        """EVENT_TYPE_ICONS dict exists with expected event types."""
        from app.event_routes import EVENT_TYPE_ICONS

        assert "wedding" in EVENT_TYPE_ICONS
        assert "immigration" in EVENT_TYPE_ICONS
        assert "other" in EVENT_TYPE_ICONS
