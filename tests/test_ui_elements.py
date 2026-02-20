"""UI element tests: page content, buttons, modals, scripts, branding.

Tests that the rendered HTML contains expected elements and does NOT
contain removed/disabled elements.
"""

import pytest
from unittest.mock import patch

from app.auth import ENABLED_OAUTH_PROVIDERS


class TestLoginPageOAuthButtons:
    """Login page should only show OAuth buttons for enabled providers."""

    def test_no_facebook_button(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Login page does NOT contain a Facebook OAuth button."""
        response = client.get("/login")
        text = response.text.lower()
        assert "facebook" not in text
        assert "sign in with facebook" not in text
        assert "fb-login" not in text

    def test_no_disabled_provider_buttons(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Login page only shows buttons for providers in ENABLED_OAUTH_PROVIDERS."""
        response = client.get("/login")
        text = response.text.lower()
        # Check that no disabled OAuth providers appear
        disabled_providers = {"facebook", "twitter", "github", "apple", "discord"} - ENABLED_OAUTH_PROVIDERS
        for provider in disabled_providers:
            assert f"sign in with {provider}" not in text, \
                f"Found disabled provider '{provider}' on login page"

    def test_enabled_providers_match_config(self):
        """ENABLED_OAUTH_PROVIDERS should only contain 'google'."""
        assert ENABLED_OAUTH_PROVIDERS == {"google"}, \
            f"Expected only 'google' in ENABLED_OAUTH_PROVIDERS, got {ENABLED_OAUTH_PROVIDERS}"


class TestGlobalScripts:
    """Workstation layout should include required global JavaScript handlers."""

    def test_error_hash_handler_present(self, client):
        """Workstation page includes the error hash fragment handler script."""
        response = client.get("/?section=to_review")
        # Check for key markers of the error hash handler
        assert "error_code" in response.text or "errorCode" in response.text
        assert "otp_expired" in response.text

    def test_login_modal_handler_present(self, client):
        """Workstation page includes the HTMX 401 → login modal handler."""
        response = client.get("/?section=to_review")
        assert "htmx:beforeSwap" in response.text
        assert "login-modal" in response.text

    def test_confirm_dialog_handler_present(self, client):
        """Workstation page includes the styled confirmation dialog handler."""
        response = client.get("/?section=to_review")
        assert "htmx:confirm" in response.text
        assert "confirm-modal" in response.text

    def test_no_native_confirm_calls(self, client):
        """No use of native window.confirm() in page scripts.

        The app uses a styled htmx:confirm dialog instead.
        Native confirm() breaks the darkroom theme.
        """
        response = client.get("/?section=to_review")
        import re
        # Look for confirm( but not htmx:confirm or confirm-modal
        # This is a heuristic check on the rendered page
        lines = response.text.split("\n")
        for line in lines:
            # Skip lines that are part of the htmx:confirm handler
            if "htmx:confirm" in line or "confirm-modal" in line:
                continue
            # Check for bare window.confirm() or confirm() calls
            if re.search(r'(?<!\w)confirm\s*\(', line):
                # Allow hx-confirm attribute values
                if 'hx-confirm' not in line and 'hx_confirm' not in line:
                    pytest.fail(f"Found native confirm() call: {line.strip()}")


class TestLoginModal:
    """Login modal component should be present on workstation pages."""

    def test_login_modal_container_present(self, client):
        """Workstation page includes the hidden login modal."""
        response = client.get("/?section=to_review")
        assert 'id="login-modal"' in response.text

    def test_login_modal_has_form(self, client):
        """Login modal includes email/password form."""
        response = client.get("/?section=to_review")
        # Check for modal form elements
        assert 'id="modal-email"' in response.text or 'name="email"' in response.text

    def test_login_modal_posts_to_modal_endpoint(self, client):
        """Login modal form submits to /login/modal (not /login)."""
        response = client.get("/?section=to_review")
        assert "/login/modal" in response.text


class TestConfirmModal:
    """Styled confirmation modal should be present on workstation pages."""

    def test_confirm_modal_container_present(self, client):
        """Workstation page includes the hidden confirmation modal."""
        response = client.get("/?section=to_review")
        assert 'id="confirm-modal"' in response.text

    def test_confirm_modal_has_buttons(self, client):
        """Confirmation modal has Cancel and Confirm buttons."""
        response = client.get("/?section=to_review")
        assert 'id="confirm-modal-yes"' in response.text
        assert 'id="confirm-modal-no"' in response.text

    def test_confirm_modal_has_message_target(self, client):
        """Confirmation modal has a message display element."""
        response = client.get("/?section=to_review")
        assert 'id="confirm-modal-message"' in response.text

    def test_confirm_handler_guards_empty_question(self, client):
        """htmx:confirm handler only shows modal when evt.detail.question exists.

        Regression test: Without the guard, ALL htmx requests triggered an empty
        confirm modal because htmx:confirm fires for every request in HTMX 1.9+.
        """
        response = client.get("/?section=to_review")
        # The handler must check for question before calling preventDefault
        assert "if (!evt.detail.question) return;" in response.text


class TestCompareUploadIndicator:
    """Compare upload form should show a loading indicator during processing."""

    def test_upload_form_has_indicator(self, client):
        """Compare page upload form has an htmx-indicator for loading state."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/compare")
            assert 'id="upload-spinner"' in response.text
            assert "htmx-indicator" in response.text

    def test_upload_spinner_has_message(self, client):
        """The upload spinner shows a descriptive message."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/compare")
            assert "Analyzing your photo" in response.text

    def test_upload_spinner_has_duration_warning(self, client):
        """The upload spinner warns about longer wait for group photos."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/compare")
            assert "group photos" in response.text

    def test_submit_button_disabled_during_request_css(self, client):
        """CSS rule disables submit button during htmx request."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/compare")
            assert "form.htmx-request button[type=\"submit\"]" in response.text
            assert "pointer-events: none" in response.text

    def test_htmx_indicator_css_handles_direct_class(self, client):
        """Triage dashboard CSS must handle .htmx-request.htmx-indicator for hx-indicator usage."""
        with patch("app.main.is_auth_enabled", return_value=False):
            # The triage dashboard (/?section=to_review) has custom CSS overriding HTMX defaults
            response = client.get("/?section=to_review")
            assert ".htmx-request.htmx-indicator" in response.text


