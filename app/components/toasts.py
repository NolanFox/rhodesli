"""
Toast notification components — extracted from app/main.py (Session 137).

Pure rendering functions for non-blocking notification UI elements.
"""

from fasthtml.common import Button, Div, Span

from core.ui_safety import ensure_utf8_display


def toast_container() -> Div:
    """
    Toast notification container.
    UX Intent: Non-blocking feedback for actions.
    """
    return Div(id="toast-container", cls="fixed top-4 right-4 z-[10001] flex flex-col gap-2")


def toast(message: str, variant: str = "info") -> Div:
    """
    Single toast notification.
    Variants: success, error, warning, info
    """
    # UI BOUNDARY: sanitize message for safe rendering
    safe_message = ensure_utf8_display(message)

    colors = {
        "success": "bg-emerald-600 text-white",
        "error": "bg-red-600 text-white",
        "warning": "bg-amber-500 text-white",
        "info": "bg-stone-700 text-white",
    }
    icons = {
        "success": "\u2713",
        "error": "\u2717",
        "warning": "\u26a0",
        "info": "\u2139",
    }
    return Div(
        Span(icons.get(variant, ""), cls="mr-2"),
        Span(safe_message),
        cls=f"px-4 py-3 rounded shadow-lg flex items-center {colors.get(variant, colors['info'])} animate-fade-in",
        # Auto-dismiss after 4 seconds
        **{"_": "on load wait 4s then remove me"},
    )


def toast_with_undo(
    message: str,
    source_id: str,
    target_id: str,
    variant: str = "info",
) -> Div:
    """
    Toast notification with inline Undo button (D5).

    Used for "Not Same Person" rejection - allows immediate reversal.
    Auto-dismisses after 8 seconds (longer than standard toast to allow undo).
    """
    colors = {
        "success": "bg-emerald-600 text-white",
        "error": "bg-red-600 text-white",
        "warning": "bg-amber-500 text-white",
        "info": "bg-stone-700 text-white",
    }
    icons = {
        "success": "\u2713",
        "error": "\u2717",
        "warning": "\u26a0",
        "info": "\u2139",
    }
    return Div(
        Span(icons.get(variant, ""), cls="mr-2"),
        Span(message, cls="flex-1"),
        Button(
            "Undo",
            cls="ml-3 px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"/api/identity/{source_id}/unreject/{target_id}",
            hx_swap="outerHTML",
            hx_target="closest div",  # Replace the toast itself
            type="button",
        ),
        cls=f"px-4 py-3 rounded shadow-lg flex items-center {colors.get(variant, colors['info'])} animate-fade-in",
        # Longer dismiss time to allow undo
        **{"_": "on load wait 8s then remove me"},
    )
