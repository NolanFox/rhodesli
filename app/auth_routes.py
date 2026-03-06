"""
Auth routes extracted from app/main.py.

All /login, /signup, /forgot-password, /reset-password, /auth/*, /logout routes.
"""

from fasthtml.common import *
from starlette.responses import RedirectResponse, JSONResponse

# Import route decorator only (bound once, never reassigned)
from app.main import rt

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod


@rt("/login")
def get(sess, next: str = ""):
    """Login page. Redirects to home if already authenticated or auth disabled."""
    if not _main_mod.is_auth_enabled():
        return RedirectResponse("/", status_code=303)
    if sess.get("auth"):
        return RedirectResponse(next or "/", status_code=303)

    # Build POST action with ?next= if provided
    post_action = "/login"
    if next:
        post_action = f"/login?next={next}"

    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Login - Rhodesli"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Script(src="https://cdn.tailwindcss.com"),
        ),
        Body(
            Div(
                H1("Rhodesli", cls="text-2xl font-bold mb-2"),
                P("Family Heritage Archive", cls="text-gray-400 mb-8"),
                Form(
                    Div(
                        Label("Email", fr="email", cls="block text-sm mb-1"),
                        Input(
                            type="email",
                            name="email",
                            id="email",
                            required=True,
                            cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                        ),
                        cls="mb-4",
                    ),
                    Div(
                        Label("Password", fr="password", cls="block text-sm mb-1"),
                        Input(
                            type="password",
                            name="password",
                            id="password",
                            required=True,
                            cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                        ),
                        cls="mb-4",
                    ),
                    Button(
                        "Sign In",
                        type="submit",
                        cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium",
                    ),
                    method="post",
                    action=post_action,
                    cls="space-y-2",
                ),
                Div(
                    Div(cls="flex-grow border-t border-gray-600"),
                    Span("or", cls="px-4 text-gray-500 text-sm"),
                    Div(cls="flex-grow border-t border-gray-600"),
                    cls="flex items-center my-6",
                )
                if _main_mod.get_oauth_url("google")
                else None,
                A(
                    NotStr(
                        '<svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>'
                    ),
                    Span("Sign in with Google"),
                    href=_main_mod.get_oauth_url("google") or "#",
                    style="display: flex; align-items: center; gap: 12px; padding: 0 16px; height: 40px; "
                    "background: white; border: 1px solid #dadce0; border-radius: 4px; cursor: pointer; "
                    "font-family: 'Roboto', Arial, sans-serif; font-size: 14px; color: #3c4043; "
                    "font-weight: 500; text-decoration: none; justify-content: center; width: 100%;",
                )
                if _main_mod.get_oauth_url("google")
                else None,
                P(
                    A("Forgot password?", href="/forgot-password", cls="text-blue-400 hover:underline"),
                    cls="mt-4 text-center text-sm",
                ),
                P(
                    "Need an account? ",
                    A("Sign up with invite code", href="/signup", cls="text-blue-400 hover:underline"),
                    cls="mt-2 text-gray-400 text-sm",
                ),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
            ),
            cls="min-h-screen bg-gray-900 text-white",
        ),
    )


@rt("/login")
async def post(email: str, password: str, sess, next: str = ""):
    """Handle login form submission."""
    user, error = await _main_mod.login_with_supabase(email, password)
    if error:
        return Html(
            Head(
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Title("Login - Rhodesli"),
                Script(src="https://cdn.tailwindcss.com"),
            ),
            Body(
                Div(
                    H1("Rhodesli", cls="text-2xl font-bold mb-2"),
                    P(error, cls="text-red-400 mb-4 text-sm"),
                    Form(
                        Div(
                            Label("Email", fr="email", cls="block text-sm mb-1"),
                            Input(
                                type="email",
                                name="email",
                                id="email",
                                value=email,
                                required=True,
                                cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                            ),
                            cls="mb-4",
                        ),
                        Div(
                            Label("Password", fr="password", cls="block text-sm mb-1"),
                            Input(
                                type="password",
                                name="password",
                                id="password",
                                required=True,
                                cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                            ),
                            cls="mb-4",
                        ),
                        Button(
                            "Sign In",
                            type="submit",
                            cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium",
                        ),
                        method="post",
                        action="/login",
                    ),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
                ),
                cls="min-h-screen bg-gray-900 text-white",
            ),
        )
    sess["auth"] = user
    # Redirect to the page they were trying to reach, or home
    redirect_to = next if next and next.startswith("/") else "/"
    return RedirectResponse(redirect_to, status_code=303)


