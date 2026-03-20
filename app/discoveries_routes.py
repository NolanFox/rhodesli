"""
Discoveries routes extracted from app/identity_routes.py and app/main.py.

Discovery inbox: high-confidence matches between unreviewed faces and confirmed identities.
Admin-only: these are actionable items that can be resolved with one click.

Routes:
  /discoveries                    — Main discoveries page
  /api/discoveries                — HTMX endpoint: render discovery cards
  /api/discoveries/photo-options  — HTMX endpoint: photo filter dropdown
  /api/discovery/reject           — Reject a discovery match
  /api/discovery/confirm          — Confirm a Tier 1 auto-clustered face
  /api/discovery/undo             — Undo a Tier 1 auto-cluster
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fasthtml.common import *


from app.main import rt

import app.main as _main_mod

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIDENCE TIER HELPERS
# =============================================================================


def confidence_tier_label(distance: float) -> str:
    """Map embedding distance to a human-readable confidence tier label.

    Returns a tier label string suitable for display in discovery cards.
    Replaces misleading percentage display with meaningful labels.
    """
    if distance < 0.80:
        return "Strong match"
    elif distance < 1.00:
        return "Good match"
    elif distance < 1.20:
        return "Possible match"
    else:
        return "Weak match"


def confidence_tier_style(distance: float) -> tuple[str, str]:
    """Return (badge_cls, ring_cls) CSS classes for a given distance.

    Uses distance-based tiers instead of legacy confidence tier names.
    """
    if distance < 0.80:
        return (
            "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
            "ring-2 ring-emerald-400/50",
        )
    elif distance < 1.00:
        return (
            "bg-indigo-500/20 text-indigo-400 border-indigo-500/30",
            "ring-2 ring-indigo-400/50",
        )
    elif distance < 1.20:
        return (
            "bg-amber-500/20 text-amber-400 border-amber-500/30",
            "ring-2 ring-amber-400/50",
        )
    else:
        return (
            "bg-slate-500/20 text-slate-400 border-slate-500/30",
            "ring-2 ring-slate-400/50",
        )


# =============================================================================
# ROUTES - DISCOVERIES PAGE
# =============================================================================


@rt("/discoveries")
def get(sess=None, request=None):
    """
    Discovery inbox: high-confidence matches between unreviewed faces and confirmed identities.
    Admin-only: these are actionable items that can be resolved with one click.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    user = _main_mod.get_current_user(sess or {})
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    community = getattr(request.state, "community", None) if request else None

    style = Style("""
        html, body { height: 100%; margin: 0; }
        body { background-color: #0f172a; }
    """)

    registry = _main_mod.load_registry()
    counts = _main_mod._compute_sidebar_counts(registry, community=community)
    discovery_count = counts.get("discoveries", 0)

    # Community URL prefix for HTMX endpoints (must go through middleware for scoping)
    prefix = _main_mod.community_url_prefix(community_slug)

    # Community identity IDs for scoping
    community_identity_ids = _main_mod._get_community_identity_ids(community)

    # Discovery log tier counts — filter by community
    tier_1_entries, tier_2_entries = _main_mod._get_pending_discovery_entries()
    if community_identity_ids is not None:
        tier_1_entries = [
            e
            for e in tier_1_entries
            if e.get("source_identity_id") in community_identity_ids
            or e.get("target_identity_id") in community_identity_ids
        ]
        tier_2_entries = [
            e
            for e in tier_2_entries
            if e.get("source_identity_id") in community_identity_ids
            or e.get("target_identity_id") in community_identity_ids
        ]
    tier_1_count = len(tier_1_entries)
    tier_2_count = len(tier_2_entries)

    page_style = Style("""
        .sidebar-container { width: 15rem; transition: width 0.2s ease, transform 0.3s ease; }
        .sidebar-container.collapsed { width: 3.5rem; }
        .sidebar-container.collapsed .sidebar-label,
        .sidebar-container.collapsed .sidebar-search,
        .sidebar-container.collapsed .sidebar-search-results { display: none; }
        .sidebar-container.collapsed .sidebar-nav-item { justify-content: center; padding-left: 0; padding-right: 0; }
        .sidebar-container.collapsed .sidebar-icon { margin: 0; }
        .sidebar-container.collapsed .sidebar-chevron { transform: rotate(180deg); }
        .sidebar-container.collapsed .sidebar-collapse-btn { margin: 0 auto; }
        .sidebar-search-results:not(:empty) { position: absolute; left: 0.75rem; right: 0.75rem; top: 100%; background: #1e293b; border: 1px solid #334155; border-radius: 0.5rem; max-height: 300px; overflow-y: auto; z-index: 50; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        @media (max-width: 767px) {
            #sidebar { width: 15rem !important; transform: translateX(-100%); transition: transform 0.3s ease; }
            #sidebar.open { transform: translateX(0); }
            #sidebar .sidebar-label { display: inline !important; }
            #sidebar .sidebar-search { display: block !important; }
            .main-content { margin-left: 0 !important; }
        }
        @media (min-width: 768px) { #sidebar { transform: translateX(0); } }
        @media (min-width: 1024px) { .main-content { margin-left: 15rem; transition: margin-left 0.2s ease; } .main-content.sidebar-collapsed { margin-left: 3.5rem; } }
    """)
    _main_mod.mobile_header = Div(
        Button(
            Svg(
                Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2", d="M4 6h16M4 12h16M4 18h16"),
                cls="w-6 h-6",
                fill="none",
                stroke="currentColor",
                viewBox="0 0 24 24",
            ),
            onclick="toggleSidebar()",
            cls="p-2 text-slate-300 hover:text-white min-h-[44px] min-w-[44px] flex items-center justify-center",
        ),
        Span("Discoveries", cls="text-lg font-bold text-white"),
        cls="mobile-header lg:hidden flex items-center gap-3 px-4 py-3 bg-slate-800 border-b border-slate-700 sticky top-0 z-30",
    )
    sidebar_overlay = Div(
        onclick="closeSidebar()", cls="sidebar-overlay fixed inset-0 bg-black/50 z-30 hidden lg:hidden"
    )
    sidebar_script = Script("""
        function toggleSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.toggle('open');
            sb.classList.toggle('-translate-x-full');
            ov.classList.toggle('hidden');
        }
        function closeSidebar() {
            var sb = document.getElementById('sidebar');
            var ov = document.querySelector('.sidebar-overlay');
            sb.classList.remove('open');
            sb.classList.add('-translate-x-full');
            ov.classList.add('hidden');
        }
        function toggleSidebarCollapse() {
            var sb = document.getElementById('sidebar');
            var mc = document.querySelector('.main-content');
            var isCollapsed = sb.classList.toggle('collapsed');
            if (mc) mc.classList.toggle('sidebar-collapsed', isCollapsed);
            try { localStorage.setItem('sidebar_collapsed', isCollapsed ? 'true' : 'false'); } catch(e) {}
        }
        (function() {
            try {
                var collapsed = localStorage.getItem('sidebar_collapsed') === 'true';
                if (collapsed && window.innerWidth >= 1024) {
                    var sb = document.getElementById('sidebar');
                    var mc = document.querySelector('.main-content');
                    if (sb) sb.classList.add('collapsed');
                    if (mc) mc.classList.add('sidebar-collapsed');
                }
            } catch(e) {}
        })();
    """)

    return (
        Title("Discoveries - Rhodesli"),
        style,
        page_style,
        Div(
            _main_mod.toast_container(),
            _main_mod.mobile_header,
            sidebar_overlay,
            _main_mod.sidebar(
                counts, current_section="discoveries", user=user, community_slug=community_slug, community=community
            ),
            Main(
                Div(
                    Div(
                        H2("Discoveries", cls="text-2xl font-bold text-white"),
                        P(
                            f"{discovery_count} high-confidence match{'es' if discovery_count != 1 else ''} to confirmed identities",
                            cls="text-sm text-slate-400 mt-1",
                        ),
                        # Tier breakdown badges
                        Div(
                            Span(
                                f"{tier_1_count} auto-added",
                                cls="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
                            )
                            if tier_1_count > 0
                            else None,
                            Span(
                                f"{tier_2_count} suggestion{'s' if tier_2_count != 1 else ''}",
                                cls="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30",
                            )
                            if tier_2_count > 0
                            else None,
                            cls="flex gap-2 mt-2",
                        )
                        if (tier_1_count + tier_2_count) > 0
                        else None,
                        cls="mb-6",
                    ),
                    # Filter controls
                    Div(
                        Div(
                            # Confidence filter buttons
                            Span("Confidence:", cls="text-xs text-slate-400 mr-2"),
                            Button(
                                "All",
                                cls="text-xs px-3 py-1.5 rounded-full bg-slate-600 text-white font-medium min-h-[32px]",
                                hx_get=f"{prefix}/api/discoveries",
                                hx_target="#discoveries-list",
                                hx_swap="innerHTML",
                                hx_include="#discovery-photo-filter",
                                data_action="discovery-filter",
                                type="button",
                            ),
                            Button(
                                "Strong (70%+)",
                                cls="text-xs px-3 py-1.5 rounded-full bg-slate-700 text-slate-300 hover:bg-slate-600 font-medium min-h-[32px]",
                                hx_get=f"{prefix}/api/discoveries?min_confidence=70",
                                hx_target="#discoveries-list",
                                hx_swap="innerHTML",
                                hx_include="#discovery-photo-filter",
                                data_action="discovery-filter",
                                type="button",
                            ),
                            Button(
                                "Possible (50%+)",
                                cls="text-xs px-3 py-1.5 rounded-full bg-slate-700 text-slate-300 hover:bg-slate-600 font-medium min-h-[32px]",
                                hx_get=f"{prefix}/api/discoveries?min_confidence=50",
                                hx_target="#discoveries-list",
                                hx_swap="innerHTML",
                                hx_include="#discovery-photo-filter",
                                data_action="discovery-filter",
                                type="button",
                            ),
                            cls="flex items-center flex-wrap gap-2",
                        ),
                        Div(
                            Span("Photo:", cls="text-xs text-slate-400 mr-2"),
                            Select(
                                Option("All photos", value=""),
                                id="discovery-photo-filter",
                                name="photo_id",
                                cls="text-xs border border-slate-600 bg-slate-700 text-slate-300 rounded px-2 py-1.5 min-h-[32px]",
                                hx_get=f"{prefix}/api/discoveries",
                                hx_target="#discoveries-list",
                                hx_swap="innerHTML",
                                hx_trigger="change",
                            ),
                            Div(
                                id="discovery-photo-loader",
                                hx_get=f"{prefix}/api/discoveries/photo-options",
                                hx_trigger="load",
                                hx_target="#discovery-photo-filter",
                                hx_swap="innerHTML",
                            ),
                            cls="flex items-center mt-2",
                        ),
                        cls="mb-4 p-3 bg-slate-800/50 border border-slate-700/50 rounded-xl",
                        id="discovery-filters",
                    ),
                    Div(
                        # Loading skeleton shown until HTMX replaces content
                        Div(
                            Div(cls="h-24 bg-slate-700/50 rounded-xl animate-pulse mb-3"),
                            Div(cls="h-24 bg-slate-700/50 rounded-xl animate-pulse mb-3"),
                            Div(cls="h-24 bg-slate-700/50 rounded-xl animate-pulse mb-3"),
                            P("Loading discoveries...", cls="text-sm text-slate-500 text-center mt-2"),
                        ),
                        id="discoveries-list",
                        hx_get=f"{prefix}/api/discoveries",
                        hx_trigger="load",
                        hx_swap="innerHTML",
                    ),
                    cls="max-w-3xl mx-auto px-4 sm:px-8 py-6",
                ),
                cls="main-content min-h-screen overflow-x-hidden",
            ),
            sidebar_script,
            cls="h-full",
        ),
    )


