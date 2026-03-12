"""Tests for the public shareable photo viewer at /photo/{photo_id}.

Pruned: CSS class assertions (group class, hidden class checks, relative
container regex). Kept: access control, 404 handling, content rendering,
functional navigation, admin inline edit.
"""

import re
import pytest
from starlette.testclient import TestClient
from unittest.mock import MagicMock, patch

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


class TestPublicPhotoViewerAccess:
    """Public photo viewer requires no authentication."""

    def test_public_access_returns_200(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200

    def test_public_access_with_auth_enabled(self, client, real_photo_id, auth_enabled, no_user):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert response.status_code == 200

    def test_page_contains_rhodesli_branding(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "Rhodesli" in response.text


class TestPublicPhotoViewer404:
    """404 handling for invalid photo IDs."""

    def test_invalid_photo_id_returns_404(self, client):
        response = client.get("/photo/nonexistent-photo-id-12345")
        assert response.status_code == 404
        assert "Photo not found" in response.text

    def test_404_page_has_explore_link(self, client):
        response = client.get("/photo/nonexistent-photo-id-12345")
        assert "Explore the Archive" in response.text


class TestPublicPhotoViewerContent:
    """Content rendering tests for photos with real data."""

    def test_photo_image_rendered(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "<img" in response.text.lower()

    def test_person_cards_section(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "People in this photo" in response.text or "Person in this photo" in response.text

    def test_face_count_display(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "detected" in response.text


class TestPhotoCarousel:
    """Photo carousel navigation."""

    def test_nav_arrows_present(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        has_prev = 'title="Previous photo"' in html
        has_next = 'title="Next photo"' in html
        assert has_prev or has_next

    def test_position_indicator(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        position = re.findall(r"Photo \d+ of \d+", response.text)
        assert len(position) > 0

    def test_collection_link_visible(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        collection_links = re.findall(r'href="/collection/[^"]+"', response.text)
        assert len(collection_links) > 0

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch(
        "app.main._photo_cache",
        {
            "photo-1": {
                "photo_id": "photo-1",
                "filename": "a.jpg",
                "collection": "Vida Capeluto NYC Collection",
                "source": "Vida Capeluto NYC Collection",
                "faces": [],
            },
            "photo-2": {
                "photo_id": "photo-2",
                "filename": "b.jpg",
                "collection": "Vida Capeluto NYC Collection",
                "source": "Vida Capeluto NYC Collection",
                "faces": [],
            },
        },
    )
    @patch("app.main._public_nav_links", return_value=[])
    @patch("app.main._public_page_nav", return_value=())
    @patch("app.main._admin_bar", return_value=())
    @patch("app.main._build_upload_provenance_line", return_value=None)
    @patch("app.main._get_date_badge", return_value=("", "low", ""))
    @patch("app.main._build_ai_analysis_section", return_value=None)
    @patch("app.main._build_face_alignment_section", return_value=None)
    @patch("app.main._build_photo_date_badge", return_value=None)
    def test_standalone_photo_page_includes_touch_swipe_navigation(
        self,
        mock_date_badge,
        mock_alignment,
        mock_ai,
        mock_date_meta,
        mock_upload_line,
        mock_admin_bar,
        mock_public_nav,
        mock_nav_links,
        mock_reg,
        mock_dim,
        mock_meta,
    ):
        del (
            mock_date_badge,
            mock_alignment,
            mock_ai,
            mock_date_meta,
            mock_upload_line,
            mock_admin_bar,
            mock_public_nav,
            mock_nav_links,
            mock_dim,
        )
        from app.main import public_photo_page, to_xml

        mock_reg.return_value = MagicMock()
        mock_meta.return_value = {
            "photo_id": "photo-1",
            "filename": "a.jpg",
            "collection": "Vida Capeluto NYC Collection",
            "source": "Vida Capeluto NYC Collection",
            "faces": [],
        }

        html = to_xml(public_photo_page("photo-1", community_slug="rhodes"))

        assert "touchstart" in html
        assert "touchend" in html
        assert ".photo-hero-container" in html
        assert "window.location.href = '/photo/photo-2'" in html


class TestFaceClickBehavior:
    """Face clicks navigate to person/identify pages."""

    def test_person_cards_link_to_person_or_identify(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        import app.main as main

        # Reset ALL caches so data is loaded fresh from disk (xdist isolation)
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._photo_id_aliases = None
        main._face_data_cache = None
        main._crop_files_cache = None
        main._skipped_neighbor_cache = None
        main._photo_registry_cache = None
        main._discovery_cache = None

        c = TestClient(main.app)
        html = c.get(f"/photo/{real_photo_id}").text
        card_links = re.findall(r'<a[^>]*href="(/person/[^"]+|/identify/[^"]+)"[^>]*class="no-underline', html)
        assert len(card_links) > 0


class TestUX103BackNavigation:
    """UX-103: Back navigation."""

    def test_back_to_photos_link_present(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert "Back to Photos" in response.text
        assert 'href="/photos"' in response.text


class TestUX103MetadataOverlay:
    """UX-103: Metadata overlay on photo hero image."""

    def test_metadata_overlay_present(self, client, real_photo_id):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'data-testid="photo-metadata-overlay"' in response.text

    def test_anonymous_sees_metadata_overlay(self, client, real_photo_id, auth_enabled, no_user):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'data-testid="photo-metadata-overlay"' in response.text


class TestPhotoInlineEdit:
    """Admin inline editing for photo collection/source."""

    def test_admin_sees_inline_edit(self, client, real_photo_id, auth_disabled):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'data-testid="photo-inline-edit"' in response.text

    def test_anonymous_no_inline_edit(self, client, real_photo_id, auth_enabled, no_user):
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        assert 'data-testid="photo-inline-edit"' not in response.text


class TestSession100PhotoWorkflow:
    """Session 100 dense multi-face and context-preserving workflow regressions."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.load_photo_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={"crop-set"})
    @patch("app.main.resolve_face_image_url", side_effect=lambda fid, _crops=None: f"/crops/{fid}.jpg")
    @patch("app.main._public_nav_links", return_value=[])
    @patch("app.main._public_page_nav", return_value=())
    @patch("app.main._admin_bar", return_value=())
    @patch("app.main._build_upload_provenance_line", return_value=None)
    @patch("app.main._get_date_badge", return_value=("", "low", ""))
    @patch("app.main._build_ai_analysis_section", return_value=None)
    @patch("app.main._build_face_alignment_section", return_value=None)
    @patch("app.main._build_photo_date_badge", return_value=None)
    def test_dense_multi_face_photo_uses_grid_and_keeps_person_context(
        self,
        mock_date_badge,
        mock_photo_badge,
        mock_alignment,
        mock_ai,
        mock_upload_line,
        mock_admin_bar,
        mock_public_nav,
        mock_nav_links,
        mock_crop_url,
        mock_crop_files,
        mock_get_id,
        mock_photo_reg,
        mock_reg,
        mock_dim,
        mock_meta,
    ):
        del (
            mock_date_badge,
            mock_photo_badge,
            mock_alignment,
            mock_ai,
            mock_upload_line,
            mock_admin_bar,
            mock_public_nav,
            mock_nav_links,
            mock_crop_url,
            mock_crop_files,
            mock_dim,
        )
        from app.main import public_photo_page, to_xml

        faces = [{"face_id": f"face-{i}", "bbox": [10 + i * 15, 10, 70 + i * 15, 80]} for i in range(7)]
        mock_meta.return_value = {
            "photo_id": "photo-1",
            "filename": "dense.jpg",
            "faces": faces,
            "collection": "Fox Collection",
            "source": "Fox Collection",
        }

        def _identity_for_face(_registry, face_id):
            idx = int(face_id.split("-")[1])
            if idx == 0:
                return {"identity_id": "context-1", "name": "Roland Fox", "state": "CONFIRMED"}
            if idx < 3:
                return {"identity_id": f"person-{idx}", "name": f"Person {idx}", "state": "CONFIRMED"}
            return {"identity_id": f"unknown-{idx}", "name": f"Unidentified Person {idx}", "state": "INBOX"}

        mock_get_id.side_effect = _identity_for_face

        registry = MagicMock()
        registry.get_identity.return_value = {
            "identity_id": "context-1",
            "name": "Roland Fox",
            "state": "CONFIRMED",
            "anchor_ids": [f"face-{i}" for i in range(3)],
            "candidate_ids": [],
        }
        mock_reg.return_value = registry

        photo_registry = MagicMock()
        photo_registry.get_photos_for_faces.return_value = ["photo-1"]
        mock_photo_reg.return_value = photo_registry

        result = public_photo_page(
            "photo-1",
            identity_id="context-1",
            sort_by="date_asc",
            user=None,
            is_admin=True,
            community_slug="fox-family",
        )
        html = to_xml(result)

        assert 'data-testid="photo-people-grid"' in html
        assert "/c/fox-family/photo/photo-1?seq=1" in html
        assert "seq=1" in html
        assert "identity_id=context-1" in html
        assert "sort_by=date_asc" in html
        assert "Back to Roland Fox" in html
        assert "/c/fox-family/identify/unknown-3" in html
        assert 'href="/c/fox-family/photos"' in html
        assert 'href="/c/fox-family/people"' in html
        assert "Viewing" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.load_photo_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={"crop-set"})
    @patch("app.main.resolve_face_image_url", side_effect=lambda fid, _crops=None: f"/crops/{fid}.jpg")
    @patch("app.main._public_nav_links", return_value=[])
    @patch("app.main._public_page_nav", return_value=())
    @patch("app.main._admin_bar", return_value=())
    @patch("app.main._build_upload_provenance_line", return_value=None)
    @patch("app.main._get_date_badge", return_value=("", "low", ""))
    @patch("app.main._build_ai_analysis_section", return_value=None)
    @patch("app.main._build_face_alignment_section", return_value=None)
    @patch("app.main._build_photo_date_badge", return_value=None)
    def test_photo_people_cards_surface_contested_state(
        self,
        mock_date_badge,
        mock_photo_badge,
        mock_alignment,
        mock_ai,
        mock_upload_line,
        mock_admin_bar,
        mock_public_nav,
        mock_nav_links,
        mock_crop_url,
        mock_crop_files,
        mock_get_id,
        mock_photo_reg,
        mock_reg,
        mock_dim,
        mock_meta,
    ):
        del (
            mock_date_badge,
            mock_photo_badge,
            mock_alignment,
            mock_ai,
            mock_upload_line,
            mock_admin_bar,
            mock_public_nav,
            mock_nav_links,
            mock_crop_url,
            mock_crop_files,
            mock_photo_reg,
            mock_dim,
        )
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = {
            "photo_id": "photo-1",
            "filename": "dense.jpg",
            "faces": [
                {"face_id": "face-0", "bbox": [10, 10, 70, 80]},
                {"face_id": "face-1", "bbox": [90, 10, 150, 80]},
            ],
            "collection": "Rhodes Collection",
            "source": "Rhodes Collection",
        }

        def _identity_for_face(_registry, face_id):
            if face_id == "face-0":
                return {"identity_id": "person-0", "name": "Known Person", "state": "CONFIRMED"}
            return {"identity_id": "person-1", "name": "Unidentified Person 863", "state": "CONTESTED"}

        mock_get_id.side_effect = _identity_for_face

        html = to_xml(public_photo_page("photo-1", user=None, is_admin=True, community_slug="rhodes"))

        assert "Contested" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.load_photo_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={"crop-set"})
    @patch("app.main.resolve_face_image_url", side_effect=lambda fid, _crops=None: f"/crops/{fid}.jpg")
    @patch("app.main._public_nav_links", return_value=[])
    @patch("app.main._public_page_nav", return_value=())
    @patch("app.main._admin_bar", return_value=())
    @patch("app.main._build_upload_provenance_line", return_value=None)
    @patch("app.main._get_date_badge", return_value=("", "low", ""))
    @patch("app.main._build_ai_analysis_section", return_value=None)
    @patch("app.main._build_face_alignment_section", return_value=None)
    @patch("app.main._build_photo_date_badge", return_value=None)
    def test_overlapping_face_assignments_surface_conflict_state(
        self,
        mock_date_badge,
        mock_photo_badge,
        mock_alignment,
        mock_ai,
        mock_upload_line,
        mock_admin_bar,
        mock_public_nav,
        mock_nav_links,
        mock_crop_url,
        mock_crop_files,
        mock_get_id,
        mock_photo_reg,
        mock_reg,
        mock_dim,
        mock_meta,
    ):
        del (
            mock_date_badge,
            mock_photo_badge,
            mock_alignment,
            mock_ai,
            mock_upload_line,
            mock_admin_bar,
            mock_public_nav,
            mock_nav_links,
            mock_crop_url,
            mock_crop_files,
            mock_photo_reg,
            mock_dim,
        )
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = {
            "photo_id": "photo-1",
            "filename": "dense.jpg",
            "faces": [
                {"face_id": "face-0", "bbox": [100, 100, 200, 240]},
                {"face_id": "face-1", "bbox": [108, 108, 198, 235]},
            ],
            "collection": "Rhodes Collection",
            "source": "Rhodes Collection",
        }

        def _identity_for_face(_registry, face_id):
            if face_id == "face-0":
                return {"identity_id": "person-0", "name": "Jacob Cohen", "state": "CONFIRMED"}
            return {"identity_id": "person-1", "name": "Caden Franco Sadis", "state": "CONFIRMED"}

        mock_get_id.side_effect = _identity_for_face

        html = to_xml(public_photo_page("photo-1", user=None, is_admin=True, community_slug="rhodes"))

        assert "Potential tag conflicts detected" in html
        assert "Conflict" in html
        assert "Needs review" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.load_photo_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={"crop-set"})
    @patch("app.main.resolve_face_image_url", side_effect=lambda fid, _crops=None: f"/crops/{fid}.jpg")
    @patch("app.main._public_nav_links", return_value=[])
    @patch("app.main._public_page_nav", return_value=())
    @patch("app.main._admin_bar", return_value=())
    @patch("app.main._build_upload_provenance_line", return_value=None)
    @patch("app.main._get_date_badge", return_value=("", "low", ""))
    @patch("app.main._build_ai_analysis_section", return_value=None)
    @patch("app.main._build_face_alignment_section", return_value=None)
    @patch("app.main._build_photo_date_badge", return_value=None)
    def test_context_identity_conflict_surfaces_warning_banner(
        self,
        mock_date_badge,
        mock_photo_badge,
        mock_alignment,
        mock_ai,
        mock_upload_line,
        mock_admin_bar,
        mock_public_nav,
        mock_nav_links,
        mock_crop_url,
        mock_crop_files,
        mock_get_id,
        mock_photo_reg,
        mock_reg,
        mock_dim,
        mock_meta,
    ):
        del (
            mock_date_badge,
            mock_photo_badge,
            mock_alignment,
            mock_ai,
            mock_upload_line,
            mock_admin_bar,
            mock_public_nav,
            mock_nav_links,
            mock_crop_url,
            mock_crop_files,
            mock_photo_reg,
            mock_dim,
        )
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = {
            "photo_id": "photo-1",
            "filename": "dense.jpg",
            "faces": [
                {"face_id": "face-0", "bbox": [100, 100, 200, 240]},
                {"face_id": "face-1", "bbox": [108, 108, 198, 235]},
            ],
            "collection": "Rhodes Collection",
            "source": "Rhodes Collection",
        }

        def _identity_for_face(_registry, face_id):
            if face_id == "face-0":
                return {"identity_id": "context-1", "name": "Jacob Cohen", "state": "CONFIRMED"}
            return {"identity_id": "person-1", "name": "Caden Franco Sadis", "state": "CONFIRMED"}

        mock_get_id.side_effect = _identity_for_face

        registry = MagicMock()
        registry.get_identity.return_value = {
            "identity_id": "context-1",
            "name": "Jacob Cohen",
            "state": "CONFIRMED",
            "anchor_ids": ["face-0"],
            "candidate_ids": [],
        }
        mock_reg.return_value = registry

        html = to_xml(
            public_photo_page(
                "photo-1",
                identity_id="context-1",
                sort_by="date_asc",
                user=None,
                is_admin=True,
                community_slug="rhodes",
            )
        )

        assert 'data-testid="photo-context-conflict-banner"' in html
        assert "The current assignment for Jacob Cohen overlaps another face on this photo." in html
