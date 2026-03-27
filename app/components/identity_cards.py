"""
Identity card components extracted from app/main.py (Session 141, REFACTOR-001 Phase 3).

Contains: identity_card, identity_card_expanded, identity_card_compact,
_sequential_display_name, _proposal_banner, _proposal_badge_inline.

Uses lazy imports for app.main dependencies to avoid circular imports.
"""

from fasthtml.common import (
    A,
    Button,
    Details,
    Div,
    H3,
    H5,
    Img,
    Input,
    NotStr,
    Option,
    P,
    Select,
    Span,
    Summary,
    Svg,
    Path,
)

from app.components.badges import (
    _CONFIDENCE_LABEL,
    _promotion_badge,
    state_badge,
)
from app.components.nav import share_button
from app.utils import make_css_id
from core import storage
from core.ui_safety import ensure_utf8_display

# ---------------------------------------------------------------------------
# Sequential display name mapping for unidentified persons
# Maps UUID-fragment suffixes to sequential integers at render time
# ---------------------------------------------------------------------------
_unidentified_seq_map: dict[str, int] = {}
_unidentified_seq_counter: int = 0


def _sequential_display_name(name: str) -> str:
    """Convert UUID-fragment unidentified names to sequential numbers.

    'Unidentified Person efb4d153' -> 'Unidentified Person 1043'

    Only converts names where the suffix is a hex string (UUID fragment).
    Names already using numeric suffixes pass through unchanged.
    """
    global _unidentified_seq_counter
    if not name or not name.startswith("Unidentified Person "):
        return name
    suffix = name[len("Unidentified Person ") :]
    # If already numeric, pass through
    if suffix.isdigit():
        return name
    # If it's a hex UUID fragment, map to sequential number
    try:
        int(suffix, 16)
    except (ValueError, TypeError):
        return name
    if suffix not in _unidentified_seq_map:
        _unidentified_seq_counter += 1
        _unidentified_seq_map[suffix] = _unidentified_seq_counter
    return f"Unidentified Person {_unidentified_seq_map[suffix]}"


# ---------------------------------------------------------------------------
# Proposal display helpers
# ---------------------------------------------------------------------------


def _proposal_banner(identity_id: str):
    """Show a proposal banner if ML found a match for this identity."""
    import app.main as _m

    best = _m._get_best_proposal_for_identity(identity_id)
    if not best:
        return None
    confidence = best.get("confidence", "")
    target_name = best.get("target_identity_name", "Unknown")
    distance = best.get("distance", 0)
    from core.confidence import compute_confidence_pct

    confidence_pct = compute_confidence_pct(distance)

    color_cls = {
        "VERY HIGH": "bg-emerald-900/30 border-emerald-500/50 text-emerald-300",
        "HIGH": "bg-indigo-900/30 border-indigo-500/50 text-indigo-300",
        "MODERATE": "bg-amber-900/30 border-amber-500/50 text-amber-300",
    }.get(confidence, "bg-slate-700/30 border-slate-500/50 text-slate-300")

    all_proposals = _m._get_proposals_for_identity(identity_id)
    count_text = f" (+{len(all_proposals) - 1} additional)" if len(all_proposals) > 1 else ""

    # User-friendly confidence labels (UX fix: avoid mixing system vocabulary with prose)
    confidence_label = _CONFIDENCE_LABEL.get(confidence, "Possible match")

    return Div(
        Span(confidence_label, cls="text-sm sm:text-xs font-bold uppercase"),
        Span(" — ", cls="text-sm sm:text-xs opacity-50"),
        Span(f"Likely {target_name}", cls="text-sm font-medium"),
        Span(f" ({confidence_pct}%)", cls="text-sm sm:text-xs opacity-70"),
        Span(count_text, cls="text-sm sm:text-xs opacity-50") if count_text else None,
        cls=f"mt-2 px-3 py-2 rounded-lg border text-sm {color_cls}",
    )


def _proposal_badge_inline(identity_id: str):
    """Inline badge showing ML match target name + confidence on browse cards.

    COMMUNITY-012: Shows "Matches [Name] (XX%)" directly, not just count.
    """
    import app.main as _m

    proposals = _m._get_proposals_for_identity(identity_id)
    if not proposals:
        return None
    best = min(proposals, key=lambda p: p.get("distance", 999))
    confidence = best.get("confidence", "")
    target_name = best.get("target_identity_name", "?")
    # Compute confidence percentage
    from core.confidence import compute_face_confidence

    conf = compute_face_confidence(best.get("distance", 999))
    pct = conf.get("confidence_pct", 0)

    color_cls = {
        "VERY HIGH": "bg-emerald-600/30 text-emerald-300 border-emerald-500/30",
        "HIGH": "bg-indigo-600/30 text-indigo-300 border-indigo-500/30",
        "MODERATE": "bg-amber-600/30 text-amber-300 border-amber-500/30",
    }.get(confidence, "bg-slate-600/30 text-slate-300 border-slate-500/30")

    # Show full target name + percentage for actionable info
    short_name = target_name if len(target_name) <= 20 else target_name[:18] + "..."
    label = f"Matches {short_name} ({pct}%)" if pct else f"Matches {short_name}"

    return Span(
        label,
        cls=f"text-sm sm:text-xs px-2 py-0.5 rounded border {color_cls}",
        title=f"ML match: {target_name} — {confidence} confidence, distance {best.get('distance', 0):.3f}",
    )


