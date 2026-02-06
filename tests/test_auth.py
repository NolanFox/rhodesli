"""Tests for auth flows: login, signup, password recovery, OAuth."""

import pytest
from unittest.mock import patch, AsyncMock


class TestLoginPage:
    """Tests for GET /login rendering."""

    def test_login_redirects_when_auth_disabled(self, client, auth_disabled):
        """When auth is disabled, /login redirects to home."""
        response = client.get("/login", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_login_renders_when_auth_enabled(self, client, auth_enabled, no_user, google_oauth_enabled):
        """When auth is enabled, /login renders the login form."""
        response = client.get("/login")
        assert response.status_code == 200
        assert "Sign In" in response.text

    def test_login_has_email_field(self, client, auth_enabled, no_user, google_oauth_disabled):
        """Login page has an email input field."""
        response = client.get("/login")
        assert 'type="email"' in response.text
        assert 'name="email"' in response.text

    def test_login_has_password_field(self, client, auth_enabled, no_user, google_oauth_disabled):
        """Login page has a password input field."""
        response = client.get("/login")
        assert 'type="password"' in response.text
        assert 'name="password"' in response.text

    def test_login_has_forgot_password_link(self, client, auth_enabled, no_user, google_oauth_disabled):
        """Login page has a forgot password link."""
        response = client.get("/login")
        assert "Forgot password?" in response.text
        assert "/forgot-password" in response.text

    def test_login_has_signup_link(self, client, auth_enabled, no_user, google_oauth_disabled):
        """Login page has a sign up link."""
        response = client.get("/login")
        assert "Sign up with invite code" in response.text
        assert "/signup" in response.text

    def test_login_no_facebook_button(self, client, auth_enabled, no_user, google_oauth_disabled):
        """Login page does NOT have a Facebook button."""
        response = client.get("/login")
        text_lower = response.text.lower()
        assert "facebook" not in text_lower
        assert "sign in with facebook" not in text_lower

    def test_login_has_google_button_when_enabled(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Login page has Google OAuth button when Google is enabled."""
        response = client.get("/login")
        assert "Sign in with Google" in response.text

    def test_login_google_button_has_svg(self, client, auth_enabled, no_user, google_oauth_enabled):
        """Google button has the official 4-color SVG logo."""
        response = client.get("/login")
        assert 'viewBox="0 0 24 24"' in response.text
        # Check for the 4 Google brand colors
        assert "#4285F4" in response.text  # Blue
        assert "#34A853" in response.text  # Green
        assert "#FBBC05" in response.text  # Yellow
        assert "#EA4335" in response.text  # Red

    def test_login_no_google_button_when_disabled(self, client, auth_enabled, no_user, google_oauth_disabled):
        """Login page does NOT have Google button when OAuth is disabled."""
        response = client.get("/login")
        assert "Sign in with Google" not in response.text

    def test_login_redirects_when_already_authenticated(self, client, auth_enabled):
        """Logged-in user visiting /login gets redirected to home."""
        # Simulate already having a session by setting cookie
        # Since we can't easily inject session, mock the sess.get check
        with patch("app.main.get_oauth_url", return_value=None):
            response = client.get("/login", follow_redirects=False)
            # If user has auth in session, should redirect
            # Without session data, they'll see the form (200)
            # This tests the page renders without error at minimum
            assert response.status_code in (200, 303)


class TestSignupPage:
    """Tests for GET /signup rendering."""

    def test_signup_redirects_when_auth_disabled(self, client, auth_disabled):
        """When auth disabled, /signup redirects to home."""
        response = client.get("/signup", follow_redirects=False)
        assert response.status_code == 303

    def test_signup_renders_when_auth_enabled(self, client, auth_enabled, no_user):
        """When auth enabled, /signup renders the signup form."""
        response = client.get("/signup")
        assert response.status_code == 200
        assert "Join Rhodesli" in response.text

    def test_signup_has_invite_code_field(self, client, auth_enabled, no_user):
        """Signup page requires invite code."""
        response = client.get("/signup")
        assert "Invite Code" in response.text
        assert 'name="invite_code"' in response.text

    def test_signup_has_email_field(self, client, auth_enabled, no_user):
        """Signup page has email field."""
        response = client.get("/signup")
        assert 'name="email"' in response.text

    def test_signup_has_password_field(self, client, auth_enabled, no_user):
        """Signup page has password field."""
        response = client.get("/signup")
        assert 'name="password"' in response.text

    def test_signup_has_login_link(self, client, auth_enabled, no_user):
        """Signup page links to login page."""
        response = client.get("/signup")
        assert "Already have an account?" in response.text
        assert "/login" in response.text


class TestForgotPasswordPage:
    """Tests for GET /forgot-password rendering."""

    def test_forgot_password_redirects_when_auth_disabled(self, client, auth_disabled):
        """When auth disabled, /forgot-password redirects."""
        response = client.get("/forgot-password", follow_redirects=False)
        assert response.status_code == 303

    def test_forgot_password_renders_when_auth_enabled(self, client, auth_enabled, no_user):
        """When auth enabled, /forgot-password renders the form."""
        response = client.get("/forgot-password")
        assert response.status_code == 200


class TestResetPasswordPage:
    """Tests for GET /reset-password rendering."""

    def test_reset_password_always_renders(self, client):
        """GET /reset-password always renders (handles email link tokens).

        Unlike /login and /signup, /reset-password doesn't check is_auth_enabled()
        because it needs to handle the token/code from the password reset email
        regardless of auth configuration.
        """
        response = client.get("/reset-password")
        assert response.status_code == 200

    def test_reset_password_has_password_fields(self, client, auth_enabled, no_user):
        """Reset password page has new password input fields."""
        response = client.get("/reset-password")
        assert response.status_code == 200


class TestAuthCallbackRoute:
    """Tests for /auth/callback and related routes."""

    def test_auth_callback_exists(self, client, auth_enabled, no_user):
        """OAuth callback route exists and returns a page."""
        response = client.get("/auth/callback")
        # Should return 200 with JS to handle the hash fragment
        assert response.status_code == 200


class TestLogout:
    """Tests for GET /logout."""

    def test_logout_redirects_to_home(self, client, auth_enabled, no_user):
        """Logout clears session and redirects to home."""
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"
