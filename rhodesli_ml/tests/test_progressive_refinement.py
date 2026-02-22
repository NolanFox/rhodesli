"""Tests for progressive refinement pipeline."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# --- Fact Gathering Tests ---

class TestGatherFacts:
    """Test fact gathering from various data sources."""

    def _make_identities(self):
        return {
            "id-1": {
                "name": "Albert Cohen",
                "state": "CONFIRMED",
                "anchor_ids": ["face_001", "face_002"],
                "candidate_ids": [],
                "negative_ids": [],
                "metadata": {"birth_year": 1905},
            },
            "id-2": {
                "name": "Eleanore Cohen",
                "state": "CONFIRMED",
                "anchor_ids": ["face_003"],
                "candidate_ids": [],
                "negative_ids": [],
                "metadata": {"birth_year": 1910},
            },
            "id-3": {
                "name": "Unknown Person",
                "state": "INBOX",
                "anchor_ids": ["face_004"],
                "candidate_ids": [],
                "negative_ids": [],
                "metadata": {},
            },
            "id-merged": {
                "name": "Old Name",
                "state": "CONFIRMED",
                "anchor_ids": ["face_005"],
                "merged_into": "id-1",
                "metadata": {},
            },
        }

    def _make_photo(self):
        return {
            "path": "Image 001_compress.jpg",
            "face_ids": ["face_001", "face_003", "face_004"],
            "collection": "Vida Capeluto NYC Collection",
            "source": "Family album",
        }

    def test_gather_confirmed_people(self):
        from rhodesli_ml.scripts.progressive_refinement import gather_facts_for_photo

        facts = gather_facts_for_photo(
            "photo-1", self._make_photo(), self._make_identities(), [], []
        )

        names = [p["name"] for p in facts["confirmed_people"]]
        assert "Albert Cohen" in names
        assert "Eleanore Cohen" in names
        # INBOX people should NOT be included
        assert "Unknown Person" not in names
        # Merged identities should NOT be included
        assert "Old Name" not in names

    def test_gather_birth_years(self):
        from rhodesli_ml.scripts.progressive_refinement import gather_facts_for_photo

        facts = gather_facts_for_photo(
            "photo-1", self._make_photo(), self._make_identities(), [], []
        )

        assert facts["birth_years"]["Albert Cohen"] == 1905
        assert facts["birth_years"]["Eleanore Cohen"] == 1910

    def test_gather_relationships(self):
        from rhodesli_ml.scripts.progressive_refinement import gather_facts_for_photo

        relationships = [
            {"person_a": "id-1", "person_b": "id-2", "type": "spouse"},
        ]

        facts = gather_facts_for_photo(
            "photo-1", self._make_photo(), self._make_identities(), relationships, []
        )

        assert len(facts["relationships"]) == 1
        assert facts["relationships"][0]["type"] == "spouse"
        assert facts["relationships"][0]["person_a"] == "Albert Cohen"

    def test_gather_annotations(self):
        from rhodesli_ml.scripts.progressive_refinement import gather_facts_for_photo

        annotations = [
            {
                "target_id": "id-1",
                "type": "bio",
                "value": "Albert was a tailor in NYC",
                "status": "approved",
            },
        ]

        facts = gather_facts_for_photo(
            "photo-1", self._make_photo(), self._make_identities(), [], annotations
        )

        assert len(facts["annotations"]) == 1
        assert "tailor" in facts["annotations"][0]["value"]

    def test_count_verified_facts(self):
        from rhodesli_ml.scripts.progressive_refinement import (
            gather_facts_for_photo, count_verified_facts,
        )

        facts = gather_facts_for_photo(
            "photo-1", self._make_photo(), self._make_identities(),
            [{"person_a": "id-1", "person_b": "id-2", "type": "spouse"}],
            [{"target_id": "id-1", "type": "bio", "value": "test", "status": "approved"}],
        )

        count = count_verified_facts(facts)
        # 2 confirmed people + 2 birth years + 1 relationship + 1 annotation = 6
        assert count == 6

    def test_no_facts_for_unidentified_photo(self):
        from rhodesli_ml.scripts.progressive_refinement import (
            gather_facts_for_photo, count_verified_facts,
        )

        photo = {"face_ids": ["face_999"], "collection": "Test"}
        facts = gather_facts_for_photo("photo-2", photo, self._make_identities(), [], [])
        assert count_verified_facts(facts) == 0


# --- Prompt Builder Tests ---

class TestPromptBuilder:
    """Test enriched prompt construction."""

    def test_build_prompt_with_facts(self):
        from rhodesli_ml.scripts.progressive_refinement import build_enriched_prompt

        facts = {
            "confirmed_people": [
                {"name": "Albert Cohen", "identity_id": "id-1", "face_ids": ["f1"]},
            ],
            "birth_years": {"Albert Cohen": 1905},
            "relationships": [{"type": "spouse", "person_a": "Albert Cohen", "person_b": "Sarah Cohen"}],
            "annotations": [],
            "collection": "Vida Capeluto NYC Collection",
            "source": "",
        }

        prompt = build_enriched_prompt(facts)
        assert "Albert Cohen" in prompt
        assert "born 1905" in prompt
        assert "spouse" in prompt
        assert "Vida Capeluto NYC Collection" in prompt
        assert "decade_probabilities" in prompt  # JSON schema in template

    def test_build_prompt_no_facts(self):
        from rhodesli_ml.scripts.progressive_refinement import build_enriched_prompt

        facts = {
            "confirmed_people": [],
            "birth_years": {},
            "relationships": [],
            "annotations": [],
            "collection": "",
            "source": "",
        }

        prompt = build_enriched_prompt(facts)
        assert "No verified facts available" in prompt

    def test_build_verified_facts_section_with_annotations(self):
        from rhodesli_ml.scripts.progressive_refinement import build_verified_facts_section

        facts = {
            "confirmed_people": [
                {"name": "Albert Cohen", "identity_id": "id-1", "face_ids": ["f1"]},
            ],
            "birth_years": {},
            "relationships": [],
            "annotations": [{"target": "Albert Cohen", "type": "bio", "value": "Tailor in NYC"}],
            "collection": "",
            "source": "",
        }

        section = build_verified_facts_section(facts)
        assert "COMMUNITY ANNOTATIONS" in section
        assert "Tailor in NYC" in section


# --- Comparison Engine Tests ---

class TestCompareAnalyses:
    """Test comparison of old vs new analyses."""

    def test_no_changes(self):
        from rhodesli_ml.scripts.progressive_refinement import compare_analyses

        old = {"estimated_decade": 1940, "confidence": "medium", "probable_range": [1935, 1945]}
        new = {"estimated_decade": 1940, "confidence": "medium", "probable_range": [1935, 1945]}
        result = compare_analyses(old, new)
        assert result["has_changes"] is False

    def test_decade_change(self):
        from rhodesli_ml.scripts.progressive_refinement import compare_analyses

        old = {"estimated_decade": 1930}
        new = {"estimated_decade": 1940}
        result = compare_analyses(old, new)
        assert result["has_changes"] is True
        assert any("Decade" in imp for imp in result["improvements"])

    def test_confidence_improvement(self):
        from rhodesli_ml.scripts.progressive_refinement import compare_analyses

        old = {"estimated_decade": 1940, "confidence": "low"}
        new = {"estimated_decade": 1940, "confidence": "high"}
        result = compare_analyses(old, new)
        assert result["has_changes"] is True
        assert any("Confidence" in imp for imp in result["improvements"])

    def test_confidence_regression(self):
        from rhodesli_ml.scripts.progressive_refinement import compare_analyses

        old = {"estimated_decade": 1940, "confidence": "high"}
        new = {"estimated_decade": 1940, "confidence": "low"}
        result = compare_analyses(old, new)
        assert any("Confidence" in r for r in result["regressions"])

    def test_range_narrowing(self):
        from rhodesli_ml.scripts.progressive_refinement import compare_analyses

        old = {"estimated_decade": 1940, "probable_range": [1930, 1950]}
        new = {"estimated_decade": 1940, "probable_range": [1938, 1945]}
        result = compare_analyses(old, new)
        assert result["has_changes"] is True
        assert any("narrowed" in imp for imp in result["improvements"])


# --- Eligibility Tests ---

class TestFindEligible:
    """Test photo eligibility ranking."""

    def test_photos_ranked_by_fact_count(self):
        from rhodesli_ml.scripts.progressive_refinement import find_eligible_photos

        identities = {
            "id-1": {
                "name": "Person A", "state": "CONFIRMED",
                "anchor_ids": ["f1"], "metadata": {"birth_year": 1905},
            },
            "id-2": {
                "name": "Person B", "state": "CONFIRMED",
                "anchor_ids": ["f2"], "metadata": {},
            },
        }
        photo_index = {
            "photos": {
                "p1": {"face_ids": ["f1"], "collection": "Test"},
                "p2": {"face_ids": ["f2"], "collection": "Test"},
                "p3": {"face_ids": ["f_unknown"], "collection": "Test"},
            },
        }

        eligible = find_eligible_photos(photo_index, identities, [], [], {})

        # p1 has 2 facts (person + birth year), p2 has 1 (person only), p3 has 0
        assert len(eligible) == 2  # p3 excluded (no facts)
        assert eligible[0][0] == "p1"  # Most facts first
        assert eligible[0][3] == 2  # 1 person + 1 birth year

    def test_no_eligible_photos(self):
        from rhodesli_ml.scripts.progressive_refinement import find_eligible_photos

        eligible = find_eligible_photos(
            {"photos": {"p1": {"face_ids": ["f_unknown"]}}},
            {}, [], [], {},
        )
        assert len(eligible) == 0


# --- Pipeline Integration Tests ---

class TestRunRefinement:
    """Test the refinement pipeline with mock API."""

    def test_mock_refinement_produces_result(self, tmp_path):
        from rhodesli_ml.scripts.progressive_refinement import run_refinement

        facts = {
            "confirmed_people": [{"name": "Albert Cohen", "identity_id": "id-1", "face_ids": ["f1"]}],
            "birth_years": {"Albert Cohen": 1905},
            "relationships": [],
            "annotations": [],
            "collection": "Test",
            "source": "",
            "photo_id": "p001",
        }

        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", tmp_path / "logs"):
            (tmp_path / "logs").mkdir()
            result = run_refinement(
                "p001", {"path": "test.jpg"}, facts, {}, "gemini-test", mock=True
            )

        assert result is not None
        assert result["estimated_decade"] == 1940
        assert "_refinement_comparison" in result

    def test_missing_api_key_returns_none(self, monkeypatch):
        from rhodesli_ml.scripts.progressive_refinement import run_refinement

        facts = {"confirmed_people": [], "birth_years": {}, "relationships": [],
                 "annotations": [], "collection": "", "source": "", "photo_id": "p001"}

        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        result = run_refinement(
            "p001", {"path": "test.jpg"}, facts, {}, "gemini-test", mock=False
        )
        assert result is None


class TestDryRunSafety:
    """Test dry-run and cost safety controls."""

    def test_dry_run_limit(self):
        from rhodesli_ml.gemini_config import DRY_RUN_PHOTO_LIMIT
        assert DRY_RUN_PHOTO_LIMIT == 3

    def test_max_cost_default(self):
        from rhodesli_ml.gemini_config import MAX_COST_DEFAULT
        assert MAX_COST_DEFAULT == 1.00
