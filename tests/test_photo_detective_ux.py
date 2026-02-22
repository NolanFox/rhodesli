"""Tests for Photo Detective UX (PRD-022, Session 61).

Tests evidence cards, detective evidence section, progressive refinement badge,
and integration with photo detail + estimate pages.
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestEvidenceCard:
    """Tests for _evidence_card() component."""

    def test_renders_with_cues(self):
        from app.main import _evidence_card
        card = _evidence_card("fashion", [
            {"cue": "Wide lapels", "strength": "strong", "suggested_range": [1930, 1945]},
            {"cue": "Fedora hats", "strength": "moderate"},
        ])
        assert card is not None
        html = repr(card)
        assert "Fashion/Grooming" in html
        assert "Wide lapels" in html
        assert "strong" in html
        assert "evidence-card-fashion" in html

    def test_returns_none_for_empty_cues(self):
        from app.main import _evidence_card
        assert _evidence_card("fashion", []) is None

    def test_limits_to_three_cues(self):
        from app.main import _evidence_card
        cues = [{"cue": f"Cue {i}", "strength": "moderate"} for i in range(5)]
        card = _evidence_card("technology", cues)
        html = repr(card)
        assert "Cue 0" in html
        assert "Cue 2" in html
        # 4th cue should not appear (0-indexed: cues 0,1,2 shown)
        assert "Cue 3" not in html

    def test_strength_badge_colors(self):
        from app.main import _evidence_card
        card = _evidence_card("environment", [
            {"cue": "Strong cue", "strength": "strong"},
        ])
        html = repr(card)
        assert "text-emerald-400" in html  # Strong = emerald

    def test_unknown_category_uses_title_case(self):
        from app.main import _evidence_card
        card = _evidence_card("some_new_category", [
            {"cue": "Something", "strength": "moderate"},
        ])
        html = repr(card)
        assert "Some New Category" in html

    def test_date_range_displayed(self):
        from app.main import _evidence_card
        card = _evidence_card("print_format", [
            {"cue": "Gelatin silver print", "strength": "strong", "suggested_range": [1920, 1960]},
        ])
        html = repr(card)
        assert "1920-1960" in html


class TestDetectiveEvidenceSection:
    """Tests for _detective_evidence_section() component."""

    def test_renders_with_evidence(self):
        from app.main import _detective_evidence_section
        label = {
            "evidence": {
                "fashion": [{"cue": "Wide ties", "strength": "strong"}],
                "environment": [{"cue": "Art Deco architecture", "strength": "moderate"}],
            },
            "model": "gemini-3.1-pro-preview",
        }
        section = _detective_evidence_section(label)
        assert section is not None
        html = repr(section)
        assert "detective-evidence" in html
        assert "Photo Detective Analysis" in html
        assert "model-badge" in html
        assert "Gemini 3.1-pro" in html

    def test_returns_none_for_no_evidence(self):
        from app.main import _detective_evidence_section
        assert _detective_evidence_section({}) is None
        assert _detective_evidence_section(None) is None

    def test_handles_nested_date_estimation_structure(self):
        from app.main import _detective_evidence_section
        label = {
            "date_estimation": {
                "evidence": {
                    "fashion": [{"cue": "Bell bottoms", "strength": "strong"}],
                },
                "cultural_lag_note": "Island communities lag mainland fashion",
            },
        }
        section = _detective_evidence_section(label)
        assert section is not None
        html = repr(section)
        assert "Bell bottoms" in html
        assert "cultural" in html.lower()

    def test_cultural_lag_note_displayed(self):
        from app.main import _detective_evidence_section
        label = {
            "evidence": {
                "fashion": [{"cue": "Something", "strength": "moderate"}],
            },
            "cultural_lag_note": "Rhodes community fashion lagged mainland trends by 5-10 years",
        }
        section = _detective_evidence_section(label)
        html = repr(section)
        assert "Cultural context" in html


class TestProgressiveRefinementBadge:
    """Tests for _progressive_refinement_badge() component."""

    def test_renders_with_refinement_metadata(self):
        from app.main import _progressive_refinement_badge
        label = {
            "_metadata": {
                "refinement": True,
                "fact_count": 3,
            }
        }
        badge = _progressive_refinement_badge(label)
        assert badge is not None
        html = repr(badge)
        assert "refinement-badge" in html
        assert "3 verified facts" in html

    def test_singular_fact_count(self):
        from app.main import _progressive_refinement_badge
        label = {"_metadata": {"refinement": True, "fact_count": 1}}
        badge = _progressive_refinement_badge(label)
        html = repr(badge)
        assert "1 verified fact" in html
        assert "facts" not in html

    def test_returns_none_without_refinement(self):
        from app.main import _progressive_refinement_badge
        assert _progressive_refinement_badge({}) is None
        assert _progressive_refinement_badge(None) is None
        assert _progressive_refinement_badge({"_metadata": {}}) is None

    def test_handles_metadata_key_variant(self):
        from app.main import _progressive_refinement_badge
        label = {"metadata": {"refinement": True, "fact_count": 5}}
        badge = _progressive_refinement_badge(label)
        assert badge is not None
        html = repr(badge)
        assert "5 verified facts" in html


class TestPhotoDateBadge:
    """Tests for _build_photo_date_badge() on photo detail page."""

    def test_renders_date_badge(self):
        from app.main import _build_photo_date_badge
        mock_labels = {
            "test_photo_1": {
                "estimated_decade": 1940,
                "best_year_estimate": 1943,
                "confidence": "high",
                "probable_range": [1938, 1948],
            }
        }
        with patch("app.main._load_date_labels", return_value=mock_labels):
            badge = _build_photo_date_badge("test_photo_1")
            assert badge is not None
            html = repr(badge)
            assert "photo-date-badge" in html
            assert "c. 1940s" in html
            assert "high confidence" in html
            assert "\u00b1" in html  # ± symbol

    def test_returns_none_without_label(self):
        from app.main import _build_photo_date_badge
        with patch("app.main._load_date_labels", return_value={}):
            assert _build_photo_date_badge("nonexistent") is None


class TestAIAnalysisDetectiveIntegration:
    """Tests that Photo Detective evidence integrates into AI Analysis section."""

    def test_detective_evidence_in_ai_analysis(self):
        from app.main import _build_ai_analysis_section
        mock_labels = {
            "test_photo_2": {
                "estimated_decade": 1930,
                "best_year_estimate": 1935,
                "confidence": "medium",
                "probable_range": [1930, 1940],
                "evidence": {
                    "fashion": [{"cue": "Cloche hats", "strength": "strong"}],
                    "print_format": [{"cue": "Sepia toning", "strength": "moderate"}],
                },
            }
        }
        with patch("app.main._load_date_labels", return_value=mock_labels), \
             patch("app.main._load_search_index", return_value=[]):
            section = _build_ai_analysis_section("test_photo_2")
            assert section is not None
            html = repr(section)
            assert "Photo Detective Evidence" in html
            assert "detective-evidence" in html

    def test_fallback_to_list_when_no_structured_evidence(self):
        from app.main import _build_ai_analysis_section
        mock_labels = {
            "test_photo_3": {
                "estimated_decade": 1950,
                "best_year_estimate": 1955,
                "confidence": "low",
                "probable_range": [1945, 1960],
                "evidence": {
                    "misc": "just a string, not a list",
                },
            }
        }
        with patch("app.main._load_date_labels", return_value=mock_labels), \
             patch("app.main._load_search_index", return_value=[]):
            section = _build_ai_analysis_section("test_photo_3")
            assert section is not None
            # Should not crash — section renders


class TestPhotoPageEstimateBadge:
    """Tests that photo detail page includes estimate badge when available."""

    def test_photo_page_has_estimate_badge(self, client):
        """Photo page renders date badge section when estimate exists."""
        mock_labels = {
            "test_photo_id": {
                "estimated_decade": 1940,
                "best_year_estimate": 1943,
                "confidence": "high",
                "probable_range": [1938, 1948],
            }
        }
        mock_photo = {
            "filename": "test.jpg",
            "collection": "Test Collection",
            "source": "Test",
            "faces": [],
            "face_ids": [],
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_photo_metadata", return_value=mock_photo), \
             patch("app.main.get_photo_dimensions", return_value=(800, 600)), \
             patch("app.main.load_registry", return_value={"identities": {}}), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._load_date_labels", return_value=mock_labels), \
             patch("app.main._load_search_index", return_value=[]), \
             patch("app.main.photo_url", return_value="/photos/test.jpg"):
            response = client.get("/photo/test_photo_id")
            assert response.status_code == 200
            assert "photo-date-badge" in response.text
            assert "c. 1940s" in response.text
