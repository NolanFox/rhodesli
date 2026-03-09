"""Tests for admin bar component."""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

import app.main


@pytest.fixture
def client():
    """Test client for the app."""
    from app.main import app

    return TestClient(app)


@pytest.fixture
def auth_disabled():
    """Disable auth for testing."""
    with patch("app.main.is_auth_enabled", return_value=False):
        yield


class TestAdminBarComponent:
    """Test the _admin_bar() helper function."""

    def test_admin_bar_renders_for_admin(self):
        """Admin bar renders when user is admin."""
        from app.main import _admin_bar

        mock_user = MagicMock()
        mock_user.is_admin = True
        bar = _admin_bar(mock_user)
        html = repr(bar)
        assert "admin-bar" in html
        assert "Admin Mode" in html

    def test_admin_bar_hidden_for_non_admin(self):
        """Admin bar returns empty for non-admin user."""
        from app.main import _admin_bar

        mock_user = MagicMock()
        mock_user.is_admin = False
        bar = _admin_bar(mock_user)
        html = repr(bar)
        assert "admin-bar" not in html

    def test_admin_bar_hidden_for_none_user(self):
        """Admin bar returns empty when user is None."""
        from app.main import _admin_bar

        bar = _admin_bar(None)
        html = repr(bar)
        assert "admin-bar" not in html

    def test_admin_bar_has_pending_count(self):
        """Admin bar shows pending identity count."""
        from app.main import _admin_bar

        mock_user = MagicMock()
        mock_user.is_admin = True
        bar = _admin_bar(mock_user)
        html = repr(bar)
        assert "Pending" in html

    def test_admin_bar_has_proposal_count(self):
        """Admin bar shows proposal count."""
        from app.main import _admin_bar

        mock_user = MagicMock()
        mock_user.is_admin = True
        bar = _admin_bar(mock_user)
        html = repr(bar)
        assert "Proposals" in html

    def test_admin_bar_links_to_admin_sections(self):
        """Admin bar has links to admin sections."""
        from app.main import _admin_bar

        mock_user = MagicMock()
        mock_user.is_admin = True
        bar = _admin_bar(mock_user)
        html = repr(bar)
        assert "section=to_review" in html
        assert "/upload" in html


class TestAdminBarOnPages:
    """Test admin bar appears on the right pages."""

    def test_photo_page_no_admin_bar_anonymous(self, client, auth_disabled):
        """Photo page has no admin bar for anonymous users."""
        response = client.get("/photo/a3d2695fe0804844")
        html = response.text
        # auth disabled means no user object, admin bar should not appear
        assert 'id="admin-bar"' not in html

    def test_person_page_no_admin_bar_anonymous(self, client, auth_disabled):
        """Person page has no admin bar for anonymous users."""
        from app.main import load_registry
        from core.registry import IdentityState

        registry = load_registry()
        confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
        if confirmed:
            person_id = confirmed[0]["identity_id"]
            response = client.get(f"/person/{person_id}")
            html = response.text
            assert 'id="admin-bar"' not in html

    def test_admin_bar_renders_with_admin_user(self):
        """Admin bar renders correctly for admin users on photo page."""
        from app.main import _admin_bar

        mock_user = MagicMock()
        mock_user.is_admin = True
        result = _admin_bar(mock_user)
        html = repr(result)
        assert 'data-testid="admin-bar"' in html
        assert "Admin Mode" in html
