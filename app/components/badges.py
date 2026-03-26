"""
Badge and tag UI components — extracted from app/main.py (Session 137).

Pure rendering functions that map data values to styled FastHTML Span/Div elements.
No module-level state dependencies on main.py.
"""

from fasthtml.common import Div, P, Span, Strong


def state_badge(state: str) -> Span:
    """
    Render state as a colored badge.
    UX Intent: Instant state recognition via color coding.
    """
    colors = {
        "INBOX": "bg-indigo-600 text-white",
        "CONFIRMED": "bg-emerald-600 text-white",
        "PROPOSED": "bg-amber-500 text-white",
        "CONTESTED": "bg-red-600 text-white",
        "REJECTED": "bg-rose-700 text-white",
        "SKIPPED": "bg-stone-500 text-white",
    }
    return Span(
        state,
        cls=f"text-sm sm:text-xs font-bold px-4 py-3 sm:px-2 sm:py-1 rounded {colors.get(state, 'bg-gray-500 text-white')}",
    )


def era_badge(era: str) -> Span:
    """
    Render era classification as a subtle badge.
    UX Intent: Temporal context without visual dominance.
    """
    if not era:
        return None
    return Span(
        era,
        cls="absolute top-2 right-2 bg-stone-700/80 text-white text-sm sm:text-xs px-4 py-3 sm:px-2 sm:py-1 font-mono",
    )


def _confidence_tier(distance: float) -> str:
    """Map embedding distance to confidence tier. Uses unified scoring (AD-200)."""
    from core.confidence import compute_face_confidence

    conf = compute_face_confidence(distance)
    # Map unified short_label -> legacy tier names for backward compat
    _label_to_tier = {"Very High": "VERY HIGH", "High": "HIGH", "Moderate": "MODERATE", "Low": "LOW", "Very Low": "LOW"}
    return _label_to_tier.get(conf["short_label"], "LOW")


_CONFIDENCE_RING = {"VERY HIGH": "ring-emerald-400", "HIGH": "ring-indigo-400", "MODERATE": "ring-amber-400"}
_CONFIDENCE_COLOR = {"VERY HIGH": "text-emerald-300", "HIGH": "text-indigo-300", "MODERATE": "text-amber-300"}
_CONFIDENCE_LABEL = {
    "VERY HIGH": "Strong match",
    "HIGH": "Good match",
    "MODERATE": "Possible match",
    "LOW": "Weak match",
}


def _confidence_tier_label(distance: float) -> "Span":
    """Map a distance value to a human-readable confidence tier pill.

    Tiers:
      < 0.80  -> Strong match (emerald)
      0.80-0.99 -> Good match (indigo)
      1.00-1.19 -> Possible match (amber)
      >= 1.20 -> Weak match (slate)
    """
    if distance < 0.80:
        text, cls_color = "Strong match", "text-emerald-300 bg-emerald-900/40 border-emerald-700/40"
    elif distance < 1.00:
        text, cls_color = "Good match", "text-indigo-300 bg-indigo-900/40 border-indigo-700/40"
    elif distance < 1.20:
        text, cls_color = "Possible match", "text-amber-300 bg-amber-900/40 border-amber-700/40"
    else:
        text, cls_color = "Weak match", "text-slate-400 bg-slate-700/40 border-slate-600/40"
    return Span(
        text, cls=f"text-[10px] font-medium px-1.5 py-0.5 rounded border {cls_color}", data_testid="confidence-tier"
    )


def _promotion_badge(identity: dict):
    """Badge for promoted (rediscovered) identities in browse view."""
    if not identity.get("promoted_from"):
        return None
    reason = identity.get("promotion_reason", "")
    if reason == "confirmed_match":
        return Span(
            "Suggested ID",
            cls="text-sm sm:text-xs px-2 py-0.5 rounded border bg-emerald-600/30 text-emerald-300 border-emerald-500/30",
            title="Previously skipped — now matches a confirmed identity",
        )
    else:
        return Span(
            "Rediscovered",
            cls="text-sm sm:text-xs px-2 py-0.5 rounded border bg-amber-600/30 text-amber-300 border-amber-500/30",
            title="Previously skipped — new match evidence found",
        )


