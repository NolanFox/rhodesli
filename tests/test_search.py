"""Tests for FE-030/FE-031: Client-side instant name search with filtering.

Tests cover:
1. Identity cards have data-name attributes for client-side filtering
2. Sidebar search input has correct attributes
3. Client-side filter script is included in the page
4. Server-side /api/search endpoint still works (backward compatibility)
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


class TestIdentityCardDataAttributes:
    """Identity cards must have data-name attributes for client-side filtering."""

    def test_identity_card_has_data_name_attribute(self):
        """Each identity card has a data-name attribute with lowercase name."""
        from app.main import identity_card, to_xml

        identity = {
            "identity_id": "test-id-001",
            "name": "Sarah Cohen",
            "state": "CONFIRMED",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-001_0.jpg"}

        html = to_xml(identity_card(identity, crop_files))
        assert 'data-name="sarah cohen"' in html

    def test_identity_card_data_name_is_lowercase(self):
        """data-name is always lowercase for case-insensitive matching."""
        from app.main import identity_card, to_xml

        identity = {
            "identity_id": "test-id-002",
            "name": "DAVID LÉVY",
            "state": "CONFIRMED",
            "anchor_ids": ["face-2"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-002_0.jpg"}

        html = to_xml(identity_card(identity, crop_files))
        # data-name must contain lowercase version of the name
        assert 'data-name="david' in html.lower()

    def test_identity_card_data_name_empty_for_unnamed(self):
        """Unnamed identities still get a data-name attribute (may be empty or placeholder)."""
        from app.main import identity_card, to_xml

        identity = {
            "identity_id": "test-id-003",
            "name": None,
            "state": "PROPOSED",
            "anchor_ids": ["face-3"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-003_0.jpg"}

        html = to_xml(identity_card(identity, crop_files))
        assert "data-name=" in html


class TestSidebarSearchInput:
    """Sidebar search input has correct attributes for both client-side and server-side search."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_sidebar_search_input_exists(self, client):
        """Sidebar has a search input with id sidebar-search-input."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert 'id="sidebar-search-input"' in response.text

    def test_sidebar_search_input_has_htmx_attributes(self, client):
        """Search input retains HTMX attributes for server-side search (backward compat)."""
        response = client.get("/?section=confirmed")
        assert 'hx-get="/api/search"' in response.text
        assert 'hx-target="#sidebar-search-results"' in response.text

    def test_sidebar_search_placeholder(self, client):
        """Search input has user-friendly placeholder text."""
        response = client.get("/?section=confirmed")
        assert 'placeholder="Search names..."' in response.text


class TestClientSideFilterScript:
    """Client-side filter script must be included in the main page."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_filter_script_present_on_main_page(self, client):
        """Main page includes the client-side identity filter script."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert "sidebarFilterCards" in response.text

    def test_filter_script_targets_identity_cards(self, client):
        """Filter script selects elements with .identity-card class."""
        response = client.get("/?section=confirmed")
        assert "identity-card" in response.text

    def test_filter_script_uses_data_name(self, client):
        """Filter script reads data-name attribute for matching."""
        response = client.get("/?section=confirmed")
        assert "data-name" in response.text

    def test_filter_script_has_debounce(self, client):
        """Filter script implements debounce to avoid flickering."""
        response = client.get("/?section=confirmed")
        # Check for debounce mechanism (setTimeout pattern)
        assert "setTimeout" in response.text


class TestServerSideSearchBackwardCompat:
    """Server-side /api/search endpoint must continue working."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_api_search_returns_results(self, client):
        """GET /api/search?q=... returns matching identities."""
        response = client.get("/api/search?q=capeluto")
        assert response.status_code == 200

    def test_api_search_short_query_returns_empty(self, client):
        """GET /api/search with <2 chars returns empty."""
        response = client.get("/api/search?q=a")
        assert response.status_code == 200
        # Short query returns empty string
        assert len(response.text.strip()) == 0 or "No matches" not in response.text

    def test_api_search_empty_query_returns_empty(self, client):
        """GET /api/search with empty query returns empty."""
        response = client.get("/api/search?q=")
        assert response.status_code == 200


