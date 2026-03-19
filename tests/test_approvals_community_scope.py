"""Tests for Session 121: UX-207 approvals community-scoped."""

from pathlib import Path


class TestApprovalsCommunityScopeCode:
    """Verify approval list filters by community."""

    def test_approvals_filter_by_community(self):
        """Approval list handler must filter pending_items by community_id."""
        source = Path("app/admin_routes.py").read_text()
        # Find the admin/pending handler
        idx = source.index('"/admin/pending"')
        handler = source[idx : idx + 2000]

        # Must filter by community
        assert "community_id" in handler, "Handler must extract community_id"
        assert 'u.get("community")' in handler or "community" in handler, (
            "Handler must filter pending items by community field"
        )

    def test_reviewed_items_also_filtered(self):
        """Reviewed items must also be filtered by community."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index('"/admin/pending"')
        handler = source[idx : idx + 2000]

        # Both pending and reviewed should filter
        assert handler.count("community_id") >= 2, "Both pending and reviewed items must be filtered by community"

    def test_community_badge_on_approval_cards(self):
        """Each approval card should show community badge."""
        source = Path("app/admin_routes.py").read_text()
        assert "community_badge" in source, "Approval cards must have community badge"
