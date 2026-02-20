"""Tests for Session 49C bug fixes.

Covers:
- Photo page 404 for community/inbox photos (alias resolution)
- Compare upload form auto-submission on file select
- Version display (not v0.0.0)
- Collection name truncation removed from identify/person pages
"""

import re

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Bug 1: Photo 404 for community/inbox photos
# ---------------------------------------------------------------------------


class TestPhotoAliasResolution:
    """Photos with inbox_* IDs in photo_index.json should resolve via alias."""

    def test_get_photo_metadata_resolves_inbox_alias(self):
        """get_photo_metadata should resolve inbox_* IDs to SHA256 cache IDs."""
        from app.main import get_photo_metadata
        import app.main as main_module

        # Simulate the cache state: SHA256 ID exists, inbox ID does not
        sha256_id = "b32b4403b21985b7"
        inbox_id = "inbox_community-batch-20260214_7_test"
        photo_data = {
            "filename": "test_photo.jpg",
            "faces": [],
            "source": "Test",
            "collection": "Test Collection",
        }

        with patch.object(main_module, "_photo_cache", {sha256_id: photo_data}), \
             patch.object(main_module, "_photo_id_aliases", {inbox_id: sha256_id}), \
             patch.object(main_module, "_face_to_photo_cache", {}), \
             patch.object(main_module, "_build_caches"):
            # Direct SHA256 lookup should work
            result = get_photo_metadata(sha256_id)
            assert result is not None
            assert result["filename"] == "test_photo.jpg"

            # Inbox alias lookup should also work
            result = get_photo_metadata(inbox_id)
            assert result is not None
            assert result["filename"] == "test_photo.jpg"

    def test_get_photo_metadata_returns_none_for_unknown_id(self):
        """Unknown photo IDs should still return None."""
        from app.main import get_photo_metadata
        import app.main as main_module

        with patch.object(main_module, "_photo_cache", {"abc": {"faces": []}}), \
             patch.object(main_module, "_photo_id_aliases", {}), \
             patch.object(main_module, "_face_to_photo_cache", {}), \
             patch.object(main_module, "_build_caches"):
            result = get_photo_metadata("nonexistent_id")
            assert result is None

    def test_photo_page_200_for_inbox_id(self, client):
        """GET /photo/{inbox_id} should return 200, not 404."""
        import app.main as main_module

        inbox_id = "inbox_community-batch-20260214_7_test"
        sha256_id = "b32b4403b21985b7"
        photo_data = {
            "filename": "test_photo.jpg",
            "path": "raw_photos/test_photo.jpg",
            "faces": [{"face_id": "test_face_1", "bbox": [10, 20, 100, 200], "det_score": 0.99}],
            "source": "Community",
            "collection": "Test Collection",
            "width": 800,
            "height": 600,
        }

        with patch.object(main_module, "_photo_cache", {sha256_id: photo_data}), \
             patch.object(main_module, "_photo_id_aliases", {inbox_id: sha256_id}), \
             patch.object(main_module, "_face_to_photo_cache", {"test_face_1": sha256_id}), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            resp = client.get(f"/photo/{inbox_id}")
            assert resp.status_code == 200
            assert "Photo not found" not in resp.text


# ---------------------------------------------------------------------------
# Bug 2: Compare upload form auto-submit
# ---------------------------------------------------------------------------


