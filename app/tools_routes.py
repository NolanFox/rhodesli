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
        ("Archive Search", "/tools/search", "search"),
    ]
    _active_cls = "font-bold text-indigo-400 border-b-2 border-indigo-400 pb-1"
    _inactive_cls = "text-slate-400 hover:text-indigo-400 transition-colors"

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
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true">'
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
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">'
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
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true">'
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
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">'
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
        # Archive Search card
        A(
            Div(
                Div(
                    NotStr(
                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-emerald-400" '
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true">'
                        '<path stroke-linecap="round" stroke-linejoin="round" '
                        'd="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"/></svg>'
                    ),
                    cls="mb-4",
                ),
                H3("Archive Search", cls="text-xl font-serif font-bold text-white mb-2"),
                P(
                    "Search the archive using natural language. Find people, "
                    "photos by decade, location, or collection.",
                    cls="text-slate-400 text-sm mb-4",
                ),
                Div(
                    Span("Try it", cls="text-emerald-400 text-sm font-medium"),
                    NotStr(
                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-emerald-400 ml-1" '
                        'fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">'
                        '<path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>'
                    ),
                    cls="flex items-center",
                ),
                cls="p-6",
            ),
            href="/tools/search",
            cls="block bg-slate-800/50 rounded-xl border border-slate-700/30 hover:border-emerald-500/50 hover:bg-slate-800/70 transition-all duration-200",
            data_testid="tool-card-search",
        ),
        cls="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto",
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


# --- Archive Search ---


@rt("/tools/search")
def get(sess=None):
    """Archive Search — natural language query tool."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    nav_links = _main_mod._public_nav_links(active="tools", user=user)

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
    """)

    search_form = Form(
        Div(
            Input(
                type="text",
                name="q",
                placeholder='Try "Nace Capeluto", "Photos from the 1940s", or "How many photos"...',
                cls="w-full bg-slate-800 text-white border border-slate-600 rounded-lg px-4 py-3 "
                "focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 "
                "placeholder-slate-500",
                autofocus=True,
                aria_label="Search the archive",
            ),
            Button(
                NotStr(
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" '
                    'viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">'
                    '<path stroke-linecap="round" stroke-linejoin="round" '
                    'd="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"/></svg>'
                ),
                Span("Search", cls="ml-2"),
                type="submit",
                cls="flex items-center bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 "
                "rounded-lg font-medium transition-colors",
            ),
            cls="flex gap-3",
        ),
        hx_post="/tools/search",
        hx_target="#search-results",
        hx_swap="innerHTML",
        hx_indicator="#search-loading",
        cls="mb-8",
    )

    example_queries = Div(
        P("Example queries:", cls="text-slate-500 text-sm mb-2"),
        Div(
            *[
                Button(
                    q,
                    type="button",
                    cls="text-xs bg-slate-800/50 text-slate-400 border border-slate-700/50 "
                    "rounded-full px-3 py-1.5 hover:border-indigo-500/50 hover:text-indigo-400 "
                    "transition-colors cursor-pointer",
                    onclick=f"document.querySelector('input[name=q]').value = '{q}'; "
                    "document.querySelector('input[name=q]').closest('form').requestSubmit();",
                )
                for q in [
                    "Nace Capeluto",
                    "Photos from the 1940s",
                    "Wedding photos",
                    "Photos from Rhodes",
                    "How many photos are in the archive?",
                ]
            ],
            cls="flex flex-wrap gap-2",
        ),
        cls="mb-8",
    )

    loading_indicator = Div(
        Div(
            NotStr(
                '<svg class="animate-spin h-5 w-5 text-indigo-400" xmlns="http://www.w3.org/2000/svg" '
                'fill="none" viewBox="0 0 24 24" aria-hidden="true">'
                '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>'
                '<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>'
            ),
            Span("Searching...", cls="ml-2 text-slate-400"),
            cls="flex items-center justify-center py-8",
        ),
        id="search-loading",
        cls="htmx-indicator",
    )

    results_div = Div(id="search-results")

    return (
        Title("Archive Search | Rhodesli"),
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
            tools_nav_bar(active_tool="search"),
            Section(
                Div(
                    H1(
                        "Archive Search",
                        cls="text-3xl font-serif font-bold text-white text-center mb-3",
                    ),
                    P(
                        "Search the archive using natural language. Find people, photos by decade, "
                        "location, or collection.",
                        cls="text-slate-400 text-center mb-10 max-w-lg mx-auto",
                    ),
                    Div(
                        search_form,
                        example_queries,
                        loading_indicator,
                        results_div,
                        cls="max-w-2xl mx-auto",
                    ),
                    cls="max-w-5xl mx-auto px-6 py-12",
                ),
            ),
            cls="min-h-screen bg-slate-900",
        ),
    )


