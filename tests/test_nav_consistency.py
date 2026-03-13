"""Tests for consistent navigation across all public pages."""

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app, _public_nav_links


@pytest.fixture
def client():
    return TestClient(app)


class TestPublicNavLinks:
    """Test the centralized _public_nav_links helper."""

    def test_returns_all_links(self):
        with patch("app.main.is_auth_enabled", return_value=False):
            links = _public_nav_links(active="photos")
            hrefs = [link.attrs.get("href", "") for link in links]
            assert "/photos" in hrefs
            assert "/collections" in hrefs
            assert "/people" in hrefs
            assert "/map" in hrefs
            assert "/timeline" in hrefs
            assert "/connect" in hrefs
            assert "/tools/compare" in hrefs
            assert "/tools/estimate" in hrefs
            assert "/help" in hrefs

    def test_active_link_highlighted(self):
        with patch("app.main.is_auth_enabled", return_value=False):
            links = _public_nav_links(active="map")
            for link in links:
                href = link.attrs.get("href", "")
                cls = link.attrs.get("class", "")
                if not href or href in ("/?section=skipped", "/help"):
                    continue
                if href == "/map":
                    assert "text-amber-950" in cls
                else:
                    assert "text-amber-900/60" in cls

    def test_sign_in_when_auth_enabled_no_user(self):
        with patch("app.main.is_auth_enabled", return_value=True):
            links = _public_nav_links(active="photos", user=None)
            texts = [str(link.children[0]) if link.children else "" for link in links]
            assert any("Sign In" in t for t in texts)

    def test_no_sign_in_when_auth_disabled(self):
        with patch("app.main.is_auth_enabled", return_value=False):
            links = _public_nav_links(active="photos", user=None)
            # Should have 11 items (5 archive + span + 4 tools + help identify)
            assert len(links) == 11

    def test_no_sign_in_when_user_logged_in(self):
        mock_user = MagicMock()
        mock_user.email = "test@test.com"
        with patch("app.main.is_auth_enabled", return_value=True):
            links = _public_nav_links(active="photos", user=mock_user)
            # Should have 12 items (5 archive + span + 4 tools + help identify + bell icon)
            assert len(links) == 12

    def test_link_order(self):
        with patch("app.main.is_auth_enabled", return_value=False):
            links = _public_nav_links(active="")
            hrefs = [link.attrs.get("href", "") for link in links]
            expected_order = [
                "/photos",
                "/collections",
                "/people",
                "/timeline",
                "/map",
                "",
                "/tree",
                "/connect",
                "/tools/compare",
                "/tools/estimate",
                "/help",
            ]
            assert hrefs == expected_order


class TestNavOnPublicPages:
    """Verify navigation links appear on all public pages."""

    def _get_page(self, client, path, extra_patches=None):
        """Get a page with standard mocks applied."""
        from core.registry import IdentityRegistry

        mock_registry = IdentityRegistry.__new__(IdentityRegistry)
        mock_registry._identities = {}
        mock_registry._history = []
        mock_registry._path = None

        mock_photo_reg = MagicMock()
        mock_photo_reg.list_photos = MagicMock(return_value=[])
        mock_photo_reg.get_photo = MagicMock(return_value=None)
        mock_photo_reg.get_photo_for_face = MagicMock(return_value=None)
        mock_photo_reg._photos = {}  # Prevent MagicMock auto-attrs leaking into JSON serialization

        import pathlib

        orig_exists = pathlib.Path.exists
        orig_read_text = pathlib.Path.read_text

        def mock_exists(self):
            s = str(self)
            if any(x in s for x in ["photo_index", "photo_locations"]):
                return True
            if any(x in s for x in ["co_occurrence", "relationships"]):
                return False
            return orig_exists(self)

        mock_pi = {"schema_version": 1, "photos": {}, "face_to_photo": {}}
        mock_locs = {"version": 1, "photos": {}}

        def mock_read_text(self, **kwargs):
            s = str(self)
            if "photo_locations" in s:
                return json.dumps(mock_locs)
            if "photo_index" in s:
                return json.dumps(mock_pi)
            return orig_read_text(self, **kwargs)

        patches = [
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.load_photo_registry", return_value=mock_photo_reg),
            patch("app.main._build_caches"),
            patch("app.main.get_crop_files", return_value={}),
            patch("core.storage.get_photo_url", side_effect=lambda p: f"/photos/{p}"),
            patch("app.main._load_date_labels", return_value={}),
            patch.object(pathlib.Path, "exists", mock_exists),
            patch.object(pathlib.Path, "read_text", mock_read_text),
        ]
        if extra_patches:
            patches.extend(extra_patches)

        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            return client.get(path)

    @pytest.mark.parametrize(
        "path,expected_links",
        [
            ("/photos", ["/collections", "/people", "/map", "/timeline", "/tree", "/connect", "/tools/compare"]),
            ("/people", ["/photos", "/collections", "/map", "/timeline", "/tree", "/connect", "/tools/compare"]),
            ("/collections", ["/photos", "/people", "/map", "/timeline", "/tree", "/connect", "/tools/compare"]),
            ("/map", ["/photos", "/collections", "/people", "/timeline", "/tree", "/connect", "/tools/compare"]),
            ("/connect", ["/photos", "/collections", "/people", "/map", "/timeline", "/tree", "/tools/compare"]),
        ],
    )
    def test_nav_links_present(self, client, path, expected_links):
        resp = self._get_page(client, path)
        assert resp.status_code == 200
        for link in expected_links:
            assert f'href="{link}"' in resp.text, f"Missing nav link {link} on {path}"
