"""
Navigation components — extracted from app/main.py (Session 137).

Includes OG tags, share buttons, nav bars, admin bar, mobile header,
and inbox badge. Functions that depend on main.py state use lazy imports.
"""

from fasthtml.common import (
    A,
    Button,
    Div,
    Nav,
    NotStr,
    Span,
)

# Share icon SVG (three connected dots) -- used everywhere for consistency
_SHARE_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'


def og_tags(
    title: str, description: str = "", image_url: str = "", canonical_url: str = "", og_type: str = "website"
) -> tuple:
    """
    Unified OG meta tags for social sharing previews.
    All URLs are converted to absolute (prepends SITE_URL if relative).
    Returns a tuple of Meta elements to spread into Title() or page head.
    """
    from fasthtml.common import Meta

    # Lazy import to avoid circular dependency
    import app.main as _main_mod

    SITE_URL = _main_mod.SITE_URL

    # Ensure absolute URLs
    if image_url and not image_url.startswith("http"):
        image_url = f"{SITE_URL}{image_url}"
    if canonical_url and not canonical_url.startswith("http"):
        canonical_url = f"{SITE_URL}{canonical_url}"
    tags = [
        Meta(property="og:title", content=title),
        Meta(property="og:description", content=description),
        Meta(property="og:url", content=canonical_url),
        Meta(property="og:type", content=og_type),
        Meta(property="og:site_name", content="Rhodesli \u2014 Heritage Photo Archive"),
        Meta(name="twitter:card", content="summary_large_image" if image_url else "summary"),
        Meta(name="twitter:title", content=title),
        Meta(name="twitter:description", content=description),
        Meta(name="description", content=description),
    ]
    if image_url:
        tags.insert(2, Meta(property="og:image", content=image_url))
        tags.append(Meta(name="twitter:image", content=image_url))
    return tuple(tags)


def share_button(
    photo_id: str = None, *, url: str = None, style: str = "icon", label: str = "Share", title: str = "", text: str = ""
):
    """
    Reusable share button. Works with photo_id (legacy) or any url.
    Uses data-action="share-photo" for global event delegation.

    photo_id: Legacy param -- generates /photo/{photo_id} URL
    url: Direct URL to share (takes precedence over photo_id)
    style: "icon" (compact), "button" (icon + text), "link" (text link), "prominent" (large CTA)
    title: Share title for native share sheet (optional)
    text: Share description for native share sheet (optional)
    """
    share_url = url or (f"/photo/{photo_id}" if photo_id else "")
    extra_attrs = {}
    if title:
        extra_attrs["data_share_title"] = title
    if text:
        extra_attrs["data_share_text"] = text
    if style == "button":
        return Button(
            NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 mr-1.5 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'
            ),
            label,
            cls="px-5 py-4 sm:px-3 sm:py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors inline-flex items-center",
            type="button",
            data_action="share-photo",
            data_share_url=share_url,
            **extra_attrs,
        )
    elif style == "link":
        return Button(
            NotStr(_SHARE_ICON_SVG),
            f" {label}",
            cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 underline inline-flex items-center gap-1",
            type="button",
            data_action="share-photo",
            data_share_url=share_url,
            **extra_attrs,
        )
    elif style == "prominent":
        return Button(
            NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 mr-2 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>'
            ),
            label,
            cls="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-base font-medium rounded-xl transition-colors inline-flex items-center shadow-lg hover:shadow-xl",
            type="button",
            data_action="share-photo",
            data_share_url=share_url,
            **extra_attrs,
        )
    else:  # "icon" -- compact, for grid overlays and card corners
        return Button(
            NotStr(_SHARE_ICON_SVG),
            cls="p-1.5 bg-black/60 hover:bg-indigo-600 text-white rounded transition-colors",
            type="button",
            data_action="share-photo",
            data_share_url=share_url,
            title=label,
            aria_label=label,
            **extra_attrs,
        )


def mobile_header() -> Div:
    """
    Mobile top bar with hamburger menu button.
    Hidden on desktop (lg+), shown on smaller screens.
    """
    return Div(
        Button(
            NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>'
            ),
            cls="text-white p-2 -ml-2",
            onclick="toggleSidebar()",
            type="button",
            aria_label="Open menu",
        ),
        Span("Rhodesli", cls="text-xl sm:text-lg font-display font-bold text-white"),
        cls="mobile-header fixed top-0 left-0 right-0 h-14 bg-slate-800 border-b border-slate-700 "
        "flex items-center gap-3 px-4 z-20",
        id="mobile-header",
    )


