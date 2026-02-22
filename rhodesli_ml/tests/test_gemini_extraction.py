"""Tests for unified Gemini extraction architecture.

Verifies presets, prompt building, and schema generation.
"""

import pytest
from rhodesli_ml.gemini_extraction import (
    EXTRACTION_PRESETS,
    build_extraction_prompt,
    get_active_extractions,
)


class TestExtractionPresets:
    """Verify preset configurations are correct."""

    def test_full_preset_includes_all_types(self):
        """Full preset enables every extraction type."""
        full = EXTRACTION_PRESETS["full"]
        assert all(v is True for v in full.values()), "Full preset must enable all types"

    def test_quick_preset_is_minimal(self):
        """Quick preset only includes fast extractions."""
        quick = EXTRACTION_PRESETS["quick"]
        assert quick["date_estimation"] is True
        assert quick["text_signage"] is True
        assert quick["location"] is True
        assert quick["face_analysis"] is False
        assert quick["cultural_markers"] is False

    def test_compare_preset_has_face_and_date(self):
        """Compare preset includes face analysis and date estimation."""
        compare = EXTRACTION_PRESETS["compare"]
        assert compare["date_estimation"] is True
        assert compare["face_analysis"] is True
        assert compare["subject_ages"] is True
        assert compare["location"] is False

    def test_all_presets_have_date_estimation(self):
        """Every preset must include date estimation."""
        for name, config in EXTRACTION_PRESETS.items():
            assert config["date_estimation"] is True, f"{name} must include date_estimation"


class TestBuildPrompt:
    """Verify prompt construction."""

    def test_full_prompt_includes_all_sections(self):
        """Full prompt has sections for every extraction type."""
        prompt = build_extraction_prompt(preset="full")
        assert "Date Estimation" in prompt
        assert "Face Analysis" in prompt
        assert "Location Identification" in prompt
        assert "Cultural Markers" in prompt
        assert "Text & Signage" in prompt
        assert "Group Composition" in prompt
        assert "Photo Condition" in prompt
        assert "Subject Age" in prompt

    def test_quick_prompt_excludes_disabled_sections(self):
        """Quick prompt should not include face analysis or cultural markers."""
        prompt = build_extraction_prompt(preset="quick")
        assert "Date Estimation" in prompt
        assert "Face Analysis" not in prompt
        assert "Cultural Markers" not in prompt

    def test_include_adds_extraction(self):
        """include parameter adds extraction types to a preset."""
        prompt = build_extraction_prompt(preset="quick", include=["face_analysis"])
        assert "Face Analysis" in prompt

    def test_exclude_removes_extraction(self):
        """exclude parameter removes extraction types from a preset."""
        prompt = build_extraction_prompt(preset="full", exclude=["face_analysis"])
        assert "Face Analysis" not in prompt
        assert "Date Estimation" in prompt

    def test_invalid_preset_raises(self):
        """Unknown preset names raise ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            build_extraction_prompt(preset="nonexistent")

    def test_verified_facts_included_in_prompt(self):
        """Verified facts are injected into the prompt."""
        facts = {
            "confirmed_names": ["Isaac Hazan", "Luna Capuano"],
            "confirmed_date": "circa 1910",
            "confirmed_location": "Rhodes, Greece",
        }
        prompt = build_extraction_prompt(preset="full", verified_facts=facts)
        assert "Isaac Hazan" in prompt
        assert "Luna Capuano" in prompt
        assert "circa 1910" in prompt
        assert "Rhodes, Greece" in prompt
        assert "Known Facts" in prompt

    def test_face_coordinates_included_when_provided(self):
        """Face bounding box coordinates are passed to face_analysis section."""
        coords = [
            {"bbox": [100, 50, 200, 180]},
            {"bbox": [300, 60, 400, 190]},
        ]
        prompt = build_extraction_prompt(
            preset="compare", face_coordinates=coords
        )
        assert "bbox=[100, 50, 200, 180]" in prompt
        assert "Face 0" in prompt
        assert "Face 1" in prompt

    def test_prompt_contains_json_schema(self):
        """Prompt includes JSON response format."""
        prompt = build_extraction_prompt(preset="full")
        assert "Response Format (JSON only)" in prompt
        assert "date_estimation" in prompt
        assert "decade_probabilities" in prompt

    def test_prompt_contains_cultural_context(self):
        """Prompt includes Sephardic cultural context."""
        prompt = build_extraction_prompt(preset="quick")
        assert "Sephardic" in prompt
        assert "Rhodes" in prompt
        assert "LAGGED" in prompt


class TestGetActiveExtractions:
    """Verify extraction type listing."""

    def test_full_returns_all(self):
        """Full preset returns all extraction types."""
        active = get_active_extractions("full")
        assert len(active) == 10

    def test_quick_returns_subset(self):
        """Quick preset returns only enabled types."""
        active = get_active_extractions("quick")
        assert "date_estimation" in active
        assert "text_signage" in active
        assert "location" in active
        assert "face_analysis" not in active

    def test_include_exclude_override(self):
        """Include/exclude modify the active list."""
        active = get_active_extractions("quick", include=["face_analysis"], exclude=["location"])
        assert "face_analysis" in active
        assert "location" not in active
