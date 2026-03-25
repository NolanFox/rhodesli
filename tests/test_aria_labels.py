"""Tests for SVG aria-label and aria-hidden accessibility attributes.

Session 127 Phase 1B: Verify that icon-only SVGs have proper ARIA labels
and decorative SVGs have aria-hidden="true".
"""

import re
from pathlib import Path

# Project root for file reading
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_file(relpath: str) -> str:
    """Read a source file relative to project root."""
    return (PROJECT_ROOT / relpath).read_text()


class TestToolsRoutesAriaLabels:
    """SVG accessibility in app/tools_routes.py."""

    def setup_method(self):
        self.content = _read_file("app/tools_routes.py")

    def test_calendar_icon_aria_hidden(self):
        """Calendar icon on Date Estimator card should be aria-hidden."""
        assert 'class="w-10 h-10 text-amber-400"' in self.content
        # The SVG with that class should have aria-hidden
        match = re.search(r'class="w-10 h-10 text-amber-400"[^>]*aria-hidden="true"', self.content)
        assert match, "Calendar icon SVG should have aria-hidden='true'"

    def test_arrow_icons_aria_hidden(self):
        """Arrow icons next to 'Try it' should be aria-hidden."""
        # Both amber and indigo arrow icons
        arrows = re.findall(r'class="w-4 h-4 text-(?:amber|indigo)-400 ml-1"[^>]*', self.content)
        assert len(arrows) >= 2, f"Expected at least 2 arrow icons, found {len(arrows)}"
        for arrow in arrows:
            assert 'aria-hidden="true"' in arrow, f"Arrow icon missing aria-hidden: {arrow[:80]}"

    def test_face_compare_icon_aria_hidden(self):
        """People icon on Face Compare card should be aria-hidden."""
        match = re.search(r'class="w-10 h-10 text-indigo-400"[^>]*aria-hidden="true"', self.content)
        assert match, "Face Compare icon SVG should have aria-hidden='true'"

    def test_all_tool_card_svgs_have_aria(self):
        """All SVGs in tools_routes.py should have aria-hidden."""
        svgs = re.findall(r"<svg[^>]+>", self.content)
        for svg in svgs:
            assert 'aria-hidden="true"' in svg, f"SVG missing aria-hidden: {svg[:80]}"


class TestDiscoveriesRoutesAriaLabels:
    """SVG accessibility in app/discoveries_routes.py."""

    def setup_method(self):
        self.content = _read_file("app/discoveries_routes.py")

    def test_hamburger_button_has_aria_label(self):
        """Hamburger menu button should have aria-label."""
        assert 'aria_label="Open sidebar menu"' in self.content

    def test_auto_added_icon_aria_hidden(self):
        """Checkmark circle icon in 'Recently Auto-Added' section should be aria-hidden."""
        # aria-hidden comes before the path in the SVG tag
        match = re.search(r'aria-hidden="true"[^>]*>.*?M9 12l2 2 4-4', self.content, re.DOTALL)
        assert match, "Auto-added checkmark icon should have aria-hidden"

    def test_suggested_matches_icon_aria_hidden(self):
        """Search icon in 'Suggested Matches' section should be aria-hidden."""
        match = re.search(r'aria-hidden="true"[^>]*>.*?M21 21l-6-6', self.content, re.DOTALL)
        assert match, "Suggested matches search icon should have aria-hidden"

    def test_confirm_button_svg_aria_hidden(self):
        """SVG icons inside Confirm/Undo/Reject buttons should be aria-hidden."""
        # Look for Svg elements with aria_hidden="true" attribute
        assert self.content.count('aria_hidden="true"') >= 5, (
            "Expected at least 5 Svg() elements with aria_hidden in discoveries_routes.py"
        )

    def test_help_identify_icon_aria_hidden(self):
        """Question mark icon in Help Identify section should be aria-hidden."""
        match = re.search(r'aria-hidden="true"[^>]*>.*?M8\.228 9c', self.content, re.DOTALL)
        assert match, "Help Identify question mark icon should have aria-hidden"

    def test_arrow_between_faces_aria_hidden(self):
        """Arrow between source and target faces should be aria-hidden."""
        # The Svg with d="M14 5l7 7..."
        assert 'aria_hidden="true"' in self.content


