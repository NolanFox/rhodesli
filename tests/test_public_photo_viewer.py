"""Tests for the public shareable photo viewer at /photo/{photo_id}.

Tests cover:
- Public access (no auth required)
- Face overlay rendering with correct coordinates
- Person cards with name and crop
- 404 handling for invalid photo IDs
- Metadata display (collection, source)
- CTA section for unidentified faces
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


_render_cache: dict[str, str] = {}


def _render_photo_page_html(photo_id: str) -> str:
    """Render a photo page via TestClient with caching."""
    key = f"/photo/{photo_id}"
    if key not in _render_cache:
        c = TestClient(app)
        _render_cache[key] = c.get(key).text
    return _render_cache[key]


class TestPublicPhotoViewerAccess:
    """Public photo viewer requires no authentication."""

    def test_public_access_returns_200(self, client, real_photo_id):
        """Anyone can view /photo/{id} without login."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200

    def test_public_access_with_auth_enabled(self, client, real_photo_id, auth_enabled, no_user):
        """Anonymous users can view photos even when auth is enabled."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200

    def test_page_contains_rhodesli_branding(self, client, real_photo_id):
        """Public page includes Rhodesli branding."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Rhodesli" in html

    def test_page_contains_nav_links(self, client, real_photo_id):
        """Public page includes navigation links to photos and people."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Photos" in html
        assert "People" in html
        # Back to Photos breadcrumb (UX-103 replaced "Explore More Photos")
        assert "Back to Photos" in html

    def test_page_contains_footer(self, client, real_photo_id):
        """Public page includes footer with heritage message."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Preserving the visual heritage" in html


class TestPublicPhotoViewer404:
    """404 handling for invalid photo IDs."""

    def test_invalid_photo_id_returns_404_with_friendly_page(self, client):
        """Invalid photo_id returns HTTP 404 with a friendly message."""
        response = client.get("/photo/nonexistent-photo-id-12345")
        assert response.status_code == 404
        html = response.text
        assert "Photo not found" in html
        assert "hasn't been added" in html

    def test_404_page_has_explore_link(self, client):
        """404 page provides a link to explore the archive."""
        response = client.get("/photo/nonexistent-photo-id-12345")
        html = response.text
        assert "Explore the Archive" in html

    def test_404_page_has_branding(self, client):
        """404 page still shows Rhodesli branding."""
        response = client.get("/photo/nonexistent-photo-id-12345")
        html = response.text
        assert "Rhodesli" in html


class TestPublicPhotoViewerContent:
    """Content rendering tests for photos with real data."""

    def test_photo_image_rendered(self, client, real_photo_id):
        """The photo image is rendered on the page."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "photo-hero" in html
        assert "<img" in html.lower()

    def test_face_overlays_present(self, client, real_photo_id):
        """Face overlay divs are rendered for detected faces."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Face overlays use percentage positioning
        assert "left:" in html
        assert "top:" in html

    def test_person_cards_section(self, client, real_photo_id):
        """Person cards section is rendered."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "People in this photo" in html or "Person in this photo" in html

    def test_face_count_display(self, client, real_photo_id):
        """Face count is displayed below the photo."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "detected" in html
        assert "identified" in html

    def test_overlay_legend_present(self, client, real_photo_id):
        """Overlay legend markup is present (may be hidden for non-admin)."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Identified" in html
        # "Unidentified" appears in legend and/or face labels — may not be
        # present if the test photo has all faces identified
        assert "face-overlay-legend-public" in html or "Unidentified" in html

    def test_heritage_archive_in_title(self, client, real_photo_id):
        """Page title includes Heritage Archive."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Heritage Archive" in html

    def test_cta_section_for_unidentified(self, client, real_photo_id):
        """CTA section shown when there are unidentified faces."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Most photos have unidentified faces
        if "Do you recognize someone" in html:
            assert "I Can Help Identify" in html
            assert "Browse All Photos" in html

    def test_cta_links_to_skipped_section(self, client, real_photo_id):
        """'I Can Help Identify' CTA links to Help Identify section, not inbox."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        if "I Can Help Identify" in html:
            # Should link to skipped section (Help Identify), not to_review (inbox)
            assert "section=skipped" in html
            assert "section=to_review" not in html or "section=skipped" in html