class TestEmailTemplateDesign:
    """Email templates in the update script should have correct inline styles."""

    def test_button_styles_are_inline(self):
        """Email template buttons use inline styles (not class-based)."""
        from pathlib import Path
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "update_email_templates.sh"
        content = script_path.read_text()

        # Check that BUTTON_STYLE variable defines inline CSS properties
        assert "BUTTON_STYLE=" in content
        assert "background-color: #2563eb" in content
        assert "color: #ffffff" in content
        # Templates reference the BUTTON_STYLE variable via style= attribute
        assert "${BUTTON_STYLE}" in content

    def test_button_text_is_white(self):
        """Email button text color is white (#ffffff)."""
        from pathlib import Path
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "update_email_templates.sh"
        content = script_path.read_text()

        # The BUTTON_STYLE variable should include white text
        assert "color: #ffffff" in content


class TestGoogleOAuthBranding:
    """Google Sign-In button follows official branding guidelines."""

    def test_google_button_on_login_page(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Login page Google button has white background per Google branding."""
        response = client.get("/login")
        # Official Google Sign-In: white background, specific border
        assert "background: white" in response.text or "background-color: white" in response.text

    def test_google_button_has_roboto_font(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Google button uses Roboto font per branding guidelines."""
        response = client.get("/login")
        assert "Roboto" in response.text

    def test_google_svg_has_four_colors(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Google G logo SVG uses all 4 brand colors."""
        response = client.get("/login")
        google_colors = ["#4285F4", "#34A853", "#FBBC05", "#EA4335"]
        for color in google_colors:
            assert color in response.text, f"Missing Google brand color {color}"


class TestLoginModalOAuthButton:
    """Login modal (on workstation page) should also have proper Google button."""

    def test_login_modal_has_google_button(self, client, google_oauth_enabled):
        """Login modal includes Google OAuth button."""
        response = client.get("/?section=to_review")
        # The login_modal() function is rendered on the workstation page
        assert "Sign in with Google" in response.text

    def test_login_modal_google_button_has_svg(self, client, google_oauth_enabled):
        """Login modal Google button has the SVG logo."""
        response = client.get("/?section=to_review")
        # Should have the Google G SVG somewhere on the page (in the modal)
        assert 'viewBox="0 0 24 24"' in response.text


class TestRecoveryFlowConfig:
    """Password recovery flow configuration tests."""

    def test_recovery_includes_redirect_to(self):
        """send_password_reset passes redirect_to parameter."""
        import inspect
        from app.auth import send_password_reset
        source = inspect.getsource(send_password_reset)
        assert "redirect_to" in source, \
            "send_password_reset must include redirect_to to control where user lands after reset"

    def test_recovery_redirects_to_reset_password_page(self):
        """redirect_to points to /reset-password, not /."""
        import inspect
        from app.auth import send_password_reset
        source = inspect.getsource(send_password_reset)
        assert "/reset-password" in source, \
            "redirect_to must point to /reset-password page"
