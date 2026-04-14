"""Tests for event context and relationship inference extraction sections.

Session 149 Phase 2: Extends gemini_extraction.py with event_context and
relationship_inference sections, plus the new "identification" preset.
"""

import json

import pytest
from rhodesli_ml.gemini_extraction import (
    EXTRACTION_PRESETS,
    _PROMPT_SECTIONS,
    _SCHEMA_FRAGMENTS,
    build_extraction_prompt,
    get_active_extractions,
)


class TestIdentificationPreset:
    """Verify the new 'identification' preset configuration."""

    def test_identification_preset_exists(self):
        """identification preset is registered."""
        assert "identification" in EXTRACTION_PRESETS

    def test_identification_includes_all_full_fields(self):
        """identification preset includes every field from 'full' preset."""
        full = EXTRACTION_PRESETS["full"]
        identification = EXTRACTION_PRESETS["identification"]
        for key, value in full.items():
            assert key in identification, f"identification missing key from full: {key}"
            if value:
                assert identification[key], f"identification should enable {key} (enabled in full)"

    def test_identification_includes_event_context(self):
        """identification preset includes event_context."""
        assert EXTRACTION_PRESETS["identification"]["event_context"] is True

    def test_identification_includes_relationship_inference(self):
        """identification preset includes relationship_inference."""
        assert EXTRACTION_PRESETS["identification"]["relationship_inference"] is True

    def test_identification_has_more_types_than_full(self):
        """identification preset has strictly more extraction types than full."""
        full_active = [k for k, v in EXTRACTION_PRESETS["full"].items() if v]
        ident_active = [k for k, v in EXTRACTION_PRESETS["identification"].items() if v]
        assert len(ident_active) > len(full_active)

    def test_identification_active_count(self):
        """identification preset should have 14 active extraction types."""
        active = get_active_extractions("identification")
        assert len(active) == 14


class TestFullPresetBackwardCompatibility:
    """Ensure the 'full' preset is NOT changed by the new sections."""

    def test_full_preset_does_not_include_event_context(self):
        """full preset should NOT include event_context (backward compat)."""
        full = EXTRACTION_PRESETS["full"]
        assert "event_context" not in full

    def test_full_preset_does_not_include_relationship_inference(self):
        """full preset should NOT include relationship_inference (backward compat)."""
        full = EXTRACTION_PRESETS["full"]
        assert "relationship_inference" not in full

    def test_full_preset_still_has_12_types(self):
        """full preset active count unchanged at 12."""
        active = get_active_extractions("full")
        assert len(active) == 12

    def test_full_prompt_unchanged(self):
        """full prompt does not mention event context or relationship inference."""
        prompt = build_extraction_prompt(preset="full")
        assert "Event Context" not in prompt
        assert "Relationship Inference" not in prompt

    def test_quick_preset_unaffected(self):
        """quick preset is unchanged."""
        active = get_active_extractions("quick")
        assert "event_context" not in active
        assert "relationship_inference" not in active

    def test_compare_preset_unaffected(self):
        """compare preset is unchanged."""
        active = get_active_extractions("compare")
        assert "event_context" not in active
        assert "relationship_inference" not in active


class TestEventContextPromptSection:
    """Test event_context prompt section content."""

    def test_event_context_in_identification_prompt(self):
        """Event Context section appears in identification prompt."""
        prompt = build_extraction_prompt(preset="identification")
        assert "Event Context" in prompt

    def test_event_types_listed(self):
        """Prompt lists all event types."""
        prompt = build_extraction_prompt(preset="identification")
        for event_type in [
            "wedding_ceremony",
            "wedding_reception",
            "bar_mitzvah",
            "funeral",
            "portrait",
            "formal_dinner",
            "graduation",
            "reunion",
        ]:
            assert event_type in prompt

    def test_role_indicators_listed(self):
        """Prompt mentions role types."""
        prompt = build_extraction_prompt(preset="identification")
        for role in ["bride", "groom", "mother_of_bride", "officiant"]:
            assert role in prompt

    def test_formality_levels_listed(self):
        """Prompt lists all formality levels."""
        prompt = build_extraction_prompt(preset="identification")
        for level in ["very_formal", "formal", "semi_formal", "casual", "intimate"]:
            assert level in prompt

    def test_event_context_schema_fragment(self):
        """event_context schema fragment exists and has required fields."""
        fragment = _SCHEMA_FRAGMENTS["event_context"]
        assert "event_type" in fragment
        assert "event_subtype" in fragment
        assert "role_indicators" in fragment
        assert "formality_level" in fragment

    def test_event_context_in_json_schema(self):
        """identification prompt JSON schema includes event_context."""
        prompt = build_extraction_prompt(preset="identification")
        # Find the JSON schema section
        schema_start = prompt.index("Response Format (JSON only)")
        schema_text = prompt[schema_start:]
        assert '"event_context"' in schema_text


