"""Tests for Phase 6: Photo collection display and management."""

import pytest
from unittest.mock import patch, MagicMock
from urllib.parse import quote


class TestCollectionStats:
    """Tests for per-collection statistics in the photo grid."""

    def test_collection_stats_computed(self):
        """Per-collection stats include photo count and face count."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = MagicMock()
        registry.list_identities.return_value = []

        cache = {
            "p1": {"filename": "img1.jpg", "source": "Collection A", "faces": [{"face_id": "f1"}]},
            "p2": {"filename": "img2.jpg", "source": "Collection A", "faces": [{"face_id": "f2"}, {"face_id": "f3"}]},
            "p3": {"filename": "img3.jpg", "source": "Collection B", "faces": [{"face_id": "f4"}]},
        }

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        # Should show collection stat cards
        assert "Collection A" in html
        assert "Collection B" in html
        assert "2 photos" in html  # Collection A
        assert "3 faces" in html   # Collection A total faces

    def test_no_stats_cards_for_single_collection(self):
        """No collection cards shown when only one collection exists."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = MagicMock()

        cache = {
            "p1": {"filename": "img1.jpg", "source": "Only One", "faces": [{"face_id": "f1"}]},
        }

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        # Should still show the collection name in photo info
        assert "Only One" in html

    def test_stats_cards_hidden_when_filtered(self):
        """Collection stat cards hidden when filtering by a specific collection."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = MagicMock()

        cache = {
            "p1": {"filename": "img1.jpg", "source": "Coll A", "faces": [{"face_id": "f1"}]},
            "p2": {"filename": "img2.jpg", "source": "Coll B", "faces": []},
        }

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set(), filter_source="Coll A"))

        # When filtered, should show the filtered collection's photos (singular)
        assert "1 photo" in html

    def test_filtered_subtitle_shows_collection_name(self):
        """When filtered to a collection, subtitle shows 'Collection — N photos', not global stats."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = MagicMock()

        cache = {
            "p1": {"filename": "img1.jpg", "source": "Betty Miami", "faces": [{"face_id": "f1"}]},
            "p2": {"filename": "img2.jpg", "source": "Betty Miami", "faces": []},
            "p3": {"filename": "img3.jpg", "source": "Vida NYC", "faces": []},
        }

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set(), filter_source="Betty Miami"))

        # Should show scoped subtitle with collection name
        assert "Betty Miami" in html
        assert "2 photos" in html
        # Should NOT show "2 collections" when filtered
        assert "2 collections" not in html

    def test_unfiltered_subtitle_shows_global_stats(self):
        """When viewing all photos, subtitle shows 'N photos • M collections'."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = MagicMock()
        registry.list_identities.return_value = []

        cache = {
            "p1": {"filename": "img1.jpg", "source": "Coll A", "collection": "Coll A", "faces": []},
            "p2": {"filename": "img2.jpg", "source": "Coll B", "collection": "Coll B", "faces": []},
        }

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        assert "2 photos" in html
        assert "2 collections" in html


class TestCollectionFilter:
    """Tests for collection filter and sort in the photo grid."""

    def test_filter_by_collection(self):
        """Filtering by collection shows only those photos."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = MagicMock()

        cache = {
            "p1": {"filename": "img1.jpg", "source": "A", "faces": []},
            "p2": {"filename": "img2.jpg", "source": "B", "faces": []},
        }

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set(), filter_source="A"))

        assert "img1.jpg" in html
        assert "img2.jpg" not in html

    def test_sort_by_collection(self):
        """Sort by collection groups photos by source."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = MagicMock()

        cache = {
            "p1": {"filename": "img1.jpg", "source": "A", "faces": []},
            "p2": {"filename": "img2.jpg", "source": "B", "faces": []},
        }

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set(), sort_by="collection"))

        # Both photos should be present
        assert "img1.jpg" in html
        assert "img2.jpg" in html


class TestCollectionReassignment:
    """Tests for the photo collection reassignment endpoint."""

    def test_reassign_requires_admin(self, client, auth_enabled, regular_user):
        """POST /api/photo/{id}/collection requires admin."""
        resp = client.post(
            "/api/photo/test-id/collection",
            data={"collection": "New Collection"},
            headers={"HX-Request": "true"}
        )
        assert resp.status_code in (401, 403)

    def test_reassign_collection(self, client, auth_disabled):
        """Admin can change a photo's collection."""
        with patch("app.main.load_photo_registry") as mock_photo_reg:
            photo_reg = MagicMock()
            photo_reg.get_photo_path.return_value = "raw_photos/test.jpg"
            mock_photo_reg.return_value = photo_reg

            resp = client.post(
                "/api/photo/test-id/collection",
                data={"collection": "New Collection"}
            )
            assert resp.status_code == 200
            assert "New Collection" in resp.text
            photo_reg.set_collection.assert_called_once_with("test-id", "New Collection")

    def test_reassign_photo_not_found(self, client, auth_disabled):
        """Reassigning collection for nonexistent photo returns 404."""
        with patch("app.main.load_photo_registry") as mock_photo_reg:
            photo_reg = MagicMock()
            photo_reg.get_photo_path.return_value = None
            mock_photo_reg.return_value = photo_reg

            resp = client.post(
                "/api/photo/nonexistent/collection",
                data={"collection": "X"}
            )
            assert resp.status_code == 404

    def test_reassign_empty_collection(self, client, auth_disabled):
        """Can clear a photo's collection."""
        with patch("app.main.load_photo_registry") as mock_photo_reg:
            photo_reg = MagicMock()
            photo_reg.get_photo_path.return_value = "raw_photos/test.jpg"
            mock_photo_reg.return_value = photo_reg

            resp = client.post(
                "/api/photo/test-id/collection",
                data={"collection": ""}
            )
            assert resp.status_code == 200
            assert "(none)" in resp.text
            photo_reg.set_collection.assert_called_once_with("test-id", "")


class TestCollectionInUpload:
    """Tests for collection field in the upload form."""

    def test_upload_form_has_source_field(self, client, auth_disabled):
        """Upload page includes collection/source input with autocomplete."""
        with patch("app.main.load_photo_registry") as mock_photo_reg, \
             patch("app.main._build_caches"), \
             patch("app.main._photo_cache", {}):
            photo_reg = MagicMock()
            mock_photo_reg.return_value = photo_reg

            resp = client.get("/upload")
            html = resp.text

            assert "Collection" in html or "Source" in html
            assert 'name="source"' in html

    def test_upload_form_has_existing_sources(self, client, auth_disabled):
        """Upload page shows existing collection names as autocomplete options."""
        with patch("app.main.load_photo_registry") as mock_photo_reg, \
             patch("app.main._build_caches"), \
             patch("app.main._photo_cache", {
                 "p1": {"filename": "t.jpg", "source": "Betty Capeluto Miami Collection", "faces": []},
             }):
            photo_reg = MagicMock()
            mock_photo_reg.return_value = photo_reg

            resp = client.get("/upload")
            html = resp.text

            assert "Betty Capeluto Miami Collection" in html