def _public_nav_links(active: str = "", user=None, community_slug: str | None = None) -> list:
    """Build standard navigation links for public pages."""
    # Lazy import to avoid circular dependency
    import app.main as _main_mod

    community_url_prefix = _main_mod.community_url_prefix

    _inactive = "text-amber-900/60 hover:text-amber-900 font-serif tracking-wide text-sm transition-colors duration-300"
    _active = "text-amber-950 font-serif tracking-wide text-sm border-b border-amber-900 pb-0.5"

    p = community_url_prefix(community_slug)

    links = [
        # Core Archive
        A("Photos", href=f"{p}/photos", cls=_active if active == "photos" else _inactive),
        A("Collections", href=f"{p}/collections", cls=_active if active == "collections" else _inactive),
        A("People", href=f"{p}/people", cls=_active if active == "people" else _inactive),
        A("Timeline", href=f"{p}/timeline", cls=_active if active == "timeline" else _inactive),
        A("Map", href=f"{p}/map", cls=_active if active == "map" else _inactive),
        # Visual separator for Tools
        Span("|", cls="text-slate-700 hidden lg:inline"),
        # Tools
        A("Tree", href=f"{p}/tree", cls=_active if active == "tree" else _inactive),
        A("Connect", href=f"{p}/connect", cls=_active if active == "connect" else _inactive),
        A("Compare", href="/tools/compare", cls=_active if active == "compare" else _inactive),
        A("Estimate", href="/tools/estimate", cls=_active if active == "estimate" else _inactive),
    ]

    # Help Identify CTA -- links to dedicated /help page
    links.append(
        A(
            "Help Identify",
            href=f"{p}/help",
            cls=(
                "text-amber-400 font-medium text-sm border-b-2 border-amber-500 pb-1 ml-2"
                if active == "help"
                else "text-amber-400 hover:text-amber-300 font-medium text-sm transition-colors border border-amber-500/30 px-2 py-0.5 rounded ml-2"
            ),
        )
    )

    # Lazy import to ensure test patches on app.main.is_auth_enabled work
    is_auth_enabled = _main_mod.is_auth_enabled
    if is_auth_enabled() and not user:
        links.append(
            A(
                "Sign In",
                href="/login",
                cls="text-indigo-400 hover:text-indigo-300 text-sm font-medium transition-colors ml-2",
            )
        )

    # Bell icon for logged-in users (PRD-028 Notifications)
    if user:
        bell_svg = NotStr(
            '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" '
            'viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">'
            '<path stroke-linecap="round" stroke-linejoin="round" '
            'd="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 '
            "6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 "
            "11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 "
            '11-6 0v-1m6 0H9"/></svg>'
        )
        links.append(
            A(
                Div(
                    bell_svg,
                    Span(id="notification-badge"),
                    cls="relative",
                    hx_get="/api/notifications/count",
                    hx_trigger="load, every 30s",
                    hx_target="#notification-badge",
                    hx_swap="outerHTML",
                ),
                href=f"{p}/notifications",
                cls="text-slate-300 hover:text-white transition-colors ml-2",
                title="Notifications",
                aria_label="Notifications",
            )
        )

    return links


