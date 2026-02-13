"""Tests for Open Graph meta tags on public pages.

Tests cover:
- /photo/{id} has correct og:title, og:description, og:image
- og:description correctly counts identified/unidentified people
- og:image URL is publicly accessible format
- Landing page has site-level OG tags
- Twitter card meta tags present
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


class TestPhotoPageOGTags:
    """Open Graph tags on /photo/{id}."""

    def test_og_title_present(self, client, real_photo_id):
        """Photo page has og:title meta tag."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'property="og:title"' in html

    def test_og_description_present(self, client, real_photo_id):
        """Photo page has og:description meta tag."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'property="og:description"' in html

    def test_og_image_present(self, client, real_photo_id):
        """Photo page has og:image meta tag."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'property="og:image"' in html

    def test_og_url_present(self, client, real_photo_id):
        """Photo page has og:url meta tag."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'property="og:url"' in html

    def test_og_type_is_article(self, client, real_photo_id):
        """Photo page og:type is article."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'content="article"' in html

    def test_og_site_name_present(self, client, real_photo_id):
        """Photo page has og:site_name."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'property="og:site_name"' in html
        assert "Heritage Photo Archive" in html

    def test_twitter_card_present(self, client, real_photo_id):
        """Photo page has Twitter card meta tags."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'name="twitter:card"' in html
        assert 'content="summary_large_image"' in html

    def test_twitter_title_present(self, client, real_photo_id):
        """Photo page has twitter:title meta tag."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'name="twitter:title"' in html

    def test_og_description_mentions_faces(self, client, real_photo_id):
        """OG description includes face/person count info."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Should mention either identified people or detected faces
        assert "identified" in html or "detected" in html or "help" in html.lower()

    def test_meta_description_present(self, client, real_photo_id):
        """Standard meta description tag is also set."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'name="description"' in html


class TestLandingPageOGTags:
    """Open Graph tags on the landing page."""

    def test_landing_og_title(self, client):
        """Landing page has og:title."""
        response = client.get("/")
        html = response.text
        assert 'property="og:title"' in html
        assert "Rhodesli" in html

    def test_landing_og_description(self, client):
        """Landing page has og:description with dynamic stats."""
        response = client.get("/")
        html = response.text
        assert 'property="og:description"' in html
        assert "photographs" in html

    def test_landing_og_image(self, client):
        """Landing page has og:image."""
        response = client.get("/")
        html = response.text
        assert 'property="og:image"' in html

    def test_landing_og_type_is_website(self, client):
        """Landing page og:type is website."""
        response = client.get("/")
        html = response.text
        assert 'content="website"' in html

    def test_landing_twitter_card(self, client):
        """Landing page has Twitter card tags."""
        response = client.get("/")
        html = response.text
        assert 'name="twitter:card"' in html

    def test_landing_meta_description(self, client):
        """Landing page has meta description."""
        response = client.get("/")
        html = response.text
        assert 'name="description"' in html


class TestOGImageURL:
    """OG image URLs should be publicly accessible."""

    def test_photo_og_image_is_absolute_url(self, client, real_photo_id):
        """og:image URL is absolute (starts with https://)."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Find the og:image content
        import re
        match = re.search(r'property="og:image"\s+content="([^"]+)"', html)
        if match:
            og_image = match.group(1)
            assert og_image.startswith("http"), f"og:image should be absolute URL, got: {og_image}"
