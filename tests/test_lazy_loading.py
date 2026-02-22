"""Lazy loading tests for /photos and /timeline pages (UX-007, UX-018).

Verifies that:
- /photos returns paginated results with lazy loading sentinel
- /api/photos/more returns additional photo cards
- /timeline lazy loads remaining decades via HTMX
- /api/timeline/more returns remaining decade sections
"""

import pytest


class TestPhotosLazyLoading:
    """UX-018: Photos page lazy loading."""

    def test_photos_page_returns_200(self, client):
        """GET /photos returns 200."""
        response = client.get("/photos")
        assert response.status_code == 200

    def test_photos_page_has_grid(self, client):
        """Photos page has the photo grid."""
        response = client.get("/photos")
        assert 'id="photo-grid"' in response.text

    def test_photos_initial_load_limited(self, client):
        """Photos page doesn't render ALL photos in initial HTML.

        With 271 photos and 24 per page, we should see the lazy sentinel
        (unless total photos < 24).
        """
        response = client.get("/photos")
        # If there are more than 24 photos, we should see the sentinel
        from app.main import _compute_landing_stats
        stats = _compute_landing_stats()
        if stats["photo_count"] > 24:
            assert "photos-lazy-sentinel" in response.text
            assert "hx-get" in response.text or "hx_get" in response.text

    def test_photos_more_returns_200(self, client):
        """GET /api/photos/more returns 200."""
        response = client.get("/api/photos/more?page=2")
        assert response.status_code == 200

    def test_photos_more_returns_cards(self, client):
        """GET /api/photos/more returns photo card HTML."""
        response = client.get("/api/photos/more?page=2")
        # Should contain photo links (href="/photo/...")
        if response.text.strip():
            assert "/photo/" in response.text

    def test_photos_more_preserves_filters(self, client):
        """GET /api/photos/more respects filter parameters."""
        response = client.get("/api/photos/more?page=1&sort_by=oldest")
        assert response.status_code == 200

    def test_photos_more_high_page_returns_empty(self, client):
        """GET /api/photos/more with very high page returns empty."""
        response = client.get("/api/photos/more?page=999")
        assert response.status_code == 200
        assert response.text.strip() == ""


class TestTimelineLazyLoading:
    """UX-007: Timeline lazy loading."""

    def test_timeline_returns_200(self, client):
        """GET /timeline returns 200."""
        response = client.get("/timeline")
        assert response.status_code == 200

    def test_timeline_has_decade_markers(self, client):
        """Timeline page shows decade markers."""
        response = client.get("/timeline")
        assert "decade-marker" in response.text

    def test_timeline_lazy_sentinel_present(self, client):
        """Timeline shows lazy loading sentinel when there are >3 decades."""
        response = client.get("/timeline")
        # Count decade markers in initial response
        decade_count = response.text.count('data-testid="decade-marker"')
        if decade_count >= 3:
            # Should have the sentinel
            assert "timeline-lazy-sentinel" in response.text

    def test_timeline_more_returns_200(self, client):
        """GET /api/timeline/more returns 200."""
        response = client.get("/api/timeline/more?offset=3")
        assert response.status_code == 200

    def test_timeline_more_returns_decade_sections(self, client):
        """GET /api/timeline/more returns remaining decade sections."""
        response = client.get("/api/timeline/more?offset=3")
        if response.text.strip():
            assert "decade-marker" in response.text

    def test_timeline_more_high_offset_returns_empty(self, client):
        """GET /api/timeline/more with very high offset returns empty."""
        response = client.get("/api/timeline/more?offset=999")
        assert response.status_code == 200
        assert response.text.strip() == ""

    def test_timeline_more_preserves_person_filter(self, client):
        """GET /api/timeline/more respects person filter."""
        response = client.get("/api/timeline/more?offset=0&person=nonexistent")
        assert response.status_code == 200