class TestRelationshipInferencePromptSection:
    """Test relationship_inference prompt section content."""

    def test_relationship_inference_in_identification_prompt(self):
        """Relationship Inference section appears in identification prompt."""
        prompt = build_extraction_prompt(preset="identification")
        assert "Relationship Inference" in prompt

    def test_couple_pairs_mentioned(self):
        """Prompt instructs about couple pairs."""
        prompt = build_extraction_prompt(preset="identification")
        assert "Couple pairs" in prompt
        assert "romantic partners" in prompt

    def test_parent_child_pairs_mentioned(self):
        """Prompt instructs about parent-child pairs."""
        prompt = build_extraction_prompt(preset="identification")
        assert "Parent-child pairs" in prompt
        assert "age gap" in prompt.lower()

    def test_sibling_pairs_mentioned(self):
        """Prompt instructs about sibling pairs."""
        prompt = build_extraction_prompt(preset="identification")
        assert "Sibling pairs" in prompt

    def test_positioning_notes_mentioned(self):
        """Prompt requests positioning notes."""
        prompt = build_extraction_prompt(preset="identification")
        assert "Positioning notes" in prompt

    def test_confidence_scores_requested(self):
        """Prompt asks for confidence scores."""
        prompt = build_extraction_prompt(preset="identification")
        assert "confidence score" in prompt.lower()

    def test_relationship_schema_fragment(self):
        """relationship_inference schema fragment has required fields."""
        fragment = _SCHEMA_FRAGMENTS["relationship_inference"]
        assert "couple_pairs" in fragment
        assert "parent_child_pairs" in fragment
        assert "sibling_pairs" in fragment
        assert "positioning_notes" in fragment
        assert "confidence" in fragment
        assert "evidence" in fragment

    def test_relationship_inference_in_json_schema(self):
        """identification prompt JSON schema includes relationship_inference."""
        prompt = build_extraction_prompt(preset="identification")
        schema_start = prompt.index("Response Format (JSON only)")
        schema_text = prompt[schema_start:]
        assert '"relationship_inference"' in schema_text


class TestFaceCoordinatesWithNewSections:
    """Test that face coordinates are injected into the new sections."""

    SAMPLE_COORDS = [
        {"bbox": [100, 50, 200, 180]},
        {"bbox": [300, 60, 400, 190]},
        {"bbox": [500, 40, 600, 170]},
    ]

    def test_event_context_gets_face_coordinates(self):
        """event_context section receives face coordinate data."""
        prompt = build_extraction_prompt(preset="identification", face_coordinates=self.SAMPLE_COORDS)
        # The event context section should have face bounding boxes
        # Find event context section
        ec_start = prompt.index("Event Context")
        ec_section = prompt[ec_start:]
        assert "Face 0" in ec_section
        assert "bbox=[100, 50, 200, 180]" in ec_section

    def test_relationship_inference_gets_face_coordinates(self):
        """relationship_inference section receives face coordinate data."""
        prompt = build_extraction_prompt(preset="identification", face_coordinates=self.SAMPLE_COORDS)
        ri_start = prompt.index("Relationship Inference")
        ri_section = prompt[ri_start:]
        assert "Face 0" in ri_section
        assert "Face 2" in ri_section
        assert "bbox=[500, 40, 600, 170]" in ri_section

    def test_no_coords_placeholder_removed(self):
        """Without face_coordinates, placeholder is cleanly removed."""
        prompt = build_extraction_prompt(preset="identification")
        assert "{face_coordinates_section}" not in prompt

    def test_face_analysis_still_gets_coords(self):
        """face_analysis section still receives coordinates (regression check)."""
        prompt = build_extraction_prompt(preset="identification", face_coordinates=self.SAMPLE_COORDS)
        fa_start = prompt.index("Face Analysis")
        # Find next section after face analysis
        fa_section = prompt[fa_start : fa_start + 500]
        assert "bbox=[100, 50, 200, 180]" in fa_section


class TestIncludeExcludeWithNewSections:
    """Test include/exclude with the new extraction types."""

    def test_include_event_context_in_quick(self):
        """Can add event_context to quick preset via include."""
        prompt = build_extraction_prompt(preset="quick", include=["event_context"])
        assert "Event Context" in prompt

    def test_include_relationship_inference_in_full(self):
        """Can add relationship_inference to full preset via include."""
        prompt = build_extraction_prompt(preset="full", include=["relationship_inference"])
        assert "Relationship Inference" in prompt
        # Full preset fields should still be there
        assert "Date Estimation" in prompt

    def test_exclude_event_context_from_identification(self):
        """Can exclude event_context from identification preset."""
        prompt = build_extraction_prompt(preset="identification", exclude=["event_context"])
        assert "Event Context" not in prompt
        assert "Relationship Inference" in prompt  # Other new section still there

    def test_exclude_relationship_inference_from_identification(self):
        """Can exclude relationship_inference from identification preset."""
        prompt = build_extraction_prompt(preset="identification", exclude=["relationship_inference"])
        assert "Relationship Inference" not in prompt
        assert "Event Context" in prompt

    def test_get_active_with_include(self):
        """get_active_extractions works with new types in include."""
        active = get_active_extractions("full", include=["event_context", "relationship_inference"])
        assert "event_context" in active
        assert "relationship_inference" in active
        assert len(active) == 14  # 12 full + 2 new