# ---------------------------------------------------------------------------
# identity_card_expanded — Focus Mode review card
# ---------------------------------------------------------------------------


def identity_card_expanded(
    identity: dict, crop_files: set, is_admin: bool = True, triage_filter: str = "", nav_prefix: str = ""
) -> Div:
    """
    Expanded identity card for Focus Mode review.
    Shows larger thumbnail and prominent actions (admin only).

    Args:
        triage_filter: Active triage filter to preserve in action URLs
    """
    import app.main as _m

    identity_id = identity["identity_id"]
    raw_name = ensure_utf8_display(identity.get("name"))
    name = _sequential_display_name(raw_name or "Unidentified Person")
    state = identity["state"]

    # Get all faces
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_count = len(all_face_ids)

    # Get best-quality face for main thumbnail
    main_crop_url = None
    main_photo_id = None
    best_face_id = _m.get_best_face_id(all_face_ids, identity=identity)
    best_face_idx = 0
    if best_face_id:
        main_crop_url = _m.resolve_face_image_url(best_face_id, crop_files)
        main_photo_id = _m.get_photo_id_for_face(best_face_id)
        # Find index of best face in all_face_ids for lightbox navigation
        for _i, _fe in enumerate(all_face_ids):
            _fid = _fe if isinstance(_fe, str) else _fe.get("face_id", "")
            if _fid == best_face_id:
                best_face_idx = _i
                break

    # Build face grid for additional faces (skip best since it's shown as main thumbnail)
    face_previews = []
    for face_idx, face_entry in enumerate(all_face_ids):
        if isinstance(face_entry, str):
            face_id = face_entry
        else:
            face_id = face_entry.get("face_id", "")
        if face_id == best_face_id:
            continue
        crop_url = _m.resolve_face_image_url(face_id, crop_files)
        if crop_url:
            face_photo_id = _m.get_photo_id_for_face(face_id)
            if face_photo_id:
                face_previews.append(
                    Button(
                        Img(
                            src=crop_url,
                            cls="w-16 h-16 rounded object-cover border border-slate-600 hover:border-indigo-400 hover:scale-110 transition-all",
                            alt=f"Face {face_id[:8]}",
                        ),
                        cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded transition-all",
                        hx_get=f"{nav_prefix}/api/identity/{identity_id}/photos?index={face_idx}",
                        hx_target="#photo-modal-content",
                        **{"_": "on click remove .hidden from #photo-modal"},
                        type="button",
                        title="Click to view photo",
                    )
                )
            else:
                face_previews.append(
                    Img(
                        src=crop_url,
                        cls="w-16 h-16 rounded object-cover border border-slate-600",
                        alt=f"Face {face_id[:8]}",
                    )
                )

    # Action buttons - only for admins
    if is_admin:
        base_confirm_url = (
            f"{nav_prefix}/inbox/{identity_id}/confirm" if state == "INBOX" else f"{nav_prefix}/confirm/{identity_id}"
        )
        base_reject_url = (
            f"{nav_prefix}/inbox/{identity_id}/reject" if state == "INBOX" else f"{nav_prefix}/reject/{identity_id}"
        )
        _filter_suffix = f"&filter={triage_filter}" if triage_filter else ""
        confirm_url = f"{base_confirm_url}?from_focus=true{_filter_suffix}"
        reject_url = f"{base_reject_url}?from_focus=true{_filter_suffix}"
        skip_url = f"{nav_prefix}/identity/{identity_id}/skip?from_focus=true{_filter_suffix}"

        _confirm_btn = Button(
            "\u2713 Confirm",
            cls="px-4 py-2 bg-green-500 text-white font-medium rounded-lg hover:bg-green-600 transition-colors min-h-[44px]",
            hx_post=confirm_url,
            hx_target="#focus-container",
            hx_swap="outerHTML",
            hx_push_url="false",
            type="button",
            id="focus-btn-confirm",
        )

        actions = Div(
            _confirm_btn,
            Button(
                "\u23f8 Skip",
                cls="px-4 py-2 bg-yellow-500 text-white font-medium rounded-lg hover:bg-yellow-600 transition-colors min-h-[44px]",
                hx_post=skip_url,
                hx_target="#focus-container",
                hx_swap="outerHTML",
                hx_push_url="false",
                type="button",
                id="focus-btn-skip",
            ),
            Button(
                "\u2717 Reject",
                cls="px-4 py-2 bg-red-500 text-white font-medium rounded-lg hover:bg-red-600 transition-colors min-h-[44px]",
                hx_post=reject_url,
                hx_target="#focus-container",
                hx_swap="outerHTML",
                hx_push_url="false",
                type="button",
                id="focus-btn-reject",
            ),
            Button(
                "Find Similar",
                cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors ml-auto min-h-[44px]",
                hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
                hx_target=f"#neighbors-{identity_id}",
                hx_swap="innerHTML",
                type="button",
                id="focus-btn-similar",
                **{
                    "hx-on::after-swap": f"document.getElementById('neighbors-{identity_id}').scrollIntoView({{behavior: 'smooth', block: 'start'}})"
                },
            ),
            Span(
                "Keyboard: C S R F",
                cls="text-sm sm:text-xs text-slate-600 hidden sm:inline ml-2",
                title="C=Confirm, S=Skip, R=Reject, F=Find Similar",
            ),
            cls="flex flex-wrap items-center gap-3 mt-6",
        )
    else:
        actions = Div(
            Button(
                "Find Similar",
                cls="px-4 py-2 bg-slate-700 text-slate-300 font-medium rounded-lg hover:bg-slate-600 transition-colors",
                hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
                hx_target=f"#neighbors-{identity_id}",
                hx_swap="innerHTML",
                type="button",
                **{
                    "hx-on::after-swap": f"document.getElementById('neighbors-{identity_id}').scrollIntoView({{behavior: 'smooth', block: 'start'}})"
                },
            ),
            Button(
                "I Know This Person",
                cls="px-4 py-2 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-500 transition-colors",
                **{"_": f"on click toggle .hidden on #suggest-name-{identity_id}"},
                type="button",
            ),
            cls="flex items-center gap-3 mt-6",
        )

    # Lazy imports for functions that stay in other modules
    from app.components.forms import _suggest_name_form
    from app.engagement_routes import _identity_annotations_section, _identity_metadata_display

    return Div(
        Div(
            # Left: Main Face (clickable to open photo)
            Div(
                Button(
                    Div(
                        Img(src=main_crop_url or "", alt=name, cls="w-full h-full object-cover")
                        if main_crop_url
                        else Span("?", cls="text-6xl text-slate-500"),
                        cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center",
                    ),
                    cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-lg transition-all",
                    hx_get=f"{nav_prefix}/api/identity/{identity_id}/photos?index={best_face_idx}"
                    if main_photo_id
                    else None,
                    hx_target="#photo-modal-content",
                    **{"_": "on click remove .hidden from #photo-modal"} if main_photo_id else {},
                    type="button",
                    title="Click to view photo",
                )
                if main_photo_id
                else Div(
                    Img(src=main_crop_url, alt=name, cls="w-full h-full object-cover")
                    if main_crop_url
                    else Span("?", cls="text-6xl text-slate-500"),
                    cls="w-48 h-48 sm:w-72 sm:h-72 rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center",
                ),
                cls="flex-shrink-0",
            ),
            # Right: Details + Actions
            Div(
                H3(name, cls="text-xl font-semibold text-white font-display"),
                Div(
                    P(
                        f"{face_count} face{'s' if face_count != 1 else ''}",
                        cls="text-sm text-slate-400",
                    ),
                    A(
                        "View Public Page",
                        href=f"{nav_prefix}/person/{identity_id}",
                        cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 ml-3",
                        data_testid="view-public-page",
                    ),
                    cls="flex items-center mt-1",
                ),
                # Proposal banner — shows ML match suggestion if one exists
                _proposal_banner(identity_id),
                # Face grid preview
                Div(*face_previews, cls="flex gap-2 mt-4 flex-wrap") if len(face_previews) > 1 else None,
                # Neighbors container — auto-load if proposals exist
                Div(
                    id=f"neighbors-{identity_id}",
                    cls="mt-4",
                    **(
                        {
                            "hx_get": f"{nav_prefix}/api/identity/{identity_id}/neighbors?from_focus=true",
                            "hx_trigger": "load",
                            "hx_swap": "innerHTML",
                        }
                        if identity_id in _m._get_identities_with_proposals()
                        else {}
                    ),
                ),
                # FB-001: Always-visible merge search in Focus view (admin only)
                Div(
                    H5("Search to Merge", cls="text-sm font-semibold text-slate-300 mb-2"),
                    Input(
                        type="text",
                        name="q",
                        placeholder="Search by name to merge...",
                        cls="w-full px-3 py-2 text-sm bg-slate-800 border border-slate-600 text-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent placeholder-slate-500",
                        hx_get=f"{nav_prefix}/api/identity/{identity_id}/search",
                        hx_trigger="keyup changed delay:300ms",
                        hx_target=f"#focus-search-results-{identity_id}",
                        hx_include="this",
                    ),
                    Div(id=f"focus-search-results-{identity_id}", cls="mt-2"),
                    cls="mt-4 pt-3 border-t border-slate-700",
                    data_testid="focus-merge-search",
                )
                if is_admin
                else None,
                actions,
                # Suggest Name form (hidden by default, shown via Hyperscript toggle)
                _suggest_name_form(identity_id, nav_prefix=nav_prefix),
                # Identity metadata (AN-012)
                _identity_metadata_display(identity, is_admin=is_admin),
                # Identity annotations (AN-013/AN-014)
                _identity_annotations_section(identity_id, is_admin=is_admin),
                # Notes section (loads via HTMX)
                Div(
                    Button(
                        "Notes",
                        cls="text-sm sm:text-xs text-slate-400 hover:text-slate-300 underline",
                        hx_get=f"{nav_prefix}/api/identity/{identity_id}/notes",
                        hx_target=f"#notes-{identity_id}",
                        hx_swap="innerHTML",
                        type="button",
                    ),
                    Div(id=f"notes-{identity_id}", cls="mt-2"),
                    cls="mt-4 pt-3 border-t border-slate-700",
                ),
                cls="flex-1 min-w-0",
            ),
            cls="flex flex-col sm:flex-row gap-4 sm:gap-6",
        ),
        cls="identity-card-archival rounded-xl p-4 sm:p-6",
        id="focus-card",
    )