def _public_page_nav(
    nav_links: list,
    *,
    active: str = "",
    user=None,
    community_slug: str | None = None,
    max_w: str = "max-w-5xl",
    font_cls: str = "text-xl sm:text-lg font-display font-bold text-white",
    sticky: bool = True,
    fixed: bool = False,
    extra_links: list = None,
    include_admin_bar: bool = True,
) -> object:
    """Build a public page nav bar with mobile hamburger menu.

    All public pages should use this instead of inlining Nav() with hidden sm:flex.
    Includes a hamburger button visible below sm breakpoint.
    """
    # Lazy import to avoid circular dependency
    import app.main as _main_mod

    community_url_prefix = _main_mod.community_url_prefix

    hamburger_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16"/></svg>'
    close_svg = '<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>'

    # Mobile menu overlay (hidden by default, shown via JS)
    mobile_menu_links = []
    for link in nav_links:
        # Skip non-link elements (e.g. Span separators)
        if not hasattr(link, "tag") or link.tag != "a":
            continue
        # Clone link with mobile-friendly styling
        href = link.attrs.get("href", "#") if hasattr(link, "attrs") else "#"
        text = link.children[0] if hasattr(link, "children") and link.children else str(link)
        if hasattr(text, "children"):
            text = str(text.children[0]) if text.children else str(text)
        mobile_menu_links.append(
            A(
                str(text),
                href=href,
                cls="block px-4 py-3 text-slate-200 hover:bg-slate-700/50 hover:text-white text-base font-medium rounded-lg transition-colors",
                onclick="document.getElementById('mobile-nav-overlay').classList.add('hidden');",
            )
        )

    mobile_overlay = Div(
        # Backdrop
        Div(
            onclick="closeMobileNav ? closeMobileNav() : document.getElementById('mobile-nav-overlay').classList.add('hidden');",
            cls="absolute inset-0 bg-black/50 transition-opacity",
        ),
        # Menu panel (slides from right)
        Div(
            Div(
                Span("Rhodesli", cls="text-xl sm:text-lg font-display font-bold text-white"),
                Button(
                    NotStr(close_svg),
                    cls="text-slate-400 hover:text-white p-3 -mr-2 -mt-2",
                    onclick="closeMobileNav ? closeMobileNav() : document.getElementById('mobile-nav-overlay').classList.add('hidden');",
                    type="button",
                    aria_label="Close menu",
                ),
                cls="flex items-center justify-between px-4 py-4 border-b border-slate-700",
            ),
            Div(*mobile_menu_links, cls="py-2 px-2"),
            cls="mobile-nav-panel absolute top-0 right-0 w-72 h-full bg-slate-800 shadow-xl overflow-y-auto transition-transform duration-200",
            style="transform: translateX(100%);",
        ),
        id="mobile-nav-overlay",
        cls="hidden fixed inset-0 z-[60]",
        style="display: none;",
    )

    # Hamburger button (visible below md/768px, hidden at md+)
    hamburger_btn = Button(
        NotStr(hamburger_svg),
        cls="md:hidden text-white p-1 -ml-1",
        onclick="openMobileNav ? openMobileNav() : document.getElementById('mobile-nav-overlay').classList.remove('hidden');",
        type="button",
        aria_label="Open navigation menu",
    )

    right_items = list(extra_links) if extra_links else []

    pos_cls = "sticky top-0" if sticky else ("fixed top-0 left-0 right-0" if fixed else "")

    home_href = (
        f"{community_url_prefix(community_slug)}/" if community_slug and community_url_prefix(community_slug) else "/"
    )

    nav = Nav(
        Div(
            Div(
                hamburger_btn,
                A(Span("Rhodesli", cls=font_cls), href=home_href),
                cls="flex items-center gap-2",
            ),
            Div(*nav_links, *right_items, cls="hidden md:flex items-center gap-6"),
            cls=f"{max_w} mx-auto px-6 flex items-center justify-between h-16",
        ),
        mobile_overlay,
        cls=f"bg-slate-900/80 backdrop-blur-md border-b border-slate-800 {pos_cls} z-50",
    )

    if include_admin_bar and user and getattr(user, "is_admin", False):
        return Div(nav, _admin_bar(user, community_slug=community_slug), id="nav-with-admin")
    return nav


