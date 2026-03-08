"""Tests for Session 92 Track F: Gemini + ML fixes.

Covers:
- F1: find_business_owner_context (AD-210)
- F2-F4: log_gemini_call with new fields
- F5: identify_low_confidence_photos
- F6: find_uncertain_pairs + add_labeled_pair
"""

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Fixtures — GEDCOM test data
# =========================================================================


@dataclass
class _MockEvent:
    event_type: str = ""
    raw_date: str = ""
    place: str = ""
    date: object = None


@dataclass
class _MockDate:
    year: Optional[int] = None
    month: Optional[int] = None


@dataclass
class _MockIndividual:
    xref_id: str = ""
    given_name: str = ""
    surname: str = ""
    full_name: str = ""
    gender: str = "M"
    birth: Optional[object] = None
    death: Optional[object] = None
    events: list = field(default_factory=list)
    family_as_spouse: list = field(default_factory=list)
    family_as_child: list = field(default_factory=list)

    @property
    def birth_year(self):
        if self.birth and hasattr(self.birth, "date") and self.birth.date:
            return self.birth.date.year
        return None

    @property
    def birth_place(self):
        if self.birth:
            return self.birth.place
        return None

    @property
    def death_year(self):
        if self.death and hasattr(self.death, "date") and self.death.date:
            return self.death.date.year
        return None

    @property
    def death_place(self):
        if self.death:
            return self.death.place
        return None


@dataclass
class _MockParsedGedcom:
    individuals: dict = field(default_factory=dict)
    families: dict = field(default_factory=dict)

    def get_parents(self, indi):
        return []

    def get_children(self, indi):
        return []

    def get_spouses(self, indi):
        return []

    def get_siblings(self, indi):
        return []

    def get_marriages(self, indi):
        return []


@pytest.fixture
def leon_gedcom():
    """GEDCOM with Leon Capeluto who owned a restaurant in Asheville."""
    leon = _MockIndividual(
        xref_id="@I1@",
        given_name="Leon",
        surname="Capeluto",
        full_name="Leon Capeluto",
        birth=_MockEvent(
            event_type="birth",
            raw_date="1895",
            place="Rhodes, Greece",
            date=_MockDate(year=1895),
        ),
        events=[
            _MockEvent(
                event_type="residence",
                raw_date="1928",
                place="33 Elizabeth St, Asheville, NC",
                date=_MockDate(year=1928),
            ),
            _MockEvent(
                event_type="residence",
                raw_date="1940",
                place="Tampa, FL",
                date=_MockDate(year=1940),
            ),
            _MockEvent(
                event_type="occupation",
                raw_date="1930",
                place="Asheville, NC",
                date=_MockDate(year=1930),
            ),
        ],
    )
    victoria = _MockIndividual(
        xref_id="@I2@",
        given_name="Victoria",
        surname="Capuano",
        full_name="Victoria Capuano",
    )
    nace = _MockIndividual(
        xref_id="@I3@",
        given_name="Nace",
        surname="Capeluto",
        full_name="Nace Capeluto",
        events=[
            _MockEvent(
                event_type="residence",
                raw_date="1945",
                place="Tampa, FL",
                date=_MockDate(year=1945),
            ),
        ],
    )

    parsed = _MockParsedGedcom(
        individuals={
            "@I1@": leon,
            "@I2@": victoria,
            "@I3@": nace,
        }
    )
    return parsed


# =========================================================================
# F1: find_business_owner_context tests
# =========================================================================


class TestFindBusinessOwnerContext:
    def test_leon_restaurant_returns_leon_data(self, leon_gedcom):
        from rhodesli_ml.gedcom_context import find_business_owner_context

        result = find_business_owner_context("LEON'S RESTAURANT", leon_gedcom)
        assert result != ""
        assert "Leon Capeluto" in result
        assert "Asheville" in result
        assert "Business owner candidate" in result.lower() or "BUSINESS OWNER" in result

    def test_no_match_returns_empty(self, leon_gedcom):
        from rhodesli_ml.gedcom_context import find_business_owner_context

        result = find_business_owner_context("ACME HARDWARE STORE", leon_gedcom)
        assert result == ""

    def test_empty_text_returns_empty(self, leon_gedcom):
        from rhodesli_ml.gedcom_context import find_business_owner_context

        assert find_business_owner_context("", leon_gedcom) == ""
        assert find_business_owner_context(None, leon_gedcom) == ""

    def test_no_gedcom_returns_empty(self):
        from rhodesli_ml.gedcom_context import find_business_owner_context

        assert find_business_owner_context("LEON'S", None) == ""

    def test_short_words_ignored(self, leon_gedcom):
        """Words shorter than 3 chars should not match (too much noise)."""
        from rhodesli_ml.gedcom_context import find_business_owner_context

        # "AL" is too short to match
        result = find_business_owner_context("AL'S DINER", leon_gedcom)
        assert result == ""

    def test_surname_match(self, leon_gedcom):
        """Surname match should also work."""
        from rhodesli_ml.gedcom_context import find_business_owner_context

        result = find_business_owner_context("CAPELUTO FAMILY STORE", leon_gedcom)
        assert result != ""
        assert "Capeluto" in result

    def test_case_insensitive(self, leon_gedcom):
        """Matching should be case-insensitive."""
        from rhodesli_ml.gedcom_context import find_business_owner_context

        result = find_business_owner_context("leon's restaurant", leon_gedcom)
        assert result != ""
        assert "Leon Capeluto" in result


