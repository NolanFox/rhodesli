"""
Card components extracted from app/main.py (Session 138).

Includes: match_info_bar, face_card, identity_card_mini, search_result_card,
search_results_panel, _build_face_cards_for_entries, _face_pagination_controls,
FACES_PER_PAGE.

Uses lazy imports for app.main dependencies to avoid circular imports.
"""

from fasthtml.common import A, Button, Div, Img, Input, NotStr, P, Span
from urllib.parse import quote

from app.components.badges import _confidence_tier_label, era_badge
from app.components.nav import share_button
from app.utils import _section_for_state, make_css_id, parse_quality_from_filename
from core.ui_safety import ensure_utf8_display


FACES_PER_PAGE = 8


def match_info_bar(
    distance: float,
    confidence_gap: float = 0.0,
    co_occurrence: int = 0,
    show_distance: bool = True,
    show_badge: bool = True,
) -> Div:
    """Shared match metrics bar — used by neighbor_card and discovery cards.

    Session 88: Unified component so all match displays show the same info.
    Args:
        show_badge: If False, skip the "X% match" badge (caller already shows pct).
    """
    from core.confidence import compute_face_confidence

    conf = compute_face_confidence(distance)
    pct = conf["confidence_pct"]
    label = conf["short_label"]

    _similarity_classes = {
        "Very High": "bg-emerald-500/30 text-emerald-300",
        "High": "bg-emerald-500/20 text-emerald-400",
        "Moderate": "bg-amber-500/20 text-amber-400",
        "Low": "bg-amber-500/15 text-amber-500",
        "Very Low": "bg-slate-600 text-slate-400",
    }
    similarity_class = _similarity_classes.get(label, "bg-slate-600 text-slate-400")

    badge = (
        Span(f"{pct}% match", cls=f"text-sm sm:text-xs px-2 py-0.5 rounded {similarity_class}") if show_badge else None
    )

    details = []
    if show_distance:
        tier_label = _confidence_tier_label(distance)
        details.append(
            Span(f"Dist: {distance:.2f}", cls="text-sm sm:text-xs font-data text-slate-400 bg-slate-700 px-1 rounded")
        )
        details.append(tier_label)
    if confidence_gap > 0:
        details.append(
            Span(
                f"+{confidence_gap}% gap",
                cls="text-sm sm:text-xs font-data text-emerald-400/70 bg-emerald-900/30 px-1 rounded",
            )
        )
    if co_occurrence > 0:
        details.append(
            Span(
                f"Seen together in {co_occurrence} photo{'s' if co_occurrence != 1 else ''}",
                cls="text-[10px] text-amber-400 italic",
            )
        )

    return Div(
        badge,
        Div(*details, cls="flex items-center flex-wrap gap-1") if details else None,
        cls="flex flex-col gap-0.5",
        data_testid="match-info-bar",
    )


def face_card(
    face_id: str,
    crop_url: str,
    quality: float = None,
    era: str = None,
    identity_id: str = None,
    photo_id: str = None,
    show_actions: bool = False,
    show_detach: bool = False,
    is_admin: bool = True,
) -> Div:
    """
    Single face card with optional action buttons.
    UX Intent: Face-first display with metadata secondary.
    """
    import app.main as _m

    if quality is None:
        quality = parse_quality_from_filename(crop_url)
    if quality == 0.0:
        emb_quality = _m.get_face_quality(face_id)
        if emb_quality is not None:
            quality = emb_quality

    view_photo_btn = None
    if photo_id:
        _vp_url = f"/photo/{photo_id}/partial?face={face_id}"
        if identity_id:
            _vp_url += f"&identity_id={identity_id}"
        view_photo_btn = Button(
            "View Photo",
            cls="text-sm sm:text-xs text-slate-400 hover:text-slate-300 underline mt-1",
            hx_get=_vp_url,
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            **{"_": "on click remove .hidden from #photo-modal"},
            type="button",
        )

    full_page_link = None
    if photo_id:
        full_page_link = Span(
            share_button(photo_id, style="link", label="Share"),
            cls="mt-1 ml-2",
        )

    detach_btn = None
    if show_detach:
        safe_dom_id = make_css_id(face_id)
        detach_btn = Button(
            "Detach",
            cls="text-sm sm:text-xs text-slate-400 hover:text-slate-300 underline mt-1 ml-2",
            hx_post=f"/api/face/{quote(face_id)}/detach",
            hx_target=f"#{safe_dom_id}",
            hx_swap="outerHTML",
            hx_confirm="Move this face to its own identity? (You can merge it back later.)",
            type="button",
        )

    quality_word = None
    quality_label = None
    if quality > 0:
        quality_word = "Excellent" if quality >= 30 else "Good" if quality >= 20 else "Fair" if quality >= 10 else "Low"
        quality_label = f"{quality_word} quality"

    return Div(
        Div(
            Img(
                src=crop_url,
                alt=face_id,
                cls="w-full h-full object-cover sepia-[.15] hover:sepia-0 transition-all duration-300",
            ),
            era_badge(era) if era else None,
            cls="relative border border-amber-900/30 rounded-sm overflow-hidden min-h-[150px] sm:min-h-[200px]",
        ),
        Div(
            Span(
                quality_label,
                cls=f"text-sm sm:text-xs font-data {'text-emerald-500' if quality >= 20 else 'text-amber-500' if quality >= 10 else 'text-slate-500'}",
                title=f"Quality score: {quality:.2f}" if is_admin else None,
            )
            if quality_label
            else None,
            Div(
                view_photo_btn,
                full_page_link,
                detach_btn,
                cls="flex items-center"
                + ("" if show_detach else " opacity-0 group-hover:opacity-100 transition-opacity"),
            )
            if view_photo_btn or detach_btn or full_page_link
            else None,
            cls="mt-1 px-0.5 flex items-center justify-between",
        ),
        cls="face-card-archival group p-1 rounded overflow-hidden",
        id=make_css_id(face_id),
    )


