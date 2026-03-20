"""Tests for Session 125 identity route fixes.

FB-163: Tag-search result rows should include community badges.
"""

from pathlib import Path


class TestTagSearchCommunityBadge:
    """FB-163: Tag search results should show community badges."""

    def test_tag_search_calls_cross_community_badge(self):
        """The tag-search route calls _cross_community_badge for each result."""
        source = Path("app/identity_routes.py").read_text()
        # Find the tag-search handler
        idx = source.index('@rt("/api/face/tag-search")')
        # Get the function body (up to the next @rt or end of a reasonable chunk)
        next_rt = source.find("@rt(", idx + 10)
        func = source[idx:next_rt] if next_rt != -1 else source[idx : idx + 5000]

        # Must call _cross_community_badge for each result row
        assert "_cross_community_badge" in func, (
            "Tag search results must call _cross_community_badge for community badge rendering"
        )

    def test_tag_search_badge_used_in_both_admin_and_nonadmin(self):
        """The cross_badge / name_row variable is used in both admin and non-admin paths."""
        source = Path("app/identity_routes.py").read_text()
        idx = source.index('@rt("/api/face/tag-search")')
        next_rt = source.find("@rt(", idx + 10)
        func = source[idx:next_rt] if next_rt != -1 else source[idx : idx + 5000]

        # The name_row variable should be computed (containing the badge)
        # and used in both the admin and non-admin button rendering
        assert "name_row" in func, "Tag search must use name_row variable containing badge"
        # name_row should appear at least 3 times: definition + admin use + non-admin use
        count = func.count("name_row")
        assert count >= 3, f"name_row should appear at least 3 times (definition + 2 uses), found {count}"

    def test_tag_search_badge_conditional_on_community(self):
        """Badge is only computed when community context exists."""
        source = Path("app/identity_routes.py").read_text()
        idx = source.index('@rt("/api/face/tag-search")')
        next_rt = source.find("@rt(", idx + 10)
        func = source[idx:next_rt] if next_rt != -1 else source[idx : idx + 5000]

        # Badge should be conditional: "if community" guard
        assert "_cross_community_badge" in func
        badge_line_idx = func.index("_cross_community_badge")
        # Find the line containing this call
        line_start = func.rfind("\n", 0, badge_line_idx) + 1
        line_end = func.find("\n", badge_line_idx)
        badge_line = func[line_start:line_end]
        assert "if community" in badge_line, (
            "Badge must be conditional on community context to avoid unnecessary lookups"
        )

    def test_tag_search_returns_results_with_names(self, client):
        """Basic tag search functionality still works (regression test)."""
        response = client.get("/api/face/tag-search?face_id=test&q=TestPerson")
        assert response.status_code == 200
        # Should include create option
        assert "create-identity" in response.text or "Create" in response.text