class TestPhotoCarousel:
    """Photo carousel navigation — prev/next within collection."""

    def test_nav_arrows_present(self, client, real_photo_id):
        """Photo page shows carousel navigation when in a collection."""
        if not real_photo_id:
            pytest.skip("No embeddings available")

        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Should have at least one nav arrow (prev or next)
        has_prev = 'title="Previous photo"' in html
        has_next = 'title="Next photo"' in html
        assert has_prev or has_next, "Photo in collection should have at least one nav arrow"

    def test_position_indicator(self, client, real_photo_id):
        """Photo page shows 'Photo X of Y' position indicator."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        import re

        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Should have position indicator like "Photo 1 of 108"
        position = re.findall(r"Photo \d+ of \d+", html)
        assert len(position) > 0, "Should show photo position in collection"

    def test_keyboard_navigation_script(self, client, real_photo_id):
        """Keyboard arrow keys navigate between photos."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "ArrowLeft" in html or "ArrowRight" in html, "Should include keyboard navigation for arrow keys"

    def test_collection_link_visible(self, client, real_photo_id):
        """Collection name is a clickable link."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        import re

        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        collection_links = re.findall(r'href="/collection/[^"]+"', html)
        assert len(collection_links) > 0, "Collection name should link to collection page"


class TestFaceClickBehavior:
    """Regression: face clicks navigate to person/identify pages, not circular scroll."""

    def test_overlay_links_to_person_or_identify(self, client, real_photo_id):
        """Face overlays link to /person/{id} or /identify/{id}, not scroll to card."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        import re

        html = _render_photo_page_html(real_photo_id)
        # Overlays should be <a> tags with person or identify hrefs
        overlay_links = re.findall(
            r'<a[^>]*href="(/person/[^"]+|/identify/[^"]+)"[^>]*class="[^"]*face-overlay-box', html
        )
        # Face overlays require photo dimensions (read from filesystem or cached in photo_index).
        # In worktrees without raw_photos/, dimensions may be 0x0 so no overlays render.
        # Check for actual overlay elements (not just CSS class references in <style>)
        has_overlay_elements = bool(re.search(r'class="[^"]*face-overlay-box[^"]*"[^>]*style="left:', html))
        if not has_overlay_elements:
            pytest.skip("No face overlays rendered (photo dimensions unavailable)")
        assert len(overlay_links) > 0, "Face overlays should link to /person/ or /identify/"

    def test_no_circular_scroll_behavior(self, client, real_photo_id):
        """No scroll-to-element behavior between overlays and cards."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        html = _render_photo_page_html(real_photo_id)
        # Should NOT have hyperscript scroll-to references
        assert "go to #person-" not in html, "Overlay should not scroll to person card"
        assert "go to #overlay-" not in html, "Card should not scroll to overlay"

    def test_person_cards_link_to_person_or_identify(self, client, real_photo_id):
        """Person cards below photo link to /person/{id} or /identify/{id}."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        import re

        html = _render_photo_page_html(real_photo_id)
        card_links = re.findall(r'<a[^>]*href="(/person/[^"]+|/identify/[^"]+)"[^>]*class="no-underline', html)
        assert len(card_links) > 0, "Person cards should link to /person/ or /identify/"


class TestFaceOverlayAlignment:
    """Regression: face overlays must be positioned relative to the image, not padded container."""

    def test_overlay_container_is_relative(self, client, real_photo_id):
        """The div wrapping image + overlays must have position:relative so
        percentage-based overlay positioning is relative to the image bounds,
        not the outer padded container (padding-top: 1.5rem caused misalignment)."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        html = _render_photo_page_html(real_photo_id)
        import re

        # The front-side div wrapping the image and face overlays must be relative
        # It should NOT depend on photo-hero-container (which has padding)
        # Find the div that contains both photo-hero img and face-overlay-box
        # The structure is: <div class="relative">...<img class="photo-hero...">...face-overlay-box...</div>
        pattern = r'<div\s+class="[^"]*relative[^"]*"[^>]*>\s*<img[^>]*photo-hero'
        assert re.search(pattern, html), "Front-side div wrapping image + overlays must have 'relative' class"

    def test_no_padding_on_overlay_container(self, client, real_photo_id):
        """The immediate overlay container must not have padding that would offset overlays."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        html = _render_photo_page_html(real_photo_id)
        # photo-hero-container has padding — overlays must NOT be direct children of it
        # They should be inside an inner relative div
        import re

        # Check that face-overlay-box elements appear inside a <div class="...relative...">
        # that is NOT the photo-hero-container
        overlay_pattern = re.search(r'<div class="([^"]*relative[^"]*)"[^>]*>\s*<img[^>]*photo-hero', html)
        assert overlay_pattern, "Overlays must be inside a relative div wrapping the image"
        container_classes = overlay_pattern.group(1)
        assert "photo-hero-container" not in container_classes, (
            "Overlay container must not be photo-hero-container (it has padding that misaligns overlays)"
        )


