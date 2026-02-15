"""Tests for Discovery Layer features (PRD 005).

Tests cover:
- _load_date_labels() — dual-key caching from rhodesli_ml/data/date_labels.json
- _load_search_index() — search index with cache_photo_id alias
- _get_decade_counts() — decade aggregation from search index
- _get_tag_counts() — tag aggregation from search index
- _search_photos() — in-memory search with match_reason
- _get_date_badge() — badge text/confidence/tooltip tuple
- _build_ai_analysis_section() — AI metadata panel rendering
- _compute_correction_priority() — priority scoring for review queue
- _get_priority_reason() — human-readable priority reason
- _load_corrections_log() / _save_corrections_log() — corrections CRUD
- POST /api/photo/{id}/correct-date — date correction endpoint
- GET /admin/review-queue — admin-only review queue
- POST /api/photo/{id}/confirm-date — admin-only date confirmation
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient
from app.auth import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_enabled():
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.auth.is_auth_enabled", return_value=True):
        yield


@pytest.fixture
def auth_disabled():
    with patch("app.main.is_auth_enabled", return_value=False), \
         patch("app.auth.is_auth_enabled", return_value=False):
        yield


@pytest.fixture
def no_user(auth_enabled):
    with patch("app.main.get_current_user", return_value=None):
        yield


@pytest.fixture
def regular_user(auth_enabled):
    user = User(id="test-user-1", email="user@example.com", is_admin=False, role="viewer")
    with patch("app.main.get_current_user", return_value=user):
        yield user


@pytest.fixture
def admin_user(auth_enabled):
    user = User(id="test-admin-1", email="admin@rhodesli.test", is_admin=True, role="admin")
    with patch("app.main.get_current_user", return_value=user):
        yield user


@pytest.fixture
def sample_date_labels():
    """Sample date labels cache keyed by photo_id."""
    return {
        "abc123": {
            "photo_id": "abc123",
            "source": "gemini",
            "estimated_decade": 1930,
            "best_year_estimate": 1935,
            "confidence": "high",
            "probable_range": [1930, 1940],
            "scene_description": "A formal studio portrait of a family.",
            "visible_text": "Rhodes 1935",
            "controlled_tags": ["studio", "portrait", "family"],
            "evidence": {
                "print_format": [
                    {"cue": "sepia tone", "strength": "strong"},
                    {"cue": "card mount", "strength": "moderate"},
                ]
            },
            "subject_ages": [30, 25, 5],
        },
        "def456": {
            "photo_id": "def456",
            "source": "gemini",
            "estimated_decade": 1920,
            "best_year_estimate": 1925,
            "confidence": "low",
            "probable_range": [1910, 1950],
            "scene_description": "Outdoor group photo near a harbor.",
            "controlled_tags": ["outdoor", "group"],
            "evidence": {},
        },
        "ghi789": {
            "photo_id": "ghi789",
            "source": "human",
            "estimated_decade": 1940,
            "best_year_estimate": 1942,
            "confidence": "high",
            "probable_range": [1940, 1944],
            "scene_description": "Wedding photo.",
            "controlled_tags": ["wedding", "formal"],
            "evidence": {},
        },
    }


@pytest.fixture
def sample_search_index():
    """Sample search index documents."""
    return [
        {
            "photo_id": "abc123",
            "cache_photo_id": "abc123",
            "searchable_text": "formal studio portrait family sepia tone",
            "controlled_tags": ["studio", "portrait", "family"],
            "estimated_decade": 1930,
        },
        {
            "photo_id": "def456",
            "cache_photo_id": "def456",
            "searchable_text": "outdoor group photo harbor waterfront",
            "controlled_tags": ["outdoor", "group"],
            "estimated_decade": 1920,
        },
        {
            "photo_id": "ghi789",
            "cache_photo_id": "ghi789",
            "searchable_text": "wedding formal ceremony bride groom",
            "controlled_tags": ["wedding", "formal"],
            "estimated_decade": 1940,
        },
        {
            "photo_id": "jkl012",
            "cache_photo_id": "jkl012",
            "searchable_text": "studio portrait child formal",
            "controlled_tags": ["studio", "portrait"],
            "estimated_decade": 1930,
        },
    ]


# ---------------------------------------------------------------------------
# _load_date_labels tests
# ---------------------------------------------------------------------------

class TestLoadDateLabels:
    """Tests for _load_date_labels() — dual-key caching."""

    def test_returns_empty_dict_when_file_missing(self):
        """When date_labels.json does not exist, returns empty dict."""
        import app.main as main_module
        main_module._date_labels_cache = None  # Reset cache
        with patch("pathlib.Path.exists", return_value=False):
            result = main_module._load_date_labels()
        assert result == {}
        main_module._date_labels_cache = None  # Clean up

    def test_returns_cached_value_on_second_call(self):
        """Once loaded, _load_date_labels returns cached dict without re-reading."""
        import app.main as main_module
        expected = {"photo1": {"estimated_decade": 1930}}
        main_module._date_labels_cache = expected
        result = main_module._load_date_labels()
        assert result is expected
        main_module._date_labels_cache = None  # Clean up

    def test_indexes_labels_by_photo_id(self, sample_date_labels):
        """Labels are keyed by their photo_id field."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels
        result = main_module._load_date_labels()
        assert "abc123" in result
        assert result["abc123"]["estimated_decade"] == 1930
        main_module._date_labels_cache = None


