"""
Form helper components — extracted from app/main.py (Session 137).

Input components, datalists, search sections, and image transform tools.
"""

from fasthtml.common import (
    Button,
    Div,
    Form,
    H4,
    H5,
    Input,
    Option,
    Select,
    Span,
)


def parse_transform_to_css(transform_str: str) -> str:
    """Convert a transform string like 'rotate:90,flipH' to CSS transform value.

    Supported transforms:
    - rotate:90, rotate:180, rotate:270 -- clockwise rotation
    - flipH -- horizontal mirror (scaleX(-1))
    - flipV -- vertical mirror (scaleY(-1))
    - invert -- handled separately via CSS filter, not transform

    Returns CSS transform property value (e.g., 'rotate(90deg) scaleX(-1)').
    """
    if not transform_str or not transform_str.strip():
        return ""

    parts = [p.strip() for p in transform_str.split(",") if p.strip()]
    css_parts = []
    for part in parts:
        if part.startswith("rotate:"):
            degrees = part.split(":")[1]
            css_parts.append(f"rotate({degrees}deg)")
        elif part == "flipH":
            css_parts.append("scaleX(-1)")
        elif part == "flipV":
            css_parts.append("scaleY(-1)")
        # 'invert' is handled via CSS filter, not transform
    return " ".join(css_parts)


def parse_transform_to_filter(transform_str: str) -> str:
    """Extract CSS filter from transform string (for 'invert')."""
    if not transform_str or "invert" not in transform_str:
        return ""
    return "invert(1)"


def _suggest_name_form(identity_id: str, nav_prefix: str = "") -> Div:
    """Hidden form for suggesting a name for an unidentified person."""
    return Div(
        H4("I Know This Person", cls="text-sm font-medium text-white mb-2"),
        Form(
            Input(type="hidden", name="target_type", value="identity"),
            Input(type="hidden", name="target_id", value=identity_id),
            Input(type="hidden", name="annotation_type", value="name_suggestion"),
            Input(
                name="value",
                placeholder="Enter name...",
                cls="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-white placeholder-slate-400",
                required=True,
            ),
            Select(
                Option("I'm certain", value="certain"),
                Option("Likely", value="likely", selected=True),
                Option("Just a guess", value="guess"),
                name="confidence",
                cls="w-full mt-2 bg-slate-700 border border-slate-600 rounded px-5 py-4 sm:px-3 sm:py-1.5 text-sm text-white",
            ),
            Input(
                name="reason",
                placeholder="How do you know? (optional)",
                cls="w-full mt-2 bg-slate-700 border border-slate-600 rounded px-3 py-2 text-sm text-white placeholder-slate-400",
            ),
            Button(
                "Submit Suggestion",
                type="submit",
                cls="mt-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded hover:bg-indigo-500",
            ),
            hx_post=f"{nav_prefix}/api/annotations/submit",
            hx_swap="beforeend",
            hx_target="#toast-container",
            cls="space-y-0",
        ),
        cls="hidden mt-4 p-4 bg-slate-900/50 border border-indigo-500/30 rounded-lg",
        id=f"suggest-name-{identity_id}",
    )


def manual_search_section(identity_id: str, nav_prefix: str = "") -> Div:
    """
    Manual search input and results container.
    Positioned in neighbors sidebar after Load More, before Rejected section.
    """
    return Div(
        H5("Manual Search", cls="text-sm font-semibold text-slate-300 mb-2"),
        Input(
            type="text",
            name="q",
            placeholder="Search by name...",
            cls="w-full px-3 py-2 text-sm bg-slate-800 border border-slate-600 text-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder-slate-500",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/search",
            hx_trigger="keyup changed delay:300ms",
            hx_target=f"#search-results-{identity_id}",
            hx_include="this",
        ),
        Div(id=f"search-results-{identity_id}", cls="mt-2"),
        cls="mt-4 pt-3 border-t border-slate-600",
    )