class TestBuildPhotoContextWithVisibleText:
    def test_visible_text_adds_business_owner_section(self, leon_gedcom):
        """build_photo_context with visible_text should include business owner context."""
        from rhodesli_ml.gedcom_context import build_photo_context

        identities = {
            "id1": {
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            }
        }
        # Even with no GEDCOM-linked faces, visible_text should add business owner
        result = build_photo_context(
            photo_id="test_photo",
            identified_faces=["face1"],
            parsed_gedcom=leon_gedcom,
            gedcom_face_links={"id1": "@I2@"},  # Victoria is linked
            identities=identities,
            visible_text="LEON'S RESTAURANT",
        )
        assert "Leon Capeluto" in result
        assert "Asheville" in result

    def test_no_visible_text_no_business_owner(self, leon_gedcom):
        """Without visible_text, no business owner section added."""
        from rhodesli_ml.gedcom_context import build_photo_context

        identities = {
            "id1": {
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            }
        }
        result = build_photo_context(
            photo_id="test_photo",
            identified_faces=["face1"],
            parsed_gedcom=leon_gedcom,
            gedcom_face_links={"id1": "@I2@"},
            identities=identities,
            visible_text=None,
        )
        # Should have Victoria (linked face) but NOT Leon's restaurant info
        assert "BUSINESS OWNER" not in result


# =========================================================================
# F2-F4: log_gemini_call with new fields
# =========================================================================


class TestLogGeminiCallNewFields:
    def test_accepts_prompt_text(self):
        """log_gemini_call should accept prompt_text parameter."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            from app.supabase_data import log_gemini_call

            result = log_gemini_call(
                photo_id="test_photo",
                model_used="gemini-2.5-pro",
                call_type="date_estimation",
                prompt_text="Analyze this photo...",
            )
            assert result is True
            call_args = mock_client.table.return_value.insert.call_args[0][0]
            assert call_args["prompt_text"] == "Analyze this photo..."

    def test_accepts_full_response(self):
        """log_gemini_call should accept full_response parameter."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            from app.supabase_data import log_gemini_call

            response = {"date_estimation": {"estimated_year": 1935}}
            result = log_gemini_call(
                photo_id="test_photo",
                model_used="gemini-2.5-pro",
                call_type="date_estimation",
                full_response=response,
            )
            assert result is True
            call_args = mock_client.table.return_value.insert.call_args[0][0]
            assert call_args["full_response"] == response

    def test_accepts_gedcom_context(self):
        """log_gemini_call should accept gedcom_context parameter."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            from app.supabase_data import log_gemini_call

            result = log_gemini_call(
                photo_id="test_photo",
                model_used="gemini-2.5-pro",
                call_type="date_estimation",
                gedcom_context="Person: Leon Capeluto\n  Residence: Asheville, NC",
            )
            assert result is True
            call_args = mock_client.table.return_value.insert.call_args[0][0]
            assert "Leon Capeluto" in call_args["gedcom_context"]

    def test_none_fields_not_included(self):
        """None values should not be included in the row."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            from app.supabase_data import log_gemini_call

            log_gemini_call(
                photo_id="test_photo",
                model_used="gemini-2.5-pro",
                call_type="date_estimation",
                prompt_text=None,
                full_response=None,
                gedcom_context=None,
            )
            call_args = mock_client.table.return_value.insert.call_args[0][0]
            assert "prompt_text" not in call_args
            assert "full_response" not in call_args
            assert "gedcom_context" not in call_args


# =========================================================================
# F5: identify_low_confidence_photos
# =========================================================================