def _promotion_banner(identity: dict):
    """Banner for promoted faces shown above expanded cards in Focus mode."""
    if not identity.get("promoted_from"):
        return None
    reason = identity.get("promotion_reason", "")
    context = identity.get("promotion_context", "")

    if reason == "confirmed_match":
        title = "Identity Suggested"
        desc = context or "This previously skipped face now matches a confirmed identity with high confidence."
        icon_cls = "text-emerald-400"
        border_cls = "border-emerald-600/40 bg-emerald-900/20"
    elif reason == "new_face_match":
        title = "New Context Available"
        desc = context or "A newly uploaded photo matches this previously skipped face."
        icon_cls = "text-amber-400"
        border_cls = "border-amber-600/40 bg-amber-900/20"
    else:  # group_discovery
        title = "Rediscovered"
        desc = context or "This face now groups with another face from a different batch."
        icon_cls = "text-amber-400"
        border_cls = "border-amber-600/40 bg-amber-900/20"

    return Div(
        Div(
            Span("*", cls=f"text-xl sm:text-lg font-bold {icon_cls}"),
            Div(
                Strong(title, cls="text-white text-sm"),
                P(desc, cls="text-slate-400 text-sm sm:text-xs mt-0.5"),
                cls="ml-2",
            ),
            cls="flex items-start",
        ),
        cls=f"rounded-lg border p-3 mb-3 {border_cls}",
    )


def _progressive_refinement_badge(label: dict) -> object:
    """Show badge when estimate was refined with verified facts."""
    if not label:
        return None
    metadata = label.get("_metadata", label.get("metadata", {}))
    if not metadata.get("refinement"):
        return None

    fact_count = metadata.get("fact_count", 0)
    return Span(
        f"Refined with {fact_count} verified fact{'s' if fact_count != 1 else ''}",
        cls="text-[10px] text-amber-300 bg-amber-900/30 px-4 py-3 sm:px-2 sm:py-1 rounded-full",
        data_testid="refinement-badge",
    )


def _actionability_badge(
    identity_id: str,
    ids_with_proposals: set = None,
    *,
    _skipped_neighbor_cache=None,
    _get_best_proposal_for_identity=None,
):
    """Return a visual badge for an identity's actionability level.

    Uses cached neighbor data from _skipped_neighbor_cache when available,
    falls back to proposals. Returns None if the identity has no leads.

    Note: _skipped_neighbor_cache and _get_best_proposal_for_identity are passed
    from main.py to avoid circular imports.
    """
    # Try cached neighbor distances first
    if _skipped_neighbor_cache and identity_id in _skipped_neighbor_cache:
        cached = _skipped_neighbor_cache[identity_id]
        confidence = cached[1]  # (distance, confidence, target_name)
    else:
        # Fallback to proposals
        if ids_with_proposals and identity_id not in ids_with_proposals:
            return None
        if _get_best_proposal_for_identity is None:
            return None
        best = _get_best_proposal_for_identity(identity_id)
        if not best:
            return None
        confidence = best.get("confidence", "")

    if confidence in ("VERY HIGH", "HIGH"):
        return Div(
            Span("Strong lead", cls="text-sm sm:text-xs font-bold text-emerald-300"),
            Span(" — ML found a likely match", cls="text-sm sm:text-xs text-slate-400"),
            cls="px-3 py-1 bg-emerald-900/30 border border-emerald-500/30 rounded-lg mb-1",
        )
    elif confidence == "MODERATE":
        return Div(
            Span("Good lead", cls="text-sm sm:text-xs font-bold text-amber-300"),
            Span(" — possible match found", cls="text-sm sm:text-xs text-slate-400"),
            cls="px-3 py-1 bg-amber-900/30 border border-amber-500/30 rounded-lg mb-1",
        )
    return None


def _cross_community_badge(identity_id: str, current_community: dict | None):
    """Return a badge if identity belongs to a DIFFERENT community than current.

    COMMUNITY-014: Shows "[Community Name]" badge when viewing cross-community content.
    Returns None if same community or no community context.
    Extracted from app/main.py in Session 138.
    """
    if current_community is None:
        return None

    current_slug = current_community.get("slug", "rhodes")
    current_id = current_community.get("id")
    if not current_id:
        return None

    from app.supabase_data import load_communities
    import app.main as _m

    communities = load_communities()
    if not communities:
        return None

    current_ids = _m._get_community_identity_ids(current_community)
    current_name = current_community.get("name", current_slug.replace("-", " ").title())
    if current_ids and identity_id in current_ids:
        return Span(
            current_name,
            cls="text-sm sm:text-xs px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400 border border-slate-600/30",
            title=f"From {current_name}",
        )

    for comm in communities:
        comm_slug = comm.get("slug", "")
        comm_id = comm.get("id")
        if not comm_id or comm_slug == current_slug:
            continue

        other_ids = _m._get_community_identity_ids(comm)
        if other_ids and identity_id in other_ids:
            comm_name = comm.get("name", comm_slug.replace("-", " ").title())
            return Span(
                comm_name,
                cls="text-sm sm:text-xs px-1.5 py-0.5 rounded bg-indigo-600/30 text-indigo-300 border border-indigo-500/30",
                title=f"This person appears in the {comm_name} archive",
            )

    return None
