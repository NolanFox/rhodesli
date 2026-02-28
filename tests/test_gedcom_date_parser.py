"""Tests for GEDCOM date parsing functions.

AD-175: Validates parse_gedcom_year() and format_lifespan() handle all
GEDCOM date formats correctly, especially the [:4] regression where
"21 SEP 1887" was sliced to "21 S".
"""
import pytest

from rhodesli_ml.graph.relationship_graph import format_lifespan, parse_gedcom_year


class TestParseGedcomYear:
    """Tests for parse_gedcom_year()."""

    def test_simple_year(self):
        assert parse_gedcom_year("1887") == "1887"

    def test_day_month_year(self):
        """Regression: [:4] produced '21 S' for this format."""
        assert parse_gedcom_year("21 SEP 1887") == "1887"

    def test_month_year(self):
        assert parse_gedcom_year("SEP 1887") == "1887"

    def test_abt_qualifier(self):
        assert parse_gedcom_year("ABT 1900") == "~1900"

    def test_about_qualifier(self):
        assert parse_gedcom_year("ABOUT 1900") == "~1900"

    def test_aft_qualifier(self):
        assert parse_gedcom_year("AFT 1930") == "aft. 1930"

    def test_after_qualifier(self):
        assert parse_gedcom_year("AFTER 1930") == "aft. 1930"

    def test_bef_qualifier(self):
        assert parse_gedcom_year("BEF 1920") == "bef. 1920"

    def test_before_qualifier(self):
        assert parse_gedcom_year("BEFORE 1920") == "bef. 1920"

    def test_bet_and_range(self):
        assert parse_gedcom_year("BET 1890 AND 1900") == "1890\u20131900"

    def test_between_full_range(self):
        assert parse_gedcom_year("BETWEEN 1890 AND 1900") == "1890\u20131900"

    def test_none_input(self):
        assert parse_gedcom_year(None) is None

    def test_empty_string(self):
        assert parse_gedcom_year("") is None

    def test_whitespace_only(self):
        assert parse_gedcom_year("   ") is None

    def test_no_year(self):
        assert parse_gedcom_year("Unknown") is None

    def test_no_four_digit_year(self):
        assert parse_gedcom_year("SEP") is None

    def test_non_string_input(self):
        assert parse_gedcom_year(42) is None

    def test_regression_no_21_s(self):
        """The exact [:4] bug: "21 SEP 1887"[:4] == "21 S"."""
        result = parse_gedcom_year("21 SEP 1887")
        assert "21 S" not in (result or "")
        assert result == "1887"

    def test_regression_no_abt_space(self):
        """[:4] bug: "ABT 1900"[:4] == "ABT "."""
        result = parse_gedcom_year("ABT 1900")
        assert result is not None
        assert "ABT " not in result

    def test_regression_no_aft_space(self):
        """[:4] bug: "AFT 1930"[:4] == "AFT "."""
        result = parse_gedcom_year("AFT 1930")
        assert result is not None
        assert "AFT " not in result

    def test_regression_no_bef_space(self):
        """[:4] bug: "BEF 1920"[:4] == "BEF "."""
        result = parse_gedcom_year("BEF 1920")
        assert result is not None
        assert "BEF " not in result


class TestFormatLifespan:
    """Tests for format_lifespan()."""

    def test_both_dates(self):
        assert format_lifespan("1887", "1944") == "1887\u20131944"

    def test_birth_only(self):
        assert format_lifespan("1887", None) == "1887\u2013"

    def test_death_only(self):
        assert format_lifespan(None, "1944") == "\u20131944"

    def test_neither(self):
        assert format_lifespan(None, None) == ""

    def test_gedcom_format_both(self):
        """GEDCOM dates should be parsed to years only."""
        result = format_lifespan("21 SEP 1887", "15 MAR 1944")
        assert result == "1887\u20131944"
        assert "SEP" not in result
        assert "MAR" not in result

    def test_gedcom_format_with_qualifier(self):
        result = format_lifespan("ABT 1900", "AFT 1960")
        assert result == "~1900\u2013aft. 1960"

    def test_empty_strings(self):
        assert format_lifespan("", "") == ""

    def test_empty_and_none(self):
        assert format_lifespan("", None) == ""
        assert format_lifespan(None, "") == ""