class TestResponseParsingGraceful:
    """Test that typical Gemini response structures are valid for new sections."""

    def test_valid_event_context_response(self):
        """A well-formed event_context JSON parses correctly."""
        response = {
            "event_context": {
                "event_type": "wedding_reception",
                "event_subtype": "head table dinner",
                "role_indicators": [
                    {"face_index": 0, "roles": ["bride"]},
                    {"face_index": 1, "roles": ["groom"]},
                ],
                "formality_level": "very_formal",
            }
        }
        # Verify it's valid JSON (round-trip)
        parsed = json.loads(json.dumps(response))
        assert parsed["event_context"]["event_type"] == "wedding_reception"
        assert len(parsed["event_context"]["role_indicators"]) == 2

    def test_valid_relationship_inference_response(self):
        """A well-formed relationship_inference JSON parses correctly."""
        response = {
            "relationship_inference": {
                "couple_pairs": [{"face_indices": [0, 1], "confidence": 0.9, "evidence": "Central positioning"}],
                "parent_child_pairs": [{"parent_index": 0, "child_index": 2, "confidence": 0.7, "evidence": "Age gap"}],
                "sibling_pairs": [],
                "positioning_notes": "Central couple flanked by children",
            }
        }
        parsed = json.loads(json.dumps(response))
        assert parsed["relationship_inference"]["couple_pairs"][0]["confidence"] == 0.9
        assert len(parsed["relationship_inference"]["sibling_pairs"]) == 0

    def test_minimal_event_context_response(self):
        """Minimal event_context with only required fields parses."""
        response = {
            "event_context": {
                "event_type": "portrait",
                "event_subtype": "",
                "role_indicators": [],
                "formality_level": "formal",
            }
        }
        parsed = json.loads(json.dumps(response))
        assert parsed["event_context"]["event_type"] == "portrait"
        assert parsed["event_context"]["role_indicators"] == []

    def test_minimal_relationship_inference_response(self):
        """Minimal relationship_inference with empty lists parses."""
        response = {
            "relationship_inference": {
                "couple_pairs": [],
                "parent_child_pairs": [],
                "sibling_pairs": [],
                "positioning_notes": "",
            }
        }
        parsed = json.loads(json.dumps(response))
        assert all(
            parsed["relationship_inference"][k] == [] for k in ["couple_pairs", "parent_child_pairs", "sibling_pairs"]
        )

    def test_missing_optional_fields_graceful(self):
        """Response with missing sub-fields doesn't crash .get() access."""
        response = {
            "event_context": {
                "event_type": "casual",
            },
            "relationship_inference": {
                "positioning_notes": "Everyone standing",
            },
        }
        parsed = json.loads(json.dumps(response))
        # Accessing missing keys via .get() returns None
        assert parsed["event_context"].get("role_indicators") is None
        assert parsed["relationship_inference"].get("couple_pairs") is None
        # But present keys work fine
        assert parsed["event_context"]["event_type"] == "casual"


class TestPromptSectionRegistration:
    """Verify new sections are properly registered in all dictionaries."""

    def test_event_context_has_prompt_section(self):
        """event_context key exists in _PROMPT_SECTIONS."""
        assert "event_context" in _PROMPT_SECTIONS

    def test_event_context_has_schema_fragment(self):
        """event_context key exists in _SCHEMA_FRAGMENTS."""
        assert "event_context" in _SCHEMA_FRAGMENTS

    def test_relationship_inference_has_prompt_section(self):
        """relationship_inference key exists in _PROMPT_SECTIONS."""
        assert "relationship_inference" in _PROMPT_SECTIONS

    def test_relationship_inference_has_schema_fragment(self):
        """relationship_inference key exists in _SCHEMA_FRAGMENTS."""
        assert "relationship_inference" in _SCHEMA_FRAGMENTS

    def test_all_identification_types_have_sections(self):
        """Every type in identification preset has a prompt section."""
        for key, enabled in EXTRACTION_PRESETS["identification"].items():
            if enabled:
                assert key in _PROMPT_SECTIONS, f"Missing prompt section for {key}"
                assert key in _SCHEMA_FRAGMENTS, f"Missing schema fragment for {key}"