class TestPublicPhotoViewerPartialUnchanged:
    """The /photo/{id}/partial route should still work for HTMX modal injection."""

    def test_partial_route_still_works(self, client, real_photo_id):
        """Partial route returns content for HTMX injection."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}/partial", headers={"HX-Request": "true"})
        assert response.status_code == 200
        html = response.text
        # Partial should contain the photo viewer content
        assert "photo-viewer" in html or "<img" in html.lower()


class TestUX103BackNavigation:
    """UX-103: Back navigation — photo page must not be a dead end."""

    def test_back_to_photos_link_present(self, client, real_photo_id):
        """Photo page has a 'Back to Photos' breadcrumb link."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'data-testid="back-to-photos"' in html
        assert "Back to Photos" in html
        assert 'href="/photos"' in html

    def test_breadcrumb_bar_present(self, client, real_photo_id):
        """Photo page has a breadcrumb navigation bar."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'data-testid="photo-breadcrumb"' in html

    def test_breadcrumb_includes_collection(self, client, real_photo_id):
        """Breadcrumb includes collection link when photo has a collection."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        import re

        # Photo should have a collection, breadcrumb should link to it
        collection_links = re.findall(r'href="/collection/[^"]+"', html)
        assert len(collection_links) > 0, "Breadcrumb should include collection link"

    def test_mobile_hamburger_menu_present(self, client, real_photo_id):
        """Photo page has a mobile hamburger menu (via _public_page_nav)."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "mobile-nav-overlay" in html, "Photo page should use _public_page_nav with mobile menu"

    def test_back_to_photos_visible_on_mobile(self, client, real_photo_id):
        """Back to Photos link is visible on all screen sizes (not hidden sm:flex)."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        import re

        # The breadcrumb bar should NOT have 'hidden' class (should be visible on mobile)
        breadcrumb = re.search(r'data-testid="photo-breadcrumb"[^>]*class="([^"]*)"', html)
        if breadcrumb:
            assert "hidden" not in breadcrumb.group(1), "Breadcrumb bar should be visible on mobile"


class TestUX103MetadataOverlay:
    """UX-103: Metadata overlay on photo hero image."""

    def test_metadata_overlay_present(self, client, real_photo_id):
        """Photo page has a metadata overlay on the hero image."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'data-testid="photo-metadata-overlay"' in html

    def test_metadata_overlay_shows_face_count(self, client, real_photo_id):
        """Metadata overlay shows face identification count."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'data-testid="photo-overlay-faces"' in html

    def test_metadata_overlay_shows_collection(self, client, real_photo_id):
        """Metadata overlay shows collection name."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'data-testid="photo-overlay-collection"' in html

    def test_photo_hero_has_group_class(self, client, real_photo_id):
        """Photo hero container has 'group' class for hover-reveal overlay."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        import re

        # The div wrapping the photo and overlays should have 'group' class
        # for hover effects on the metadata overlay
        pattern = r'class="[^"]*relative[^"]*group[^"]*"'
        assert re.search(pattern, html), "Photo container should have 'group' class for hover overlay"

    def test_anonymous_sees_metadata_overlay(self, client, real_photo_id, auth_enabled, no_user):
        """Anonymous users can see the metadata overlay."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'data-testid="photo-metadata-overlay"' in html

    def test_keyboard_navigation_still_works(self, client, real_photo_id):
        """Keyboard navigation (arrow keys) still works after UX-103 changes."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "ArrowLeft" in html or "ArrowRight" in html, "Keyboard navigation should still be present"


class TestUX103FaceOverlayToggle:
    """UX-103: Face overlay toggle still works after changes."""

    def test_face_overlay_toggle_button_present(self, client, real_photo_id):
        """Face overlay toggle button is present on photo page."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert 'data-action="toggle-face-overlays-public"' in html

    def test_share_button_still_present(self, client, real_photo_id):
        """Share button is still present after UX-103 changes."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Share This Photo" in html

    def test_download_button_still_present(self, client, real_photo_id):
        """Download button is still present after UX-103 changes."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Download" in html


class TestPhotoInlineEdit:
    """Admin inline editing for photo collection/source on photo page."""

    def test_admin_sees_inline_edit(self, client, real_photo_id, auth_disabled):
        """Admin (auth disabled) sees inline edit form on photo page."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert 'data-testid="photo-inline-edit"' in response.text

    def test_inline_edit_has_collection_input(self, client, real_photo_id, auth_disabled):
        """Inline edit has collection input field."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'name="collection"' in response.text

    def test_inline_edit_has_source_input(self, client, real_photo_id, auth_disabled):
        """Inline edit has source input field."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'name="source"' in response.text

    def test_anonymous_no_inline_edit(self, client, real_photo_id, auth_enabled, no_user):
        """Anonymous users do not see inline edit form."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200
        assert 'data-testid="photo-inline-edit"' not in response.text