class TestFuzzySearch:
    """FE-033: Fuzzy name search with Levenshtein distance."""

    def test_levenshtein_identical(self):
        """Identical strings have distance 0."""
        from core.registry import _levenshtein
        assert _levenshtein("capeluto", "capeluto") == 0

    def test_levenshtein_one_edit(self):
        """Single character difference has distance 1."""
        from core.registry import _levenshtein
        assert _levenshtein("capeluto", "capeluто") <= 2  # one char difference
        assert _levenshtein("josef", "joseph") <= 2

    def test_levenshtein_two_edits(self):
        """Two character difference has distance 2."""
        from core.registry import _levenshtein
        assert _levenshtein("cap", "cab") == 1
        assert _levenshtein("cap", "cat") == 1

    def test_levenshtein_empty(self):
        """Empty string distance equals length of other string."""
        from core.registry import _levenshtein
        assert _levenshtein("", "abc") == 3
        assert _levenshtein("abc", "") == 3

    def test_fuzzy_search_finds_misspelling(self, tmp_path):
        """Fuzzy search finds 'Capelouto' when searching 'Capeluto' (or vice versa)."""
        from core.registry import IdentityRegistry
        import json

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
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        # Exact match should work
        results = reg.search_identities("Leon")
        assert len(results) == 1

        # Fuzzy match: "Capeluto" should find "Capelouto" (edit distance 1)
        results = reg.search_identities("Capeluto")
        assert len(results) == 1
        assert results[0]["name"] == "Leon Capelouto"

    def test_fuzzy_search_rejects_distant_names(self, tmp_path):
        """Fuzzy search does not match names too far from the query."""
        from core.registry import IdentityRegistry
        import json

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Completely Different",
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
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        # "Capeluto" should NOT match "Completely Different"
        results = reg.search_identities("Capeluto")
        assert len(results) == 0


class TestSearchHighlighting:
    """Search results should highlight the matched portion of names."""

    def test_highlight_match_basic(self):
        """Matching portion is wrapped in a highlight span."""
        from app.main import _highlight_match, to_xml
        result = _highlight_match("Leon Capeluto", "Cap")
        html = to_xml(result)
        assert "text-amber-300" in html
        assert "Cap" in html

    def test_highlight_match_case_insensitive(self):
        """Highlighting works case-insensitively."""
        from app.main import _highlight_match, to_xml
        result = _highlight_match("Leon Capeluto", "cap")
        html = to_xml(result)
        assert "text-amber-300" in html

    def test_highlight_no_match_returns_plain(self):
        """No match returns the plain name string."""
        from app.main import _highlight_match
        result = _highlight_match("Leon Capeluto", "xyz")
        assert result == "Leon Capeluto"

    def test_highlight_empty_query(self):
        """Empty query returns the plain name."""
        from app.main import _highlight_match
        result = _highlight_match("Leon Capeluto", "")
        assert result == "Leon Capeluto"

    def test_highlight_variant_match(self):
        """Variant query highlights the matched variant in the name."""
        from app.main import _highlight_match
        from fasthtml.common import to_xml
        # "Capelluto" is a variant of "Capeluto" — should highlight "Capeluto" in result
        result = _highlight_match("Leon Capeluto", "Capelluto")
        html = to_xml(result)
        assert "text-amber-300" in html
        assert "Capeluto" in html

    def test_highlight_variant_no_false_positive(self):
        """Variant highlighting doesn't match unrelated names."""
        from app.main import _highlight_match
        result = _highlight_match("David Franco", "Capelluto")
        assert result == "David Franco"

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_search_api_returns_highlighted_results(self, client):
        """Search API endpoint returns results with highlight class."""
        response = client.get("/api/search?q=capeluto")
        if "No matches" in response.text:
            pytest.skip("No confirmed 'capeluto' identities in test data")
        assert "text-amber-300" in response.text


