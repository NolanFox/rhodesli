"""Tests for WORKSPACE-001: Personal archive creation on signup."""

import pytest
from unittest.mock import patch, AsyncMock


# auth_routes accesses functions via _main_mod (app.main), but some auth
# functions live in app.auth and may be dynamically resolved.  We patch on
# the _main_mod reference that auth_routes actually calls.
_MAIN = "app.auth_routes._main_mod"


@pytest.fixture
def mock_auth_enabled():
    """Mock auth as enabled."""
    with patch(f"{_MAIN}.is_auth_enabled", return_value=True):
        yield


@pytest.fixture
def mock_valid_invite():
    """Mock invite code validation as passing."""
    with patch(f"{_MAIN}.validate_invite_code", create=True, return_value=True):
        yield


@pytest.fixture
def mock_invalid_invite():
    """Mock invite code validation as failing."""
    with patch(f"{_MAIN}.validate_invite_code", create=True, return_value=False):
        yield


@pytest.fixture
def mock_signup_success():
    """Mock successful Supabase signup."""
    user = {"id": "user-uuid-1234", "email": "test@example.com"}
    with patch(f"{_MAIN}.signup_with_supabase", create=True, new_callable=AsyncMock, return_value=(user, None)):
        yield user


@pytest.fixture
def mock_signup_failure():
    """Mock failed Supabase signup."""
    with patch(
        f"{_MAIN}.signup_with_supabase",
        create=True,
        new_callable=AsyncMock,
        return_value=(None, "Email already registered"),
    ):
        yield


class TestWorkspaceSignup:
    """Test personal archive creation during signup flow."""

    def test_successful_signup_calls_create_personal_archive(
        self, client, mock_auth_enabled, mock_valid_invite, mock_signup_success
    ):
        """After successful signup, create_personal_archive is called with user_id and email."""
        with patch("app.auth_routes.create_personal_archive") as mock_create:
            resp = client.post(
                "/signup",
                data={"email": "test@example.com", "password": "securepass123", "invite_code": "VALID"},
                follow_redirects=False,
            )
            assert resp.status_code == 303
            mock_create.assert_called_once_with("user-uuid-1234", "test@example.com")

    def test_signup_succeeds_even_if_archive_creation_fails(
        self, client, mock_auth_enabled, mock_valid_invite, mock_signup_success
    ):
        """Signup should still redirect to / even if create_personal_archive raises."""
        with patch("app.auth_routes.create_personal_archive", side_effect=Exception("DB error")):
            resp = client.post(
                "/signup",
                data={"email": "test@example.com", "password": "securepass123", "invite_code": "VALID"},
                follow_redirects=False,
            )
            # Signup still succeeds — archive failure is non-blocking
            assert resp.status_code == 303
            assert resp.headers.get("location") == "/"

    def test_archive_not_created_on_invalid_invite(self, client, mock_auth_enabled, mock_invalid_invite):
        """create_personal_archive should NOT be called when invite code is invalid."""
        with patch("app.auth_routes.create_personal_archive") as mock_create:
            resp = client.post(
                "/signup",
                data={"email": "test@example.com", "password": "securepass123", "invite_code": "WRONG"},
            )
            # Error page returned (not redirect)
            assert resp.status_code == 200
            assert b"Invalid invite code" in resp.content
            mock_create.assert_not_called()

    def test_archive_not_created_on_supabase_error(
        self, client, mock_auth_enabled, mock_valid_invite, mock_signup_failure
    ):
        """create_personal_archive should NOT be called when Supabase signup fails."""
        with patch("app.auth_routes.create_personal_archive") as mock_create:
            resp = client.post(
                "/signup",
                data={"email": "test@example.com", "password": "securepass123", "invite_code": "VALID"},
            )
            assert resp.status_code == 200
            assert b"Email already registered" in resp.content
            mock_create.assert_not_called()

    def test_redirect_goes_to_home_after_signup(
        self, client, mock_auth_enabled, mock_valid_invite, mock_signup_success
    ):
        """After successful signup, redirect should go to /."""
        with patch("app.auth_routes.create_personal_archive"):
            resp = client.post(
                "/signup",
                data={"email": "test@example.com", "password": "securepass123", "invite_code": "VALID"},
                follow_redirects=False,
            )
            assert resp.status_code == 303
            assert resp.headers.get("location") == "/"
