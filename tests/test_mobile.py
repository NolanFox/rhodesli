"""Mobile responsive tests: viewport meta, media queries, sidebar, layout.

Verifies that all pages include proper mobile viewport configuration,
that CSS includes responsive breakpoints, and that mobile-specific
elements (hamburger menu, sidebar overlay) are present.

The homepage (/) is the landing page, while /?section=to_review is the
workstation (Command Center) with sidebar navigation.
"""

import pytest
from unittest.mock import patch


# The workstation URL (has sidebar, mobile header, media queries)
WORKSTATION_URL = "/?section=to_review"


# ---------------------------------------------------------------------------
# Viewport meta tag tests
# ---------------------------------------------------------------------------

class TestViewportMeta:
    """All pages must include the viewport meta tag for mobile scaling."""

    def test_landing_page_has_viewport_meta(self, client):
        """Landing page includes viewport meta tag."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'name="viewport"' in response.text
        assert "width=device-width" in response.text

    def test_workstation_has_viewport_meta(self, client):
        """Workstation page includes viewport meta tag."""
        response = client.get(WORKSTATION_URL)
        assert response.status_code == 200
        assert 'name="viewport"' in response.text
        assert "width=device-width" in response.text

    def test_login_page_has_viewport_meta(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Login page includes viewport meta tag."""
        response = client.get("/login")
        assert response.status_code == 200
        assert 'name="viewport"' in response.text
        assert "width=device-width" in response.text

    def test_signup_page_has_viewport_meta(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Signup page includes viewport meta tag."""
        response = client.get("/signup")
        assert response.status_code == 200
        assert 'name="viewport"' in response.text
        assert "width=device-width" in response.text

    def test_forgot_password_page_has_viewport_meta(self, client, auth_enabled, no_user):
        """Forgot password page includes viewport meta tag."""
        response = client.get("/forgot-password")
        assert response.status_code == 200
        assert 'name="viewport"' in response.text
        assert "width=device-width" in response.text

    def test_reset_password_page_has_viewport_meta(self, client, auth_enabled, no_user):
        """Reset password page includes viewport meta tag."""
        response = client.get("/reset-password")
        assert response.status_code == 200
        assert 'name="viewport"' in response.text
        assert "width=device-width" in response.text


# ---------------------------------------------------------------------------
# Mobile CSS breakpoint tests
# ---------------------------------------------------------------------------

class TestMobileBreakpoints:
    """Workstation layout CSS must include mobile-responsive media queries."""

    def test_workstation_has_mobile_media_query(self, client):
        """Workstation CSS includes max-width: 767px media query."""
        response = client.get(WORKSTATION_URL)
        assert "@media" in response.text
        assert "max-width: 767px" in response.text

    def test_workstation_has_tablet_media_query(self, client):
        """Workstation CSS includes tablet breakpoint."""
        response = client.get(WORKSTATION_URL)
        assert "min-width: 768px" in response.text

    def test_workstation_has_desktop_media_query(self, client):
        """Workstation CSS includes desktop breakpoint (lg)."""
        response = client.get(WORKSTATION_URL)
        assert "min-width: 1024px" in response.text

    def test_main_content_responsive_class(self, client):
        """Main content area uses responsive CSS class instead of fixed ml-64."""
        response = client.get(WORKSTATION_URL)
        assert "main-content" in response.text


# ---------------------------------------------------------------------------
# Mobile navigation tests (workstation pages with sidebar)
# ---------------------------------------------------------------------------

class TestMobileNavigation:
    """Mobile sidebar toggle and overlay elements must be present on workstation."""

    def test_mobile_header_present(self, client):
        """Workstation includes mobile header with hamburger button."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        assert "mobile-header" in text
        assert "toggleSidebar" in text

    def test_sidebar_has_id(self, client):
        """Sidebar has an id attribute for JavaScript targeting."""
        response = client.get(WORKSTATION_URL)
        assert 'id="sidebar"' in response.text

    def test_sidebar_overlay_present(self, client):
        """Sidebar overlay element is present for mobile backdrop."""
        response = client.get(WORKSTATION_URL)
        assert "sidebar-overlay" in response.text

    def test_sidebar_close_button_present(self, client):
        """Sidebar includes a close button for mobile."""
        response = client.get(WORKSTATION_URL)
        assert "closeSidebar" in response.text

    def test_sidebar_toggle_script_present(self, client):
        """Page includes toggleSidebar and closeSidebar JavaScript functions."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        assert "function toggleSidebar()" in text
        assert "function closeSidebar()" in text

    def test_sidebar_starts_offscreen_on_mobile(self, client):
        """Sidebar has translate class to start off-screen on mobile."""
        response = client.get(WORKSTATION_URL)
        assert "-translate-x-full" in response.text
        assert "lg:translate-x-0" in response.text


# ---------------------------------------------------------------------------
# Mobile bottom tab navigation
# ---------------------------------------------------------------------------

class TestMobileBottomTabs:
    """Bottom tab navigation must be present on mobile."""

    def test_bottom_tabs_present(self, client):
        """Workstation includes mobile bottom tab navigation."""
        response = client.get(WORKSTATION_URL)
        assert 'id="mobile-tabs"' in response.text

    def test_bottom_tabs_has_four_links(self, client):
        """Bottom tabs have Photos, People, Inbox, Search links."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        assert "Photos" in text
        assert "People" in text
        assert "Matches" in text
        assert "Search" in text

    def test_bottom_tabs_hidden_on_desktop(self, client):
        """Bottom tabs use lg:hidden to be invisible on desktop."""
        response = client.get(WORKSTATION_URL)
        assert "lg:hidden" in response.text

    def test_bottom_tabs_touch_targets(self, client):
        """Bottom tab items have minimum 44px touch targets."""
        response = client.get(WORKSTATION_URL)
        # mobile-tabs links should have min-h-[44px]
        assert "min-h-[44px]" in response.text

    def test_bottom_tabs_highlight_active_section(self, client):
        """Active section tab should be highlighted."""
        response = client.get("/?section=photos")
        # Photos tab should be indigo (active)
        assert "text-indigo-400" in response.text

    def test_main_content_has_bottom_padding_for_tabs(self, client):
        """Main content area has extra bottom padding for mobile tabs."""
        response = client.get(WORKSTATION_URL)
        assert "pb-20" in response.text


# ---------------------------------------------------------------------------
# Upload page mobile tests
# ---------------------------------------------------------------------------

class TestUploadPageMobile:
    """Upload page must have mobile-responsive layout."""

    def test_upload_page_has_mobile_header(self, client, auth_disabled):
        """Upload page includes mobile header."""
        response = client.get("/upload")
        assert response.status_code == 200
        assert "mobile-header" in response.text

    def test_upload_page_has_responsive_main(self, client, auth_disabled):
        """Upload page uses responsive main-content class."""
        response = client.get("/upload")
        assert "main-content" in response.text

    def test_upload_page_has_sidebar_overlay(self, client, auth_disabled):
        """Upload page has sidebar overlay for mobile."""
        response = client.get("/upload")
        assert "sidebar-overlay" in response.text

    def test_upload_page_has_mobile_media_queries(self, client, auth_disabled):
        """Upload page CSS includes mobile breakpoints."""
        response = client.get("/upload")
        assert "@media" in response.text
        assert "max-width: 767px" in response.text


# ---------------------------------------------------------------------------
# Touch target tests
# ---------------------------------------------------------------------------

class TestTouchTargets:
    """Buttons must have minimum 44px touch targets on mobile."""

    def test_focus_action_buttons_have_min_height(self, client):
        """Focus mode action buttons specify minimum height for touch."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        # The min-h-[44px] class should be in the rendered HTML
        assert "min-h-[44px]" in text

    def test_nav_items_have_min_height(self, client):
        """Sidebar nav items have minimum height for touch targets."""
        response = client.get(WORKSTATION_URL)
        assert "min-h-[44px]" in response.text


# ---------------------------------------------------------------------------
# Modal responsiveness tests
# ---------------------------------------------------------------------------

class TestModalResponsiveness:
    """Modals must be usable on mobile viewports."""

    def test_photo_modal_has_full_width(self, client):
        """Photo modal content uses w-full with responsive max-width for mobile."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        assert "w-full max-w-full sm:max-w-5xl" in text

    def test_login_modal_has_full_width(self, client):
        """Login modal uses w-full to fill mobile screens."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        assert "w-full" in text

    def test_confirm_modal_has_full_width(self, client):
        """Confirm modal uses w-full to fill mobile screens."""
        response = client.get(WORKSTATION_URL)
        text = response.text
        assert "w-full" in text


# ---------------------------------------------------------------------------
# Auth pages mobile tests
# ---------------------------------------------------------------------------

class TestAuthPagesMobile:
    """Auth pages should have mobile-friendly padding and spacing."""

    def test_login_page_responsive_padding(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Login form uses responsive padding (sm:p-8 for desktop, p-4 for mobile)."""
        response = client.get("/login")
        text = response.text
        assert "sm:p-8" in text
        assert "p-4" in text

    def test_login_page_responsive_margin(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Login form uses responsive top margin (sm:mt-20 for desktop, mt-10 for mobile)."""
        response = client.get("/login")
        text = response.text
        assert "sm:mt-20" in text
        assert "mt-10" in text

    def test_signup_page_responsive_padding(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Signup form uses responsive padding."""
        response = client.get("/signup")
        text = response.text
        assert "sm:p-8" in text
        assert "p-4" in text


# ---------------------------------------------------------------------------
# Landing page mobile tests
# ---------------------------------------------------------------------------

class TestLandingPageMobile:
    """Landing page should be mobile-friendly."""

    def test_landing_page_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_landing_page_has_responsive_grid(self, client):
        """Landing page uses responsive CSS for the photo grid."""
        response = client.get("/")
        # The hero grid uses media queries for responsive row heights
        assert "@media" in response.text

    def test_landing_page_nav_uses_flex_wrap(self, client):
        """Landing page nav bar uses flex for responsiveness."""
        response = client.get("/")
        assert "flex" in response.text


# ---------------------------------------------------------------------------
# Page accessibility tests
# ---------------------------------------------------------------------------

class TestPageResponds:
    """All key pages must return 200 status."""

    def test_homepage_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_workstation_returns_200(self, client):
        response = client.get(WORKSTATION_URL)
        assert response.status_code == 200

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_login_returns_200(self, client, auth_enabled, no_user, google_oauth_enabled):
        response = client.get("/login")
        assert response.status_code == 200

    def test_signup_returns_200(self, client, auth_enabled, no_user, google_oauth_enabled):
        response = client.get("/signup")
        assert response.status_code == 200

    def test_forgot_password_returns_200(self, client, auth_enabled, no_user):
        response = client.get("/forgot-password")
        assert response.status_code == 200

    def test_reset_password_returns_200(self, client, auth_enabled, no_user):
        response = client.get("/reset-password")
        assert response.status_code == 200

    def test_photos_section_returns_200(self, client):
        response = client.get("/?section=photos")
        assert response.status_code == 200

    def test_confirmed_section_returns_200(self, client):
        response = client.get("/?section=confirmed")
        assert response.status_code == 200

    def test_skipped_section_returns_200(self, client):
        response = client.get("/?section=skipped")
        assert response.status_code == 200

    def test_rejected_section_returns_200(self, client):
        response = client.get("/?section=rejected")
        assert response.status_code == 200


class TestMobileOverflowPrevention:
    """Elements must not cause horizontal overflow on mobile viewports."""

    def test_main_content_has_overflow_hidden(self, client):
        """Main content container prevents horizontal scroll from child elements."""
        response = client.get("/?section=photos")
        assert response.status_code == 200
        assert "overflow-x-hidden" in response.text

    def test_filter_bar_selects_have_max_width(self, client):
        """Filter bar selects constrain width on mobile to prevent overflow."""
        response = client.get("/?section=photos")
        assert response.status_code == 200
        assert "max-w-[10rem]" in response.text

    def test_neighbors_sidebar_has_overflow_hidden(self):
        """Neighbors sidebar prevents content from expanding the viewport."""
        from app.main import neighbors_sidebar
        from fasthtml.common import to_xml

        html = to_xml(neighbors_sidebar("test-id", [], set()))
        assert "overflow-hidden" in html

    def test_neighbor_card_buttons_wrap_on_mobile(self):
        """Neighbor card button group wraps below info on mobile."""
        from app.main import neighbor_card
        from fasthtml.common import to_xml

        neighbor = {
            "identity_id": "n-001",
            "name": "Test Neighbor",
            "state": "PROPOSED",
            "distance": 0.85,
            "confidence_gap": 10.0,
            "co_occurrence": 0,
            "can_merge": True,
            "face_count": 1,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
        }
        html = to_xml(neighbor_card(neighbor, "target-id", set()))
        # Should wrap on mobile
        assert "flex-wrap" in html
        # Buttons should have margin-top on mobile
        assert "mt-2 sm:mt-0" in html

    def test_landing_nav_hidden_on_mobile(self, client):
        """Landing page nav links are hidden on mobile (bottom tabs used instead)."""
        response = client.get("/")
        assert response.status_code == 200
        # The archival landing page nav items container should be hidden on mobile
        assert "hidden sm:flex" in response.text or "hidden md:flex" in response.text


# ---------------------------------------------------------------------------
# Public page mobile navigation (Session 49B audit fix H1)
# ---------------------------------------------------------------------------

class TestPublicPageMobileNav:
    """Public pages must include mobile nav script for hamburger menu.

    The global mobile nav script injects a hamburger button and overlay
    on pages that have nav links hidden with 'hidden sm:flex'.
    """

    PUBLIC_PAGES = ["/", "/photos", "/people", "/compare", "/estimate",
                    "/map", "/timeline", "/tree", "/connect", "/collections",
                    "/about"]

    def test_mobile_nav_script_on_landing(self, client):
        """Landing page includes mobile nav injection script."""
        response = client.get("/")
        assert response.status_code == 200
        assert "mobile-nav-overlay" in response.text

    def test_mobile_nav_script_on_photos(self, client):
        """Photos page includes mobile nav injection script."""
        response = client.get("/photos")
        assert response.status_code == 200
        assert "mobile-nav-overlay" in response.text

    def test_mobile_nav_script_on_people(self, client):
        """People page includes mobile nav injection script."""
        response = client.get("/people")
        assert response.status_code == 200
        assert "mobile-nav-overlay" in response.text

    def test_mobile_nav_script_on_compare(self, client):
        """Compare page includes mobile nav injection script."""
        response = client.get("/compare")
        assert response.status_code == 200
        assert "mobile-nav-overlay" in response.text

    def test_mobile_nav_script_on_map(self, client):
        """Map page includes mobile nav injection script."""
        response = client.get("/map")
        assert response.status_code == 200
        assert "mobile-nav-overlay" in response.text

    def test_mobile_nav_hamburger_reference(self, client):
        """Public pages include hamburger button injection logic."""
        response = client.get("/photos")
        assert "Open navigation menu" in response.text

    def test_mobile_nav_skips_sidebar_pages(self, client):
        """Script skips pages that already have sidebar navigation."""
        response = client.get("/")
        # Script checks for sidebar element and skips if present
        assert "getElementById('sidebar')" in response.text


# ---------------------------------------------------------------------------
# Styled 404 catch-all tests (Session 49B audit fix M1)
# ---------------------------------------------------------------------------

class TestStyled404CatchAll:
    """Unknown routes must return a styled 404 page, not bare text."""

    def test_unknown_route_returns_404(self, client):
        """Arbitrary unknown path returns 404 status."""
        response = client.get("/nonexistent-page-xyz")
        assert response.status_code == 404

    def test_unknown_route_has_styled_page(self, client):
        """404 page has styled content, not bare text."""
        response = client.get("/nonexistent-page-xyz")
        assert "Rhodesli" in response.text
        assert "Page not found" in response.text

    def test_unknown_route_has_explore_link(self, client):
        """404 page has a link back to the archive."""
        response = client.get("/nonexistent-page-xyz")
        assert "Explore the Archive" in response.text

    def test_unknown_route_has_nav(self, client):
        """404 page has navigation bar."""
        response = client.get("/nonexistent-page-xyz")
        assert 'href="/"' in response.text


# ---------------------------------------------------------------------------
# Favicon tests (Session 49B audit fix M4)
# ---------------------------------------------------------------------------

class TestFavicon:
    """Pages must include a favicon to prevent console 404 errors."""

    def test_landing_page_has_favicon(self, client):
        """Landing page includes favicon link."""
        response = client.get("/")
        assert 'rel="icon"' in response.text

    def test_workstation_has_favicon(self, client):
        """Workstation includes favicon link."""
        response = client.get(WORKSTATION_URL)
        assert 'rel="icon"' in response.text
