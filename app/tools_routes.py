"""
Tools routes — standalone, community-agnostic tool pages.

Provides:
- /tools — landing page with tool cards
- /estimate redirect → /tools/estimate
- /compare redirect → /tools/compare
- tools_nav_bar() — shared navigation bar for tool pages
"""

from fasthtml.common import *
from starlette.responses import RedirectResponse

from app.main import rt

import app.main as _main_mod


def tools_nav_bar(active_tool=None):
    """Render a navigation bar for tool pages.

    Args:
        active_tool: One of "hub", "estimate", "compare", or None.
    """
    tools = [
        ("Tools", "/tools", "hub"),
        ("Date Estimator", "/tools/estimate", "estimate"),
        ("Face Compare", "/tools/compare", "compare"),
    ]
    _active_cls = "font-bold text-blue-400 border-b-2 border-blue-400 pb-1"
    _inactive_cls = "text-slate-400 hover:text-blue-400 transition-colors"

    links = []
    for label, href, key in tools:
        cls = _active_cls if key == active_tool else _inactive_cls
        links.append(A(label, href=href, cls=f"text-sm py-3 {cls}"))

    return Div(
        *links,
        cls="flex gap-6 px-6 py-3 border-b border-slate-700/50 bg-slate-800/30",
    )


@rt("/tools")
def get(sess=None):
    """Tools Hub — landing page for standalone ML tools."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    nav_links = _main_mod._public_nav_links(active="tools", user=user)

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
    """)

    tool_cards = Div(
        # Date Estimator card
        A(
            Div(
                Div(
                    NotStr(
                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-amber-400" '
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">'
                        '<path stroke-linecap="round" stroke-linejoin="round" '
                        'd="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 '
                        "012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 "
                        "2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 "
                        '2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/></svg>'
                    ),
                    cls="mb-4",
                ),
                H3("Date & Location Estimator", cls="text-xl font-serif font-bold text-white mb-2"),
                P(
                    "Upload a photo and let AI estimate when and where it was taken "
                    "using facial age analysis and historical clues.",
                    cls="text-slate-400 text-sm mb-4",
                ),
                Div(
                    Span("Try it", cls="text-amber-400 text-sm font-medium"),
                    NotStr(
                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-amber-400 ml-1" '
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
                        '<path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>'
                    ),
                    cls="flex items-center",
                ),
                cls="p-6",
            ),
            href="/tools/estimate",
            cls="block bg-slate-800/50 rounded-xl border border-slate-700/30 hover:border-amber-500/50 hover:bg-slate-800/70 transition-all duration-200",
            data_testid="tool-card-estimate",
        ),
        # Face Compare card
        A(
            Div(
                Div(
                    NotStr(
                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-indigo-400" '
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">'
                        '<path stroke-linecap="round" stroke-linejoin="round" '
                        'd="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 '
                        "004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 "
                        "19.128v.106A12.318 12.318 0 018.624 21c-2.331 "
                        "0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 "
                        "0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 "
                        '016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/></svg>'
                    ),
                    cls="mb-4",
                ),
                H3("Face Comparison", cls="text-xl font-serif font-bold text-white mb-2"),
                P(
                    "Compare faces across photos to find potential matches. "
                    "Upload your own photos or search the archive.",
                    cls="text-slate-400 text-sm mb-4",
                ),
                Div(
                    Span("Try it", cls="text-indigo-400 text-sm font-medium"),
                    NotStr(
                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-indigo-400 ml-1" '
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">'
                        '<path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>'
                    ),
                    cls="flex items-center",
                ),
                cls="p-6",
            ),
            href="/tools/compare",
            cls="block bg-slate-800/50 rounded-xl border border-slate-700/30 hover:border-indigo-500/50 hover:bg-slate-800/70 transition-all duration-200",
            data_testid="tool-card-compare",
        ),
        cls="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto",
    )

    return (
        Title("ML Tools"),
        page_style,
        Main(
            Nav(
                Div(
                    A(Span("Rhodesli", cls="text-lg font-serif font-bold text-white"), href="/"),
                    Div(*nav_links, cls="hidden sm:flex items-center gap-6"),
                    cls="max-w-5xl mx-auto px-6 flex items-center justify-between h-16",
                ),
                cls="bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-50",
            ),
            tools_nav_bar(active_tool="hub"),
            Section(
                Div(
                    H1(
                        "ML Tools",
                        cls="text-3xl font-serif font-bold text-white text-center mb-3",
                    ),
                    P(
                        "AI-powered tools for historical photo analysis and identification.",
                        cls="text-slate-400 text-center mb-10 max-w-lg mx-auto",
                    ),
                    tool_cards,
                    cls="max-w-5xl mx-auto px-6 py-12",
                ),
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


# --- Redirects from old URLs ---


@rt("/estimate")
def get_estimate_redirect(photo: str = "", sess=None):
    """Redirect /estimate → /tools/estimate for backward compatibility."""
    target = "/tools/estimate"
    if photo:
        target += f"?photo={photo}"
    return RedirectResponse(target, status_code=302)


@rt("/compare")
def get_compare_redirect(
    face_id: str = "",
    photo_id: str = "",
    person_id: str = "",
    sess=None,
):
    """Redirect /compare → /tools/compare for backward compatibility."""
    # Preserve query params
    params = []
    if face_id:
        params.append(f"face_id={face_id}")
    if photo_id:
        params.append(f"photo_id={photo_id}")
    if person_id:
        params.append(f"person_id={person_id}")
    target = "/tools/compare"
    if params:
        target += "?" + "&".join(params)
    return RedirectResponse(target, status_code=302)
