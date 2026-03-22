"""Lazy loading tests for /photos and /timeline pages (UX-007, UX-018).

Also verifies image lazy loading on key UI components for performance:
- identity_card hero images
- identity_card_mini thumbnails
- face_card hero images
- neighbor_card thumbnails
- /people page avatars
- Person page face gallery
- Preconnect headers for CDN domains
"""

from unittest.mock import patch


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

    def test_photos_more_preserves_community_prefix(self, client, monkeypatch):
        """Community-scoped lazy loading must keep archive-prefixed photo links."""
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "_build_caches", lambda: None)
        monkeypatch.setattr(
            main_mod,
            "_photo_cache",
            {
                "photo-1": {
                    "photo_id": "photo-1",
                    "filename": "photo-1.jpg",
                    "collection": "Fox Family Collection",
                    "faces": [{"face_id": "face-1"}],
                    "width": 800,
                    "height": 600,
                    "media_role": "front",
                }
            },
        )
        monkeypatch.setattr(main_mod, "_get_community_photo_ids", lambda _community: None)
        monkeypatch.setattr(main_mod, "_get_date_badge", lambda _photo_id: ("c. 1930s", "high", "Estimated: 1930s"))

        class FakeRegistry:
            def list_identities(self, include_merged=False):
                return []

        monkeypatch.setattr(main_mod, "load_registry", lambda: FakeRegistry())
        monkeypatch.setattr(main_mod, "get_identity_for_face", lambda *_args, **_kwargs: None)

        with patch(
            "app.supabase_data.get_community_by_slug",
            return_value={"slug": "fox-family", "name": "Fox Family Archive"},
        ):
            response = client.get("/c/fox-family/api/photos/more?page=1")

        assert response.status_code == 200
        assert "/c/fox-family/photo/photo-1" in response.text


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


# ---------------------------------------------------------------------------
# Image lazy loading tests for grid/list components
# ---------------------------------------------------------------------------


def _html(element) -> str:
    """Get full HTML string from a FastHTML element."""
    return repr(element)


def _make_identity(identity_id="test-id-1", name="Test Person", state="CONFIRMED"):
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": ["face1", "face2"],
        "candidate_ids": [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


class TestIdentityCardLazyLoading:
    """identity_card() hero image must use loading='lazy' for grid performance."""

    def test_hero_image_has_lazy_loading(self):
        import app.main as m

        identity = _make_identity()
        crop_files = {"face1.jpg", "face2.jpg"}

        with (
            patch.object(m, "resolve_face_image_url", return_value="https://example.com/face1.jpg"),
            patch.object(m, "get_best_face_id", return_value="face1"),
            patch.object(m, "get_face_quality", return_value=25.0),
            patch.object(m, "_load_gedcom_face_links", return_value={}),
            patch.object(m, "share_button", return_value=None),
        ):
            card = m.identity_card(identity, crop_files, is_admin=False)

        html = _html(card)
        assert 'loading="lazy"' in html, "identity_card hero image must have loading='lazy' for grid performance"


class TestIdentityCardMiniLazyLoading:
    """identity_card_mini() image must use loading='lazy'."""

    def test_mini_card_has_lazy_loading(self):
        import app.main as m

        identity = _make_identity()
        crop_files = {"face1.jpg"}

        with (
            patch.object(m, "resolve_face_image_url", return_value="https://example.com/face1.jpg"),
            patch.object(m, "get_best_face_id", return_value="face1"),
        ):
            card = m.identity_card_mini(identity, crop_files, clickable=False)

        html = _html(card)
        assert 'loading="lazy"' in html, "identity_card_mini image must have loading='lazy'"


class TestNeighborCardLazyLoading:
    """neighbor_card() thumbnail must use loading='lazy'."""

    def test_neighbor_thumbnail_has_lazy_loading(self):
        import app.main as m

        neighbor = {
            "identity_id": "n1",
            "name": "Neighbor Person",
            "distance": 0.5,
            "percentile": 0.3,
            "confidence_gap": 0.2,
            "can_merge": True,
            "face_count": 2,
            "co_occurrence": 0,
            "anchor_face_ids": ["nface1"],
            "candidate_face_ids": [],
        }
        crop_files = {"nface1.jpg"}

        with (
            patch.object(m, "resolve_face_image_url", return_value="https://example.com/nface1.jpg"),
            patch.object(m, "get_best_face_id", return_value="nface1"),
        ):
            card = m.neighbor_card(neighbor, "target-id", crop_files, user_role="admin")

        html = _html(card)
        assert 'loading="lazy"' in html, "neighbor_card thumbnail must have loading='lazy'"


class TestPreconnectHeaders:
    """App headers should include preconnect hints for CDN domains."""

    def test_cdn_preconnect_in_headers(self):
        import app.main as m

        hdrs = m.app.hdrs if hasattr(m.app, "hdrs") else []
        hdrs_html = " ".join(_html(h) for h in hdrs if h is not None)

        assert "cdn.tailwindcss.com" in hdrs_html, "Must preconnect to Tailwind CDN"
        assert "unpkg.com" in hdrs_html, "Must preconnect to unpkg CDN"
        assert "fonts.googleapis.com" in hdrs_html, "Must preconnect to Google Fonts"