@rt("/api/discoveries")
def get(sess=None, request=None, photo_id: str = "", min_confidence: int = 0):
    """HTMX endpoint: render discovery cards for the discoveries page.

    Merges two sources:
    1. Dynamic computation (_compute_discoveries) — matches with distance < 1.05
    2. Discovery log (data/discovery_log.json) — Tier 2 suggestions from auto-clustering

    Shows cards with tier labels and appropriate actions (AD-179).
    Community-scoped via request.state.community (set by CommunityMiddleware).

    Filter params:
      photo_id: filter to discoveries whose source face is in this photo
      min_confidence: minimum confidence_pct (0=all, 50=possible+, 70=strong+)
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    from core.confidence import compute_confidence_pct

    # Extract community context for scoping
    # Bare /api/discoveries (no /c/ prefix) goes through middleware skip,
    # so community is None. Fall back to Rhodes for performance.
    community = getattr(request.state, "community", None) if request else None
    if community is None:
        from app.supabase_data import get_community_by_slug

        community = get_community_by_slug("rhodes")
    community_identity_ids = _main_mod._get_community_identity_ids(community)

    # Community URL prefix for user-facing links
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    registry = _main_mod.load_registry()
    discoveries = _main_mod._compute_discoveries(registry, community_identity_ids=community_identity_ids)
    crop_files = _main_mod.get_crop_files()

    # Merge discovery_log Tier 2 entries that aren't in dynamic discoveries
    tier_1_entries, tier_2_entries = _main_mod._get_pending_discovery_entries()
    # Filter discovery log entries by community
    if community_identity_ids is not None:
        tier_1_entries = [
            e
            for e in tier_1_entries
            if e.get("source_identity_id") in community_identity_ids
            or e.get("target_identity_id") in community_identity_ids
        ]
        tier_2_entries = [
            e
            for e in tier_2_entries
            if e.get("source_identity_id") in community_identity_ids
            or e.get("target_identity_id") in community_identity_ids
        ]
    dynamic_source_ids = {d["source_id"] for d in discoveries}

    for entry in tier_2_entries:
        src_id = entry.get("source_identity_id", "")
        if src_id and src_id not in dynamic_source_ids:
            distance = entry.get("distance", 999)
            discoveries.append(
                {
                    "source_id": src_id,
                    "source_name": entry.get("source_identity_name", ""),
                    "target_id": entry.get("target_identity_id", ""),
                    "target_name": entry.get("target_identity_name", ""),
                    "distance": distance,
                    "confidence": _main_mod._confidence_tier(distance),
                    "from_log": True,
                    "created_at": entry.get("created_at", entry.get("timestamp", "")),
                }
            )

    # Compute confidence_pct for each discovery
    for d in discoveries:
        d["confidence_pct"] = compute_confidence_pct(d.get("distance", 999))
        # Ensure created_at is populated for sort
        if "created_at" not in d:
            d["created_at"] = d.get("timestamp", "")

    # Sort by recency (newest first) — most recently discovered matches on top
    discoveries.sort(key=lambda d: d.get("created_at", ""), reverse=True)

    # Also include pending Tier 1 entries (auto-clustered, needs confirmation)
    all_items = []
    for entry in tier_1_entries:
        dist = entry.get("distance", 0)
        all_items.append(
            {
                "source_id": entry.get("source_identity_id", ""),
                "source_name": entry.get("source_identity_name", ""),
                "target_id": entry.get("target_identity_id", ""),
                "target_name": entry.get("target_identity_name", ""),
                "distance": dist,
                "face_id": entry.get("face_id", ""),
                "tier": 1,
                "confidence_pct": compute_confidence_pct(dist),
                "created_at": entry.get("created_at", entry.get("timestamp", "")),
            }
        )
    for d in discoveries:
        d["tier"] = 2
        all_items.append(d)

    # --- Apply filters ---
    # Resolve source face -> photo_id for photo filter
    if photo_id:
        filtered = []
        for item in all_items:
            src_id = item.get("source_id", "")
            source_identity = _main_mod._safe_get_identity(registry, src_id)
            if source_identity:
                face_ids = source_identity.get("anchor_ids", []) + source_identity.get("candidate_ids", [])
                for f in face_ids:
                    fid = f if isinstance(f, str) else f.get("face_id", "")
                    if fid:
                        pid = _main_mod.get_photo_id_for_face(fid)
                        if pid == photo_id:
                            filtered.append(item)
                            break
        all_items = filtered

    # Confidence filter
    if min_confidence > 0:
        all_items = [d for d in all_items if d.get("confidence_pct", 0) >= min_confidence]

    # Pagination: limit to 50 items per page to prevent server timeout (738+ cards = too slow)
    PAGE_SIZE = 50
    total_count = len(all_items)
    all_items = all_items[:PAGE_SIZE]

    sections = []

    # Build Help Identify section early (shown even when no ML matches)
    help_section = _build_help_identify_section(
        registry, crop_files, community_identity_ids=community_identity_ids, nav_prefix=nav_prefix
    )

    if not all_items:
        filter_msg = (
            "No matches found with current filters."
            if (photo_id or min_confidence > 0)
            else "No high-confidence matches found. New discoveries will appear here when uploaded faces match confirmed identities."
        )
        empty_state = Div(
            Div(
                Span("\u2705", cls="text-4xl mb-3 block"),
                H3(
                    "All discoveries reviewed!" if not (photo_id or min_confidence > 0) else "No matches",
                    cls="text-lg font-semibold text-white mb-1",
                ),
                P(filter_msg, cls="text-sm text-slate-400"),
                cls="text-center py-12",
            ),
            cls="bg-slate-800/50 border border-slate-700/50 rounded-xl",
            data_testid="discoveries-empty-state",
        )
        if help_section is not None:
            return Div(empty_state, help_section, cls="space-y-4")
        return empty_state

    # --- Section 1: Auto-Added (Tier 1) ---
    tier_1_items = [d for d in all_items if d.get("tier") == 1]
    if tier_1_items:
        tier_1_cards = []
        for d in tier_1_items:
            card = _build_discovery_card(
                d, registry, crop_files, tier=1, current_community=community, nav_prefix=nav_prefix
            )
            if card:
                tier_1_cards.append(card)
        if tier_1_cards:
            sections.append(
                Div(
                    Div(
                        Div(
                            Span(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
                                ),
                                cls="text-emerald-400",
                            ),
                            H3("Recently Auto-Added", cls="text-lg font-semibold text-emerald-400"),
                            cls="flex items-center gap-2",
                        ),
                        P(
                            f"ML automatically added {len(tier_1_cards)} face{'s' if len(tier_1_cards) != 1 else ''} to clusters — review to confirm or undo",
                            cls="text-xs text-slate-400 mt-1",
                        ),
                        cls="mb-3 pb-3 border-b border-emerald-500/20",
                    ),
                    Div(*tier_1_cards, cls="space-y-3"),
                    cls="mb-8 p-4 bg-emerald-500/5 border border-emerald-500/10 rounded-xl",
                    data_testid="section-auto-added",
                )
            )

    # --- Section 2: Suggested Matches (Tier 2) ---
    tier_2_items = [d for d in all_items if d.get("tier") == 2]
    if tier_2_items:
        tier_2_cards = []
        for d in tier_2_items:
            card = _build_discovery_card(
                d, registry, crop_files, tier=2, current_community=community, nav_prefix=nav_prefix
            )
            if card:
                tier_2_cards.append(card)
        if tier_2_cards:
            sections.append(
                Div(
                    Div(
                        Div(
                            Span(
                                NotStr(
                                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>'
                                ),
                                cls="text-indigo-400",
                            ),
                            H3("Suggested Matches", cls="text-lg font-semibold text-indigo-400"),
                            cls="flex items-center gap-2",
                        ),
                        P(
                            f"{len(tier_2_cards)} potential match{'es' if len(tier_2_cards) != 1 else ''} — newest first",
                            cls="text-xs text-slate-400 mt-1",
                        ),
                        cls="mb-3 pb-3 border-b border-indigo-500/20",
                    ),
                    Div(*tier_2_cards, cls="space-y-3"),
                    cls="mb-8 p-4 bg-indigo-500/5 border border-indigo-500/10 rounded-xl",
                    data_testid="section-suggested-matches",
                )
            )

    # --- Section 3: Help Identify (cold cases) ---
    if help_section is not None:
        sections.append(help_section)

    # Show truncation notice if results were limited
    if total_count > PAGE_SIZE:
        sections.append(
            Div(
                P(
                    f"Showing top {PAGE_SIZE} of {total_count} discoveries. "
                    "Use the confidence or photo filters above to narrow results.",
                    cls="text-sm text-slate-400 text-center",
                ),
                cls="py-4 border-t border-slate-700/50",
                data_testid="discoveries-truncation-notice",
            )
        )

    return (
        Div(*sections, cls="space-y-4")
        if sections
        else Div(
            Div(
                Span("\u2705", cls="text-4xl mb-3 block"),
                H3("All discoveries reviewed!", cls="text-lg font-semibold text-white mb-1"),
                P("No matches to review.", cls="text-sm text-slate-400"),
                cls="text-center py-12",
            ),
            cls="bg-slate-800/50 border border-slate-700/50 rounded-xl",
            data_testid="discoveries-empty-state",
        )
    )


@rt("/api/discoveries/photo-options")
def get(sess=None, request=None):
    """HTMX endpoint: populate the photo filter dropdown for discoveries.

    Returns Option elements listing all unique photos that have discovery matches.
    Community-scoped via request.state.community.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    # Extract community context for scoping (same Rhodes fallback as main endpoint)
    community = getattr(request.state, "community", None) if request else None
    if community is None:
        from app.supabase_data import get_community_by_slug

        community = get_community_by_slug("rhodes")
    community_identity_ids = _main_mod._get_community_identity_ids(community)

    registry = _main_mod.load_registry()
    discoveries = _main_mod._compute_discoveries(registry, community_identity_ids=community_identity_ids)
    tier_1_entries, tier_2_entries = _main_mod._get_pending_discovery_entries()
    if community_identity_ids is not None:
        tier_1_entries = [
            e
            for e in tier_1_entries
            if e.get("source_identity_id") in community_identity_ids
            or e.get("target_identity_id") in community_identity_ids
        ]
        tier_2_entries = [
            e
            for e in tier_2_entries
            if e.get("source_identity_id") in community_identity_ids
            or e.get("target_identity_id") in community_identity_ids
        ]

    # Collect all source identity IDs
    source_ids = {d["source_id"] for d in discoveries}
    for entry in tier_1_entries + tier_2_entries:
        src_id = entry.get("source_identity_id", "")
        if src_id:
            source_ids.add(src_id)

    # Map source identities -> photos
    photo_map = {}  # photo_id -> photo label
    for src_id in source_ids:
        identity = _main_mod._safe_get_identity(registry, src_id)
        if not identity:
            continue
        face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        for f in face_ids:
            fid = f if isinstance(f, str) else f.get("face_id", "")
            if fid:
                pid = _main_mod.get_photo_id_for_face(fid)
                if pid and pid not in photo_map:
                    photo_data = _main_mod.get_photo_metadata(pid)
                    if photo_data:
                        label = photo_data.get("collection", "") or photo_data.get("path", pid[:12])
                        photo_map[pid] = label
            break  # only need first face per identity

    options = [Option("All photos", value="")]
    for pid, label in sorted(photo_map.items(), key=lambda x: x[1]):
        options.append(Option(f"{label} ({pid[:8]}...)", value=pid))

    return tuple(options)