# ---------------------------------------------------------------------------
# _load_search_index tests
# ---------------------------------------------------------------------------

class TestLoadSearchIndex:
    """Tests for _load_search_index() — search index with cache_photo_id alias."""

    def test_returns_empty_list_when_file_missing(self):
        """When photo_search_index.json does not exist, returns empty list."""
        import app.main as main_module
        main_module._search_index_cache = None
        with patch("pathlib.Path.exists", return_value=False):
            result = main_module._load_search_index()
        assert result == []
        main_module._search_index_cache = None

    def test_returns_cached_value_on_second_call(self, sample_search_index):
        """Once loaded, _load_search_index returns cached list."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        result = main_module._load_search_index()
        assert result is sample_search_index
        main_module._search_index_cache = None

    def test_documents_have_cache_photo_id(self, sample_search_index):
        """Each document should have a cache_photo_id field."""
        for doc in sample_search_index:
            assert "cache_photo_id" in doc


# ---------------------------------------------------------------------------
# _get_decade_counts tests
# ---------------------------------------------------------------------------

class TestGetDecadeCounts:
    """Tests for _get_decade_counts() — decade aggregation."""

    def test_counts_photos_per_decade(self, sample_search_index):
        """Returns correct counts for each decade."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        counts = main_module._get_decade_counts()
        assert counts[1930] == 2  # abc123 + jkl012
        assert counts[1920] == 1  # def456
        assert counts[1940] == 1  # ghi789
        main_module._search_index_cache = None

    def test_returns_sorted_by_decade(self, sample_search_index):
        """Decades should be sorted chronologically."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        counts = main_module._get_decade_counts()
        decades = list(counts.keys())
        assert decades == sorted(decades)
        main_module._search_index_cache = None

    def test_empty_index_returns_empty_dict(self):
        """Empty search index produces no decade counts."""
        import app.main as main_module
        main_module._search_index_cache = []
        counts = main_module._get_decade_counts()
        assert counts == {}
        main_module._search_index_cache = None

    def test_skips_docs_without_decade(self):
        """Documents missing estimated_decade are not counted."""
        import app.main as main_module
        main_module._search_index_cache = [
            {"photo_id": "x", "searchable_text": "test", "controlled_tags": [], "estimated_decade": 1930},
            {"photo_id": "y", "searchable_text": "test", "controlled_tags": []},  # no decade
        ]
        counts = main_module._get_decade_counts()
        assert counts == {1930: 1}
        main_module._search_index_cache = None


# ---------------------------------------------------------------------------
# _get_tag_counts tests
# ---------------------------------------------------------------------------

class TestGetTagCounts:
    """Tests for _get_tag_counts() — tag aggregation."""

    def test_counts_photos_per_tag(self, sample_search_index):
        """Returns correct counts for each tag."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        counts = main_module._get_tag_counts()
        assert counts["studio"] == 2  # abc123 + jkl012
        assert counts["portrait"] == 2
        assert counts["family"] == 1
        assert counts["outdoor"] == 1
        assert counts["wedding"] == 1
        main_module._search_index_cache = None

    def test_sorted_by_count_descending(self, sample_search_index):
        """Tags should be sorted by count (highest first)."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        counts = main_module._get_tag_counts()
        values = list(counts.values())
        assert values == sorted(values, reverse=True)
        main_module._search_index_cache = None

    def test_empty_index_returns_empty_dict(self):
        """Empty search index produces no tag counts."""
        import app.main as main_module
        main_module._search_index_cache = []
        counts = main_module._get_tag_counts()
        assert counts == {}
        main_module._search_index_cache = None


# ---------------------------------------------------------------------------
# _search_photos tests
# ---------------------------------------------------------------------------

class TestSearchPhotos:
    """Tests for _search_photos() — in-memory search with match_reason."""

    def test_returns_all_docs_when_no_filters(self, sample_search_index):
        """No query/decade/tag returns all documents."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos()
        assert len(results) == 4
        main_module._search_index_cache = None

    def test_query_filters_by_searchable_text(self, sample_search_index):
        """Query string filters by substring match in searchable_text."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(query="harbor")
        assert len(results) == 1
        assert results[0]["photo_id"] == "def456"
        main_module._search_index_cache = None

    def test_query_is_case_insensitive(self, sample_search_index):
        """Search is case-insensitive."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(query="WEDDING")
        assert len(results) == 1
        assert results[0]["photo_id"] == "ghi789"
        main_module._search_index_cache = None

    def test_decade_filter(self, sample_search_index):
        """Decade filter returns only photos from that decade."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(decade=1930)
        assert len(results) == 2
        photo_ids = {r["photo_id"] for r in results}
        assert photo_ids == {"abc123", "jkl012"}
        main_module._search_index_cache = None

    def test_tag_filter(self, sample_search_index):
        """Tag filter returns only photos with that tag."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(tag="outdoor")
        assert len(results) == 1
        assert results[0]["photo_id"] == "def456"
        main_module._search_index_cache = None

    def test_query_and_decade_combined(self, sample_search_index):
        """Query + decade filter combine with AND logic."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        # "studio" appears in abc123 (1930s) and jkl012 (1930s) — but not def456 (1920s)
        results = main_module._search_photos(query="studio", decade=1920)
        assert len(results) == 0  # No studio photos in the 1920s
        main_module._search_index_cache = None

    def test_query_and_tag_combined(self, sample_search_index):
        """Query + tag filter combine with AND logic."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(query="formal", tag="family")
        assert len(results) == 1
        assert results[0]["photo_id"] == "abc123"
        main_module._search_index_cache = None

    def test_match_reason_tags_when_query_matches_tag(self, sample_search_index):
        """match_reason is 'tags' when query matches a controlled tag."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(query="studio")
        for r in results:
            assert r["match_reason"] == "tags"
        main_module._search_index_cache = None

    def test_match_reason_scene_when_query_matches_text_only(self, sample_search_index):
        """match_reason is 'scene' when query matches searchable_text but not tags."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(query="harbor")
        assert len(results) == 1
        assert results[0]["match_reason"] == "scene"
        main_module._search_index_cache = None

    def test_match_reason_none_when_no_query(self, sample_search_index):
        """match_reason is None when no text query is applied."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(decade=1930)
        for r in results:
            assert r["match_reason"] is None
        main_module._search_index_cache = None

    def test_empty_query_string_treated_as_no_query(self, sample_search_index):
        """Empty string query returns all docs (no text filter)."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(query="")
        assert len(results) == 4
        main_module._search_index_cache = None

    def test_no_results_for_nonexistent_query(self, sample_search_index):
        """Query that matches nothing returns empty list."""
        import app.main as main_module
        main_module._search_index_cache = sample_search_index
        results = main_module._search_photos(query="xylophone")
        assert len(results) == 0
        main_module._search_index_cache = None


