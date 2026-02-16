"""Tests for GEDCOM parser — date handling, individual/family extraction."""

import pytest
from pathlib import Path

from rhodesli_ml.importers.gedcom_parser import (
    parse_gedcom,
    parse_gedcom_date,
    ParsedDate,
    GedcomIndividual,
)

FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "test_capeluto.ged"


# --- Date parsing tests ---

class TestParseGedcomDate:
    """TEST 2: Messy dates parsed correctly."""

    def test_exact_full_date(self):
        result = parse_gedcom_date("15 MAR 1895")
        assert result.year == 1895
        assert result.month == 3
        assert result.day == 15
        assert result.confidence == "HIGH"
        assert result.modifier is None

    def test_month_year(self):
        result = parse_gedcom_date("MAR 1895")
        assert result.year == 1895
        assert result.month == 3
        assert result.day is None
        assert result.confidence == "HIGH"

    def test_year_only(self):
        result = parse_gedcom_date("1895")
        assert result.year == 1895
        assert result.month is None
        assert result.day is None
        assert result.confidence == "HIGH"

    def test_about(self):
        result = parse_gedcom_date("ABT 1905")
        assert result.year == 1905
        assert result.modifier == "about"
        assert result.confidence == "MEDIUM"

    def test_estimated(self):
        result = parse_gedcom_date("EST 1900")
        assert result.year == 1900
        assert result.modifier == "estimated"
        assert result.confidence == "MEDIUM"

    def test_calculated(self):
        result = parse_gedcom_date("CAL 1890")
        assert result.year == 1890
        assert result.modifier == "calculated"
        assert result.confidence == "MEDIUM"

    def test_before(self):
        result = parse_gedcom_date("BEF 1910")
        assert result.year == 1909  # Adjusted -1
        assert result.modifier == "before"
        assert result.confidence == "LOW"

    def test_after(self):
        result = parse_gedcom_date("AFT 1890")
        assert result.year == 1891  # Adjusted +1
        assert result.modifier == "after"
        assert result.confidence == "LOW"

    def test_between(self):
        result = parse_gedcom_date("BET 1890 AND 1900")
        assert result.year == 1895  # Midpoint
        assert result.modifier == "between"
        assert result.confidence == "MEDIUM"
        assert result.year_end == 1900

    def test_from_to_period(self):
        result = parse_gedcom_date("FROM 1920 TO 1945")
        assert result.year == 1932  # Midpoint
        assert result.modifier == "between"
        assert result.confidence == "MEDIUM"

    def test_interpreted(self):
        result = parse_gedcom_date("INT 1895 (about five years old in 1900 census)")
        assert result.year == 1895
        assert result.modifier == "interpreted"
        assert result.confidence == "MEDIUM"

    def test_phrase_returns_none(self):
        result = parse_gedcom_date("(Stillborn)")
        assert result is None

    def test_empty_returns_none(self):
        assert parse_gedcom_date("") is None
        assert parse_gedcom_date(None) is None

    def test_dual_year(self):
        result = parse_gedcom_date("11 FEB 1750/51")
        assert result.year == 1750
        assert result.month == 2
        assert result.day == 11

    def test_about_with_full_date(self):
        result = parse_gedcom_date("ABT 15 MAR 1895")
        assert result.year == 1895
        assert result.month == 3
        assert result.modifier == "about"

    def test_all_months(self):
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        for i, month in enumerate(months, 1):
            result = parse_gedcom_date(f"{month} 1900")
            assert result.month == i, f"Failed for {month}"


# --- GEDCOM file parsing tests ---

