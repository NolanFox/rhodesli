"""
Identity routes extracted from app/main.py.

Identity modification routes: confirm, reject, merge, rename, notes,
metadata, bulk operations, skip, discoveries, inbox review, face operations,
neighbors, search, and associated helpers.
"""

import json
import logging
from pathlib import Path

from fasthtml.common import *
from starlette.responses import Response

from core.ui_safety import ensure_utf8_display

from app.main import rt
from app.utils import photo_url, _section_for_state

import app.main as _main_mod

logger = logging.getLogger(__name__)


@rt("/confirm/{identity_id}")
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
    """
    Confirm an identity (move from PROPOSED to CONFIRMED).
    Requires admin.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        # Lock contention or file access error
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Confirm the identity
    try:
        registry.confirm_identity(identity_id, user_source="web")
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _main_mod.save_registry(
            registry,
            confirmed_identity_info={
                "identity_id": identity_id,
                "identity_name": identity.get("name", "Unknown"),
                "user_id": _user.id if _user else None,
                "user_email": _user.email if _user else None,
            },
        )
        _main_mod.posthog_capture(
            "admin_identity_confirmed",
            distinct_id=_user.email if _user else "admin",
            properties={"identity_id": identity_id, "identity_name": identity.get("name", "Unknown")},
        )
    except Exception as e:
        # Could be variance explosion or other error
        return Response(
            to_xml(_main_mod.toast(f"Cannot confirm: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # AD-150: Fire recalibration hook (best-effort, non-blocking)
    try:
        anchor_ids = identity.get("anchor_ids", [])
        _main_mod._fire_recalibration_hook("confirm", identity_id, anchor_face_ids=anchor_ids)
    except Exception:
        pass  # Never block confirm on calibration

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            _main_mod.get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
            _main_mod.toast("Identity confirmed.", "success"),
        )

    # Return updated card (now CONFIRMED, no action buttons)
    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)
    identity_name = ensure_utf8_display(updated_identity.get("name", "Unknown"))

    # Check if already linked to GEDCOM — if not, show link panel (AD-160)
    gedcom_panel = None
    existing_links = _main_mod._load_gedcom_face_links()
    if identity_id not in existing_links and not identity_name.startswith("Unidentified"):
        gedcom_panel = _main_mod._gedcom_link_panel(identity_id, identity_name)

    # Return the card plus a success toast (+ GEDCOM link panel if applicable)
    parts = [
        _main_mod.identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        _main_mod.toast("Identity confirmed.", "success"),
    ]
    if gedcom_panel:
        parts.append(gedcom_panel)
    return tuple(parts)


@rt("/reject/{identity_id}")
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
    """Contest/reject an identity (move to CONTESTED). Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        registry.contest_identity(identity_id, user_source="web", reason="Rejected via UI")
        _main_mod.save_registry(registry)
    except Exception as e:
        return Response(
            to_xml(_main_mod.toast(f"Cannot reject: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            _main_mod.get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
            _main_mod.toast("Identity contested.", "warning"),
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    return (
        _main_mod.identity_card(updated_identity, crop_files, lane_color="red", show_actions=False),
        _main_mod.toast("Identity contested.", "warning"),
    )


@rt("/api/identity/{identity_id}/reject-match/{neighbor_id}", methods=["POST"])
def post(identity_id: str, neighbor_id: str, sess=None):
    """Record a negative match between two identities and remove the tile."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    is_admin = user and user.is_admin if user else not _main_mod.is_auth_enabled()
    if not is_admin:
        return Response("Forbidden", status_code=403)

    registry = _main_mod.load_registry()
    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")
    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    # Record bidirectional negative pair
    try:
        registry.reject_identity_pair(identity_id, neighbor_id, user_source="admin_inline")
        _main_mod.save_registry(registry)
    except KeyError:
        pass  # Neighbor may have been merged/deleted

    # Return empty div to remove the tile
    return ""


# ---- Collection Pages ----


def _collection_slug(name: str) -> str:
    """Convert collection name to URL slug."""
    return _main_mod.re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _collection_from_slug(slug: str, collections: dict) -> str:
    """Find collection name from slug."""
    for name in collections:
        if _main_mod._collection_slug(name) == slug:
            return name
    return ""


def _get_collections_data():
    """Build collection metadata from photo_index."""
    photo_reg = _main_mod.load_photo_registry()
    registry = _main_mod.load_registry()
    photos = photo_reg.list_photos() if hasattr(photo_reg, "list_photos") else []

    # Fall back to raw photo_index if list_photos not available
    if not photos:
        pi_path = _main_mod.data_path / "photo_index.json"
        if pi_path.exists():
            pi = json.loads(pi_path.read_text(encoding="utf-8"))
            photos = list(pi.get("photos", {}).values())
            for p in photos:
                if "photo_id" not in p:
                    # Try to generate from path
                    path = p.get("path", "")
                    if path:
                        p["photo_id"] = _main_mod.hashlib.sha256(Path(path).name.encode()).hexdigest()[:16]

    collections = {}
    for photo in photos:
        col_name = photo.get("collection", "") or photo.get("source", "")
        if not col_name:
            continue
        if col_name not in collections:
            collections[col_name] = {
                "name": col_name,
                "slug": _main_mod._collection_slug(col_name),
                "photos": [],
                "identified_count": 0,
                "unidentified_count": 0,
            }
        collections[col_name]["photos"].append(photo)

    # Count identified vs unidentified faces per collection
    for col_name, col_data in collections.items():
        identified = set()
        unidentified = 0
        for photo in col_data["photos"]:
            for fid in photo.get("face_ids", []):
                ident = _main_mod.get_identity_for_face(registry, fid)
                if ident and ident.get("state") == "CONFIRMED" and not ident.get("name", "").startswith("Unidentified"):
                    identified.add(ident.get("identity_id"))
                elif ident:
                    unidentified += 1
        col_data["identified_count"] = len(identified)
        col_data["unidentified_count"] = unidentified

    return collections


# =============================================================================
# ROUTES - PHASE 3: DISCOVERY & ACTION
# =============================================================================


@rt("/api/identity/{identity_id}/neighbors")
def get(
    identity_id: str,
    limit: int = 5,
    offset: int = 0,
    from_focus: bool = False,
    focus_section: str = "",
    container_id: str = "",
    sess=None,
    request=None,
):
    """
    Get nearest neighbor identities for potential merge.

    Args:
        identity_id: Identity to find neighbors for
        limit: Number of neighbors per page (default 5)
        offset: Number of neighbors already shown (for Load More)

    Returns HTML partial with neighbor cards and merge buttons.
    Implements D3 (Load More pagination).
    """
    try:
        registry = _main_mod.load_registry()
        registry.get_identity(identity_id)
    except KeyError:
        return Div(P("Identity not found.", cls="text-red-600 text-center py-4"), cls="neighbors-sidebar")

    # Load required data
    face_data = _main_mod.get_face_data()
    photo_registry = _main_mod.load_photo_registry()

    # Request one extra to determine if more exist (B3: pagination)
    try:
        from core.neighbors import find_nearest_neighbors

        total_to_fetch = offset + limit + 1
        all_neighbors = find_nearest_neighbors(identity_id, registry, photo_registry, face_data, limit=total_to_fetch)
    except ImportError as e:
        print(f"[neighbors] Missing dependency: {e}")
        return Div(
            P("Find Similar requires scipy. Check server dependencies.", cls="text-amber-500 text-center py-4"),
            cls="neighbors-sidebar",
        )
    except Exception as e:
        print(f"[neighbors] Error computing neighbors: {e}")
        return Div(
            P("Could not compute similar identities.", cls="text-red-500 text-center py-4"), cls="neighbors-sidebar"
        )

    # Determine if more neighbors exist beyond current page
    has_more = len(all_neighbors) > offset + limit

    # Return only neighbors up to current offset + limit
    neighbors = all_neighbors[: offset + limit]

    # Enhance neighbor data with additional info for UI
    crop_files = _main_mod.get_crop_files()
    for n in neighbors:
        # Add face IDs for thumbnail resolution (B2-REPAIR)
        # First try anchors, then fallback to candidates for PROPOSED identities
        n["anchor_face_ids"] = registry.get_anchor_face_ids(n["identity_id"])
        n["candidate_face_ids"] = registry.get_candidate_face_ids(n["identity_id"])
        # Add state for correct section routing in neighbor_card links
        try:
            n_identity = registry.get_identity(n["identity_id"])
            n["state"] = n_identity.get("state", "INBOX")
        except KeyError:
            n["state"] = "INBOX"

        # Compute co-occurrence: how many photos these two identities share
        n["co_occurrence"] = _main_mod._compute_co_occurrence(identity_id, n["identity_id"], registry, photo_registry)

        # Enhance blocked merge reason with photo filename
        if not n["can_merge"] and n["merge_blocked_reason"] == "co_occurrence":
            filename = _main_mod.find_shared_photo_filename(identity_id, n["identity_id"], registry, photo_registry)
            if filename:
                n["merge_blocked_reason_display"] = f"Appear together in {filename}"
            else:
                n["merge_blocked_reason_display"] = "Appear together in a photo"

    # Count rejected identities for contextual recovery indicator
    identity = registry.get_identity(identity_id)
    rejected_count = sum(1 for neg in identity.get("negative_ids", []) if neg.startswith("identity:"))

    target_name = ensure_utf8_display(identity.get("name", "")) or ""
    current_community = getattr(request.state, "community", None) if request else None
    return _main_mod.neighbors_sidebar(
        identity_id,
        neighbors,
        crop_files,
        offset=offset + limit,  # Next offset for Load More
        has_more=has_more,
        rejected_count=rejected_count,
        user_role=_main_mod._get_user_role(sess),
        from_focus=from_focus,
        focus_section=focus_section,
        target_name=target_name,
        container_id=container_id,
        current_community=current_community,
    )


@rt("/api/identity/{identity_id}/neighbors/close")
def get(identity_id: str):
    """
    Close the neighbors sidebar (B1: explicit exit from Find Similar mode).

    Returns empty content to clear the sidebar.
    """
    return Div(
        # Return just the loading indicator (hidden by default)
        Span(
            "Loading...",
            id=f"neighbors-loading-{identity_id}",
            cls="htmx-indicator text-slate-400 text-sm",
        ),
    )


@rt("/api/identity/{identity_id}/skip-hints")
def get(identity_id: str):
    """
    Lazy-loaded ML hints for skipped identities.

    Shows top 3 similar confirmed/named identities to help re-evaluate.
    """
    try:
        registry = _main_mod.load_registry()
        registry.get_identity(identity_id)
    except KeyError:
        return Span()

    face_data = _main_mod.get_face_data()
    photo_registry = _main_mod.load_photo_registry()

    try:
        from core.neighbors import find_nearest_neighbors

        # Fetch up to 5 candidates, then trim based on confidence
        neighbors = find_nearest_neighbors(identity_id, registry, photo_registry, face_data, limit=5)
    except Exception:
        return Span()

    if not neighbors:
        return Span("No similar identities found.", cls="text-xs text-slate-500 italic")

    # Variable suggestion count: show more when top match is confident,
    # fewer when uncertain. If best match is strong, show up to 3;
    # if weak, show only 1 to avoid decision fatigue.
    best_dist = neighbors[0]["distance"] if neighbors else float("inf")
    if best_dist < _main_mod.MATCH_THRESHOLD_HIGH:
        max_show = 3  # Strong match — show alternatives for comparison
    elif best_dist < _main_mod.MATCH_THRESHOLD_LOW:
        max_show = 2  # Moderate — show a couple
    else:
        max_show = 1  # Weak — just show the best guess
    neighbors = neighbors[:max_show]

    # Enrich neighbor data with face IDs for thumbnail resolution
    # (find_nearest_neighbors returns raw results without face IDs)
    for n in neighbors:
        n["anchor_face_ids"] = registry.get_anchor_face_ids(n["identity_id"])
        n["candidate_face_ids"] = registry.get_candidate_face_ids(n["identity_id"])

    # Map distance to confidence tier for visual display
    # Uses config constants for consistency with neighbor_card (AD-013)
    from core.confidence import confidence_tier_with_dots

    # Build suggestion cards with visual confidence and action buttons
    crop_files = _main_mod.get_crop_files()
    suggestion_items = []
    for n in neighbors:
        name = ensure_utf8_display(n.get("name", "Unknown"))
        dist = n.get("distance", 0)
        neighbor_id = n.get("identity_id", "")
        tier_label, tier_color, tier_dots = confidence_tier_with_dots(dist)

        # Face thumbnail — use enriched anchor/candidate face IDs (same pattern as neighbor_card)
        thumb = Div(cls="w-10 h-10 rounded-full bg-slate-600 flex-shrink-0")
        all_face_ids = n.get("anchor_face_ids", []) + n.get("candidate_face_ids", [])
        for fid in all_face_ids:
            face_url = _main_mod.resolve_face_image_url(fid, crop_files)
            if face_url:
                thumb = Img(
                    src=face_url, cls="w-10 h-10 rounded-full object-cover flex-shrink-0 border border-slate-600"
                )
                break

        # Confidence dots (filled vs empty)
        dots = Span(
            *[
                Span(cls=f"inline-block w-1.5 h-1.5 rounded-full {'bg-current' if i < tier_dots else 'bg-slate-600'}")
                for i in range(5)
            ],
            cls=f"flex gap-0.5 items-center {tier_color.replace('bg-', 'text-')}",
        )

        # State badge for named vs unidentified
        is_named = not name.startswith("Unidentified Person")
        name_cls = "text-sm text-white font-medium truncate" if is_named else "text-sm text-slate-300 truncate"

        # Action buttons
        compare_btn = Button(
            "Compare",
            cls="text-[10px] px-2 py-0.5 bg-slate-600 hover:bg-slate-500 text-slate-300 rounded transition-colors",
            hx_get=f"/api/identity/{identity_id}/compare/{neighbor_id}",
            hx_target="#compare-modal-content",
            hx_swap="innerHTML",
            type="button",
            **{"_": "on click remove .hidden from #compare-modal"},
        )
        _merge_confirm = (
            f"Merge with {name}? All faces will be combined."
            if name and not name.startswith("Unidentified")
            else "Merge these identities? This can be undone."
        )
        merge_btn = (
            Button(
                "Merge",
                cls="text-[10px] px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors",
                hx_post=f"/api/identity/{neighbor_id}/merge/{identity_id}",
                hx_target="#focus-container",
                hx_swap="outerHTML",
                hx_confirm=_merge_confirm,
                type="button",
            )
            if tier_dots >= 3
            else None
        )  # Only show merge for Moderate+ confidence

        suggestion_items.append(
            Div(
                thumb,
                Div(
                    Span(name, cls=name_cls),
                    Div(
                        dots,
                        Span(tier_label, cls=f"text-[10px] {tier_color.replace('bg-', 'text-')}"),
                        cls="flex items-center gap-1.5",
                    ),
                    cls="flex-1 min-w-0 flex flex-col",
                ),
                Div(compare_btn, merge_btn, cls="flex gap-1 flex-shrink-0"),
                cls="flex items-center gap-2 p-2 rounded hover:bg-slate-700/50 transition-colors",
            )
        )

    return Div(
        Div(
            Span("AI suggestions", cls="text-xs text-slate-400 font-medium"),
            cls="mb-1",
        ),
        *suggestion_items,
        cls="mt-2 bg-slate-800/50 rounded-lg border border-slate-700/50 p-1",
    )


@rt("/api/identity/{identity_id}/search")
def get(identity_id: str, q: str = "", sess=None):
    """
    Search for identities by name for manual merge.

    Phase 3B: Manual Search & Human-Authorized Merge Tools

    Args:
        identity_id: Current identity (excluded from results)
        q: Search query (minimum 2 characters)

    Returns HTMX partial with search result cards.
    """
    # Minimum query length
    if len(q.strip()) < 2:
        return Div(id=f"search-results-{identity_id}")

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Div(P("Search unavailable.", cls="text-slate-400 italic text-sm"), id=f"search-results-{identity_id}")

    # Search for matching identities
    results = registry.search_identities(q, exclude_id=identity_id)

    # Get target name for merge confirmation
    try:
        target_data = registry.get_identity(identity_id)
        _target_name = ensure_utf8_display(target_data.get("name", ""))
    except (KeyError, TypeError):
        _target_name = ""

    crop_files = _main_mod.get_crop_files()
    return _main_mod.search_results_panel(
        results, identity_id, crop_files, user_role=_main_mod._get_user_role(sess), target_name=_target_name
    )


@rt("/api/search")
def get(q: str = ""):
    """
    Global search for identities by name. Used by the sidebar search input.

    Args:
        q: Search query (minimum 2 characters, case-insensitive partial match)

    Returns HTMX partial with matching identity results (limit 10).
    Each result links to the correct section based on identity state.
    """
    if len(q.strip()) < 2:
        return ""

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Div(
            P("Search unavailable.", cls="text-slate-400 italic text-sm p-2"),
        )

    # Search all non-merged identities by name
    results = registry.search_identities(q)
    if not results:
        return Div(
            P("No matches found.", cls="text-slate-400 italic text-sm p-3"),
        )

    crop_files = _main_mod.get_crop_files()
    items = []
    query_stripped = q.strip()
    for r in results[:10]:
        face_url = (
            _main_mod.resolve_face_image_url(r["preview_face_id"], crop_files) if r.get("preview_face_id") else None
        )
        thumb = (
            Img(src=face_url, cls="w-8 h-8 rounded-full object-cover flex-shrink-0")
            if face_url
            else Div(cls="w-8 h-8 rounded-full bg-slate-600 flex-shrink-0")
        )
        name = ensure_utf8_display(r["name"]) or "Unnamed"

        # Highlight matched portion in name (case-insensitive)
        highlighted_name = _main_mod._highlight_match(name, query_stripped)

        # Route to correct section based on identity state
        section = _section_for_state(r.get("state", "INBOX"))

        # State badge for non-confirmed results
        state = r.get("state", "INBOX")
        state_indicator = None
        if state != "CONFIRMED":
            state_colors = {
                "PROPOSED": "bg-indigo-500/20 text-indigo-300",
                "INBOX": "bg-slate-500/20 text-slate-300",
                "SKIPPED": "bg-amber-500/20 text-amber-300",
            }
            badge_cls = state_colors.get(state, "bg-slate-500/20 text-slate-300")
            state_label = "Help Identify" if state == "SKIPPED" else state.title()
            state_indicator = Span(state_label, cls=f"text-[10px] px-1.5 py-0.5 rounded {badge_cls}")

        # Navigate to the right page based on state
        if state == "CONFIRMED" and not name.startswith("Unidentified"):
            result_href = f"/person/{r['identity_id']}"
        else:
            result_href = f"/identify/{r['identity_id']}"

        items.append(
            A(
                thumb,
                Div(
                    Div(
                        Span(highlighted_name, cls="text-sm text-slate-200 truncate"),
                        state_indicator,
                        cls="flex items-center gap-1.5",
                    ),
                    Span(
                        f"{r['face_count']} {'face' if r['face_count'] == 1 else 'faces'}", cls="text-xs text-slate-500"
                    ),
                    cls="flex flex-col min-w-0",
                ),
                href=result_href,
                cls="flex items-center gap-2 px-3 py-2 hover:bg-slate-700 transition-colors cursor-pointer",
            )
        )
    return Div(*items)


@rt("/api/face/tag-search")
def get(face_id: str, q: str = "", seq: str = "", sess=None):
    """
    Search for identities to tag a face with (Instagram-style tagging).

    Admin: returns merge buttons (direct action).
    Non-admin: returns suggestion buttons (creates annotation for review).
    Pass seq=1 to propagate sequential "Name These Faces" mode through tag actions.
    """
    import json as _json
    from urllib.parse import quote as _url_quote

    safe_face_id = face_id.replace(":", "-").replace(" ", "_")
    face_id_encoded = _url_quote(face_id, safe="")
    seq_suffix = "&seq=1" if seq == "1" else ""
    results_id = f"tag-results-{safe_face_id}"

    if len(q.strip()) < 2:
        return Div(id=results_id)

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Div(P("Search unavailable.", cls="text-slate-400 italic text-xs"), id=results_id)

    # Determine user role for rendering appropriate action buttons
    user_is_admin = False
    if not _main_mod.is_auth_enabled():
        user_is_admin = True
    else:
        user = _main_mod.get_current_user(sess or {})
        if user and user.is_admin:
            user_is_admin = True

    # Find the identity this face belongs to (to exclude from results)
    source_identity = _main_mod.get_identity_for_face(registry, face_id)
    exclude_id = source_identity["identity_id"] if source_identity else None
    source_identity_id = source_identity["identity_id"] if source_identity else ""

    # Search all identities (confirmed get priority in search_identities)
    results = registry.search_identities(q, exclude_id=exclude_id)

    crop_files = _main_mod.get_crop_files()
    items = []
    for r in results[:8]:
        face_url = (
            _main_mod.resolve_face_image_url(r["preview_face_id"], crop_files) if r.get("preview_face_id") else None
        )
        thumb = (
            Img(src=face_url, cls="w-8 h-8 rounded-full object-cover flex-shrink-0")
            if face_url
            else Div(cls="w-8 h-8 rounded-full bg-slate-600 flex-shrink-0")
        )
        name = ensure_utf8_display(r["name"]) or "Unnamed"

        if user_is_admin:
            # Admin: direct merge
            btn = Button(
                thumb,
                Div(
                    Span(name, cls="text-sm text-slate-200 truncate"),
                    Span(f"{r['face_count']} faces", cls="text-xs text-slate-500"),
                    cls="flex flex-col min-w-0 text-left",
                ),
                cls="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer",
                hx_post=f"/api/face/tag?face_id={face_id_encoded}&target_id={r['identity_id']}{seq_suffix}",
                hx_target="#photo-modal-content",
                hx_swap="innerHTML",
                type="button",
            )
        else:
            # Non-admin: submit name suggestion annotation
            btn = Button(
                thumb,
                Div(
                    Span(name, cls="text-sm text-slate-200 truncate"),
                    Span("Suggest match", cls="text-xs text-indigo-400"),
                    cls="flex flex-col min-w-0 text-left",
                ),
                cls="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer",
                hx_post="/api/annotations/submit",
                hx_vals=_json.dumps(
                    {
                        "target_type": "identity",
                        "target_id": source_identity_id,
                        "annotation_type": "name_suggestion",
                        "value": name,
                        "confidence": "likely",
                        "reason": f"face_tag:{face_id}:matched_to:{r['identity_id']}",
                    }
                ),
                hx_target="#toast-container",
                hx_swap="beforeend",
                type="button",
            )
        items.append(btn)

    # Bottom option: create new identity (admin) or suggest new name (non-admin)
    from urllib.parse import quote as _url_quote

    if user_is_admin:
        create_btn = Button(
            Div(
                "+",
                cls="w-8 h-8 rounded-full bg-indigo-600 flex-shrink-0 flex items-center justify-center text-white font-bold text-lg",
            ),
            Div(
                Span(f'Create "{q.strip()}"', cls="text-sm text-indigo-300 truncate"),
                Span("New identity", cls="text-xs text-slate-500"),
                cls="flex flex-col min-w-0 text-left",
            ),
            cls="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer "
            "border-t border-slate-700 mt-1 pt-1",
            hx_post=f"/api/face/create-identity?face_id={face_id_encoded}&name={_url_quote(q.strip())}{seq_suffix}",
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            type="button",
        )
    else:
        create_btn = Button(
            Div(
                "+",
                cls="w-8 h-8 rounded-full bg-indigo-600 flex-shrink-0 flex items-center justify-center text-white font-bold text-lg",
            ),
            Div(
                Span(f'Suggest "{q.strip()}"', cls="text-sm text-indigo-300 truncate"),
                Span("Submit for review", cls="text-xs text-slate-500"),
                cls="flex flex-col min-w-0 text-left",
            ),
            cls="flex items-center gap-2 w-full px-2 py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer "
            "border-t border-slate-700 mt-1 pt-1",
            hx_post="/api/annotations/submit",
            hx_vals=_json.dumps(
                {
                    "target_type": "identity",
                    "target_id": source_identity_id,
                    "annotation_type": "name_suggestion",
                    "value": q.strip(),
                    "confidence": "likely",
                    "reason": f"face_tag:{face_id}:new_name",
                }
            ),
            hx_target=f"#tag-results-{safe_face_id}",
            hx_swap="innerHTML",
            type="button",
        )
    # UX-074: "Create New" at top of dropdown (first option, before search results)
    if not results:
        # Show only the create/suggest button with a "no matches" message
        return Div(
            P("No existing matches.", cls="text-slate-500 italic text-xs p-1"),
            create_btn,
            id=results_id,
        )

    return Div(create_btn, *items, id=results_id)


@rt("/api/face/tag")
def post(face_id: str, target_id: str, seq: str = "", sess=None):
    """
    Tag a face with an identity by merging the face's current identity into target.

    This is the one-click merge for Instagram-style face tagging.
    Returns the updated photo view with a success toast.
    Pass seq=1 to stay in sequential "Name These Faces" mode.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    try:
        registry = _main_mod.load_registry()
        photo_registry = _main_mod.load_photo_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Find the source identity (the one the face currently belongs to)
    source_identity = _main_mod.get_identity_for_face(registry, face_id)
    if not source_identity:
        return Response(
            to_xml(_main_mod.toast("Face not found in any identity.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    source_id = source_identity["identity_id"]
    if source_id == target_id:
        return Response(
            to_xml(_main_mod.toast("Face already belongs to this identity.", "info")),
            status_code=200,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Get target name for toast
    try:
        target = registry.get_identity(target_id)
        target_name = ensure_utf8_display(target.get("name")) or f"Identity {target_id[:8]}..."
    except KeyError:
        target_name = f"Identity {target_id[:8]}..."

    # Merge
    result = registry.merge_identities(
        source_id=source_id,
        target_id=target_id,
        user_source="face_tag",
        photo_registry=photo_registry,
    )

    if result["success"]:
        _main_mod.save_registry(registry)
        _main_mod._invalidate_discovery_cache()

        # Find the photo this face is in to re-render the photo view
        photo_id = _main_mod.get_photo_id_for_face(face_id)
        if photo_id:
            # Re-render the photo view to reflect the merge
            # If seq=1, stay in sequential mode for the next unidentified face
            seq_mode = seq == "1"
            photo_content = _main_mod.photo_view_content(
                photo_id, selected_face_id=face_id, is_partial=True, is_admin=True, seq_mode=seq_mode
            )
            oob_toast = Div(
                _main_mod.toast(f"Tagged as {target_name}!", "success"),
                hx_swap_oob="beforeend:#toast-container",
            )
            return (*photo_content, oob_toast)
        else:
            return _main_mod.toast(f"Tagged as {target_name}!", "success")
    else:
        return Response(
            to_xml(_main_mod.toast(f"Cannot tag: {result['reason']}", "warning")),
            status_code=200,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )


@rt("/api/face/quick-action")
def post(identity_id: str, action: str, photo_id: str, sess=None):
    """
    Quick inline action on a face overlay: confirm, skip, or reject.

    Returns a refreshed photo view with updated overlay colors.
    Admin-only.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if action not in ("confirm", "skip", "reject"):
        return Response("Invalid action. Must be confirm, skip, or reject.", status_code=400)

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    state = identity.get("state", "INBOX")
    action_name = action.capitalize()

    try:
        if action == "confirm":
            registry.confirm_identity(identity_id, user_source="quick_action")
        elif action == "skip":
            registry.skip_identity(identity_id, user_source="quick_action")
        elif action == "reject":
            registry.contest_identity(identity_id, user_source="quick_action", reason="Rejected via quick action")
        _notify = None
        if action == "confirm":
            _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
            _notify = {
                "identity_id": identity_id,
                "identity_name": identity.get("name", "Unknown"),
                "user_id": _user.id if _user else None,
                "user_email": _user.email if _user else None,
            }
        _main_mod.save_registry(registry, confirmed_identity_info=_notify)
    except (ValueError, Exception) as e:
        return Response(
            to_xml(_main_mod.toast(f"Cannot {action}: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Re-render the photo view with updated overlay colors
    photo_content = _main_mod.photo_view_content(photo_id, is_partial=True, is_admin=True)
    oob_toast = Div(
        _main_mod.toast(f"{action_name}ed identity!", "success"),
        hx_swap_oob="beforeend:#toast-container",
    )
    return (*photo_content, oob_toast)


@rt("/api/face/create-identity")
def post(face_id: str, name: str, seq: str = "", sess=None):
    """
    Create a named identity for a face by renaming its current identity.

    Used from the tag dropdown "+ Create" button. Renames the face's current
    identity (typically an INBOX singleton) to the user-provided name.
    Pass seq=1 to stay in sequential "Name These Faces" mode.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    name = name.strip()
    if not name:
        return Response(
            to_xml(_main_mod.toast("Name cannot be empty.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    source_identity = _main_mod.get_identity_for_face(registry, face_id)
    if not source_identity:
        return Response(
            to_xml(_main_mod.toast("Face not found in any identity.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    identity_id = source_identity["identity_id"]
    try:
        registry.rename_identity(identity_id, name, user_source="face_tag")
    except (KeyError, ValueError) as e:
        return Response(
            to_xml(_main_mod.toast(f"Could not rename: {e}", "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )
    # Auto-confirm when naming from tag dropdown (tagging = "this IS that person")
    current_state = source_identity.get("state", "INBOX")
    _notify = None
    if current_state in ("INBOX", "PROPOSED", "SKIPPED"):
        try:
            registry.confirm_identity(identity_id, user_source="face_tag")
            _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
            _notify = {
                "identity_id": identity_id,
                "identity_name": name,
                "user_id": _user.id if _user else None,
                "user_email": _user.email if _user else None,
            }
        except Exception:
            pass  # Already confirmed, or other benign error
    _main_mod.save_registry(registry, confirmed_identity_info=_notify)

    # Re-render the photo view to show the new name
    # If seq=1, stay in sequential mode for the next unidentified face
    seq_mode = seq == "1"
    photo_id = _main_mod.get_photo_id_for_face(face_id)
    if photo_id:
        photo_content = _main_mod.photo_view_content(
            photo_id, selected_face_id=face_id, is_partial=True, is_admin=True, seq_mode=seq_mode
        )
        oob_toast = Div(
            _main_mod.toast(f'Named as "{name}"!', "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (*photo_content, oob_toast)
    else:
        return _main_mod.toast(f'Named as "{name}"!', "success")


@rt("/api/identity/{identity_id}/rejected")
def get(identity_id: str):
    """
    Get list of rejected identities for contextual recovery.

    Returns a lightweight list within the sidebar showing blocked identities
    with thumbnail, name, and Unblock button.
    """
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Div(
            P("Identity not found.", cls="text-red-600 text-sm"),
        )

    # Extract rejected identity IDs
    rejected_ids = [
        neg.replace("identity:", "") for neg in identity.get("negative_ids", []) if neg.startswith("identity:")
    ]

    if not rejected_ids:
        return Div(
            P("No hidden matches.", cls="text-slate-400 text-xs italic"),
        )

    crop_files = _main_mod.get_crop_files()
    items = []

    for rejected_id in rejected_ids:
        try:
            rejected_identity = registry.get_identity(rejected_id)
        except KeyError:
            continue

        # UI BOUNDARY: sanitize name for safe rendering
        raw_name = ensure_utf8_display(rejected_identity.get("name"))
        name = raw_name or f"Identity {rejected_id[:8]}..."

        # Resolve thumbnail using anchor faces, then candidates
        thumbnail_img = None
        anchor_face_ids = registry.get_anchor_face_ids(rejected_id)
        for face_id in anchor_face_ids:
            crop_url = _main_mod.resolve_face_image_url(face_id, crop_files)
            if crop_url:
                thumbnail_img = Img(src=crop_url, alt=name, cls="w-8 h-8 object-cover rounded border border-slate-600")
                break

        if thumbnail_img is None:
            candidate_face_ids = registry.get_candidate_face_ids(rejected_id)
            for face_id in candidate_face_ids:
                crop_url = _main_mod.resolve_face_image_url(face_id, crop_files)
                if crop_url:
                    thumbnail_img = Img(
                        src=crop_url, alt=name, cls="w-8 h-8 object-cover rounded border border-slate-600"
                    )
                    break

        if thumbnail_img is None:
            thumbnail_img = Div(cls="w-8 h-8 bg-slate-600 rounded")

        unblock_btn = Button(
            "Unblock",
            cls="px-2 py-0.5 text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/50 rounded hover:bg-indigo-500/20",
            hx_post=f"/api/identity/{identity_id}/unreject/{rejected_id}",
            hx_target=f"#rejected-item-{rejected_id}",
            hx_swap="outerHTML",
            type="button",
        )

        items.append(
            Div(
                thumbnail_img,
                Span(name, cls="text-xs text-slate-300 truncate flex-1 mx-2"),
                unblock_btn,
                id=f"rejected-item-{rejected_id}",
                cls="flex items-center py-1.5 border-b border-slate-700 last:border-0",
            )
        )

    close_list_btn = Button(
        "Hide",
        cls="text-xs text-slate-400 hover:text-slate-300",
        hx_get=f"/api/identity/{identity_id}/rejected/close",
        hx_target=f"#rejected-list-{identity_id}",
        hx_swap="innerHTML",
        type="button",
    )

    return Div(
        Div(
            Span("Hidden Matches", cls="text-xs font-medium text-slate-400"),
            close_list_btn,
            cls="flex items-center justify-between mb-2",
        ),
        Div(*items),
        cls="mt-2 bg-slate-700 rounded border border-slate-600 p-2",
    )


@rt("/api/identity/{identity_id}/rejected/close")
def get(identity_id: str):
    """Close the rejected identities list."""
    return ""


@rt("/api/identity/{source_id}/reject/{target_id}")
def post(source_id: str, target_id: str, sess=None):
    """
    Record that two identities are NOT the same person (D2, D4). Requires admin.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Guard merged identities (UX-038)
    is_merged, canonical_id = _main_mod._check_merged_identity(source_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")
    is_merged, canonical_id = _main_mod._check_merged_identity(target_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    # Validate both identities exist
    try:
        registry.get_identity(source_id)
        registry.get_identity(target_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Record rejection
    registry.reject_identity_pair(source_id, target_id, user_source="web")
    _main_mod.save_registry(registry)

    # AD-150: Fire recalibration hook (best-effort, non-blocking)
    try:
        _main_mod._fire_recalibration_hook("reject", source_id, target_id)
    except Exception:
        pass  # Never block reject on calibration

    # Log the action
    _main_mod.log_user_action(
        "REJECT_IDENTITY",
        source_identity_id=source_id,
        target_identity_id=target_id,
    )

    # Return empty div to replace the neighbor card + toast with undo (D5)
    # The neighbor card will be removed via hx-swap="outerHTML"
    return (
        Div(),  # Empty replacement - card disappears
        _main_mod.toast_with_undo("Marked as 'Not Same Person'", source_id, target_id, "info"),
    )


@rt("/api/identity/{source_id}/unreject/{target_id}")
def post(source_id: str, target_id: str, sess=None):
    """Undo "Not Same Person" rejection (D5). Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Guard merged identities (UX-038)
    is_merged, canonical_id = _main_mod._check_merged_identity(source_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")
    is_merged, canonical_id = _main_mod._check_merged_identity(target_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    # Validate both identities exist
    try:
        registry.get_identity(source_id)
        registry.get_identity(target_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Remove rejection
    registry.unreject_identity_pair(source_id, target_id, user_source="web")
    _main_mod.save_registry(registry)

    # Log the action
    _main_mod.log_user_action(
        "UNREJECT_IDENTITY",
        source_identity_id=source_id,
        target_identity_id=target_id,
    )

    # Return empty div to replace target + OOB toast
    # This handles both: undo from toast (replaces toast) and unblock from list (removes item)
    oob_toast = Div(
        _main_mod.toast("Rejection undone. Identity will reappear in Find Similar.", "success"),
        hx_swap_oob="beforeend:#toast-container",
    )
    return (Div(), oob_toast)


def _name_conflict_modal(target_id: str, source_id: str, details: dict, merge_source: str) -> Div:
    """Render a name conflict resolution modal for two-named merges."""
    a = details["identity_a"]
    b = details["identity_b"]
    return Div(
        Div(cls="absolute inset-0 bg-black/80", **{"_": "on click remove closest .fixed"}),
        Div(
            H3("Name Conflict", cls="text-lg font-bold text-white mb-4"),
            P("Both identities have names. Choose which name to keep:", cls="text-slate-300 mb-4 text-sm"),
            Form(
                Input(type="hidden", name="source", value=merge_source),
                Div(
                    Label(
                        Input(type="radio", name="resolved_name", value=a["name"], cls="mr-2", checked=True),
                        Span(a["name"], cls="font-semibold text-white"),
                        Span(f" ({a['face_count']} faces, {a['state']})", cls="text-slate-400 text-sm"),
                        cls="flex items-center cursor-pointer hover:bg-slate-700 p-2 rounded",
                    ),
                    cls="mb-2",
                ),
                Div(
                    Label(
                        Input(type="radio", name="resolved_name", value=b["name"], cls="mr-2"),
                        Span(b["name"], cls="font-semibold text-white"),
                        Span(f" ({b['face_count']} faces, {b['state']})", cls="text-slate-400 text-sm"),
                        cls="flex items-center cursor-pointer hover:bg-slate-700 p-2 rounded",
                    ),
                    cls="mb-2",
                ),
                Div(
                    Label(
                        Input(
                            type="radio",
                            name="resolved_name",
                            value="__custom__",
                            cls="mr-2",
                            **{"_": "on change show #custom-name-input"},
                        ),
                        Span("Custom name", cls="text-slate-300"),
                        cls="flex items-center cursor-pointer hover:bg-slate-700 p-2 rounded",
                    ),
                    Input(
                        type="text",
                        name="custom_name",
                        id="custom-name-input",
                        placeholder="Enter custom name...",
                        cls="hidden mt-2 w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm",
                    ),
                    cls="mb-4",
                ),
                Div(
                    Button(
                        "Cancel",
                        type="button",
                        cls="px-4 py-2 text-sm text-slate-400 hover:text-white",
                        **{"_": "on click remove closest .fixed"},
                    ),
                    Button(
                        "Merge",
                        type="submit",
                        cls="px-4 py-2 text-sm font-bold bg-blue-600 text-white rounded hover:bg-blue-500",
                    ),
                    cls="flex justify-end gap-3",
                ),
                hx_post=f"/api/identity/{target_id}/merge/{source_id}",
                hx_target=f"#identity-{target_id}",
                hx_swap="outerHTML",
            ),
            cls="bg-slate-800 rounded-lg shadow-2xl w-full max-w-md p-6 relative border border-slate-700",
        ),
        cls="fixed inset-0 flex items-center justify-center p-4 z-[9999]",
    )


def toast_with_merge_undo(message: str, target_id: str) -> Div:
    """Toast notification with Undo button for merge actions."""
    return Div(
        Span("\u2713", cls="mr-2"),
        Span(message, cls="flex-1"),
        Button(
            "Undo",
            cls="ml-3 px-2 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"/api/identity/{target_id}/undo-merge",
            hx_swap="outerHTML",
            hx_target="closest div",
            type="button",
        ),
        cls="px-4 py-3 rounded shadow-lg flex items-center bg-emerald-600 text-white animate-fade-in",
        **{"_": "on load wait 8s then remove me"},
    )


@rt("/api/identity/{target_id}/merge/{source_id}")
def post(
    target_id: str,
    source_id: str,
    source: str = "web",
    resolved_name: str = None,
    custom_name: str = None,
    from_focus: bool = False,
    filter: str = "",
    focus_section: str = "",
    sess=None,
):
    """
    Merge source identity into target identity. Requires admin.

    Enhanced behavior:
    - Auto-corrects merge direction (named identity always survives)
    - Detects name conflicts (both named) and shows resolution modal
    - Records merge_history on target for undo capability
    - Promotes target state if source had higher-trust state
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Guard merged identities (UX-038)
    is_merged, canonical_id = _main_mod._check_merged_identity(target_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")
    is_merged, canonical_id = _main_mod._check_merged_identity(source_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    # Validate both identities exist
    try:
        registry.get_identity(target_id)
        registry.get_identity(source_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Load photo registry for validation
    photo_registry = _main_mod.load_photo_registry()

    # Determine user_source from merge origin
    user_source = source if source in ("web", "manual_search") else "web"

    # Handle custom name from conflict resolution form
    actual_resolved_name = resolved_name
    if resolved_name == "__custom__" and custom_name:
        actual_resolved_name = custom_name.strip()
    elif resolved_name == "__custom__":
        actual_resolved_name = None  # No custom name, will re-trigger conflict

    # Attempt merge (with auto-correction)
    result = registry.merge_identities(
        source_id=source_id,
        target_id=target_id,
        user_source=user_source,
        photo_registry=photo_registry,
        resolved_name=actual_resolved_name,
    )

    if not result["success"]:
        # Handle name conflict -- show resolution modal
        if result["reason"] == "name_conflict":
            return _main_mod._name_conflict_modal(
                target_id,
                source_id,
                result["name_conflict_details"],
                merge_source=source,
            )

        error_messages = {
            "co_occurrence": "Cannot merge: these identities appear in the same photo.",
            "already_merged": "Cannot merge: source identity was already merged.",
        }
        message = error_messages.get(result["reason"], f"Merge failed: {result['reason']}")

        return Response(
            to_xml(_main_mod.toast(message, "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Save and return success
    _main_mod.save_registry(registry)

    # Use the actual target/source from the result (may have been swapped)
    actual_target_id = result["target_id"]
    actual_source_id = result["source_id"]

    # AD-150: Fire recalibration hook (best-effort, non-blocking)
    try:
        _main_mod._fire_recalibration_hook("merge", actual_target_id, actual_source_id)
    except Exception:
        pass  # Never block merge on calibration

    # BE-006: Retarget annotations from source to target
    _main_mod._merge_annotations(actual_source_id, actual_target_id)

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(actual_target_id)
    target_name = ensure_utf8_display(updated_identity.get("name")) or "identity"
    is_unnamed = target_name.startswith("Unidentified") or target_name.startswith("identity")

    # Log the action
    _main_mod.log_user_action(
        "MERGE",
        source_identity_id=actual_source_id,
        target_identity_id=actual_target_id,
        faces_merged=result["faces_merged"],
        direction_swapped=result.get("direction_swapped", False),
    )

    # Build OOB elements to remove absorbed identity from DOM
    oob_elements = [
        Div(id=f"identity-{actual_source_id}", hx_swap_oob="delete"),
        Div(id=f"neighbor-{actual_source_id}", hx_swap_oob="delete"),
        Div(id=f"search-result-{actual_source_id}", hx_swap_oob="delete"),
    ]

    # If direction was swapped, also clean up the original identity cards
    if result.get("direction_swapped"):
        oob_elements.extend(
            [
                Div(id=f"neighbor-{actual_target_id}", hx_swap_oob="delete"),
                Div(id=f"search-result-{actual_target_id}", hx_swap_oob="delete"),
            ]
        )

    # Toast with undo
    merge_toast = _main_mod.toast_with_merge_undo(
        f"Merged {_main_mod._pl(result['faces_merged'], 'face')} into {target_name}.",
        actual_target_id,
    )

    # Post-merge re-evaluation: suggest nearby unmatched faces (ML-005)
    suggestion_panel = _main_mod._post_merge_suggestions(actual_target_id, registry, crop_files)

    # Post-merge guidance banner — encourage naming unnamed identities
    if is_unnamed:
        faces_merged = result["faces_merged"]
        merge_guidance = Div(
            Div(
                Span("Grouped!", cls="font-bold text-emerald-300"),
                Span(f" {_main_mod._pl(faces_merged, 'face')} are now linked together.", cls="text-slate-300"),
                cls="text-sm",
            ),
            Button(
                "Add a name \u2192",
                cls="text-xs text-indigo-400 hover:text-indigo-300 underline mt-1",
                hx_get=f"/api/identity/{actual_target_id}/rename-form",
                hx_target=f"#name-{actual_target_id}",
                hx_swap="outerHTML",
                type="button",
            ),
            cls="bg-emerald-900/20 border border-emerald-500/30 rounded-lg px-4 py-3 mb-3",
            id=f"merge-guidance-{actual_target_id}",
            hx_swap_oob=f"afterbegin:#identity-{actual_target_id}",
        )
    else:
        total_faces = len(updated_identity.get("anchor_ids", [])) + len(updated_identity.get("candidate_ids", []))
        merge_guidance = Div(
            Div(
                Span("Merge complete!", cls="font-bold text-emerald-300"),
                Span(f" {_main_mod._pl(total_faces, 'face')} now confirmed as ", cls="text-slate-300"),
                Span(target_name, cls="font-semibold text-white"),
                Span(".", cls="text-slate-300"),
                cls="text-sm",
            ),
            cls="bg-emerald-900/20 border border-emerald-500/30 rounded-lg px-4 py-3 mb-3",
            id=f"merge-guidance-{actual_target_id}",
            hx_swap_oob=f"afterbegin:#identity-{actual_target_id}",
            **{"_": "on load wait 6s then transition opacity to 0 over 1s then remove me"},
        )

    # If from focus mode, advance to next identity instead of showing browse card
    if from_focus:
        if focus_section == "skipped":
            return (
                _main_mod.get_next_skipped_focus_card(exclude_id=actual_target_id),
                merge_toast,
            )
        return (
            _main_mod.get_next_focus_card(exclude_id=actual_target_id, triage_filter=filter),
            merge_toast,
        )

    return (
        _main_mod.identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        merge_guidance,
        *oob_elements,
        merge_toast,
        suggestion_panel,
    )


def _post_merge_suggestions(target_id: str, registry, crop_files: set, max_suggestions: int = 3):
    """
    After a merge, find nearby unmatched faces and suggest them for review.
    Uses multi-anchor best-linkage (AD-001 compliant). Only shows HIGH+ matches.
    """
    try:
        from core.neighbors import find_nearest_neighbors

        face_data = _main_mod.get_face_data()
        photo_registry = _main_mod.load_photo_registry()
        neighbors = find_nearest_neighbors(target_id, registry, photo_registry, face_data, limit=max_suggestions)
    except Exception:
        return Span()

    # Filter to HIGH confidence or better
    high_matches = [n for n in neighbors if n["distance"] < _main_mod.MATCH_THRESHOLD_HIGH]
    if not high_matches:
        return Span()

    cards = []
    target_identity = registry.get_identity(target_id)
    _target_name = ensure_utf8_display(target_identity.get("name", "")) if target_identity else ""
    for n in high_matches:
        cards.append(_main_mod.neighbor_card(n, target_id, crop_files, show_checkbox=False, target_name=_target_name))

    return Div(
        Div(
            H4("You might also want to review:", cls="text-sm font-medium text-amber-400"),
            P(f"{_main_mod._pl(len(high_matches), 'similar face')} found after merge", cls="text-xs text-slate-400"),
            cls="mb-2",
        ),
        Div(*cards, cls="space-y-2"),
        cls="mt-4 p-4 bg-slate-800/50 border border-amber-500/30 rounded-lg",
        id="post-merge-suggestions",
        hx_swap_oob="beforeend:#toast-container",
    )


@rt("/api/identity/{target_id}/suggest-merge/{source_id}")
def post(target_id: str, source_id: str, confidence: str = "likely", reason: str = "", sess=None):
    """
    Contributor endpoint: suggest merging source into target. Creates a
    merge_suggestion annotation for admin review instead of executing the merge.
    """
    denied = _main_mod._check_contributor(sess)
    if denied:
        return denied

    user = _main_mod.get_current_user(sess)
    submitted_by = user.email if user else "anonymous"

    # Validate both identities exist
    try:
        registry = _main_mod.load_registry()
        registry.get_identity(target_id)
        registry.get_identity(source_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    _main_mod._create_merge_suggestion(
        target_id=target_id,
        source_id=source_id,
        submitted_by=submitted_by,
        confidence=confidence,
        reason=reason,
    )

    _main_mod.log_user_action("SUGGEST_MERGE", target=target_id, source=source_id, user=submitted_by)

    return Response(
        to_xml(_main_mod.toast("Merge suggestion submitted for admin review.", "success")),
        headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
    )


@rt("/api/identity/{identity_id}/undo-merge")
def post(identity_id: str, sess=None):
    """
    Undo the most recent merge on an identity. Requires admin.

    Reads merge_history, restores the source identity, removes
    merged faces from target.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Validate identity exists
    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Attempt undo
    result = registry.undo_merge(identity_id, user_source="web")

    if not result["success"]:
        error_messages = {
            "no_merge_history": "Nothing to undo.",
            "source_not_found": "Cannot undo: source identity no longer exists.",
            "target_is_merged": "Cannot undo: this identity has been merged into another.",
        }
        message = error_messages.get(result["reason"], f"Undo failed: {result['reason']}")
        return Response(
            to_xml(_main_mod.toast(message, "warning")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    _main_mod.save_registry(registry)

    _main_mod.log_user_action(
        "UNDO_MERGE",
        target_identity_id=identity_id,
        restored_source_id=result["source_id"],
        faces_removed=result["faces_removed"],
    )

    return _main_mod.toast(f"Merge undone. {_main_mod._pl(result['faces_removed'], 'face')} restored.", "success")


@rt("/api/identity/{identity_id}/bulk-merge")
def post(identity_id: str, bulk_ids: list[str] = None, sess=None):
    """
    Bulk merge multiple identities into one target. Requires admin.

    Merges each selected identity into the target one by one.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not bulk_ids:
        return _main_mod.toast("No identities selected.", "warning")

    # Ensure bulk_ids is a list (single value comes as string)
    if isinstance(bulk_ids, str):
        bulk_ids = [bulk_ids]

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Guard merged target identity (UX-038)
    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    photo_registry = _main_mod.load_photo_registry()

    merged_count = 0
    total_faces = 0
    errors = []

    for source_id in bulk_ids:
        try:
            result = registry.merge_identities(
                source_id=source_id,
                target_id=identity_id,
                user_source="web",
                photo_registry=photo_registry,
            )
            if result["success"]:
                merged_count += 1
                total_faces += result["faces_merged"]
            else:
                errors.append(f"{source_id[:8]}: {result['reason']}")
        except Exception as e:
            errors.append(f"{source_id[:8]}: {str(e)}")

    if merged_count > 0:
        _main_mod.save_registry(registry)

    if errors:
        return _main_mod.toast(
            f"Merged {merged_count} identities ({total_faces} faces). {len(errors)} failed.", "warning"
        )

    return _main_mod.toast(f"Merged {merged_count} identities ({total_faces} faces).", "success")


@rt("/api/identity/{identity_id}/bulk-reject")
def post(identity_id: str, bulk_ids: list[str] = None, sess=None):
    """
    Bulk mark multiple identities as Not Same. Requires admin.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not bulk_ids:
        return _main_mod.toast("No identities selected.", "warning")

    # Ensure bulk_ids is a list
    if isinstance(bulk_ids, str):
        bulk_ids = [bulk_ids]

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Guard merged identity (UX-038)
    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    rejected_count = 0
    for target_id in bulk_ids:
        try:
            registry.reject_identity_pair(identity_id, target_id, user_source="web")
            rejected_count += 1
        except Exception:
            pass

    if rejected_count > 0:
        _main_mod.save_registry(registry)

    return _main_mod.toast(f"Marked {rejected_count} identities as 'Not Same'.", "info")


@rt("/api/identity/{identity_id}/faces")
def get(identity_id: str, sort: str = "date", page: int = 0):
    """
    Get faces for an identity with optional sorting and pagination.

    Query params:
    - sort: "date" (default) or "outlier"
    - page: 0-indexed page number (FACES_PER_PAGE items per page)

    Returns HTML partial with face cards and pagination controls.
    """
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    crop_files = _main_mod.get_crop_files()
    face_data = _main_mod.get_face_data()

    # Get all face entries in requested order
    if sort == "outlier":
        from core.neighbors import sort_faces_by_outlier_score

        sorted_faces = sort_faces_by_outlier_score(identity_id, registry, face_data)
        all_entries = [face_id for face_id, _ in sorted_faces]
    else:
        all_entries = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])

    total_faces = len(all_entries)
    can_detach = total_faces > 1

    # Paginate
    start = page * _main_mod.FACES_PER_PAGE
    end = start + _main_mod.FACES_PER_PAGE
    page_entries = all_entries[start:end]

    # Build face cards
    if sort == "outlier":
        # For outlier sort, entries are plain face_id strings
        cards = []
        for face_id in page_entries:
            crop_url = _main_mod.resolve_face_image_url(face_id, crop_files)
            if crop_url:
                photo_id = _main_mod.get_photo_id_for_face(face_id)
                cards.append(
                    _main_mod.face_card(
                        face_id=face_id,
                        crop_url=crop_url,
                        photo_id=photo_id,
                        identity_id=identity_id,
                        show_detach=can_detach,
                    )
                )
            else:
                cards.append(
                    Div(
                        Div(
                            Span("?", cls="text-4xl text-slate-500"),
                            cls="w-full aspect-square bg-slate-700 border border-slate-600 flex items-center justify-center",
                        ),
                        P("Image unavailable", cls="text-xs text-slate-400 mt-1"),
                        P(f"ID: {face_id[:12]}...", cls="text-xs font-data text-slate-500"),
                        cls="face-card",
                        id=_main_mod.make_css_id(face_id),
                    )
                )
    else:
        cards = _main_mod._build_face_cards_for_entries(page_entries, crop_files, identity_id, can_detach)

    pagination = _main_mod._face_pagination_controls(identity_id, page, total_faces, sort)

    return Div(
        Div(
            *cards,
            cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3",
        ),
        pagination,
        id=f"faces-{identity_id}",
    )


# =============================================================================
# ROUTES - RENAME IDENTITY
# =============================================================================


@rt("/api/identity/{identity_id}/photos")
def get(identity_id: str, index: int = 0):
    """Get a single photo for the lightbox, with face overlays and navigation."""
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return P("Identity not found", cls="text-red-400")

    all_face_entries = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    if not all_face_entries:
        return P("No faces for this identity", cls="text-slate-400")

    index = max(0, min(index, len(all_face_entries) - 1))
    total = len(all_face_entries)

    face_entry = all_face_entries[index]
    face_id = face_entry if isinstance(face_entry, str) else face_entry.get("face_id", "")

    pid = _main_mod.get_photo_id_for_face(face_id)
    if not pid:
        return P("Photo not found for this face", cls="text-slate-400")
    photo = _main_mod.get_photo_metadata(pid)
    if not photo:
        return P("Photo metadata not found", cls="text-slate-400")

    width, height = _main_mod.get_photo_dimensions(photo["filename"])
    has_dimensions = width > 0 and height > 0

    face_overlays = []
    identity_name = ensure_utf8_display(identity.get("name")) or "Unknown"
    if has_dimensions:
        for fd in photo["faces"]:
            fid = fd["face_id"]
            x1, y1, x2, y2 = fd["bbox"]
            lp = (x1 / width) * 100
            tp = (y1 / height) * 100
            wp = ((x2 - x1) / width) * 100
            hp = ((y2 - y1) / height) * 100
            fi = _main_mod.get_identity_for_face(registry, fid)
            is_t = fi and fi["identity_id"] == identity_id
            if is_t:
                oc = "absolute border-2 border-amber-500 bg-amber-500/20 cursor-pointer"
                lb = Span(
                    identity_name,
                    cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-amber-600 text-white text-xs px-2 py-0.5 rounded whitespace-nowrap pointer-events-none",
                )
            else:
                dn = ensure_utf8_display(fi.get("name", "")) if fi else ""
                oc = "absolute border border-emerald-500/50 bg-emerald-500/5 group cursor-pointer hover:bg-emerald-500/15"
                lb = (
                    Span(
                        dn or "Unknown",
                        cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-xs px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none",
                    )
                    if dn
                    else None
                )

            # Determine the correct section for navigation based on identity state
            fi_id = fi["identity_id"] if fi else None
            fi_section = _section_for_state(fi.get("state", "INBOX")) if fi else "to_review"

            # Click handler: navigate to the identity's face card in the correct section
            click_script = None
            if fi_id:
                click_script = (
                    f"on click halt the event's bubbling "
                    f"then add .hidden to #photo-modal "
                    f"then go to url '/?section={fi_section}&view=browse#identity-{fi_id}'"
                )

            face_overlays.append(
                Div(
                    lb,
                    cls=oc,
                    style=f"left: {lp:.2f}%; top: {tp:.2f}%; width: {wp:.2f}%; height: {hp:.2f}%;",
                    **{"_": click_script} if click_script else {},
                )
            )

    # Lightbox prev/next buttons use data-action for event delegation.
    # The global handler reads data-action and hx-get to dispatch navigation.
    prev_btn = (
        Button(
            Span("\u25c0", cls="text-xl"),
            cls="absolute left-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white w-12 h-12 rounded-full flex items-center justify-center transition-colors z-10",
            hx_get=f"/api/identity/{identity_id}/photos?index={index - 1}",
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            type="button",
            data_action="lightbox-prev",
        )
        if index > 0
        else None
    )
    next_btn = (
        Button(
            Span("\u25b6", cls="text-xl"),
            cls="absolute right-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white w-12 h-12 rounded-full flex items-center justify-center transition-colors z-10",
            hx_get=f"/api/identity/{identity_id}/photos?index={index + 1}",
            hx_target="#photo-modal-content",
            hx_swap="innerHTML",
            type="button",
            data_action="lightbox-next",
        )
        if index < total - 1
        else None
    )

    # Touch swipe script only — keyboard is handled by global event delegation
    nav_script = Script(
        f"""(function(){{var el=document.getElementById('lightbox-photo-container');if(!el)return;var sx=0;el.addEventListener('touchstart',function(e){{sx=e.touches[0].clientX}});el.addEventListener('touchend',function(e){{var d=e.changedTouches[0].clientX-sx;if(Math.abs(d)>50){{if(d>0&&{index}>0)htmx.ajax('GET','/api/identity/{identity_id}/photos?index={index - 1}',{{target:'#photo-modal-content',swap:'innerHTML'}});else if(d<0&&{index}<{total - 1})htmx.ajax('GET','/api/identity/{identity_id}/photos?index={index + 1}',{{target:'#photo-modal-content',swap:'innerHTML'}})}}}});}})();"""
    )

    return Div(
        Div(
            Img(src=photo_url(photo["filename"]), alt=photo["filename"], cls="max-h-[80vh] max-w-full object-contain"),
            *face_overlays,
            prev_btn,
            next_btn,
            cls="relative inline-block",
            id="lightbox-photo-container",
        ),
        Div(
            Span(f"{index + 1} / {total}", cls="text-white font-medium"),
            Span(f" -- {photo['filename']}", cls="text-slate-400 text-sm ml-2"),
            Span(identity_name, cls="text-amber-400 text-sm ml-4"),
            cls="mt-3 text-center",
        ),
        nav_script,
        cls="flex flex-col items-center",
    )


@rt("/api/identity/{identity_id}/rename-form")
def get(identity_id: str):
    """
    Return inline edit form for renaming an identity.
    Replaces the name display via HTMX.
    """
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    # UI BOUNDARY: sanitize name for safe rendering in input value
    current_name = ensure_utf8_display(identity.get("name")) or ""

    return Form(
        Input(
            name="name",
            value=current_name,
            placeholder="Enter name...",
            cls="border border-slate-600 bg-slate-700 text-slate-200 rounded px-2 py-1 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-400",
            autofocus=True,
        ),
        Button(
            "Save",
            type="submit",
            cls="ml-2 bg-emerald-600 text-white px-2 py-1 rounded text-sm hover:bg-emerald-500",
        ),
        Button(
            "Cancel",
            type="button",
            hx_get=f"/api/identity/{identity_id}/name-display",
            hx_target=f"#name-{identity_id}",
            hx_swap="outerHTML",
            cls="ml-1 text-slate-400 hover:text-slate-300 text-sm underline",
        ),
        hx_post=f"/api/identity/{identity_id}/rename",
        hx_target=f"#name-{identity_id}",
        hx_swap="outerHTML",
        id=f"name-{identity_id}",
        cls="flex items-center",
    )


@rt("/api/identity/{identity_id}/name-display")
def get(identity_id: str):
    """
    Return the name display component (for cancel button).
    """
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    return _main_mod.name_display(identity_id, identity.get("name"))


@rt("/api/identity/{identity_id}/rename")
def post(identity_id: str, name: str = "", sess=None):
    """Rename an identity. Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Validate name
    name = name.strip() if name else ""
    if not name:
        return Response(
            to_xml(_main_mod.toast("Name cannot be empty.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        previous_name = registry.rename_identity(identity_id, name, user_source="web")
        _main_mod.save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )
    except Exception as e:
        return Response(
            to_xml(_main_mod.toast(f"Rename failed: {str(e)}", "error")),
            status_code=500,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Return updated name display + success toast
    return (
        _main_mod.name_display(identity_id, name),
        _main_mod.toast(f"Renamed to '{name}'", "success"),
    )


# =============================================================================
# ROUTES - IDENTITY NOTES
# =============================================================================


@rt("/api/identity/{identity_id}/notes")
def get(identity_id: str):
    """Get notes for an identity and show the notes panel."""
    try:
        registry = _main_mod.load_registry()
        notes = registry.get_notes(identity_id)
    except KeyError:
        return P("Identity not found.", cls="text-red-400 text-sm")

    note_items = [
        Div(
            P(n["text"], cls="text-sm text-slate-200"),
            Div(
                Span(n.get("author", ""), cls="text-xs text-slate-500"),
                Span(n.get("timestamp", "")[:10], cls="text-xs text-slate-500 ml-2"),
                cls="flex items-center mt-1",
            ),
            cls="p-2 bg-slate-700 rounded mb-1",
        )
        for n in reversed(notes)  # Newest first
    ]

    return Div(
        H5("Notes", cls="text-sm font-semibold text-slate-300 mb-2"),
        Div(*note_items) if note_items else P("No notes yet.", cls="text-xs text-slate-500 italic"),
        # Add note form
        Form(
            Input(
                type="text",
                name="text",
                placeholder="Add a note...",
                cls="w-full px-2 py-1.5 text-sm bg-slate-800 border border-slate-600 text-white rounded "
                "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500",
                required=True,
            ),
            Button(
                "Add",
                type="submit",
                cls="mt-1 px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
            ),
            hx_post=f"/api/identity/{identity_id}/notes",
            hx_target=f"#notes-{identity_id}",
            hx_swap="innerHTML",
            cls="mt-2",
        ),
        id=f"notes-{identity_id}",
    )


@rt("/api/identity/{identity_id}/notes")
def post(identity_id: str, text: str = "", sess=None):
    """Add a note to an identity. Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    text = text.strip()
    if not text:
        return _main_mod.toast("Note cannot be empty.", "warning")

    user_email = ""
    if sess:
        user = _main_mod.get_current_user(sess)
        if user:
            user_email = user.email

    try:
        registry = _main_mod.load_registry()
        registry.add_note(identity_id, text, author=user_email)
        _main_mod.save_registry(registry)
    except KeyError:
        return _main_mod.toast("Identity not found.", "error")
    except Exception as e:
        return _main_mod.toast(f"Failed to add note: {e}", "error")

    # Re-render the notes panel
    notes = registry.get_notes(identity_id)
    note_items = [
        Div(
            P(n["text"], cls="text-sm text-slate-200"),
            Div(
                Span(n.get("author", ""), cls="text-xs text-slate-500"),
                Span(n.get("timestamp", "")[:10], cls="text-xs text-slate-500 ml-2"),
                cls="flex items-center mt-1",
            ),
            cls="p-2 bg-slate-700 rounded mb-1",
        )
        for n in reversed(notes)
    ]

    return Div(
        H5("Notes", cls="text-sm font-semibold text-slate-300 mb-2"),
        Div(*note_items),
        Form(
            Input(
                type="text",
                name="text",
                placeholder="Add a note...",
                cls="w-full px-2 py-1.5 text-sm bg-slate-800 border border-slate-600 text-white rounded "
                "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500",
                required=True,
            ),
            Button(
                "Add",
                type="submit",
                cls="mt-1 px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
            ),
            hx_post=f"/api/identity/{identity_id}/notes",
            hx_target=f"#notes-{identity_id}",
            hx_swap="innerHTML",
            cls="mt-2",
        ),
        id=f"notes-{identity_id}",
    )


@rt("/api/identity/{identity_id}/metadata-form")
def get(identity_id: str, sess=None):
    """Return an inline metadata edit form for an identity."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return _main_mod.toast("Identity not found.", "error")

    _input_cls = (
        "w-full px-2 py-1.5 text-sm bg-slate-700 border border-slate-600 text-white rounded "
        "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500"
    )

    return Div(
        Form(
            Div(
                Div(
                    Label("Display Name", cls="text-xs text-slate-400"),
                    Input(
                        type="text",
                        name="display_name",
                        value=identity.get("name", ""),
                        placeholder="e.g. Isaac Cohen",
                        cls=_input_cls,
                    ),
                    cls="flex-1",
                ),
                cls="mb-1",
            ),
            Div(
                Div(
                    Label("Maiden Name", cls="text-xs text-slate-400"),
                    Input(
                        type="text",
                        name="maiden_name",
                        value=identity.get("maiden_name", ""),
                        placeholder="née ...",
                        cls=_input_cls,
                    ),
                    cls="flex-1",
                ),
                Div(
                    Label("Qualifier", cls="text-xs text-slate-400"),
                    Input(
                        type="text",
                        name="generation_qualifier",
                        value=identity.get("generation_qualifier", ""),
                        placeholder="e.g. Sr., Jr.",
                        cls=_input_cls,
                    ),
                    cls="w-24",
                ),
                cls="flex gap-2",
            ),
            Div(
                Div(
                    Label("Birth Year", cls="text-xs text-slate-400"),
                    Input(
                        type="text",
                        name="birth_year",
                        value=str(identity.get("birth_year", "")),
                        placeholder="e.g. 1920",
                        cls=_input_cls,
                    ),
                    cls="w-24",
                ),
                Div(
                    Label("Death Year", cls="text-xs text-slate-400"),
                    Input(
                        type="text",
                        name="death_year",
                        value=str(identity.get("death_year", "")),
                        placeholder="e.g. 1995",
                        cls=_input_cls,
                    ),
                    cls="w-24",
                ),
                Div(
                    Label("Birthplace", cls="text-xs text-slate-400"),
                    Input(
                        type="text",
                        name="birth_place",
                        value=identity.get("birth_place", ""),
                        placeholder="e.g. Rhodes, Greece",
                        cls=_input_cls,
                        list="places-list",
                    ),
                    cls="flex-1",
                ),
                Div(
                    Label("Death Place", cls="text-xs text-slate-400"),
                    Input(
                        type="text",
                        name="death_place",
                        value=identity.get("death_place", ""),
                        placeholder="e.g. Auschwitz",
                        cls=_input_cls,
                        list="places-list",
                    ),
                    cls="flex-1",
                ),
                cls="flex gap-2 flex-wrap",
            ),
            Div(
                Label("Relationships", cls="text-xs text-slate-400"),
                Input(
                    type="text",
                    name="relationship_notes",
                    value=identity.get("relationship_notes", ""),
                    placeholder="e.g. Daughter of X & Y, married to Z",
                    cls=_input_cls,
                ),
            ),
            Div(
                Label("Bio", cls="text-xs text-slate-400"),
                Textarea(
                    identity.get("bio", ""),
                    name="bio",
                    rows="2",
                    placeholder="Biographical notes...",
                    cls=_input_cls + " resize-y",
                ),
            ),
            Div(
                Button(
                    "Save",
                    type="submit",
                    cls="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
                ),
                Button(
                    "Cancel",
                    type="button",
                    cls="px-3 py-1.5 text-xs bg-slate-600 text-slate-300 rounded hover:bg-slate-500",
                    hx_get=f"/api/identity/{identity_id}/metadata-display",
                    hx_target=f"#metadata-{identity_id}",
                    hx_swap="innerHTML",
                ),
                cls="flex gap-2 mt-1",
            ),
            hx_post=f"/api/identity/{identity_id}/metadata",
            hx_target=f"#metadata-{identity_id}",
            hx_swap="innerHTML",
            cls="space-y-2",
        ),
        _main_mod._place_datalist(),
        id=f"metadata-{identity_id}",
    )


@rt("/api/identity/{identity_id}/metadata-display")
def get(identity_id: str, sess=None):
    """Return the metadata display (non-form) for an identity."""
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Span()
    is_admin = not _main_mod._check_admin(sess)
    return _main_mod._identity_metadata_display(identity, is_admin=is_admin)


@rt("/api/identity/{identity_id}/metadata")
def post(
    identity_id: str,
    display_name: str = "",
    birth_year: str = "",
    death_year: str = "",
    birth_place: str = "",
    death_place: str = "",
    maiden_name: str = "",
    generation_qualifier: str = "",
    relationship_notes: str = "",
    bio: str = "",
    sess=None,
):
    """Update identity metadata. Admin-only (BE-011)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    # Handle display name rename separately (it's stored as identity "name", not metadata)
    renamed = False
    if display_name.strip():
        try:
            registry = _main_mod.load_registry()
            registry.rename_identity(identity_id, display_name.strip(), user_source="admin_web")
            _main_mod.save_registry(registry)
            renamed = True
        except KeyError:
            return _main_mod.toast("Identity not found.", "error")

    metadata = {}
    if birth_year.strip():
        try:
            metadata["birth_year"] = int(birth_year.strip())
        except ValueError:
            pass
    if death_year.strip():
        try:
            metadata["death_year"] = int(death_year.strip())
        except ValueError:
            pass
    if birth_place.strip():
        metadata["birth_place"] = birth_place.strip()
    if death_place.strip():
        metadata["death_place"] = death_place.strip()
    if maiden_name.strip():
        metadata["maiden_name"] = maiden_name.strip()
    if generation_qualifier.strip():
        metadata["generation_qualifier"] = generation_qualifier.strip()
    if relationship_notes.strip():
        metadata["relationship_notes"] = relationship_notes.strip()
    if bio.strip():
        metadata["bio"] = bio.strip()

    if not metadata and not renamed:
        return _main_mod.toast("No changes provided.", "warning")

    try:
        registry = _main_mod.load_registry() if not renamed else registry
        if metadata:
            registry.set_metadata(identity_id, metadata, user_source="admin_web")
            _main_mod.save_registry(registry)
        # Return updated display with success toast
        identity = registry.get_identity(identity_id)
        display = _main_mod._identity_metadata_display(identity, is_admin=True)
        changes = len(metadata) + (1 if renamed else 0)
        msg = f"Updated ({changes} field{'s' if changes != 1 else ''})."
        if renamed:
            msg = f'Name set to "{display_name.strip()}". ' + msg
        oob_toast = Div(
            _main_mod.toast(msg, "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        # Also update the name display header if renamed
        oob_parts = [display, oob_toast]
        if renamed:
            updated_name = identity.get("name", "Unknown")
            gen_qual = identity.get("generation_qualifier", "")
            oob_name = Div(
                _main_mod.name_display(identity_id, updated_name, is_admin=True, generation_qualifier=gen_qual),
                hx_swap_oob=f"outerHTML:#name-{identity_id}",
            )
            oob_parts.append(oob_name)
        return tuple(oob_parts)
    except KeyError:
        return _main_mod.toast("Identity not found.", "error")


# =============================================================================
# ML BIRTH YEAR REVIEW ENDPOINTS (Gatekeeper Pattern — AD-097)
# =============================================================================


@rt("/api/photo/{photo_id}/metadata")
def post(
    photo_id: str,
    date_taken: str = "",
    location: str = "",
    caption: str = "",
    occasion: str = "",
    donor: str = "",
    notes: str = "",
    back_image: str = "",
    back_transcription: str = "",
    sess=None,
):
    """Update photo metadata. Admin-only (BE-012)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    metadata = {}
    if date_taken.strip():
        metadata["date_taken"] = date_taken.strip()
    if location.strip():
        metadata["location"] = location.strip()
    if caption.strip():
        metadata["caption"] = caption.strip()
    if occasion.strip():
        metadata["occasion"] = occasion.strip()
    if donor.strip():
        metadata["donor"] = donor.strip()
    if notes.strip():
        metadata["notes"] = notes.strip()
    if back_image.strip():
        metadata["back_image"] = back_image.strip()
    if back_transcription.strip():
        metadata["back_transcription"] = back_transcription.strip()

    if not metadata:
        return _main_mod.toast("No metadata provided.", "warning")

    photo_registry = _main_mod.load_photo_registry()
    if not photo_registry.set_metadata(photo_id, metadata):
        return _main_mod.toast("Photo not found.", "error")
    _main_mod.save_photo_registry(photo_registry)

    return _main_mod.toast(f"Photo metadata updated ({len(metadata)} field(s)).", "success")


@rt("/api/photo/{photo_id}/back-image")
async def post(photo_id: str, file: UploadFile = None, back_transcription: str = "", sess=None):
    """Upload a back image for a photo and optionally add transcription. Admin-only."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not file or not file.filename:
        return _main_mod.toast("No file selected.", "warning")

    # Validate file type
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return _main_mod.toast(f"File type '{ext}' not allowed. Use .jpg, .png, or .webp.", "error")

    # Read file content
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        return _main_mod.toast("File too large. Maximum is 50 MB.", "error")

    # Generate back image filename: {original_stem}_back{ext}
    photo_registry = _main_mod.load_photo_registry()
    photo = photo_registry.get_photo(photo_id)
    if not photo:
        return _main_mod.toast("Photo not found.", "error")

    original_path = photo.get("path", photo.get("filename", ""))
    original_stem = Path(original_path).stem
    back_filename = f"{original_stem}_back{ext}"

    # Save to raw_photos/ (local dev) or staging (production)
    raw_photos_dir = Path("raw_photos")
    if raw_photos_dir.exists():
        save_path = raw_photos_dir / back_filename
        save_path.write_bytes(content)
    else:
        # Staging for production upload
        staging_dir = _main_mod.data_path / "staging" / "back_images"
        staging_dir.mkdir(parents=True, exist_ok=True)
        save_path = staging_dir / back_filename
        save_path.write_bytes(content)

    # Update photo metadata
    metadata = {"back_image": back_filename}
    if back_transcription.strip():
        metadata["back_transcription"] = back_transcription.strip()
    photo_registry.set_metadata(photo_id, metadata)
    _main_mod.save_photo_registry(photo_registry)

    return Div(
        P(f"Back image uploaded: {back_filename}", cls="text-emerald-400 text-sm"),
        P("The 'Turn Over' button is now available on this photo.", cls="text-slate-400 text-xs mt-1"),
        cls="p-2",
    )


@rt("/api/photo/{photo_id}/back-transcription")
def post(photo_id: str, back_transcription: str = "", sess=None):
    """Update the back transcription for a photo. Admin-only."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not back_transcription.strip():
        return _main_mod.toast("No transcription provided.", "warning")

    photo_registry = _main_mod.load_photo_registry()
    if not photo_registry.set_metadata(photo_id, {"back_transcription": back_transcription.strip()}):
        return _main_mod.toast("Photo not found.", "error")
    _main_mod.save_photo_registry(photo_registry)

    return _main_mod.toast("Transcription saved.", "success")


@rt("/api/photo/{photo_id}/transform")
def post(photo_id: str, transform: str = "", field: str = "transform", sess=None):
    """Set non-destructive image transformation. Admin-only.

    transform: The transform to apply (e.g., 'rotate:90', 'flipH', 'reset')
    field: 'transform' (front image) or 'back_transform' (back image)
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if field not in {"transform", "back_transform"}:
        return _main_mod.toast("Invalid field.", "error")

    photo_registry = _main_mod.load_photo_registry()
    photo = photo_registry.get_photo(photo_id)
    if not photo:
        return _main_mod.toast("Photo not found.", "error")

    if transform == "reset":
        new_transform = ""
    else:
        # Append to existing transform (or start fresh)
        existing = photo.get(field, "")
        if existing:
            new_transform = f"{existing},{transform}"
        else:
            new_transform = transform

    photo_registry.set_metadata(photo_id, {field: new_transform})
    _main_mod.save_photo_registry(photo_registry)

    # Return the CSS transform for live preview
    css_transform = _main_mod.parse_transform_to_css(new_transform)
    css_filter = _main_mod.parse_transform_to_filter(new_transform)
    return Div(
        P(f"Transform: {new_transform}" if new_transform else "Transform reset.", cls="text-xs text-slate-400"),
        Script(f"""
            var img = document.querySelector('.photo-hero, .photo-flip-front img');
            if (img) {{
                img.style.transform = '{css_transform}';
                img.style.filter = '{css_filter}';
            }}
        """)
        if css_transform or css_filter or transform == "reset"
        else None,
        cls="mt-1",
    )


@rt("/api/photos/bulk-update-source")
def post(photo_ids: str = "[]", collection: str = "", source: str = "", source_url: str = "", sess=None):
    """Bulk update collection/source/source_url for multiple photos. Admin-only."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not collection.strip() and not source.strip() and not source_url.strip():
        return _main_mod.toast("Please provide collection, source, or source URL.", "warning")

    try:
        ids = json.loads(photo_ids)
    except (json.JSONDecodeError, TypeError):
        return _main_mod.toast("Invalid photo selection.", "error")

    if not ids:
        return _main_mod.toast("No photos selected.", "warning")

    photo_registry = _main_mod.load_photo_registry()
    updated = 0
    for pid in ids:
        if collection.strip():
            photo_registry.set_collection(pid, collection.strip())
        if source.strip():
            photo_registry.set_source(pid, source.strip())
        if source_url.strip():
            photo_registry.set_source_url(pid, source_url.strip())
        updated += 1
    _main_mod.save_photo_registry(photo_registry)

    # Invalidate photo cache so grid reflects changes
    _main_mod._photo_cache = None
    _main_mod._photo_id_aliases = None

    fields = []
    if collection.strip():
        fields.append(f"collection={collection.strip()}")
    if source.strip():
        fields.append(f"source={source.strip()}")
    if source_url.strip():
        fields.append("source_url")

    _main_mod.log_user_action("BULK_UPDATE_METADATA", count=updated, fields=", ".join(fields))

    return _main_mod.toast(f"Updated {updated} photo(s): {', '.join(fields)}.", "success")


# =============================================================================
# ROUTES - DETACH FACE
# =============================================================================


@rt("/api/face/{face_id:path}/detach")
def post(face_id: str, sess=None):
    """Detach a face from its identity into a new identity. Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Find identity containing this face
    identity = _main_mod.get_identity_for_face(registry, face_id)
    if not identity:
        return Response(
            to_xml(_main_mod.toast("Face not found in any identity.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    identity_id = identity["identity_id"]

    # Attempt detach
    result = registry.detach_face(
        identity_id=identity_id,
        face_id=face_id,
        user_source="web",
    )

    if not result["success"]:
        error_messages = {
            "only_face": "Cannot detach: this is the only face in the identity.",
            "face_not_found": "Face not found in identity.",
        }
        message = error_messages.get(result["reason"], f"Detach failed: {result['reason']}")

        return Response(
            to_xml(_main_mod.toast(message, "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Save registry
    _main_mod.save_registry(registry)

    # Log the action
    _main_mod.log_user_action(
        "DETACH",
        face_id=face_id,
        from_identity_id=identity_id,
        to_identity_id=result["to_identity_id"],
    )

    # 1. Get crop files for rendering
    crop_files = _main_mod.get_crop_files()

    # 2. Render the NEW identity card (detached face's new home)
    new_identity = registry.get_identity(result["to_identity_id"])
    new_card_html = _main_mod.identity_card(
        new_identity,
        crop_files,
        lane_color="amber",  # New identities are PROPOSED
        show_actions=True,
    )

    # 3. Render the UPDATED old identity card (with correct face count)
    old_identity = registry.get_identity(identity_id)
    state_colors = {
        "INBOX": "blue",
        "PROPOSED": "amber",
        "CONFIRMED": "emerald",
        "CONTESTED": "red",
    }
    old_lane_color = state_colors.get(old_identity["state"], "stone")
    old_card_html = _main_mod.identity_card(
        old_identity,
        crop_files,
        lane_color=old_lane_color,
        show_actions=old_identity["state"] in ("INBOX", "PROPOSED"),
    )

    return (
        # A. Replace OLD identity card with updated face count
        Div(old_card_html, id=f"identity-{identity_id}", hx_swap_oob="outerHTML"),
        # B. Insert the new identity card at the top of the Proposed lane
        Div(new_card_html, hx_swap_oob="afterbegin:#proposed-lane"),
        # C. Success toast
        _main_mod.toast("Face moved to its own identity. Use Merge to combine them back.", "success"),
    )


# --- INSTRUMENTATION SKIP ENDPOINT ---
@rt("/api/identity/{id}/skip")
def post(id: str, sess=None):
    """Log the skip action. Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    registry = _main_mod.load_registry()
    is_merged, canonical_id = _main_mod._check_merged_identity(id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")
    _main_mod.get_event_recorder().record("SKIP", {"identity_id": id})
    # No return needed as this is fire-and-forget for logging
    # The UI handles the DOM move client-side
    return Response(status_code=200)


# -------------------------------------


# -------------------------------------


# =============================================================================
# ROUTES - INBOX INGESTION (extracted to app/upload_routes.py)
# =============================================================================


# =============================================================================
# ROUTES - ADMIN PENDING UPLOADS REVIEW
# =============================================================================


# =============================================================================
# ROUTES - DISCOVERIES (extracted to app/discoveries_routes.py)
# =============================================================================


# =============================================================================
# ROUTES - INBOX REVIEW (existing)
# =============================================================================


@rt("/inbox/{identity_id}/review")
def post(identity_id: str, sess=None):
    """Move identity from INBOX to PROPOSED state. Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        registry.move_to_proposed(identity_id, user_source="web")
        _main_mod.save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now PROPOSED, with full action buttons)
    return (
        _main_mod.identity_card(updated_identity, crop_files, lane_color="amber", show_actions=True),
        _main_mod.toast("Moved to Proposed for review.", "success"),
    )


@rt("/inbox/{identity_id}/confirm")
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
    """Confirm identity from INBOX state (INBOX -> CONFIRMED). Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        _identity = registry.get_identity(identity_id)
        registry.confirm_identity(identity_id, user_source="web_review")
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _main_mod.save_registry(
            registry,
            confirmed_identity_info={
                "identity_id": identity_id,
                "identity_name": _identity.get("name", "Unknown"),
                "user_id": _user.id if _user else None,
                "user_email": _user.email if _user else None,
            },
        )
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            _main_mod.get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
            _main_mod.toast("Identity confirmed.", "success"),
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now CONFIRMED)
    return (
        _main_mod.identity_card(updated_identity, crop_files, lane_color="emerald", show_actions=False),
        _main_mod.toast("Identity confirmed.", "success"),
    )


@rt("/inbox/{identity_id}/reject")
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
    """Reject identity from INBOX state (INBOX -> REJECTED). Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        registry.reject_identity(identity_id, user_source="web_review")
        _main_mod.save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            _main_mod.get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
            _main_mod.toast("Identity rejected.", "success"),
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now REJECTED)
    return (
        _main_mod.identity_card(updated_identity, crop_files, lane_color="rose", show_actions=False),
        _main_mod.toast("Identity rejected.", "success"),
    )


@rt("/identity/{identity_id}/skip")
def post(identity_id: str, from_focus: bool = False, filter: str = "", sess=None):
    """
    Skip identity (defer for later review). Requires admin.

    Works from INBOX or PROPOSED state -> SKIPPED.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        registry.skip_identity(identity_id, user_source="web_review")
        _main_mod.save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # If from focus mode, return the next focus card
    if from_focus:
        return (
            _main_mod.get_next_focus_card(exclude_id=identity_id, triage_filter=filter),
            _main_mod.toast("Skipped for later.", "info"),
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    return (
        _main_mod.identity_card(updated_identity, crop_files, lane_color="stone", show_actions=False),
        _main_mod.toast("Skipped for later.", "info"),
    )


# =============================================================================
# ROUTES — SKIPPED FOCUS MODE ACTIONS
# =============================================================================


@rt("/api/skipped/{identity_id}/focus-skip")
def post(identity_id: str, sess=None):
    """Advance to next identity in skipped focus mode without taking action."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    registry = _main_mod.load_registry()
    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")
    return (
        _main_mod.get_next_skipped_focus_card(exclude_id=identity_id),
        _main_mod.toast("Skipped for now.", "info"),
    )


@rt("/api/skipped/{identity_id}/reject-suggestion")
def post(identity_id: str, suggestion_id: str = "", sess=None):
    """Reject a suggestion for a skipped identity and advance to next."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if suggestion_id:
        try:
            registry = _main_mod.load_registry()
            registry.reject_identity_pair(identity_id, suggestion_id, user_source="skipped_focus")
            _main_mod.save_registry(registry)
        except (KeyError, ValueError):
            # If reject fails, just advance — don't block the user
            pass

    # Toast with undo for reject action
    reject_toast = Div(
        Span("✗", cls="mr-2"),
        Span("Suggestion rejected. Moving to next.", cls="flex-1"),
        Button(
            "Undo",
            cls="ml-3 px-2 py-1 text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"/api/identity/{identity_id}/unreject/{suggestion_id}",
            hx_swap="outerHTML",
            hx_target="closest div",
            type="button",
        )
        if suggestion_id
        else None,
        cls="px-4 py-3 rounded shadow-lg flex items-center bg-amber-600 text-white animate-fade-in",
        **{"_": "on load wait 8s then remove me"},
    )

    return (
        _main_mod.get_next_skipped_focus_card(exclude_id=identity_id),
        reject_toast,
    )


@rt("/api/skipped/{identity_id}/name-and-confirm")
def post(identity_id: str, name: str = "", sess=None):
    """Name a skipped identity and confirm it, then advance to next in focus mode."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    name = name.strip()
    if not name:
        return Response(
            to_xml(_main_mod.toast("Please enter a name.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        registry = _main_mod.load_registry()
        registry.rename_identity(identity_id, name, user_source="web_review")
        registry.confirm_identity(identity_id, user_source="web_review")
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _main_mod.save_registry(
            registry,
            confirmed_identity_info={
                "identity_id": identity_id,
                "identity_name": name,
                "user_id": _user.id if _user else None,
                "user_email": _user.email if _user else None,
            },
        )
    except (KeyError, ValueError) as e:
        return Response(
            to_xml(_main_mod.toast(f"Cannot confirm: {str(e)}", "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    _main_mod.log_user_action("CONFIRM_NAMED", identity_id=identity_id, name=name)

    return (
        _main_mod.get_next_skipped_focus_card(exclude_id=identity_id),
        _main_mod.toast(f"Confirmed as {name}!", "success"),
    )


@rt("/identity/{identity_id}/reset")
def post(identity_id: str, sess=None):
    """Reset identity back to Inbox. Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"/person/{canonical_id}")

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        registry.reset_identity(identity_id, user_source="web_review")
        _main_mod.save_registry(registry)
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)

    return (
        _main_mod.identity_card(updated_identity, crop_files, lane_color="blue", show_actions=True),
        _main_mod.toast("Returned to Inbox.", "info"),
    )