# =============================================================================
# DISCOVERY CARD BUILDER
# =============================================================================


def _build_discovery_card(d, registry, crop_files, tier=2, current_community=None, nav_prefix=""):
    """Build a single discovery card for the Discoveries page.

    Args:
        d: discovery dict with source_id, target_id, distance, etc.
        registry: identity registry
        crop_files: set of crop filenames
        tier: 1 (auto-added) or 2 (suggestion)
        current_community: current community dict for cross-community badges (COMMUNITY-014)
        nav_prefix: community URL prefix (e.g. "/c/rhodes") for user-facing links
    """

    source_id = d["source_id"]
    target_id = d["target_id"]
    source_name = d.get("source_name") or f"Identity {source_id[:8]}..."
    target_name = d.get("target_name") or f"Identity {target_id[:8]}..."
    distance = d.get("distance", 999)

    # Use distance-based tier labels instead of misleading percentages
    tier_label = confidence_tier_label(distance)
    badge_cls, ring_cls = confidence_tier_style(distance)

    source_crop = _resolve_identity_crop(source_id, crop_files)
    target_crop = _resolve_identity_crop(target_id, crop_files)

    # Build the face_id for source identity (first face)
    source_identity = _main_mod._safe_get_identity(registry, source_id)
    source_face_ids = (
        (source_identity.get("anchor_ids", []) + source_identity.get("candidate_ids", [])) if source_identity else []
    )
    first_face_id = d.get("face_id", "")
    if not first_face_id:
        for f in source_face_ids:
            first_face_id = f if isinstance(f, str) else f.get("face_id", "")
            if first_face_id:
                break

    face_id_encoded = quote(first_face_id, safe="")

    # Co-occurrence and confidence gap from discovery data
    co_occurrence = d.get("co_occurrence", 0)
    confidence_gap = d.get("confidence_gap", 0.0)

    # Resolve photo context for source face
    photo_context_el = None
    photo_id = None
    if first_face_id:
        photo_id = _main_mod.get_photo_id_for_face(first_face_id)
        if photo_id:
            photo_data = _main_mod.get_photo_metadata(photo_id)
            if photo_data:
                collection = photo_data.get("collection", "")
                co_faces = []
                photo_face_ids = [
                    f.get("face_id", "") if isinstance(f, dict) else f for f in photo_data.get("faces", [])
                ]
                for fid in photo_face_ids:
                    if fid == first_face_id or not fid:
                        continue
                    # Use fast identity lookup instead of O(n) scan
                    ident = _main_mod.get_identity_for_face(registry, fid)
                    if ident:
                        iid = ident.get("identity_id", "")
                        if iid and iid != source_id:
                            co_name = ident.get("name", "Unknown")
                            co_state = ident.get("state", "")
                            co_faces.append((iid, co_name, co_state))
                context_parts = []
                if collection:
                    context_parts.append(Span(collection, cls="text-xs text-slate-400"))
                if co_faces:
                    co_labels = []
                    for co_id, co_name, co_state in co_faces[:3]:
                        state_color = "text-green-400" if co_state == "CONFIRMED" else "text-slate-300"
                        co_labels.append(
                            A(
                                co_name,
                                href=f"{nav_prefix}/person/{co_id}",
                                cls=f"text-xs {state_color} hover:text-indigo-300",
                            )
                        )
                    context_parts.append(
                        Div(
                            Span("Also in photo: ", cls="text-xs text-slate-500"),
                            *[Span(label, ", " if i < len(co_labels) - 1 else "") for i, label in enumerate(co_labels)],
                            cls="flex flex-wrap items-center gap-0.5",
                        )
                    )
                context_parts.append(
                    A(
                        "View photo",
                        href=f"{nav_prefix}/photo/{photo_id}",
                        cls="text-xs text-indigo-400 hover:text-indigo-300 underline",
                        data_testid="discovery-photo-link",
                    )
                )
                if context_parts:
                    photo_context_el = Div(
                        *context_parts, cls="flex flex-col gap-1 px-4 py-2 border-t border-slate-700/50"
                    )

    # Face images — w-28 h-28 = 112px, rounded-lg for better face visibility
    source_img_el = (
        Img(
            src=source_crop or "/static/placeholder.jpg",
            alt=source_name,
            cls=f"w-28 h-28 rounded-lg object-cover {ring_cls}",
            loading="lazy",
        )
        if source_crop
        else Div(
            Span("?", cls="text-2xl text-slate-500"),
            cls=f"w-28 h-28 rounded-lg bg-slate-700 flex items-center justify-center {ring_cls}",
        )
    )
    source_img = A(
        source_img_el,
        href=f"{nav_prefix}/person/{source_id}",
        cls="block cursor-pointer hover:opacity-80 transition-opacity",
        title=f"View {source_name}",
        data_testid="discovery-source-link",
    )

    target_img_el = (
        Img(
            src=target_crop or "/static/placeholder.jpg",
            alt=target_name,
            cls="w-28 h-28 rounded-lg object-cover ring-2 ring-green-400/50",
            loading="lazy",
        )
        if target_crop
        else Div(
            Span("?", cls="text-2xl text-slate-500"),
            cls="w-28 h-28 rounded-lg bg-slate-700 flex items-center justify-center ring-2 ring-green-400/50",
        )
    )
    target_img = A(
        target_img_el,
        href=f"{nav_prefix}/person/{target_id}",
        cls="block cursor-pointer hover:opacity-80 transition-opacity",
        title=f"View {target_name}",
        data_testid="discovery-target-link",
    )

    # Tier-specific action buttons
    if tier == 1:
        # Auto-added: Confirm / Undo
        action_buttons = Div(
            Button(
                Svg(
                    Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2", d="M5 13l4 4L19 7"),
                    cls="w-4 h-4",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                ),
                Span("Confirm"),
                hx_post=f"/api/discovery/confirm?face_id={face_id_encoded}&target_id={target_id}&source_id={source_id}",
                hx_target=f"#discovery-card-{source_id}",
                hx_swap="outerHTML",
                cls="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-500 transition-colors min-h-[44px]",
            )
            if first_face_id
            else None,
            Button(
                Svg(
                    Path(
                        stroke_linecap="round",
                        stroke_linejoin="round",
                        stroke_width="2",
                        d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6",
                    ),
                    cls="w-4 h-4",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                ),
                Span("Undo"),
                hx_post=f"/api/discovery/undo?face_id={face_id_encoded}&target_id={target_id}&source_id={source_id}",
                hx_target=f"#discovery-card-{source_id}",
                hx_swap="outerHTML",
                cls="flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-500 transition-colors min-h-[44px]",
            ),
            cls="flex items-center justify-center gap-3 pb-4 px-4",
        )
    else:
        # Suggestion: Accept / Reject
        action_buttons = Div(
            Button(
                Svg(
                    Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2", d="M5 13l4 4L19 7"),
                    cls="w-4 h-4",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                ),
                Span(f"Confirm as {target_name}", cls="truncate max-w-[200px]"),
                hx_post=f"/api/face/tag?face_id={face_id_encoded}&target_id={target_id}",
                hx_target=f"#discovery-card-{source_id}",
                hx_swap="outerHTML",
                cls="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-500 transition-colors min-h-[44px] max-w-full",
                title=f"Confirm this face as {target_name}",
            )
            if first_face_id
            else None,
            Button(
                Svg(
                    Path(stroke_linecap="round", stroke_linejoin="round", stroke_width="2", d="M6 18L18 6M6 6l12 12"),
                    cls="w-4 h-4",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                ),
                Span("Not a match"),
                hx_post=f"/api/discovery/reject?source_id={source_id}&target_id={target_id}",
                hx_target=f"#discovery-card-{source_id}",
                hx_swap="outerHTML",
                cls="flex items-center gap-1.5 px-4 py-2 bg-slate-600 text-slate-200 text-sm font-medium rounded-lg hover:bg-slate-500 transition-colors min-h-[44px]",
            ),
            cls="flex items-center justify-center gap-3 pb-4 px-4",
        )

    # Tier indicator border
    tier_border = "border-l-2 border-l-emerald-500" if tier == 1 else "border-l-2 border-l-indigo-500"

    # Compare link — opens compare workspace with source and target pre-filled
    compare_link = A(
        Svg(
            Path(
                stroke_linecap="round",
                stroke_linejoin="round",
                stroke_width="2",
                d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
            ),
            cls="w-3.5 h-3.5",
            fill="none",
            stroke="currentColor",
            viewBox="0 0 24 24",
        ),
        Span("Compare"),
        href=f"{nav_prefix}/compare?face_id={face_id_encoded}&person_id={target_id}",
        cls="flex items-center gap-1 text-xs text-slate-400 hover:text-indigo-300 transition-colors",
        title="Compare side-by-side",
        data_testid="discovery-compare-link",
    )

    # Share button for this discovery
    share_btn = _main_mod.share_button(
        url=f"/person/{source_id}",
        style="link",
        label="Share",
        title="Can you help identify this person?",
        text=f"This face may be {target_name} — help us confirm!",
    )

    return Div(
        Div(
            Div(
                source_img,
                Div(
                    A(
                        source_name,
                        href=f"{nav_prefix}/person/{source_id}",
                        cls="text-sm font-medium text-white hover:text-indigo-300 truncate max-w-[200px] block",
                        title=source_name,
                        data_testid="discovery-source-name-link",
                    ),
                    Span(
                        "Auto-added" if tier == 1 else "Unreviewed",
                        cls=f"text-xs {'text-emerald-400' if tier == 1 else 'text-slate-400'}",
                    ),
                    _main_mod._cross_community_badge(source_id, current_community),
                    cls="mt-1.5 text-center",
                ),
                cls="flex flex-col items-center",
            ),
            Div(
                Svg(
                    Path(
                        stroke_linecap="round", stroke_linejoin="round", stroke_width="2", d="M14 5l7 7m0 0l-7 7m7-7H3"
                    ),
                    cls="w-6 h-6 text-slate-400",
                    fill="none",
                    stroke="currentColor",
                    viewBox="0 0 24 24",
                ),
                Span(
                    tier_label,
                    cls=f"text-sm font-semibold px-2 py-0.5 rounded-full border {badge_cls}",
                    data_testid="discovery-confidence-label",
                ),
                # Shared match metrics bar — same component as neighbor_card (Session 88 parity fix)
                _main_mod.match_info_bar(
                    distance,
                    confidence_gap=confidence_gap,
                    co_occurrence=co_occurrence,
                    show_badge=False,
                    show_distance=False,
                ),
                Div(compare_link, share_btn, cls="flex items-center gap-3"),
                cls="flex flex-col items-center gap-1.5 px-4",
            ),
            Div(
                target_img,
                Div(
                    A(
                        target_name,
                        href=f"{nav_prefix}/person/{target_id}",
                        cls="text-sm font-medium text-white hover:text-indigo-300 truncate max-w-[200px] block",
                        title=target_name,
                        data_testid="discovery-target-name-link",
                    ),
                    Span("Confirmed", cls="text-xs text-green-400"),
                    _main_mod._cross_community_badge(target_id, current_community),
                    cls="mt-1.5 text-center",
                ),
                cls="flex flex-col items-center",
            ),
            cls="flex items-center justify-center gap-2 py-4",
        ),
        photo_context_el,
        action_buttons,
        id=f"discovery-card-{source_id}",
        cls=f"bg-slate-800/80 border border-slate-700/50 rounded-xl hover:border-slate-600/50 transition-colors {tier_border}",
    )