@rt("/tools/search")
def post(q: str = "", sess=None, request=None):
    """Handle search query — parse intent and execute against Supabase."""
    # Rate limit: 60 searches/hr per IP (Security audit Finding 3)
    from app.rate_limit import check_rate_limit

    client_ip = request.client.host if request and request.client else "unknown"
    if not check_rate_limit(client_ip, max_per_hour=60):
        return Div(
            P("Too many searches. Please wait a few minutes.", cls="text-amber-400 text-center py-8"),
            id="search-results",
        )

    if not q or not q.strip():
        return Div(
            P(
                "Please enter a search query above.",
                cls="text-slate-400 text-center py-8",
            ),
            id="search-results",
        )

    # Truncate excessively long queries (Finding 10)
    q = q.strip()[:500]

    from rhodesli_ml.nl_query import parse_query_intent
    from app.nl_query_executor import execute_query
    from app.supabase_data import get_supabase_client

    intent_result = parse_query_intent(q)
    sb = get_supabase_client()
    result = execute_query(intent_result, supabase_client=sb)

    return _render_search_results(result, q)


def _render_search_results(result: dict, query: str):
    """Render search results as FastHTML elements."""
    result_type = result.get("result_type", "message")
    items = result.get("items", [])
    message = result.get("message", "")
    query_summary = result.get("query_summary", "")

    # Header with query summary
    header = Div(
        P(query_summary, cls="text-indigo-400 text-sm font-medium"),
        P(message, cls="text-slate-300 text-sm mt-1"),
        cls="mb-6 pb-4 border-b border-slate-700/50",
    )

    if result_type == "persons" and items:
        person_cards = []
        for item in items:
            state_colors = {
                "CONFIRMED": "bg-emerald-500/20 text-emerald-400",
                "PROPOSED": "bg-amber-500/20 text-amber-400",
                "INBOX": "bg-slate-500/20 text-slate-400",
            }
            state_cls = state_colors.get(item["state"], "bg-slate-500/20 text-slate-400")
            person_cards.append(
                A(
                    Div(
                        Div(
                            Span(item["name"], cls="text-white font-medium"),
                            Span(
                                item["state"].title(),
                                cls=f"text-xs px-2 py-0.5 rounded-full {state_cls}",
                            ),
                            cls="flex items-center justify-between",
                        ),
                        P(
                            f"{item['face_count']} face{'s' if item['face_count'] != 1 else ''}",
                            cls="text-slate-500 text-sm mt-1",
                        ),
                        cls="p-4",
                    ),
                    href=f"/person/{item['identity_id']}",
                    cls="block bg-slate-800/50 rounded-lg border border-slate-700/30 "
                    "hover:border-indigo-500/50 hover:bg-slate-800/70 transition-all",
                )
            )
        content = Div(*person_cards, cls="space-y-2")

    elif result_type == "photos" and items:
        from core.storage import get_photo_url

        photo_cards = []
        for item in items:
            photo_url = get_photo_url(item["path"]) if item.get("path") else ""
            meta_parts = []
            if item.get("date_estimate"):
                meta_parts.append(f"~{item['date_estimate']}")
            if item.get("collection"):
                meta_parts.append(item["collection"])
            if item.get("source"):
                meta_parts.append(item["source"])
            meta_text = " | ".join(meta_parts) if meta_parts else "No metadata"

            photo_cards.append(
                A(
                    Div(
                        Img(
                            src=photo_url,
                            alt=f"Photo {item['photo_id']}",
                            cls="w-20 h-20 object-cover rounded-lg flex-shrink-0",
                            loading="lazy",
                        )
                        if photo_url
                        else Div(cls="w-20 h-20 bg-slate-700 rounded-lg flex-shrink-0"),
                        Div(
                            P(
                                item.get("path", "Unknown photo"),
                                cls="text-white text-sm font-medium truncate",
                            ),
                            P(meta_text, cls="text-slate-500 text-xs mt-1"),
                            cls="flex-1 min-w-0",
                        ),
                        cls="flex items-center gap-4 p-3",
                    ),
                    href=f"/photo/{item['photo_id']}",
                    cls="block bg-slate-800/50 rounded-lg border border-slate-700/30 "
                    "hover:border-indigo-500/50 hover:bg-slate-800/70 transition-all",
                )
            )
        content = Div(*photo_cards, cls="space-y-2")

    elif result_type == "aggregate":
        counts = result.get("counts", {})
        stat_cards = []
        for label, value in [
            ("Photos", counts.get("photos", 0)),
            ("People", counts.get("identities", 0)),
        ]:
            stat_cards.append(
                Div(
                    P(str(value), cls="text-3xl font-bold text-white"),
                    P(label, cls="text-slate-400 text-sm"),
                    cls="bg-slate-800/50 rounded-lg border border-slate-700/30 p-6 text-center",
                )
            )
        content = Div(*stat_cards, cls="grid grid-cols-2 gap-4")

    else:
        # Message-only result (unknown, relationship, error)
        lines = message.split("\n")
        content = Div(
            *[P(line, cls="text-slate-300 text-sm") for line in lines if line.strip()],
            cls="bg-slate-800/30 rounded-lg p-6",
        )

    return Div(header, content, id="search-results")


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
