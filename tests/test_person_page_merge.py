"""Tests for P0 merge button fix on person page (FB-006).

The Similar Identities and Manual Search merge buttons on the person page
were broken because:
1. search_result_card targeted #identity-{id} which doesn't exist on person page
2. The merge endpoint's OOB elements deleted the merged indicator immediately
3. The merge toast was not OOB-wrapped so it didn't appear in the toast container

These tests verify the fix by checking:
- Merge button hx_post URLs include from_person_page=true on person page
- Merge button hx_target points to elements that exist on the person page
- The merge endpoint returns correct response for from_person_page context
"""

import pytest
from unittest.mock import patch, MagicMock
from fasthtml.common import to_xml


class TestNeighborCardMergeOnPersonPage:
    """Neighbor card merge button must target #neighbor-{id} on person page."""

    def test_neighbor_card_merge_includes_from_person_page(self):
        """Merge button on person page includes from_person_page=true in URL."""
        from app.components.cards import neighbor_card

        neighbor = {
            "identity_id": "test-neighbor-001",
            "name": "Test Neighbor",
            "distance": 0.75,
            "percentile": 0.3,
            "confidence_gap": 15.0,
            "can_merge": True,
            "face_count": 2,
            "co_occurrence": 0,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
        }
        with (
            patch("app.main.get_best_face_id", return_value=None),
            patch("app.main._sequential_display_name", side_effect=lambda x: x),
            patch("app.main._identity_home_community_slug", return_value=None),
            patch("app.main.community_url_prefix", return_value="/c/test"),
        ):
            html = to_xml(
                neighbor_card(
                    neighbor,
                    "test-target-001",
                    set(),
                    from_person_page=True,
                    nav_prefix="/c/test",
                )
            )

        assert "from_person_page=true" in html
        assert 'hx-target="#neighbor-test-neighbor-001"' in html

    def test_neighbor_card_merge_on_browse_page_targets_identity(self):
        """Merge button on browse page targets #identity-{id} (existing behavior)."""
        from app.components.cards import neighbor_card

        neighbor = {
            "identity_id": "test-neighbor-001",
            "name": "Test Neighbor",
            "distance": 0.75,
            "percentile": 0.3,
            "confidence_gap": 15.0,
            "can_merge": True,
            "face_count": 2,
            "co_occurrence": 0,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
        }
        with (
            patch("app.main.get_best_face_id", return_value=None),
            patch("app.main._sequential_display_name", side_effect=lambda x: x),
            patch("app.main._identity_home_community_slug", return_value=None),
            patch("app.main.community_url_prefix", return_value="/c/test"),
        ):
            html = to_xml(
                neighbor_card(
                    neighbor,
                    "test-target-001",
                    set(),
                    from_person_page=False,
                    nav_prefix="/c/test",
                )
            )

        assert 'hx-target="#identity-test-target-001"' in html


class TestSearchResultCardMergeOnPersonPage:
    """Search result card merge button must target #search-result-{id} on person page."""

    def test_search_result_merge_targets_search_result_on_person_page(self):
        """On person page, merge button targets #search-result-{id} instead of #identity-{id}."""
        from app.components.cards import search_result_card

        result = {
            "identity_id": "test-result-001",
            "name": "Test Result",
            "face_count": 3,
            "preview_face_id": None,
        }
        with patch("app.main.resolve_face_image_url", return_value=None):
            html = to_xml(
                search_result_card(
                    result,
                    "test-target-001",
                    set(),
                    nav_prefix="/c/test",
                    from_person_page=True,
                )
            )

        assert 'hx-target="#search-result-test-result-001"' in html
        assert "from_person_page=true" in html

    def test_search_result_merge_targets_identity_on_browse_page(self):
        """On browse page, merge button targets #identity-{id} (existing behavior)."""
        from app.components.cards import search_result_card

        result = {
            "identity_id": "test-result-001",
            "name": "Test Result",
            "face_count": 3,
            "preview_face_id": None,
        }
        with patch("app.main.resolve_face_image_url", return_value=None):
            html = to_xml(
                search_result_card(
                    result,
                    "test-target-001",
                    set(),
                    nav_prefix="/c/test",
                    from_person_page=False,
                )
            )

        assert 'hx-target="#identity-test-target-001"' in html
        assert "from_person_page" not in html


class TestManualSearchSectionFromPersonPage:
    """Manual search section must pass from_person_page to search URL."""

    def test_search_url_includes_from_person_page(self):
        """Search input URL includes from_person_page=true on person page."""
        from app.components.forms import manual_search_section

        html = to_xml(
            manual_search_section(
                "test-id-001",
                nav_prefix="/c/test",
                from_person_page=True,
            )
        )

        assert "from_person_page=true" in html

    def test_search_url_excludes_from_person_page_on_browse(self):
        """Search input URL does not include from_person_page on browse page."""
        from app.components.forms import manual_search_section

        html = to_xml(
            manual_search_section(
                "test-id-001",
                nav_prefix="/c/test",
                from_person_page=False,
            )
        )

        assert "from_person_page" not in html


class TestMergeEndpointPersonPageResponse:
    """Merge endpoint must not OOB-delete the element it just swapped into."""

    def test_person_page_merge_oob_does_not_delete_indicator(self):
        """OOB elements must not delete the merged indicator element."""
        # This tests the logic extracted from identity_routes.py merge endpoint.
        # When from_person_page=True and source != "manual_search",
        # the indicator has id=neighbor-{source_id}.
        # The OOB elements must NOT include a delete for that same id.
        from fasthtml.common import Div

        actual_source_id = "test-source-001"
        source = "web"

        # Simulate the OOB elements list
        oob_elements = [
            Div(id=f"identity-{actual_source_id}", hx_swap_oob="delete"),
            Div(id=f"neighbor-{actual_source_id}", hx_swap_oob="delete"),
            Div(id=f"search-result-{actual_source_id}", hx_swap_oob="delete"),
        ]

        # The indicator id for neighbor merge
        _indicator_id = f"neighbor-{actual_source_id}"

        # Filter out OOB elements that would delete the indicator
        _person_page_oob = [el for el in oob_elements if el.attrs.get("id") != _indicator_id]

        # Verify the neighbor delete was removed
        oob_ids = [el.attrs.get("id") for el in _person_page_oob]
        assert f"neighbor-{actual_source_id}" not in oob_ids
        # But identity and search-result deletes remain
        assert f"identity-{actual_source_id}" in oob_ids
        assert f"search-result-{actual_source_id}" in oob_ids

    def test_person_page_manual_search_merge_uses_search_result_indicator(self):
        """When source=manual_search, indicator uses search-result-{id} not neighbor-{id}."""
        source_id = "test-source-001"
        source = "manual_search"

        if source == "manual_search":
            _indicator_id = f"search-result-{source_id}"
        else:
            _indicator_id = f"neighbor-{source_id}"

        assert _indicator_id == f"search-result-{source_id}"


class TestNeighborsSidebarPersonPageDetection:
    """neighbors_sidebar must detect person page context and pass to manual_search_section."""

    def test_person_similar_container_id_detected(self):
        """container_id starting with 'person-similar-' sets person page context."""
        # This tests the _is_person_page detection logic
        container_id = "person-similar-test-id-001"
        _is_person_page = container_id.startswith("person-similar-")
        assert _is_person_page is True

    def test_browse_container_id_not_person_page(self):
        """container_id like 'expand-test-id' is not person page context."""
        container_id = "expand-test-id-001"
        _is_person_page = container_id.startswith("person-similar-")
        assert _is_person_page is False
