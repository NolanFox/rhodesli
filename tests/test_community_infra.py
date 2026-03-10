"""Tests for multi-community infrastructure (PRD-035 Phase 1).

Covers:
- Community routing middleware
- Community landing pages
- Upload cap and TIFF conversion
- Community admin CRUD
- Backward compatibility
- Supabase data layer functions
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# TIFF Detection & Conversion
# ============================================================================


class TestTiffDetection:
    """Tests for TIFF file detection by extension and magic bytes."""

    def test_tiff_by_extension_tif(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.tif", b"\x00" * 10) is True

    def test_tiff_by_extension_tiff(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.tiff", b"\x00" * 10) is True

    def test_tiff_by_extension_case_insensitive(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.TIFF", b"\x00" * 10) is True
        assert is_tiff("photo.TIF", b"\x00" * 10) is True

    def test_tiff_by_magic_bytes_little_endian(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.unknown", b"II\x2a\x00" + b"\x00" * 10) is True

    def test_tiff_by_magic_bytes_big_endian(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.unknown", b"MM\x00\x2a" + b"\x00" * 10) is True

    def test_not_tiff_jpg(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 10) is False

    def test_not_tiff_png(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.png", b"\x89PNG" + b"\x00" * 10) is False

    def test_not_tiff_empty_bytes(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.unknown", b"") is False

    def test_not_tiff_short_bytes(self):
        from app.upload_routes import is_tiff

        assert is_tiff("photo.unknown", b"\x00\x00") is False


class TestTiffConversion:
    """Tests for TIFF to JPEG conversion."""

    def test_convert_rgb_tiff(self):
        from PIL import Image

        from app.upload_routes import convert_tiff_to_jpg

        # Create a small test TIFF in memory
        img = Image.new("RGB", (10, 10), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, "TIFF")
        tiff_bytes = buf.getvalue()

        result = convert_tiff_to_jpg(tiff_bytes)
        assert len(result) > 0
        # Verify it's a valid JPEG
        assert result[:2] == b"\xff\xd8"

    def test_convert_rgba_tiff(self):
        from PIL import Image

        from app.upload_routes import convert_tiff_to_jpg

        # Create RGBA TIFF (should be converted to RGB)
        img = Image.new("RGBA", (10, 10), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, "TIFF")
        tiff_bytes = buf.getvalue()

        result = convert_tiff_to_jpg(tiff_bytes)
        assert len(result) > 0
        assert result[:2] == b"\xff\xd8"


# ============================================================================
# Upload Cap
# ============================================================================


class TestUploadCap:
    """Tests for upload file count limit."""

    def test_max_files_per_upload_is_200(self):
        """Verify the upload cap was raised from 50 to 200."""
        import app.upload_routes as upload_mod

        # Read the source to verify the constant
        import inspect

        source = inspect.getsource(upload_mod.post)
        assert "MAX_FILES_PER_UPLOAD = 200" in source


# ============================================================================
# Community Supabase Data Layer
# ============================================================================


class TestCommunityDataLayer:
    """Tests for community functions in supabase_data.py."""

    def test_default_rhodes_community(self):
        from app.supabase_data import _default_rhodes_community

        c = _default_rhodes_community()
        assert c["slug"] == "rhodes"
        assert c["is_default"] is True
        assert "Rhodes" in c["name"]

    def test_get_community_by_slug_fallback_rhodes(self):
        """When Supabase is unavailable, Rhodes slug returns default."""
        from app.supabase_data import get_community_by_slug

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import _invalidate_community_cache

            _invalidate_community_cache()
            result = get_community_by_slug("rhodes")
            assert result is not None
            assert result["slug"] == "rhodes"

    def test_get_community_by_slug_fallback_unknown(self):
        """When Supabase is unavailable, unknown slug returns None."""
        from app.supabase_data import get_community_by_slug

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import _invalidate_community_cache

            _invalidate_community_cache()
            result = get_community_by_slug("nonexistent")
            assert result is None

    def test_load_communities_no_supabase(self):
        from app.supabase_data import load_communities

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_communities() is None

    def test_create_community_no_supabase(self):
        from app.supabase_data import create_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert create_community({"name": "Test", "slug": "test"}) is None

    def test_update_community_no_supabase(self):
        from app.supabase_data import update_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert update_community("some-id", {"name": "Updated"}) is None

    def test_add_photo_to_community_no_supabase(self):
        from app.supabase_data import add_photo_to_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert add_photo_to_community("photo-1", "comm-1") is False

    def test_add_identity_to_community_no_supabase(self):
        from app.supabase_data import add_identity_to_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert add_identity_to_community("id-1", "comm-1") is False

    def test_create_upload_batch_no_supabase(self):
        from app.supabase_data import create_upload_batch

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert create_upload_batch({"job_id": "abc"}) is None

    def test_load_photos_for_community_no_supabase(self):
        from app.supabase_data import load_photos_for_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_photos_for_community("comm-1") is None

    def test_load_identities_for_community_no_supabase(self):
        from app.supabase_data import load_identities_for_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_identities_for_community("comm-1") is None

    def test_community_cache_invalidation(self):
        from app.supabase_data import _community_cache, _invalidate_community_cache

        # Populate cache
        from app.supabase_data import _community_cache as cache_ref

        _invalidate_community_cache()
        import app.supabase_data as sd

        sd._community_cache["test"] = {"slug": "test"}
        sd._community_cache_ts = 99999999999.0
        assert "test" in sd._community_cache

        _invalidate_community_cache()
        assert len(sd._community_cache) == 0
        assert sd._community_cache_ts == 0.0


# ============================================================================
# Community Middleware
# ============================================================================


class TestCommunityMiddleware:
    """Tests for CommunityMiddleware path parsing."""

    def test_middleware_class_exists(self):
        from app.main import CommunityMiddleware

        assert CommunityMiddleware is not None

    def test_community_slug_pattern(self):
        from app.main import _community_slug_pattern

        # Valid slug patterns
        m = _community_slug_pattern.match("/c/fox-family/browse")
        assert m is not None
        assert m.group(1) == "fox-family"
        assert m.group(2) == "/browse"

        m = _community_slug_pattern.match("/c/rhodes/photos")
        assert m is not None
        assert m.group(1) == "rhodes"
        assert m.group(2) == "/photos"

    def test_community_slug_pattern_root(self):
        from app.main import _community_slug_pattern

        m = _community_slug_pattern.match("/c/fox-family/")
        assert m is not None
        assert m.group(1) == "fox-family"
        assert m.group(2) == "/"

    def test_no_match_regular_path(self):
        from app.main import _community_slug_pattern

        m = _community_slug_pattern.match("/browse")
        assert m is None

    def test_no_match_incomplete_prefix(self):
        from app.main import _community_slug_pattern

        m = _community_slug_pattern.match("/c/")
        assert m is None

    def test_skip_prefixes_defined(self):
        from app.main import _COMMUNITY_SKIP_PREFIXES

        assert "/static/" in _COMMUNITY_SKIP_PREFIXES
        assert "/api/" in _COMMUNITY_SKIP_PREFIXES


# ============================================================================
# Community Landing Page
# ============================================================================


class TestCommunityLandingPage:
    """Tests for community-specific landing pages."""

    def test_community_landing_page_renders(self):
        from app.page_routes import _community_landing_page

        community = {
            "id": "test-id",
            "slug": "fox-family",
            "name": "Fox Family Archive",
            "landing_title": "Fox Family Heritage",
            "landing_subtitle": "Four generations of family photos",
        }

        with patch("app.supabase_data.load_photos_for_community", return_value=[]):
            with patch("app.supabase_data.load_identities_for_community", return_value=[]):
                result = _community_landing_page(community, "fox-family")

        # Should return a tuple (Title, Div)
        assert len(result) == 2
        html = repr(result[1])
        assert "Fox Family Heritage" in html
        assert "community-landing" in html
        assert "fox-family" in html

    def test_community_landing_page_empty_state(self):
        import app.main  # noqa: F401 — ensure full import chain resolves
        from app.page_routes import _community_landing_page

        community = {
            "id": "test-id",
            "slug": "new-community",
            "name": "New Community",
        }

        with patch("app.supabase_data.load_photos_for_community", return_value=[]):
            with patch("app.supabase_data.load_identities_for_community", return_value=[]):
                result = _community_landing_page(community, "new-community")

        html = repr(result[1])
        assert "just getting started" in html

    def test_community_landing_page_with_content(self):
        import app.main  # noqa: F401 — ensure full import chain resolves
        from app.page_routes import _community_landing_page

        community = {
            "id": "test-id",
            "slug": "fox-family",
            "name": "Fox Family",
            "landing_title": "Fox Family Archive",
        }

        with patch("app.main._get_community_photo_ids", return_value={"p1", "p2", "p3"}):
            with patch("app.main._get_community_identity_ids", return_value={"i1", "i2"}):
                result = _community_landing_page(community, "fox-family")

        html = repr(result[1])
        assert "3" in html  # photo count
        assert "2" in html  # identity count
        assert "Browse Photos" in html


# ============================================================================
# Community Admin CRUD
# ============================================================================


class TestCommunityAdminCRUD:
    """Tests for admin community management routes."""

    def test_community_form_helper(self):
        from app.admin_routes import _community_form

        form = _community_form(action="/admin/communities", submit_label="Create")
        html = repr(form)
        assert "community-form" in html
        assert "Create" in html

    def test_community_form_with_existing(self):
        from app.admin_routes import _community_form

        community = {"name": "Test", "slug": "test", "landing_title": "Test Title"}
        form = _community_form(action="/admin/communities/test", submit_label="Save", community=community)
        html = repr(form)
        assert "Test" in html
        assert "readonly" in html  # slug is readonly for edit


# ============================================================================
# Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Tests verifying existing URLs continue to work with community middleware."""

    def test_health_route_exists(self):
        """Health endpoint should still be accessible."""
        from app.main import app

        route_paths = [getattr(r, "path", "") for r in app.routes]
        assert "/health" in route_paths

    def test_browse_route_exists(self):
        """Browse photos route should still be accessible."""
        from app.main import app

        route_paths = [getattr(r, "path", "") for r in app.routes]
        assert "/photos" in route_paths

    def test_root_route_exists(self):
        """Root route should still be accessible."""
        from app.main import app

        route_paths = [getattr(r, "path", "") for r in app.routes]
        assert "/" in route_paths

    def test_upload_route_exists(self):
        """Upload route should still be accessible."""
        from app.main import app

        route_paths = [getattr(r, "path", "") for r in app.routes]
        assert "/upload" in route_paths

    def test_identify_route_exists(self):
        """Identify route should still be accessible."""
        from app.main import app

        route_paths = [getattr(r, "path", "") for r in app.routes]
        # Check for identify pattern
        has_identify = any("/identify" in str(getattr(r, "path", "")) for r in app.routes)
        assert has_identify

    def test_admin_communities_route_exists(self):
        """Admin communities route should be registered."""
        from app.main import app

        route_paths = [getattr(r, "path", "") for r in app.routes]
        assert "/admin/communities" in route_paths

    def test_admin_community_edit_route_exists(self):
        """Admin community edit route should be registered."""
        from app.main import app

        has_edit = any("/admin/communities/" in str(getattr(r, "path", "")) for r in app.routes)
        assert has_edit
