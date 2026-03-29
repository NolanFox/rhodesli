"""
Identity routes extracted from app/main.py.

Identity modification routes: confirm, reject, merge, rename, notes,
metadata, bulk operations, skip, discoveries, inbox review, face operations,
neighbors, search, and associated helpers.
"""

import json
import logging
import time as _time
from pathlib import Path

from fasthtml.common import *
from starlette.responses import Response

from core.registry import IdentityRegistry
from core.ui_safety import ensure_utf8_display

from app.auth import _check_origin
from app.main import rt
from app.utils import photo_url, _section_for_state
from app.audit import _log_audit

import app.main as _main_mod

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Neighbors (similar panel) TTL cache — 5 min per identity_id
# ---------------------------------------------------------------------------
_neighbors_cache: dict = {}  # identity_id -> (timestamp, results_list)
_NEIGHBORS_CACHE_TTL: float = 300.0  # 5 minutes


def _get_cached_neighbors(identity_id: str):
    """Return cached neighbors or None if cache miss / expired."""
    entry = _neighbors_cache.get(identity_id)
    if entry is None:
        return None
    ts, results = entry
    if _time.time() - ts > _NEIGHBORS_CACHE_TTL:
        del _neighbors_cache[identity_id]
        return None
    return results


def _set_cached_neighbors(identity_id: str, results: list):
    """Store neighbors in cache."""
    _neighbors_cache[identity_id] = (_time.time(), results)


def invalidate_neighbors_cache(identity_id: str | None = None):
    """Invalidate neighbors cache for one identity or all.

    Called after merge/confirm/reject to ensure stale results are not shown.
    """
    if identity_id:
        _neighbors_cache.pop(identity_id, None)
    else:
        _neighbors_cache.clear()


def _nav_prefix_from_request(request) -> str:
    """Return the active community URL prefix for HTMX/admin responses."""
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    return _main_mod.community_url_prefix(community_slug)


def _community_from_request(request):
    """Return the community dict from request.state (set by CommunityMiddleware)."""
    return getattr(request.state, "community", None) if request else None