class TestParseGedcom:
    """TEST 1: GEDCOM parser handles valid file."""

    @pytest.fixture
    def parsed(self):
        assert FIXTURE_PATH.exists(), f"Test fixture not found: {FIXTURE_PATH}"
        return parse_gedcom(str(FIXTURE_PATH))

    def test_individual_count(self, parsed):
        assert parsed.individual_count == 14

    def test_family_count(self, parsed):
        assert parsed.family_count == 6

    def test_individual_has_name(self, parsed):
        leon = parsed.individuals["@I3@"]
        assert leon.given_name == "Leon"
        assert leon.surname == "Capeluto"
        assert leon.full_name == "Leon Capeluto"

    def test_individual_has_gender(self, parsed):
        leon = parsed.individuals["@I3@"]
        assert leon.gender == "M"
        victoria = parsed.individuals["@I8@"]
        assert victoria.gender == "F"

    def test_individual_has_birth(self, parsed):
        leon = parsed.individuals["@I3@"]
        assert leon.birth is not None
        assert leon.birth_year == 1903
        assert leon.birth_place == "Rhodes, Ottoman Empire"
        assert leon.birth.date.month == 3
        assert leon.birth.date.day == 12

    def test_individual_has_death(self, parsed):
        leon = parsed.individuals["@I3@"]
        assert leon.death is not None
        assert leon.death_year == 1982
        assert leon.death_place == "Miami, Florida, USA"

    def test_approximate_birth(self, parsed):
        moise = parsed.individuals["@I4@"]
        assert moise.birth_year == 1895
        assert moise.birth.date.modifier == "about"
        assert moise.birth.date.confidence == "MEDIUM"

    def test_between_date(self, parsed):
        nace = parsed.individuals["@I5@"]
        assert nace.birth_year == 1900  # Midpoint of 1898-1902
        assert nace.birth.date.modifier == "between"

    def test_before_death(self, parsed):
        rahamin = parsed.individuals["@I1@"]
        # BEF 1940 → year 1939
        assert rahamin.death_year == 1939
        assert rahamin.death.date.modifier == "before"

    def test_after_death(self, parsed):
        hanula = parsed.individuals["@I2@"]
        # AFT 1945 → year 1946
        assert hanula.death_year == 1946
        assert hanula.death.date.modifier == "after"


class TestRelationships:
    """TEST 3: Relationships extracted from FAM records."""

    @pytest.fixture
    def parsed(self):
        return parse_gedcom(str(FIXTURE_PATH))

    def test_parent_child(self, parsed):
        leon = parsed.individuals["@I3@"]
        parents = parsed.get_parents(leon)
        parent_names = sorted([p.full_name for p in parents])
        assert "Hanula Mosafir" in parent_names
        assert "Rahamin Capeluto" in parent_names

    def test_children(self, parsed):
        rahamin = parsed.individuals["@I1@"]
        children = parsed.get_children(rahamin)
        child_names = sorted([c.full_name for c in children])
        assert "Leon Capeluto" in child_names
        assert "Moise Capeluto" in child_names
        assert "Nace Capeluto" in child_names
        assert "Victor Capelluto" in child_names
        assert "Selma Capeluto" in child_names
        assert len(children) == 5

    def test_spouses(self, parsed):
        leon = parsed.individuals["@I3@"]
        spouses = parsed.get_spouses(leon)
        assert len(spouses) == 1
        assert spouses[0].full_name == "Victoria Capuano"

    def test_siblings(self, parsed):
        leon = parsed.individuals["@I3@"]
        siblings = parsed.get_siblings(leon)
        sibling_names = sorted([s.full_name for s in siblings])
        assert "Moise Capeluto" in sibling_names
        assert "Nace Capeluto" in sibling_names
        assert len(siblings) == 4  # Moise, Nace, Victor, Selma

    def test_marriage_event(self, parsed):
        leon = parsed.individuals["@I3@"]
        marriages = parsed.get_marriages(leon)
        assert len(marriages) == 1
        assert marriages[0].event_type == "marriage"
        assert marriages[0].date.year == 1935
        assert marriages[0].place == "New York, USA"

    def test_family_as_child(self, parsed):
        betty = parsed.individuals["@I9@"]
        assert len(betty.family_as_child) == 1
        assert betty.family_as_child[0] == "@F2@"

    def test_family_as_spouse(self, parsed):
        betty = parsed.individuals["@I9@"]
        assert len(betty.family_as_spouse) == 1
        assert betty.family_as_spouse[0] == "@F6@"


class TestParsedGedcomProperties:
    """Test ParsedGedcom convenience properties."""

    @pytest.fixture
    def parsed(self):
        return parse_gedcom(str(FIXTURE_PATH))

    def test_source_file(self, parsed):
        assert parsed.source_file == "test_capeluto.ged"

    def test_individual_birth_year_property(self, parsed):
        """Birth year property returns None when no birth event."""
        indi = GedcomIndividual(xref_id="@TEST@")
        assert indi.birth_year is None
        assert indi.death_year is None
        assert indi.birth_place is None
        assert indi.death_place is None
