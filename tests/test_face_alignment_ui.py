"""Tests for face alignment UI elements — PRD-015 Phase 4."""

from unittest.mock import patch

import pytest


class TestFaceAlignmentSection:
    """Test _build_face_alignment_section rendering."""

    def test_admin_sees_trigger_when_no_alignment(self):
        """Admin sees 'Run Face Analysis' button when no alignment exists."""
        from app.main import _build_face_alignment_section

        with patch("app.face_alignment.get_cached_alignment", return_value=None), \
             patch("app.face_alignment.load_alignments_from_file", return_value={}):
            result = _build_face_alignment_section("photo_test", is_admin=True)

        html = repr(result)
        assert "Run Face Analysis" in html
        assert "face-alignment-trigger" in html

    def test_non_admin_sees_nothing_when_no_alignment(self):
        """Non-admin sees nothing when no alignment exists."""
        from app.main import _build_face_alignment_section

        with patch("app.face_alignment.get_cached_alignment", return_value=None), \
             patch("app.face_alignment.load_alignments_from_file", return_value={}):
            result = _build_face_alignment_section("photo_test", is_admin=False)

        assert result is None

    def test_renders_alignment_results(self):
        """Renders face description cards when alignment exists."""
        from app.main import _build_face_alignment_section

        alignment_data = {
            "photo_id": "photo_test",
            "faces_detected": 2,
            "faces_described": 2,
            "model_used": "gemini-3.1-pro",
            "scene_context": "Formal studio portrait",
            "aligned_faces": [
                {
                    "face_id": "face_0",
                    "face_index": 0,
                    "bbox": [100, 50, 250, 300],
                    "estimated_age": 40,
                    "gender": "male",
                    "gemini_description": "Man with dark hair",
                    "clothing": "Dark suit",
                    "position_in_photo": "Left side",
                    "identifying_features": "Mustache",
                    "identity_name": "Leon Capeluto",
                    "is_subject": True,
                    "matched": True,
                },
                {
                    "face_id": "face_1",
                    "face_index": 1,
                    "bbox": [300, 50, 450, 300],
                    "estimated_age": 35,
                    "gender": "female",
                    "gemini_description": "Woman with pearl necklace",
                    "clothing": "Floral dress",
                    "position_in_photo": "Right side",
                    "identifying_features": "Pearl necklace",
                    "identity_name": None,
                    "is_subject": True,
                    "matched": True,
                },
            ],
            "gemini_only_faces": [],
            "unmatched_faces": [],
        }

        with patch("app.face_alignment.get_cached_alignment", return_value=None), \
             patch("app.face_alignment.load_alignments_from_file",
                   return_value={"photo_test": alignment_data}):
            result = _build_face_alignment_section("photo_test", is_admin=False)

        html = repr(result)
        assert "Face Analysis" in html
        assert "Leon Capeluto" in html
        assert "Age: ~40" in html
        assert "Dark suit" in html
        assert "face-alignment-results" in html

    def test_renders_mismatch_warning(self):
        """Shows mismatch warning when face counts differ."""
        from app.main import _build_face_alignment_section

        alignment_data = {
            "photo_id": "photo_mismatch",
            "faces_detected": 4,
            "faces_described": 3,
            "model_used": "gemini-pro",
            "scene_context": "",
            "aligned_faces": [],
            "gemini_only_faces": [{"description": "Extra face"}],
            "unmatched_faces": ["face_3"],
        }

        with patch("app.face_alignment.get_cached_alignment", return_value=None), \
             patch("app.face_alignment.load_alignments_from_file",
                   return_value={"photo_mismatch": alignment_data}):
            result = _build_face_alignment_section("photo_mismatch", is_admin=False)

        html = repr(result)
        assert "detected 4 faces" in html
        assert "described 3" in html
        assert "face-alignment-mismatch" in html

    def test_admin_sees_rerun_button(self):
        """Admin sees Re-run Analysis button when alignment exists."""
        from app.main import _build_face_alignment_section

        alignment_data = {
            "photo_id": "photo_x",
            "faces_detected": 1,
            "faces_described": 1,
            "model_used": "gemini-pro",
            "scene_context": "",
            "aligned_faces": [
                {
                    "face_id": "f1", "face_index": 0, "bbox": [0, 0, 10, 10],
                    "estimated_age": 30, "gender": "male", "gemini_description": "...",
                    "is_subject": True, "matched": True,
                }
            ],
            "gemini_only_faces": [],
            "unmatched_faces": [],
        }

        with patch("app.face_alignment.get_cached_alignment", return_value=None), \
             patch("app.face_alignment.load_alignments_from_file",
                   return_value={"photo_x": alignment_data}):
            result = _build_face_alignment_section("photo_x", is_admin=True)

        html = repr(result)
        assert "Re-run Analysis" in html

    def test_non_subject_faces_hidden(self):
        """Non-subject faces (background, newspaper) are not shown."""
        from app.main import _build_face_alignment_section

        alignment_data = {
            "photo_id": "photo_bg",
            "faces_detected": 3,
            "faces_described": 3,
            "model_used": "gemini-pro",
            "scene_context": "",
            "aligned_faces": [
                {
                    "face_id": "f1", "face_index": 0, "bbox": [0, 0, 10, 10],
                    "estimated_age": 30, "gender": "male",
                    "gemini_description": "Real person",
                    "is_subject": True, "matched": True,
                },
                {
                    "face_id": "f2", "face_index": 1, "bbox": [20, 0, 30, 10],
                    "estimated_age": None, "gender": None,
                    "gemini_description": "Newspaper face",
                    "is_subject": False, "matched": True,
                },
            ],
            "gemini_only_faces": [],
            "unmatched_faces": [],
        }

        with patch("app.face_alignment.get_cached_alignment", return_value=None), \
             patch("app.face_alignment.load_alignments_from_file",
                   return_value={"photo_bg": alignment_data}):
            result = _build_face_alignment_section("photo_bg", is_admin=False)

        html = repr(result)
        assert "Real person" in html
        assert "Newspaper face" not in html
