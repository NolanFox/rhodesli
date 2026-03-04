"""
Tests for Session 69 Design Audit — Archival Aesthetic (DD-001, DD-002).

Verifies:
- Google Fonts (Playfair Display) is included in HTML headers
- Tailwind config extends font-display and font-serif
- Face cards use archival CSS classes
- Identity cards use archival CSS classes
- Section headers use font-display class
- Sidebar branding uses font-display class
"""
import pytest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient


class TestGoogleFontsInclusion:
    """DD-001: Verify Google Fonts link tags are present in the app headers."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_google_fonts_preconnect_present(self, client):
        """Preconnect link to fonts.googleapis.com is in the HTML head."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'fonts.googleapis.com' in response.text

    def test_google_fonts_stylesheet_present(self, client):
        """Playfair Display stylesheet link is in the HTML head."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'Playfair+Display' in response.text or 'Playfair Display' in response.text

    def test_tailwind_config_has_font_display(self, client):
        """Tailwind config script extends fontFamily with display and serif."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'Playfair Display' in response.text
        assert 'fontFamily' in response.text


class TestFaceCardArchivalStyle:
    """DD-002: Verify face cards use archival styling classes."""

    def test_face_card_has_archival_class(self):
        """face_card() returns an element with face-card-archival class."""
        from app.main import face_card, to_xml
        html = to_xml(face_card(
            face_id="test-face-001",
            crop_url="/static/crops/test_0.jpg",
            identity_id="test-id-001",
        ))
        assert 'face-card-archival' in html

    def test_face_card_image_has_sepia(self):
        """face_card() image uses sepia filter for archival look."""
        from app.main import face_card, to_xml
        html = to_xml(face_card(
            face_id="test-face-001",
            crop_url="/static/crops/test_0.jpg",
            identity_id="test-id-001",
        ))
        assert 'sepia-' in html

    def test_face_card_has_warm_border(self):
        """face_card() image container uses warm amber border tone."""
        from app.main import face_card, to_xml
        html = to_xml(face_card(
            face_id="test-face-001",
            crop_url="/static/crops/test_0.jpg",
            identity_id="test-id-001",
        ))
        assert 'amber-900' in html


class TestIdentityCardArchivalStyle:
    """DD-002: Verify identity cards use archival styling classes."""

    def test_identity_card_has_card_styling(self):
        """identity_card() returns photo-dominant card with modern styling (DD-005)."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-id-design-001",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-design-1"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-design-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files))
        assert 'identity-card' in html
        assert 'rounded-2xl' in html

    def test_identity_card_name_uses_display_font(self):
        """identity_card name heading uses font-display class."""
        from app.main import name_display, to_xml
        html = to_xml(name_display("test-id-001", "Test Person"))
        assert 'font-display' in html


class TestSectionHeaderFont:
    """DD-001: Section headers use the archival display font."""

    def test_section_header_uses_display_font(self):
        """section_header H2 uses font-display class."""
        from app.main import section_header, to_xml
        html = to_xml(section_header("Test Title", "Test subtitle"))
        assert 'font-display' in html


class TestSidebarBranding:
    """DD-001: Sidebar uses the archival display font for branding."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_sidebar_rhodesli_uses_display_font(self, client):
        """Sidebar 'Rhodesli' heading uses font-display class."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
        assert response.status_code == 200
        # The sidebar branding should have font-display
        assert 'font-display' in response.text


class TestArchivalCSSDefinitions:
    """Verify CSS class definitions for archival aesthetics exist."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_font_display_css_defined(self, client):
        """CSS defines .font-display with Playfair Display font family."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert '.font-display' in response.text

    def test_face_card_archival_css_defined(self, client):
        """CSS defines .face-card-archival class."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert '.face-card-archival' in response.text

    def test_identity_card_class_present(self, client):
        """Identity cards use identity-card class (DD-005 redesign)."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert 'identity-card' in response.text

    def test_photo_card_frame_css_defined(self, client):
        """CSS defines .photo-card-frame class."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert '.photo-card-frame' in response.text


class TestFaceGridDensity:
    """DD-002: Face grid uses more columns for compact cards."""

    def test_card_is_photo_dominant(self):
        """Identity card has photo-dominant design with aspect-square hero (DD-005)."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-id-grid-001",
            "name": "Grid Test",
            "state": "PROPOSED",
            "anchor_ids": ["face-grid-1"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-grid-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files))
        assert 'aspect-square' in html


class TestLandingPageDisplayFont:
    """DD-001: Landing page uses the archival display font for the hero headline."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_landing_hero_h1_uses_display_font(self, client):
        """Landing page hero H1 uses font-display class."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'font-display' in response.text


# ---------------------------------------------------------------------------
# Test: Faces button + visible detach (Session 87 Act 6a)
# ---------------------------------------------------------------------------

class TestIdentityCardFacesButton:
    """Tests for the Faces button on multi-face identity cards."""

    def test_faces_button_shown_for_multi_face_identity(self):
        """Identity cards with >1 face show a 'Faces (N)' button."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = {
            "identity_id": "test-multi-face-001",
            "name": "Multi Face Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a", "face-b", "face-c"],
            "candidate_ids": [],
        }
        crop_files = {"test-multi-face-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files, is_admin=True))
        assert 'data-testid="faces-button"' in html
        assert "Faces (3)" in html

    def test_faces_button_not_shown_for_single_face_identity(self):
        """Identity cards with only 1 face do NOT show a Faces button."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = {
            "identity_id": "test-single-face-001",
            "name": "Single Face Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a"],
            "candidate_ids": [],
        }
        crop_files = {"test-single-face-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files, is_admin=True))
        assert 'data-testid="faces-button"' not in html

    def test_faces_button_targets_admin_details(self):
        """Faces button opens the admin details section via JS onclick."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = {
            "identity_id": "test-detail-open-001",
            "name": "Detail Person",
            "state": "PROPOSED",
            "anchor_ids": ["face-a"],
            "candidate_ids": ["face-b"],
        }
        crop_files = {"test-detail-open-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files, is_admin=True))
        # The details element should have an ID that the Faces button targets
        assert "admin-details-" in html
        assert 'data-testid="faces-button"' in html


class TestDetachButtonVisibility:
    """Tests for detach button visibility on face cards."""

    def test_detach_button_visible_for_admin_multi_face(self):
        """Detach button is always visible (not hover-only) for admin on multi-face identities."""
        from app.main import face_card
        from fastcore.xml import to_xml

        html = to_xml(face_card(
            face_id="test-face-detach-001",
            crop_url="/static/crops/test.jpg",
            show_detach=True,
            is_admin=True,
            identity_id="test-id-001",
        ))
        # Detach button should be present
        assert "Detach" in html
        # Should NOT have opacity-0 (hover-only) class when show_detach=True
        assert "opacity-0" not in html

    def test_detach_button_hover_only_when_not_detachable(self):
        """When show_detach is False, secondary actions are still hover-only."""
        from app.main import face_card
        from fastcore.xml import to_xml

        html = to_xml(face_card(
            face_id="test-face-no-detach-001",
            crop_url="/static/crops/test.jpg",
            show_detach=False,
            is_admin=True,
            identity_id="test-id-001",
            photo_id="photo-001",
        ))
        # Should have opacity-0 class (hover-only) since show_detach is False
        assert "opacity-0" in html