# ---------------------------------------------------------------------------
# _get_date_badge tests
# ---------------------------------------------------------------------------

class TestGetDateBadge:
    """Tests for _get_date_badge() — badge text/confidence/tooltip tuple."""

    def test_returns_badge_for_known_photo(self, sample_date_labels):
        """Returns (badge_text, confidence, tooltip) for a photo with a label."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels
        badge_text, confidence, tooltip = main_module._get_date_badge("abc123")
        assert badge_text == "c. 1930s"
        assert confidence == "high"
        assert "1935" in tooltip
        assert "1930" in tooltip
        assert "1940" in tooltip
        main_module._date_labels_cache = None

    def test_returns_none_tuple_for_unknown_photo(self, sample_date_labels):
        """Returns (None, None, None) for a photo with no label."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels
        result = main_module._get_date_badge("nonexistent_photo")
        assert result == (None, None, None)
        main_module._date_labels_cache = None

    def test_returns_none_tuple_when_no_decade(self):
        """Returns (None, None, None) when label exists but has no decade."""
        import app.main as main_module
        main_module._date_labels_cache = {
            "nodecade": {"photo_id": "nodecade", "confidence": "low"}
        }
        result = main_module._get_date_badge("nodecade")
        assert result == (None, None, None)
        main_module._date_labels_cache = None

    def test_tooltip_format_with_year_and_range(self, sample_date_labels):
        """Tooltip shows 'Best estimate: YEAR (range: START-END)'."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels
        _, _, tooltip = main_module._get_date_badge("abc123")
        assert tooltip.startswith("Best estimate: 1935")
        assert "range:" in tooltip
        main_module._date_labels_cache = None

    def test_tooltip_fallback_without_year(self):
        """Tooltip falls back to 'Estimated: DECADEs' when no best_year."""
        import app.main as main_module
        main_module._date_labels_cache = {
            "noyr": {"photo_id": "noyr", "estimated_decade": 1950, "confidence": "medium"}
        }
        _, _, tooltip = main_module._get_date_badge("noyr")
        assert "1950s" in tooltip
        main_module._date_labels_cache = None


# ---------------------------------------------------------------------------
# _build_ai_analysis_section tests
# ---------------------------------------------------------------------------

class TestBuildAiAnalysisSection:
    """Tests for _build_ai_analysis_section() — AI metadata panel rendering."""

    def test_returns_none_when_no_label(self, sample_date_labels):
        """Returns None when photo has no date label."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = []
        result = main_module._build_ai_analysis_section("nonexistent_photo")
        assert result is None
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_returns_section_with_ai_analysis_testid(self, sample_date_labels, sample_search_index):
        """Returns a Section with data_testid='ai-analysis'."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        assert section is not None
        html = to_xml(section)
        assert 'data-testid="ai-analysis"' in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_contains_ai_analysis_heading(self, sample_date_labels, sample_search_index):
        """Section contains 'AI Analysis' heading."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        assert "AI Analysis" in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_shows_date_estimate(self, sample_date_labels, sample_search_index):
        """Section shows the date estimate value."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        assert "1935" in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_shows_scene_description(self, sample_date_labels, sample_search_index):
        """Section shows the scene description."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        assert "formal studio portrait" in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_shows_tags_as_pills(self, sample_date_labels, sample_search_index):
        """Section shows controlled tags with ai-tag testid."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        assert 'data-testid="ai-tag"' in html
        assert "studio" in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_shows_visible_text(self, sample_date_labels, sample_search_index):
        """Section shows visible text when present."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        assert "Rhodes 1935" in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_shows_evidence_cues(self, sample_date_labels, sample_search_index):
        """Section shows dating evidence with cue text."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        assert "sepia tone" in html
        assert "card mount" in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_shows_subject_ages(self, sample_date_labels, sample_search_index):
        """Section shows subject ages when present."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        assert "30" in html
        assert "25" in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_human_verified_label_shows_verified_provenance(self, sample_date_labels, sample_search_index):
        """Human-verified label shows 'Verified' and emerald styling."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("ghi789")
        html = to_xml(section)
        assert "Verified" in html
        assert 'data-provenance="human"' in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_ai_estimated_label_shows_ai_provenance(self, sample_date_labels, sample_search_index):
        """AI-estimated label shows 'AI Estimated' and data-provenance='ai'."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        # The date section has AI provenance for gemini-sourced labels
        assert 'data-provenance="ai"' in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    def test_correction_pencil_button_present(self, sample_date_labels, sample_search_index):
        """Section includes the correction pencil button."""
        import app.main as main_module
        from fasthtml.common import to_xml
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index
        section = main_module._build_ai_analysis_section("abc123")
        html = to_xml(section)
        assert 'data-testid="correct-date"' in html
        main_module._date_labels_cache = None
        main_module._search_index_cache = None


