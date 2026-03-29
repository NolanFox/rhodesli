"""Tests for AI analysis section rendering with both batch and re-analyze label formats.

Session 143: The batch Gemini script produces different field names/formats than
the web UI re-analyze endpoint. The template must handle both.
Session 144 FB-002: Face analysis shows person name when face is identified.
"""

from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def mock_app():
    """Provide access to the main module with caches cleared."""
    import app.main as main

    main._date_labels_cache = None
    main._search_index_cache = None
    return main


class TestBatchLabelRendering:
    """Verify that batch-format labels render correctly."""

    BATCH_LABEL = {
        "photo_id": "test_batch_photo",
        "estimated_decade": 1920,
        "best_year_estimate": 1923,
        "confidence": "high",
        "probable_range": [1920, 1926],
        "reasoning_summary": "Based on clothing styles and photo technique.",
        "location_estimate": {"place": "Rhodes, Greece", "confidence": "high", "visual_evidence": "Stone architecture"},
        "scene_description": "A formal family portrait in a studio setting.",
        "face_analysis": [
            {"face_index": 0, "estimated_age": 45, "gender": "male", "description": "Mustached man in suit"},
            {"face_index": 1, "estimated_age": 38, "gender": "female", "description": "Woman in dark dress"},
        ],
        "group_composition": {"type": "formal_portrait", "people_count": 5, "arrangement": "seated family group"},
        "clothing_notes": "Man in three-piece suit with pocket watch chain, woman in dark formal dress.",
        "subject_ages": [45, 38, 12, 8],
        "text_signage": {"detected": True, "text": "A mi querida familia", "language": "Ladino"},
        "controlled_tags": ["studio_portrait", "family_group"],
        "evidence": {
            "fashion": [{"cue": "Three-piece suit style", "strength": "strong"}],
        },
    }

    REANALYZE_LABEL = {
        "photo_id": "test_reanalyze_photo",
        "estimated_decade": 1910,
        "best_year_estimate": 1915,
        "confidence": "medium",
        "probable_range": [1910, 1920],
        "reasoning_summary": "Clothing and architecture suggest 1910s.",
        "location_estimate": "Rhodes, Greece",
        "scene_description": "An outdoor market scene.",
        "visible_text": "Photographe Rhodes",
        "evidence": {
            "environment": [{"cue": "Mediterranean architecture", "strength": "moderate"}],
        },
        "subject_ages": "35, 12",
    }

    def test_batch_label_renders_face_analysis(self, mock_app):
        """Face analysis section appears for batch labels."""
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_batch_photo": self.BATCH_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_batch_photo", is_admin=True)
            html = repr(section)
            assert "Face Analysis" in html
            assert "Age ~45" in html
            assert "Mustached man in suit" in html

    def test_batch_label_renders_group_composition(self, mock_app):
        """Group composition section appears for batch labels."""
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_batch_photo": self.BATCH_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_batch_photo", is_admin=True)
            html = repr(section)
            assert "Group Composition" in html
            assert "Formal Portrait" in html
            assert "5 people" in html

    def test_batch_label_renders_clothing_notes(self, mock_app):
        """Clothing notes section appears for batch labels."""
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_batch_photo": self.BATCH_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_batch_photo", is_admin=True)
            html = repr(section)
            assert "Clothing" in html
            assert "pocket watch chain" in html

    def test_batch_label_renders_reasoning_summary(self, mock_app):
        """Reasoning summary appears for batch labels."""
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_batch_photo": self.BATCH_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_batch_photo", is_admin=True)
            html = repr(section)
            assert "AI Reasoning" in html
            assert "clothing styles" in html

    def test_batch_label_location_dict_handled(self, mock_app):
        """Location as dict (batch format) is handled gracefully."""
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_batch_photo": self.BATCH_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_batch_photo", is_admin=True)
            html = repr(section)
            # Should extract visual_evidence from dict, not show raw dict
            assert "Stone architecture" in html
            assert "{'place'" not in html

    def test_batch_label_text_signage_rendered_as_visible_text(self, mock_app):
        """text_signage dict is rendered as visible text."""
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_batch_photo": self.BATCH_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_batch_photo", is_admin=True)
            html = repr(section)
            assert "Visible Text" in html
            assert "A mi querida familia" in html

    def test_reanalyze_label_still_works(self, mock_app):
        """Re-analyze format (string location, direct visible_text) still renders."""
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_reanalyze_photo": self.REANALYZE_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_reanalyze_photo", is_admin=True)
            html = repr(section)
            assert "circa 1915" in html
            assert "outdoor market" in html.lower()
            assert "Photographe Rhodes" in html

    def test_empty_face_analysis_no_section(self, mock_app):
        """Empty face_analysis doesn't create a section."""
        label = {**self.REANALYZE_LABEL, "face_analysis": []}
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_reanalyze_photo": label}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_reanalyze_photo", is_admin=True)
            html = repr(section)
            assert "Face Analysis" not in html

    def test_subject_ages_list_and_string(self, mock_app):
        """subject_ages handles both list (batch) and string (re-analyze) formats."""
        # List format
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_batch_photo": self.BATCH_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_batch_photo", is_admin=True)
            html = repr(section)
            assert "45, 38, 12, 8" in html

        # String format
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_reanalyze_photo": self.REANALYZE_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
        ):
            section = mock_app._build_ai_analysis_section("test_reanalyze_photo", is_admin=True)
            html = repr(section)
            assert "35, 12" in html

    def test_face_analysis_shows_person_name_when_single_face_identified(self, mock_app):
        """FB-002: Face analysis uses person name for single-face identified photos."""
        # Single-face label (only face_index 0)
        single_face_label = {
            **self.BATCH_LABEL,
            "photo_id": "test_single_face",
            "face_analysis": [
                {"face_index": 0, "estimated_age": 21, "gender": "male", "description": "Young man"},
            ],
        }
        mock_photo_cache = {
            "test_single_face": {
                "faces": [{"face_id": "face_0_abc"}],
            }
        }
        mock_registry = {
            "identities": {
                "id-albert": {
                    "identity_id": "id-albert",
                    "name": "Albert Fox",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face_0_abc"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_single_face": single_face_label}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
            patch.object(mock_app, "_photo_cache", mock_photo_cache),
            patch.object(mock_app, "load_registry", return_value=mock_registry),
            patch.object(
                mock_app,
                "get_identity_for_face",
                side_effect=lambda reg, fid: mock_registry["identities"]["id-albert"] if fid == "face_0_abc" else None,
            ),
        ):
            section = mock_app._build_ai_analysis_section("test_single_face", is_admin=True)
            html = repr(section)
            # Single face should show "Albert Fox" not "Face 0"
            assert "Albert Fox:" in html
            assert "Face 0:" not in html

    def test_face_analysis_falls_back_to_face_n_when_unidentified(self, mock_app):
        """Face analysis falls back to 'Face N' when no identity is linked."""
        with (
            patch.object(mock_app, "_load_date_labels", return_value={"test_batch_photo": self.BATCH_LABEL}),
            patch.object(mock_app, "_load_photo_locations", return_value={}),
            patch.object(mock_app, "_load_search_index", return_value=[]),
            patch.object(mock_app, "_photo_cache", {}),
        ):
            section = mock_app._build_ai_analysis_section("test_batch_photo", is_admin=True)
            html = repr(section)
            assert "Face 0:" in html
            assert "Face 1:" in html