# ---------------------------------------------------------------------------
# identity_card_compact — backward compat delegate
# ---------------------------------------------------------------------------


def identity_card_compact(
    identity: dict,
    crop_files: set,
    is_admin: bool = True,
) -> Div:
    """Deprecated: delegates to identity_card(show_triage=True) for backward compat."""
    return identity_card(identity, crop_files, show_triage=True, is_admin=is_admin)


# ---------------------------------------------------------------------------
# identity_card — main browse card
# ---------------------------------------------------------------------------


def identity_card(
    identity: dict,
    crop_files: set,
    lane_color: str = "stone",
    show_actions: bool = False,
    is_admin: bool = True,
    show_triage: bool = False,
    nav_prefix: str = "",
) -> Div:
    """
    Identity group card showing all faces (anchors + candidates).
    UX Intent: Group context with individual face visibility.
    Action buttons only shown for admin users.
    Shows first page of faces (max FACES_PER_PAGE) with pagination if more exist.
    """
    import app.main as _m
    from app.components.cards import FACES_PER_PAGE, _build_face_cards_for_entries, _face_pagination_controls
    from app.relationship_routes import _load_gedcom_face_links

    identity_id = identity["identity_id"]
    raw_name = ensure_utf8_display(identity.get("name"))
    name = _sequential_display_name(raw_name or f"Identity {identity_id[:8]}...")
    state = identity["state"]

    # Combine anchors (confirmed) and candidates (proposed) for display
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    total_faces = len(all_face_ids)

    # Show detach button only if identity has more than one face AND user is admin
    can_detach = total_faces > 1 and is_admin

    # Show only first page of faces
    page_entries = all_face_ids[:FACES_PER_PAGE]
    face_cards = _build_face_cards_for_entries(
        page_entries, crop_files, identity_id, can_detach, is_admin=is_admin, nav_prefix=nav_prefix
    )

    if not face_cards:
        return None

    # Sort dropdown for face ordering
    sort_dropdown = Select(
        Option("Sort by Date", value="date", selected=True),
        Option("Sort by Outlier", value="outlier"),
        cls="text-sm sm:text-xs border border-slate-600 bg-slate-700 text-slate-300 rounded px-4 py-3 sm:px-2 sm:py-1",
        hx_get=f"{nav_prefix}/api/identity/{identity_id}/faces",
        hx_target=f"#faces-{identity_id}",
        hx_swap="outerHTML",
        name="sort",
        hx_trigger="change",
    )

    # --- Compact pill-style action buttons for card layout (DD-005) ---
    _pill = "px-4 py-3 sm:px-2.5 sm:py-1 text-sm sm:text-xs font-medium rounded-full transition-all duration-200"

    # View All Photos button (opens photo modal)
    view_all_photos_btn = (
        Button(
            "Photos",
            cls=f"{_pill} bg-amber-500/15 text-amber-300 hover:bg-amber-500/25",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/photos?index=0",
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            **{"_": "on click remove .hidden from #photo-modal"},
            type="button",
        )
        if total_faces > 0
        else None
    )

    # Faces button — for multi-face identities, opens the admin face gallery
    _faces_detail_id = f"admin-details-{make_css_id(identity_id)}"
    faces_btn = None
    if total_faces > 1:
        faces_btn = Button(
            f"Faces ({total_faces})",
            cls=f"{_pill} bg-purple-500/15 text-purple-300 hover:bg-purple-500/25 transition-all duration-200 active:scale-95",
            type="button",
            data_testid="faces-button",
            data_action="toggle-faces",
        )

    # View Public Page link (Gap 3: always show Profile link)
    view_public_link = A(
        "Profile",
        href=f"{nav_prefix}/person/{identity_id}",
        cls=f"{_pill} text-slate-400 hover:text-indigo-300 hover:bg-indigo-500/15",
    )

    _id_css = make_css_id(identity_id)

    # GEDCOM Tree link button (B3)
    gedcom_tree_btn = None
    if is_admin and state == "CONFIRMED":
        gedcom_links = _load_gedcom_face_links()
        gedcom_link = gedcom_links.get(identity_id)
        if gedcom_link:
            gedcom_tree_btn = A(
                "Tree",
                href=f"{nav_prefix}/tree?person={identity_id}",
                cls=f"{_pill} text-emerald-300 hover:bg-emerald-500/15",
            )
        else:
            _tree_icon = NotStr(
                '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" '
                'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
                'stroke-linejoin="round" aria-hidden="true" style="display:inline;vertical-align:-1px;margin-right:3px">'
                '<path d="M17 18a2 2 0 0 0-2-2H9a2 2 0 0 0-2 2"/>'
                '<rect width="18" height="18" x="3" y="3" rx="2"/>'
                '<circle cx="12" cy="10" r="3"/>'
                "</svg>"
            )
            gedcom_tree_btn = Button(
                _tree_icon,
                "Link Tree",
                hx_get=f"{nav_prefix}/api/cluster-review/gedcom-panel?identity_id={identity_id}",
                hx_target=f"#expand-{_id_css}",
                hx_swap="innerHTML",
                type="button",
                title="Connect this person to their family tree record",
                cls=f"{_pill} text-amber-300 bg-amber-500/10 hover:bg-amber-500/20",
            )

    # Find Similar — admin: inline expansion with full neighbors_sidebar, public: full-page link
    if is_admin:
        find_similar_btn = Button(
            "Similar",
            cls=f"{_pill} bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?container_id=expand-{_id_css}",
            hx_target=f"#expand-{_id_css}",
            hx_swap="innerHTML",
            type="button",
            **{"_": "on click toggle .find-similar-active on closest .identity-card"},
        )
    else:
        find_similar_btn = A(
            "Similar",
            href=f"{nav_prefix}/people/{identity_id}/similar",
            cls=f"{_pill} bg-indigo-500/15 text-indigo-300 hover:bg-indigo-500/25",
        )

    proposal_count = _m._get_proposal_target_count(identity_id) if is_admin else 0
    review_proposals_btn = (
        A(
            f"Proposals ({proposal_count})",
            href=f"{nav_prefix}/admin/upload-review#identity-group-{identity_id}",
            cls=f"{_pill} bg-amber-500/15 text-amber-300 hover:bg-amber-500/25",
            data_testid="identity-card-review-proposals",
        )
        if proposal_count > 0
        else None
    )

    # Pagination controls
    pagination = _face_pagination_controls(identity_id, 0, total_faces, "date", nav_prefix=nav_prefix)

    # Badge for merged-unnamed identities (multiple faces but no human name)
    grouped_badge = None
    if total_faces > 1 and (name.startswith("Unidentified") or name.startswith("Identity ")):
        grouped_badge = Span(
            f"Grouped ({total_faces} faces)",
            cls="text-sm sm:text-xs px-2 py-0.5 rounded bg-purple-600/20 text-purple-300 border border-purple-500/30 ml-2",
        )

    # Quality label from best face for compact header display
    best_face_id = _m.get_best_face_id(all_face_ids, identity=identity) if all_face_ids else None
    best_quality = None
    if best_face_id:
        best_quality = _m.get_face_quality(best_face_id)
    quality_label_text = None
    if best_quality and best_quality > 0:
        quality_label_text = (
            "Excellent"
            if best_quality >= 30
            else "Good"
            if best_quality >= 20
            else "Fair"
            if best_quality >= 10
            else "Low"
        )

    # --- Photo-dominant card design (DD-005) ---
    best_face = best_face_id or (all_face_ids[0] if all_face_ids else None)
    hero_crop_url = _m.resolve_face_image_url(best_face, crop_files) if best_face else None
    person_href = (
        f"{nav_prefix}/person/{identity_id}" if state == "CONFIRMED" else f"{nav_prefix}/identify/{identity_id}"
    )

    # Build cycle URLs for face cycling carousel (up to 5 faces)
    cycle_urls = []
    if hero_crop_url:
        cycle_urls.append(hero_crop_url)
    best_face_str = best_face if isinstance(best_face, str) else ""
    for fid_entry in all_face_ids:
        fid = fid_entry if isinstance(fid_entry, str) else fid_entry.get("face_id", "")
        if fid == best_face_str:
            continue
        url = _m.resolve_face_image_url(fid, crop_files)
        if url:
            cycle_urls.append(url)
        if len(cycle_urls) >= 5:
            break
    has_cycling = len(cycle_urls) > 1

    # Share button for this person — show for any named identity
    person_share_btn = (
        share_button(
            url=f"{nav_prefix}/person/{identity_id}",
            style="icon",
            title=f"{name} — Jews of Rhodes Heritage Archive",
            text=f"Do you recognize {name}? Help us identify people in our heritage photo archive.",
        )
        if not name.startswith("Unidentified") and not name.startswith("Identity ")
        else None
    )

    # Multi-face gallery thumbnails for identities with 3+ faces
    multi_face_gallery = None
    if total_faces >= 3:
        extra_faces = []
        for fid_entry in all_face_ids:
            fid = fid_entry if isinstance(fid_entry, str) else fid_entry.get("face_id", "")
            if fid == best_face_str:
                continue
            extra_url = _m.resolve_face_image_url(fid, crop_files)
            if extra_url:
                extra_faces.append(extra_url)
            if len(extra_faces) >= 3:
                break

        if extra_faces:
            thumb_items = []
            for idx, eurl in enumerate(extra_faces):
                thumb_items.append(
                    Img(
                        src=eurl,
                        alt=f"{name} face {idx + 2}",
                        cls="w-8 h-8 rounded-full object-cover border-2 border-slate-800"
                        " shadow-sm hover:scale-110 transition-transform",
                        loading="lazy",
                    )
                )
            remaining = total_faces - 1 - len(extra_faces)
            if remaining > 0:
                thumb_items.append(
                    Span(
                        f"+{remaining}",
                        cls="w-8 h-8 rounded-full bg-slate-700 border-2 border-slate-800"
                        " text-[10px] text-slate-300 font-medium flex items-center justify-center",
                    )
                )
            multi_face_gallery = A(
                *thumb_items,
                href=person_href,
                cls="flex items-center -space-x-2 mt-1.5 cursor-pointer",
                title=f"View all {total_faces} faces",
            )

    # Face cycling arrows (prev/next) — only for multi-face identities
    cycle_prev_btn = None
    cycle_next_btn = None
    cycle_dots = None
    if has_cycling:
        _arrow_cls = (
            "absolute top-1/2 -translate-y-1/2 z-10 w-7 h-7 flex items-center justify-center"
            " bg-black/60 hover:bg-black/80 text-white rounded-full text-sm font-bold"
            " opacity-60 group-hover:opacity-100 transition-opacity duration-200 cursor-pointer"
            " backdrop-blur-sm select-none"
        )
        cycle_prev_btn = Button(
            NotStr("&#8249;"),
            cls=f"{_arrow_cls} left-1.5",
            data_action="face-cycle-prev",
            type="button",
            aria_label="Previous face",
        )
        cycle_next_btn = Button(
            NotStr("&#8250;"),
            cls=f"{_arrow_cls} right-1.5",
            data_action="face-cycle-next",
            type="button",
            aria_label="Next face",
        )
        dots = []
        for i in range(len(cycle_urls)):
            dot_cls = "w-1.5 h-1.5 rounded-full transition-all duration-200 " + (
                "bg-white" if i == 0 else "bg-white/40"
            )
            dots.append(Span(cls=dot_cls, data_dot_index=str(i)))
        cycle_dots = Div(
            *dots,
            cls="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1 z-10"
            " opacity-70 group-hover:opacity-100 transition-opacity duration-200",
            data_cycle_dots="true",
        )

    hero_section = Div(
        A(
            Img(
                src=hero_crop_url,
                alt=name,
                cls="w-full aspect-square object-cover face-crop-enter rounded-xl transition-all duration-300",
                loading="lazy",
                data_cycle_img="true",
            )
            if hero_crop_url
            else Div(
                Span("?", cls="text-5xl text-slate-600"),
                cls="w-full aspect-square bg-slate-800 rounded-xl flex items-center justify-center",
            ),
            href=person_href,
            cls="block overflow-hidden rounded-xl",
        ),
        cycle_prev_btn,
        cycle_next_btn,
        cycle_dots,
        Span(
            f"{total_faces}",
            cls="absolute top-2 right-2 w-7 h-7 flex items-center justify-center"
            " bg-amber-600/90 text-white text-sm sm:text-xs font-bold rounded-full"
            " shadow-lg backdrop-blur-sm",
        )
        if total_faces > 1
        else None,
        Span(
            person_share_btn,
            cls="absolute top-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200",
        )
        if person_share_btn
        else None,
        Div(
            multi_face_gallery,
            cls="absolute bottom-2 left-2 right-2",
        )
        if multi_face_gallery
        else None,
        cls="relative group",
        data_cycle_urls="|".join(cycle_urls) if has_cycling else None,
        data_cycle_index="0" if has_cycling else None,
    )

    # Name + state row
    display_name = name
    if name.startswith("Unidentified Person "):
        display_name = "Person " + name[len("Unidentified Person ") :]
    name_section = Div(
        A(
            display_name,
            href=person_href,
            cls="text-sm font-semibold text-slate-100 hover:text-amber-300 transition-colors block truncate",
            title=name,
        ),
        Div(
            state_badge(state),
            _proposal_badge_inline(identity_id),
            _promotion_badge(identity),
            grouped_badge,
            cls="flex items-center gap-1.5 mt-1",
        ),
        cls="mt-3 px-1",
    )

    # Action buttons — clean icon pills
    action_section = Div(
        view_all_photos_btn,
        faces_btn,
        find_similar_btn,
        review_proposals_btn,
        gedcom_tree_btn,
        view_public_link,
        cls="flex flex-col sm:flex-row flex-wrap gap-3 sm:gap-1.5 w-full sm:w-auto text-center mt-3 px-1",
    )

    # Triage buttons — visible labeled row for quick review (when show_triage=True)
    triage_section = None
    if show_triage and is_admin and state in ("INBOX", "PROPOSED", "SKIPPED"):
        _triage_pill = "px-5 py-4 sm:px-3 sm:py-1.5 text-sm sm:text-xs font-bold rounded-full transition-all duration-200 min-h-[32px]"
        confirm_url = (
            f"{nav_prefix}/inbox/{identity_id}/confirm" if state == "INBOX" else f"{nav_prefix}/confirm/{identity_id}"
        )
        reject_url = (
            f"{nav_prefix}/inbox/{identity_id}/reject" if state == "INBOX" else f"{nav_prefix}/reject/{identity_id}"
        )

        # FB-004: Show merge context when strong match exists, and wire auto-merge
        best_match = _m._get_best_match_for_identity(identity_id)
        confirm_label = "\u2713 Confirm"
        _confirm_url = confirm_url
        if best_match:
            match_name = best_match.get("target_identity_name", "")
            match_target_id = best_match.get("target_identity_id", "")
            if match_name and not match_name.startswith("Unidentified") and match_target_id:
                confirm_label = f"\u2713 Confirm as {match_name}"
                # Pass merge_target_id so confirm also auto-merges
                _sep = "&" if "?" in _confirm_url else "?"
                _confirm_url = f"{_confirm_url}{_sep}merge_target_id={match_target_id}"

        triage_btns = [
            Button(
                confirm_label,
                cls=f"{_triage_pill} bg-emerald-600 text-white hover:bg-emerald-500",
                hx_post=_confirm_url,
                hx_target=f"#identity-{identity_id}",
                hx_swap="outerHTML",
                type="button",
                title=f"Confirm and merge with {best_match.get('target_identity_name', '')}"
                if best_match and best_match.get("target_identity_name", "")
                else "Confirm as new person",
            ),
        ]
        if state in ("INBOX", "PROPOSED"):
            triage_btns.append(
                Button(
                    "\u23f8 Skip",
                    cls=f"{_triage_pill} bg-amber-600/80 text-white hover:bg-amber-500",
                    hx_post=f"{nav_prefix}/identity/{identity_id}/skip",
                    hx_target=f"#identity-{identity_id}",
                    hx_swap="outerHTML",
                    type="button",
                )
            )
        triage_btns.append(
            Button(
                "\u2717 Reject",
                cls=f"{_triage_pill} border border-red-500/60 text-red-400 hover:bg-red-500/20",
                hx_post=reject_url,
                hx_target=f"#identity-{identity_id}",
                hx_swap="outerHTML",
                type="button",
            )
        )
        triage_section = Div(
            *triage_btns,
            cls="flex flex-col sm:flex-row flex-wrap gap-3 sm:gap-1.5 w-full sm:w-auto text-center mt-2 px-1",
        )

    # Admin tools — collapsible to keep cards clean
    admin_tools = None
    if is_admin:
        from app.engagement_routes import _identity_metadata_display

        admin_tools = Details(
            Summary(
                NotStr(
                    '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/></svg>'
                ),
                cls="list-none cursor-pointer mt-2 px-1 flex items-center gap-1"
                " text-slate-500 hover:text-slate-300 transition-colors select-none",
                aria_label="Admin tools",
            ),
            Div(
                Div(
                    sort_dropdown,
                    _m.review_action_buttons(
                        identity_id, state, is_admin=is_admin, nav_prefix=nav_prefix, identity_name=name
                    ),
                    cls="flex flex-wrap items-center gap-2",
                ),
                _identity_metadata_display(identity, is_admin=is_admin),
                Div(
                    Div(
                        *face_cards,
                        cls="grid grid-cols-1 sm:grid-cols-1 sm:grid-cols-2 md:grid-cols-3 md:grid-cols-4 gap-3",
                    ),
                    pagination,
                    id=f"faces-{identity_id}",
                    cls="mt-2",
                )
                if total_faces > 1
                else None,
                cls="mt-2 px-1 pt-2 border-t border-slate-700/50",
            ),
            id=_faces_detail_id,
        )

    # Build expanded face view for toggle animation (FB-001)
    expanded_face_cards = []
    for face_entry in all_face_ids:
        fid = face_entry if isinstance(face_entry, str) else face_entry.get("face_id", "")
        c_url = _m.resolve_face_image_url(fid, crop_files)
        p_id = _m.get_photo_id_for_face(fid)
        qual = _m.get_face_quality(fid) or 0
        q_label = "Excellent" if qual >= 30 else "Good" if qual >= 20 else "Fair" if qual >= 10 else "Low"
        q_color = "text-emerald-400" if qual >= 20 else "text-amber-400" if qual >= 10 else "text-slate-400"

        if c_url:
            expanded_face_cards.append(
                A(
                    Img(
                        src=c_url,
                        alt=f"Face of {name}",
                        cls="w-28 h-28 sm:w-32 sm:h-32 object-cover rounded-2xl shadow-lg hover:scale-[1.03] transition-transform duration-300 ring-1 ring-white/10",
                        loading="lazy",
                    ),
                    P(q_label, cls=f"text-center text-sm font-medium {q_color} mt-2"),
                    href=f"{nav_prefix}/photo/{p_id}" if p_id else "#",
                    target="_blank",
                    cls="flex flex-col items-center",
                )
            )
        else:
            expanded_face_cards.append(
                Div(
                    Div(
                        Span("?", cls="text-3xl text-slate-500"),
                        cls="w-28 h-28 sm:w-32 sm:h-32 bg-slate-700 border border-slate-600 rounded-2xl flex items-center justify-center shadow-inner",
                    ),
                    P("Unavailable", cls="text-center text-sm font-medium text-slate-500 mt-2"),
                    cls="flex flex-col items-center",
                )
            )

    faces_expanded = Div(
        Div(
            Div(
                H3(display_name, cls="text-2xl font-serif font-bold text-white"),
                state_badge(state),
                cls="flex items-center gap-3",
            ),
            Button(
                "\u2715",
                cls="text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-full w-8 h-8 flex items-center justify-center text-xl sm:text-lg font-bold transition-colors shadow-sm",
                data_action="toggle-faces",
                type="button",
                aria_label="Close expanded view",
            ),
            cls="flex justify-between items-start mb-6 w-full",
        ),
        Div(
            *expanded_face_cards,
            cls="flex flex-wrap gap-4 sm:gap-6 justify-center w-full mb-6",
        ),
        Div(
            view_all_photos_btn,
            find_similar_btn,
            review_proposals_btn,
            gedcom_tree_btn,
            view_public_link,
            cls="flex flex-wrap gap-2 justify-center w-full pt-4 border-t border-slate-700/50",
        ),
        cls="faces-expanded w-full flex-col",
    )

    return Div(
        Div(
            hero_section,
            name_section,
            action_section,
            triage_section,
            admin_tools,
            cls="faces-compact flex-col h-full",
        ),
        faces_expanded,
        cls="person-card identity-card bg-slate-800/60 border border-slate-700/50 rounded-2xl p-3"
        " hover:border-slate-600 hover:bg-slate-800/80 transition-all"
        " hover:shadow-lg hover:shadow-slate-900/50 relative group ring-0 hover:ring-2 ring-indigo-500/30",
        id=f"identity-{identity_id}",
        data_name=(raw_name or "").lower(),
    )
