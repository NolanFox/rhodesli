"""Tests for GEDCOM identity matching."""

import pytest
from pathlib import Path

from rhodesli_ml.importers.gedcom_parser import parse_gedcom, GedcomIndividual, GedcomEvent, ParsedDate
from rhodesli_ml.importers.identity_matcher import (
    match_gedcom_to_identities,
    normalize_name,
    extract_name_parts,
    name_similarity,
    levenshtein_distance,
    load_surname_variants,
    MatchProposal,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "test_capeluto.ged"


class TestNormalizeName:
    def test_basic(self):
        assert normalize_name("John Smith") == "john smith"

    def test_strip_prefix(self):
        assert normalize_name("Big Leon Capeluto") == "leon capeluto"

    def test_strip_suffix(self):
        assert normalize_name("John Smith Jr.") == "john smith"

    def test_strip_both(self):
        assert normalize_name("Old John Smith III") == "john smith"

    def test_empty(self):
        assert normalize_name("") == ""
        assert normalize_name(None) == ""

    def test_preserves_middle_names(self):
        assert normalize_name("Victoria Cukran Capeluto") == "victoria cukran capeluto"


class TestExtractNameParts:
    def test_two_words(self):
        first, last = extract_name_parts("Leon Capeluto")
        assert first == "leon"
        assert last == "capeluto"

    def test_three_words(self):
        first, last = extract_name_parts("Victoria Cukran Capeluto")
        assert first == "victoria cukran"
        assert last == "capeluto"

    def test_single_word(self):
        first, last = extract_name_parts("Madonna")
        assert first == ""
        assert last == "madonna"

    def test_empty(self):
        first, last = extract_name_parts("")
        assert first == ""
        assert last == ""


class TestNameSimilarity:
    def test_identical(self):
        assert name_similarity("Leon", "Leon") == 1.0

    def test_case_insensitive(self):
        assert name_similarity("leon", "Leon") == 1.0

    def test_similar(self):
        sim = name_similarity("Moise", "Mose")
        assert 0.7 < sim < 0.9

    def test_different(self):
        sim = name_similarity("Leon", "Victoria")
        assert sim < 0.5

    def test_empty(self):
        assert name_similarity("", "Leon") == 0.0
        assert name_similarity("Leon", "") == 0.0


class TestLevenshteinDistance:
    def test_identical(self):
        assert levenshtein_distance("test", "test") == 0

    def test_one_edit(self):
        assert levenshtein_distance("test", "tset") == 2  # transposition = 2 edits
        assert levenshtein_distance("test", "tests") == 1  # insertion

    def test_empty(self):
        assert levenshtein_distance("", "test") == 4
        assert levenshtein_distance("test", "") == 4


class TestLoadSurnameVariants:
    def test_loads_from_file(self):
        variants_path = Path(__file__).resolve().parent.parent.parent / "data" / "surname_variants.json"
        if not variants_path.exists():
            pytest.skip("surname_variants.json not found")
        lookup = load_surname_variants(str(variants_path))
        assert "capeluto" in lookup
        assert lookup["capuano"] == "capeluto"
        assert lookup["capelluto"] == "capeluto"

    def test_nonexistent_path(self):
        result = load_surname_variants("/nonexistent/path.json")
        assert result == {}


class TestMatchGedcomToIdentities:
    """TEST 4: Identity matching proposes matches."""

    @pytest.fixture
    def mock_identities(self):
        """Simplified identity records for testing."""
        return {
            "id-leon": {
                "identity_id": "id-leon",
                "name": "Big Leon Capeluto",
                "state": "CONFIRMED",
            },
            "id-moise": {
                "identity_id": "id-moise",
                "name": "Moise Capeluto",
                "state": "CONFIRMED",
            },
            "id-victoria-c": {
                "identity_id": "id-victoria-c",
                "name": "Victoria Cukran Capeluto",
                "state": "CONFIRMED",
            },
            "id-victoria-cap": {
                "identity_id": "id-victoria-cap",
                "name": "Victoria Capuano Capeluto",
                "state": "CONFIRMED",
            },
            "id-betty": {
                "identity_id": "id-betty",
                "name": "Betty Capeluto",
                "state": "CONFIRMED",
            },
            "id-nace": {
                "identity_id": "id-nace",
                "name": "Nace Capeluto",
                "state": "CONFIRMED",
            },
            "id-unidentified": {
                "identity_id": "id-unidentified",
                "name": "Unidentified Person 42",
                "state": "INBOX",
            },
            "id-merged": {
                "identity_id": "id-merged",
                "name": "Old Name",
                "state": "CONFIRMED",
                "merged_into": "id-leon",
            },
        }

    @pytest.fixture
    def parsed(self):
        return parse_gedcom(str(FIXTURE_PATH))

    def test_finds_matches(self, parsed, mock_identities):
        result = match_gedcom_to_identities(parsed, mock_identities)
        assert result.match_count > 0

    def test_leon_matched(self, parsed, mock_identities):
        result = match_gedcom_to_identities(parsed, mock_identities)
        leon_matches = [p for p in result.proposals if p.identity_id == "id-leon"]
        assert len(leon_matches) == 1
        assert leon_matches[0].gedcom_individual.given_name == "Leon"

    def test_maiden_name_match(self, parsed, mock_identities):
        """Victoria Cukran (GEDCOM) -> Victoria Cukran Capeluto (archive)."""
        result = match_gedcom_to_identities(parsed, mock_identities)
        vc_matches = [p for p in result.proposals if p.identity_id == "id-victoria-c"]
        assert len(vc_matches) == 1
        assert vc_matches[0].gedcom_individual.surname == "Cukran"

    def test_skips_unidentified(self, parsed, mock_identities):
        result = match_gedcom_to_identities(parsed, mock_identities)
        ids = [p.identity_id for p in result.proposals]
        assert "id-unidentified" not in ids

    def test_skips_merged(self, parsed, mock_identities):
        result = match_gedcom_to_identities(parsed, mock_identities)
        ids = [p.identity_id for p in result.proposals]
        assert "id-merged" not in ids

    def test_match_scores_are_positive(self, parsed, mock_identities):
        result = match_gedcom_to_identities(parsed, mock_identities)
        for p in result.proposals:
            assert 0 < p.match_score <= 1.0

    def test_proposals_sorted_by_score(self, parsed, mock_identities):
        result = match_gedcom_to_identities(parsed, mock_identities)
        scores = [p.match_score for p in result.proposals]
        assert scores == sorted(scores, reverse=True)

    def test_unmatched_gedcom(self, parsed, mock_identities):
        result = match_gedcom_to_identities(parsed, mock_identities)
        # Some GEDCOM individuals won't match (no archive identity)
        unmatched_names = [u.full_name for u in result.unmatched_gedcom]
        # Rahamin, Selma, Vida, Roland, etc. not in mock_identities
        assert "Rahamin Capeluto" in unmatched_names

    def test_match_proposal_to_dict(self, parsed, mock_identities):
        result = match_gedcom_to_identities(parsed, mock_identities)
        if result.proposals:
            d = result.proposals[0].to_dict()
            assert "gedcom_xref" in d
            assert "gedcom_name" in d
            assert "identity_id" in d
            assert "match_score" in d
            assert d["status"] == "pending"

    def test_birth_year_boost(self):
        """Matching with birth year proximity should boost score."""
        from rhodesli_ml.importers.gedcom_parser import ParsedGedcom, GedcomFamily

        # Create a minimal GEDCOM with one individual
        parsed = ParsedGedcom()
        indi = GedcomIndividual(
            xref_id="@I1@",
            given_name="Betty",
            surname="Capeluto",
            full_name="Betty Capeluto",
            gender="F",
            birth=GedcomEvent(
                event_type="birth",
                date=ParsedDate(year=1950, confidence="HIGH"),
            ),
        )
        parsed.individuals["@I1@"] = indi

        identities_with_year = {
            "id-betty": {
                "identity_id": "id-betty",
                "name": "Betty Capeluto",
                "state": "CONFIRMED",
                "birth_year": 1951,
            },
        }
        identities_without_year = {
            "id-betty": {
                "identity_id": "id-betty",
                "name": "Betty Capeluto",
                "state": "CONFIRMED",
            },
        }

        result_with = match_gedcom_to_identities(parsed, identities_with_year)
        result_without = match_gedcom_to_identities(parsed, identities_without_year)

        assert result_with.proposals[0].match_score > result_without.proposals[0].match_score