@rt("/login/modal")
async def post(email: str, password: str, sess):
    """Handle login from the modal context. Returns error text or HX-Refresh on success."""
    user, error = await _main_mod.login_with_supabase(email, password)
    if error:
        return error
    sess["auth"] = user
    return Response("", headers={"HX-Refresh": "true"})


@rt("/signup")
def get(sess):
    """Signup page with invite code."""
    if not _main_mod.is_auth_enabled():
        return RedirectResponse("/", status_code=303)
    if sess.get("auth"):
        return RedirectResponse("/", status_code=303)

    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Sign Up - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
        ),
        Body(
            Div(
                H1("Join Rhodesli", cls="text-2xl font-bold mb-2"),
                P("Invite-only registration", cls="text-gray-400 mb-8"),
                Form(
                    Div(
                        Label("Invite Code", fr="invite_code", cls="block text-sm mb-1"),
                        Input(
                            type="text",
                            name="invite_code",
                            id="invite_code",
                            required=True,
                            cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                        ),
                        cls="mb-4",
                    ),
                    Div(
                        Label("Email", fr="email", cls="block text-sm mb-1"),
                        Input(
                            type="email",
                            name="email",
                            id="email",
                            required=True,
                            cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                        ),
                        cls="mb-4",
                    ),
                    Div(
                        Label("Password", fr="password", cls="block text-sm mb-1"),
                        Input(
                            type="password",
                            name="password",
                            id="password",
                            required=True,
                            minlength="8",
                            cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                        ),
                        P("Minimum 8 characters", cls="text-gray-500 text-xs mt-1"),
                        cls="mb-4",
                    ),
                    Button(
                        "Create Account",
                        type="submit",
                        cls="w-full p-2 bg-green-600 hover:bg-green-700 rounded text-white font-medium",
                    ),
                    method="post",
                    action="/signup",
                ),
                P(
                    "Already have an account? ",
                    A("Sign in", href="/login", cls="text-blue-400 hover:underline"),
                    cls="mt-4 text-gray-400 text-sm",
                ),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
            ),
            cls="min-h-screen bg-gray-900 text-white",
        ),
    )


@rt("/signup")
async def post(email: str, password: str, invite_code: str, sess):
    """Handle signup form submission."""
    if not _main_mod.validate_invite_code(invite_code):
        error = "Invalid invite code"
        user = None
    else:
        user, error = await _main_mod.signup_with_supabase(email, password)
    if error:
        return Html(
            Head(
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Title("Sign Up - Rhodesli"),
                Script(src="https://cdn.tailwindcss.com"),
            ),
            Body(
                Div(
                    H1("Join Rhodesli", cls="text-2xl font-bold mb-2"),
                    P(error, cls="text-red-400 mb-4 text-sm"),
                    Form(
                        Div(
                            Label("Invite Code", fr="invite_code", cls="block text-sm mb-1"),
                            Input(
                                type="text",
                                name="invite_code",
                                id="invite_code",
                                value=invite_code,
                                required=True,
                                cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                            ),
                            cls="mb-4",
                        ),
                        Div(
                            Label("Email", fr="email", cls="block text-sm mb-1"),
                            Input(
                                type="email",
                                name="email",
                                id="email",
                                value=email,
                                required=True,
                                cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                            ),
                            cls="mb-4",
                        ),
                        Div(
                            Label("Password", fr="password", cls="block text-sm mb-1"),
                            Input(
                                type="password",
                                name="password",
                                id="password",
                                required=True,
                                minlength="8",
                                cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                            ),
                            cls="mb-4",
                        ),
                        Button(
                            "Create Account",
                            type="submit",
                            cls="w-full p-2 bg-green-600 hover:bg-green-700 rounded text-white font-medium",
                        ),
                        method="post",
                        action="/signup",
                    ),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
                ),
                cls="min-h-screen bg-gray-900 text-white",
            ),
        )
    sess["auth"] = user
    return RedirectResponse("/", status_code=303)


