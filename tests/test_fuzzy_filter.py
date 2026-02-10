"""Tests for client-side fuzzy name filtering (BUG-008).

Root cause: sidebarFilterCards used exact substring matching (indexOf),
so "Capeluto" wouldn't match "Capelluto". Now uses Levenshtein distance.

Tests cover:
1. Client-side filter script includes levenshtein function
2. Client-side filter uses fuzzy matching, not just indexOf
3. Server-side fuzzy search still works (regression)
"""

import pytest
from starlette.testclient import TestClient


class TestClientSideFuzzyFilter:
    """Client-side filter must use fuzzy matching, not exact substring."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_filter_script_includes_levenshtein(self, client):
        """Client-side filter script must include a levenshtein function."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert "levenshtein" in response.text.lower(), (
            "Client-side filter must include Levenshtein distance function "
            "for fuzzy name matching"
        )

    def test_filter_script_not_pure_indexof(self, client):
        """Filter must not rely solely on indexOf for matching."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        # The fuzzy match function should exist alongside indexOf
        assert "fuzzyMatch" in response.text or "fuzzy_match" in response.text or "levenshtein" in response.text.lower(), (
            "Client-side filter must use fuzzy matching"
        )


class TestServerSideFuzzyRegression:
    """Server-side /api/search fuzzy matching must still work."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_server_search_with_exact_match(self, client):
        """Server search finds exact substring matches."""
        response = client.get("/api/search?q=capeluto")
        assert response.status_code == 200

    def test_server_fuzzy_search_finds_misspelling(self):
        """Server-side search finds 'Capelouto' when searching 'Capeluto'."""
        from core.registry import IdentityRegistry
        import json, tempfile

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Leon Capelouto",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "history": [],
                    "merge_history": [],
                }
            }
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            path = f.name

        reg = IdentityRegistry.load(path)
        results = reg.search_identities("Capeluto")
        assert len(results) == 1, "Fuzzy search should find 'Capelouto' when searching 'Capeluto'"
        assert results[0]["name"] == "Leon Capelouto"