# ---------------------------------------------------------------------------
# _compute_correction_priority tests
# ---------------------------------------------------------------------------

class TestComputeCorrectionPriority:
    """Tests for _compute_correction_priority() — priority scoring."""

    def test_high_confidence_narrow_range_low_priority(self):
        """High confidence + narrow range = low priority score."""
        import app.main as main_module
        label = {"confidence": "high", "probable_range": [1930, 1940]}
        score = main_module._compute_correction_priority(label)
        # (1 - 0.9) * (10/50) * (1 + 0) = 0.1 * 0.2 * 1.0 = 0.02
        assert abs(score - 0.02) < 0.001

    def test_low_confidence_wide_range_high_priority(self):
        """Low confidence + wide range = high priority score."""
        import app.main as main_module
        label = {"confidence": "low", "probable_range": [1910, 1950]}
        score = main_module._compute_correction_priority(label)
        # (1 - 0.3) * (40/50) * (1 + 0) = 0.7 * 0.8 * 1.0 = 0.56
        assert abs(score - 0.56) < 0.001

    def test_medium_confidence_default(self):
        """Medium confidence uses 0.6 numeric value."""
        import app.main as main_module
        label = {"confidence": "medium", "probable_range": [1920, 1940]}
        score = main_module._compute_correction_priority(label)
        # (1 - 0.6) * (20/50) * (1 + 0) = 0.4 * 0.4 * 1.0 = 0.16
        assert abs(score - 0.16) < 0.001

    def test_missing_range_defaults_to_20(self):
        """Missing probable_range defaults to width 20."""
        import app.main as main_module
        label = {"confidence": "medium"}
        score = main_module._compute_correction_priority(label)
        # (1 - 0.6) * (20/50) * (1 + 0) = 0.4 * 0.4 * 1.0 = 0.16
        assert abs(score - 0.16) < 0.001

    def test_unknown_confidence_defaults_to_0_5(self):
        """Unknown confidence string defaults to 0.5."""
        import app.main as main_module
        label = {"confidence": "unknown_level", "probable_range": [1920, 1970]}
        score = main_module._compute_correction_priority(label)
        # (1 - 0.5) * (50/50) * (1 + 0) = 0.5 * 1.0 * 1.0 = 0.5
        assert abs(score - 0.5) < 0.001

    def test_low_confidence_always_higher_than_high_confidence(self):
        """Low confidence labels always have higher priority than high confidence."""
        import app.main as main_module
        low = main_module._compute_correction_priority(
            {"confidence": "low", "probable_range": [1920, 1940]}
        )
        high = main_module._compute_correction_priority(
            {"confidence": "high", "probable_range": [1920, 1940]}
        )
        assert low > high


