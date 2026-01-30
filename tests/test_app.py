"""Integration tests for app/main.py - FastHTML gallery."""

import pytest
from starlette.testclient import TestClient

from app.main import app, parse_quality_from_filename


class TestParseQualityFromFilename:
    """Tests for the parse_quality_from_filename function."""

    def test_extracts_quality_from_standard_format(self):
        """Extracts quality from filename like 'name_21.98_0.jpg'."""
        assert parse_quality_from_filename("brass_rail_21.98_0.jpg") == 21.98

    def test_extracts_quality_with_high_value(self):
        """Handles quality scores above 25."""
        assert parse_quality_from_filename("photo_27.18_2.jpg") == 27.18

    def test_returns_zero_for_invalid_format(self):
        """Returns 0.0 for filenames without quality score."""
        assert parse_quality_from_filename("invalid.jpg") == 0.0

    def test_handles_complex_filename(self):
        """Handles real-world filename format."""
        result = parse_quality_from_filename("603569530_803296_1_24.55_0.jpg")
        assert result == 24.55


class TestGalleryRoute:
    """Integration tests for the gallery endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client for the FastHTML app."""
        return TestClient(app)

    def test_gallery_returns_200(self, client):
        """GET / returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_gallery_contains_title(self, client):
        """Gallery page contains the title."""
        response = client.get("/")
        assert "Rhodesli" in response.text

    def test_gallery_has_css_grid(self, client):
        """Gallery uses CSS grid layout."""
        response = client.get("/")
        assert "grid" in response.text  # Tailwind grid classes

    def test_gallery_has_quality_scores(self, client):
        """Gallery displays quality scores."""
        response = client.get("/")
        assert "Quality:" in response.text

    def test_gallery_has_face_cards(self, client):
        """Gallery has face card elements with images."""
        response = client.get("/")
        assert "/crops/" in response.text and "<img" in response.text

    def test_gallery_has_workstation_subtitle(self, client):
        """Gallery has workstation subtitle."""
        response = client.get("/")
        assert "Forensic Identity Workstation" in response.text


class TestNeighborCardThumbnail:
    """Tests for neighbor_card thumbnail rendering (B2)."""

    def test_uses_first_anchor_with_valid_crop(self):
        """When first anchor has crop file, uses it for thumbnail."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "test-id",
            "name": "Test Identity",
            "mls_score": -50,
            "can_merge": True,
            "face_count": 2,
            "anchor_face_ids": ["image_001:face0", "image_002:face0"],
        }
        crop_files = {"image_001_21.50_0.jpg", "image_002_22.00_0.jpg"}

        card = neighbor_card(neighbor, "target-id", crop_files)
        html = to_xml(card)

        # Should use first anchor's crop
        assert "/crops/image_001_21.50_0.jpg" in html

    def test_falls_back_to_second_anchor_when_first_has_no_crop(self):
        """When first anchor has no crop, tries subsequent anchors (B2 fix)."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "test-id",
            "name": "Test Identity",
            "mls_score": -50,
            "can_merge": True,
            "face_count": 2,
            "anchor_face_ids": ["missing_image:face0", "image_002:face0"],
        }
        # Only second anchor has a crop file
        crop_files = {"image_002_22.00_0.jpg"}

        card = neighbor_card(neighbor, "target-id", crop_files)
        html = to_xml(card)

        # Should fall back to second anchor's crop
        assert "/crops/image_002_22.00_0.jpg" in html
        # Should NOT show placeholder
        assert 'class="w-12 h-12 bg-stone-200' not in html

    def test_shows_placeholder_when_no_anchors_have_crops(self):
        """When no anchors have crop files, shows placeholder."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "test-id",
            "name": "Test Identity",
            "mls_score": -50,
            "can_merge": True,
            "face_count": 2,
            "anchor_face_ids": ["missing_a:face0", "missing_b:face0"],
        }
        crop_files = set()  # No crops available

        card = neighbor_card(neighbor, "target-id", crop_files)
        html = to_xml(card)

        # Should show placeholder div
        assert 'class="w-12 h-12 bg-stone-200' in html

    def test_shows_placeholder_when_no_anchors(self):
        """When identity has no anchors, shows placeholder."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "test-id",
            "name": "Test Identity",
            "mls_score": -50,
            "can_merge": True,
            "face_count": 0,
            "anchor_face_ids": [],
        }
        crop_files = {"some_crop_21.50_0.jpg"}

        card = neighbor_card(neighbor, "target-id", crop_files)
        html = to_xml(card)

        # Should show placeholder
        assert 'class="w-12 h-12 bg-stone-200' in html

    def test_falls_back_to_candidate_when_no_anchor_crops(self):
        """When no anchors have crops, falls back to candidate faces (B2-REPAIR)."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "test-id",
            "name": "Test Identity",
            "mls_score": -50,
            "can_merge": True,
            "face_count": 2,
            "anchor_face_ids": ["missing_anchor:face0"],
            "candidate_face_ids": ["candidate_image:face0"],
        }
        # Only candidate has a crop
        crop_files = {"candidate_image_21.50_0.jpg"}

        card = neighbor_card(neighbor, "target-id", crop_files)
        html = to_xml(card)

        # Should use candidate's crop
        assert "/crops/candidate_image_21.50_0.jpg" in html
        # Should NOT show placeholder
        assert 'class="w-12 h-12 bg-stone-200' not in html

    def test_falls_back_to_candidate_when_no_anchors(self):
        """PROPOSED identities with only candidates should show candidate thumbnail."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "test-id",
            "name": "Test Identity",
            "mls_score": -50,
            "can_merge": True,
            "face_count": 1,
            "anchor_face_ids": [],  # No anchors (PROPOSED singleton)
            "candidate_face_ids": ["solo_candidate:face0"],
        }
        crop_files = {"solo_candidate_21.50_0.jpg"}

        card = neighbor_card(neighbor, "target-id", crop_files)
        html = to_xml(card)

        # Should use candidate's crop
        assert "/crops/solo_candidate_21.50_0.jpg" in html
        # Should NOT show placeholder
        assert 'class="w-12 h-12 bg-stone-200' not in html

    def test_shows_placeholder_when_neither_anchor_nor_candidate_has_crop(self):
        """When neither anchors nor candidates have crops, shows placeholder."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "test-id",
            "name": "Test Identity",
            "mls_score": -50,
            "can_merge": True,
            "face_count": 2,
            "anchor_face_ids": ["missing_anchor:face0"],
            "candidate_face_ids": ["missing_candidate:face0"],
        }
        crop_files = set()  # No crops available

        card = neighbor_card(neighbor, "target-id", crop_files)
        html = to_xml(card)

        # Should show placeholder
        assert 'class="w-12 h-12 bg-stone-200' in html
