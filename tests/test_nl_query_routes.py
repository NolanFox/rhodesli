"""
Tests for /tools/search — Natural Language Archive Query.

Tests cover:
- GET /tools/search returns 200 with search form
- POST /tools/search with person name returns person_search results
- POST /tools/search with temporal query returns photo results
- POST /tools/search with empty query returns helpful message
- POST /tools/search with aggregate query returns counts
- POST /tools/search with photo type query returns filtered results
- POST /tools/search with unknown query returns suggestions
- POST /tools/search with relationship query returns placeholder
- Search card appears on /tools hub page
- Archive Search appears in tools nav bar
- Executor handles None supabase client gracefully
"""

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _standard_patches():
    """Return patches that mock auth/caches for tools routes."""
    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main._build_caches"),
    ]


def _run_get(client, url):
    """Run a GET request with standard patches."""
    patches = _standard_patches()
    for p in patches:
        p.start()
    try:
        return client.get(url)
    finally:
        for p in patches:
            p.stop()


def _run_post(client, url, data=None):
    """Run a POST request with standard patches."""
    patches = _standard_patches()
    for p in patches:
        p.start()
    try:
        return client.post(url, data=data)
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# GET /tools/search
# ---------------------------------------------------------------------------


class TestSearchPageGet:
    """Tests for GET /tools/search."""

    def test_search_returns_200(self, client):
        """GET /tools/search returns HTTP 200."""
        resp = _run_get(client, "/tools/search")
        assert resp.status_code == 200

    def test_search_has_title(self, client):
        """Page title includes 'Archive Search'."""
        resp = _run_get(client, "/tools/search")
        assert "Archive Search" in resp.text

    def test_search_has_form(self, client):
        """Page contains the search form with input."""
        resp = _run_get(client, "/tools/search")
        assert 'name="q"' in resp.text
        assert "hx-post" in resp.text or "hx_post" in resp.text

    def test_search_has_example_queries(self, client):
        """Page shows example query buttons."""
        resp = _run_get(client, "/tools/search")
        assert "Nace Capeluto" in resp.text
        assert "1940s" in resp.text

    def test_search_has_tools_nav(self, client):
        """Page includes the tools navigation bar."""
        resp = _run_get(client, "/tools/search")
        assert "/tools/estimate" in resp.text
        assert "/tools/compare" in resp.text
        assert "/tools/search" in resp.text


# ---------------------------------------------------------------------------
# POST /tools/search — person search
# ---------------------------------------------------------------------------


class TestSearchPersonQuery:
    """Tests for person search queries."""

    def test_person_search_returns_results(self, client):
        """POST with 'Find Nace Capeluto' returns person results."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "identity_id": "test-id-1",
                "name": "Nace Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face-1", "face-2"],
            }
        ]
        mock_sb.table.return_value.select.return_value.ilike.return_value.neq.return_value.limit.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = _run_post(client, "/tools/search", data={"q": "Find Nace Capeluto"})

        assert resp.status_code == 200
        assert "Nace Capeluto" in resp.text
        assert "Confirmed" in resp.text
        assert "2 faces" in resp.text

    def test_person_search_no_results(self, client):
        """POST with name that matches no one returns empty message."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb.table.return_value.select.return_value.ilike.return_value.neq.return_value.limit.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = _run_post(client, "/tools/search", data={"q": "Find Nobody McNotReal"})

        assert resp.status_code == 200
        assert "0 people" in resp.text


# ---------------------------------------------------------------------------
# POST /tools/search — temporal / photo filter
# ---------------------------------------------------------------------------