# ---------------------------------------------------------------------------
# _get_priority_reason tests
# ---------------------------------------------------------------------------

class TestGetPriorityReason:
    """Tests for _get_priority_reason() — human-readable priority reason."""

    def test_low_confidence_reason(self):
        """Low confidence label shows 'Low confidence' reason."""
        import app.main as main_module
        label = {"confidence": "low", "probable_range": [1930, 1940]}
        reason = main_module._get_priority_reason(label)
        assert "Low confidence" in reason

    def test_wide_range_reason(self):
        """Wide date range (>=15 years) shows range in reason."""
        import app.main as main_module
        label = {"confidence": "medium", "probable_range": [1910, 1950]}
        reason = main_module._get_priority_reason(label)
        assert "Wide date range" in reason
        assert "1910" in reason
        assert "1950" in reason

    def test_both_reasons_combined(self):
        """Low confidence + wide range shows both reasons joined."""
        import app.main as main_module
        label = {"confidence": "low", "probable_range": [1910, 1950]}
        reason = main_module._get_priority_reason(label)
        assert "Low confidence" in reason
        assert "Wide date range" in reason

    def test_routine_review_when_no_flags(self):
        """High confidence + narrow range shows 'Routine review'."""
        import app.main as main_module
        label = {"confidence": "high", "probable_range": [1930, 1935]}
        reason = main_module._get_priority_reason(label)
        assert reason == "Routine review"

    def test_no_range_means_no_wide_range_reason(self):
        """Missing probable_range does not trigger 'Wide date range'."""
        import app.main as main_module
        label = {"confidence": "high"}
        reason = main_module._get_priority_reason(label)
        assert "Wide date range" not in reason


# ---------------------------------------------------------------------------
# _load_corrections_log / _save_corrections_log tests
# ---------------------------------------------------------------------------

class TestCorrectionsLog:
    """Tests for _load_corrections_log and _save_corrections_log."""

    def test_load_returns_empty_schema_when_no_file(self, tmp_path):
        """Loading from nonexistent file returns default schema."""
        import app.main as main_module
        with patch.object(main_module, "data_path", tmp_path):
            result = main_module._load_corrections_log()
        assert result == {"schema_version": 1, "corrections": []}

    def test_load_reads_existing_file(self, tmp_path):
        """Loading from existing file returns its contents."""
        import app.main as main_module
        corrections = {"schema_version": 1, "corrections": [{"id": "corr_1"}]}
        (tmp_path / "corrections_log.json").write_text(json.dumps(corrections))
        with patch.object(main_module, "data_path", tmp_path):
            result = main_module._load_corrections_log()
        assert len(result["corrections"]) == 1
        assert result["corrections"][0]["id"] == "corr_1"

    def test_save_and_reload(self, tmp_path):
        """Save followed by load returns the same data."""
        import app.main as main_module
        data = {"schema_version": 1, "corrections": [{"id": "corr_test", "photo_id": "abc"}]}
        with patch.object(main_module, "data_path", tmp_path):
            main_module._save_corrections_log(data)
            result = main_module._load_corrections_log()
        assert result == data

    def test_load_handles_corrupt_file(self, tmp_path):
        """Loading corrupt JSON returns default schema."""
        import app.main as main_module
        (tmp_path / "corrections_log.json").write_text("{invalid json!!!")
        with patch.object(main_module, "data_path", tmp_path):
            result = main_module._load_corrections_log()
        assert result == {"schema_version": 1, "corrections": []}


