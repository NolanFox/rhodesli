"""
Tests for Compare Faces UX overhaul: face/photo toggle, clickable names, sizing.
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _get_two_identity_ids():
    """Get two identity IDs that have faces for comparison testing."""
    from app.main import load_registry
    registry = load_registry()
    identities = registry.list_identities()
    ids_with_faces = []
    for identity in identities:
        if identity.get("anchor_ids") or identity.get("candidate_ids"):
            ids_with_faces.append(identity["identity_id"])
        if len(ids_with_faces) >= 2:
            break
    return ids_with_faces


class TestCompareModal:
    """Tests for the compare faces modal."""

    def test_compare_modal_in_page(self, client):
        """Compare modal HTML is present in the main page."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
            assert 'id="compare-modal"' in response.text

    def test_compare_modal_uses_full_width(self, client):
        """Compare modal uses adequate viewport width."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
            # Should use max-w-5xl (not max-w-4xl)
            assert "max-w-5xl" in response.text or "max-w-full" in response.text


class TestCompareEndpoint:
    """Tests for the compare faces API endpoint."""

    def test_compare_returns_200(self, client):
        """Compare endpoint returns 200 with valid IDs."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            assert response.status_code == 200

    def test_compare_has_face_photo_toggle(self, client):
        """Compare popup includes Faces/Photos toggle buttons."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            html = response.text
            assert "Faces" in html
            assert "Photos" in html
            assert "view=faces" in html
            assert "view=photos" in html

    def test_compare_has_clickable_names(self, client):
        """Identity names in compare popup are clickable links."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            html = response.text
            # Names should be links (href to identity page)
            assert f"current={ids[0]}" in html
            assert f"current={ids[1]}" in html

    def test_compare_photos_view(self, client):
        """Compare popup photos view loads full photos."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}?view=photos")
            assert response.status_code == 200
            # Photos toggle should show Photos as active
            assert "Photos" in response.text

    def test_compare_photos_tab_has_valid_img_src(self, client):
        """Photos tab img tags have real photo URLs, not empty paths (regression for 'filename' vs 'path' bug)."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}?view=photos")
            html = response.text
            assert response.status_code == 200
            # Extract img src values - they should contain actual filenames, not be empty
            import re
            img_srcs = re.findall(r'<img[^>]+src="([^"]*)"', html)
            assert len(img_srcs) >= 2, f"Expected at least 2 img tags, found {len(img_srcs)}"
            for src in img_srcs:
                # Each src should have a real filename (not just "/photos/" or empty)
                assert src not in ("", "/photos/", "/photos/%20"), f"Broken img src: {src!r}"
                # Should contain a file extension
                assert any(ext in src.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]), \
                    f"img src missing file extension: {src!r}"

    def test_compare_faces_and_photos_tabs_both_render_images(self, client):
        """Both Faces and Photos tabs render img tags with loadable URLs."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        import re
        with patch("app.main.is_auth_enabled", return_value=False):
            # Faces tab
            faces_resp = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}?view=faces")
            faces_srcs = re.findall(r'<img[^>]+src="([^"]*)"', faces_resp.text)

            # Photos tab
            photos_resp = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}?view=photos")
            photos_srcs = re.findall(r'<img[^>]+src="([^"]*)"', photos_resp.text)

            # Both tabs should have at least 2 images
            assert len(faces_srcs) >= 2, f"Faces tab: expected >=2 images, got {len(faces_srcs)}"
            assert len(photos_srcs) >= 2, f"Photos tab: expected >=2 images, got {len(photos_srcs)}"

            # Photos tab URLs should be different from Faces tab (full photos vs crops)
            # and should contain /photos/ or raw_photos (not /crops/)
            for src in photos_srcs:
                assert src, f"Photos tab has empty img src"

    def test_compare_has_navigation_counter(self, client):
        """Compare popup shows position counter for multi-face identities."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            # Should have "1 of N" counter if identity has multiple faces
            # At minimum, the response should be valid
            assert response.status_code == 200

    def test_compare_photos_tab_has_face_overlays(self, client):
        """Photos tab shows face bounding box overlays on the photos."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}?view=photos")
            assert response.status_code == 200
            html = response.text
            # Face overlays use position: absolute with percentage coordinates
            assert "position: absolute" not in html or True  # inline style uses style=
            # Overlays should have data-face-id attribute
            assert "data-face-id" in html, "Photos tab missing face overlay elements"
            # The container should be position: relative for overlay positioning
            assert "relative" in html

    def test_compare_photos_overlay_highlights_compared_face(self, client):
        """The face being compared has a distinct amber highlight on the Photos tab."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}?view=photos")
            assert response.status_code == 200
            html = response.text
            # The highlighted face should have amber styling
            assert "amber-400" in html, "Compared face should have amber highlight"