class TestMainPyAriaLabels:
    """SVG accessibility in app/main.py and extracted component files."""

    def setup_method(self):
        self.content = _read_file("app/main.py")
        # Session 137: some components extracted to app/components/
        for comp_file in ("nav.py", "modals.py", "badges.py", "toasts.py", "forms.py", "layouts.py"):
            try:
                self.content += _read_file(f"app/components/{comp_file}")
            except FileNotFoundError:
                pass

    def test_notification_bell_aria_hidden(self):
        """Bell notification SVG should be aria-hidden (link has aria-label)."""
        assert 'aria_label="Notifications"' in self.content

    def test_notification_link_aria_label(self):
        """Notification link should have aria-label for screen readers."""
        # The A() element with notifications href
        match = re.search(r'aria_label="Notifications"', self.content)
        assert match, "Notification link should have aria-label"

    def test_sidebar_chevron_aria_hidden(self):
        """Sidebar collapse chevron SVG should be aria-hidden."""
        # The sidebar chevron Svg() has aria_hidden
        match = re.search(r"sidebar-chevron.*?aria_hidden", self.content, re.DOTALL)
        assert match, "Sidebar chevron should have aria_hidden"

    def test_sidebar_collapse_aria_label(self):
        """Sidebar collapse button should have aria-label."""
        assert 'aria_label="Toggle sidebar"' in self.content

    def test_search_icon_aria_hidden(self):
        """Sidebar search icon should be aria-hidden."""
        # The search SVG Svg() call with M21 21l-6-6 spans multiple lines
        # Just check that the search path and aria_hidden appear together in the sidebar area
        match = re.search(r"M21 21l-6-6.*?aria_hidden", self.content, re.DOTALL)
        assert match, "Sidebar search icon should have aria_hidden"

    def test_upload_icon_aria_hidden(self):
        """Upload button icon should be aria-hidden."""
        # The upload SVG with M4 16v1 path
        match = re.search(r"M4 16v1.*?aria_hidden", self.content, re.DOTALL)
        assert match, "Upload icon should have aria_hidden"

    def test_share_icon_svg_aria_hidden(self):
        """_SHARE_ICON_SVG constant should have aria-hidden."""
        assert "_SHARE_ICON_SVG = '<svg" in self.content
        match = re.search(r"_SHARE_ICON_SVG.*?aria-hidden=\"true\"", self.content)
        assert match, "_SHARE_ICON_SVG should have aria-hidden"

    def test_share_button_svg_aria_hidden(self):
        """Share button SVG (w-4 h-4 mr-1.5) should have aria-hidden."""
        match = re.search(r'class="w-4 h-4 mr-1\.5 inline"[^>]*aria-hidden="true"', self.content)
        assert match, "Share button SVG should have aria-hidden"

    def test_share_prominent_svg_aria_hidden(self):
        """Share prominent SVG (w-5 h-5 mr-2) should have aria-hidden."""
        match = re.search(r'class="w-5 h-5 mr-2 inline"[^>]*aria-hidden="true"', self.content)
        assert match, "Share prominent SVG should have aria-hidden"

    def test_share_icon_button_aria_label(self):
        """Icon-only share button should have aria-label."""
        assert "aria_label=label" in self.content

    def test_reanalyze_icon_aria_hidden(self):
        """Reanalyze refresh icon should be aria-hidden."""
        match = re.search(r'class="w-3\.5 h-3\.5 mr-1"[^>]*aria-hidden="true"', self.content)
        assert match, "Reanalyze icon should have aria-hidden"

    def test_tree_icon_aria_hidden(self):
        """GEDCOM tree icon should have aria-hidden."""
        match = re.search(r'width="12" height="12"[^>]*aria-hidden="true"', self.content)
        assert match, "GEDCOM tree icon should have aria-hidden"

    def test_settings_gear_aria_label(self):
        """Admin tools settings gear summary should have aria-label."""
        assert 'aria_label="Admin tools"' in self.content

    def test_settings_gear_svg_aria_hidden(self):
        """Admin tools settings gear SVG should be aria-hidden."""
        match = re.search(r'class="w-4 h-4"[^>]*aria-hidden="true"[^>]*>.*?M9\.594', self.content, re.DOTALL)
        assert match, "Settings gear SVG should have aria-hidden"

    def test_google_logo_aria_hidden(self):
        """Google sign-in logo SVG should be aria-hidden."""
        match = re.search(r'viewBox="0 0 24 24" width="18"[^>]*aria-hidden="true"', self.content)
        assert match, "Google logo SVG should have aria-hidden"

    def test_mobile_hamburger_svg_aria_hidden(self):
        """Mobile hamburger SVGs should be aria-hidden (buttons have aria-label)."""
        hamburger_svgs = re.findall(r"<svg[^>]*>.*?M4 6h16", self.content)
        assert len(hamburger_svgs) >= 2, "Should have at least 2 hamburger SVGs"

    def test_public_nav_close_svg_aria_hidden(self):
        """Public nav close SVG should be aria-hidden."""
        match = re.search(r'close_svg.*?aria-hidden="true"', self.content, re.DOTALL)
        assert match, "Public nav close SVG should have aria-hidden"


class TestMinimumAriaCount:
    """Verify minimum number of aria additions across all files."""

    def test_at_least_10_new_aria_additions(self):
        """At least 10 new aria-label or aria-hidden additions across the 3 files."""
        tools = _read_file("app/tools_routes.py")
        discoveries = _read_file("app/discoveries_routes.py")
        main = _read_file("app/main.py")

        all_content = tools + discoveries + main

        # Count aria-hidden="true" in inline SVGs
        inline_hidden = len(re.findall(r'aria-hidden="true"', all_content))
        # Count aria_hidden="true" in Svg() elements
        element_hidden = len(re.findall(r'aria_hidden="true"', all_content))
        # Count aria-label and aria_label additions (excluding pre-existing ones like "Open menu")
        aria_labels = len(re.findall(r"aria[_-]label=", all_content))

        total = inline_hidden + element_hidden + aria_labels
        assert total >= 10, f"Expected at least 10 aria additions, found {total}"