# ---------------------------------------------------------------------------
# POST /api/photo/{id}/correct-date endpoint tests
# ---------------------------------------------------------------------------

class TestCorrectDateEndpoint:
    """Tests for POST /api/photo/{photo_id}/correct-date."""

    def test_correct_date_auth_disabled(self, client, auth_disabled, sample_date_labels):
        """When auth disabled, correction succeeds."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels.copy()
        mock_save = MagicMock()
        with patch.object(main_module, "_load_corrections_log", return_value={"schema_version": 1, "corrections": []}), \
             patch.object(main_module, "_save_corrections_log", mock_save):
            response = client.post("/api/photo/abc123/correct-date", data={"correction_year": 1938})
        assert response.status_code == 200
        mock_save.assert_called_once()
        main_module._date_labels_cache = None

    def test_correct_date_requires_login(self, client, no_user):
        """Returns 401 when user is not logged in."""
        response = client.post("/api/photo/abc123/correct-date", data={"correction_year": 1938})
        assert response.status_code == 401

    def test_correct_date_regular_user_succeeds(self, client, regular_user, sample_date_labels):
        """Logged-in non-admin user can submit corrections."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels.copy()
        mock_save = MagicMock()
        with patch.object(main_module, "_load_corrections_log", return_value={"schema_version": 1, "corrections": []}), \
             patch.object(main_module, "_save_corrections_log", mock_save):
            response = client.post("/api/photo/abc123/correct-date", data={"correction_year": 1938})
        assert response.status_code == 200
        mock_save.assert_called_once()
        # Verify the logged correction has 'registered' contributor type
        saved_data = mock_save.call_args[0][0]
        correction = saved_data["corrections"][0]
        assert correction["contributor_type"] == "registered"
        assert correction["contributor_email"] == "user@example.com"
        main_module._date_labels_cache = None

    def test_correct_date_invalid_year_rejected(self, client, auth_disabled, sample_date_labels):
        """Year outside 1850-2030 returns error message."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels.copy()
        response = client.post("/api/photo/abc123/correct-date", data={"correction_year": 1800})
        assert response.status_code == 200
        assert "Invalid year" in response.text
        main_module._date_labels_cache = None

    def test_correct_date_no_year_rejected(self, client, auth_disabled, sample_date_labels):
        """Missing correction_year returns error message."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels.copy()
        response = client.post("/api/photo/abc123/correct-date", data={})
        assert response.status_code == 200
        assert "Invalid year" in response.text
        main_module._date_labels_cache = None

    def test_correct_date_unknown_photo_returns_error(self, client, auth_disabled):
        """Correction for unknown photo_id returns 'No date label found'."""
        import app.main as main_module
        main_module._date_labels_cache = {}
        response = client.post("/api/photo/unknown_photo/correct-date", data={"correction_year": 1935})
        assert response.status_code == 200
        assert "No date label found" in response.text
        main_module._date_labels_cache = None

    def test_correct_date_updates_cache(self, client, auth_disabled, sample_date_labels):
        """Correction updates the in-memory label cache."""
        import app.main as main_module
        labels = {k: dict(v) for k, v in sample_date_labels.items()}
        main_module._date_labels_cache = labels
        mock_save = MagicMock()
        with patch.object(main_module, "_load_corrections_log", return_value={"schema_version": 1, "corrections": []}), \
             patch.object(main_module, "_save_corrections_log", mock_save):
            response = client.post("/api/photo/abc123/correct-date", data={"correction_year": 1942})
        assert response.status_code == 200
        # The in-memory cache should be updated
        assert labels["abc123"]["best_year_estimate"] == 1942
        assert labels["abc123"]["estimated_decade"] == 1940
        assert labels["abc123"]["source"] == "human"
        assert labels["abc123"]["confidence"] == "high"
        main_module._date_labels_cache = None

    def test_correct_date_logs_correction_entry(self, client, auth_disabled, sample_date_labels):
        """Correction is appended to the corrections log."""
        import app.main as main_module
        labels = {k: dict(v) for k, v in sample_date_labels.items()}
        main_module._date_labels_cache = labels
        mock_save = MagicMock()
        with patch.object(main_module, "_load_corrections_log", return_value={"schema_version": 1, "corrections": []}), \
             patch.object(main_module, "_save_corrections_log", mock_save):
            client.post("/api/photo/abc123/correct-date", data={"correction_year": 1938})
        saved_data = mock_save.call_args[0][0]
        correction = saved_data["corrections"][0]
        assert correction["photo_id"] == "abc123"
        assert correction["field"] == "estimated_decade"
        assert correction["status"] == "applied"
        assert correction["new_source"] == "human"
        assert correction["new_value"]["year"] == 1938
        assert correction["new_value"]["decade"] == 1930
        assert correction["old_value"]["decade"] == 1930
        assert correction["old_value"]["year"] == 1935
        main_module._date_labels_cache = None