def _build_help_identify_section(registry, crop_files, max_faces=6, community_identity_ids=None, nav_prefix=""):
    """Build the 'Help Identify' section showing top cold-case faces.

    These are unidentified faces (INBOX/PROPOSED/SKIPPED) that need community
    help. Sorted by face quality (highest first).
    """
    unid_faces = []
    for ident in registry.list_identities():
        if ident.get("merged_into"):
            continue
        # Community filter: skip identities not in current community
        if community_identity_ids is not None and ident["identity_id"] not in community_identity_ids:
            continue
        state = ident.get("state", "")
        if state not in ("INBOX", "PROPOSED", "SKIPPED"):
            continue
        face_ids = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
        if not face_ids:
            continue
        best_fid = _main_mod.get_best_face_id(face_ids)
        if not best_fid:
            best_fid = face_ids[0] if isinstance(face_ids[0], str) else face_ids[0].get("face_id", "")
        crop_url = _main_mod.resolve_face_image_url(best_fid, crop_files) if crop_files else None
        if not crop_url:
            continue
        quality = _main_mod.get_face_quality(best_fid) or 0.0
        photo_id = _main_mod.get_photo_id_for_face(best_fid)
        collection = ""
        if photo_id and _main_mod._photo_cache:
            pm = _main_mod._photo_cache.get(photo_id, {})
            collection = pm.get("collection", "")
        unid_faces.append(
            {
                "identity_id": ident["identity_id"],
                "crop_url": crop_url,
                "quality": quality,
                "collection": collection,
                "photo_id": photo_id,
            }
        )

    unid_faces.sort(key=lambda x: x["quality"], reverse=True)
    top_faces = unid_faces[:max_faces]

    if not top_faces:
        return None

    face_cards = []
    for item in top_faces:
        _iid = item["identity_id"]
        face_cards.append(
            A(
                Div(
                    Img(
                        src=item["crop_url"],
                        alt="Unidentified person",
                        cls="w-full h-full object-cover rounded-lg",
                        loading="lazy",
                    ),
                    cls="aspect-square overflow-hidden rounded-lg",
                ),
                Div(
                    P("Can you help?", cls="text-[10px] text-amber-300/80 font-medium mt-1"),
                    P(item["collection"], cls="text-[10px] text-slate-500 leading-snug truncate")
                    if item["collection"]
                    else None,
                    cls="text-center",
                ),
                href=f"{nav_prefix}/identify/{_iid}",
                cls="block hover:opacity-80 transition-opacity",
                data_testid="help-identify-card",
            )
        )

    total_unid = len(unid_faces)
    return Div(
        Div(
            Div(
                Span(
                    NotStr(
                        '<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
                    ),
                    cls="text-amber-400",
                ),
                H3("Help Identify", cls="text-lg font-semibold text-amber-400"),
                cls="flex items-center gap-2",
            ),
            P(
                f"{total_unid} face{'s' if total_unid != 1 else ''} still unidentified — can you help?",
                cls="text-xs text-slate-400 mt-1",
            ),
            cls="mb-3 pb-3 border-b border-amber-500/20",
        ),
        Div(*face_cards, cls="grid grid-cols-3 sm:grid-cols-6 gap-3"),
        Div(
            A(
                "View all unidentified faces",
                href="/help",
                cls="text-sm text-amber-400 hover:text-amber-300 underline",
            ),
            cls="mt-3 text-center",
        ),
        cls="p-4 bg-amber-500/5 border border-amber-500/10 rounded-xl",
        data_testid="section-help-identify",
    )


