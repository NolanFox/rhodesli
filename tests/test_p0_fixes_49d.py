"""Tests for P0 bug fixes documented in Session 49D.

Covers:
- UX-036: Merge button URL in focus mode uses ? not & for query string start
- UX-070-072: /photo/{id} page has id="photo-modal-content" and Name These Faces
  targets #photo-modal-content (not the old #admin-name-faces-container)
- UX-044/052: Compare upload area messaging (49E: corrected to "used for matching")
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Bug 1: UX-036 — Merge Button URL (from_focus=true query string)
# ---------------------------------------------------------------------------


class TestMergeButtonFocusUrl:
    """In focus mode, the merge button URL must begin query params with ?.

    Bug: The URL was being constructed as
         /api/identity/{target}/merge/{neighbor}&from_focus=true
    Fix: It should be
         /api/identity/{target}/merge/{neighbor}?from_focus=true
    """

    def _make_neighbor(self, neighbor_id="neighbor-abc", can_merge=True):
        return {
            "identity_id": neighbor_id,
            "name": "Test Person",
            "distance": 0.4,
            "percentile": 0.9,
            "confidence_gap": 15.0,
            "can_merge": can_merge,
            "merge_blocked_reason": None,
            "anchor_face_ids": ["face-1"],
            "candidate_face_ids": [],
            "state": "INBOX",
        }

    def test_focus_mode_merge_url_starts_with_question_mark(self):
        """Merge button URL in focus mode must use ?from_focus=true, not &from_focus=true."""
        from app.main import neighbor_card, to_xml

        neighbor = self._make_neighbor()
        html = to_xml(
            neighbor_card(
                neighbor,
                "target-id",
                set(),
                user_role="admin",
                from_focus=True,
            )
        )

        # The URL must contain ?from_focus=true — the query string starts with ?
        assert "?from_focus=true" in html, \
            "Merge URL must use ?from_focus=true to start the query string"

    def test_focus_mode_merge_url_does_not_start_with_ampersand(self):
        """Merge button URL must not join from_focus with & (invalid URL)."""
        from app.main import neighbor_card, to_xml

        neighbor = self._make_neighbor()
        html = to_xml(
            neighbor_card(
                neighbor,
                "target-id",
                set(),
                user_role="admin",
                from_focus=True,
            )
        )

        # Catch the regression: &from_focus appearing without a preceding ?
        import re
        # Find all hx-post URLs that contain from_focus
        bad_pattern = re.findall(r'hx-post="[^"]*&amp;from_focus=true', html)
        bad_pattern += re.findall(r'hx-post="[^"]*&from_focus=true', html)
        assert len(bad_pattern) == 0, \
            f"Merge URL joins from_focus with & instead of ?: {bad_pattern}"

    def test_non_focus_mode_merge_url_has_no_suffix(self):
        """In non-focus mode the merge URL must have no from_focus suffix."""
        from app.main import neighbor_card, to_xml

        neighbor = self._make_neighbor()
        html = to_xml(
            neighbor_card(
                neighbor,
                "target-id",
                set(),
                user_role="admin",
                from_focus=False,
            )
        )

        assert "from_focus" not in html, \
            "Non-focus mode must not include from_focus in merge URL"

    def test_focus_mode_with_filter_url_correct_order(self):
        """Focus mode with a triage filter: ?from_focus=true&filter=ready."""
        from app.main import neighbor_card, to_xml

        neighbor = self._make_neighbor()
        html = to_xml(
            neighbor_card(
                neighbor,
                "target-id",
                set(),
                user_role="admin",
                from_focus=True,
                triage_filter="ready",
            )
        )

        # The query string must start with ? and filter follows with &
        assert "?from_focus=true&amp;filter=ready" in html or \
               "?from_focus=true&filter=ready" in html, \
            "Filter must follow from_focus with &, not precede it with ?"

    def test_focus_mode_merge_url_full_structure(self):
        """The full merge URL in focus mode follows the correct structure."""
        from app.main import neighbor_card, to_xml

        neighbor = self._make_neighbor(neighbor_id="neighbor-xyz")
        html = to_xml(
            neighbor_card(
                neighbor,
                "target-id",
                set(),
                user_role="admin",
                from_focus=True,
            )
        )

        # Should contain the merge endpoint with query string starting with ?
        import re
        merge_urls = re.findall(
            r'hx-post="(/api/identity/[^"]+/merge/[^"]+)"', html
        )
        assert len(merge_urls) > 0, "Should have a merge button with hx-post URL"
        for url in merge_urls:
            # ? must appear before from_focus, never & before from_focus
            if "from_focus" in url:
                idx_q = url.find("?")
                idx_focus = url.find("from_focus")
                assert idx_q < idx_focus, \
                    f"? must precede from_focus in merge URL: {url!r}"
                assert idx_q != -1, \
                    f"Merge URL has from_focus but no leading ?: {url!r}"


# ---------------------------------------------------------------------------
# Bug 2: UX-070-072 — /photo/{id} page targets and element IDs
# ---------------------------------------------------------------------------


class TestPhotoPageModalContent:
    """/photo/{id} renders id="photo-modal-content" and Name These Faces
    targets #photo-modal-content, not the old #admin-name-faces-container.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    def _get_real_photo_id(self):
        """Return a real photo_id from the app's cache."""
        from app.main import load_embeddings_for_photos
        photos = load_embeddings_for_photos()
        return next(iter(photos.keys())) if photos else None

    def test_photo_page_has_photo_modal_content_id(self):
        """The /photo/{id} page must contain id="photo-modal-content"."""
        photo_id = self._get_real_photo_id()
        if not photo_id:
            pytest.skip("No embeddings available")

        resp = self.client.get(f"/photo/{photo_id}")
        assert resp.status_code == 200
        assert 'id="photo-modal-content"' in resp.text, \
            "The /photo/{id} page must have id='photo-modal-content' on its main content div"

    def test_photo_page_does_not_have_old_container_id(self):
        """The /photo/{id} page must NOT contain the old admin-name-faces-container."""
        photo_id = self._get_real_photo_id()
        if not photo_id:
            pytest.skip("No embeddings available")

        resp = self.client.get(f"/photo/{photo_id}")
        assert resp.status_code == 200
        assert "admin-name-faces-container" not in resp.text, \
            "The old id='admin-name-faces-container' must not be present (replaced by photo-modal-content)"

    def test_name_these_faces_button_targets_photo_modal_content(self):
        """When Name These Faces button is present, it must target #photo-modal-content."""
        photo_id = self._get_real_photo_id()
        if not photo_id:
            pytest.skip("No embeddings available")

        # Use admin user so Name These Faces button is rendered (if eligible)
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user") as mock_user:
            from app.auth import User
            mock_user.return_value = User(
                id="admin-1", email="admin@rhodesli.test", is_admin=True
            )
            resp = self.client.get(f"/photo/{photo_id}")

        assert resp.status_code == 200
        html = resp.text

        # If the button is present, verify its target
        if "Name These Faces" in html:
            assert 'hx-target="#photo-modal-content"' in html, \
                "Name These Faces button must target #photo-modal-content"
            assert 'hx-target="#admin-name-faces-container"' not in html, \
                "Name These Faces must not target the old #admin-name-faces-container"

    def test_name_these_faces_button_targets_not_old_container(self):
        """Name These Faces must never reference #admin-name-faces-container anywhere."""
        photo_id = self._get_real_photo_id()
        if not photo_id:
            pytest.skip("No embeddings available")

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user") as mock_user:
            from app.auth import User
            mock_user.return_value = User(
                id="admin-1", email="admin@rhodesli.test", is_admin=True
            )
            resp = self.client.get(f"/photo/{photo_id}")

        assert "admin-name-faces-container" not in resp.text, \
            "#admin-name-faces-container must not appear anywhere on /photo/{id}"

    def test_photo_page_photo_modal_content_is_present_for_anonymous(self):
        """Anonymous users also see a page with id='photo-modal-content'."""
        photo_id = self._get_real_photo_id()
        if not photo_id:
            pytest.skip("No embeddings available")

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = self.client.get(f"/photo/{photo_id}")

        assert resp.status_code == 200
        assert 'id="photo-modal-content"' in resp.text, \
            "Anonymous users must also see id='photo-modal-content'"


