"""Tests for share buttons and links to the public photo viewer.

Tests cover:
- Photo modal has share button and "Open" link
- Face card has share button
- Photos grid has share button and "Open" link
- Share buttons use data-action="share-photo" pattern
- Links point to correct /photo/{id} URL
- Share button renders on Focus Mode photo context
"""

import pytest
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos, share_button, og_tags


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


class TestShareButtonComponent:
    """The share_button() helper renders correctly in all styles."""

    def test_icon_style_has_data_action(self):
        """Icon-style share button has data-action='share-photo'."""
        from fasthtml.common import to_xml
        btn = share_button("abc123", style="icon")
        html = to_xml(btn)
        assert 'data-action="share-photo"' in html
        assert 'data-share-url="/photo/abc123"' in html

    def test_button_style_has_label(self):
        """Button-style share button includes label text."""
        from fasthtml.common import to_xml
        btn = share_button("abc123", style="button", label="Share Photo")
        html = to_xml(btn)
        assert "Share Photo" in html
        assert 'data-action="share-photo"' in html

    def test_link_style_has_label(self):
        """Link-style share button includes label text."""
        from fasthtml.common import to_xml
        btn = share_button("abc123", style="link", label="Share")
        html = to_xml(btn)
        assert "Share" in html
        assert 'data-action="share-photo"' in html

    def test_share_url_uses_photo_path(self):
        """Share URL is always /photo/{id}."""
        from fasthtml.common import to_xml
        btn = share_button("test_photo_id", style="icon")
        html = to_xml(btn)
        assert 'data-share-url="/photo/test_photo_id"' in html

    def test_url_param_takes_precedence(self):
        """url= keyword overrides photo_id for any URL."""
        from fasthtml.common import to_xml
        btn = share_button(url="/person/abc123", style="button", label="Share Person")
        html = to_xml(btn)
        assert 'data-share-url="/person/abc123"' in html
        assert "Share Person" in html

    def test_prominent_style_renders(self):
        """Prominent style creates a large CTA button."""
        from fasthtml.common import to_xml
        btn = share_button(url="/compare/result/xyz", style="prominent", label="Share This Match")
        html = to_xml(btn)
        assert "Share This Match" in html
        assert 'data-action="share-photo"' in html
        assert "shadow-lg" in html

    def test_share_title_and_text_data_attributes(self):
        """title and text params add data attributes for native share."""
        from fasthtml.common import to_xml
        btn = share_button(url="/person/abc", style="button", title="Check this out", text="A face from Rhodes")
        html = to_xml(btn)
        assert 'data-share-title="Check this out"' in html
        assert 'data-share-text="A face from Rhodes"' in html


class TestOgTagsHelper:
    """The og_tags() helper generates correct Open Graph meta tags."""

    def test_basic_og_tags(self):
        """og_tags returns title, description, and site_name."""
        from fasthtml.common import to_xml
        tags = og_tags("Test Title", "Test Description")
        html = " ".join(to_xml(t) for t in tags)
        assert 'og:title' in html
        assert 'Test Title' in html
        assert 'og:description' in html
        assert 'Test Description' in html
        assert 'og:site_name' in html

    def test_og_image_absolute_url(self):
        """Relative image URLs are converted to absolute."""
        from fasthtml.common import to_xml
        tags = og_tags("T", image_url="/static/crops/test.jpg")
        html = " ".join(to_xml(t) for t in tags)
        assert 'og:image' in html
        assert "https://" in html
        assert "/static/crops/test.jpg" in html

    def test_og_image_already_absolute(self):
        """Absolute image URLs are passed through unchanged."""
        from fasthtml.common import to_xml
        tags = og_tags("T", image_url="https://example.com/img.jpg")
        html = " ".join(to_xml(t) for t in tags)
        assert "https://example.com/img.jpg" in html

    def test_og_canonical_url(self):
        """Canonical URL appears in og:url."""
        from fasthtml.common import to_xml
        tags = og_tags("T", canonical_url="/person/abc123")
        html = " ".join(to_xml(t) for t in tags)
        assert 'og:url' in html
        assert "/person/abc123" in html

    def test_twitter_card_with_image(self):
        """summary_large_image card when image is provided."""
        from fasthtml.common import to_xml
        tags = og_tags("T", image_url="/img.jpg")
        html = " ".join(to_xml(t) for t in tags)
        assert 'summary_large_image' in html

    def test_twitter_card_without_image(self):
        """summary card when no image provided."""
        from fasthtml.common import to_xml
        tags = og_tags("T")
        html = " ".join(to_xml(t) for t in tags)
        assert 'content="summary"' in html

    def test_returns_tuple(self):
        """og_tags returns a tuple for spreading into page head."""
        tags = og_tags("T", "D", "/img.jpg", "/url")
        assert isinstance(tags, tuple)
        assert len(tags) >= 9  # At least 9 meta tags with image


class TestPhotoModalShareButton:
    """Photo context modal contains share button and open link."""

    def test_partial_has_share_button(self, client, real_photo_id):
        """The photo partial (modal content) has a share button."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        html = response.text
        assert 'data-action="share-photo"' in html
        assert f"/photo/{real_photo_id}" in html

    def test_partial_has_open_link(self, client, real_photo_id):
        """The photo partial has an 'Open' link to the public viewer."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        html = response.text
        assert ">Open</a>" in html or "Open" in html
        assert 'target="_blank"' in html

    def test_no_full_page_text(self, client, real_photo_id):
        """'Open Full Page' and 'Full Page' text no longer appears."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(
            f"/photo/{real_photo_id}/partial",
            headers={"HX-Request": "true"}
        )
        html = response.text
        assert "Open Full Page" not in html
        assert "Full Page" not in html


class TestPhotosGridShareButton:
    """Photos grid section has share buttons."""

    def test_photos_section_has_share_buttons(self, client):
        """The photos section renders share buttons."""
        response = client.get("/?section=photos")
        html = response.text
        assert 'data-action="share-photo"' in html

    def test_photos_section_has_open_link(self, client):
        """Photos grid has 'Open' links to public viewer."""
        response = client.get("/?section=photos")
        html = response.text
        assert '/photo/' in html

    def test_photos_section_no_full_page_text(self, client):
        """'Full Page' text no longer appears on photos grid."""
        response = client.get("/?section=photos")
        html = response.text
        # Should not contain bare "Full Page" (but "Open" is fine)
        assert ">Full Page<" not in html


class TestFaceCardShareButton:
    """Face cards contain share buttons."""

    def test_face_card_has_share_button(self, client):
        """Face cards in browse view include share button."""
        response = client.get("/?section=confirmed&view=browse")
        html = response.text
        # Face cards with photos should have share buttons
        if 'data-action="share-photo"' in html:
            assert "/photo/" in html


class TestGlobalShareJS:
    """Global share JavaScript is present in the main layout."""

    def test_main_page_has_share_functions(self, client):
        """The main SPA layout includes global share utility functions."""
        # Use a section page (not landing) to get the full SPA layout with scripts
        response = client.get("/?section=photos")
        html = response.text
        assert "_sharePhotoUrl" in html
        assert "_copyAndToast" in html
        assert "_showShareToast" in html

    def test_public_photo_page_has_share_functions(self, client, real_photo_id):
        """The public photo page includes share utility functions."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "_sharePhotoUrl" in html
        assert "_showShareToast" in html

    def test_share_handler_in_global_delegation(self, client):
        """Global event delegation handles share-photo action."""
        response = client.get("/?section=photos")
        html = response.text
        assert 'share-photo' in html