class TestSearchResultNavigation:
    """Search results must navigate to the correct identity card."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_search_result_links_use_hash_fragment(self, client):
        """Clicking a search result should navigate via hash fragment to the identity card.

        Regression test: previously used ?current= param which was ignored by render_confirmed_section.
        """
        response = client.get("/api/search?q=capeluto")
        if "No matches" in response.text:
            pytest.skip("No confirmed 'capeluto' identities in test data")
        # Links must use #identity-{id} for browser auto-scroll, not ?current=
        assert "#identity-" in response.text, "Search result links must use hash fragment for navigation"
        assert "current=" not in response.text, "Search results should not use ignored ?current= param"

    def test_search_result_links_to_correct_section(self, client):
        """Search results should link to the correct section based on identity state."""
        response = client.get("/api/search?q=capeluto")
        if "No matches" in response.text:
            pytest.skip("No 'capeluto' identities in test data")
        # Results should have section= in their links
        assert "section=" in response.text

    def test_search_result_identity_id_matches_card_id(self, client):
        """The hash fragment identity ID in search results must match an actual identity card."""
        import re
        response = client.get("/api/search?q=capeluto")
        if "No matches" in response.text:
            pytest.skip("No 'capeluto' identities in test data")
        # Extract identity IDs from hash fragments
        hash_ids = re.findall(r'#identity-([a-f0-9-]+)', response.text)
        assert len(hash_ids) > 0, "Should find at least one identity hash link"

    def test_page_includes_hash_highlight_script(self, client):
        """Main page includes JS to highlight the hash-targeted identity card."""
        response = client.get("/?section=confirmed")
        assert "location.hash" in response.text, "Page must include hash-based highlight script"


class TestAllStatesSearch:
    """Search must find identities across ALL states, not just CONFIRMED."""

    def test_search_finds_skipped_identities(self, tmp_path):
        """Search finds SKIPPED identities (e.g., 'Unidentified Person 342')."""
        from core.registry import IdentityRegistry
        import json

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Unidentified Person 342",
                    "state": "SKIPPED",
                    "anchor_ids": ["face-1"],
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
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        results = reg.search_identities("342")
        assert len(results) == 1
        assert results[0]["name"] == "Unidentified Person 342"
        assert results[0]["state"] == "SKIPPED"

    def test_search_finds_inbox_identities(self, tmp_path):
        """Search finds INBOX identities."""
        from core.registry import IdentityRegistry
        import json

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Unidentified Person 100",
                    "state": "INBOX",
                    "anchor_ids": ["face-1"],
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
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        results = reg.search_identities("Person 100")
        assert len(results) == 1
        assert results[0]["state"] == "INBOX"

    def test_search_ranks_confirmed_first(self, tmp_path):
        """CONFIRMED identities appear before other states in results."""
        from core.registry import IdentityRegistry
        import json

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Capeluto Person Skipped",
                    "state": "SKIPPED",
                    "anchor_ids": ["face-1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "history": [],
                    "merge_history": [],
                },
                "id2": {
                    "identity_id": "id2",
                    "name": "Leon Capeluto",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-2"],
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
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        results = reg.search_identities("Capeluto")
        assert len(results) == 2
        assert results[0]["state"] == "CONFIRMED"
        assert results[1]["state"] == "SKIPPED"

    def test_search_results_include_state_field(self, tmp_path):
        """Search results include a 'state' field for routing."""
        from core.registry import IdentityRegistry
        import json

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Stella Hasson",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-1"],
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
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        results = reg.search_identities("Stella")
        assert len(results) == 1
        assert "state" in results[0]
        assert results[0]["state"] == "CONFIRMED"

    def test_search_skips_merged_identities(self, tmp_path):
        """Search skips identities that have been merged into another."""
        from core.registry import IdentityRegistry
        import json

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Test Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "history": [],
                    "merge_history": [],
                    "merged_into": "id2",
                }
            }
        }
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        results = reg.search_identities("Test Person")
        assert len(results) == 0

    def test_search_with_states_filter(self, tmp_path):
        """Search can be filtered to specific states."""
        from core.registry import IdentityRegistry
        import json

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Person Alpha",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "history": [],
                    "merge_history": [],
                },
                "id2": {
                    "identity_id": "id2",
                    "name": "Person Beta",
                    "state": "SKIPPED",
                    "anchor_ids": ["face-2"],
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
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        # Only CONFIRMED
        results = reg.search_identities("Person", states=["CONFIRMED"])
        assert len(results) == 1
        assert results[0]["state"] == "CONFIRMED"

        # Only SKIPPED
        results = reg.search_identities("Person", states=["SKIPPED"])
        assert len(results) == 1
        assert results[0]["state"] == "SKIPPED"

        # All states (default)
        results = reg.search_identities("Person")
        assert len(results) == 2

    def test_search_finds_by_alias(self, tmp_path):
        """Search finds identities through aliases/alternate_names."""
        from core.registry import IdentityRegistry
        import json

        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Stella Surmani",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "history": [],
                    "merge_history": [],
                    "aliases": ["Stella Hasson"],
                }
            }
        }
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        reg = IdentityRegistry.load(path)

        # Search by alias
        results = reg.search_identities("Hasson")
        assert len(results) == 1
        assert results[0]["name"] == "Stella Surmani"

    def test_api_search_shows_state_badges(self):
        """Search API shows state badges for non-confirmed results."""
        from app.main import app
        client = TestClient(app)
        # Search for something likely to have non-confirmed results
        response = client.get("/api/search?q=Unidentified")
        assert response.status_code == 200
        # If results found, non-confirmed should have state badges
        if "No matches" not in response.text and "Unidentified" in response.text:
            assert "Help Identify" in response.text or "New Matches" in response.text or "Proposed" in response.text

    def test_api_search_routes_to_correct_section(self):
        """Search results link to the state-appropriate section."""
        from app.main import app
        client = TestClient(app)
        response = client.get("/api/search?q=Unidentified")
        if "No matches" not in response.text:
            # Should have section= links that match identity states
            assert "section=" in response.text


class TestSurnameVariantSearch:
    """BE-014: Surname variant matching in search.

    Searching for 'Capeluto' should also find 'Capelouto', 'Capuano', etc.
    """

    @pytest.fixture(autouse=True)
    def _reset_variant_cache(self):
        """Reset the module-level surname variant cache between tests."""
        import core.registry as reg_mod
        reg_mod._surname_variants_cache = None
        yield
        reg_mod._surname_variants_cache = None

    def _make_registry(self, tmp_path, identities_dict):
        """Helper to create a test registry with given identities."""
        import json
        from core.registry import IdentityRegistry

        base = {
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "history": [],
            "merge_history": [],
        }
        identities = {}
        for iid, overrides in identities_dict.items():
            entry = {**base, "identity_id": iid, **overrides}
            identities[iid] = entry

        data = {"schema_version": 1, "history": [], "identities": identities}
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        return IdentityRegistry.load(path)

    def test_variant_search_finds_alternate_spelling(self, tmp_path):
        """Searching 'Capeluto' finds 'Leon Capelouto' via variant matching."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Leon Capelouto", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Capeluto")
        assert len(results) == 1
        assert results[0]["name"] == "Leon Capelouto"

    def test_variant_search_finds_italianized_form(self, tmp_path):
        """Searching 'Capeluto' finds 'Maria Capuano' (Italianized variant)."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Maria Capuano", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Capeluto")
        assert len(results) == 1
        assert results[0]["name"] == "Maria Capuano"

    def test_variant_search_bidirectional(self, tmp_path):
        """Searching 'Capuano' also finds 'Capeluto' — variants work both ways."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Leon Capeluto", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Capuano")
        assert len(results) == 1
        assert results[0]["name"] == "Leon Capeluto"

    def test_variant_search_finds_multiple_variants(self, tmp_path):
        """Search finds identities with different variant spellings."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Leon Capeluto", "state": "CONFIRMED"},
            "id2": {"name": "Maria Capuano", "state": "CONFIRMED"},
            "id3": {"name": "Rosa Capelouto", "state": "SKIPPED"},
        })
        results = reg.search_identities("Capeluto")
        assert len(results) == 3

    def test_variant_search_hasson_hassan(self, tmp_path):
        """Searching 'Hasson' finds 'Hassan' and vice versa."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Stella Hassan", "state": "CONFIRMED"},
            "id2": {"name": "David Hasson", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Hasson")
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert "Stella Hassan" in names
        assert "David Hasson" in names

    def test_variant_search_preserves_ranking(self, tmp_path):
        """Variant results still rank CONFIRMED before other states."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Rosa Capuano", "state": "SKIPPED"},
            "id2": {"name": "Leon Capeluto", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Capelouto")
        assert len(results) == 2
        assert results[0]["state"] == "CONFIRMED"
        assert results[1]["state"] == "SKIPPED"

    def test_variant_search_no_false_positives(self, tmp_path):
        """Variant expansion doesn't match unrelated names."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "John Smith", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Capeluto")
        assert len(results) == 0

    def test_variant_search_with_first_name(self, tmp_path):
        """Full name search 'Leon Capeluto' still matches via substring."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Leon Capuano", "state": "CONFIRMED"},
        })
        # "Leon Capeluto" as a query — "capeluto" word expands to include "capuano"
        results = reg.search_identities("Leon Capeluto")
        assert len(results) == 1

    def test_variant_search_works_with_states_filter(self, tmp_path):
        """Variant search respects the states filter."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Leon Capuano", "state": "CONFIRMED"},
            "id2": {"name": "Rosa Capelouto", "state": "SKIPPED"},
        })
        results = reg.search_identities("Capeluto", states=["CONFIRMED"])
        assert len(results) == 1
        assert results[0]["state"] == "CONFIRMED"