def identity_card_mini(
    identity: dict, crop_files: set, clickable: bool = False, triage_filter: str = "", nav_prefix: str = ""
) -> Div:
    """Mini identity card for queue preview in Focus Mode."""
    import app.main as _m

    identity_id = identity["identity_id"]
    all_face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    crop_url = None
    best_fid = _m.get_best_face_id(all_face_ids)
    if best_fid:
        crop_url = _m.resolve_face_image_url(best_fid, crop_files)

    img_element = (
        Img(
            src=crop_url or "",
            cls="w-full h-full object-cover",
            loading="lazy",
            alt=identity.get("name", "Face thumbnail"),
        )
        if crop_url
        else Span("?", cls="text-2xl text-slate-500")
    )

    if clickable:
        section = _section_for_state(identity.get("state", "INBOX"))
        filter_suffix = f"&filter={triage_filter}" if triage_filter else ""
        return A(
            Div(
                img_element,
                cls="w-full aspect-square rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center hover:ring-2 hover:ring-indigo-400 transition-all",
            ),
            href=f"{nav_prefix}/?section={section}&view=focus&current={identity_id}{filter_suffix}",
            cls="w-24 flex-shrink-0 cursor-pointer",
            title="Click to review this identity",
        )
    else:
        return Div(
            Div(
                img_element,
                cls="w-full aspect-square rounded-lg overflow-hidden bg-slate-700 flex items-center justify-center",
            ),
            cls="w-24 flex-shrink-0",
        )