@rt("/forgot-password")
def get(sess):
    """Forgot password page."""
    if not _main_mod.is_auth_enabled():
        return RedirectResponse("/", status_code=303)

    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Reset Password - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
        ),
        Body(
            Div(
                H1("Reset Password", cls="text-2xl font-bold mb-2"),
                P("Enter your email to receive a reset link", cls="text-gray-400 mb-6"),
                Form(
                    Div(
                        Label("Email", fr="email", cls="block text-sm mb-1"),
                        Input(
                            type="email",
                            name="email",
                            id="email",
                            required=True,
                            cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                        ),
                        cls="mb-4",
                    ),
                    Button(
                        "Send Reset Link",
                        type="submit",
                        cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium",
                    ),
                    method="post",
                    action="/forgot-password",
                ),
                P(A("← Back to Login", href="/login", cls="text-blue-400 hover:underline"), cls="mt-6 text-center"),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
            ),
            cls="min-h-screen bg-gray-900 text-white",
        ),
    )


@rt("/forgot-password")
async def post(email: str, sess):
    """Handle forgot password form."""
    success, error = await _main_mod.send_password_reset(email)

    # Always show success message to avoid email enumeration
    msg = "If an account exists with that email, you'll receive a reset link."
    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Reset Password - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
        ),
        Body(
            Div(
                H1("Reset Password", cls="text-2xl font-bold mb-2"),
                P(msg, cls="text-green-400 mb-6 text-sm"),
                P(A("← Back to Login", href="/login", cls="text-blue-400 hover:underline"), cls="mt-6 text-center"),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
            ),
            cls="min-h-screen bg-gray-900 text-white",
        ),
    )


@rt("/reset-password")
def get(sess):
    """Handle reset password callback from email link. Tokens are in URL fragment."""
    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Set New Password - Rhodesli"),
            Script(src="https://cdn.tailwindcss.com"),
            Script("""
                document.addEventListener('DOMContentLoaded', function() {
                    // Check for PKCE code in query params (Supabase email flow)
                    const urlParams = new URLSearchParams(window.location.search);
                    const code = urlParams.get('code');

                    if (code) {
                        // Exchange PKCE code server-side for access token
                        document.getElementById('error-msg').textContent = 'Verifying your link...';
                        fetch('/auth/exchange-code', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({code: code})
                        }).then(r => r.json()).then(data => {
                            if (data.access_token) {
                                document.getElementById('access_token').value = data.access_token;
                                document.getElementById('reset-form').style.display = 'block';
                                document.getElementById('error-msg').style.display = 'none';
                            } else {
                                document.getElementById('error-msg').textContent = data.error || 'This link has expired. Please request a new one.';
                            }
                        }).catch(function() {
                            document.getElementById('error-msg').textContent = 'Something went wrong. Please request a new reset link.';
                        });
                        return;
                    }

                    // Legacy: check for access_token in URL hash fragment
                    const hash = window.location.hash.substring(1);
                    const params = new URLSearchParams(hash);
                    const accessToken = params.get('access_token');
                    const type = params.get('type');

                    if (accessToken && type === 'recovery') {
                        document.getElementById('access_token').value = accessToken;
                        document.getElementById('reset-form').style.display = 'block';
                        document.getElementById('error-msg').style.display = 'none';
                    } else if (!accessToken && !code) {
                        document.getElementById('error-msg').textContent = 'Invalid or expired reset link. Please request a new one.';
                    }
                });
            """),
        ),
        Body(
            Div(
                H1("Set New Password", cls="text-2xl font-bold mb-6"),
                P("Invalid or expired reset link.", id="error-msg", cls="text-red-400 mb-4 text-sm"),
                Form(
                    Input(type="hidden", name="access_token", id="access_token"),
                    Div(
                        Label("New Password", fr="password", cls="block text-sm mb-1"),
                        Input(
                            type="password",
                            name="password",
                            id="password",
                            required=True,
                            minlength="8",
                            cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                        ),
                        P("Minimum 8 characters", cls="text-gray-500 text-xs mt-1"),
                        cls="mb-4",
                    ),
                    Div(
                        Label("Confirm Password", fr="password_confirm", cls="block text-sm mb-1"),
                        Input(
                            type="password",
                            name="password_confirm",
                            id="password_confirm",
                            required=True,
                            minlength="8",
                            cls="w-full p-2 rounded bg-gray-700 text-white border border-gray-600",
                        ),
                        cls="mb-4",
                    ),
                    Button(
                        "Update Password",
                        type="submit",
                        cls="w-full p-2 bg-green-600 hover:bg-green-700 rounded text-white font-medium",
                    ),
                    method="post",
                    action="/reset-password",
                    id="reset-form",
                    style="display:none",
                ),
                P(A("← Back to Login", href="/login", cls="text-blue-400 hover:underline"), cls="mt-6 text-center"),
                cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
            ),
            cls="min-h-screen bg-gray-900 text-white",
        ),
    )


