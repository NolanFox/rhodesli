"""
Modal dialog components — extracted from app/main.py (Session 137).

Modal containers for photo viewing, face comparison, login, and confirmations.
Content is populated dynamically via HTMX.
"""

from fasthtml.common import (
    A,
    Button,
    Div,
    Form,
    H2,
    Input,
    Label,
    NotStr,
    P,
    Span,
)


def photo_modal() -> Div:
    """
    Modal container for photo context viewer.
    Hidden by default, shown via HTMX when "View Photo" is clicked.

    Z-index hierarchy:
    - Confirm modal: z-[10002] (above compare -- always topmost interactive)
    - Toast container: z-[10001] (above all content modals)
    - Compare modal: z-[10000] (above photo modal)
    - Photo modal: z-[9999] (above page content)
    - Backdrop: absolute, no z-index (first child, renders behind content)
    - Content: relative, no z-index (second child, renders above backdrop)
    """
    return Div(
        # Backdrop - absolute within the fixed parent, click to close
        Div(
            cls="absolute inset-0 bg-black/80",
            **{"_": "on click add .hidden to #photo-modal"},
        ),
        # Modal content - relative positioning to sit above backdrop
        Div(
            # Header with close button
            Div(
                H2("Photo Context", cls="text-xl font-serif font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click add .hidden to #photo-modal"},
                    type="button",
                    aria_label="Close modal",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700",
            ),
            # Content area (populated by HTMX)
            Div(
                P("Loading...", cls="text-slate-400 text-center py-8"),
                id="photo-modal-content",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-full sm:max-w-5xl max-h-[90vh] overflow-auto p-3 sm:p-6 relative border border-slate-700",
        ),
        id="photo-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-2 sm:p-4 z-[9999]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
        tabindex="-1",
    )


def compare_modal() -> Div:
    """
    Side-by-side comparison modal for evaluating merge candidates.
    Shows the source identity's best face alongside the neighbor's best face.
    """
    return Div(
        # Backdrop
        Div(
            cls="absolute inset-0 bg-black/85",
            **{"_": "on click add .hidden to #compare-modal"},
        ),
        # Content
        Div(
            # Header
            Div(
                H2("Compare Faces", cls="text-xl font-serif font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click add .hidden to #compare-modal"},
                    type="button",
                    aria_label="Close comparison",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700",
            ),
            # Comparison content (populated by HTMX)
            Div(
                P("Loading...", cls="text-slate-400 text-center py-8"),
                id="compare-modal-content",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-full sm:max-w-[90vw] lg:max-w-7xl max-h-[90vh] overflow-auto p-3 sm:p-6 relative border border-slate-700",
        ),
        id="compare-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-2 sm:p-4 z-[10000]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
    )


def login_modal() -> Div:
    """Login modal for unauthenticated HTMX action attempts.
    Shown by htmx:beforeSwap handler when server returns 401."""
    # Lazy import to ensure test patches on app.main.get_oauth_url work
    import app.main as _main_mod

    google_url = _main_mod.get_oauth_url("google")
    return Div(
        Div(cls="absolute inset-0 bg-black/80", **{"_": "on click add .hidden to #login-modal"}),
        Div(
            Div(
                H2("Sign in to continue", cls="text-xl font-bold text-white"),
                Button(
                    "X",
                    cls="text-slate-400 hover:text-white text-xl font-bold",
                    **{"_": "on click add .hidden to #login-modal"},
                    type="button",
                    aria_label="Close",
                ),
                cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700",
            ),
            P("Sign in to contribute to the archive.", id="login-modal-message", cls="text-slate-400 mb-6 text-sm"),
            Form(
                Div(
                    Label("Email", fr="modal-email", cls="block text-sm mb-1 text-slate-300"),
                    Input(
                        type="email",
                        name="email",
                        id="modal-email",
                        required=True,
                        cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600",
                    ),
                    cls="mb-4",
                ),
                Div(
                    Label("Password", fr="modal-password", cls="block text-sm mb-1 text-slate-300"),
                    Input(
                        type="password",
                        name="password",
                        id="modal-password",
                        required=True,
                        cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600",
                    ),
                    cls="mb-4",
                ),
                Button(
                    "Sign In",
                    type="submit",
                    cls="w-full p-2 bg-indigo-600 hover:bg-indigo-500 rounded text-white font-medium",
                ),
                Div(id="login-modal-error", cls="text-red-400 text-sm mt-2"),
                hx_post="/login/modal",
                hx_target="#login-modal-error",
                hx_swap="innerHTML",
            ),
            # Google OAuth divider + button
            Div(
                Div(cls="flex-grow border-t border-slate-600"),
                Span("or", cls="px-4 text-slate-500 text-sm"),
                Div(cls="flex-grow border-t border-slate-600"),
                cls="flex items-center my-4",
            )
            if google_url
            else None,
            A(
                NotStr(
                    '<svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>'
                ),
                Span("Sign in with Google"),
                href=google_url or "#",
                style="display: flex; align-items: center; gap: 12px; padding: 0 16px; height: 40px; "
                "background: white; border: 1px solid #dadce0; border-radius: 4px; cursor: pointer; "
                "font-family: 'Roboto', Arial, sans-serif; font-size: 14px; color: #3c4043; "
                "font-weight: 500; text-decoration: none; justify-content: center; width: 100%;",
            )
            if google_url
            else None,
            Div(
                P(A("Forgot password?", href="/forgot-password", cls="text-indigo-400 hover:underline"), cls="text-sm"),
                P(
                    "No account? ",
                    A("Sign up with invite code", href="/signup", cls="text-indigo-400 hover:underline"),
                    cls="text-sm text-slate-400",
                ),
                cls="mt-4 text-center space-y-1",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-8 relative border border-slate-700",
        ),
        id="login-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[9998]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
    )


def confirm_modal() -> Div:
    """Styled confirmation modal replacing native browser confirm().
    Shown by htmx:confirm event handler."""
    return Div(
        Div(cls="absolute inset-0 bg-black/80", **{"_": "on click add .hidden to #confirm-modal"}),
        Div(
            P("", id="confirm-modal-message", cls="text-white text-xl sm:text-lg mb-6"),
            Div(
                Button(
                    "Cancel",
                    id="confirm-modal-no",
                    type="button",
                    cls="px-4 py-2 bg-slate-600 text-white rounded hover:bg-slate-500",
                ),
                Button(
                    "Confirm",
                    id="confirm-modal-yes",
                    type="button",
                    cls="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-500 font-bold",
                ),
                cls="flex justify-end gap-3",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-6 relative border border-slate-700",
        ),
        id="confirm-modal",
        cls="hidden fixed inset-0 flex items-center justify-center p-4 z-[10002]",
        **{"_": "on keydown[key=='Escape'] add .hidden to me"},
    )
