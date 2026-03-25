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


def image_transform_toolbar(photo_id: str, target: str = "front") -> Div:
    """Admin toolbar for non-destructive image orientation.

    target: 'front' or 'back' -- which image side to transform.
    """
    field_name = "transform" if target == "front" else "back_transform"
    label = "Front orientation" if target == "front" else "Back orientation"

    def _btn(icon_label, transform_val, danger=False):
        cls_base = "px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs rounded transition-colors"
        cls_color = (
            "bg-red-900/50 hover:bg-red-800/50 text-red-300"
            if danger
            else "bg-slate-700 hover:bg-slate-600 text-slate-200"
        )
        return Button(
            icon_label,
            type="button",
            hx_post=f"/api/photo/{photo_id}/transform",
            hx_vals=f'{{"field": "{field_name}", "value": "{transform_val}"}}',
            hx_target=f"#photo-detail-{photo_id}",
            hx_swap="outerHTML",
            cls=f"{cls_base} {cls_color}",
        )

    return Div(
        Span(label, cls="text-[10px] text-slate-500 uppercase tracking-wider block mb-1"),
        Div(
            _btn("Rotate 90", "rotate:90"),
            _btn("Rotate 180", "rotate:180"),
            _btn("Rotate 270", "rotate:270"),
            _btn("Flip H", "flipH"),
            _btn("Flip V", "flipV"),
            _btn("Invert", "invert"),
            _btn("Reset", "", danger=True),
            cls="flex flex-wrap gap-1",
        ),
        cls="mt-2",
    )


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