def _resolve_identity_crop(identity_id: str, crop_files: set) -> str:
    """Resolve the best face crop URL for an identity. Returns URL or None."""
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
        face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        for f in face_ids:
            fid = f if isinstance(f, str) else f.get("face_id", "")
            url = _main_mod.resolve_face_image_url(fid, crop_files)
            if url:
                return url
    except (KeyError, Exception):
        pass
    return None


# =============================================================================
# ROUTES - DISCOVERY ACTIONS (reject, confirm, undo)
# =============================================================================


@rt("/api/discovery/reject")
def post(source_id: str, target_id: str, sess=None):
    """Reject a discovery match by adding the target as a negative for the source identity.

    This prevents the match from showing up again. Logs to discovery_log.json
    for ML signal collection (AD-179). Returns a success confirmation
    that replaces the card via HTMX.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(source_id)
        negatives = identity.get("negative_ids", [])
        neg_entry = f"identity:{target_id}"
        if neg_entry not in negatives:
            registry.add_negative_reference(
                source_id,
                neg_entry,
                user_source="discovery_reject",
                metadata={"rejected_identity_id": target_id, "context": "discovery"},
            )
            _main_mod.save_registry(registry, changed_ids={source_id})

        # Log rejection to discovery_log for ML signal (AD-179)
        face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        first_fid = ""
        for f in face_ids:
            first_fid = f if isinstance(f, str) else f.get("face_id", "")
            if first_fid:
                break
        _main_mod._update_discovery_log_entry(first_fid, target_id, "rejected")

        # Dual-write to Supabase
        from app.supabase_data import sync_discovery_log_entry

        sync_discovery_log_entry(first_fid, target_id, "rejected")

        _main_mod._invalidate_discovery_cache()
        return Div(
            Div(
                Span("\u2716", cls="text-slate-500 mr-2"),
                Span("Match dismissed", cls="text-sm text-slate-400"),
                cls="flex items-center justify-center py-3",
            ),
            cls="bg-slate-800/30 border border-slate-700/30 rounded-xl opacity-60",
            style="animation: fadeOut 2s forwards;",
        )
    except (KeyError, Exception) as e:
        logging.error(f"[discoveries] Reject failed: {e}")
        return Div(
            _main_mod.toast("Failed to dismiss match. Please try again.", "error"),
            hx_swap_oob="beforeend:#toast-container",
        )


@rt("/api/discovery/confirm")
def post(face_id: str, target_id: str, source_id: str = "", sess=None, request=None):
    """Confirm a Tier 1 auto-clustered face. Logs to discovery_log.json (AD-179)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    try:
        from urllib.parse import unquote

        face_id = unquote(face_id)

        # Tag the face to the target identity (same as /api/face/tag)
        registry = _main_mod.load_registry()
        is_merged, canonical_id = _main_mod._check_merged_identity(target_id, registry)
        if is_merged:
            return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")
        target = registry.get_identity(target_id)
        if target:
            added = registry.add_candidate_face(
                target_id,
                face_id,
                user_source="discovery_confirm",
                metadata={"source_identity_id": source_id, "context": "discovery"},
            )
            if added:
                _main_mod.save_registry(registry, changed_ids={target_id})

        # Log confirmation to discovery_log
        _main_mod._update_discovery_log_entry(face_id, target_id, "confirmed")

        # Dual-write to Supabase
        from app.supabase_data import sync_discovery_log_entry

        sync_discovery_log_entry(face_id, target_id, "confirmed")

        _main_mod._invalidate_discovery_cache()

        return Div(
            Div(
                Span("\u2705", cls="text-green-500 mr-2"),
                Span("Confirmed", cls="text-sm text-green-400"),
                cls="flex items-center justify-center py-3",
            ),
            cls="bg-slate-800/30 border border-emerald-700/30 rounded-xl opacity-60",
            style="animation: fadeOut 2s forwards;",
        )
    except (KeyError, Exception) as e:
        logging.error(f"[discoveries] Confirm failed: {e}")
        return Div(
            _main_mod.toast("Failed to confirm. Please try again.", "error"), hx_swap_oob="beforeend:#toast-container"
        )