def search_result_card(
    result: dict,
    target_identity_id: str,
    crop_files: set,
    user_role: str = "admin",
    target_name: str = "",
    nav_prefix: str = "",
) -> Div:
    """Card for a manual search result."""
    import app.main as _m

    result_id = result["identity_id"]
    raw_name = ensure_utf8_display(result["name"])
    name = raw_name or f"Identity {result_id[:8]}..."
    face_count = result.get("face_count", 0)
    preview_face_id = result.get("preview_face_id")

    thumbnail_img = Div(cls="w-10 h-10 bg-slate-600 rounded")
    if preview_face_id:
        crop_url = _m.resolve_face_image_url(preview_face_id, crop_files)
        if crop_url:
            thumbnail_img = Img(src=crop_url, alt=name, cls="w-12 h-12 object-cover rounded border border-slate-600")

    compare_btn = Button(
        "Compare",
        cls="px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs font-bold border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20",
        hx_get=f"{nav_prefix}/api/identity/{target_identity_id}/compare/{result_id}",
        hx_target="#compare-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #compare-modal"},
        type="button",
    )

    if user_role == "contributor":
        merge_btn = Button(
            "Suggest Merge",
            cls="px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs font-bold bg-purple-600 text-white rounded hover:bg-purple-500",
            hx_post=f"{nav_prefix}/api/identity/{target_identity_id}/suggest-merge/{result_id}",
            hx_target=f"#search-result-{result_id}",
            hx_swap="outerHTML",
            data_auth_action="suggest a merge",
        )
    else:
        _confirm_msg = (
            f"Merge {name} into {target_name}? All faces will be combined."
            if target_name and not target_name.startswith("Unidentified")
            else "Merge these identities? This can be undone."
        )
        merge_btn = Button(
            "Merge",
            cls="px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs font-bold border border-indigo-500/50 text-indigo-400 rounded hover:bg-indigo-500/20",
            hx_post=f"{nav_prefix}/api/identity/{target_identity_id}/merge/{result_id}?source=manual_search",
            hx_target=f"#identity-{target_identity_id}",
            hx_swap="outerHTML",
            data_auth_action="merge these identities",
            hx_confirm=_confirm_msg,
        )

    nav_script = f"on click set target to #identity-{result_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-indigo-400 to target then wait 1.5s then remove .ring-2 .ring-indigo-400 from target"

    return Div(
        Div(
            A(
                thumbnail_img,
                href=f"#identity-{result_id}",
                cls="flex-shrink-0 cursor-pointer hover:opacity-80",
                **{"_": nav_script},
            ),
            Div(
                A(
                    name,
                    href=f"#identity-{result_id}",
                    cls="font-medium text-slate-200 truncate text-sm hover:text-indigo-400 hover:underline cursor-pointer",
                    **{"_": nav_script},
                ),
                Span(
                    f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-sm sm:text-xs text-slate-400 ml-2"
                ),
                Span(
                    cls="search-distance-scanner inline-block w-28 h-5 rounded bg-slate-700/50 ml-2",
                    hx_get=f"{nav_prefix}/api/identity/{target_identity_id}/distance/{result_id}",
                    hx_trigger="load",
                    hx_swap="outerHTML",
                ),
                cls="flex items-center ml-2 flex-1 min-w-0",
            ),
            Div(compare_btn, merge_btn, cls="flex items-center gap-1 flex-shrink-0 ml-2"),
            cls="flex items-center",
        ),
        id=f"search-result-{result_id}",
        cls="p-2 bg-slate-700 border border-slate-600 rounded shadow-md mb-2 hover:shadow-lg",
    )


def search_results_panel(
    results: list,
    target_identity_id: str,
    crop_files: set,
    user_role: str = "admin",
    target_name: str = "",
    nav_prefix: str = "",
) -> Div:
    """Panel showing manual search results."""
    if not results:
        return Div(
            P("No matching identities found.", cls="text-slate-400 italic text-sm"),
            id=f"search-results-{target_identity_id}",
        )

    cards = [
        search_result_card(
            r, target_identity_id, crop_files, user_role=user_role, target_name=target_name, nav_prefix=nav_prefix
        )
        for r in results
    ]
    return Div(*cards, id=f"search-results-{target_identity_id}")


def _build_face_cards_for_entries(face_entries, crop_files, identity_id, can_detach, is_admin=True):
    """Build face card elements from a list of face entries."""
    import app.main as _m

    cards = []
    for face_entry in face_entries:
        if isinstance(face_entry, str):
            face_id = face_entry
            era = None
        else:
            face_id = face_entry.get("face_id", "")
            era = face_entry.get("era_bin")

        crop_url = _m.resolve_face_image_url(face_id, crop_files)
        if crop_url:
            photo_id = _m.get_photo_id_for_face(face_id)
            cards.append(
                face_card(
                    face_id=face_id,
                    crop_url=crop_url,
                    era=era,
                    identity_id=identity_id,
                    photo_id=photo_id,
                    show_detach=can_detach,
                    is_admin=is_admin,
                )
            )
        else:
            cards.append(
                Div(
                    Div(
                        Span("?", cls="text-4xl text-slate-500"),
                        cls="w-full aspect-square bg-slate-700 border border-slate-600 flex items-center justify-center",
                    ),
                    P("Image unavailable", cls="text-sm sm:text-xs text-slate-400 mt-1"),
                    P(f"ID: {face_id[:12]}...", cls="text-sm sm:text-xs font-data text-slate-500"),
                    cls="face-card",
                    id=make_css_id(face_id),
                )
            )
    return cards


