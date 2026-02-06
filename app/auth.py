"""
Authentication module with role-based permissions.

Permission levels:
- Public: Can view everything (no login required)
- User: Can view + upload photos (login required)
- Admin: Can view + upload + edit/confirm/detach (admin flag required)

When SUPABASE_URL is not set, auth is disabled and all routes are accessible.
"""

import os
from dataclasses import dataclass
from functools import wraps

# Auth configuration from environment
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-secret-change-in-production")
INVITE_CODES = [c.strip() for c in os.getenv("INVITE_CODES", "").split(",") if c.strip()]

# Admin emails — users with these emails get admin privileges
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}


def is_auth_enabled() -> bool:
    """Check if authentication is configured."""
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


@dataclass
class User:
    id: str
    email: str
    is_admin: bool = False

    @classmethod
    def from_session(cls, session_data: dict) -> "User | None":
        if not session_data:
            return None
        email = session_data.get("email", "")
        return cls(
            id=session_data.get("id", ""),
            email=email,
            is_admin=email.lower() in ADMIN_EMAILS,
        )


def get_current_user(session: dict) -> User | None:
    """Get the current user from session, or None if not logged in."""
    user_data = session.get("auth")
    return User.from_session(user_data) if user_data else None


def is_admin(session: dict) -> bool:
    """Check if current user is an admin."""
    user = get_current_user(session)
    return user is not None and user.is_admin


def require_login(func):
    """Decorator: requires any logged-in user. Returns 303 redirect to /login."""
    @wraps(func)
    def wrapper(*args, sess, **kwargs):
        if not get_current_user(sess):
            from starlette.responses import RedirectResponse
            return RedirectResponse("/login", status_code=303)
        return func(*args, sess=sess, **kwargs)
    return wrapper


def require_admin(func):
    """Decorator: requires admin user. Returns 403 for non-admins, 303 redirect for anonymous."""
    @wraps(func)
    def wrapper(*args, sess, **kwargs):
        user = get_current_user(sess)
        if not user:
            from starlette.responses import RedirectResponse
            return RedirectResponse("/login", status_code=303)
        if not user.is_admin:
            from starlette.responses import Response
            return Response("Forbidden", status_code=403)
        return func(*args, sess=sess, **kwargs)
    return wrapper


def validate_invite_code(code: str) -> bool:
    """Check if invite code is valid."""
    return code.strip() in INVITE_CODES


async def signup_with_supabase(email: str, password: str) -> tuple[dict | None, str | None]:
    """Create a new user in Supabase via direct HTTP."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None, "Authentication not configured"

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SUPABASE_URL}/auth/v1/signup",
                json={"email": email, "password": password},
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                user = data.get("user", {})
                return {
                    "id": user.get("id"),
                    "email": user.get("email"),
                }, None
            else:
                error_data = response.json()
                msg = error_data.get("error_description") or error_data.get("msg") or "Signup failed"
                return None, msg
    except Exception as e:
        return None, f"Connection error: {e}"


async def send_password_reset(email: str) -> tuple[bool, str | None]:
    """Send password reset email via Supabase."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "Authentication not configured"

    import httpx

    try:
        site_url = os.getenv("SITE_URL", "https://rhodesli.nolanandrewfox.com")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SUPABASE_URL}/auth/v1/recover",
                json={
                    "email": email,
                },
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                return True, None
            else:
                error_data = response.json()
                msg = error_data.get("error_description") or error_data.get("msg") or "Failed to send reset email"
                return False, msg
    except Exception as e:
        return False, f"Connection error: {e}"


async def update_password(access_token: str, new_password: str) -> tuple[bool, str | None]:
    """Update user's password using their access token."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return False, "Authentication not configured"

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{SUPABASE_URL}/auth/v1/user",
                json={"password": new_password},
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                return True, None
            else:
                error_data = response.json()
                msg = error_data.get("error_description") or "Failed to update password"
                return False, msg
    except Exception as e:
        return False, f"Connection error: {e}"


ENABLED_OAUTH_PROVIDERS = {"google"}  # Facebook deferred — requires Meta Business Verification


def get_oauth_url(provider: str) -> str | None:
    """Get OAuth redirect URL for social login."""
    if provider not in ENABLED_OAUTH_PROVIDERS:
        return None
    if not SUPABASE_URL:
        return None
    site_url = os.getenv("SITE_URL", "https://rhodesli.nolanandrewfox.com")
    return f"{SUPABASE_URL}/auth/v1/authorize?provider={provider}&redirect_to={site_url}/auth/callback"


async def get_user_from_token(access_token: str) -> tuple[dict | None, str | None]:
    """Get user info from Supabase using an access token."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None, "Authentication not configured"

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {access_token}",
                },
            )

            if response.status_code == 200:
                user_data = response.json()
                return {
                    "id": user_data.get("id"),
                    "email": user_data.get("email"),
                }, None
            else:
                error_data = response.json()
                msg = error_data.get("error_description") or "Failed to get user"
                return None, msg
    except Exception as e:
        return None, f"Connection error: {e}"


async def login_with_supabase(email: str, password: str) -> tuple[dict | None, str | None]:
    """Authenticate user with Supabase via direct HTTP."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None, "Authentication not configured"

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                json={"email": email, "password": password},
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                data = response.json()
                user = data.get("user", {})
                return {
                    "id": user.get("id"),
                    "email": user.get("email"),
                }, None
            else:
                error_data = response.json()
                msg = error_data.get("error_description") or error_data.get("msg") or "Login failed"
                return None, msg
    except Exception as e:
        return None, f"Connection error: {e}"