@rt("/api/discovery/undo")
def post(face_id: str, target_id: str, source_id: str = "", sess=None):
    """Undo a Tier 1 auto-clustered face. Removes from cluster, logs to discovery_log (AD-179)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    try:
        from urllib.parse import unquote

        face_id = unquote(face_id)

        # Remove face from target identity's candidate_ids
        registry = _main_mod.load_registry()
        target = registry.get_identity(target_id)
        if target:
            removed = registry.remove_candidate_face(
                target_id,
                face_id,
                user_source="discovery_undo",
                metadata={"source_identity_id": source_id, "context": "discovery"},
            )
            if removed:
                _main_mod.save_registry(registry, changed_ids={target_id})

        # Log undo to discovery_log — critical ML signal (false positive)
        _main_mod._update_discovery_log_entry(face_id, target_id, "undone")

        # Dual-write to Supabase
        from app.supabase_data import sync_discovery_log_entry

        sync_discovery_log_entry(face_id, target_id, "undone")

        _main_mod._invalidate_discovery_cache()

        return Div(
            Div(
                Span("\u21a9", cls="text-amber-500 mr-2"),
                Span("Auto-add undone — face returned to inbox", cls="text-sm text-amber-400"),
                cls="flex items-center justify-center py-3",
            ),
            cls="bg-slate-800/30 border border-amber-700/30 rounded-xl opacity-60",
            style="animation: fadeOut 2s forwards;",
        )
    except (KeyError, Exception) as e:
        logging.error(f"[discoveries] Undo failed: {e}")
        return Div(
            _main_mod.toast("Failed to undo. Please try again.", "error"), hx_swap_oob="beforeend:#toast-container"
        )


_main_mod._reorder_routes_atomic()