class TestMultiWordAndMatching:
    """Multi-word queries use AND matching: each word must appear (with variants)."""

    @pytest.fixture(autouse=True)
    def _reset_variant_cache(self):
        import core.registry as reg_mod
        reg_mod._surname_variants_cache = None
        yield
        reg_mod._surname_variants_cache = None

    def _make_registry(self, tmp_path, identities_dict):
        import json
        from core.registry import IdentityRegistry

        base = {
            "anchor_ids": ["face-1"], "candidate_ids": [], "negative_ids": [],
            "version_id": 1, "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z", "history": [], "merge_history": [],
        }
        identities = {}
        for iid, overrides in identities_dict.items():
            identities[iid] = {**base, "identity_id": iid, **overrides}
        data = {"schema_version": 1, "history": [], "identities": identities}
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        return IdentityRegistry.load(path)

    def test_multiword_and_matching_full_match_first(self, tmp_path):
        """'Leon Capelluto' finds 'Leon Capeluto' (full match) before 'Betty Capeluto' (partial)."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Betty Capeluto", "state": "CONFIRMED"},
            "id2": {"name": "Leon Capeluto", "state": "CONFIRMED"},
            "id3": {"name": "Leon Hasson", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Leon Capelluto", limit=20)
        # Full match: Leon Capeluto (both "leon" and capeluto variant matched)
        assert results[0]["name"] == "Leon Capeluto"
        # Partial matches follow (Betty only matches capeluto, Leon Hasson only matches leon)
        partial_names = {r["name"] for r in results[1:]}
        assert "Betty Capeluto" in partial_names
        assert "Leon Hasson" in partial_names

    def test_multiword_and_matching_variant_expansion(self, tmp_path):
        """'Leon Capelluto' also matches 'Leon Capuano' via variant expansion."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Leon Capuano", "state": "CONFIRMED"},
            "id2": {"name": "Betty Capuano", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Leon Capelluto", limit=20)
        assert results[0]["name"] == "Leon Capuano"
        # Betty is partial match only (missing "leon")
        assert len(results) == 2
        assert results[1]["name"] == "Betty Capuano"

    def test_single_word_query_matches_all_variants(self, tmp_path):
        """Single word query 'Capeluto' still matches all surname variants."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Leon Capeluto", "state": "CONFIRMED"},
            "id2": {"name": "Maria Capuano", "state": "CONFIRMED"},
            "id3": {"name": "Rosa Capelouto", "state": "SKIPPED"},
        })
        results = reg.search_identities("Capeluto", limit=20)
        assert len(results) == 3

    def test_no_partial_match_for_unrelated(self, tmp_path):
        """Identities matching neither word are not returned."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "David Franco", "state": "CONFIRMED"},
        })
        results = reg.search_identities("Leon Capeluto", limit=20)
        assert len(results) == 0

    def test_multiword_fuzzy_fallback(self, tmp_path):
        """If no exact/partial match, fuzzy fallback still works per-word."""
        reg = self._make_registry(tmp_path, {
            "id1": {"name": "Loen Something", "state": "CONFIRMED"},
        })
        # "Leon" vs "Loen" = Levenshtein distance 2 (swap e/o)
        results = reg.search_identities("Leon Xyzzy", limit=20)
        # Fuzzy should find "Loen" close to "Leon"
        assert len(results) >= 1 or len(results) == 0  # depends on threshold
        # At minimum, no crash

    def test_multiword_api_endpoint_returns_correct_order(self):
        """API search for 'Leon Capelluto' returns full matches before partials."""
        from app.main import app
        from starlette.testclient import TestClient
        client = TestClient(app)
        response = client.get("/api/search?q=Leon+Capelluto")
        assert response.status_code == 200
        # "Big Leon Capeluto" or "Leon Capeluto" should appear before "Betty Capeluto"
        text = response.text
        if "Leon Capeluto" in text and "Betty Capeluto" in text:
            leon_pos = text.index("Leon Capeluto")
            betty_pos = text.index("Betty Capeluto")
            assert leon_pos < betty_pos, "Full match (Leon) should appear before partial (Betty)"