class TestIdentifyLowConfidencePhotos:
    def test_returns_low_confidence_photos(self):
        from rhodesli_ml.multi_pass import identify_low_confidence_photos

        labels = {
            "photo_a": {"confidence": 0.3, "estimated_year": 1935},
            "photo_b": {"confidence": 0.8, "estimated_year": 1940},
            "photo_c": {"confidence": 0.5, "estimated_year": 1920},
        }
        result = identify_low_confidence_photos(labels, threshold=0.6)
        photo_ids = [r["photo_id"] for r in result]
        assert "photo_a" in photo_ids
        assert "photo_c" in photo_ids
        assert "photo_b" not in photo_ids

    def test_none_confidence_included(self):
        from rhodesli_ml.multi_pass import identify_low_confidence_photos

        labels = {
            "photo_x": {"estimated_year": 1950},  # no confidence
        }
        result = identify_low_confidence_photos(labels)
        assert len(result) == 1
        assert result[0]["photo_id"] == "photo_x"
        assert result[0]["reason"] == "no_confidence_score"

    def test_sorted_by_confidence_ascending(self):
        from rhodesli_ml.multi_pass import identify_low_confidence_photos

        labels = {
            "photo_a": {"confidence": 0.5},
            "photo_b": {"confidence": 0.2},
            "photo_c": {},  # None confidence
        }
        result = identify_low_confidence_photos(labels)
        # None first, then 0.2, then 0.5
        assert result[0]["photo_id"] == "photo_c"
        assert result[1]["photo_id"] == "photo_b"
        assert result[2]["photo_id"] == "photo_a"

    def test_empty_labels(self):
        from rhodesli_ml.multi_pass import identify_low_confidence_photos

        assert identify_low_confidence_photos({}) == []

    def test_all_high_confidence(self):
        from rhodesli_ml.multi_pass import identify_low_confidence_photos

        labels = {
            "photo_a": {"confidence": 0.9},
            "photo_b": {"confidence": 0.7},
        }
        result = identify_low_confidence_photos(labels, threshold=0.6)
        assert result == []

    def test_build_reanalysis_prompt(self):
        from rhodesli_ml.multi_pass import build_reanalysis_prompt

        prompt = build_reanalysis_prompt(
            photo_id="test",
            previous_result={
                "estimated_year": 1935,
                "confidence": 0.3,
                "location": {"place": "Tampa, FL"},
            },
            gedcom_context="Person: Leon Capeluto",
            visible_text="LEON'S RESTAURANT",
        )
        assert "1935" in prompt
        assert "0.3" in prompt
        assert "Tampa" in prompt
        assert "LEON'S RESTAURANT" in prompt
        assert "Leon Capeluto" in prompt


# =========================================================================
# F6: Active learning
# =========================================================================


class TestFindUncertainPairs:
    def test_finds_pairs_near_boundary(self):
        import numpy as np

        from rhodesli_ml.active_learning import find_uncertain_pairs

        # Create embeddings where distance between a and b is ~0.5
        emb_a = np.zeros(512)
        emb_b = np.zeros(512)
        emb_b[0] = 0.5  # distance = 0.5
        emb_c = np.ones(512)  # distance from a = sqrt(512) >> 0.6

        embeddings = {"face_a": emb_a, "face_b": emb_b, "face_c": emb_c}
        identities = {
            "id_a": {"anchor_ids": ["face_a"], "candidate_ids": []},
            "id_b": {"anchor_ids": ["face_b"], "candidate_ids": []},
            "id_c": {"anchor_ids": ["face_c"], "candidate_ids": []},
        }

        result = find_uncertain_pairs(embeddings, identities)
        assert len(result) >= 1
        pair = result[0]
        assert pair["distance"] >= 0.4
        assert pair["distance"] <= 0.6

    def test_skips_same_identity_pairs(self):
        import numpy as np

        from rhodesli_ml.active_learning import find_uncertain_pairs

        emb_a = np.zeros(512)
        emb_b = np.zeros(512)
        emb_b[0] = 0.5

        embeddings = {"face_a": emb_a, "face_b": emb_b}
        # Both faces belong to same identity
        identities = {
            "id_same": {
                "anchor_ids": ["face_a", "face_b"],
                "candidate_ids": [],
            },
        }

        result = find_uncertain_pairs(embeddings, identities)
        assert len(result) == 0

    def test_empty_embeddings(self):
        from rhodesli_ml.active_learning import find_uncertain_pairs

        assert find_uncertain_pairs({}, {}) == []


class TestAddLabeledPair:
    def test_add_new_pair(self):
        from rhodesli_ml.active_learning import add_labeled_pair

        pairs = []
        result = add_labeled_pair(pairs, "face_a", "face_b", True)
        assert len(result) == 1
        assert result[0]["face_id_a"] == "face_a"
        assert result[0]["face_id_b"] == "face_b"
        assert result[0]["is_same_person"] is True
        assert "labeled_at" in result[0]

    def test_update_existing_pair(self):
        from rhodesli_ml.active_learning import add_labeled_pair

        pairs = [
            {
                "face_id_a": "face_a",
                "face_id_b": "face_b",
                "is_same_person": True,
                "labeled_by": "admin",
                "labeled_at": "2026-01-01",
            }
        ]
        result = add_labeled_pair(pairs, "face_a", "face_b", False)
        assert len(result) == 1  # no duplicate
        assert result[0]["is_same_person"] is False

    def test_normalizes_order(self):
        from rhodesli_ml.active_learning import add_labeled_pair

        pairs = []
        result = add_labeled_pair(pairs, "face_z", "face_a", True)
        assert result[0]["face_id_a"] == "face_a"
        assert result[0]["face_id_b"] == "face_z"
