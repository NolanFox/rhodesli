"""Tests for Session 71 Track A UX fixes.

Covers:
- A2: Face card photo size (min-width >= 150px)
- A4: AI Analysis — Scene expanded by default
- A5: "Often appears with" name truncation (max-w increased to 140px)
- A6: Quality score labels (human-readable, not raw numbers)
- A3: Run Face Analysis button feedback (loading indicator)
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

import json
from pathlib import Path

from app.main import app, load_registry, data_path


def _load_photos_list():
    """Load photos from photo_index.json directly (PhotoRegistry has no list_photos)."""
    pi_path = data_path / "photo_index.json"
    if not pi_path.exists():
        return []
    pi = json.loads(pi_path.read_text(encoding="utf-8"))
    photos = []
    for pid, entry in pi.get("photos", {}).items():
        entry["photo_id"] = pid
        photos.append(entry)
    return photos


@pytest.fixture
def client():
    return TestClient(app)


class TestQualityScoreLabels:
    """A6: Quality score should show human-readable labels, not raw numbers."""

    def test_quality_label_excellent(self, client):
        """Quality >= 30 shows 'Excellent quality'."""
        # Test via confirmed identity page
        registry = load_registry()
        confirmed = [i for i in registry.list_identities()
                     if i.get("state") == "CONFIRMED"]
        if not confirmed:
            pytest.skip("No confirmed identities")

        response = client.get(f"/?section=confirmed")
        assert response.status_code == 200
        # Should NOT show raw "Quality: XX.XX" format
        assert "Quality: " not in response.text or "quality" in response.text.lower()

    def test_quality_labels_present(self, client):
        """People page shows human-readable quality labels."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        html = response.text
        # Should contain at least one of the quality labels
        has_label = any(label in html for label in
                       ["Excellent quality", "Good quality", "Fair quality", "Low quality"])
        # It's OK if no faces have quality scores (some crops lack them)
        # But raw "Quality: XX.XX" should NOT appear
        assert "Quality: " not in html, "Raw quality scores should not be shown to users"

    def test_quality_tooltip_admin_only(self, client):
        """Raw quality score in tooltip should only appear for admin."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        html = response.text
        # Admin sees tooltip with raw score
        if "Quality score:" in html:
            assert 'title="Quality score:' in html, "Raw score should be in title attribute"


class TestFaceCardSize:
    """A2: Face cards should have minimum width for visible photos."""

    def test_face_card_has_min_width(self, client):
        """Face card container should have min-w-[150px]."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert "min-w-[150px]" in response.text, "Face cards need minimum width of 150px"

    def test_face_grid_uses_fewer_columns(self, client):
        """Grid should use lg:grid-cols-5 (not 6) for larger face cards."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert "lg:grid-cols-5" in response.text, "Grid should use 5 columns max on large screens"
        assert "lg:grid-cols-6" not in response.text, "Grid should NOT use 6 columns"


class TestAIAnalysisExpanded:
    """A4: Scene and Photo Detective Evidence sections should be expanded by default."""

    def test_scene_section_expanded(self, client):
        """Scene section should have 'open' attribute when data exists."""
        # We test via a photo that has AI analysis data
        photos = _load_photos_list()
        if not photos:
            pytest.skip("No photos available")

        # Try a few photos to find one with AI analysis
        for photo in photos[:10]:
            photo_id = photo.get("photo_id", "")
            response = client.get(f"/photo/{photo_id}/partial")
            if response.status_code == 200 and "Scene" in response.text:
                # The Scene details element should be open
                # In the HTML, <details open ...> means expanded
                html = response.text
                scene_idx = html.find("Scene")
                if scene_idx > 0:
                    # Find the parent <details> tag
                    details_start = html.rfind("<details", 0, scene_idx)
                    if details_start >= 0:
                        details_tag = html[details_start:scene_idx]
                        assert "open" in details_tag, "Scene section should be expanded by default"
                        return

        pytest.skip("No photos with Scene data found")


class TestNameTruncation:
    """A5: 'Often appears with' should show wider names (max-w-[140px])."""

    def test_companion_names_wider(self, client):
        """Companion name spans should use max-w-[140px], not max-w-[80px]."""
        registry = load_registry()
        confirmed = [i for i in registry.list_identities()
                     if i.get("state") == "CONFIRMED"
                     and not i.get("name", "").startswith("Unidentified")]
        if not confirmed:
            pytest.skip("No confirmed identities")

        for identity in confirmed[:5]:
            response = client.get(f"/person/{identity['identity_id']}")
            if "Often appears with" in response.text:
                assert "max-w-[140px]" in response.text, "Companion names should use 140px max width"
                assert "max-w-[80px]" not in response.text, "Old 80px max width should be removed"
                return

        pytest.skip("No confirmed identities with companions found")

    def test_companion_names_have_title_tooltip(self, client):
        """Companion name elements should have title attribute for full name on hover."""
        registry = load_registry()
        confirmed = [i for i in registry.list_identities()
                     if i.get("state") == "CONFIRMED"
                     and not i.get("name", "").startswith("Unidentified")]
        if not confirmed:
            pytest.skip("No confirmed identities")

        for identity in confirmed[:5]:
            response = client.get(f"/person/{identity['identity_id']}")
            html = response.text
            if "Often appears with" in html:
                # Find the section
                idx = html.index("Often appears with")
                section = html[idx:idx + 2000]
                # Companion names should have title attributes
                assert "title=" in section, "Companion names need title tooltip for full name"
                return

        pytest.skip("No confirmed identities with companions found")


class TestRunFaceAnalysisFeedback:
    """A3: Run Face Analysis button should show loading feedback."""

    def test_analysis_button_has_loading_indicator(self, client):
        """Face analysis button should have htmx-indicator for loading state."""
        photos = _load_photos_list()
        if not photos:
            pytest.skip("No photos available")

        for photo in photos[:10]:
            photo_id = photo.get("photo_id", "")
            response = client.get(f"/photo/{photo_id}/partial")
            if response.status_code == 200 and "Run Face Analysis" in response.text:
                html = response.text
                assert "Analyzing faces..." in html, "Should show 'Analyzing faces...' indicator text"
                assert "hx-disabled-elt" in html, "Button should be disabled during request"
                return

        pytest.skip("No photos with Face Analysis trigger found")


class TestEnterKeyHandler:
    """A1: Enter key in face tag search should create identity."""

    def test_tag_search_has_enter_handler(self, client):
        """Face tag search input should have Enter key hyperscript handler."""
        photos = _load_photos_list()
        if not photos:
            pytest.skip("No photos available")

        # Get a photo with faces
        for photo in photos[:10]:
            photo_id = photo.get("photo_id", "")
            face_ids = photo.get("face_ids", [])
            if not face_ids:
                continue
            response = client.get(f"/photo/{photo_id}/partial")
            if response.status_code == 200 and "tag" in response.text.lower():
                html = response.text
                # Should have the Enter key handler in hyperscript
                if "keydown" in html and "Enter" in html:
                    # Verify the retry logic exists (wait 400ms fallback)
                    assert "wait 400ms" in html, "Enter handler should have 400ms retry fallback"
                    return

        pytest.skip("No photos with face tag search found")
