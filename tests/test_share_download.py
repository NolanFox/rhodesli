"""Tests for share and download buttons on the public photo viewer.

Tests cover:
- Share button present on page with correct data attributes
- Download button present with correct href
- Download endpoint returns photo or redirect
- Share JS handler is included
- Toast notification function exists
"""

import pytest
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos


def get_real_photo_id():
    """Get a real photo_id from the embeddings for testing."""
    photos = load_embeddings_for_photos()
    if photos:
        return next(iter(photos.keys()))
    return None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_photo_id():
    return get_real_photo_id()


class TestShareButton:
    """Share button on the public photo viewer."""

    def test_share_button_present(self, client, real_photo_id):
        """Share button is rendered on the page."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Share This Photo" in html

    def test_share_button_has_data_attributes(self, client, real_photo_id):
        """Share button has data-share-url attribute."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "data-share-url" in html
        assert "data-share-title" in html

    def test_share_js_handler_present(self, client, real_photo_id):
        """JavaScript share handler is included in the page."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "navigator.share" in html
        assert "_copyAndToast" in html

    def test_share_toast_function_present(self, client, real_photo_id):
        """Toast notification function is included."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "_showShareToast" in html
        assert "Link copied" in html

    def test_share_action_attribute(self, client, real_photo_id):
        """Share button uses data-action pattern (event delegation)."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'data-action="share-photo"' in html


class TestDownloadButton:
    """Download button on the public photo viewer."""

    def test_download_button_present(self, client, real_photo_id):
        """Download button/link is rendered on the page."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Download" in html

    def test_download_link_href(self, client, real_photo_id):
        """Download link points to /photo/{id}/download."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert f"/photo/{real_photo_id}/download" in html


class TestDownloadEndpoint:
    """Download endpoint at /photo/{id}/download."""

    def test_download_returns_file(self, client, real_photo_id):
        """Download endpoint returns a file response."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}/download", follow_redirects=False)
        # In local mode: 200 with file content
        # In R2 mode: 302 redirect to R2 URL
        assert response.status_code in (200, 302)

    def test_download_invalid_photo_returns_404(self, client):
        """Download for nonexistent photo returns 404."""
        response = client.get("/photo/nonexistent-id-12345/download")
        assert response.status_code == 404

    def test_download_has_content_disposition(self, client, real_photo_id):
        """Download response has Content-Disposition attachment header."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}/download", follow_redirects=False)
        if response.status_code == 200:
            assert "content-disposition" in response.headers
            assert "attachment" in response.headers["content-disposition"]


class TestActionBar:
    """Action bar layout on the public photo viewer."""

    def test_action_bar_contains_both_buttons(self, client, real_photo_id):
        """Action bar has both share and download buttons."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Share This Photo" in html
        assert "Download" in html

    def test_share_url_matches_og_url(self, client, real_photo_id):
        """Share URL matches the og:url meta tag."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        import re
        og_match = re.search(r'property="og:url"\s+content="([^"]+)"', html)
        share_match = re.search(r'data-share-url="([^"]+)"', html)
        if og_match and share_match:
            assert og_match.group(1) == share_match.group(1)
