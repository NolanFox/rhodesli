"""Tests for rhodesli_ml.multi_pass — multi-pass Gemini re-analysis foundation."""

import pytest

from rhodesli_ml.multi_pass import (
    LOW_CONFIDENCE_THRESHOLD,
    build_reanalysis_prompt,
    identify_low_confidence_photos,
)


class TestIdentifyLowConfidencePhotos:
    """Tests for identify_low_confidence_photos()."""

    def test_empty_input_returns_empty(self):
        assert identify_low_confidence_photos({}) == []

    def test_all_high_confidence_returns_empty(self):
        labels = {
            "photo1": {"confidence": 0.9, "estimated_year": 1940},
            "photo2": {"confidence": 0.8, "estimated_year": 1950},
        }
        result = identify_low_confidence_photos(labels)
        assert result == []

    def test_low_confidence_included(self):
        labels = {
            "photo1": {"confidence": 0.3, "estimated_year": 1940},
            "photo2": {"confidence": 0.9, "estimated_year": 1950},
        }
        result = identify_low_confidence_photos(labels)
        assert len(result) == 1
        assert result[0]["photo_id"] == "photo1"
        assert result[0]["confidence"] == 0.3
        assert result[0]["reason"] == "below_threshold"

    def test_none_confidence_always_included(self):
        labels = {
            "photo1": {"estimated_year": 1940},
            "photo2": {"confidence": 0.9, "estimated_year": 1950},
        }
        result = identify_low_confidence_photos(labels)
        assert len(result) == 1
        assert result[0]["photo_id"] == "photo1"
        assert result[0]["confidence"] is None
        assert result[0]["reason"] == "no_confidence_score"

    def test_sorted_by_confidence_ascending_none_first(self):
        labels = {
            "a": {"confidence": 0.5, "estimated_year": 1940},
            "b": {"confidence": None, "estimated_year": 1950},
            "c": {"confidence": 0.2, "estimated_year": 1960},
        }
        result = identify_low_confidence_photos(labels)
        assert len(result) == 3
        # None confidence first, then 0.2, then 0.5
        assert result[0]["photo_id"] == "b"
        assert result[1]["photo_id"] == "c"
        assert result[2]["photo_id"] == "a"

    def test_custom_threshold(self):
        labels = {
            "photo1": {"confidence": 0.7, "estimated_year": 1940},
            "photo2": {"confidence": 0.9, "estimated_year": 1950},
        }
        # Default threshold 0.6 would exclude photo1, but 0.8 includes it
        result = identify_low_confidence_photos(labels, threshold=0.8)
        assert len(result) == 1
        assert result[0]["photo_id"] == "photo1"

    def test_best_year_estimate_fallback(self):
        """estimated_year falls back to best_year_estimate."""
        labels = {
            "photo1": {"confidence": 0.3, "best_year_estimate": 1935},
        }
        result = identify_low_confidence_photos(labels)
        assert result[0]["estimated_year"] == 1935

    def test_estimated_decade_included(self):
        labels = {
            "photo1": {"confidence": 0.3, "estimated_decade": "1940s"},
        }
        result = identify_low_confidence_photos(labels)
        assert result[0]["estimated_decade"] == "1940s"

    def test_non_numeric_confidence_skipped(self):
        """String confidence values should be skipped (not numeric)."""
        labels = {
            "photo1": {"confidence": "high", "estimated_year": 1940},
        }
        result = identify_low_confidence_photos(labels)
        assert len(result) == 0


class TestBuildReanalysisPrompt:
    """Tests for build_reanalysis_prompt()."""

    def test_basic_prompt_structure(self):
        prompt = build_reanalysis_prompt(
            photo_id="photo1",
            previous_result={"estimated_year": 1940, "confidence": 0.3},
        )
        assert "re-analyzing" in prompt.lower()
        assert "1940" in prompt
        assert "0.3" in prompt
        assert "Instructions for Re-Analysis" in prompt

    def test_includes_previous_location(self):
        prompt = build_reanalysis_prompt(
            photo_id="photo1",
            previous_result={
                "estimated_year": 1940,
                "confidence": 0.3,
                "location": {"place": "Rhodes, Greece"},
            },
        )
        assert "Rhodes, Greece" in prompt

    def test_includes_gedcom_context(self):
        prompt = build_reanalysis_prompt(
            photo_id="photo1",
            previous_result={"confidence": 0.3},
            gedcom_context="Family: Capeluto, born 1920 Rhodes",
        )
        assert "Family: Capeluto, born 1920 Rhodes" in prompt

    def test_includes_visible_text(self):
        prompt = build_reanalysis_prompt(
            photo_id="photo1",
            previous_result={"confidence": 0.3},
            visible_text="Wedding of Nace and Victoria, 1948",
        )
        assert "Wedding of Nace and Victoria, 1948" in prompt
        assert "Text Detected" in prompt

    def test_empty_previous_result(self):
        """Should not crash with empty previous result."""
        prompt = build_reanalysis_prompt(
            photo_id="photo1",
            previous_result={},
        )
        assert "re-analyzing" in prompt.lower()
        assert "Previous Analysis" in prompt

    def test_previous_decade_included(self):
        prompt = build_reanalysis_prompt(
            photo_id="photo1",
            previous_result={"estimated_decade": "1940s", "confidence": 0.4},
        )
        assert "1940s" in prompt

    def test_best_year_estimate_fallback_in_prompt(self):
        prompt = build_reanalysis_prompt(
            photo_id="photo1",
            previous_result={"best_year_estimate": 1935, "confidence": 0.2},
        )
        assert "1935" in prompt

    def test_location_without_place_key_excluded(self):
        """Location dict without 'place' should not appear."""
        prompt = build_reanalysis_prompt(
            photo_id="photo1",
            previous_result={"location": {"lat": 36.4}, "confidence": 0.3},
        )
        assert "Location:" not in prompt


class TestConstants:
    def test_default_threshold(self):
        assert LOW_CONFIDENCE_THRESHOLD == 0.6
