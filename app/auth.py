"""
Authentication module using Supabase.

Implements invite-only signup with session management.
When SUPABASE_URL is not set, auth is disabled and all routes are accessible.
"""

import os

# Auth configuration from environment
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-in-production")
INVITE_CODES = [c.strip() for c in os.getenv("INVITE_CODES", "").split(",") if c.strip()]

_supabase_client = None


def is_auth_enabled() -> bool:
    """Check if authentication is configured."""
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


def get_supabase():
    """Get the Supabase client (lazy initialization)."""
    global _supabase_client
    if not is_auth_enabled():
        return None
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _supabase_client


def login_user(email: str, password: str) -> tuple[dict | None, str | None]:
    """
    Attempt to log in a user.
    Returns (user_data, error_message).
    """
    client = get_supabase()
    if not client:
        return None, "Authentication not configured"

    try:
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return {"email": response.user.email, "id": response.user.id}, None
    except Exception as e:
        return None, str(e)


def signup_user(email: str, password: str, invite_code: str) -> tuple[dict | None, str | None]:
    """
    Register a new user (invite-only).
    Returns (user_data, error_message).
    """
    if not INVITE_CODES:
        return None, "No invite codes configured"
    if invite_code not in INVITE_CODES:
        return None, "Invalid invite code"

    client = get_supabase()
    if not client:
        return None, "Authentication not configured"

    try:
        response = client.auth.sign_up({
            "email": email,
            "password": password
        })
        return {"email": response.user.email, "id": response.user.id}, None
    except Exception as e:
        return None, str(e)


def logout_user():
    """Sign out the current user from Supabase."""
    client = get_supabase()
    if client:
        try:
            client.auth.sign_out()
        except Exception:
            pass


# Routes that don't require authentication
AUTH_SKIP_ROUTES = [
    "/login", "/signup", "/logout", "/health",
    "/static", "/favicon.ico",
]
