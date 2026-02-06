"""Shared test fixtures for auth, permission, and UI tests."""

import os
import pytest
from unittest.mock import patch

from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Auth state fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Create a fresh test client for the FastHTML app."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_enabled():
    """Mock auth as enabled (Supabase configured)."""
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.auth.is_auth_enabled", return_value=True):
        yield


@pytest.fixture
def auth_disabled():
    """Mock auth as disabled (no Supabase configured)."""
    with patch("app.main.is_auth_enabled", return_value=False), \
         patch("app.auth.is_auth_enabled", return_value=False):
        yield


@pytest.fixture
def no_user():
    """Mock no user logged in (anonymous)."""
    with patch("app.main.get_current_user", return_value=None):
        yield


@pytest.fixture
def regular_user():
    """Mock a logged-in non-admin user."""
    from app.auth import User
    user = User(id="test-user-1", email="user@example.com", is_admin=False)
    with patch("app.main.get_current_user", return_value=user):
        yield user


@pytest.fixture
def admin_user():
    """Mock a logged-in admin user."""
    from app.auth import User
    user = User(id="test-admin-1", email="admin@rhodesli.test", is_admin=True)
    with patch("app.main.get_current_user", return_value=user):
        yield user


@pytest.fixture
def google_oauth_enabled():
    """Mock Google OAuth as available."""
    with patch("app.main.get_oauth_url", side_effect=lambda p: (
        "https://fvynibivlphxwfowzkjl.supabase.co/auth/v1/authorize?provider=google&redirect_to=https://rhodesli.nolanandrewfox.com/auth/callback"
        if p == "google" else None
    )):
        yield


@pytest.fixture
def google_oauth_disabled():
    """Mock Google OAuth as unavailable."""
    with patch("app.main.get_oauth_url", return_value=None):
        yield
