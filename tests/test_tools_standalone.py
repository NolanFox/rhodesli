"""
Tests for the standalone tools suite (Session 95 Track 2).

Tests cover:
- Tools hub page renders with tool cards
- Tool navigation bar renders on all tool pages
- Redirects from old URLs work (302 status)
- No Rhodes-specific language in standalone tool pages
- All existing estimate/compare tests still pass via redirects
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def client_no_follow():
    """Client that does NOT follow redirects, for testing 302 status."""
    return TestClient(app, follow_redirects=False)


# --- Mock data ---

_MOCK_IDENTITIES = {
    "identities": {
        "test-id-1": {
            "identity_id": "test-id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "metadata": {},
        },
    },
    "history": [],
}

_MOCK_PHOTOS = {
    "photos": {
        "photo-1": {
            "path": "test.jpg",
            "face_ids": ["face-a1"],
            "source": "Test",
            "collection": "Test Collection",
            "width": 800,
            "height": 600,
        },
    },
    "face_to_photo": {"face-a1": "photo-1"},
}

_MOCK_EMBEDDINGS = np.array(
    [
        {
            "filename": "test.jpg",
            "bbox": [10, 10, 100, 100],
            "embeddings": np.zeros(512),
            "det_score": 0.99,
            "quality": 0.8,
        }
    ]
)


def _build_mock_registry():
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._version = 1
    mock_registry._path = "/tmp/test_identities.json"
    return mock_registry


def _standard_patches():
    """Return the standard set of patches needed for route tests."""
    return [
        patch("app.main.load_registry", return_value=_build_mock_registry()),
        patch(
            "app.main.load_photo_registry",
            return_value=MagicMock(data=_MOCK_PHOTOS, get_photo=lambda pid: _MOCK_PHOTOS["photos"].get(pid)),
        ),
        patch("app.main._photo_cache", _MOCK_PHOTOS["photos"]),
        patch("app.main._face_to_photo_cache", _MOCK_PHOTOS["face_to_photo"]),
        patch("app.main.get_crop_files", return_value=set()),
        patch("app.main._load_date_labels", return_value={}),
        patch("app.main._load_birth_year_estimates", return_value={}),
    ]


# =========================================================================
# Tools Hub Page
# =========================================================================


class TestToolsHub:
    """Tests for the /tools landing page."""

    def test_tools_hub_returns_200(self, client):
        """GET /tools returns 200."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/tools")
        assert resp.status_code == 200

    def test_tools_hub_has_title(self, client):
        """Tools hub page has ML Tools title."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/tools")
        assert "ML Tools" in resp.text

    def test_tools_hub_has_estimate_card(self, client):
        """Tools hub has a card for the Date Estimator."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/tools")
        assert "tool-card-estimate" in resp.text
        assert "Date &amp; Location Estimator" in resp.text or "Date" in resp.text

    def test_tools_hub_has_compare_card(self, client):
        """Tools hub has a card for Face Comparison."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/tools")
        assert "tool-card-compare" in resp.text
        assert "Face Comparison" in resp.text

    def test_tools_hub_links_to_tool_pages(self, client):
        """Tool cards link to /tools/estimate and /tools/compare."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/tools")
        assert "/tools/estimate" in resp.text
        assert "/tools/compare" in resp.text

    def test_tools_hub_no_rhodes_specific_language(self, client):
        """Tools hub page should not contain Rhodes-specific language."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/tools")
        text = resp.text.lower()
        # The hub page itself should not reference Rhodes community
        assert "jewish community of rhodes" not in text
        assert "rhodes jewish heritage" not in text


# =========================================================================
# Tools Navigation Bar
# =========================================================================


class TestToolsNavBar:
    """Tests for the tools_nav_bar component."""

    def test_nav_bar_renders_all_links(self):
        """Navigation bar contains links to all three tool pages."""
        from app.tools_routes import tools_nav_bar

        nav = tools_nav_bar(active_tool="hub")
        html = repr(nav)
        assert "/tools" in html
        assert "/tools/estimate" in html
        assert "/tools/compare" in html

    def test_nav_bar_highlights_active_tool(self):
        """Active tool gets bold styling."""
        from app.tools_routes import tools_nav_bar

        nav = tools_nav_bar(active_tool="estimate")
        html = repr(nav)
        assert "font-bold" in html

    def test_nav_bar_on_estimate_page(self, client):
        """Tools nav bar appears on the estimate page."""
        patches = _standard_patches()
        patches.append(patch("app.main.is_auth_enabled", return_value=False))
        with ExitStack(patches):
            resp = client.get("/tools/estimate")
        assert resp.status_code == 200
        assert "Date Estimator" in resp.text

    def test_nav_bar_on_compare_page(self, client):
        """Tools nav bar appears on the compare page."""
        patches = _standard_patches()
        patches.append(patch("app.main.is_auth_enabled", return_value=False))
        with ExitStack(patches):
            resp = client.get("/tools/compare")
        assert resp.status_code == 200
        assert "Face Compare" in resp.text


# =========================================================================
# Redirects
# =========================================================================


class TestRedirects:
    """Tests for backward-compatible redirects from old URLs."""

    def test_estimate_redirect(self, client_no_follow):
        """GET /estimate returns 302 redirect to /tools/estimate."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client_no_follow.get("/estimate")
        assert resp.status_code == 302
        assert "/tools/estimate" in resp.headers["location"]

    def test_estimate_redirect_preserves_photo_param(self, client_no_follow):
        """GET /estimate?photo=X preserves the selected photo in the redirect."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client_no_follow.get("/estimate?photo=photo-123")
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "/tools/estimate" in location
        assert "photo=photo-123" in location

    def test_compare_redirect(self, client_no_follow):
        """GET /compare returns 302 redirect to /tools/compare."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client_no_follow.get("/compare")
        assert resp.status_code == 302
        assert "/tools/compare" in resp.headers["location"]

    def test_compare_redirect_preserves_params(self, client_no_follow):
        """GET /compare?face_id=X preserves query params in redirect."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client_no_follow.get("/compare?face_id=test123&person_id=abc")
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "/tools/compare" in location
        assert "face_id=test123" in location
        assert "person_id=abc" in location

    def test_estimate_redirect_follows_to_200(self, client):
        """GET /estimate with follow_redirects=True ends at 200."""
        patches = _standard_patches()
        patches.append(patch("app.main.is_auth_enabled", return_value=False))
        with ExitStack(patches):
            resp = client.get("/estimate")
        assert resp.status_code == 200

    def test_compare_redirect_follows_to_200(self, client):
        """GET /compare with follow_redirects=True ends at 200."""
        patches = _standard_patches()
        patches.append(patch("app.main.is_auth_enabled", return_value=False))
        with ExitStack(patches):
            resp = client.get("/compare")
        assert resp.status_code == 200


# =========================================================================
# Community-Agnostic Language
# =========================================================================


class TestCommunityAgnosticLanguage:
    """Verify standalone tool pages use community-agnostic language."""

    def test_estimate_page_no_rhodes_language(self, client):
        """Estimate page should not contain Rhodes-specific community language."""
        patches = _standard_patches()
        patches.append(patch("app.main.is_auth_enabled", return_value=False))
        with ExitStack(patches):
            resp = client.get("/tools/estimate")
        text = resp.text.lower()
        assert "jewish community of rhodes" not in text
        assert "rhodes jewish heritage" not in text

    def test_compare_page_no_rhodes_language(self, client):
        """Compare page should not contain Rhodes-specific community language."""
        patches = _standard_patches()
        patches.append(patch("app.main.is_auth_enabled", return_value=False))
        with ExitStack(patches):
            resp = client.get("/tools/compare")
        text = resp.text.lower()
        assert "jewish community of rhodes" not in text
        assert "rhodes jewish heritage" not in text


# =========================================================================
# Direct /tools/estimate and /tools/compare access
# =========================================================================


class TestDirectToolAccess:
    """Tests for accessing tools directly at their new URLs."""

    def test_tools_estimate_returns_200(self, client):
        """GET /tools/estimate returns 200."""
        patches = _standard_patches()
        patches.append(patch("app.main.is_auth_enabled", return_value=False))
        with ExitStack(patches):
            resp = client.get("/tools/estimate")
        assert resp.status_code == 200
        assert "When Was This Photo Taken?" in resp.text

    def test_tools_compare_returns_200(self, client):
        """GET /tools/compare returns 200."""
        patches = _standard_patches()
        patches.append(patch("app.main.is_auth_enabled", return_value=False))
        with ExitStack(patches):
            resp = client.get("/tools/compare")
        assert resp.status_code == 200
        assert "Compare Faces" in resp.text


# =========================================================================
# Helper: ExitStack for multiple context managers
# =========================================================================


class ExitStack:
    """Simple context manager that enters multiple patches."""

    def __init__(self, patches):
        self._patches = patches
        self._exits = []

    def __enter__(self):
        for p in self._patches:
            self._exits.append(p.__enter__())
        return self

    def __exit__(self, *args):
        for p in reversed(self._patches):
            p.__exit__(*args)