# ---------------------------------------------------------------------------
# GET /admin/review-queue route tests
# ---------------------------------------------------------------------------

class TestReviewQueueRoute:
    """Tests for GET /admin/review-queue — admin-only."""

    def test_review_queue_requires_admin_auth_enabled(self, client, no_user):
        """Returns 401 for unauthenticated user when auth is enabled."""
        response = client.get("/admin/review-queue")
        assert response.status_code == 401

    def test_review_queue_forbidden_for_regular_user(self, client, regular_user):
        """Returns 403 for non-admin user."""
        response = client.get("/admin/review-queue")
        assert response.status_code == 403

    def test_review_queue_accessible_auth_disabled(self, client, auth_disabled, sample_date_labels):
        """When auth disabled, admin routes pass through."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels
        response = client.get("/admin/review-queue")
        assert response.status_code == 200
        assert "Review Queue" in response.text
        main_module._date_labels_cache = None

    def test_review_queue_shows_unverified_photos(self, client, auth_disabled, sample_date_labels):
        """Queue shows photos with source != 'human'."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels
        response = client.get("/admin/review-queue")
        assert response.status_code == 200
        # abc123 (gemini) and def456 (gemini) should appear, ghi789 (human) should not
        assert "photos need review" in response.text
        main_module._date_labels_cache = None

    def test_review_queue_excludes_human_verified(self, client, auth_disabled):
        """Human-verified labels are excluded from the review queue."""
        import app.main as main_module
        main_module._date_labels_cache = {
            "verified1": {"photo_id": "verified1", "source": "human", "estimated_decade": 1930,
                          "best_year_estimate": 1935, "confidence": "high", "probable_range": [1930, 1940]},
        }
        response = client.get("/admin/review-queue")
        assert response.status_code == 200
        # "0 photos need review" since all are human-verified
        assert "0 photos need review" in response.text
        main_module._date_labels_cache = None

    def test_review_queue_sorted_by_priority(self, client, auth_disabled):
        """Review items are sorted by priority score (highest first)."""
        import app.main as main_module
        main_module._date_labels_cache = {
            "high_priority": {
                "photo_id": "high_priority", "source": "gemini", "confidence": "low",
                "estimated_decade": 1920, "best_year_estimate": 1925,
                "probable_range": [1910, 1950],
            },
            "low_priority": {
                "photo_id": "low_priority", "source": "gemini", "confidence": "high",
                "estimated_decade": 1930, "best_year_estimate": 1935,
                "probable_range": [1930, 1940],
            },
        }
        response = client.get("/admin/review-queue")
        assert response.status_code == 200
        html = response.text
        # High priority should appear before low priority
        high_pos = html.find("high_pri")
        low_pos = html.find("low_prio")
        assert high_pos < low_pos, "High priority item should appear first"
        main_module._date_labels_cache = None

    def test_review_queue_has_confirm_button(self, client, auth_disabled, sample_date_labels):
        """Each review item has a 'Confirm AI' button."""
        import app.main as main_module
        main_module._date_labels_cache = sample_date_labels
        response = client.get("/admin/review-queue")
        assert response.status_code == 200
        assert "Confirm AI" in response.text
        main_module._date_labels_cache = None

    def test_review_queue_empty_shows_all_reviewed(self, client, auth_disabled):
        """Empty label set shows 'All photos have been reviewed!'."""
        import app.main as main_module
        main_module._date_labels_cache = {}
        response = client.get("/admin/review-queue")
        assert response.status_code == 200
        assert "All photos have been reviewed" in response.text
        main_module._date_labels_cache = None


# ---------------------------------------------------------------------------
# POST /api/photo/{id}/confirm-date endpoint tests
# ---------------------------------------------------------------------------