class TestSearchTemporalQuery:
    """Tests for temporal photo filter queries."""

    def test_temporal_search_decade(self, client):
        """POST with 'Photos from the 1940s' returns photo results."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "photo_id": "abc123",
                "path": "Image_001.jpg",
                "source": "Vida Collection",
                "collection": "NYC Photos",
                "date_estimate": 1942,
                "upload_date": None,
            }
        ]
        # Chain: table().select().gte().lte().limit().execute()
        chain = mock_sb.table.return_value.select.return_value
        chain.gte.return_value.lte.return_value.limit.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = _run_post(client, "/tools/search", data={"q": "Photos from the 1940s"})

        assert resp.status_code == 200
        assert "1940s" in resp.text
        assert "1 photo" in resp.text


# ---------------------------------------------------------------------------
# POST /tools/search — empty query
# ---------------------------------------------------------------------------


class TestSearchEmptyQuery:
    """Tests for empty/blank queries."""

    def test_empty_query_returns_message(self, client):
        """POST with empty query returns helpful message."""
        resp = _run_post(client, "/tools/search", data={"q": ""})
        assert resp.status_code == 200
        assert "Please enter a search query" in resp.text

    def test_missing_query_returns_message(self, client):
        """POST with no q param returns helpful message."""
        resp = _run_post(client, "/tools/search", data={})
        assert resp.status_code == 200
        assert "Please enter a search query" in resp.text


# ---------------------------------------------------------------------------
# POST /tools/search — aggregate
# ---------------------------------------------------------------------------


class TestSearchAggregateQuery:
    """Tests for aggregate queries."""

    def test_aggregate_returns_counts(self, client):
        """POST with 'How many photos' returns counts."""
        mock_sb = MagicMock()

        mock_photo_result = MagicMock()
        mock_photo_result.count = 971
        mock_identity_result = MagicMock()
        mock_identity_result.count = 1654

        # photos count query
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_photo_result
        # identities count query — different chain
        mock_sb.table.return_value.select.return_value.neq.return_value.execute.return_value = mock_identity_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = _run_post(client, "/tools/search", data={"q": "How many photos are there?"})

        assert resp.status_code == 200
        # Should contain the word "photos" and "people" in the response
        assert "photos" in resp.text.lower()
        assert "people" in resp.text.lower()


# ---------------------------------------------------------------------------
# POST /tools/search — photo type filter
# ---------------------------------------------------------------------------


class TestSearchPhotoTypeQuery:
    """Tests for photo type filter queries."""

    def test_wedding_photos_filter(self, client):
        """POST with 'wedding photos' returns filtered results."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "photo_id": "wed123",
                "path": "wedding_photo.jpg",
                "source": "Wedding Album",
                "collection": "Wedding Photos",
                "date_estimate": 1935,
                "upload_date": None,
            }
        ]
        # Chain: table().select().or_().limit().execute()
        chain = mock_sb.table.return_value.select.return_value
        chain.or_.return_value.limit.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = _run_post(client, "/tools/search", data={"q": "wedding photos"})

        assert resp.status_code == 200
        assert "wedding" in resp.text.lower()


# ---------------------------------------------------------------------------
# POST /tools/search — unknown intent
# ---------------------------------------------------------------------------


class TestSearchUnknownQuery:
    """Tests for unrecognized queries."""

    def test_unknown_returns_suggestions(self, client):
        """POST with unrecognizable query returns suggestions."""
        mock_sb = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = _run_post(client, "/tools/search", data={"q": "asdfghjkl"})

        assert resp.status_code == 200
        assert "not sure" in resp.text.lower() or "try" in resp.text.lower()


# ---------------------------------------------------------------------------
# POST /tools/search — relationship (placeholder)
# ---------------------------------------------------------------------------


class TestSearchRelationshipQuery:
    """Tests for relationship queries (placeholder)."""

    def test_relationship_returns_placeholder(self, client):
        """POST with 'children of Nace Capeluto' returns coming soon message."""
        mock_sb = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = _run_post(client, "/tools/search", data={"q": "children of Nace Capeluto"})

        assert resp.status_code == 200
        assert "coming soon" in resp.text.lower()


# ---------------------------------------------------------------------------
# Tools hub page — search card
# ---------------------------------------------------------------------------


class TestToolsHubSearchCard:
    """Tests that the search card appears on the /tools hub."""

    def test_search_card_on_hub(self, client):
        """The /tools page includes an Archive Search card."""
        resp = _run_get(client, "/tools")
        assert resp.status_code == 200
        assert "Archive Search" in resp.text
        assert "/tools/search" in resp.text

    def test_search_card_has_testid(self, client):
        """The search card has the expected data-testid."""
        resp = _run_get(client, "/tools")
        assert "tool-card-search" in resp.text


# ---------------------------------------------------------------------------
# Nav bar includes search
# ---------------------------------------------------------------------------


class TestToolsNavBarSearch:
    """Tests that Archive Search appears in tools nav."""

    def test_nav_bar_has_search_link(self, client):
        """The tools nav bar includes an Archive Search link."""
        resp = _run_get(client, "/tools/search")
        assert resp.status_code == 200
        # Nav bar should have the search link
        assert "Archive Search" in resp.text


# ---------------------------------------------------------------------------
# Executor unit tests
# ---------------------------------------------------------------------------