def _face_pagination_controls(identity_id: str, page: int, total_faces: int, sort: str = "date", nav_prefix: str = ""):
    """Build pagination controls for face grid carousel."""
    total_pages = (total_faces + FACES_PER_PAGE - 1) // FACES_PER_PAGE
    if total_pages <= 1:
        return None

    start = page * FACES_PER_PAGE + 1
    end = min((page + 1) * FACES_PER_PAGE, total_faces)

    prev_btn = (
        Button(
            Span("<", cls="text-lg"),
            cls="px-4 py-3 sm:px-2 sm:py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded transition-colors",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/faces?page={page - 1}&sort={sort}",
            hx_target=f"#faces-{identity_id}",
            hx_swap="outerHTML",
            type="button",
        )
        if page > 0
        else Button(
            Span("<", cls="text-lg"),
            cls="px-4 py-3 sm:px-2 sm:py-1 text-slate-400 opacity-30 cursor-not-allowed rounded",
            type="button",
            disabled=True,
        )
    )

    next_btn = (
        Button(
            Span(">", cls="text-lg"),
            cls="px-4 py-3 sm:px-2 sm:py-1 text-slate-400 hover:text-white hover:bg-slate-600 rounded transition-colors",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/faces?page={page + 1}&sort={sort}",
            hx_target=f"#faces-{identity_id}",
            hx_swap="outerHTML",
            type="button",
        )
        if page < total_pages - 1
        else Button(
            Span(">", cls="text-lg"),
            cls="px-4 py-3 sm:px-2 sm:py-1 text-slate-400 opacity-30 cursor-not-allowed rounded",
            type="button",
            disabled=True,
        )
    )

    return Div(
        prev_btn,
        Span(f"{start}-{end} of {total_faces}", cls="text-sm sm:text-xs text-slate-400 mx-2"),
        next_btn,
        cls="flex items-center justify-center gap-1 mt-3",
    )