class TestCompareUploadFormSubmit:
    """Compare upload form should auto-submit when a file is selected."""

    def test_upload_input_has_onchange_handler(self, client):
        """File input must have onchange to trigger form submission."""
        resp = client.get("/compare")
        html = resp.text
        # The input[type=file] should have an onchange handler
        assert "onchange" in html
        assert "requestSubmit" in html

    def test_upload_form_has_htmx_post(self, client):
        """Upload form must have hx-post for HTMX submission."""
        resp = client.get("/compare")
        html = resp.text
        assert "/api/compare/upload" in html

    def test_upload_form_has_htmx_multipart_encoding(self, client):
        """Upload form must have hx-encoding=multipart/form-data for HTMX file uploads.
        Without this, HTMX sends URL-encoded data and the file is never received."""
        resp = client.get("/compare")
        html = resp.text
        assert 'hx-encoding="multipart/form-data"' in html

    def test_upload_input_restricts_file_types(self, client):
        """File input must accept only JPG and PNG, not all images."""
        resp = client.get("/compare")
        html = resp.text
        assert 'accept="image/jpeg,image/png"' in html

    def test_upload_has_client_side_size_validation(self, client):
        """File input must check file size before submitting."""
        resp = client.get("/compare")
        html = resp.text
        assert "10*1024*1024" in html or "10485760" in html

    def test_upload_has_loading_indicator(self, client):
        """Upload form must have an hx-indicator for loading state."""
        resp = client.get("/compare")
        html = resp.text
        assert "htmx-indicator" in html
        assert "Analyzing your photo" in html

    def test_upload_rejects_invalid_file_type_server_side(self, client):
        """Server must reject non-JPG/PNG files with error message."""
        from io import BytesIO
        resp = client.post(
            "/api/compare/upload",
            files={"photo": ("test.gif", BytesIO(b"GIF89a"), "image/gif")},
        )
        assert resp.status_code == 200
        assert "JPG or PNG" in resp.text

    def test_upload_rejects_oversized_file_server_side(self, client):
        """Server must reject files over 10 MB."""
        from io import BytesIO
        # 11 MB of data
        large_content = b"x" * (11 * 1024 * 1024)
        resp = client.post(
            "/api/compare/upload",
            files={"photo": ("big.jpg", BytesIO(large_content), "image/jpeg")},
        )
        assert resp.status_code == 200
        assert "too large" in resp.text

    def test_upload_no_photo_returns_error(self, client):
        """Posting without a photo should show error with proper target ID."""
        resp = client.post("/api/compare/upload")
        assert resp.status_code == 200
        assert "No photo uploaded" in resp.text


# ---------------------------------------------------------------------------
# Bug 3: Version display
# ---------------------------------------------------------------------------


class TestVersionNotZero:
    """Version should read from CHANGELOG.md, never v0.0.0."""

    def test_version_reads_from_changelog(self):
        """APP_VERSION should come from CHANGELOG.md, not be v0.0.0."""
        from app.main import APP_VERSION
        assert APP_VERSION != "v0.0.0", "Version is still v0.0.0 — CHANGELOG.md not being read"
        assert APP_VERSION.startswith("v"), f"Version '{APP_VERSION}' should start with 'v'"

    def test_changelog_copied_in_dockerfile(self):
        """Dockerfile must COPY CHANGELOG.md for production version display."""
        with open("Dockerfile") as f:
            content = f.read()
        assert "COPY CHANGELOG.md" in content, "Dockerfile must COPY CHANGELOG.md"


# ---------------------------------------------------------------------------
# Bug 4: Collection name truncation
# ---------------------------------------------------------------------------


class TestCollectionNameNoTruncation:
    """Collection names should wrap, not truncate with ellipsis."""

    def test_no_collection_name_truncation_in_source(self):
        """No collection name elements should use CSS truncate class.

        Session 49 fixed stat cards, Session 49C fixes identify/person/compare pages.
        Regression test: ensure no 'text-slate-400 truncate' or 'text-slate-500 truncate'
        patterns remain in collection name rendering code.
        """
        with open("app/main.py") as f:
            source = f.read()

        # These patterns were used for collection names and are now replaced with leading-snug.
        # Exclude comments and test-related lines.
        lines = source.split('\n')
        violations = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            # Check for truncate on slate-colored text elements (collection name pattern)
            if 'text-slate-400 truncate' in line or 'text-slate-500 truncate' in line:
                # Exclude non-collection truncation (names, emails)
                if 'match_name' in line or 'user.email' in line:
                    continue
                violations.append(f"Line {i}: {stripped}")

        assert len(violations) == 0, \
            f"Collection name elements still use truncate class:\n" + "\n".join(violations)

    def test_collection_names_use_leading_snug(self):
        """Collection name elements should use leading-snug for text wrapping."""
        with open("app/main.py") as f:
            source = f.read()

        # Verify the replacement pattern exists
        assert 'text-slate-400 leading-snug' in source, \
            "Expected 'text-slate-400 leading-snug' for collection context items"
        assert 'text-slate-500 leading-snug' in source, \
            "Expected 'text-slate-500 leading-snug' for collection labels"
