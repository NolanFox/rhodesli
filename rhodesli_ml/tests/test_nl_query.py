"""Tests for rhodesli_ml.nl_query — natural language archive query parser."""

import pytest

from rhodesli_ml.nl_query import parse_query_intent


class TestEmptyAndInvalidInput:
    def test_empty_string(self):
        result = parse_query_intent("")
        assert result["intent"] == "unknown"

    def test_none_input(self):
        result = parse_query_intent(None)
        assert result["intent"] == "unknown"

    def test_whitespace_only(self):
        result = parse_query_intent("   ")
        assert result["intent"] == "unknown"

    def test_unknown_single_lowercase_word(self):
        result = parse_query_intent("xyzzy")
        assert result["intent"] == "unknown"
        assert result["raw_query"] == "xyzzy"


class TestPersonSearch:
    def test_find_person(self):
        result = parse_query_intent("Find Nace Capeluto")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Nace Capeluto"

    def test_search_for_person(self):
        result = parse_query_intent("Search for Victoria Capeluto")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Victoria Capeluto"

    def test_who_is_person(self):
        result = parse_query_intent("Who is Albert Fox?")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Albert Fox"

    def test_capitalized_name(self):
        result = parse_query_intent("Esther Burd")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Esther Burd"

    def test_show_me_person(self):
        result = parse_query_intent("Show me Harry Fox")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Harry Fox"


class TestRelationshipQueries:
    def test_children_of(self):
        result = parse_query_intent("children of Nace Capeluto")
        assert result["intent"] == "relationship"
        assert result["relationship_type"] == "child"
        assert "Nace Capeluto" in result["entities"]["name"]

    def test_possessive_children(self):
        result = parse_query_intent("Nace's children")
        assert result["intent"] == "relationship"
        assert result["relationship_type"] == "child"

    def test_wife_of(self):
        result = parse_query_intent("wife of Albert Fox")
        assert result["intent"] == "relationship"
        assert result["relationship_type"] == "spouse"

    def test_who_are_siblings(self):
        result = parse_query_intent("who are the siblings of Esther Burd?")
        assert result["intent"] == "relationship"
        assert result["relationship_type"] == "sibling"

    def test_father_of(self):
        result = parse_query_intent("father of Charles Fox")
        assert result["intent"] == "relationship"
        assert result["relationship_type"] == "parent"


class TestTemporalQueries:
    def test_decade_1940s(self):
        result = parse_query_intent("Photos from the 1940s")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["decade"] == "1940s"

    def test_single_year(self):
        result = parse_query_intent("Photos from 1935")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["year"] == 1935

    def test_year_range(self):
        result = parse_query_intent("Photos from 1920 to 1940")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["year_start"] == 1920
        assert result["filters"]["year_end"] == 1940

    def test_before_year(self):
        # 1937 is not a decade-ending year, so it's parsed as single year
        result = parse_query_intent("Photos before 1937")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["year_end"] == 1937

    def test_after_year(self):
        # 1953 is not a decade-ending year, so it's parsed as single year
        result = parse_query_intent("Photos after 1953")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["year_start"] == 1953

    def test_decade_without_s(self):
        # 1920 matches decade pattern (ends in 0) — parsed as decade, not year
        result = parse_query_intent("Photos from 1920")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["decade"] == "1920s"


class TestLocationQueries:
    def test_rhodes(self):
        result = parse_query_intent("Photos from Rhodes")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["location"] == "rhodes"

    def test_new_york(self):
        result = parse_query_intent("Photos taken in New York")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["location"] == "new york"

    def test_congo(self):
        result = parse_query_intent("Congo photos")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["location"] == "congo"


class TestPhotoTypeQueries:
    def test_wedding_photos(self):
        result = parse_query_intent("Show wedding photos")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["photo_type"] == "wedding"

    def test_portrait(self):
        result = parse_query_intent("portrait photographs")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["photo_type"] == "portrait"

    def test_group_photo(self):
        result = parse_query_intent("group photos")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["photo_type"] == "group"


class TestAggregateQueries:
    def test_how_many(self):
        result = parse_query_intent("How many photos are there?")
        assert result["intent"] == "aggregate"

    def test_count(self):
        result = parse_query_intent("Count the wedding photos")
        assert result["intent"] == "aggregate"

    def test_total(self):
        result = parse_query_intent("Total number of identities")
        assert result["intent"] == "aggregate"


class TestEdgeCases:
    def test_special_characters_dont_crash(self):
        """Special characters should not cause exceptions."""
        result = parse_query_intent("Find O'Brien")
        assert result is not None

    def test_sql_injection_attempt(self):
        """SQL-like input should be treated as unknown or person search, not executed."""
        result = parse_query_intent("'; DROP TABLE identities; --")
        # Should not crash, intent should be unknown
        assert result["intent"] in ("unknown", "person_search")

    def test_very_long_input(self):
        result = parse_query_intent("a " * 10000)
        assert result["intent"] == "unknown"

    def test_preserves_original_casing_in_names(self):
        result = parse_query_intent("Find Nace Capeluto")
        assert result["entities"]["name"] == "Nace Capeluto"