def neighbor_card(
    neighbor: dict,
    target_identity_id: str,
    crop_files: set,
    show_checkbox: bool = True,
    user_role: str = "admin",
    from_focus: bool = False,
    triage_filter: str = "",
    focus_section: str = "",
    target_name: str = "",
    current_community: dict | None = None,
    nav_prefix: str = "",
    from_person_page: bool = False,
) -> Div:
    """Neighbor card for Similar Identities panel."""
    import app.main as _m

    neighbor_id = neighbor["identity_id"]
    name = _m._sequential_display_name(ensure_utf8_display(neighbor["name"]))
    if name.startswith("Unidentified Person "):
        name = "Person " + name[len("Unidentified Person ") :]
    distance = neighbor["distance"]
    percentile = neighbor.get("percentile", 1.0)
    confidence_gap = neighbor.get("confidence_gap", 0.0)

    can_merge = neighbor["can_merge"]
    face_count = neighbor.get("face_count", 0)
    co_occurrence = neighbor.get("co_occurrence", 0)

    from core.confidence import compute_face_confidence

    _disc_conf = compute_face_confidence(distance)
    similarity_label = _disc_conf["short_label"]
    calibrated_pct = _disc_conf["confidence_pct"]

    _similarity_classes = {
        "Very High": "bg-emerald-500/30 text-emerald-300",
        "High": "bg-emerald-500/20 text-emerald-400",
        "Moderate": "bg-amber-500/20 text-amber-400",
        "Low": "bg-amber-500/15 text-amber-500",
        "Very Low": "bg-slate-600 text-slate-400",
    }
    similarity_class = _similarity_classes.get(similarity_label, "bg-slate-600 text-slate-400")

    _focus_filter = f"&filter={triage_filter}" if triage_filter else ""
    _focus_section = f"&focus_section={focus_section}" if focus_section else ""
    focus_suffix = f"?from_focus=true{_focus_filter}{_focus_section}" if from_focus else ""
    _person_page_suffix = "&from_person_page=true" if from_person_page else ""
    if from_focus and focus_section == "skipped":
        merge_target = "#skipped-focus-container"
    elif from_focus:
        merge_target = "#focus-container"
    elif from_person_page:
        merge_target = f"#neighbor-{neighbor_id}"
    else:
        merge_target = f"#identity-{target_identity_id}"
    merge_swap = "outerHTML"
    if not can_merge:
        if user_role == "admin" and neighbor.get("merge_blocked_reason") == "co_occurrence":
            _preview_params = []
            if from_focus:
                _preview_params.append("from_focus=true")
                if triage_filter:
                    _preview_params.append(f"filter={triage_filter}")
                if focus_section:
                    _preview_params.append(f"focus_section={focus_section}")
            if from_person_page:
                _preview_params.append("from_person_page=true")
            _preview_qs = f"?{'&'.join(_preview_params)}" if _preview_params else ""
            merge_btn = Div(
                Button(
                    "Override \u26a0\ufe0f",
                    cls="px-3 py-1 text-sm font-bold bg-amber-700 hover:bg-amber-600 text-white rounded",
                    hx_get=f"{nav_prefix}/api/identity/{target_identity_id}/co-occurrence-preview/{neighbor_id}{_preview_qs}",
                    hx_target=f"#override-preview-{neighbor_id}",
                    hx_swap="innerHTML",
                    title=f"Override: {neighbor.get('merge_blocked_reason_display', 'Same photo')}",
                    aria_label="Show co-occurrence photo preview before override",
                ),
                Div(id=f"override-preview-{neighbor_id}"),
            )
        else:
            merge_btn = Button(
                "Blocked",
                cls="px-3 py-1 text-sm font-bold bg-slate-600 text-slate-400 rounded cursor-not-allowed",
                disabled=True,
                title=neighbor.get("merge_blocked_reason_display"),
            )
    elif user_role == "contributor":
        merge_btn = Button(
            "Suggest Merge",
            cls="px-3 py-1 text-sm font-bold bg-purple-600 text-white rounded hover:bg-purple-500",
            hx_post=f"{nav_prefix}/api/identity/{target_identity_id}/suggest-merge/{neighbor_id}",
            hx_target=f"#neighbor-{neighbor_id}",
            hx_swap="outerHTML",
            data_auth_action="suggest a merge",
        )
    else:
        _merge_label = (
            f"Merge \u2192 {target_name}" if target_name and not target_name.startswith("Unidentified") else "Merge"
        )
        _confirm_msg = (
            f"Merge {name} into {target_name}? All faces will be combined."
            if target_name and not target_name.startswith("Unidentified")
            else "Merge these identities? This can be undone."
        )
        _merge_url_suffix = focus_suffix
        if from_person_page and not _merge_url_suffix:
            _merge_url_suffix = "?from_person_page=true"
        elif from_person_page:
            _merge_url_suffix += "&from_person_page=true"
        _merge_btn_attrs = {
            "hx_post": f"{nav_prefix}/api/identity/{target_identity_id}/merge/{neighbor_id}{_merge_url_suffix}",
            "hx_target": merge_target,
            "hx_swap": merge_swap,
            "hx_disabled_elt": "this",
            "data_auth_action": "merge these identities",
            "title": f"Merge {name} into {target_name}" if target_name else "Merge these identities",
        }
        if from_focus:
            _merge_btn_attrs["hx_push_url"] = "false"
        if not from_focus:
            _merge_btn_attrs["hx_confirm"] = _confirm_msg
        merge_btn = Button(
            _merge_label,
            cls="px-3 py-1 text-sm font-bold bg-indigo-600 text-white rounded hover:bg-indigo-500 disabled:opacity-50",
            **_merge_btn_attrs,
            **{"_": "on click put 'Merging...' into me"},
        )

    _compare_filter = f"?filter={triage_filter}" if triage_filter else ""
    compare_btn = Button(
        "Compare",
        cls="px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs font-bold border border-amber-400/50 text-amber-400 rounded hover:bg-amber-500/20",
        hx_get=f"{nav_prefix}/api/identity/{target_identity_id}/compare/{neighbor_id}{_compare_filter}",
        hx_target="#compare-modal-content",
        hx_swap="innerHTML",
        **{"_": "on click remove .hidden from #compare-modal"},
        type="button",
    )

    thumbnail_img = Div(cls="w-16 h-16 sm:w-20 sm:h-20 bg-slate-600 rounded")
    anchor_face_ids = neighbor.get("anchor_face_ids", []) + neighbor.get("candidate_face_ids", [])
    crop_url = None
    best_fid = _m.get_best_face_id(anchor_face_ids) if anchor_face_ids else None
    if best_fid:
        crop_url = _m.resolve_face_image_url(best_fid, crop_files)
    if not crop_url:
        for fid in anchor_face_ids:
            crop_url = _m.resolve_face_image_url(fid, crop_files)
            if crop_url:
                break
    if crop_url:
        thumbnail_img = Img(
            src=crop_url,
            alt=name,
            cls="w-16 h-16 sm:w-20 sm:h-20 object-cover rounded border border-slate-600 hover:scale-105 transition-transform",
            loading="lazy",
        )

    checkbox = (
        Input(
            type="checkbox",
            cls="visible-bulk-cb w-4 h-4 rounded border-slate-500 bg-slate-700 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-0 cursor-pointer flex-shrink-0",
            **{"_": f"on change set #bulk-{neighbor_id}.checked to my.checked"},
        )
        if (show_checkbox and can_merge)
        else None
    )

    neighbor_section = _section_for_state(neighbor.get("state", "INBOX"))

    _cross_slug = _m._identity_home_community_slug(neighbor_id, current_community)
    if _cross_slug:
        _nav_prefix = _m.community_url_prefix(_cross_slug)
    else:
        _community_slug = current_community.get("slug") if current_community else None
        _nav_prefix = nav_prefix or _m.community_url_prefix(_community_slug)

    nav_script = f"on click set target to #identity-{neighbor_id} then if target exists call target.scrollIntoView({{behavior: 'smooth', block: 'center'}}) then add .ring-2 .ring-indigo-400 to target then wait 1.5s then remove .ring-2 .ring-indigo-400 from target else go to url '{_nav_prefix}/?section={neighbor_section}&view=browse#identity-{neighbor_id}'"

    return Div(
        Div(
            checkbox,
            A(
                thumbnail_img,
                href=f"{_nav_prefix}/?section={neighbor_section}&view=browse#identity-{neighbor_id}",
                cls="flex-shrink-0 cursor-pointer hover:opacity-80",
                **{"_": nav_script},
            ),
            Div(
                Div(
                    A(
                        name,
                        href=f"{_nav_prefix}/?section={neighbor_section}&view=browse#identity-{neighbor_id}",
                        cls="font-medium text-slate-200 hover:text-indigo-400 hover:underline cursor-pointer text-sm leading-tight",
                        **{"_": nav_script},
                    ),
                    Span(
                        f"{calibrated_pct}% match" if calibrated_pct is not None else similarity_label,
                        cls=f"text-sm sm:text-xs px-2 py-0.5 rounded ml-2 {similarity_class}",
                    ),
                    _m._cross_community_badge(neighbor_id, current_community),
                    cls="flex items-center flex-wrap gap-1",
                ),
                Div(
                    Span(
                        f"Dist: {distance:.2f}",
                        cls="text-sm sm:text-xs font-data text-slate-400 ml-2 bg-slate-700 px-1 rounded",
                    ),
                    _confidence_tier_label(distance),
                    Span(
                        f"+{confidence_gap}% gap",
                        cls="text-sm sm:text-xs font-data text-emerald-400/70 ml-1 bg-emerald-900/30 px-1 rounded",
                    )
                    if confidence_gap > 0
                    else None,
                    Span(
                        f"Seen together in {co_occurrence} photo{'s' if co_occurrence != 1 else ''}",
                        cls="text-[10px] text-amber-400 italic ml-1",
                    )
                    if co_occurrence > 0 and not neighbor.get("has_shared_faces")
                    else None,
                    Span(
                        f"Shares {neighbor.get('shared_face_count', 0)} face{'s' if neighbor.get('shared_face_count', 0) != 1 else ''} — merge recommended",
                        cls="text-[10px] text-red-400 font-bold italic ml-1",
                    )
                    if neighbor.get("has_shared_faces")
                    else None,
                    cls="flex items-center flex-wrap",
                ),
                cls="flex-1 min-w-0 ml-3",
            ),
            Div(
                compare_btn,
                merge_btn,
                Button(
                    "Not Same",
                    cls="px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs font-bold border border-red-400/50 text-red-400 rounded hover:bg-red-500/20",
                    hx_post=f"{_nav_prefix}/api/identity/{target_identity_id}/reject/{neighbor_id}",
                    hx_target=f"#neighbor-{neighbor_id}",
                    hx_swap="outerHTML",
                ),
                share_button(
                    url=f"{_nav_prefix}/identify/{target_identity_id}/match/{neighbor_id}",
                    style="icon",
                    title="Are these the same person?",
                    text=f"Help identify: {name}",
                ),
                cls="flex items-center gap-1 sm:gap-2 flex-shrink-0 sm:ml-2 mt-2 sm:mt-0",
            ),
            cls="flex flex-wrap sm:flex-nowrap items-center gap-2",
        ),
        id=f"neighbor-{neighbor_id}",
        cls="p-3 bg-slate-700 border border-slate-600 rounded shadow-md mb-2 hover:shadow-lg overflow-hidden",
    )