@rt("/confirm/{identity_id}")
def post(
    identity_id: str,
    from_focus: bool = False,
    filter: str = "",
    from_person_page: bool = False,
    merge_target_id: str = "",
    sess=None,
    request=None,
):
    """
    Confirm an identity (move from PROPOSED to CONFIRMED).
    When merge_target_id is provided, also auto-merges into that target (FB-004).
    Requires admin.
    """
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
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
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Session 138 FB-006: Allow confirming unidentified persons.
    # User workflow: confirm cluster as real person first, identify (name) later.
    # Previously blocked by FB-077/FB-009 — removed per user feedback.

    # Confirm the identity (state promotion only — merge is a separate explicit action)
    try:
        registry.confirm_identity(identity_id, user_source="web")
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        # FB-069: Only write the 1 changed identity
        _main_mod.save_registry(
            registry,
            confirmed_identity_info={
                "identity_id": identity_id,
                "identity_name": identity.get("name", "Unknown"),
                "user_id": _user.id if _user else None,
                "user_email": _user.email if _user else None,
            },
            changed_ids={identity_id},
        )
        _main_mod.posthog_capture(
            "admin_identity_confirmed",
            distinct_id=_user.email if _user else "admin",
            properties={"identity_id": identity_id, "identity_name": identity.get("name", "Unknown")},
        )
        _main_mod.log_user_action(
            "CONFIRM",
            identity_id=identity_id,
            identity_name=identity.get("name", "Unknown"),
            context="person_page" if from_person_page else "browse",
        )
        _log_audit(
            "confirm",
            entity_id=identity_id,
            user_email=_user.email if _user else None,
            old_value={"state": identity.get("state", "PROPOSED"), "name": identity.get("name")},
            new_value={"state": "CONFIRMED"},
            metadata={"route": "confirm", "context": "person_page" if from_person_page else "browse"},
        )
    except Exception as e:
        return Response(
            to_xml(_main_mod.toast(f"Cannot confirm: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # FB-004: Auto-merge with best match when merge_target_id provided
    merge_result = None
    if merge_target_id:
        try:
            photo_registry = _main_mod.load_photo_registry()
            merge_result = registry.merge_identities(
                source_id=identity_id,
                target_id=merge_target_id,
                user_source="web",
                photo_registry=photo_registry,
            )
            if merge_result["success"]:
                actual_target = merge_result["target_id"]
                actual_source = merge_result["source_id"]
                _main_mod.save_registry(registry, changed_ids={actual_target, actual_source})
                _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
                _log_audit(
                    "merge",
                    entity_id=actual_target,
                    user_email=_user.email if _user else None,
                    old_value={"source_id": actual_source},
                    new_value={"merged_into": actual_target, "faces_merged": merge_result.get("faces_merged", 0)},
                    metadata={"route": "confirm_and_merge", "trigger": "confirm_as_button"},
                )
                _main_mod.log_user_action(
                    "CONFIRM_AND_MERGE",
                    identity_id=identity_id,
                    merge_target_id=merge_target_id,
                    faces_merged=merge_result.get("faces_merged", 0),
                    direction_swapped=merge_result.get("direction_swapped", False),
                )
                logger.info(
                    "Confirm+merge: %s -> %s, %d faces merged",
                    identity_id[:8],
                    merge_target_id[:8],
                    merge_result.get("faces_merged", 0),
                )
                # Codex P1: Run merge side effects (annotations + recalibration)
                try:
                    _main_mod._fire_recalibration_hook("merge", actual_target, actual_source)
                except Exception:
                    pass
                _main_mod._merge_annotations(actual_source, actual_target)
            else:
                logger.warning(
                    "Confirm succeeded but auto-merge failed: %s -> %s, reason=%s",
                    identity_id[:8],
                    merge_target_id[:8],
                    merge_result.get("reason", "unknown"),
                )
        except Exception:
            logger.exception("Confirm+merge error: %s -> %s", identity_id[:8], merge_target_id[:8])

    # AD-150: Fire recalibration hook (best-effort, non-blocking)
    try:
        anchor_ids = identity.get("anchor_ids", [])
        _main_mod._fire_recalibration_hook("confirm", identity_id, anchor_face_ids=anchor_ids)
    except Exception:
        pass  # Never block confirm on calibration

    # PRD-049: Post-confirm re-matching — find new proposals for confirmed identity
    try:
        import threading

        def _post_confirm_rematch(iid, data_path):
            try:
                from core.cross_batch_matching import find_cross_batch_matches
                from scripts.cluster_new_faces import load_face_data, load_identities

                identities_data = load_identities(data_path)
                face_data_dict = load_face_data(data_path)
                photo_reg = _main_mod.load_photo_registry()
                confirmed_identity = identities_data.get("identities", {}).get(iid, {})
                confirmed_face_ids = []
                for fid in confirmed_identity.get("anchor_ids", []):
                    if isinstance(fid, str):
                        confirmed_face_ids.append(fid)

                if not confirmed_face_ids:
                    return

                matches = find_cross_batch_matches(
                    new_face_ids=confirmed_face_ids,
                    identities=identities_data,
                    face_data=face_data_dict,
                    photo_registry=photo_reg,
                )
                if matches:
                    import json
                    from datetime import datetime as _dt, timezone as _tz

                    proposals_path = data_path / "proposals.json"
                    # Read existing proposals via unified reader (Supabase or JSON, PRD-051)
                    existing_proposals = _main_mod._load_proposals().get("proposals", [])

                    existing_pairs = {
                        (p.get("source_identity_id"), p.get("target_identity_id")) for p in existing_proposals
                    }
                    new_proposals = []
                    for m in matches:
                        pair = (m["source_identity_id"], m["target_identity_id"])
                        reverse = (m["target_identity_id"], m["source_identity_id"])
                        if pair not in existing_pairs and reverse not in existing_pairs:
                            new_proposals.append(
                                {
                                    "source_identity_id": m["source_identity_id"],
                                    "source_identity_name": m["source_identity_name"],
                                    "target_identity_id": m["target_identity_id"],
                                    "target_identity_name": m["target_identity_name"],
                                    "distance": m["distance"],
                                    "match_type": m["match_type"],
                                    "confidence_tier": m["confidence_tier"],
                                    "face_id": m["source_face_id"],
                                    "source_state": "CONFIRMED",
                                }
                            )
                            existing_pairs.add(pair)

                    if new_proposals:
                        all_proposals = existing_proposals + new_proposals
                        proposals_data = {
                            "generated_at": _dt.now(_tz.utc).isoformat(),
                            "threshold": 1.05,
                            "proposals": all_proposals,
                            "triggered_by": "post_confirm",
                        }
                        with open(proposals_path, "w") as f:
                            json.dump(proposals_data, f, indent=2)
                        # Invalidate proposals cache so new proposals are visible (PRD-051)
                        _main_mod.invalidate_proposals_cache()
                        logger.info(
                            "Post-confirm re-match for %s: %d new proposals",
                            iid[:8],
                            len(new_proposals),
                        )
            except Exception as e:
                logger.error("Post-confirm re-match failed for %s: %s", iid[:8], e)

        # Codex P2: Use surviving identity for rematching (not source if it was merged)
        _rematch_id = merge_result["target_id"] if (merge_result and merge_result.get("success")) else identity_id
        threading.Thread(
            target=_post_confirm_rematch,
            args=(_rematch_id, _main_mod.data_path),
            daemon=True,
        ).start()
    except Exception:
        pass  # Never block confirm on re-matching

    # Build appropriate toast message
    if merge_result and merge_result.get("success"):
        actual_target = merge_result["target_id"]
        target_identity = registry.get_identity(actual_target)
        target_name = ensure_utf8_display(target_identity.get("name", "identity"))
        toast_msg = f"Confirmed and merged {merge_result.get('faces_merged', 0)} face(s) into {target_name}."
    else:
        toast_msg = "Identity confirmed."
        if merge_target_id and (not merge_result or not merge_result.get("success")):
            reason = merge_result.get("reason", "unknown") if merge_result else "error"
            toast_msg = f"Confirmed, but merge failed ({reason}). You may need to merge manually."

    # If from focus mode, return the next focus card with OOB toast
    if from_focus:
        nav_prefix = _nav_prefix_from_request(request)
        oob_toast = Div(
            _main_mod.toast(toast_msg, "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (
            _main_mod.get_next_focus_card(
                exclude_id=identity_id,
                triage_filter=filter,
                nav_prefix=nav_prefix,
                community=_community_from_request(request),
            ),
            oob_toast,
        )

    # FB-017: On person page, return status update instead of full identity card
    if from_person_page:
        return (
            Div(
                Span(
                    "\u2713 CONFIRMED",
                    cls="text-sm sm:text-xs px-2 py-0.5 rounded-full font-medium bg-emerald-500/20 text-emerald-400",
                ),
                id="person-admin-actions",
                cls="flex items-center justify-center gap-2 mb-3",
            ),
            _main_mod.toast(toast_msg, "success"),
        )

    nav_prefix = _nav_prefix_from_request(request)

    # If merge succeeded, show the surviving identity's card instead
    if merge_result and merge_result.get("success"):
        from app.utils import make_css_id

        actual_target = merge_result["target_id"]
        actual_source = merge_result["source_id"]
        crop_files = _main_mod.get_crop_files()
        surviving = registry.get_identity(actual_target)
        target_name = ensure_utf8_display(surviving.get("name", "identity"))
        oob_delete = [
            Div(id=f"identity-{actual_source}", hx_swap_oob="delete"),
            Div(id=f"neighbor-{actual_source}", hx_swap_oob="delete"),
            # FB-012: Clear expansion panels for both source and target
            Div("", id=f"expand-{make_css_id(identity_id)}", hx_swap_oob="innerHTML"),
            Div("", id=f"expand-{make_css_id(actual_source)}", hx_swap_oob="innerHTML"),
        ]
        return (
            _main_mod.identity_card(
                surviving, crop_files, lane_color="emerald", show_actions=False, nav_prefix=nav_prefix
            ),
            _main_mod.toast(toast_msg, "success"),
            *oob_delete,
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

    # FB-012: Clear the expansion panel (Similar Identities) which is a sibling div
    from app.utils import make_css_id

    _expand_clear = Div("", id=f"expand-{make_css_id(identity_id)}", hx_swap_oob="innerHTML")

    # Return the card plus a success toast (+ GEDCOM link panel if applicable)
    parts = [
        _main_mod.identity_card(
            updated_identity, crop_files, lane_color="emerald", show_actions=False, nav_prefix=nav_prefix
        ),
        _main_mod.toast(toast_msg, "success"),
        _expand_clear,
    ]
    if gedcom_panel:
        parts.append(gedcom_panel)
    return tuple(parts)


@rt("/reject/{identity_id}")
def post(
    identity_id: str,
    from_focus: bool = False,
    filter: str = "",
    from_person_page: bool = False,
    sess=None,
    request=None,
):
    """Contest/reject an identity (move to CONTESTED). Requires admin."""
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
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
        _main_mod.save_registry(registry, changed_ids={identity_id})
        _main_mod.log_user_action(
            "REJECT",
            identity_id=identity_id,
            identity_name=identity.get("name", "Unknown"),
            context="person_page" if from_person_page else "browse",
        )
    except Exception as e:
        return Response(
            to_xml(_main_mod.toast(f"Cannot reject: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # If from focus mode, return the next focus card with OOB toast
    if from_focus:
        nav_prefix = _nav_prefix_from_request(request)
        oob_toast = Div(
            _main_mod.toast("Identity contested.", "warning"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (
            _main_mod.get_next_focus_card(
                exclude_id=identity_id,
                triage_filter=filter,
                nav_prefix=nav_prefix,
                community=_community_from_request(request),
            ),
            oob_toast,
        )

    # FB-017: On person page, return status update instead of full identity card
    if from_person_page:
        return (
            Div(
                Span(
                    "\u2717 REJECTED",
                    cls="text-sm sm:text-xs px-2 py-0.5 rounded-full font-medium bg-red-500/20 text-red-400",
                ),
                id="person-admin-actions",
                cls="flex items-center justify-center gap-2 mb-3",
            ),
            _main_mod.toast("Identity contested.", "warning"),
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)
    nav_prefix = _nav_prefix_from_request(request)

    return (
        _main_mod.identity_card(
            updated_identity, crop_files, lane_color="red", show_actions=False, nav_prefix=nav_prefix
        ),
        _main_mod.toast("Identity contested.", "warning"),
    )


@rt("/api/identity/{identity_id}/reject-match/{neighbor_id}", methods=["POST"])
def post(identity_id: str, neighbor_id: str, sess=None, request=None):
    """Record a negative match between two identities and remove the tile."""
    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    is_admin = user and user.is_admin if user else not _main_mod.is_auth_enabled()
    if not is_admin:
        return Response("Forbidden", status_code=403)

    registry = _main_mod.load_registry()
    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")
    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    # Record bidirectional negative pair
    try:
        registry.reject_identity_pair(identity_id, neighbor_id, user_source="admin_inline")
        _main_mod.save_registry(registry, changed_ids={identity_id, neighbor_id})
        invalidate_neighbors_cache(identity_id)
        invalidate_neighbors_cache(neighbor_id)
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
    community_filter: str = "",
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
    _t0 = _time.monotonic()
    try:
        registry = _main_mod.load_registry()
        registry.get_identity(identity_id)
    except KeyError:
        return Div(P("Identity not found.", cls="text-red-600 text-center py-4"), cls="neighbors-sidebar")

    # Request one extra to determine if more exist (B3: pagination)
    total_to_fetch = offset + limit + 1
    try:
        # Check cache first
        cached = _get_cached_neighbors(identity_id)
        if cached is not None and len(cached) >= total_to_fetch:
            all_neighbors = cached[:total_to_fetch]
            cache_hit = True
        else:
            from app.perf_cache import get_all_neighbors

            # Use precomputed global embedding matrix (Session 135b)
            # Eliminates 100-200ms matrix construction per request
            # Session 138: Fetch more when community filter is active, since filtering
            # may eliminate most results from the raw pool (Codex P1 finding)
            # FB-008 (Session 142): Fetch 100 base to survive merged_into + negative_ids
            # filtering. ~51% of identities are merged, so 20 was far too few.
            _base_limit = 100 if community_filter in ("same", "cross") else 100
            fetch_limit = max(total_to_fetch, _base_limit)
            all_neighbors = get_all_neighbors(identity_id, limit=fetch_limit)
            _set_cached_neighbors(identity_id, all_neighbors)
            cache_hit = False
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

    _elapsed_ms = round((_time.monotonic() - _t0) * 1000, 1)
    logger.info(
        "similar_scan",
        similar_scan_ms=_elapsed_ms,
        identity_id=identity_id,
        result_count=len(all_neighbors),
        cache_hit=cache_hit,
    )

    # FB-038: For Load More (offset > 0), only return NEW cards (not already-shown ones)
    is_incremental = offset > 0

    # Session 138 FB-012: Apply community filter BEFORE pagination so Load More works correctly.
    # Previously, community filter was applied after slicing, causing Load More to return empty
    # results when "Same community only" was selected.
    current_community = getattr(request.state, "community", None) if request else None
    comm_ids = _main_mod._get_community_identity_ids(current_community) if current_community else None
    if comm_ids is not None:
        for n in all_neighbors:
            n["_same_community"] = n["identity_id"] in comm_ids
        if community_filter == "same":
            all_neighbors = [n for n in all_neighbors if n.get("_same_community", False)]
        elif community_filter == "cross":
            all_neighbors = [n for n in all_neighbors if not n.get("_same_community", False)]
        elif community_filter == "all":
            pass
        else:
            all_neighbors.sort(key=lambda n: (0 if n.get("_same_community", False) else 1, n.get("distance", 999)))
        _community_filter_applied_early = True
    else:
        _community_filter_applied_early = False

    # Session 138 FB-013: Filter out rejected identities (negative_ids).
    # perf_cache.get_all_neighbors doesn't check negative_ids, so we filter here.
    try:
        target_identity = registry.get_identity(identity_id)
        negative_ids = set(target_identity.get("negative_ids", []))
        if negative_ids:
            all_neighbors = [n for n in all_neighbors if f"identity:{n['identity_id']}" not in negative_ids]
    except KeyError:
        pass

    # FB-007 (Session 142): Filter out already-merged identities.
    # These appear in the embedding index but have merged_into set, causing
    # "already merged" errors when users try to merge them.
    all_neighbors = [n for n in all_neighbors if not registry.get_identity(n["identity_id"]).get("merged_into")]

    # Determine if more neighbors exist beyond current page (AFTER community + rejection filter)
    has_more = len(all_neighbors) > offset + limit

    # Return only neighbors up to current offset + limit
    neighbors = all_neighbors[: offset + limit]

    # Enhance neighbor data with additional info for UI
    photo_registry = _main_mod.load_photo_registry()
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

    # Filter out duplicate face detections: same face detected twice in same photo
    # These show as Dist ~0.00 with co-occurrence (seen together in same photo)
    # BUT: if the identities share face IDs (multi-claimed faces), that's a data
    # integrity issue — keep them and flag for merge instead of hiding them.
    target_faces = set(registry.get_anchor_face_ids(identity_id) + registry.get_candidate_face_ids(identity_id))
    filtered_neighbors = []
    for n in neighbors:
        if n.get("distance", 1.0) < 0.1 and n.get("co_occurrence", 0) > 0:
            # Check if this is multi-claimed faces (shared face IDs) vs genuine co-occurrence
            neighbor_faces = set(n.get("anchor_face_ids", []) + n.get("candidate_face_ids", []))
            shared_faces = target_faces & neighbor_faces
            if shared_faces:
                # Multi-claimed faces — keep and flag for merge
                n["has_shared_faces"] = True
                n["shared_face_count"] = len(shared_faces)
                filtered_neighbors.append(n)
            else:
                # Genuine co-occurrence with near-identical embedding — likely duplicate detection, filter out
                pass
        else:
            filtered_neighbors.append(n)
    neighbors = filtered_neighbors

    # FB-011: Community-aware sorting/filtering — already applied early (Session 138 FB-012)
    # current_community already set above for early community filter

    # Count rejected identities for contextual recovery indicator
    identity = registry.get_identity(identity_id)
    rejected_count = sum(1 for neg in identity.get("negative_ids", []) if neg.startswith("identity:"))

    target_name = ensure_utf8_display(identity.get("name", "")) or ""
    # current_community already set above for FB-011 community sorting
    if current_community is None:
        current_community = getattr(request.state, "community", None) if request else None
    nav_prefix = _nav_prefix_from_request(request)

    # FB-038: When Load More is clicked (offset > 0), return only the NEW cards
    # plus a new Load More button. This preserves checkbox state on existing cards.
    if is_incremental:
        new_neighbors = neighbors[offset:]  # Only the newly fetched ones
        _is_person_page = container_id.startswith("person-similar-") if container_id else False
        new_cards = [
            _main_mod.neighbor_card(
                n,
                identity_id,
                crop_files,
                user_role=_main_mod._get_user_role(sess),
                from_focus=from_focus,
                focus_section=focus_section,
                target_name=target_name,
                current_community=current_community,
                nav_prefix=nav_prefix,
                from_person_page=_is_person_page,
            )
            for n in new_neighbors
        ]
        # Build new Load More button (or nothing if no more)
        _focus_section_param = f"&focus_section={focus_section}" if focus_section else ""
        _container_param = f"&container_id={container_id}" if container_id else ""
        _community_filter_param = f"&community_filter={community_filter}" if community_filter else ""
        focus_param = f"&from_focus=true{_focus_section_param}" if from_focus else ""
        next_offset = offset + limit
        _load_more_id = f"load-more-{identity_id}"
        if has_more:
            load_more_btn = Div(
                Button(
                    "Load More",
                    cls="w-full text-sm text-indigo-400 hover:text-indigo-300 py-2 border border-indigo-500/50 rounded hover:bg-indigo-500/20",
                    hx_get=f"{nav_prefix}/api/identity/{identity_id}/neighbors?offset={next_offset}{focus_param}{_container_param}{_community_filter_param}",
                    hx_target=f"#{_load_more_id}",
                    hx_swap="outerHTML",
                ),
                id=_load_more_id,
            )
        else:
            load_more_btn = None

        # Return fragment: new cards + optional load more (replaces the old load-more div)
        return Div(*new_cards, load_more_btn)

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
        nav_prefix=nav_prefix,
        community_filter=community_filter,
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
def get(identity_id: str, request=None):
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
        return Span("No similar identities found.", cls="text-sm sm:text-xs text-slate-500 italic")

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
    nav_prefix = _nav_prefix_from_request(request)
    suggestion_items = []
    for n in neighbors:
        name = ensure_utf8_display(n.get("name", "Unknown"))
        dist = n.get("distance", 0)
        neighbor_id = n.get("identity_id", "")
        tier_label, tier_color, tier_dots = confidence_tier_with_dots(dist)

        # Face thumbnail — use enriched anchor/candidate face IDs (same pattern as neighbor_card)
        thumb = Div(cls="w-10 h-10 aspect-square rounded-lg bg-slate-600 flex-shrink-0")
        all_face_ids = n.get("anchor_face_ids", []) + n.get("candidate_face_ids", [])
        for fid in all_face_ids:
            face_url = _main_mod.resolve_face_image_url(fid, crop_files)
            if face_url:
                thumb = Img(
                    src=face_url,
                    cls="w-10 h-10 aspect-square rounded-lg object-cover flex-shrink-0 border border-slate-600",
                    alt="Face thumbnail",
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
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/compare/{neighbor_id}",
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
                hx_post=f"{nav_prefix}/api/identity/{neighbor_id}/merge/{identity_id}",
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
            Span("AI suggestions", cls="text-sm sm:text-xs text-slate-400 font-medium"),
            cls="mb-1",
        ),
        *suggestion_items,
        cls="mt-2 bg-slate-800/50 rounded-lg border border-slate-700/50 p-1",
    )


@rt("/api/identity/{identity_id}/search")
def get(identity_id: str, q: str = "", from_person_page: bool = False, sess=None, request=None):
    """
    Search for identities by name for manual merge.

    Phase 3B: Manual Search & Human-Authorized Merge Tools

    Args:
        identity_id: Current identity (excluded from results)
        q: Search query (minimum 2 characters)
        from_person_page: Whether this search is on the person page (affects merge button targets)

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
    nav_prefix = _nav_prefix_from_request(request)
    return _main_mod.search_results_panel(
        results,
        identity_id,
        crop_files,
        user_role=_main_mod._get_user_role(sess),
        target_name=_target_name,
        nav_prefix=nav_prefix,
        from_person_page=from_person_page,
    )


@rt("/api/identity/{source_id}/distance/{target_id}")
def get(source_id: str, target_id: str, sess=None, request=None):
    """Compute embedding distance between two identities (lazy-loaded via HTMX)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return Span("", cls="hidden")

    try:
        registry = _main_mod.load_registry()
        registry.get_identity(source_id)
        registry.get_identity(target_id)
    except (KeyError, Exception):
        return Span("", cls="hidden")

    face_data = _main_mod.get_face_data()
    from core.neighbors import get_identity_embeddings
    from scipy.spatial.distance import cdist

    _s_fids, s_embs = get_identity_embeddings(source_id, registry, face_data)
    _t_fids, t_embs = get_identity_embeddings(target_id, registry, face_data)

    if s_embs.size == 0 or t_embs.size == 0:
        return Span("No embedding", cls="text-[10px] text-slate-500 italic distance-badge-reveal ml-2")

    dists = cdist(s_embs, t_embs, metric="euclidean")
    min_dist = float(dists.min())

    from core.confidence import compute_face_confidence

    conf = compute_face_confidence(min_dist)
    pct = conf.get("calibrated_score", 0)
    tier = conf.get("tier_label", "")

    # Color based on tier
    if pct >= 60:
        color = "bg-emerald-600/80 text-emerald-100"
    elif pct >= 45:
        color = "bg-amber-600/80 text-amber-100"
    else:
        color = "bg-slate-600/80 text-slate-300"

    return Span(
        Span(f"{pct}% match", cls=f"text-[10px] font-bold px-1.5 py-0.5 rounded {color}"),
        Span(f"Dist: {min_dist:.2f}", cls="text-[10px] font-mono text-slate-400 ml-1"),
        Span(tier, cls="text-[10px] text-slate-400 ml-1"),
        cls="flex items-center gap-1 distance-badge-reveal ml-2",
    )


@rt("/api/search")
def get(q: str = "", request=None):
    """
    Global search for identities by name. Used by the sidebar search input.

    Args:
        q: Search query (minimum 2 characters, case-insensitive partial match)

    Returns HTMX partial with matching identity results (limit 10).
    Each result links to the correct section based on identity state.
    """
    if len(q.strip()) < 2:
        return ""
    nav_prefix = _nav_prefix_from_request(request)

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Div(
            P("Search unavailable.", cls="text-slate-400 italic text-sm p-2"),
        )

    # Search identities by name — include merged so users can find them (FB-065)
    results = registry.search_identities(q, include_merged=True)

    # Also search photo filenames (FB-015)
    query_lower = q.strip().lower()
    photo_results = []
    _main_mod._build_caches()
    photo_cache = _main_mod._photo_cache or {}
    for photo_id, pdata in photo_cache.items():
        fname = pdata.get("filename", "")
        if fname and query_lower in fname.lower():
            photo_results.append({"photo_id": photo_id, "filename": fname, "pdata": pdata})
            if len(photo_results) >= 5:
                break

    if not results and not photo_results:
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
            Img(src=face_url, cls="w-8 h-8 rounded-full object-cover flex-shrink-0", alt="Face thumbnail")
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
            result_href = f"{nav_prefix}/person/{r['identity_id']}"
        else:
            result_href = f"{nav_prefix}/identify/{r['identity_id']}"

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
                        f"{r['face_count']} {'face' if r['face_count'] == 1 else 'faces'}",
                        cls="text-sm sm:text-xs text-slate-500",
                    ),
                    cls="flex flex-col min-w-0",
                ),
                href=result_href,
                cls="flex items-center gap-2 px-3 py-2 hover:bg-slate-700 transition-colors cursor-pointer",
            )
        )

    # Add photo filename results (FB-015)
    if photo_results:
        if items:
            items.append(
                Div(
                    Span("Photos", cls="text-[10px] font-medium uppercase tracking-wider text-slate-500"),
                    cls="px-3 pt-2 pb-1 border-t border-slate-700",
                )
            )
        for pr in photo_results:
            fname = pr["filename"]
            photo_id = pr["photo_id"]
            face_count = len(pr["pdata"].get("faces", []))
            highlighted_fname = _main_mod._highlight_match(fname, query_stripped)
            photo_thumb = Div(cls="w-8 h-8 rounded bg-slate-700 flex-shrink-0")
            items.append(
                A(
                    photo_thumb,
                    Div(
                        Span(highlighted_fname, cls="text-sm text-slate-200 truncate"),
                        Span(
                            f"{face_count} {'face' if face_count == 1 else 'faces'}",
                            cls="text-sm sm:text-xs text-slate-500",
                        ),
                        cls="flex flex-col min-w-0",
                    ),
                    href=f"{nav_prefix}/photo/{photo_id}",
                    cls="flex items-center gap-2 px-3 py-2 hover:bg-slate-700 transition-colors cursor-pointer",
                    data_testid="search-photo-result",
                )
            )

    return Div(*items)


@rt("/api/review-search")
def get(q: str = "", request=None, sess=None):
    """FB-067: Server-side search for review cards beyond the 150-card display limit.

    Returns compact identity cards matching the query, including identities
    not rendered in the initial page load.
    """
    if len(q.strip()) < 2:
        return ""

    nav_prefix = _nav_prefix_from_request(request)
    try:
        registry = _main_mod.load_registry()
    except Exception:
        return ""

    results = registry.search_identities(q, include_merged=True)
    if not results:
        return Div(P("No matching identities found.", cls="text-slate-400 text-sm italic p-2"))

    crop_files = _main_mod.get_crop_files()
    items = []
    for r in results[:20]:
        identity_id = r["identity_id"]
        name = ensure_utf8_display(r["name"]) or f"Person {identity_id[:8]}"
        state = r.get("state", "INBOX")
        face_count = r.get("face_count", 0)
        face_url = (
            _main_mod.resolve_face_image_url(r["preview_face_id"], crop_files) if r.get("preview_face_id") else None
        )
        thumb = (
            Img(src=face_url, cls="w-10 h-10 rounded object-cover flex-shrink-0", loading="lazy", alt="Face thumbnail")
            if face_url
            else Div(cls="w-10 h-10 rounded bg-slate-700 flex-shrink-0")
        )
        state_colors = {
            "CONFIRMED": "text-emerald-400",
            "PROPOSED": "text-indigo-400",
            "INBOX": "text-slate-400",
            "SKIPPED": "text-amber-400",
        }
        state_cls = state_colors.get(state, "text-slate-400")
        section = _section_for_state(state)
        href = f"{nav_prefix}/?section={section}&view=browse#identity-{identity_id}"
        if state == "CONFIRMED" and not name.startswith("Unidentified"):
            href = f"{nav_prefix}/person/{identity_id}"

        items.append(
            A(
                thumb,
                Div(
                    Span(name, cls="text-sm text-white font-medium truncate"),
                    Div(
                        Span(state, cls=f"text-sm sm:text-xs {state_cls}"),
                        Span(
                            f" · {face_count} face{'s' if face_count != 1 else ''}",
                            cls="text-sm sm:text-xs text-slate-500",
                        ),
                        cls="flex items-center gap-1",
                    ),
                    cls="flex flex-col min-w-0",
                ),
                href=href,
                cls="flex items-center gap-3 px-3 py-2 bg-slate-800/80 border border-slate-700 rounded-lg hover:bg-slate-700 transition-colors",
            )
        )

    return Div(
        Div(
            Span(
                f"Server search: {len(results)} match{'es' if len(results) != 1 else ''}",
                cls="text-sm sm:text-xs text-slate-500",
            ),
            cls="px-1 mb-1",
        ),
        *items,
        cls="space-y-1",
    )


@rt("/api/face/tag-search")
def get(
    face_id: str,
    q: str = "",
    seq: str = "",
    context_identity_id: str = "",
    sort_by: str = "date_asc",
    show_all: str = "",
    sess=None,
    request=None,
):
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
    context_suffix = f"&context_identity_id={context_identity_id}&sort_by={sort_by}" if context_identity_id else ""
    results_id = f"tag-results-{safe_face_id}"
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    if len(q.strip()) < 2:
        return Div(id=results_id)

    try:
        registry = _main_mod.load_registry()
    except Exception:
        return Div(P("Search unavailable.", cls="text-slate-400 italic text-sm sm:text-xs"), id=results_id)

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

    # FB-004: Filter by community by default, show all only when requested
    community = getattr(request.state, "community", None) if request else None
    comm_ids = _main_mod._get_community_identity_ids(community) if community else None
    is_community_filtered = False
    all_results_count = len(results)
    if comm_ids is not None and show_all != "1":
        # Filter to only community identities
        results = [r for r in results if r["identity_id"] in comm_ids]
        is_community_filtered = True

    # FB-162: Re-sort to prioritize same-community + confirmed + higher face count
    if comm_ids is not None:
        _sr = {"CONFIRMED": 0, "PROPOSED": 1, "INBOX": 2, "SKIPPED": 3}
        results.sort(
            key=lambda r: (
                0 if r["identity_id"] in comm_ids else 1,
                _sr.get(r.get("state", "INBOX"), 9),
                -(r.get("face_count", 0)),
            )
        )

    crop_files = _main_mod.get_crop_files()
    items = []
    for r in results[:8]:
        face_url = (
            _main_mod.resolve_face_image_url(r["preview_face_id"], crop_files) if r.get("preview_face_id") else None
        )
        thumb = (
            Img(src=face_url, cls="w-8 h-8 rounded-full object-cover flex-shrink-0", alt="Face thumbnail")
            if face_url
            else Div(cls="w-8 h-8 rounded-full bg-slate-600 flex-shrink-0")
        )
        name = ensure_utf8_display(r["name"]) or "Unnamed"
        cross_badge = _main_mod._cross_community_badge(r["identity_id"], community) if community else None
        name_row = (
            Div(
                Span(name, cls="text-sm text-slate-200 truncate"),
                cross_badge,
                cls="flex items-center gap-1",
            )
            if cross_badge
            else Span(name, cls="text-sm text-slate-200 truncate")
        )

        if user_is_admin:
            # Admin: direct merge
            btn = Button(
                thumb,
                Div(
                    name_row,
                    Span(f"{r['face_count']} faces", cls="text-sm sm:text-xs text-slate-500"),
                    cls="flex flex-col min-w-0 text-left",
                ),
                cls="flex items-center gap-2 w-full px-4 py-3 sm:px-2 sm:py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer",
                hx_post=f"{nav_prefix}/api/face/tag?face_id={face_id_encoded}&target_id={r['identity_id']}{seq_suffix}{context_suffix}",
                hx_target="#photo-modal-content",
                hx_swap="innerHTML",
                type="button",
            )
        else:
            # Non-admin: submit name suggestion annotation
            btn = Button(
                thumb,
                Div(
                    name_row,
                    Span("Suggest match", cls="text-sm sm:text-xs text-indigo-400"),
                    cls="flex flex-col min-w-0 text-left",
                ),
                cls="flex items-center gap-2 w-full px-4 py-3 sm:px-2 sm:py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer",
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
                Span("New identity", cls="text-sm sm:text-xs text-slate-500"),
                cls="flex flex-col min-w-0 text-left",
            ),
            cls="flex items-center gap-2 w-full px-4 py-3 sm:px-2 sm:py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer "
            "border-t border-slate-700 mt-1 pt-1",
            hx_post=(
                f"{nav_prefix}/api/face/create-identity?face_id={face_id_encoded}&name={_url_quote(q.strip())}"
                f"{seq_suffix}{context_suffix}"
            ),
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
                Span("Submit for review", cls="text-sm sm:text-xs text-slate-500"),
                cls="flex flex-col min-w-0 text-left",
            ),
            cls="flex items-center gap-2 w-full px-4 py-3 sm:px-2 sm:py-1.5 hover:bg-slate-700 rounded transition-colors cursor-pointer "
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
    # FB-004: "Show all communities" link when community-filtered
    show_all_btn = None
    if is_community_filtered and all_results_count > len(results):
        from urllib.parse import quote as _url_quote_all

        show_all_btn = Button(
            Span("Show all communities", cls="text-sm text-indigo-400"),
            Span(f"({all_results_count - len(results)} more)", cls="text-sm sm:text-xs text-slate-500 ml-1"),
            cls="flex items-center justify-center w-full px-4 py-2 sm:px-2 sm:py-1 hover:bg-slate-700 rounded "
            "transition-colors cursor-pointer border-t border-slate-700 mt-1 pt-1",
            hx_get=(
                f"{nav_prefix}/api/face/tag-search?face_id={face_id_encoded}&q={_url_quote_all(q)}"
                f"&show_all=1{seq_suffix}{context_suffix}"
            ),
            hx_target=f"#{results_id}",
            hx_swap="outerHTML",
            type="button",
        )

    # UX-074: "Create New" at top of dropdown (first option, before search results)
    if not results:
        # Show only the create/suggest button with a "no matches" message
        extra = [show_all_btn] if show_all_btn else []
        return Div(
            P("No existing matches.", cls="text-slate-500 italic text-sm sm:text-xs p-1"),
            create_btn,
            *extra,
            id=results_id,
        )

    extra = [show_all_btn] if show_all_btn else []
    return Div(create_btn, *items, *extra, id=results_id)


@rt("/api/face/tag")
def post(
    face_id: str,
    target_id: str,
    seq: str = "",
    context_identity_id: str = "",
    sort_by: str = "date_asc",
    sess=None,
    request=None,
):
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
        actual_source = result.get("source_id", source_id)
        actual_target = result.get("target_id", target_id)
        save_ok = _main_mod.save_registry(registry, changed_ids={actual_source, actual_target})
        _main_mod._invalidate_discovery_cache()
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _log_audit(
            "merge",
            entity_id=actual_target,
            user_email=_user.email if _user else None,
            old_value={"source_id": actual_source, "face_id": face_id},
            new_value={"merged_into": actual_target, "faces_merged": result.get("faces_merged", 0)},
            metadata={"route": "face_tag"},
        )
        if save_ok is False:
            logging.error(f"Tag face {face_id} -> {target_id}: merge in memory but Postgres write failed")
            # FB-036/037: Surface sync failure to user instead of silent success
            toast_msg = f"Tagged as {target_name}, but sync failed — may not persist. Try refreshing."
            toast_level = "warning"
        else:
            toast_msg = f"Tagged as {target_name}!"
            toast_level = "success"

        # Find the photo this face is in to re-render the photo view
        photo_id = _main_mod.get_photo_id_for_face(face_id)

        # Fallback: check photo_registry directly (face may not be in embeddings cache)
        if not photo_id:
            try:
                photo_id = photo_registry.get_photo_for_face(face_id)
            except Exception:
                pass

        if photo_id:
            # Re-render the photo view to reflect the merge
            # If seq=1, stay in sequential mode for the next unidentified face
            seq_mode = seq == "1"
            community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
            photo_content = _main_mod.photo_view_content(
                photo_id,
                selected_face_id=face_id,
                is_partial=True,
                identity_id=context_identity_id or None,
                sort_by=sort_by,
                is_admin=True,
                seq_mode=seq_mode,
                community_slug=community_slug,
            )
            oob_toast = Div(
                _main_mod.toast(toast_msg, toast_level),
                hx_swap_oob="beforeend:#toast-container",
            )
            return (*photo_content, oob_toast)
        else:
            # FB-168: Must retarget to toast container, not photo-modal-content.
            # Without retarget, the bare toast replaces the entire photo viewer
            # with a fading message — appears as "nothing happens."
            return Response(
                to_xml(_main_mod.toast(toast_msg, toast_level)),
                status_code=200,
                headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
            )
    else:
        return Response(
            to_xml(_main_mod.toast(f"Cannot tag: {result['reason']}", "warning")),
            status_code=200,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )


@rt("/api/face/quick-action")
def post(
    identity_id: str,
    action: str,
    photo_id: str,
    seq: str = "",
    context_identity_id: str = "",
    sort_by: str = "date_asc",
    sess=None,
    request=None,
):
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
    action_name = "Ignored" if action == "skip" else action.capitalize()

    # Session 138 FB-006: Allow confirming unidentified persons.
    # Previously blocked by FB-066 — removed per user feedback.

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
        _main_mod.save_registry(registry, confirmed_identity_info=_notify, changed_ids={identity_id})
        _user_email = None
        if action == "confirm" and _notify:
            _user_email = _notify.get("user_email")
        elif _main_mod.is_auth_enabled():
            _qa_user = _main_mod.get_current_user(sess or {})
            _user_email = _qa_user.email if _qa_user else None
        _log_audit(
            action,
            entity_id=identity_id,
            user_email=_user_email,
            old_value={"state": state, "name": identity.get("name")},
            new_value={
                "state": "CONFIRMED" if action == "confirm" else ("SKIPPED" if action == "skip" else "CONTESTED")
            },
            metadata={"route": "quick_action", "photo_id": photo_id},
        )
    except (ValueError, Exception) as e:
        return Response(
            to_xml(_main_mod.toast(f"Cannot {action}: {str(e)}", "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Re-render the photo view with updated overlay colors
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    photo_content = _main_mod.photo_view_content(
        photo_id,
        is_partial=True,
        identity_id=context_identity_id or None,
        sort_by=sort_by,
        is_admin=True,
        seq_mode=seq == "1",
        community_slug=community_slug,
    )
    oob_toast = Div(
        _main_mod.toast(
            "Ignored for now. You can still rediscover it later." if action == "skip" else f"{action_name}ed identity!",
            "success",
        ),
        hx_swap_oob="beforeend:#toast-container",
    )
    return (*photo_content, oob_toast)


@rt("/api/face/create-identity")
def post(
    face_id: str,
    name: str,
    seq: str = "",
    context_identity_id: str = "",
    sort_by: str = "date_asc",
    sess=None,
    request=None,
):
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
        previous_name = registry.rename_identity(identity_id, name, user_source="face_tag")
    except (KeyError, ValueError) as e:
        return Response(
            to_xml(_main_mod.toast(f"Could not rename: {e}", "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )
    # Auto-confirm when naming from tag dropdown (tagging = "this IS that person")
    current_state = source_identity.get("state", "INBOX")
    _notify = None
    _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    if current_state in ("INBOX", "PROPOSED", "SKIPPED"):
        try:
            registry.confirm_identity(identity_id, user_source="face_tag")
            _notify = {
                "identity_id": identity_id,
                "identity_name": name,
                "user_id": _user.id if _user else None,
                "user_email": _user.email if _user else None,
            }
        except Exception:
            pass  # Already confirmed, or other benign error
    _main_mod.save_registry(registry, confirmed_identity_info=_notify, changed_ids={identity_id})
    _main_mod.log_user_action(
        "RENAME_IDENTITY",
        identity_id=identity_id,
        previous_name=previous_name or "",
        new_name=name,
        admin=_user.email if _user else "admin",
        source="face_tag",
    )
    _log_audit(
        "rename",
        entity_id=identity_id,
        user_email=_user.email if _user else None,
        old_value={"name": previous_name},
        new_value={"name": name, "state": "CONFIRMED" if _notify else current_state},
        metadata={"route": "create_identity", "auto_confirmed": bool(_notify)},
    )

    # Re-render the photo view to show the new name
    # If seq=1, stay in sequential mode for the next unidentified face
    seq_mode = seq == "1"
    photo_id = _main_mod.get_photo_id_for_face(face_id)
    if photo_id:
        community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
        photo_content = _main_mod.photo_view_content(
            photo_id,
            selected_face_id=face_id,
            is_partial=True,
            identity_id=context_identity_id or None,
            sort_by=sort_by,
            is_admin=True,
            seq_mode=seq_mode,
            community_slug=community_slug,
        )
        oob_toast = Div(
            _main_mod.toast(f'Named as "{name}"!', "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (*photo_content, oob_toast)
    else:
        return _main_mod.toast(f'Named as "{name}"!', "success")


@rt("/api/identity/{identity_id}/rejected")
def get(identity_id: str, request=None):
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
            P("No hidden matches.", cls="text-slate-400 text-sm sm:text-xs italic"),
        )

    crop_files = _main_mod.get_crop_files()
    nav_prefix = _nav_prefix_from_request(request)
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
            cls="px-2 py-0.5 text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/50 rounded hover:bg-indigo-500/20",
            hx_post=f"{nav_prefix}/api/identity/{identity_id}/unreject/{rejected_id}",
            hx_target=f"#rejected-item-{rejected_id}",
            hx_swap="outerHTML",
            type="button",
        )

        items.append(
            Div(
                thumbnail_img,
                Span(name, cls="text-sm sm:text-xs text-slate-300 truncate flex-1 mx-2"),
                unblock_btn,
                id=f"rejected-item-{rejected_id}",
                cls="flex items-center py-1.5 border-b border-slate-700 last:border-0",
            )
        )

    close_list_btn = Button(
        "Hide",
        cls="text-sm sm:text-xs text-slate-400 hover:text-slate-300",
        hx_get=f"{nav_prefix}/api/identity/{identity_id}/rejected/close",
        hx_target=f"#rejected-list-{identity_id}",
        hx_swap="innerHTML",
        type="button",
    )

    return Div(
        Div(
            Span("Hidden Matches", cls="text-sm sm:text-xs font-medium text-slate-400"),
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
def post(source_id: str, target_id: str, sess=None, request=None):
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
    nav_prefix = _nav_prefix_from_request(request)
    is_merged, canonical_id = _main_mod._check_merged_identity(source_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")
    is_merged, canonical_id = _main_mod._check_merged_identity(target_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

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
    _main_mod.save_registry(registry, changed_ids={source_id, target_id})

    # Session 138 FB-013: Invalidate neighbors cache so rejected identity won't reappear
    invalidate_neighbors_cache(source_id)
    invalidate_neighbors_cache(target_id)

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
def post(source_id: str, target_id: str, sess=None, request=None):
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
    nav_prefix = _nav_prefix_from_request(request)
    is_merged, canonical_id = _main_mod._check_merged_identity(source_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")
    is_merged, canonical_id = _main_mod._check_merged_identity(target_id, registry)
    if is_merged:
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

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
    _main_mod.save_registry(registry, changed_ids={source_id, target_id})
    invalidate_neighbors_cache(source_id)
    invalidate_neighbors_cache(target_id)

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
            H3("Name Conflict", cls="text-xl sm:text-lg font-bold text-white mb-4"),
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
                        cls="px-4 py-2 text-sm font-bold bg-indigo-600 text-white rounded hover:bg-indigo-500",
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


def toast_with_merge_undo(message: str, target_id: str, nav_prefix: str = "", target_name: str = "") -> Div:
    """Toast notification with View link and Undo button for merge actions."""
    view_label = f"View {target_name}" if target_name and not target_name.startswith("Unidentified") else "View"
    return Div(
        Span("\u2713", cls="mr-2"),
        Span(message, cls="flex-1"),
        A(
            view_label,
            href=f"{nav_prefix}/person/{target_id}",
            cls="ml-3 px-3 py-1 text-sm font-medium bg-white/20 hover:bg-white/30 rounded transition-colors underline",
        ),
        Button(
            "Undo",
            cls="ml-2 px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"{nav_prefix}/api/identity/{target_id}/undo-merge",
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
    return_to: str = "",
    resolved_name: str = None,
    custom_name: str = None,
    from_focus: bool = False,
    filter: str = "",
    focus_section: str = "",
    override_co_occurrence: bool = False,
    override_reason: str = "",
    from_person_page: bool = False,
    sess=None,
    request=None,
):
    """
    Merge source identity into target identity. Requires admin.

    Enhanced behavior:
    - Auto-corrects merge direction (named identity always survives)
    - Detects name conflicts (both named) and shows resolution modal
    - Records merge_history on target for undo capability
    - Promotes target state if source had higher-trust state
    """
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    try:
        registry = _main_mod.load_registry()
    except Exception:
        logger.exception(f"Merge failed: could not load registry for {source_id} -> {target_id}")
        return Response(
            to_xml(_main_mod.toast("System busy. Please try again.", "warning")),
            status_code=423,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Guard merged identities (UX-038)
    nav_prefix = _nav_prefix_from_request(request)
    is_merged, canonical_id = _main_mod._check_merged_identity(target_id, registry)
    if is_merged:
        logger.warning(f"Merge target {target_id} already merged into {canonical_id}")
        if from_focus:
            return Response(
                to_xml(_main_mod.toast("Target identity was already merged. Refreshing...", "warning")),
                status_code=409,
                headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
            )
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")
    is_merged, canonical_id = _main_mod._check_merged_identity(source_id, registry)
    if is_merged:
        logger.warning(f"Merge source {source_id} already merged into {canonical_id}")
        if from_focus:
            # Remove the already-merged neighbor card from the DOM
            return Response(
                to_xml(
                    Div(
                        Div(id=f"neighbor-{source_id}", hx_swap_oob="delete"),
                        _main_mod.toast("Already merged. Removed from suggestions.", "info"),
                    )
                ),
                headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
            )
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

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

    # PRD-048: Validate override parameters
    allow_co_occurrence = False
    if override_co_occurrence and override_reason:
        valid_reasons = {"collage", "photo_album", "picture_on_wall", "other"}
        if override_reason in valid_reasons:
            allow_co_occurrence = True
            logger.info(f"Co-occurrence override: {source_id} -> {target_id} reason={override_reason} by admin")

    # Attempt merge (with auto-correction)
    result = registry.merge_identities(
        source_id=source_id,
        target_id=target_id,
        user_source=user_source,
        photo_registry=photo_registry,
        resolved_name=actual_resolved_name,
        allow_co_occurrence=allow_co_occurrence,
    )

    if not result["success"]:
        logger.warning(
            f"Merge failed: {source_id} -> {target_id}, reason={result['reason']}, "
            f"from_focus={from_focus}, message={result.get('message', '')}"
        )
        # Handle name conflict -- show resolution modal
        if result["reason"] == "name_conflict":
            return _main_mod._name_conflict_modal(
                target_id,
                source_id,
                result["name_conflict_details"],
                merge_source=source,
            )

        error_messages = {
            "co_occurrence": "Cannot merge: these identities appear in the same photo. Use Override to merge collages.",
            "already_merged": "Already merged. Try refreshing the page.",
        }
        message = error_messages.get(result["reason"], f"Merge failed: {result['reason']}")

        return Response(
            to_xml(_main_mod.toast(message, "error")),
            status_code=409,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Use the actual target/source from the result (may have been swapped)
    actual_target_id = result["target_id"]
    actual_source_id = result["source_id"]

    # Save with targeted Supabase write (FB-069: only write changed identities)
    _main_mod.save_registry(registry, changed_ids={actual_target_id, actual_source_id})

    _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    _log_audit(
        "merge",
        entity_id=actual_target_id,
        user_email=_user.email if _user else None,
        old_value={"source_id": actual_source_id},
        new_value={"merged_into": actual_target_id, "faces_merged": result.get("faces_merged", 0)},
        metadata={"route": "merge_search", "user_source": user_source, "override_co_occurrence": allow_co_occurrence},
    )

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

    # Log the action — include override info for audit trail
    _merge_action = "MERGE_OVERRIDE" if allow_co_occurrence else "MERGE"
    _merge_log_kwargs = {
        "source_identity_id": actual_source_id,
        "target_identity_id": actual_target_id,
        "faces_merged": result["faces_merged"],
        "direction_swapped": result.get("direction_swapped", False),
    }
    if allow_co_occurrence:
        _merge_log_kwargs["override_reason"] = override_reason
        _merge_log_kwargs["co_occurrence_override"] = True
    if from_person_page:
        _merge_log_kwargs["context"] = "person_page"
    _main_mod.log_user_action(_merge_action, **_merge_log_kwargs)

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

    # Toast with undo + link to surviving identity (FB-002)
    merge_toast = _main_mod.toast_with_merge_undo(
        f"Merged {_main_mod._pl(result['faces_merged'], 'face')} into {target_name}.",
        actual_target_id,
        nav_prefix=_nav_prefix_from_request(request),
        target_name=target_name,
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
                cls="text-sm sm:text-xs text-indigo-400 hover:text-indigo-300 underline mt-1",
                hx_get=f"{_nav_prefix_from_request(request)}/api/identity/{actual_target_id}/rename-form",
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
    # FB-028: Use OOB swap for toast so it persists across focus container replacement
    if from_focus:
        nav_prefix = _nav_prefix_from_request(request)
        oob_toast = Div(
            merge_toast,
            hx_swap_oob="beforeend:#toast-container",
        )
        if focus_section == "skipped":
            return (
                _main_mod.get_next_skipped_focus_card(
                    exclude_id=actual_target_id, nav_prefix=nav_prefix, community=_community_from_request(request)
                ),
                oob_toast,
            )
        return (
            _main_mod.get_next_focus_card(
                exclude_id=actual_target_id,
                triage_filter=filter,
                nav_prefix=nav_prefix,
                community=_community_from_request(request),
            ),
            oob_toast,
        )

    nav_prefix = _nav_prefix_from_request(request)
    if source == "similar_page":
        return HttpHeader("HX-Redirect", return_to or f"{nav_prefix}/person/{actual_target_id}")

    # FB-019/FB-020: On person page, replace the neighbor/search-result card with merged indicator
    # instead of replacing the identity card (which doesn't exist on person page).
    # This keeps the Similar panel open after merge.
    if from_person_page:
        # Determine the correct element ID for the merged indicator.
        # Manual search merge targets #search-result-{source_id}, neighbor merge targets #neighbor-{source_id}.
        if source == "manual_search":
            _indicator_id = f"search-result-{source_id}"
        else:
            _indicator_id = f"neighbor-{actual_source_id}"

        merged_indicator = Div(
            Div(
                Span("\u2713 Merged", cls="text-emerald-400 font-bold text-sm"),
                cls="p-3 text-center",
            ),
            id=_indicator_id,
            cls="bg-emerald-900/20 border border-emerald-500/30 rounded-lg mb-2",
            **{"_": "on load wait 2s then transition opacity to 0 over 0.5s then remove me"},
        )

        # Filter OOB elements to avoid deleting the element we just swapped into
        _person_page_oob = [el for el in oob_elements if el.attrs.get("id") != _indicator_id]

        # Wrap toast in OOB so it appears in the toast container (not in the swap target)
        oob_toast = Div(
            merge_toast,
            hx_swap_oob="beforeend:#toast-container",
        )

        return (
            merged_indicator,
            *_person_page_oob,
            oob_toast,
        )

    return (
        _main_mod.identity_card(
            updated_identity, crop_files, lane_color="emerald", show_actions=False, nav_prefix=nav_prefix
        ),
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
            P(
                f"{_main_mod._pl(len(high_matches), 'similar face')} found after merge",
                cls="text-sm sm:text-xs text-slate-400",
            ),
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

    _main_mod.save_registry(registry, changed_ids={identity_id, result["source_id"]})

    _main_mod.log_user_action(
        "UNDO_MERGE",
        target_identity_id=identity_id,
        restored_source_id=result["source_id"],
        faces_removed=result["faces_removed"],
    )

    return _main_mod.toast(f"Merge undone. {_main_mod._pl(result['faces_removed'], 'face')} restored.", "success")


@rt("/api/identity/{identity_id}/bulk-merge")
def post(
    identity_id: str,
    bulk_ids: list[str] = None,
    from_focus: bool = False,
    filter: str = "",
    focus_section: str = "",
    sess=None,
    request=None,
):
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
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

    photo_registry = _main_mod.load_photo_registry()

    merged_count = 0
    total_faces = 0
    failed_details = []  # list of (name, reason)

    _REASON_LABELS = {
        "co_occurrence": "same photo",
        "already_merged": "already merged",
        "name_conflict": "name conflict",
    }

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
                source_ident = _main_mod._safe_get_identity(registry, source_id)
                name = ensure_utf8_display(source_ident.get("name", "")) if source_ident else f"Person {source_id[:8]}"
                reason = _REASON_LABELS.get(result["reason"], result["reason"])
                failed_details.append((name, reason))
        except Exception as e:
            failed_details.append((f"Person {source_id[:8]}", str(e)))

    if merged_count > 0:
        _main_mod.save_registry(registry, changed_ids={identity_id} | set(bulk_ids))
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _log_audit(
            "merge",
            entity_id=identity_id,
            user_email=_user.email if _user else None,
            old_value={"source_ids": bulk_ids},
            new_value={"merged_count": merged_count, "total_faces": total_faces},
            metadata={"route": "bulk_merge"},
        )

    # Build toast message
    # FB-006 (Session 142): Separate "already merged" from real failures
    real_failures = [(n, r) for n, r in failed_details if r != "already merged"]
    already_merged_count = len(failed_details) - len(real_failures)

    if real_failures:
        failed_items = "; ".join(f"{name} ({reason})" for name, reason in real_failures[:5])
        if len(real_failures) > 5:
            failed_items += f" +{len(real_failures) - 5} more"
        msg = f"Merged {merged_count} ({total_faces} faces). {len(real_failures)} blocked: {failed_items}"
        if already_merged_count:
            msg += f" ({already_merged_count} already merged)"
        toast_level = "warning"
    elif already_merged_count and merged_count > 0:
        msg = f"Merged {merged_count} identities ({total_faces} faces)."
        if already_merged_count:
            msg += f" {already_merged_count} were already merged."
        toast_level = "success"
    elif already_merged_count and merged_count == 0:
        msg = f"All {already_merged_count} identities were already merged."
        toast_level = "info"
    else:
        msg = f"Merged {merged_count} identities ({total_faces} faces)."
        toast_level = "success"

    merge_toast = _main_mod.toast(msg, toast_level)

    # If from focus mode, advance to next identity instead of just showing toast
    if from_focus and merged_count > 0:
        nav_prefix = _nav_prefix_from_request(request)
        oob_toast = Div(
            merge_toast,
            hx_swap_oob="beforeend:#toast-container",
        )
        if focus_section == "skipped":
            return (
                _main_mod.get_next_skipped_focus_card(
                    exclude_id=identity_id, nav_prefix=nav_prefix, community=_community_from_request(request)
                ),
                oob_toast,
            )
        return (
            _main_mod.get_next_focus_card(
                exclude_id=identity_id,
                triage_filter=filter,
                nav_prefix=nav_prefix,
                community=_community_from_request(request),
            ),
            oob_toast,
        )

    return merge_toast


@rt("/api/identity/{identity_id}/bulk-reject")
def post(identity_id: str, bulk_ids: list[str] = None, sess=None, request=None):
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
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

    rejected_count = 0
    for target_id in bulk_ids:
        try:
            registry.reject_identity_pair(identity_id, target_id, user_source="web")
            rejected_count += 1
        except Exception:
            pass

    if rejected_count > 0:
        _main_mod.save_registry(registry, changed_ids={identity_id} | set(bulk_ids))
        invalidate_neighbors_cache(identity_id)
        for _bid in bulk_ids:
            invalidate_neighbors_cache(_bid)
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _log_audit(
            "negative_match",
            entity_id=identity_id,
            user_email=_user.email if _user else None,
            old_value={"rejected_ids": bulk_ids[:10]},
            new_value={"rejected_count": rejected_count},
            metadata={"route": "bulk_reject"},
        )

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
                        P("Image unavailable", cls="text-sm sm:text-xs text-slate-400 mt-1"),
                        P(f"ID: {face_id[:12]}...", cls="text-sm sm:text-xs font-data text-slate-500"),
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
            cls="grid grid-cols-1 sm:grid-cols-1 sm:grid-cols-2 md:grid-cols-3 md:grid-cols-4 gap-3",
        ),
        pagination,
        id=f"faces-{identity_id}",
    )


# =============================================================================
# ROUTES - RENAME IDENTITY
# =============================================================================


@rt("/api/identity/{identity_id}/photos")
def get(identity_id: str, index: int = 0, request=None):
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
    nav_prefix = _nav_prefix_from_request(request)
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
                    cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-amber-600 text-white text-sm sm:text-xs px-2 py-0.5 rounded whitespace-nowrap pointer-events-none",
                )
            else:
                dn = ensure_utf8_display(fi.get("name", "")) if fi else ""
                oc = "absolute border border-emerald-500/50 bg-emerald-500/5 group cursor-pointer hover:bg-emerald-500/15"
                lb = (
                    Span(
                        dn or "Unknown",
                        cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-sm sm:text-xs px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none",
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
                    f"then go to url '{nav_prefix}/?section={fi_section}&view=browse#identity-{fi_id}'"
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
            cls="absolute left-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white w-12 h-12 aspect-square rounded-lg flex items-center justify-center transition-colors z-10",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/photos?index={index - 1}",
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
            cls="absolute right-2 top-1/2 -translate-y-1/2 bg-black/60 hover:bg-black/80 text-white w-12 h-12 aspect-square rounded-lg flex items-center justify-center transition-colors z-10",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/photos?index={index + 1}",
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
def get(identity_id: str, request=None):
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

    nav_prefix = _nav_prefix_from_request(request)

    return Form(
        Input(
            name="name",
            value=current_name,
            placeholder="Enter name...",
            cls="border border-slate-600 bg-slate-700 text-slate-200 rounded px-4 py-3 sm:px-2 sm:py-1 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-indigo-400",
            autofocus=True,
        ),
        Button(
            "Save",
            type="submit",
            cls="ml-2 bg-emerald-600 text-white px-4 py-3 sm:px-2 sm:py-1 rounded text-sm hover:bg-emerald-500",
        ),
        Button(
            "Cancel",
            type="button",
            hx_get=f"{nav_prefix}/api/identity/{identity_id}/name-display",
            hx_target=f"#name-{identity_id}",
            hx_swap="outerHTML",
            cls="ml-1 text-slate-400 hover:text-slate-300 text-sm underline",
        ),
        hx_post=f"{nav_prefix}/api/identity/{identity_id}/rename",
        hx_target=f"#name-{identity_id}",
        hx_swap="outerHTML",
        id=f"name-{identity_id}",
        cls="flex items-center",
    )


@rt("/api/identity/{identity_id}/name-display")
def get(identity_id: str, request=None):
    """
    Return the name display component (for cancel button).
    """
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response("Identity not found", status_code=404)

    return _main_mod.name_display(identity_id, identity.get("name"), nav_prefix=_nav_prefix_from_request(request))


@rt("/api/identity/{identity_id}/rename")
def post(identity_id: str, name: str = "", sess=None, request=None):
    """Rename an identity. Requires admin."""
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
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
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

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
        _main_mod.save_registry(registry, changed_ids={identity_id})
        user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _main_mod.log_user_action(
            "RENAME_IDENTITY",
            identity_id=identity_id,
            previous_name=previous_name or "",
            new_name=name,
            admin=user.email if user else "admin",
            source="web",
        )
        _log_audit(
            "rename",
            entity_id=identity_id,
            user_email=user.email if user else None,
            old_value={"name": previous_name},
            new_value={"name": name},
            metadata={"route": "rename"},
        )
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
        _main_mod.name_display(identity_id, name, nav_prefix=_nav_prefix_from_request(request)),
        _main_mod.toast(f"Renamed to '{name}'", "success"),
    )


# =============================================================================
# ROUTES - IDENTITY NOTES
# =============================================================================


@rt("/api/identity/{identity_id}/notes")
def get(identity_id: str, request=None):
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
                Span(n.get("author", ""), cls="text-sm sm:text-xs text-slate-500"),
                Span(n.get("timestamp", "")[:10], cls="text-sm sm:text-xs text-slate-500 ml-2"),
                cls="flex items-center mt-1",
            ),
            cls="p-2 bg-slate-700 rounded mb-1",
        )
        for n in reversed(notes)  # Newest first
    ]

    nav_prefix = _nav_prefix_from_request(request)

    return Div(
        H5("Notes", cls="text-sm font-semibold text-slate-300 mb-2"),
        Div(*note_items) if note_items else P("No notes yet.", cls="text-sm sm:text-xs text-slate-500 italic"),
        # Add note form
        Form(
            Input(
                type="text",
                name="text",
                placeholder="Add a note...",
                cls="w-full px-4 py-3 sm:px-2 sm:py-1.5 text-sm bg-slate-800 border border-slate-600 text-white rounded "
                "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500",
                required=True,
            ),
            Button(
                "Add",
                type="submit",
                cls="mt-1 px-3 py-1 text-sm sm:text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
            ),
            hx_post=f"{nav_prefix}/api/identity/{identity_id}/notes",
            hx_target=f"#notes-{identity_id}",
            hx_swap="innerHTML",
            cls="mt-2",
        ),
        id=f"notes-{identity_id}",
    )


@rt("/api/identity/{identity_id}/notes")
def post(identity_id: str, text: str = "", sess=None, request=None):
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
        _main_mod.save_registry(registry, changed_ids={identity_id})
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
                Span(n.get("author", ""), cls="text-sm sm:text-xs text-slate-500"),
                Span(n.get("timestamp", "")[:10], cls="text-sm sm:text-xs text-slate-500 ml-2"),
                cls="flex items-center mt-1",
            ),
            cls="p-2 bg-slate-700 rounded mb-1",
        )
        for n in reversed(notes)
    ]

    nav_prefix = _nav_prefix_from_request(request)

    return Div(
        H5("Notes", cls="text-sm font-semibold text-slate-300 mb-2"),
        Div(*note_items),
        Form(
            Input(
                type="text",
                name="text",
                placeholder="Add a note...",
                cls="w-full px-4 py-3 sm:px-2 sm:py-1.5 text-sm bg-slate-800 border border-slate-600 text-white rounded "
                "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500",
                required=True,
            ),
            Button(
                "Add",
                type="submit",
                cls="mt-1 px-3 py-1 text-sm sm:text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
            ),
            hx_post=f"{nav_prefix}/api/identity/{identity_id}/notes",
            hx_target=f"#notes-{identity_id}",
            hx_swap="innerHTML",
            cls="mt-2",
        ),
        id=f"notes-{identity_id}",
    )


@rt("/api/identity/{identity_id}/metadata-form")
def get(identity_id: str, sess=None, request=None):
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
        "w-full px-4 py-3 sm:px-2 sm:py-1.5 text-sm bg-slate-700 border border-slate-600 text-white rounded "
        "focus:outline-none focus:ring-1 focus:ring-indigo-400 placeholder-slate-500"
    )

    nav_prefix = _nav_prefix_from_request(request)

    return Div(
        Form(
            Div(
                Div(
                    Label("Display Name", cls="text-sm sm:text-xs text-slate-400"),
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
                    Label("Maiden Name", cls="text-sm sm:text-xs text-slate-400"),
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
                    Label("Qualifier", cls="text-sm sm:text-xs text-slate-400"),
                    Input(
                        type="text",
                        name="generation_qualifier",
                        value=identity.get("generation_qualifier", ""),
                        placeholder="e.g. Sr., Jr.",
                        cls=_input_cls,
                    ),
                    cls="w-24",
                ),
                cls="flex flex-col sm:flex-row gap-3 sm:gap-2 w-full sm:w-auto",
            ),
            Div(
                Div(
                    Label("Birth Year", cls="text-sm sm:text-xs text-slate-400"),
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
                    Label("Death Year", cls="text-sm sm:text-xs text-slate-400"),
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
                    Label("Birthplace", cls="text-sm sm:text-xs text-slate-400"),
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
                    Label("Death Place", cls="text-sm sm:text-xs text-slate-400"),
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
                Label("Relationships", cls="text-sm sm:text-xs text-slate-400"),
                Input(
                    type="text",
                    name="relationship_notes",
                    value=identity.get("relationship_notes", ""),
                    placeholder="e.g. Daughter of X & Y, married to Z",
                    cls=_input_cls,
                ),
            ),
            Div(
                Label("Bio", cls="text-sm sm:text-xs text-slate-400"),
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
                    cls="px-5 py-4 sm:px-3 sm:py-1.5 text-sm sm:text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
                ),
                Button(
                    "Cancel",
                    type="button",
                    cls="px-5 py-4 sm:px-3 sm:py-1.5 text-sm sm:text-xs bg-slate-600 text-slate-300 rounded hover:bg-slate-500",
                    hx_get=f"{nav_prefix}/api/identity/{identity_id}/metadata-display",
                    hx_target=f"#metadata-{identity_id}",
                    hx_swap="innerHTML",
                ),
                cls="flex gap-2 mt-1",
            ),
            hx_post=f"{nav_prefix}/api/identity/{identity_id}/metadata",
            hx_target=f"#metadata-{identity_id}",
            hx_swap="innerHTML",
            cls="space-y-2",
        ),
        _main_mod._place_datalist(),
        id=f"metadata-{identity_id}",
    )


@rt("/api/identity/{identity_id}/metadata-display")
def get(identity_id: str, sess=None, request=None):
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
    request=None,
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
            previous_name = registry.rename_identity(identity_id, display_name.strip(), user_source="admin_web")
            _main_mod.save_registry(registry, changed_ids={identity_id})
            user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
            _main_mod.log_user_action(
                "RENAME_IDENTITY",
                identity_id=identity_id,
                previous_name=previous_name or "",
                new_name=display_name.strip(),
                admin=user.email if user else "admin",
                source="admin_web",
            )
            _log_audit(
                "rename",
                entity_id=identity_id,
                user_email=user.email if user else None,
                old_value={"name": previous_name},
                new_value={"name": display_name.strip()},
                metadata={"route": "metadata"},
            )
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
            _main_mod.save_registry(registry, changed_ids={identity_id})
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
                _main_mod.name_display(
                    identity_id,
                    updated_name,
                    is_admin=True,
                    generation_qualifier=gen_qual,
                    nav_prefix=_nav_prefix_from_request(request),
                ),
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
        P("The 'Turn Over' button is now available on this photo.", cls="text-slate-400 text-sm sm:text-xs mt-1"),
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
        P(
            f"Transform: {new_transform}" if new_transform else "Transform reset.",
            cls="text-sm sm:text-xs text-slate-400",
        ),
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
def post(face_id: str, sess=None, request=None):
    """Detach a face from its identity into a new identity. Requires admin."""
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
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
    _main_mod.save_registry(registry, changed_ids={identity_id, result["to_identity_id"]})

    # Log the action
    _main_mod.log_user_action(
        "DETACH",
        face_id=face_id,
        from_identity_id=identity_id,
        to_identity_id=result["to_identity_id"],
    )
    _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    _log_audit(
        "detach",
        entity_id=identity_id,
        user_email=_user.email if _user else None,
        old_value={"face_id": face_id, "from_identity_id": identity_id},
        new_value={"to_identity_id": result["to_identity_id"]},
        metadata={"route": "detach"},
    )

    # 1. Get crop files for rendering
    crop_files = _main_mod.get_crop_files()
    nav_prefix = _nav_prefix_from_request(request)

    # 2. Render the NEW identity card (detached face's new home)
    new_identity = registry.get_identity(result["to_identity_id"])
    new_card_html = _main_mod.identity_card(
        new_identity,
        crop_files,
        lane_color="amber",  # New identities are PROPOSED
        show_actions=True,
        nav_prefix=nav_prefix,
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
        nav_prefix=nav_prefix,
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
def post(id: str, sess=None, request=None):
    """Log the skip action. Requires admin."""
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    registry = _main_mod.load_registry()
    is_merged, canonical_id = _main_mod._check_merged_identity(id, registry)
    if is_merged:
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")
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
def post(identity_id: str, sess=None, request=None):
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
        _main_mod.save_registry(registry, changed_ids={identity_id})
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)
    nav_prefix = _nav_prefix_from_request(request)

    # Return updated card (now PROPOSED, with full action buttons)
    return (
        _main_mod.identity_card(
            updated_identity, crop_files, lane_color="amber", show_actions=True, nav_prefix=nav_prefix
        ),
        _main_mod.toast("Moved to Proposed for review.", "success"),
    )


@rt("/inbox/{identity_id}/confirm")
def post(
    identity_id: str,
    from_focus: bool = False,
    filter: str = "",
    from_person_page: bool = False,
    merge_target_id: str = "",
    sess=None,
    request=None,
):
    """Confirm identity from INBOX state (INBOX -> CONFIRMED). Requires admin.
    When merge_target_id is provided, also auto-merges into that target (FB-004).
    """
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
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
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    _identity = registry.get_identity(identity_id)

    try:
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
            changed_ids={identity_id},
        )
        _main_mod.log_user_action(
            "CONFIRM",
            identity_id=identity_id,
            identity_name=_identity.get("name", "Unknown"),
            source_state="INBOX",
            context="person_page" if from_person_page else "browse",
        )
        _log_audit(
            "confirm",
            entity_id=identity_id,
            user_email=_user.email if _user else None,
            old_value={"state": _identity.get("state", "INBOX"), "name": _identity.get("name")},
            new_value={"state": "CONFIRMED"},
            metadata={"route": "inbox_confirm"},
        )
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # FB-004: Auto-merge with best match when merge_target_id provided
    merge_result = None
    if merge_target_id:
        try:
            photo_registry = _main_mod.load_photo_registry()
            merge_result = registry.merge_identities(
                source_id=identity_id,
                target_id=merge_target_id,
                user_source="web_review",
                photo_registry=photo_registry,
            )
            if merge_result["success"]:
                actual_target = merge_result["target_id"]
                actual_source = merge_result["source_id"]
                _main_mod.save_registry(registry, changed_ids={actual_target, actual_source})
                _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
                _log_audit(
                    "merge",
                    entity_id=actual_target,
                    user_email=_user.email if _user else None,
                    old_value={"source_id": actual_source},
                    new_value={"merged_into": actual_target, "faces_merged": merge_result.get("faces_merged", 0)},
                    metadata={"route": "inbox_confirm_and_merge", "trigger": "confirm_as_button"},
                )
                _main_mod.log_user_action(
                    "CONFIRM_AND_MERGE",
                    identity_id=identity_id,
                    merge_target_id=merge_target_id,
                    faces_merged=merge_result.get("faces_merged", 0),
                    source_state="INBOX",
                )
                logger.info(
                    "Inbox confirm+merge: %s -> %s, %d faces merged",
                    identity_id[:8],
                    merge_target_id[:8],
                    merge_result.get("faces_merged", 0),
                )
                # Codex P1: Run merge side effects (annotations + recalibration)
                try:
                    _main_mod._fire_recalibration_hook("merge", actual_target, actual_source)
                except Exception:
                    pass
                _main_mod._merge_annotations(actual_source, actual_target)
            else:
                logger.warning(
                    "Inbox confirm succeeded but auto-merge failed: %s -> %s, reason=%s",
                    identity_id[:8],
                    merge_target_id[:8],
                    merge_result.get("reason", "unknown"),
                )
        except Exception:
            logger.exception("Inbox confirm+merge error: %s -> %s", identity_id[:8], merge_target_id[:8])

    # Build toast message
    if merge_result and merge_result.get("success"):
        actual_target = merge_result["target_id"]
        target_identity = registry.get_identity(actual_target)
        target_name = ensure_utf8_display(target_identity.get("name", "identity"))
        toast_msg = f"Confirmed and merged {merge_result.get('faces_merged', 0)} face(s) into {target_name}."
    else:
        toast_msg = "Identity confirmed."
        if merge_target_id and (not merge_result or not merge_result.get("success")):
            reason = merge_result.get("reason", "unknown") if merge_result else "error"
            toast_msg = f"Confirmed, but merge failed ({reason}). You may need to merge manually."

    # If from focus mode, return the next focus card with OOB toast
    if from_focus:
        nav_prefix = _nav_prefix_from_request(request)
        oob_toast = Div(
            _main_mod.toast(toast_msg, "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (
            _main_mod.get_next_focus_card(
                exclude_id=identity_id,
                triage_filter=filter,
                nav_prefix=nav_prefix,
                community=_community_from_request(request),
            ),
            oob_toast,
        )

    # FB-017: On person page, return status update
    if from_person_page:
        return (
            Div(
                Span(
                    "\u2713 CONFIRMED",
                    cls="text-sm sm:text-xs px-2 py-0.5 rounded-full font-medium bg-emerald-500/20 text-emerald-400",
                ),
                id="person-admin-actions",
                cls="flex items-center justify-center gap-2 mb-3",
            ),
            _main_mod.toast(toast_msg, "success"),
        )

    nav_prefix = _nav_prefix_from_request(request)
    crop_files = _main_mod.get_crop_files()

    # If merge succeeded, show surviving identity card
    if merge_result and merge_result.get("success"):
        actual_target = merge_result["target_id"]
        actual_source = merge_result["source_id"]
        surviving = registry.get_identity(actual_target)
        oob_delete = [
            Div(id=f"identity-{actual_source}", hx_swap_oob="delete"),
            Div(id=f"neighbor-{actual_source}", hx_swap_oob="delete"),
        ]
        return (
            _main_mod.identity_card(
                surviving, crop_files, lane_color="emerald", show_actions=False, nav_prefix=nav_prefix
            ),
            _main_mod.toast(toast_msg, "success"),
            *oob_delete,
        )

    updated_identity = registry.get_identity(identity_id)

    # Return updated card (now CONFIRMED)
    return (
        _main_mod.identity_card(
            updated_identity, crop_files, lane_color="emerald", show_actions=False, nav_prefix=nav_prefix
        ),
        _main_mod.toast(toast_msg, "success"),
    )


@rt("/inbox/{identity_id}/reject")
def post(
    identity_id: str,
    from_focus: bool = False,
    filter: str = "",
    from_person_page: bool = False,
    sess=None,
    request=None,
):
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
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

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
        registry.reject_identity(identity_id, user_source="web_review")
        _main_mod.save_registry(registry, changed_ids={identity_id})
        _main_mod.log_user_action(
            "REJECT",
            identity_id=identity_id,
            identity_name=_identity.get("name", "Unknown"),
            source_state="INBOX",
            context="person_page" if from_person_page else "browse",
        )
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # If from focus mode, return the next focus card with OOB toast
    if from_focus:
        nav_prefix = _nav_prefix_from_request(request)
        oob_toast = Div(
            _main_mod.toast("Identity rejected.", "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (
            _main_mod.get_next_focus_card(
                exclude_id=identity_id,
                triage_filter=filter,
                nav_prefix=nav_prefix,
                community=_community_from_request(request),
            ),
            oob_toast,
        )

    # FB-017: On person page, return status update instead of full identity card
    if from_person_page:
        return (
            Div(
                Span(
                    "\u2717 REJECTED",
                    cls="text-sm sm:text-xs px-2 py-0.5 rounded-full font-medium bg-red-500/20 text-red-400",
                ),
                id="person-admin-actions",
                cls="flex items-center justify-center gap-2 mb-3",
            ),
            _main_mod.toast("Identity rejected.", "success"),
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)
    nav_prefix = _nav_prefix_from_request(request)

    # Return updated card (now REJECTED)
    return (
        _main_mod.identity_card(
            updated_identity, crop_files, lane_color="rose", show_actions=False, nav_prefix=nav_prefix
        ),
        _main_mod.toast("Identity rejected.", "success"),
    )


@rt("/identity/{identity_id}/skip")
def post(
    identity_id: str,
    from_focus: bool = False,
    filter: str = "",
    from_person_page: bool = False,
    sess=None,
    request=None,
):
    """
    Skip identity (defer for later review). Requires admin.

    Works from INBOX or PROPOSED state -> SKIPPED.
    """
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
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
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    try:
        identity = registry.get_identity(identity_id)
        registry.skip_identity(identity_id, user_source="web_review")
        _main_mod.save_registry(registry, changed_ids={identity_id})
        _main_mod.log_user_action(
            "SKIP",
            identity_id=identity_id,
            identity_name=identity.get("name", "Unknown"),
            context="person_page" if from_person_page else "browse",
        )
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _log_audit(
            "skip",
            entity_id=identity_id,
            user_email=_user.email if _user else None,
            old_value={"state": identity.get("state", "INBOX"), "name": identity.get("name")},
            new_value={"state": "SKIPPED"},
            metadata={"route": "skip"},
        )
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # If from focus mode, return the next focus card with OOB toast
    if from_focus:
        nav_prefix = _nav_prefix_from_request(request)
        oob_toast = Div(
            _main_mod.toast("Skipped for later.", "info"),
            hx_swap_oob="beforeend:#toast-container",
        )
        return (
            _main_mod.get_next_focus_card(
                exclude_id=identity_id,
                triage_filter=filter,
                nav_prefix=nav_prefix,
                community=_community_from_request(request),
            ),
            oob_toast,
        )

    # FB-017: On person page, return status update instead of full identity card
    if from_person_page:
        return (
            Div(
                Span(
                    "\u23f8 SKIPPED",
                    cls="text-sm sm:text-xs px-2 py-0.5 rounded-full font-medium bg-amber-500/20 text-amber-400",
                ),
                id="person-admin-actions",
                cls="flex items-center justify-center gap-2 mb-3",
            ),
            _main_mod.toast("Skipped for later.", "info"),
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)
    nav_prefix = _nav_prefix_from_request(request)

    return (
        _main_mod.identity_card(
            updated_identity, crop_files, lane_color="stone", show_actions=False, nav_prefix=nav_prefix
        ),
        _main_mod.toast("Skipped for later.", "info"),
    )


# =============================================================================
# ROUTES — ADMIN FORCE STATE CHANGE
# =============================================================================


@rt("/api/admin/force-state/{identity_id}/{new_state}")
def post(identity_id: str, new_state: str, sess=None, request=None):
    """Force an identity to a specific state. Admin only.

    Used for data integrity fixes when normal state transitions are blocked
    (e.g., reverting a wrongly CONFIRMED identity back to INBOX/SKIPPED).
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    valid_states = {"INBOX", "PROPOSED", "CONFIRMED", "SKIPPED", "REJECTED"}
    if new_state not in valid_states:
        return Response(
            to_xml(_main_mod.toast(f"Invalid state: {new_state}", "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    registry = _main_mod.load_registry()
    try:
        identity = registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    old_state = identity.get("state", "UNKNOWN")
    if old_state == new_state:
        return _main_mod.toast(f"State already {new_state}", "info")

    registry.force_state(
        identity_id,
        new_state,
        user_source="admin_force_state",
        reason="data_integrity_fix",
    )
    _main_mod.save_registry(registry, changed_ids={identity_id})

    import logging

    logging.getLogger(__name__).warning(f"ADMIN FORCE STATE: {identity_id} {old_state} -> {new_state}")

    return _main_mod.toast(f"State changed: {old_state} → {new_state}", "success")


# =============================================================================
# ROUTES — SKIPPED FOCUS MODE ACTIONS
# =============================================================================


@rt("/api/skipped/{identity_id}/focus-skip")
def post(identity_id: str, sess=None, request=None):
    """Advance to next identity in skipped focus mode without taking action."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    registry = _main_mod.load_registry()
    is_merged, canonical_id = _main_mod._check_merged_identity(identity_id, registry)
    if is_merged:
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")
    return (
        _main_mod.get_next_skipped_focus_card(
            exclude_id=identity_id,
            nav_prefix=_nav_prefix_from_request(request),
            community=_community_from_request(request),
        ),
        _main_mod.toast("Skipped for now.", "info"),
    )


@rt("/api/skipped/{identity_id}/reject-suggestion")
def post(identity_id: str, suggestion_id: str = "", sess=None, request=None):
    """Reject a suggestion for a skipped identity and advance to next."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if suggestion_id:
        try:
            registry = _main_mod.load_registry()
            registry.reject_identity_pair(identity_id, suggestion_id, user_source="skipped_focus")
            _main_mod.save_registry(registry, changed_ids={identity_id, suggestion_id})
            _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
            _log_audit(
                "negative_match",
                entity_id=identity_id,
                user_email=_user.email if _user else None,
                old_value={"suggestion_id": suggestion_id},
                metadata={"route": "skipped_focus"},
            )
        except (KeyError, ValueError):
            # If reject fails, just advance — don't block the user
            pass

    # Toast with undo for reject action
    reject_toast = Div(
        Span("✗", cls="mr-2"),
        Span("Suggestion rejected. Moving to next.", cls="flex-1"),
        Button(
            "Undo",
            cls="ml-3 px-4 py-3 sm:px-2 sm:py-1 text-sm sm:text-xs font-bold bg-white/20 hover:bg-white/30 rounded transition-colors",
            hx_post=f"{_nav_prefix_from_request(request)}/api/identity/{identity_id}/unreject/{suggestion_id}",
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
        _main_mod.get_next_skipped_focus_card(
            exclude_id=identity_id,
            nav_prefix=_nav_prefix_from_request(request),
            community=_community_from_request(request),
        ),
        reject_toast,
    )


@rt("/api/skipped/{identity_id}/name-and-confirm")
def post(identity_id: str, name: str = "", sess=None, request=None):
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
        previous_name = registry.rename_identity(identity_id, name, user_source="web_review")
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
            changed_ids={identity_id},
        )
    except (KeyError, ValueError) as e:
        return Response(
            to_xml(_main_mod.toast(f"Cannot confirm: {str(e)}", "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    _main_mod.log_user_action(
        "CONFIRM_NAMED",
        identity_id=identity_id,
        name=name,
        previous_name=previous_name or "",
        admin=_user.email if _user else "admin",
    )
    _log_audit(
        "confirm",
        entity_id=identity_id,
        user_email=_user.email if _user else None,
        old_value={"name": previous_name, "state": "SKIPPED"},
        new_value={"name": name, "state": "CONFIRMED"},
        metadata={"route": "name_and_confirm"},
    )

    return (
        _main_mod.get_next_skipped_focus_card(
            exclude_id=identity_id,
            nav_prefix=_nav_prefix_from_request(request),
            community=_community_from_request(request),
        ),
        _main_mod.toast(f"Confirmed as {name}!", "success"),
    )


@rt("/identity/{identity_id}/reset")
def post(identity_id: str, sess=None, request=None):
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
        nav_prefix = _nav_prefix_from_request(request)
        return HttpHeader("HX-Redirect", f"{nav_prefix}/person/{canonical_id}")

    try:
        registry.get_identity(identity_id)
    except KeyError:
        return Response(
            to_xml(_main_mod.toast("Identity not found.", "error")),
            status_code=404,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    _prev_identity = registry.get_identity(identity_id)
    _prev_state = _prev_identity.get("state", "INBOX")
    try:
        registry.reset_identity(identity_id, user_source="web_review")
        _main_mod.save_registry(registry, changed_ids={identity_id})
        _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        _log_audit(
            "reset",
            entity_id=identity_id,
            user_email=_user.email if _user else None,
            old_value={"state": _prev_state, "name": _prev_identity.get("name")},
            new_value={"state": "INBOX"},
            metadata={"route": "reset"},
        )
    except ValueError as e:
        return Response(
            to_xml(_main_mod.toast(str(e), "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    crop_files = _main_mod.get_crop_files()
    updated_identity = registry.get_identity(identity_id)
    nav_prefix = _nav_prefix_from_request(request)

    return (
        _main_mod.identity_card(
            updated_identity, crop_files, lane_color="blue", show_actions=True, nav_prefix=nav_prefix
        ),
        _main_mod.toast("Returned to Inbox.", "info"),
    )


# ---------------------------------------------------------------------------
# Co-occurrence preview — shows shared photo before override merge
# ---------------------------------------------------------------------------


@rt("/api/identity/{target_id}/co-occurrence-preview/{neighbor_id}")
def get(
    target_id: str,
    neighbor_id: str,
    sess=None,
    request=None,
    from_focus: bool = False,
    filter: str = "",
    focus_section: str = "",
    from_person_page: bool = False,
):
    """Preview the shared photo between two co-occurring identities.

    Shows the photo with face bounding box overlays:
    - Target identity faces highlighted in amber
    - Neighbor identity faces highlighted in indigo

    Admin-only. Returns 404 if no shared photo found.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    registry = _main_mod.load_registry()
    photo_registry = _main_mod.load_photo_registry()

    # Find the shared photo filename
    shared_filename = _main_mod.find_shared_photo_filename(target_id, neighbor_id, registry, photo_registry)
    if not shared_filename:
        return Response(
            to_xml(
                Div(
                    P("No shared photo found between these identities.", cls="text-amber-400 text-sm italic py-2"),
                    cls="co-occurrence-preview",
                )
            ),
            status_code=404,
        )

    nav_prefix = _nav_prefix_from_request(request)

    # Get photo dimensions and URL
    width, height = _main_mod.get_photo_dimensions(shared_filename)
    photo_url_str = photo_url(shared_filename)
    has_dimensions = width > 0 and height > 0

    # Find the photo_id to get face data from cache
    photo_id = _main_mod.generate_photo_id(shared_filename)
    photo_meta = _main_mod.get_photo_metadata(photo_id)

    # Get face IDs for each identity
    target_face_ids = set(registry.get_all_face_ids(target_id))
    neighbor_face_ids = set(registry.get_all_face_ids(neighbor_id))

    # Build face overlays
    face_overlays = []
    if has_dimensions and photo_meta:
        for face_data in photo_meta.get("faces", []):
            face_id = face_data["face_id"]
            bbox = face_data.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox

            left_pct = (x1 / width) * 100
            top_pct = (y1 / height) * 100
            width_pct = ((x2 - x1) / width) * 100
            height_pct = ((y2 - y1) / height) * 100

            # Color coding: amber for target, indigo for neighbor, slate for others
            if face_id in target_face_ids:
                overlay_cls = "border-2 border-amber-400 bg-amber-400/25"
                label = "Target"
            elif face_id in neighbor_face_ids:
                overlay_cls = "border-2 border-indigo-400 bg-indigo-400/25"
                label = "Neighbor"
            else:
                overlay_cls = "border-2 border-dashed border-slate-400/40 bg-slate-400/5"
                label = ""

            # Get identity name for tooltip
            identity = _main_mod.get_identity_for_face(registry, face_id)
            raw_name = identity.get("name", "Unidentified") if identity else "Unidentified"
            display_name = ensure_utf8_display(raw_name)

            tooltip_text = f"{display_name} ({label})" if label else display_name

            overlay = Div(
                Span(
                    tooltip_text,
                    cls="absolute -top-7 left-1/2 -translate-x-1/2 bg-stone-800 text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10",
                ),
                cls=f"absolute cursor-pointer transition-all group {overlay_cls}",
                style=f"left: {left_pct:.2f}%; top: {top_pct:.2f}%; width: {width_pct:.2f}%; height: {height_pct:.2f}%;",
                title=tooltip_text,
                data_face_id=face_id,
            )
            face_overlays.append(overlay)

    # Build the override merge URL with all necessary params
    focus_suffix = ""
    if from_focus:
        _focus_filter = f"&filter={filter}" if filter else ""
        _focus_section = f"&focus_section={focus_section}" if focus_section else ""
        focus_suffix = f"?from_focus=true{_focus_filter}{_focus_section}"
    _override_sep = "&" if focus_suffix else "?"
    _person_page_param = "&from_person_page=true" if from_person_page else ""
    override_url = (
        f"{nav_prefix}/api/identity/{target_id}/merge/{neighbor_id}"
        f"{focus_suffix}{_override_sep}override_co_occurrence=true"
        f"&override_reason=collage&source=web{_person_page_param}"
    )

    # Determine merge target for the confirm button
    if from_focus and focus_section == "skipped":
        merge_target = "#skipped-focus-container"
    elif from_focus:
        merge_target = "#focus-container"
    elif from_person_page:
        merge_target = f"#neighbor-{neighbor_id}"
    else:
        merge_target = f"#identity-{target_id}"

    # Legend
    legend = Div(
        Span("", cls="inline-block w-3 h-3 border-2 border-amber-400 bg-amber-400/25 rounded-sm mr-1"),
        Span("Target", cls="text-xs text-amber-400 mr-3"),
        Span("", cls="inline-block w-3 h-3 border-2 border-indigo-400 bg-indigo-400/25 rounded-sm mr-1"),
        Span("Neighbor", cls="text-xs text-indigo-400"),
        cls="flex items-center mt-2 mb-1",
    )

    return Div(
        Div(
            P(
                "These faces appear in the same photo. Override only if this is a collage, photo-of-album, or composite image.",
                cls="text-amber-400 text-xs mb-2",
            ),
            # Photo with overlays
            Div(
                Img(
                    src=photo_url_str,
                    cls="max-w-full max-h-64 object-contain rounded",
                    alt=f"Shared photo: {shared_filename}",
                ),
                *face_overlays,
                cls="relative inline-block",
            )
            if has_dimensions
            else Div(
                Img(
                    src=photo_url_str,
                    cls="max-w-full max-h-64 object-contain rounded",
                    alt=f"Shared photo: {shared_filename}",
                ),
                cls="inline-block",
            ),
            legend,
            P(shared_filename, cls="text-xs text-slate-500 mt-1 truncate"),
            cls="bg-slate-800 rounded p-3 mt-2",
        ),
        Div(
            Button(
                "Cancel",
                cls="px-3 py-1 text-sm font-bold border border-slate-500 text-slate-400 rounded hover:bg-slate-600",
                aria_label="Cancel override",
                **{"_": "on click remove closest .co-occurrence-preview"},
            ),
            Button(
                "Confirm Override & Merge",
                cls="px-3 py-1 text-sm font-bold bg-amber-700 hover:bg-amber-600 text-white rounded disabled:opacity-50",
                hx_post=override_url,
                hx_target=merge_target,
                hx_swap="outerHTML",
                hx_disabled_elt="this",
                aria_label="Confirm override and merge these identities",
                **{"_": "on click put 'Merging...' into me"},
            ),
            cls="flex items-center gap-2 mt-2",
        ),
        cls="co-occurrence-preview",
    )


# ---------------------------------------------------------------------------
# Hero Face Picker — Set Primary Face (Session 141 Track B)
# ---------------------------------------------------------------------------


@rt("/api/identity/{identity_id}/set-primary-face/{face_id:path}")
def post(identity_id: str, face_id: str, sess=None, request=None):
    """Set a face as the hero thumbnail for an identity. Admin-only."""
    origin_err = _check_origin(request)
    if origin_err:
        return origin_err
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

    # Validate the face belongs to this identity
    all_face_ids = list(identity.get("anchor_ids", [])) + list(identity.get("candidate_ids", []))
    if face_id not in all_face_ids:
        return Response(
            to_xml(_main_mod.toast("Face does not belong to this identity.", "error")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    # Set primary_face_id on the identity (directly on internal dict — Lesson 36)
    registry._identities[identity_id]["primary_face_id"] = face_id
    registry._identities[identity_id]["updated_at"] = (
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    )

    _main_mod.save_registry(registry, changed_ids={identity_id})
    _main_mod.log_user_action(
        "SET_PRIMARY_FACE",
        identity_id=identity_id,
        identity_name=identity.get("name", "Unknown"),
        context=f"face_id={face_id}",
    )

    return _main_mod.toast(
        f"Set hero face for {identity.get('name', 'this person')}",
        "success",
    )