class TestConfirmDateEndpoint:
    """Tests for POST /api/photo/{photo_id}/confirm-date — admin-only."""

    def test_confirm_date_requires_admin(self, client, no_user):
        """Returns 401 for unauthenticated user."""
        response = client.post("/api/photo/abc123/confirm-date")
        assert response.status_code == 401

    def test_confirm_date_forbidden_for_regular_user(self, client, regular_user):
        """Returns 403 for non-admin user."""
        response = client.post("/api/photo/abc123/confirm-date")
        assert response.status_code == 403

    def test_confirm_date_succeeds_auth_disabled(self, client, auth_disabled, sample_date_labels):
        """When auth disabled, confirm succeeds."""
        import app.main as main_module
        labels = {k: dict(v) for k, v in sample_date_labels.items()}
        main_module._date_labels_cache = labels
        mock_save = MagicMock()
        with patch.object(main_module, "_load_corrections_log", return_value={"schema_version": 1, "corrections": []}), \
             patch.object(main_module, "_save_corrections_log", mock_save):
            response = client.post("/api/photo/abc123/confirm-date")
        assert response.status_code == 200
        assert "Confirmed" in response.text
        mock_save.assert_called_once()
        main_module._date_labels_cache = None

    def test_confirm_date_sets_source_to_human(self, client, auth_disabled, sample_date_labels):
        """Confirming sets source to 'human' in the in-memory cache."""
        import app.main as main_module
        labels = {k: dict(v) for k, v in sample_date_labels.items()}
        main_module._date_labels_cache = labels
        mock_save = MagicMock()
        with patch.object(main_module, "_load_corrections_log", return_value={"schema_version": 1, "corrections": []}), \
             patch.object(main_module, "_save_corrections_log", mock_save):
            client.post("/api/photo/abc123/confirm-date")
        assert labels["abc123"]["source"] == "human"
        main_module._date_labels_cache = None

    def test_confirm_date_does_not_change_values(self, client, auth_disabled, sample_date_labels):
        """Confirming preserves the original decade and year (only changes source)."""
        import app.main as main_module
        labels = {k: dict(v) for k, v in sample_date_labels.items()}
        main_module._date_labels_cache = labels
        mock_save = MagicMock()
        with patch.object(main_module, "_load_corrections_log", return_value={"schema_version": 1, "corrections": []}), \
             patch.object(main_module, "_save_corrections_log", mock_save):
            client.post("/api/photo/abc123/confirm-date")
        assert labels["abc123"]["estimated_decade"] == 1930
        assert labels["abc123"]["best_year_estimate"] == 1935
        main_module._date_labels_cache = None

    def test_confirm_date_logs_confirmation(self, client, auth_disabled, sample_date_labels):
        """Confirmation is logged with status 'confirmed'."""
        import app.main as main_module
        labels = {k: dict(v) for k, v in sample_date_labels.items()}
        main_module._date_labels_cache = labels
        mock_save = MagicMock()
        with patch.object(main_module, "_load_corrections_log", return_value={"schema_version": 1, "corrections": []}), \
             patch.object(main_module, "_save_corrections_log", mock_save):
            client.post("/api/photo/abc123/confirm-date")
        saved_data = mock_save.call_args[0][0]
        correction = saved_data["corrections"][0]
        assert correction["status"] == "confirmed"
        assert correction["new_source"] == "human"
        assert correction["photo_id"] == "abc123"
        main_module._date_labels_cache = None

    def test_confirm_date_unknown_photo_returns_error(self, client, auth_disabled):
        """Confirming unknown photo_id returns 'Label not found'."""
        import app.main as main_module
        main_module._date_labels_cache = {}
        response = client.post("/api/photo/unknown_photo/confirm-date")
        assert response.status_code == 200
        assert "Label not found" in response.text
        main_module._date_labels_cache = None


# ---------------------------------------------------------------------------
# Photo Context modal includes AI Analysis
# ---------------------------------------------------------------------------

class TestPhotoContextModalAIAnalysis:
    """Verify AI Analysis section appears in the Photo Context modal partial."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_modal_includes_ai_analysis(self, mock_reg, mock_dim, mock_meta, sample_date_labels, sample_search_index):
        """Photo context modal partial includes AI Analysis section when labels exist."""
        import app.main as main_module
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test Collection",
        }
        mock_reg.return_value = MagicMock()
        main_module._date_labels_cache = sample_date_labels
        main_module._search_index_cache = sample_search_index

        result = photo_view_content("abc123", is_partial=True)
        html = to_xml(result)

        assert "AI Analysis" in html
        assert 'data-testid="ai-analysis"' in html
        assert "circa 1935" in html

        main_module._date_labels_cache = None
        main_module._search_index_cache = None

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_modal_omits_ai_analysis_when_no_labels(self, mock_reg, mock_dim, mock_meta):
        """Photo context modal omits AI Analysis when no labels exist for photo."""
        import app.main as main_module
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test Collection",
        }
        mock_reg.return_value = MagicMock()
        main_module._date_labels_cache = {}
        main_module._search_index_cache = []

        result = photo_view_content("unknown_photo", is_partial=True)
        html = to_xml(result)

        assert "AI Analysis" not in html
        assert 'data-testid="ai-analysis"' not in html

        main_module._date_labels_cache = None
        main_module._search_index_cache = None
