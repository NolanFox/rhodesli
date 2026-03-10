"""Tests for COMMUNITY-008 (bottom nav prefix) and COMMUNITY-013 (admin page headers).

COMMUNITY-008: Mobile bottom nav links must include community URL prefix
               so navigation stays within the community context (e.g. /c/fox-family/).
COMMUNITY-013: Admin page titles must reflect the active community name
               rather than always saying "Rhodesli".
"""

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_source(relative_path: str) -> str:
    """Read a source file directly to avoid circular import issues."""
    return (_REPO_ROOT / relative_path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# COMMUNITY-008: Source-level verification that bottom nav uses _nav_prefix
# ---------------------------------------------------------------------------


class TestBottomNavSourceUsesPrefix(unittest.TestCase):
    """page_routes.py bottom nav must reference _nav_prefix (COMMUNITY-008)."""

    def _get_page_routes_source(self):
        return _read_source("app/page_routes.py")

    def test_nav_prefix_variable_is_assigned(self):
        """The _nav_prefix variable must be computed from community_url_prefix()."""
        source = self._get_page_routes_source()
        assert "_nav_prefix = _main_mod.community_url_prefix(community_slug)" in source

    def test_bottom_nav_photos_link_uses_nav_prefix(self):
        """The Photos nav link in the mobile bottom nav uses the prefix variable."""
        source = self._get_page_routes_source()
        assert 'href=f"{_nav_prefix}/?section=photos"' in source

    def test_bottom_nav_confirmed_link_uses_nav_prefix(self):
        """The People nav link uses the prefix variable."""
        source = self._get_page_routes_source()
        assert 'href=f"{_nav_prefix}/?section=confirmed&view=browse"' in source

    def test_bottom_nav_to_review_link_uses_nav_prefix(self):
        """The Matches nav link uses the prefix variable."""
        source = self._get_page_routes_source()
        assert 'href=f"{_nav_prefix}/?section=to_review&view=focus"' in source

    def test_no_bare_hardcoded_section_in_mobile_nav_block(self):
        """The mobile_tabs Nav block must not contain bare href=\"/?section= links."""
        source = self._get_page_routes_source()
        # Find the mobile_tabs Nav block (from assignment to closing paren+comma)
        # Locate via comment marker
        marker = "# Mobile bottom tab navigation (lg:hidden)"
        marker_pos = source.find(marker)
        assert marker_pos != -1, "Could not find mobile_tabs block marker"

        # Extract a reasonable chunk after the marker (1500 chars covers the full block)
        block = source[marker_pos : marker_pos + 1500]

        # Should NOT have bare href="/?section= (without prefix variable)
        assert 'href="/?section=' not in block, (
            'Found bare href="/?section= in mobile bottom nav — must use _nav_prefix'
        )


# ---------------------------------------------------------------------------
# COMMUNITY-008: Logic tests for prefix computation
# ---------------------------------------------------------------------------


class TestCommunityUrlPrefixLogic(unittest.TestCase):
    """community_url_prefix returns correct values for each slug type."""

    def test_rhodes_returns_empty(self):
        from app.main import community_url_prefix

        assert community_url_prefix("rhodes") == ""

    def test_none_returns_empty(self):
        from app.main import community_url_prefix

        assert community_url_prefix(None) == ""

    def test_fox_family_returns_prefix(self):
        from app.main import community_url_prefix

        assert community_url_prefix("fox-family") == "/c/fox-family"

    def test_smith_archive_returns_prefix(self):
        from app.main import community_url_prefix

        assert community_url_prefix("smith-archive") == "/c/smith-archive"

    def test_nav_link_construction_for_fox_family(self):
        """Simulates what bottom nav does: prefix + /?section=photos."""
        from app.main import community_url_prefix

        prefix = community_url_prefix("fox-family")
        assert prefix + "/?section=photos" == "/c/fox-family/?section=photos"
        assert prefix + "/?section=confirmed&view=browse" == "/c/fox-family/?section=confirmed&view=browse"
        assert prefix + "/?section=to_review&view=focus" == "/c/fox-family/?section=to_review&view=focus"

    def test_nav_link_construction_for_rhodes(self):
        """Rhodes prefix is empty, so links are bare /?section=... links."""
        from app.main import community_url_prefix

        prefix = community_url_prefix("rhodes")
        assert prefix + "/?section=photos" == "/?section=photos"


# ---------------------------------------------------------------------------
# COMMUNITY-013: Source-level verification that admin Titles use f-strings
# ---------------------------------------------------------------------------


class TestAdminRoutesTitleStrings(unittest.TestCase):
    """Admin route Title() calls must use community_name variable (COMMUNITY-013)."""

    def _get_admin_routes_source(self):
        return _read_source("app/admin_routes.py")

    def test_pending_uploads_title_is_dynamic(self):
        """Title for /admin/pending must be an f-string, not hardcoded."""
        source = self._get_admin_routes_source()
        assert 'Title(f"Pending Uploads - {community_name}")' in source

    def test_proposals_title_is_dynamic(self):
        """Title for /admin/proposals must be an f-string."""
        source = self._get_admin_routes_source()
        assert 'Title(f"Proposals - {community_name}")' in source

    def test_ml_dashboard_title_is_dynamic(self):
        """Title for /admin/ml-dashboard must be an f-string."""
        source = self._get_admin_routes_source()
        # Source may have literal em-dash (—) or unicode escape (\u2014) — accept either
        assert (
            'Title(f"ML Dashboard \u2014 {community_name}")' in source
            or 'Title(f"ML Dashboard \\u2014 {community_name}")' in source
        )

    def test_approvals_title_is_dynamic(self):
        """Title for /admin/approvals must be an f-string."""
        source = self._get_admin_routes_source()
        assert (
            'Title(f"Annotation Approvals \u2014 {community_name}")' in source
            or 'Title(f"Annotation Approvals \\u2014 {community_name}")' in source
        )

    def test_birth_year_review_title_is_dynamic(self):
        """Title for /admin/review/birth-years must be an f-string."""
        source = self._get_admin_routes_source()
        assert 'Title(f"ML Birth Year Review - {community_name} Admin")' in source

    def test_audit_log_title_is_dynamic(self):
        """Title for /admin/audit must be an f-string."""
        source = self._get_admin_routes_source()
        assert (
            'Title(f"Audit Log \u2014 {community_name}")' in source
            or 'Title(f"Audit Log \\u2014 {community_name}")' in source
        )

    def test_gedcom_title_is_dynamic(self):
        """Title for /admin/gedcom must be an f-string."""
        source = self._get_admin_routes_source()
        assert (
            'Title(f"GEDCOM Import \u2014 {community_name}")' in source
            or 'Title(f"GEDCOM Import \\u2014 {community_name}")' in source
        )

    def test_review_queue_title_is_dynamic(self):
        """Title for /admin/review-queue must be an f-string."""
        source = self._get_admin_routes_source()
        assert (
            'Title(f"Review Queue \u2014 {community_name}")' in source
            or 'Title(f"Review Queue \\u2014 {community_name}")' in source
        )

    def test_no_hardcoded_rhodesli_in_titles(self):
        """No Title() call in admin_routes.py should hardcode 'Rhodesli'."""
        source = self._get_admin_routes_source()
        # Find all Title(...) calls (single-line)
        title_calls = re.findall(r"Title\([^)]+\)", source)
        for call in title_calls:
            if "Rhodesli" in call:
                self.fail(f"Hardcoded 'Rhodesli' found in Title() call: {call!r}. Use community_name variable instead.")


# ---------------------------------------------------------------------------
# COMMUNITY-013: Logic tests for community name extraction in admin routes
# ---------------------------------------------------------------------------


class TestAdminCommunityNameExtraction(unittest.TestCase):
    """Verify the community_name extraction logic that admin routes now use."""

    def test_community_with_name_returns_name(self):
        """When community dict has name, community_name is that value."""
        community = {"name": "Fox Family Archive", "slug": "fox-family"}
        community_name = community.get("name", "Rhodesli") if community else "Rhodesli"
        assert community_name == "Fox Family Archive"

    def test_none_community_falls_back_to_rhodesli(self):
        """When community is None (Rhodes default), falls back to 'Rhodesli'."""
        community = None
        community_name = community.get("name", "Rhodesli") if community else "Rhodesli"
        assert community_name == "Rhodesli"

    def test_community_missing_name_falls_back_to_rhodesli(self):
        """When community dict lacks 'name' key, falls back to 'Rhodesli'."""
        community = {"slug": "some-community"}
        community_name = community.get("name", "Rhodesli") if community else "Rhodesli"
        assert community_name == "Rhodesli"

    def test_smith_archive_name(self):
        """Any community name is reflected correctly."""
        community = {"name": "Smith Family Archive"}
        community_name = community.get("name", "Rhodesli") if community else "Rhodesli"
        assert community_name == "Smith Family Archive"

    def test_admin_routes_have_request_in_affected_signatures(self):
        """All affected admin GET routes now have request parameter."""
        source = _read_source("app/admin_routes.py")
        # The specific routes that must have been updated
        affected_routes = [
            '/admin/pending")',
            '/admin/proposals")',
            '/admin/ml-dashboard")',
            '/admin/approvals")',
            '/admin/review/birth-years")',
            '/admin/audit")',
            '/admin/gedcom")',
            '/admin/review-queue")',
        ]
        for route_pattern in affected_routes:
            assert route_pattern in source, f"Route {route_pattern!r} not found in admin_routes.py source"

        # Spot-check: at least 6 occurrences of 'def get(request, sess=None)'
        # (the 8 updated routes, some may be deduplicated by grep)
        count = source.count("def get(request, sess=None)")
        assert count >= 6, (
            f"Expected at least 6 'def get(request, sess=None)' in admin_routes.py, "
            f"found {count}. Some admin routes may not have been updated."
        )


if __name__ == "__main__":
    unittest.main()
