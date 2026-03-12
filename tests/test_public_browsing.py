"""Tests for public /photos and /people browsing pages.

Tests cover:
- Public access without authentication
- Photo grid renders with correct structure
- People grid renders with identified persons
- Collection filter works
- Sort options work
- Admin controls NOT visible
- Cross-links between pages work
- OG meta tags present
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestPublicPhotosPage:
    """The /photos page is publicly accessible."""

    def test_returns_200(self, client):
        """Anyone can access /photos."""
        response = client.get("/photos")
        assert response.status_code == 200

    def test_returns_200_with_auth_enabled(self, client, auth_enabled, no_user):
        """Anonymous users can access /photos with auth enabled."""
        response = client.get("/photos")
        assert response.status_code == 200

    def test_contains_rhodesli_branding(self, client):
        """Page has Rhodesli branding."""
        response = client.get("/photos")
        assert "Rhodesli" in response.text

    def test_contains_photos_heading(self, client):
        """Page has Photos heading."""
        response = client.get("/photos")
        assert "Photos" in response.text

    def test_photos_link_to_photo_viewer(self, client):
        """Photo thumbnails link to /photo/{id}."""
        response = client.get("/photos")
        html = response.text
        # Photos should link to the public viewer
        assert "/photo/" in html

    def test_no_admin_controls(self, client):
        """No admin-only controls visible (select mode, bulk actions)."""
        response = client.get("/photos")
        html = response.text
        # Admin-only elements should not appear
        assert "Select" not in html or 'data-action="toggle-photo-select"' not in html
        assert "Mark Processed" not in html

    def test_collection_filter(self, client):
        """Collection filter dropdown is present."""
        response = client.get("/photos")
        assert "All Collections" in response.text

    def test_sort_options(self, client):
        """Sort dropdown is present."""
        response = client.get("/photos")
        assert "Upload Date (Newest)" in response.text

    def test_people_nav_link(self, client):
        """Page has link to /people."""
        response = client.get("/photos")
        assert 'href="/people"' in response.text

    def test_og_meta_tags(self, client):
        """OG meta tags present."""
        response = client.get("/photos")
        assert "og:title" in response.text

    def test_community_photos_preserve_prefixed_photo_links(self, client, monkeypatch):
        """Community-scoped /photos must keep photo/detail links inside that archive."""
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
        monkeypatch.setattr(main_mod, "_get_decade_counts", lambda: {})
        monkeypatch.setattr(main_mod, "_get_tag_counts", lambda: {})
        monkeypatch.setattr(main_mod, "_get_date_badge", lambda _photo_id: ("c. 1930s", "high", "Estimated: 1930s"))

        class FakeRegistry:
            pass

        monkeypatch.setattr(main_mod, "load_registry", lambda: FakeRegistry())
        monkeypatch.setattr(main_mod, "get_identity_for_face", lambda *_args, **_kwargs: None)

        with patch(
            "app.supabase_data.get_community_by_slug",
            return_value={"slug": "fox-family", "name": "Fox Family Archive"},
        ):
            response = client.get("/c/fox-family/photos")

        assert response.status_code == 200
        assert 'href="/c/fox-family/photo/photo-1"' in response.text
        assert 'href="/c/fox-family/"' in response.text


class TestPublicPeoplePage:
    """The /people page is publicly accessible."""

    def test_returns_200(self, client):
        """Anyone can access /people."""
        response = client.get("/people")
        assert response.status_code == 200

    def test_returns_200_with_auth_enabled(self, client, auth_enabled, no_user):
        """Anonymous users can access /people with auth enabled."""
        response = client.get("/people")
        assert response.status_code == 200

    def test_contains_rhodesli_branding(self, client):
        """Page has Rhodesli branding."""
        response = client.get("/people")
        assert "Rhodesli" in response.text

    def test_contains_people_heading(self, client):
        """Page has People heading."""
        response = client.get("/people")
        assert "People" in response.text

    def test_people_link_to_person_pages(self, client):
        """Person cards link to /person/{id}."""
        response = client.get("/people")
        html = response.text
        assert "/person/" in html

    def test_sort_options(self, client):
        """Sort dropdown is present."""
        response = client.get("/people")
        assert "A-Z" in response.text

    def test_photos_nav_link(self, client):
        """Page has link to /photos."""
        response = client.get("/people")
        assert 'href="/photos"' in response.text

    def test_og_meta_tags(self, client):
        """OG meta tags present."""
        response = client.get("/people")
        assert "og:title" in response.text

    def test_shows_identified_people_only(self, client):
        """Only confirmed, named identities appear."""
        response = client.get("/people")
        html = response.text
        # Should not show "Unidentified Person" entries
        assert "Unidentified Person" not in html

    def test_cta_present(self, client):
        """Call to action for helping identify people."""
        response = client.get("/people")
        assert "Browse Photos" in response.text

    def test_footer_present(self, client):
        """Footer with heritage branding."""
        response = client.get("/people")
        assert "Heritage Archive" in response.text