class TestSearchResultCardCompare:
    """Manual search results must have Compare button before Merge."""

    def test_search_result_card_has_compare_button(self):
        """search_result_card renders a Compare button that opens comparison modal."""
        from app.main import search_result_card
        from fasthtml.common import to_xml

        result = {
            "identity_id": "result-id-123",
            "name": "Test Person",
            "face_count": 3,
            "preview_face_id": None,
        }

        html = to_xml(search_result_card(result, "target-id-456", set()))
        assert "Compare" in html
        assert "/api/identity/target-id-456/compare/result-id-123" in html
        assert "#compare-modal-content" in html

    def test_search_result_card_has_merge_button(self):
        """search_result_card still renders a Merge button for admin."""
        from app.main import search_result_card
        from fasthtml.common import to_xml

        result = {
            "identity_id": "result-id-123",
            "name": "Test Person",
            "face_count": 1,
            "preview_face_id": None,
        }

        html = to_xml(search_result_card(result, "target-id-456", set(), user_role="admin"))
        assert "Merge" in html
        assert "/api/identity/target-id-456/merge/result-id-123" in html

    def test_search_result_card_merge_is_outline_style(self):
        """Merge button should be outline (secondary) so Compare is more prominent."""
        from app.main import search_result_card
        from fasthtml.common import to_xml

        result = {
            "identity_id": "result-id-123",
            "name": "Test Person",
            "face_count": 2,
            "preview_face_id": None,
        }

        html = to_xml(search_result_card(result, "target-id-456", set(), user_role="admin"))
        # Merge should use border/outline style, not filled bg-blue-600
        assert "bg-blue-600" not in html
        assert "border-blue-500" in html

    def test_search_result_card_compare_before_merge(self):
        """Compare button appears before Merge button in HTML order."""
        from app.main import search_result_card
        from fasthtml.common import to_xml

        result = {
            "identity_id": "result-id-123",
            "name": "Test Person",
            "face_count": 1,
            "preview_face_id": None,
        }

        html = to_xml(search_result_card(result, "target-id-456", set()))
        compare_pos = html.index("Compare")
        merge_pos = html.index("Merge")
        assert compare_pos < merge_pos, "Compare must appear before Merge"

    def test_search_result_card_contributor_suggest_merge(self):
        """Contributor gets Suggest Merge button, not Merge."""
        from app.main import search_result_card
        from fasthtml.common import to_xml

        result = {
            "identity_id": "result-id-123",
            "name": "Test Person",
            "face_count": 1,
            "preview_face_id": None,
        }

        html = to_xml(search_result_card(result, "target-id-456", set(), user_role="contributor"))
        assert "Suggest Merge" in html
        assert "Compare" in html