class TestNlQueryExecutor:
    """Unit tests for the executor module."""

    def test_no_supabase_returns_message(self):
        """execute_query with None client returns unavailable message."""
        from app.nl_query_executor import execute_query

        result = execute_query({"intent": "person_search", "entities": {"name": "Test"}})
        assert result["result_type"] == "message"
        assert "unavailable" in result["message"].lower()

    def test_person_search_empty_name(self):
        """Person search with empty name returns helpful message."""
        from app.nl_query_executor import execute_query

        mock_sb = MagicMock()
        result = execute_query(
            {"intent": "person_search", "entities": {"name": ""}},
            supabase_client=mock_sb,
        )
        assert result["result_type"] == "message"
        assert "name" in result["message"].lower()

    def test_unknown_intent_returns_suggestions(self):
        """Unknown intent returns suggestion text."""
        from app.nl_query_executor import execute_query

        mock_sb = MagicMock()
        result = execute_query({"intent": "unknown", "raw_query": "blah"}, supabase_client=mock_sb)
        assert result["result_type"] == "message"
        assert "not sure" in result["message"].lower()

    def test_exception_handling(self):
        """Executor handles exceptions gracefully."""
        from app.nl_query_executor import execute_query

        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("DB error")
        result = execute_query(
            {"intent": "person_search", "entities": {"name": "Test"}},
            supabase_client=mock_sb,
        )
        assert result["result_type"] == "message"
        assert "went wrong" in result["message"].lower()

    def test_anchor_ids_string_parsing(self):
        """Person search handles anchor_ids stored as JSON strings."""
        from app.nl_query_executor import execute_query

        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {
                "identity_id": "id-1",
                "name": "Test Person",
                "state": "CONFIRMED",
                "anchor_ids": '["face-1", "face-2", "face-3"]',
            }
        ]
        mock_sb.table.return_value.select.return_value.ilike.return_value.neq.return_value.limit.return_value.execute.return_value = mock_result

        result = execute_query(
            {"intent": "person_search", "entities": {"name": "Test"}},
            supabase_client=mock_sb,
        )
        assert result["result_type"] == "persons"
        assert result["items"][0]["face_count"] == 3


class TestSecuritySanitization:
    """Session 134: Security audit findings 1 + 2 — input sanitization."""

    def test_sanitize_postgrest_strips_metacharacters(self):
        """PostgREST metacharacters (.,()) are stripped from filter values."""
        from app.nl_query_executor import _sanitize_postgrest_value

        assert _sanitize_postgrest_value("normal text") == "normal text"
        assert _sanitize_postgrest_value("evil.comma,paren(") == "evilcommaparen"
        assert _sanitize_postgrest_value("Rhodes") == "Rhodes"
        assert _sanitize_postgrest_value("New York") == "New York"

    def test_sanitize_postgrest_preserves_allowed_chars(self):
        """Apostrophes and hyphens are preserved (common in names/places)."""
        from app.nl_query_executor import _sanitize_postgrest_value

        assert _sanitize_postgrest_value("O'Brien") == "O'Brien"
        assert _sanitize_postgrest_value("Tel-Aviv") == "Tel-Aviv"

    def test_escape_ilike_wildcards(self):
        """ILIKE special characters % and _ are escaped."""
        from app.nl_query_executor import _escape_ilike

        assert _escape_ilike("normal") == "normal"
        assert _escape_ilike("100%") == r"100\%"
        assert _escape_ilike("test_name") == r"test\_name"
        assert _escape_ilike("%_%") == r"\%\_\%"

    def test_person_search_uses_escaped_ilike(self):
        """Person search escapes % and _ in name before ilike query."""
        from app.nl_query_executor import execute_query

        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb.table.return_value.select.return_value.ilike.return_value.neq.return_value.limit.return_value.execute.return_value = mock_result

        execute_query(
            {"intent": "person_search", "entities": {"name": "test%user"}},
            supabase_client=mock_sb,
        )

        # Verify ilike was called with escaped value
        ilike_call = mock_sb.table.return_value.select.return_value.ilike
        ilike_call.assert_called_once_with("name", r"%test\%user%")

    def test_sanitize_postgrest_blocks_injection_payload(self):
        """A realistic PostgREST injection payload gets fully sanitized."""
        from app.nl_query_executor import _sanitize_postgrest_value

        # This payload would alter a .or_() filter if unsanitized
        payload = "rhodes%,identity_id.eq.secret-id"
        sanitized = _sanitize_postgrest_value(payload)
        assert "," not in sanitized
        assert ".eq." not in sanitized
        assert "%" not in sanitized
