"""Tests for natural language archive query parsing (PRD-032)."""

import pytest


class TestNLQueryImport:
    """parse_query_intent exists and is importable."""

    def test_importable(self):
        from rhodesli_ml.nl_query import parse_query_intent

        assert callable(parse_query_intent)


class TestPersonSearch:
    """Person search intent parsing."""

    def test_find_person(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Find Nace Capeluto")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Nace Capeluto"

    def test_search_for_person(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Search for Betty Capeluto")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Betty Capeluto"

    def test_who_is_person(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Who is Vida Capeluto?")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Vida Capeluto"

    def test_capitalized_name(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Nace Capeluto")
        assert result["intent"] == "person_search"
        assert result["entities"]["name"] == "Nace Capeluto"


class TestTemporalFilter:
    """Temporal intent parsing."""

    def test_decade(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Photos from the 1940s")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["decade"] == "1940s"

    def test_single_year(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Photos from 1923")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["year"] == 1923

    def test_before_year(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Photos before 1944")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["year_end"] == 1944

    def test_year_range(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Photos from 1920 to 1940")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["year_start"] == 1920
        assert result["filters"]["year_end"] == 1940


class TestRelationship:
    """Relationship intent parsing."""

    def test_children_of(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Who are the children of Nace Capeluto?")
        assert result["intent"] == "relationship"
        assert result["relationship_type"] == "child"
        assert result["entities"]["name"] == "Nace Capeluto"

    def test_possessive_children(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Nace Capeluto's children")
        assert result["intent"] == "relationship"
        assert result["relationship_type"] == "child"

    def test_spouse_of(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("wife of Nace Capeluto")
        assert result["intent"] == "relationship"
        assert result["relationship_type"] == "spouse"


class TestLocationFilter:
    """Location-based filter parsing."""

    def test_rhodes_location(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Photos from Rhodes")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["location"] == "rhodes"

    def test_new_york_location(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Show me photos from New York")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["location"] == "new york"


class TestPhotoType:
    """Photo type filter parsing."""

    def test_wedding_photos(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("Show me wedding photos")
        assert result["intent"] == "photo_filter"
        assert result["filters"]["photo_type"] == "wedding"


class TestAggregate:
    """Aggregation intent parsing."""

    def test_how_many(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("How many photos show Nace?")
        assert result["intent"] == "aggregate"


class TestUnknownIntent:
    """Unknown/fallback intent."""

    def test_gibberish(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("asdfghjkl")
        assert result["intent"] == "unknown"
        assert result["raw_query"] == "asdfghjkl"

    def test_empty_string(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent("")
        assert result["intent"] == "unknown"

    def test_none_input(self):
        from rhodesli_ml.nl_query import parse_query_intent

        result = parse_query_intent(None)
        assert result["intent"] == "unknown"


class TestPRDFilesExist:
    """All PRD files exist and are under 300 lines."""

    @pytest.mark.parametrize(
        "prd_file",
        [
            "docs/prds/031_face_compare_tier2.md",
            "docs/prds/032_nl_archive_query.md",
            "docs/prds/033_date_estimator_standalone.md",
        ],
    )
    def test_prd_exists(self, prd_file):
        from pathlib import Path

        path = Path(prd_file)
        assert path.exists(), f"{prd_file} does not exist"
        lines = path.read_text().count("\n") + 1
        assert lines <= 300, f"{prd_file} has {lines} lines (max 300)"

    def test_fox_family_prep_exists(self):
        from pathlib import Path

        path = Path("docs/collections/fox_family_prep.md")
        assert path.exists()
        lines = path.read_text().count("\n") + 1
        assert lines <= 300, f"fox_family_prep.md has {lines} lines (max 300)"

    def test_ml_service_doc_exists(self):
        from pathlib import Path

        path = Path("docs/architecture/ML_SERVICE.md")
        assert path.exists()
        lines = path.read_text().count("\n") + 1
        assert lines <= 300, f"ML_SERVICE.md has {lines} lines (max 300)"