class TestPhotoPartialRouteModalContent:
    """The /photo/{id}/partial HTMX route must also target photo-modal-content."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    def _get_real_photo_id(self):
        from app.main import load_embeddings_for_photos
        photos = load_embeddings_for_photos()
        return next(iter(photos.keys())) if photos else None

    def test_partial_route_does_not_have_old_container(self):
        """The /photo/{id}/partial route must not reference admin-name-faces-container."""
        photo_id = self._get_real_photo_id()
        if not photo_id:
            pytest.skip("No embeddings available")

        resp = self.client.get(
            f"/photo/{photo_id}/partial",
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        assert "admin-name-faces-container" not in resp.text, \
            "Partial route must not reference admin-name-faces-container"


# ---------------------------------------------------------------------------
# Bug 3: UX-044/052 — Compare upload messaging
# ---------------------------------------------------------------------------


class TestCompareUploadMessaging:
    """The compare upload area must accurately describe what happens with uploads.

    UX-044: Upload area originally said "Photos are saved to help grow the archive."
    49D Fix: Changed to "not stored in the archive" — but this was also inaccurate.
    49E Fix: Changed to "used for matching. Sign in to contribute" — accurate.
    Photos ARE uploaded to R2 for processing, and logged-in users can contribute.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    def test_compare_page_contains_matching_messaging(self):
        """The compare page must say the photo is used for matching."""
        resp = self.client.get("/compare")
        assert resp.status_code == 200
        assert "used for matching" in resp.text, \
            "Compare page must tell users their photo is used for matching"

    def test_compare_page_does_not_contain_saved_to_grow(self):
        """The compare page must NOT say 'saved to help grow the archive'."""
        resp = self.client.get("/compare")
        assert resp.status_code == 200
        assert "saved to help grow the archive" not in resp.text, \
            "Old misleading 'saved to help grow the archive' text must be removed"

    def test_compare_page_contribute_messaging(self):
        """The compare page should mention contributing to the archive."""
        resp = self.client.get("/compare")
        assert resp.status_code == 200
        assert "contribute" in resp.text.lower(), \
            "Compare page must mention the option to contribute"

    def test_compare_page_upload_messaging_with_auth_enabled(self):
        """Correct messaging also appears when auth is enabled."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = self.client.get("/compare")
        assert resp.status_code == 200
        assert "used for matching" in resp.text, \
            "Upload messaging must be correct regardless of auth state"
        assert "saved to help grow the archive" not in resp.text