@rt("/reset-password")
async def post(access_token: str, password: str, password_confirm: str, sess):
    """Handle password reset form submission."""
    error = None
    if not access_token:
        error = "Invalid reset link. Please request a new one."
    elif password != password_confirm:
        error = "Passwords do not match."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."

    if error:
        return Html(
            Head(
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Title("Set New Password - Rhodesli"),
                Script(src="https://cdn.tailwindcss.com"),
            ),
            Body(
                Div(
                    H1("Set New Password", cls="text-2xl font-bold mb-6"),
                    P(error, cls="text-red-400 mb-4 text-sm"),
                    P(
                        A("← Request a new reset link", href="/forgot-password", cls="text-blue-400 hover:underline"),
                        cls="mt-4",
                    ),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
                ),
                cls="min-h-screen bg-gray-900 text-white",
            ),
        )

    success, err = await _main_mod.update_password(access_token, password)

    if success:
        return Html(
            Head(
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Title("Password Updated - Rhodesli"),
                Script(src="https://cdn.tailwindcss.com"),
            ),
            Body(
                Div(
                    H1("Password Updated", cls="text-2xl font-bold mb-4"),
                    P("Your password has been updated successfully.", cls="text-green-400 mb-6"),
                    A(
                        "Sign in with your new password",
                        href="/login",
                        cls="block w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium text-center",
                    ),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
                ),
                cls="min-h-screen bg-gray-900 text-white",
            ),
        )
    else:
        return Html(
            Head(
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Title("Set New Password - Rhodesli"),
                Script(src="https://cdn.tailwindcss.com"),
            ),
            Body(
                Div(
                    H1("Set New Password", cls="text-2xl font-bold mb-6"),
                    P(err or "Failed to update password.", cls="text-red-400 mb-4 text-sm"),
                    P(
                        A("← Request a new reset link", href="/forgot-password", cls="text-blue-400 hover:underline"),
                        cls="mt-4",
                    ),
                    cls="max-w-md mx-auto mt-10 sm:mt-20 p-4 sm:p-8 bg-gray-800 rounded-lg",
                ),
                cls="min-h-screen bg-gray-900 text-white",
            ),
        )


@rt("/auth/callback")
def get(sess):
    """Handle OAuth callback from social providers. Tokens are in URL fragment."""
    return Html(
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title("Logging in..."),
            Script(src="https://cdn.tailwindcss.com"),
            Script("""
                document.addEventListener('DOMContentLoaded', function() {
                    const hash = window.location.hash.substring(1);
                    const params = new URLSearchParams(hash);
                    const accessToken = params.get('access_token');

                    if (accessToken) {
                        fetch('/auth/session', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({access_token: accessToken})
                        }).then(r => r.json()).then(data => {
                            if (data.success) {
                                window.location.href = '/';
                            } else {
                                window.location.href = '/login?error=oauth_failed';
                            }
                        }).catch(() => {
                            window.location.href = '/login?error=oauth_failed';
                        });
                    } else {
                        window.location.href = '/login?error=oauth_failed';
                    }
                });
            """),
        ),
        Body(
            Div(
                P("Completing login...", cls="text-gray-400"),
                cls="flex items-center justify-center min-h-screen bg-gray-900",
            ),
        ),
    )


@rt("/auth/session")
async def post(request, sess):
    """Create session from OAuth access token."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request"}, status_code=400)

    access_token = data.get("access_token")
    if not access_token:
        return JSONResponse({"error": "No token"}, status_code=400)

    user, error = await _main_mod.get_user_from_token(access_token)
    if user:
        sess["auth"] = user
        # Submit any pending annotation stashed before OAuth login
        _main_mod._submit_pending_annotation(sess, user)
        return JSONResponse({"success": True})
    else:
        return JSONResponse({"error": error or "Failed to get user"}, status_code=401)


@rt("/auth/exchange-code")
async def post(request, sess):
    """Exchange a PKCE auth code for an access token (used by password recovery)."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid request"}, status_code=400)

    code = data.get("code")
    if not code:
        return JSONResponse({"error": "No code provided"}, status_code=400)

    result, error = await _main_mod.exchange_code_for_session(code)
    if result:
        return JSONResponse({"access_token": result["access_token"]})
    else:
        return JSONResponse({"error": error or "Code exchange failed"}, status_code=400)


@rt("/logout")
def get(sess):
    """Log out and redirect to home."""
    sess.clear()
    return RedirectResponse("/", status_code=303)