def _admin_bar(user=None, community_slug: str = "rhodes", community: dict | None = None) -> object:
    """Admin mode indicator bar -- only visible for admin users.

    Shows pending count, quick links to admin sections.
    Returns empty string for non-admin users.
    Community-aware: scopes counts and links to active community.
    """
    if not user or not getattr(user, "is_admin", False):
        return NotStr("")

    # Lazy imports to avoid circular dependency
    import app.main as _main_mod

    community_url_prefix = _main_mod.community_url_prefix
    load_registry = _main_mod.load_registry
    _get_community_identity_ids = _main_mod._get_community_identity_ids

    prefix = community_url_prefix(community_slug or "rhodes")

    # Count pending items (scoped to community)
    pending_count = 0
    proposal_count = 0
    try:
        registry = load_registry()
        community_identity_ids = _get_community_identity_ids(community)
        for ident in registry.list_identities():
            if community_identity_ids is not None and ident.get("identity_id") not in community_identity_ids:
                continue
            state = ident.get("state", "")
            if state == "INBOX":
                pending_count += 1
            elif state == "PROPOSED":
                proposal_count += 1
    except Exception:
        import logging

        logging.warning("_admin_bar: failed to compute pending/proposal counts", exc_info=True)

    return Div(
        Div(
            Span(
                "Admin Mode",
                cls="text-amber-400/80 text-[10px] sm:text-xs font-medium tracking-wide uppercase shrink-0",
            ),
            Div(
                A(
                    f"Pending ({pending_count})",
                    href=f"{prefix}/?section=to_review",
                    cls="text-slate-400 hover:text-white text-sm sm:text-xs whitespace-nowrap transition-colors",
                ),
                Span("|", cls="text-slate-700 mx-1 sm:mx-2"),
                A(
                    f"Proposals ({proposal_count})",
                    href=f"{prefix}/?section=to_review",
                    cls="text-slate-400 hover:text-white text-sm sm:text-xs whitespace-nowrap transition-colors",
                ),
                Span("|", cls="text-slate-700 mx-1 sm:mx-2"),
                A(
                    "Upload",
                    href=f"{prefix}/upload",
                    cls="text-slate-400 hover:text-white text-sm sm:text-xs whitespace-nowrap transition-colors",
                ),
                cls="flex items-center overflow-x-auto scrollbar-hide w-full sm:w-auto",
            ),
            cls="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1 sm:gap-0",
        ),
        cls="bg-slate-950 border-b border-amber-400/20 py-1.5 sm:py-1",
        id="admin-bar",
        data_testid="admin-bar",
    )


def _admin_dashboard_banner(counts: dict, current_section: str) -> Div:
    """Admin-only dashboard summary banner at the top of the workstation.

    Shows inbox count, skipped count, and quick links.
    Focus/Browse toggle lives in each section's header instead.
    Only rendered when user is admin.
    """
    to_review = counts.get("to_review", 0)
    skipped = counts.get("skipped", 0)
    confirmed = counts.get("confirmed", 0)
    proposals = counts.get("proposals", 0)

    stat_items = [
        ("New Matches", to_review, "/?section=to_review&view=focus", "text-amber-500"),
        ("People", confirmed, "/?section=confirmed", "text-emerald-500"),
        ("Help Identify", skipped, "/?section=skipped", "text-amber-300"),
    ]
    if proposals > 0:
        stat_items.append(("Proposals", proposals, "/admin/proposals", "text-indigo-400"))

    stats_row = [
        A(
            Span(str(count), cls=f"font-display font-semibold text-xl sm:text-lg {color}"),
            Span(f" {label}", cls="text-slate-400 text-sm sm:text-xs font-medium uppercase tracking-wider ml-1"),
            href=link,
            cls="hover:bg-slate-800 px-5 py-4 sm:px-3 sm:py-1.5 rounded-md transition-colors flex items-baseline line-height-none border border-transparent hover:border-slate-700",
        )
        for label, count, link, color in stat_items
    ]

    return Div(
        Div(
            Div(*stats_row, cls="flex items-center gap-2"),
            cls="max-w-7xl mx-auto px-6 flex items-center justify-between",
        ),
        id="admin-dashboard-banner",
        cls="py-2 bg-slate-900 border-b border-amber-900/40 sticky top-0 z-40 shadow-sm ui99-workstation-banner",
    )


def inbox_badge(count: int) -> A:
    """
    New Matches badge showing count of items awaiting review.
    """
    if count == 0:
        return A(
            Span("\U0001f4e5", cls="mr-2"),
            "New Matches",
            Span("(0)", cls="text-slate-500 ml-1"),
            href="#inbox-lane",
            cls="text-slate-400 hover:text-slate-300 text-sm",
        )
    return A(
        Span("\U0001f4e5", cls="mr-2"),
        "New Matches",
        Span(f"({count})", cls="bg-indigo-600 text-white text-sm sm:text-xs px-1.5 py-0.5 rounded-full ml-1"),
        href="#inbox-lane",
        cls="text-slate-300 hover:text-indigo-400 text-sm font-medium",
    )
