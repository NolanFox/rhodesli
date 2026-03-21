"""
Match mode and FaceCompare routes extracted from app/main.py.

All /api/match/*, /facecompare/*, /api/facecompare/*, /uploads/facecompare/* routes
plus match/facecompare-exclusive helpers.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SAFE_UPLOAD_ID = re.compile(r"^[a-zA-Z0-9\-_]+$")

import numpy as np
from fasthtml.common import *
from starlette.datastructures import UploadFile
from starlette.responses import FileResponse, HTMLResponse

from starlette.responses import Response as StarletteResponse

from core.registry import IdentityState
from core.config import DATA_DIR
from core.ui_safety import ensure_utf8_display
from core import storage
from app.rate_limit import check_rate_limit

# Import route decorator only (bound once, never reassigned)
from app.main import rt

# All other main.py functions accessed via module reference
# so that test patches on app.main.X work correctly
import app.main as _main_mod
from app.audit import _log_audit

logger = logging.getLogger(__name__)


def _log_match_decision(identity_a: str, identity_b: str, decision: str, confidence: int, sess=None):
    """
    Log a match decision for audit trail and future ML training.

    Appends to data/match_decisions.jsonl (one JSON object per line).
    """
    import json as _json
    from datetime import datetime, timezone

    user_email = ""
    if sess:
        user = _main_mod.get_current_user(sess)
        if user:
            user_email = user.email

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "identity_a": identity_a,
        "identity_b": identity_b,
        "decision": decision,
        "confidence_pct": confidence,
        "user": user_email,
    }

    log_path = _main_mod.data_path / "match_decisions.jsonl"
    try:
        with open(log_path, "a") as f:
            f.write(_json.dumps(entry) + "\n")
    except Exception as e:
        print(f"[match] Failed to log decision: {e}")


def _get_best_match_pair(triage_filter: str = ""):
    """
    Find the best pair of identities to show in match mode.

    Returns (identity_a, identity_b, distance) or None if no pairs available.

    Args:
        triage_filter: Optional filter to scope pairs:
            - "ready": Only proposal pairs (skip NN fallback)
            - "rediscovered": Only pairs where source has promoted_from
            - "unmatched": Skip proposals, NN search only for non-proposal faces
            - "": All pairs (default behavior)

    Priority:
    1. Clustering proposals (pre-computed, highest confidence first)
    2. Live nearest-neighbor search (fallback when proposals exhausted)
    """
    registry = _main_mod.load_registry()
    face_data = _main_mod.get_face_data()
    photo_registry = _main_mod.load_photo_registry()

    ids_with_proposals = _main_mod._get_identities_with_proposals()

    # Priority 1: Check clustering proposals (skip for "unmatched" filter)
    if triage_filter != "unmatched":
        proposals_data = _main_mod._load_proposals()
        for proposal in proposals_data.get("proposals", []):
            source_id = proposal["source_identity_id"]
            target_id = proposal["target_identity_id"]
            try:
                source = registry.get_identity(source_id)
                target = registry.get_identity(target_id)
            except KeyError:
                continue
            if not source or not target:
                continue
            # Skip if already merged or resolved
            if source.get("merged_into") or target.get("merged_into"):
                continue
            # Skip confirmed-confirmed pairs (already resolved)
            if source.get("state") == "CONFIRMED" and target.get("state") == "CONFIRMED":
                continue
            # Apply rediscovered filter: source must have promoted_from
            if triage_filter == "rediscovered" and not source.get("promoted_from"):
                continue
            # Valid proposal — return as match pair
            neighbor_info = {
                "identity_id": target_id,
                "name": target.get("name", "Unknown"),
                "state": target.get("state", ""),
                "distance": proposal["distance"],
                "face_count": len(target.get("anchor_ids", []) + target.get("candidate_ids", [])),
                "confidence": proposal.get("confidence", ""),
                "from_proposal": True,
            }
            return (source, neighbor_info, proposal["distance"])

    # Priority 2: Fallback to live nearest-neighbor search
    # Skip for "ready" filter (only proposals matter)
    if triage_filter == "ready":
        return None

    inbox = registry.list_identities(state=IdentityState.INBOX)
    proposed = registry.list_identities(state=IdentityState.PROPOSED)
    to_review = inbox + proposed

    # Apply filter to NN candidates
    if triage_filter == "rediscovered":
        to_review = [i for i in to_review if i.get("promoted_from") is not None]
    elif triage_filter == "unmatched":
        to_review = [
            i for i in to_review if i.get("identity_id", "") not in ids_with_proposals and not i.get("promoted_from")
        ]

    if len(to_review) < 2:
        return None

    best_pair = None
    best_distance = float("inf")

    to_review.sort(key=lambda x: len(x.get("anchor_ids", []) + x.get("candidate_ids", [])), reverse=True)

    for identity in to_review[:20]:
        try:
            from core.neighbors import find_nearest_neighbors

            neighbors = find_nearest_neighbors(identity["identity_id"], registry, photo_registry, face_data, limit=1)
            if neighbors and neighbors[0]["distance"] < best_distance:
                best_distance = neighbors[0]["distance"]
                best_pair = (identity, neighbors[0], best_distance)
        except Exception:
            continue

    return best_pair


@rt("/api/match/next-pair")
def get(filter: str = "", sess=None, request=None):
    """
    Get the next pair of faces to compare in Match mode.

    Returns an HTMX partial with two large face crops side by side,
    confidence bar, clickable photos, and action buttons.

    Args:
        filter: Triage filter (ready/rediscovered/unmatched) to scope pairs.
    """
    pair = _get_best_match_pair(triage_filter=filter)

    if pair is None:
        _back_url = f"/?section=to_review&view=focus&filter={filter}" if filter else "/?section=to_review&view=focus"
        return Div(
            H3("No more pairs to match!", cls="text-lg font-medium text-white"),
            P("All available identities have been reviewed.", cls="text-slate-400 mt-2"),
            A(
                "Back to Focus mode",
                href=_back_url,
                cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium",
            ),
            cls="text-center py-12",
        )

    identity_a, neighbor_b, distance = pair
    identity_id_a = identity_a["identity_id"]
    identity_id_b = neighbor_b["identity_id"]

    # Community context for URL generation (FB-001)
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    crop_files = _main_mod.get_crop_files()

    # Get face data for both identities
    def _get_face_info(identity_data):
        face_ids = identity_data.get("anchor_ids", []) + identity_data.get("candidate_ids", [])
        if not face_ids:
            return None, None, None
        first = face_ids[0]
        fid = first if isinstance(first, str) else first.get("face_id", "")
        crop_url = _main_mod.resolve_face_image_url(fid, crop_files)
        photo_id = _main_mod.get_photo_id_for_face(fid)
        return fid, crop_url, photo_id

    face_id_a, crop_url_a, photo_id_a = _get_face_info(identity_a)
    try:
        registry = _main_mod.load_registry()
        identity_b_full = registry.get_identity(identity_id_b)
        face_id_b, crop_url_b, photo_id_b = _get_face_info(identity_b_full)
    except KeyError:
        face_id_b, crop_url_b, photo_id_b = None, None, None

    name_a = ensure_utf8_display(identity_a.get("name")) or f"Person {identity_id_a[:8]}..."
    name_b = ensure_utf8_display(neighbor_b.get("name")) or f"Person {identity_id_b[:8]}..."
    faces_a = len(identity_a.get("anchor_ids", []) + identity_a.get("candidate_ids", []))
    faces_b = neighbor_b.get("face_count", 0)

    # Confidence calculation (inverse distance, clamped 0-100)
    # Unified confidence scoring (AD-200)
    from core.confidence import compute_face_confidence

    _conf = compute_face_confidence(distance)
    confidence_pct = _conf["confidence_pct"]

    # Color based on confidence
    if confidence_pct >= 70:
        bar_color = "bg-emerald-500"
        conf_label = "High"
        conf_text_cls = "text-emerald-400"
    elif confidence_pct >= 40:
        bar_color = "bg-amber-500"
        conf_label = "Medium"
        conf_text_cls = "text-amber-400"
    else:
        bar_color = "bg-red-500"
        conf_label = "Low"
        conf_text_cls = "text-red-400"

    # Build clickable face card
    def _face_card(name, crop_url, face_id, photo_id, face_count, iid=None):
        img_el = (
            Img(src=crop_url or "", alt=name, cls="w-full h-full object-cover")
            if crop_url
            else Span("?", cls="text-6xl text-slate-500")
        )

        # Make clickable to view source photo (with identity nav context) — FB-001: use nav_prefix
        if photo_id:
            _fc_url = (
                f"{nav_prefix}/photo/{photo_id}/partial?face={face_id}"
                if face_id
                else f"{nav_prefix}/photo/{photo_id}/partial"
            )
            if iid:
                _fc_url += f"&identity_id={iid}"
            face_el = Button(
                Div(
                    img_el,
                    cls="w-full aspect-square rounded-xl overflow-hidden bg-slate-700 flex items-center justify-center",
                ),
                cls="p-0 bg-transparent cursor-pointer hover:ring-2 hover:ring-indigo-400 rounded-xl transition-all w-full",
                hx_get=_fc_url,
                hx_target="#photo-modal-content",
                **{"_": "on click remove .hidden from #photo-modal"},
                type="button",
                title="Click to view source photo",
            )
        else:
            face_el = Div(
                img_el,
                cls="w-full aspect-square rounded-xl overflow-hidden bg-slate-700 flex items-center justify-center",
            )

        # FB-002: Source photo thumbnail
        source_photo_el = None
        if photo_id:
            photo_meta = _main_mod.get_photo_metadata(photo_id)
            if photo_meta and photo_meta.get("filename"):
                source_url = storage.get_photo_url(photo_meta["filename"])
                source_photo_el = A(
                    Img(
                        src=source_url,
                        alt="Source photo",
                        cls="w-full h-20 object-cover rounded-lg border border-slate-600",
                        loading="lazy",
                    ),
                    href=f"{nav_prefix}/photo/{photo_id}",
                    cls="block mt-2",
                    title="View source photo",
                    data_testid="match-source-photo",
                )

        # FB-003: Photo and person page links
        links = []
        if photo_id:
            links.append(
                A(
                    "View Photo",
                    href=f"{nav_prefix}/photo/{photo_id}",
                    cls="text-xs text-indigo-400 hover:text-indigo-300",
                    data_testid="match-photo-link",
                )
            )
        if iid:
            links.append(
                A(
                    "View Person",
                    href=f"{nav_prefix}/person/{iid}",
                    cls="text-xs text-indigo-400 hover:text-indigo-300",
                    data_testid="match-person-link",
                )
            )
        links_el = Div(*links, cls="flex gap-3 justify-center mt-1") if links else None

        return Div(
            face_el,
            source_photo_el,
            P(name, cls="text-sm font-medium text-slate-200 mt-3 text-center truncate"),
            P(f"{face_count} face{'s' if face_count != 1 else ''}", cls="text-xs text-slate-500 text-center"),
            links_el,
            cls="flex-1 max-w-[280px]",
        )

    # Build filter query suffix for URL propagation
    filter_suffix = f"&filter={filter}" if filter else ""

    return Div(
        # Confidence bar
        Div(
            Div(
                Span(f"Match Confidence: {confidence_pct}%", cls=f"text-sm font-medium {conf_text_cls}"),
                Span(f"({conf_label})", cls=f"text-xs {conf_text_cls} ml-1"),
                Span(f"dist: {distance:.3f}", cls="text-xs font-data text-slate-500 ml-3"),
                cls="flex items-center justify-center mb-2",
            ),
            # Progress bar
            Div(
                Div(cls=f"{bar_color} h-full rounded-full transition-all", style=f"width: {confidence_pct}%"),
                cls="w-full max-w-md mx-auto h-2 bg-slate-700 rounded-full overflow-hidden",
            ),
            cls="mb-6",
        ),
        # Side by side faces — large display
        Div(
            _face_card(name_a, crop_url_a, face_id_a, photo_id_a, faces_a, iid=identity_id_a),
            # VS divider
            Div(Span("vs", cls="text-slate-500 text-xl font-bold"), cls="flex items-center justify-center px-6 pt-8"),
            _face_card(name_b, crop_url_b, face_id_b, photo_id_b, faces_b, iid=identity_id_b),
            cls="flex flex-col sm:flex-row items-center sm:items-start justify-center gap-2",
        ),
        # Action buttons -- role-aware
        Div(
            Button(
                "Suggest Same" if _main_mod._get_user_role(sess) == "contributor" else "Same Person",
                cls=f"px-8 py-3 text-sm font-bold {'bg-purple-600 hover:bg-purple-500' if _main_mod._get_user_role(sess) == 'contributor' else 'bg-emerald-600 hover:bg-emerald-500'} text-white rounded-lg transition-colors min-h-[44px]",
                hx_post=f"{nav_prefix}/api/match/decide?identity_a={identity_id_a}&identity_b={identity_id_b}&decision=same&confidence={confidence_pct}{filter_suffix}",
                hx_target="#match-pair-container",
                hx_swap="innerHTML",
                type="button",
                id="match-btn-same",
                data_auth_action="identify these faces",
                # FB-006: Loading feedback — disable + show merging text on click
                **{"_": "on click add .opacity-50 to me then put 'Merging...' into me then add @disabled to me"},
                data_testid="match-btn-same",
            ),
            Button(
                "Different People",
                cls="px-8 py-3 text-sm font-bold border-2 border-red-500 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors min-h-[44px]",
                hx_post=f"{nav_prefix}/api/match/decide?identity_a={identity_id_a}&identity_b={identity_id_b}&decision=different&confidence={confidence_pct}{filter_suffix}",
                hx_target="#match-pair-container",
                hx_swap="innerHTML",
                type="button",
                id="match-btn-diff",
            ),
            Button(
                "Skip",
                cls="px-4 py-3 text-sm text-slate-400 hover:text-slate-300 transition-colors min-h-[44px]",
                hx_get=f"{nav_prefix}/api/match/next-pair?filter={filter}"
                if filter
                else f"{nav_prefix}/api/match/next-pair",
                hx_target="#match-pair-container",
                hx_swap="innerHTML",
                type="button",
                id="match-btn-skip",
            ),
            Button(
                "Share This Match",
                cls="px-3 py-2 text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-600/50 rounded-lg transition-colors min-h-[44px]",
                data_action="share-photo",
                data_share_url=f"{_main_mod.SITE_URL}/identify/{identity_id_a}/match/{identity_id_b}",
                data_share_title="Are these the same person?",
                data_share_text="Help us confirm if these two faces from the Rhodesli Heritage Archive are the same person.",
                type="button",
            ),
            Span(
                "Keyboard: Y N S",
                cls="text-xs text-slate-600 hidden sm:inline",
                title="Y=Same Person, N=Different People, S=Skip",
            ),
            cls="flex flex-wrap items-center justify-center gap-4 mt-8 pt-4 border-t border-slate-700",
        ),
        # Community response summary (if any)
        _main_mod._match_community_summary(identity_id_a, identity_id_b),
        cls="match-pair",
    )


@rt("/api/match/decide")
def post(identity_a: str, identity_b: str, decision: str, confidence: int = 0, filter: str = "", sess=None):
    """
    Record a match decision, log it, and return the next pair.

    Args:
        identity_a: First identity ID
        identity_b: Second identity ID
        decision: "same" (merge) or "different" (reject pair)
        confidence: Match confidence percentage at time of decision
    """
    # Allow contributors to suggest (they can't merge but can say "same")
    user_role = _main_mod._get_user_role(sess)
    if user_role == "contributor":
        denied = _main_mod._check_contributor(sess)
    else:
        denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    # Log the decision
    _log_match_decision(identity_a, identity_b, decision, confidence, sess)

    # Contributors create merge suggestions instead of executing merges
    if decision == "same" and user_role == "contributor":
        user = _main_mod.get_current_user(sess)
        _main_mod._create_merge_suggestion(
            target_id=identity_a,
            source_id=identity_b,
            submitted_by=user.email if user else "contributor",
            confidence="certain" if confidence >= 80 else "likely" if confidence >= 50 else "guess",
            reason=f"Matched in match mode (confidence: {confidence}%)",
        )
        oob_toast = Div(
            _main_mod.toast("Suggestion recorded! An admin will review it.", "success"),
            hx_swap_oob="beforeend:#toast-container",
        )
        counter_script = Div(
            Script("if (typeof incrementMatchCount === 'function') incrementMatchCount();"),
            hx_swap_oob="beforeend:body",
        )
        pair = _get_best_match_pair(triage_filter=filter)
        if pair is None:
            return (
                Div(
                    H3("No more pairs!", cls="text-lg font-medium text-white"),
                    P("You have reviewed all available pairs.", cls="text-slate-400 mt-2"),
                    cls="text-center py-12",
                ),
                oob_toast,
                counter_script,
            )
        _next_url = f"/api/match/next-pair?filter={filter}" if filter else "/api/match/next-pair"
        next_pair_html = Div(
            P("Loading next pair...", cls="text-slate-400 text-center py-4"),
            hx_get=_next_url,
            hx_trigger="load",
            hx_swap="outerHTML",
        )
        return (next_pair_html, oob_toast, counter_script)

    if decision == "same":
        # Merge identity_b into identity_a
        try:
            registry = _main_mod.load_registry()
            photo_registry = _main_mod.load_photo_registry()
            result = registry.merge_identities(
                source_id=identity_b,
                target_id=identity_a,
                user_source="match_mode",
                photo_registry=photo_registry,
            )
            if result["success"]:
                _main_mod.save_registry(registry, changed_ids={identity_a, identity_b})
                _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
                _log_audit(
                    "merge",
                    entity_id=result.get("target_id", identity_a),
                    user_email=_user.email if _user else None,
                    old_value={"source_id": result.get("source_id", identity_b)},
                    new_value={
                        "merged_into": result.get("target_id", identity_a),
                        "faces_merged": result.get("faces_merged", 0),
                    },
                    metadata={"route": "match_mode", "confidence": confidence},
                )
                oob_toast = Div(
                    _main_mod.toast(f"Merged! {_main_mod._pl(result['faces_merged'], 'face')} combined.", "success"),
                    hx_swap_oob="beforeend:#toast-container",
                )
            else:
                oob_toast = Div(
                    _main_mod.toast(f"Cannot merge: {result['reason']}", "warning"),
                    hx_swap_oob="beforeend:#toast-container",
                )
        except Exception as e:
            oob_toast = Div(
                _main_mod.toast(f"Error: {str(e)}", "error"),
                hx_swap_oob="beforeend:#toast-container",
            )
    elif decision == "different":
        # Mark as not same person
        try:
            registry = _main_mod.load_registry()
            registry.reject_identity_pair(identity_a, identity_b, user_source="match_mode")
            _main_mod.save_registry(registry, changed_ids={identity_a, identity_b})
            _user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
            _log_audit(
                "negative_match",
                entity_id=identity_a,
                user_email=_user.email if _user else None,
                old_value={"rejected_id": identity_b},
                metadata={"route": "match_mode", "confidence": confidence},
            )
            oob_toast = Div(
                _main_mod.toast("Marked as different people.", "info"),
                hx_swap_oob="beforeend:#toast-container",
            )
        except Exception as e:
            oob_toast = Div(
                _main_mod.toast(f"Error: {str(e)}", "error"),
                hx_swap_oob="beforeend:#toast-container",
            )
    else:
        oob_toast = Div(
            _main_mod.toast("Invalid decision.", "error"),
            hx_swap_oob="beforeend:#toast-container",
        )

    # Increment counter script (OOB)
    counter_script = Div(
        Script("if (typeof incrementMatchCount === 'function') incrementMatchCount();"),
        hx_swap_oob="beforeend:body",
    )

    # Get next pair (respecting active filter)
    pair = _get_best_match_pair(triage_filter=filter)
    if pair is None:
        _back_url = f"/?section=to_review&view=focus&filter={filter}" if filter else "/?section=to_review&view=focus"
        next_content = Div(
            H3("No more pairs!", cls="text-lg font-medium text-white"),
            P("You have matched all available pairs.", cls="text-slate-400 mt-2"),
            A(
                "Back to Focus mode",
                href=_back_url,
                cls="inline-block mt-4 text-indigo-400 hover:text-indigo-300 font-medium",
            ),
            cls="text-center py-12",
        )
        return (next_content, oob_toast, counter_script)

    _next_url = f"/api/match/next-pair?filter={filter}" if filter else "/api/match/next-pair"
    next_pair_html = Div(
        P("Loading next pair...", cls="text-slate-400 text-center py-4"),
        hx_get=_next_url,
        hx_trigger="load",
        hx_swap="outerHTML",
    )
    return (next_pair_html, oob_toast, counter_script)


# ============================================================================
# FACE COMPARE STANDALONE — /facecompare
# Separate from /compare (archive tool). This is the "front door for strangers."
# No login required, no archive nav, museum-quality design.
# AD-131: Standalone route separate from /compare
# AD-132: Community-agnostic language for future expansion
# ============================================================================


def _fc_og_tags(title: str = "", description: str = "", image: str = "") -> list:
    """OpenGraph meta tags for facecompare pages."""
    t = title or "Face Compare — Find Matches in Historical Archives"
    d = (
        description
        or "Upload a photo and find matching faces in curated historical archives. Free, no account required."
    )
    i = image or f"{_main_mod.SITE_URL}/static/og-facecompare.jpg"
    return [
        Meta(property="og:title", content=t),
        Meta(property="og:description", content=d),
        Meta(property="og:image", content=i),
        Meta(property="og:type", content="website"),
        Meta(property="og:url", content=f"{_main_mod.SITE_URL}/facecompare"),
        Meta(name="description", content=d),
        Meta(name="twitter:card", content="summary_large_image"),
    ]


def _fc_page(title_text: str, *content, og_title: str = "", og_desc: str = "", og_image: str = "") -> object:
    """Standalone page wrapper for /facecompare. No archive nav, own design."""
    return Title(title_text), Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title(title_text),
            *_fc_og_tags(og_title, og_desc, og_image),
            Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"),
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
            Link(
                rel="stylesheet",
                href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&display=swap",
            ),
            Script(src="https://unpkg.com/htmx.org@1.9.10"),
            Style("""
                :root {
                    --fc-cream: #f5f0e8;
                    --fc-warm: #d4a574;
                    --fc-brown: #8b6f47;
                    --fc-dark: #1a1612;
                    --fc-darker: #0f0d0a;
                    --fc-accent: #c9956b;
                }
                body {
                    margin: 0;
                    background: var(--fc-darker);
                    color: var(--fc-cream);
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                }
                .fc-serif {
                    font-family: 'Cormorant Garamond', Georgia, serif;
                }
                .fc-grain {
                    position: relative;
                }
                .fc-grain::after {
                    content: '';
                    position: absolute;
                    inset: 0;
                    opacity: 0.03;
                    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
                    pointer-events: none;
                }
                .fc-upload-zone {
                    border: 2px dashed var(--fc-brown);
                    transition: all 0.2s;
                    cursor: pointer;
                }
                .fc-upload-zone:hover, .fc-upload-zone.dragover {
                    border-color: var(--fc-warm);
                    background: rgba(212, 165, 116, 0.05);
                }
                .htmx-indicator { display: none; }
                .htmx-request .htmx-indicator,
                .htmx-request.htmx-indicator { display: block; }
                form.htmx-request button[type="submit"],
                form.htmx-request .fc-upload-zone {
                    opacity: 0.5;
                    pointer-events: none;
                }
            """),
        ),
        Body(
            NotStr(_main_mod._upload_progress_script()),
            *content,
            data_theme="facecompare",
        ),
        lang="en",
    )


def _fc_result_card(result: dict, crop_files: set, index: int, nav_prefix: str = "") -> object | None:
    """Build a museum-quality result card for facecompare."""
    fid = result["face_id"]
    dist = result["distance"]
    tier = result.get("tier", "WEAK")
    confidence_pct = result.get("confidence_pct", 50)
    name = ensure_utf8_display(result.get("identity_name", "Unknown"))
    state = result.get("state", "")
    identity_id = result.get("identity_id", "")

    crop_url = _main_mod.resolve_face_image_url(fid, crop_files)
    if not crop_url:
        return None

    photo_id = _main_mod.get_photo_id_for_face(fid)

    # Tier colors — warm palette
    tier_config = {
        "STRONG MATCH": {
            "color": "#4ade80",
            "bg": "rgba(74, 222, 128, 0.08)",
            "border": "rgba(74, 222, 128, 0.3)",
            "label": "Strong Match",
        },
        "POSSIBLE MATCH": {
            "color": "#fbbf24",
            "bg": "rgba(251, 191, 36, 0.08)",
            "border": "rgba(251, 191, 36, 0.25)",
            "label": "Possible Match",
        },
        "SIMILAR": {
            "color": "#93c5fd",
            "bg": "rgba(147, 197, 253, 0.06)",
            "border": "rgba(147, 197, 253, 0.2)",
            "label": "Similar Features",
        },
    }
    tc = tier_config.get(
        tier, {"color": "#94a3b8", "bg": "transparent", "border": "rgba(148, 163, 184, 0.15)", "label": tier}
    )

    # Display name
    display_name = name if state == "CONFIRMED" else "Unidentified Person"

    # Confidence label
    if confidence_pct >= 85:
        conf_label = "Very likely same person"
    elif confidence_pct >= 70:
        conf_label = "Strong match"
    elif confidence_pct >= 50:
        conf_label = "Possible match"
    else:
        conf_label = "Some similarity"

    # Archive links
    links = []
    if state == "CONFIRMED" and identity_id:
        links.append(
            A(
                f"Explore {name.split()[0]}'s story in the archive",
                href=f"{nav_prefix}/person/{identity_id}",
                style=f"color: {tc['color']}; font-size: 0.8rem; text-decoration: none;",
                cls="hover:underline block mt-3",
            )
        )
    elif photo_id:
        links.append(
            A(
                "View in the archive",
                href=f"{nav_prefix}/photo/{photo_id}",
                style="color: var(--fc-warm); font-size: 0.8rem; text-decoration: none;",
                cls="hover:underline block mt-3",
            )
        )

    return Div(
        Div(
            Img(
                src=crop_url,
                style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover; "
                f"border: 2px solid {tc['border']};",
                alt=f"Archive match: {display_name}",
            ),
            style="display: flex; justify-content: center;",
        ),
        Div(
            P(
                display_name,
                style="font-size: 1rem; font-weight: 600; color: var(--fc-cream); "
                "margin: 0.75rem 0 0.25rem; text-align: center;",
                cls="fc-serif",
            ),
            Div(
                Span(
                    f"{confidence_pct}%",
                    style=f"font-size: 0.75rem; font-weight: 600; color: {tc['color']}; "
                    f"background: {tc['bg']}; padding: 0.15rem 0.5rem; "
                    f"border-radius: 9999px; border: 1px solid {tc['border']};",
                ),
                Span(tc["label"], style=f"font-size: 0.7rem; color: {tc['color']}; margin-left: 0.5rem;"),
                style="display: flex; align-items: center; justify-content: center; gap: 0.25rem; margin-top: 0.25rem;",
            ),
            P(conf_label, style="font-size: 0.7rem; color: #94a3b8; text-align: center; margin-top: 0.25rem;"),
            P(
                "Jews of Rhodes Community Archive",
                style="font-size: 0.65rem; color: #64748b; text-align: center; margin-top: 0.5rem; font-style: italic;",
            ),
            *links,
        ),
        style=f"background: {tc['bg']}; border: 1px solid {tc['border']}; "
        "border-radius: 0.75rem; padding: 1.25rem; transition: transform 0.2s;",
        cls="hover:scale-[1.02]",
        data_testid="fc-result-card",
        data_tier=tier.lower().replace(" ", "-"),
    )


def _fc_results_section(
    results: list,
    crop_files: set,
    date_info: dict = None,
    upload_image_url: str = "",
    face_count: int = 0,
    result_id: str = "",
    nav_prefix: str = "",
) -> object:
    """Build the full results section for facecompare."""
    parts = []

    # Header with uploaded photo context
    header_parts = []
    if upload_image_url:
        header_parts.append(
            Div(
                Img(
                    src=upload_image_url,
                    style="max-height: 160px; border-radius: 0.5rem; object-fit: contain;",
                    alt="Your uploaded photo",
                ),
                style="display: flex; justify-content: center; margin-bottom: 1rem;",
            )
        )

    # Date estimation
    if date_info:
        decade = date_info.get("predicted_decade", "")
        confidence = date_info.get("confidence", 0)
        if decade:
            conf_color = "#4ade80" if confidence >= 0.5 else "#fbbf24" if confidence >= 0.3 else "#94a3b8"
            header_parts.append(
                P(
                    f"Your photo appears to be from the {decade}s",
                    style=f"font-size: 1.1rem; color: {conf_color}; text-align: center; margin-bottom: 0.5rem;",
                    cls="fc-serif",
                    data_testid="fc-date-estimate",
                )
            )
            # Decade probability bars
            decade_probs = date_info.get("decade_probabilities", {})
            if decade_probs:
                bars = []
                for dec_str, prob in sorted(decade_probs.items()):
                    dec = int(dec_str)
                    pct = prob * 100
                    is_pred = dec == decade
                    bar_color = "var(--fc-warm)" if is_pred else "#334155"
                    text_w = "600" if is_pred else "400"
                    text_c = "var(--fc-warm)" if is_pred else "#64748b"
                    bars.append(
                        Div(
                            Span(
                                f"{dec}s",
                                style=f"font-size: 0.65rem; color: {text_c}; "
                                f"font-weight: {text_w}; width: 2.5rem; "
                                "text-align: right; margin-right: 0.5rem; flex-shrink: 0;",
                            ),
                            Div(
                                Div(
                                    style=f"width: {max(1, pct)}%; height: 100%; "
                                    f"background: {bar_color}; border-radius: 0 0.25rem 0.25rem 0;"
                                ),
                                style="flex: 1; background: #1e293b; border-radius: 0.25rem; height: 0.5rem;",
                            ),
                            Span(
                                f"{pct:.0f}%",
                                style=f"font-size: 0.6rem; color: {text_c}; "
                                "width: 2rem; margin-left: 0.5rem; flex-shrink: 0;",
                            ),
                            style="display: flex; align-items: center;",
                        )
                    )
                header_parts.append(
                    Div(*bars, style="max-width: 20rem; margin: 0.75rem auto 0;", data_testid="fc-decade-bars")
                )

    # Summary line
    match_tiers = {"STRONG MATCH": 0, "POSSIBLE MATCH": 0, "SIMILAR": 0}
    for r in results:
        t = r.get("tier", "WEAK")
        if t in match_tiers:
            match_tiers[t] += 1

    total_shown = sum(match_tiers.values())
    if total_shown > 0:
        header_parts.append(
            P(
                f"We found {total_shown} potential match{'es' if total_shown != 1 else ''} in the archive",
                style="font-size: 1.25rem; font-weight: 700; color: var(--fc-cream); "
                "text-align: center; margin: 1.5rem 0 0.5rem;",
                cls="fc-serif",
                data_testid="fc-match-summary",
            )
        )

    if header_parts:
        parts.append(Div(*header_parts, style="padding: 2rem 1rem; border-bottom: 1px solid rgba(139, 111, 71, 0.2);"))

    # Results grid — grouped by tier
    tier_order = ["STRONG MATCH", "POSSIBLE MATCH", "SIMILAR"]
    for tier_name in tier_order:
        tier_results = [r for r in results if r.get("tier") == tier_name]
        if not tier_results:
            continue
        cards = [_fc_result_card(r, crop_files, i, nav_prefix=nav_prefix) for i, r in enumerate(tier_results)]
        cards = [c for c in cards if c is not None]
        if not cards:
            continue

        tier_config = {
            "STRONG MATCH": {"label": "Strong Matches", "color": "#4ade80"},
            "POSSIBLE MATCH": {"label": "Possible Matches", "color": "#fbbf24"},
            "SIMILAR": {"label": "Similar Features", "color": "#93c5fd"},
        }
        tc = tier_config.get(tier_name, {"label": tier_name, "color": "#94a3b8"})

        parts.append(
            Div(
                P(
                    tc["label"],
                    style=f"font-size: 0.85rem; font-weight: 600; color: {tc['color']}; "
                    "text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem;",
                    cls="fc-serif",
                ),
                Div(
                    *cards,
                    style="display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 1rem;",
                ),
                style="padding: 1.5rem 1rem;",
                data_testid=f"fc-tier-{tier_name.lower().replace(' ', '-')}",
            )
        )

    # Empty state
    if total_shown == 0:
        parts.append(
            Div(
                P(
                    "No strong matches found in the archive",
                    style="font-size: 1.25rem; font-weight: 600; color: var(--fc-cream); text-align: center;",
                    cls="fc-serif",
                ),
                P(
                    "That doesn't mean they aren't here. Historical photos vary in quality and angle, "
                    "and new photos are added regularly.",
                    style="font-size: 0.9rem; color: #94a3b8; text-align: center; "
                    "margin-top: 0.75rem; max-width: 28rem; margin-left: auto; margin-right: auto;",
                ),
                Div(
                    A(
                        "Browse the archive",
                        href="/",
                        style="display: inline-block; padding: 0.75rem 1.5rem; "
                        "background: var(--fc-brown); color: var(--fc-cream); "
                        "border-radius: 0.5rem; text-decoration: none; font-size: 0.9rem;",
                        cls="hover:opacity-90",
                    ),
                    A(
                        "Try a different photo",
                        href="/facecompare",
                        style="display: inline-block; padding: 0.75rem 1.5rem; margin-left: 1rem; "
                        "border: 1px solid var(--fc-brown); color: var(--fc-warm); "
                        "border-radius: 0.5rem; text-decoration: none; font-size: 0.9rem;",
                        cls="hover:opacity-90",
                    ),
                    style="display: flex; justify-content: center; gap: 1rem; margin-top: 1.5rem; flex-wrap: wrap;",
                ),
                style="padding: 3rem 1rem;",
                data_testid="fc-empty-state",
            )
        )

    # Share + bridge CTAs
    if total_shown > 0:
        share_section = []
        if result_id:
            share_url = f"{_main_mod.SITE_URL}/facecompare/result/{result_id}"
            share_section.append(
                Div(
                    Button(
                        "Share this result",
                        onclick=f"if(navigator.share){{navigator.share({{title:'Face Compare Result',url:'{share_url}'}})}}else{{navigator.clipboard.writeText('{share_url}');this.textContent='Link copied!'}}",
                        style="padding: 0.6rem 1.5rem; background: var(--fc-brown); "
                        "color: var(--fc-cream); border: none; border-radius: 0.5rem; "
                        "cursor: pointer; font-size: 0.9rem;",
                        cls="hover:opacity-90",
                        data_testid="fc-share-btn",
                    ),
                    style="display: flex; justify-content: center; margin-bottom: 1.5rem;",
                )
            )

        bridge = Div(
            Div(
                A(
                    "Explore the full archive",
                    href="/",
                    style="display: inline-block; padding: 0.6rem 1.25rem; "
                    "border: 1px solid var(--fc-brown); color: var(--fc-warm); "
                    "border-radius: 0.5rem; text-decoration: none; font-size: 0.85rem;",
                    cls="hover:opacity-90",
                ),
                A(
                    "Upload to the archive",
                    href="/tools/compare",
                    style="display: inline-block; padding: 0.6rem 1.25rem; margin-left: 0.75rem; "
                    "border: 1px solid var(--fc-brown); color: var(--fc-warm); "
                    "border-radius: 0.5rem; text-decoration: none; font-size: 0.85rem;",
                    cls="hover:opacity-90",
                ),
                A(
                    "Try another photo",
                    href="/facecompare",
                    style="display: inline-block; padding: 0.6rem 1.25rem; margin-left: 0.75rem; "
                    "background: var(--fc-brown); color: var(--fc-cream); "
                    "border: none; border-radius: 0.5rem; text-decoration: none; font-size: 0.85rem;",
                    cls="hover:opacity-90",
                ),
                style="display: flex; justify-content: center; gap: 0.5rem; flex-wrap: wrap;",
            ),
            style="padding: 1.5rem 1rem; border-top: 1px solid rgba(139, 111, 71, 0.2);",
            data_testid="fc-bridge-ctas",
        )

        parts.append(Div(*share_section, bridge))

    return Div(*parts, id="fc-results", data_testid="fc-results")


@rt("/facecompare")
def get():
    """Redirect /facecompare → /tools/compare (ROUTE-001).

    /tools/compare is now the canonical standalone compare tool.
    Keeping this redirect for any external links that point here.
    """
    from starlette.responses import RedirectResponse

    return RedirectResponse("/tools/compare", status_code=301)


# --- Original /facecompare landing page (deprecated, kept for reference) ---
def _facecompare_landing_DEPRECATED():  # noqa: N802
    return _fc_page(
        "Face Compare — Find Matches in Historical Archives",
        # Minimal header
        Header(
            Div(
                A(
                    "Face Compare",
                    href="/facecompare",
                    style="font-size: 1.1rem; font-weight: 700; color: var(--fc-cream); "
                    "text-decoration: none; letter-spacing: 0.02em;",
                    cls="fc-serif",
                ),
                style="max-width: 48rem; margin: 0 auto; padding: 1rem 1.5rem;",
            ),
            style="border-bottom: 1px solid rgba(139, 111, 71, 0.15);",
        ),
        # Hero section
        Section(
            Div(
                H1(
                    "Who is in your photo?",
                    style="font-size: clamp(2rem, 5vw, 3.5rem); font-weight: 700; "
                    "color: var(--fc-cream); line-height: 1.15; margin: 0;",
                    cls="fc-serif",
                ),
                P(
                    "Upload a photo and find matching faces in historical archives. "
                    "Our system detects every face, estimates the photo's era, and searches "
                    "for matches among hundreds of identified individuals.",
                    style="font-size: 1.05rem; color: #a39584; margin-top: 1.25rem; "
                    "line-height: 1.6; max-width: 32rem;",
                ),
                # Upload form
                Form(
                    Div(
                        Div(
                            # Upload icon (camera)
                            NotStr(
                                '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--fc-brown); margin-bottom: 0.75rem;"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>'
                            ),
                            P(
                                "Drop a photo here or tap to upload",
                                style="font-size: 0.95rem; color: var(--fc-brown); margin: 0;",
                            ),
                            P(
                                "JPEG, PNG, or WebP — up to 10 MB",
                                style="font-size: 0.75rem; color: #64748b; margin: 0.25rem 0 0;",
                            ),
                            style="text-align: center; padding: 2.5rem 1.5rem;",
                        ),
                        Input(
                            type="file",
                            name="photo",
                            accept="image/jpeg,image/png,image/webp",
                            style="position: absolute; inset: 0; opacity: 0; cursor: pointer;",
                            data_testid="fc-file-input",
                        ),
                        style="position: relative;",
                        cls="fc-upload-zone",
                        id="fc-upload-zone",
                    ),
                    style="margin-top: 2rem;",
                    hx_post="/api/facecompare/upload",
                    hx_target="#fc-results",
                    hx_swap="innerHTML",
                    hx_encoding="multipart/form-data",
                    hx_indicator="#fc-loading",
                    data_testid="fc-upload-form",
                    onsubmit="if(typeof startProgressUpload==='function'){return startProgressUpload(this,'facecompare')}",
                ),
                # Loading indicator
                Div(
                    Div(
                        Div(
                            style="width: 2rem; height: 2rem; border: 2px solid var(--fc-brown); "
                            "border-top-color: transparent; border-radius: 50%; "
                            "animation: spin 0.8s linear infinite;"
                        ),
                        P(
                            "Analyzing your photo...",
                            style="font-size: 0.9rem; color: var(--fc-brown); margin-top: 0.75rem;",
                        ),
                        style="text-align: center; padding: 2rem;",
                    ),
                    id="fc-loading",
                    cls="htmx-indicator",
                ),
                # Progressive upload stages
                Div(
                    Div(
                        _main_mod._upload_stage_item("received", "Photo received", "pending"),
                        _main_mod._upload_stage_item("detecting", "Detecting faces", "pending"),
                        _main_mod._upload_stage_item("comparing", "Searching archive", "pending"),
                        _main_mod._upload_stage_item("estimating", "Estimating date", "pending"),
                        _main_mod._upload_stage_item("complete", "Analysis complete", "pending"),
                        style="text-align: left; max-width: 16rem; margin: 0 auto; display: flex; flex-direction: column; gap: 0.75rem;",
                        id="stage-list",
                    ),
                    id="upload-progress",
                    style="display: none; text-align: center; padding: 1.5rem;",
                    data_testid="fc-upload-progress",
                ),
                style="max-width: 32rem;",
            ),
            style="max-width: 48rem; margin: 0 auto; padding: 4rem 1.5rem 3rem;",
            cls="fc-grain",
            data_testid="fc-hero",
        ),
        # Results container (filled by HTMX)
        Div(id="fc-results"),
        # How it works
        Section(
            Div(
                H2(
                    "How it works",
                    style="font-size: 1.5rem; font-weight: 600; color: var(--fc-cream); "
                    "text-align: center; margin-bottom: 2.5rem;",
                    cls="fc-serif",
                ),
                Div(
                    # Step 1
                    Div(
                        Div(
                            "1",
                            style="width: 2.5rem; height: 2.5rem; border-radius: 50%; "
                            "border: 1.5px solid var(--fc-brown); display: flex; "
                            "align-items: center; justify-content: center; "
                            "font-size: 1rem; color: var(--fc-warm); margin: 0 auto 0.75rem;",
                            cls="fc-serif",
                        ),
                        P(
                            "Upload",
                            style="font-size: 1.1rem; font-weight: 600; color: var(--fc-cream); margin: 0;",
                            cls="fc-serif",
                        ),
                        P(
                            "Drop any photo — modern or vintage",
                            style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.3rem;",
                        ),
                        style="text-align: center; flex: 1; min-width: 140px;",
                    ),
                    # Connector
                    Div(
                        NotStr(
                            '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: #4a3f34;"><path d="M5 12h14M12 5l7 7-7 7"/></svg>'
                        ),
                        style="display: flex; align-items: center; padding-top: 1rem;",
                        cls="hidden sm:flex",
                    ),
                    # Step 2
                    Div(
                        Div(
                            "2",
                            style="width: 2.5rem; height: 2.5rem; border-radius: 50%; "
                            "border: 1.5px solid var(--fc-brown); display: flex; "
                            "align-items: center; justify-content: center; "
                            "font-size: 1rem; color: var(--fc-warm); margin: 0 auto 0.75rem;",
                            cls="fc-serif",
                        ),
                        P(
                            "Detect",
                            style="font-size: 1.1rem; font-weight: 600; color: var(--fc-cream); margin: 0;",
                            cls="fc-serif",
                        ),
                        P(
                            "Every face found and analyzed",
                            style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.3rem;",
                        ),
                        style="text-align: center; flex: 1; min-width: 140px;",
                    ),
                    # Connector
                    Div(
                        NotStr(
                            '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: #4a3f34;"><path d="M5 12h14M12 5l7 7-7 7"/></svg>'
                        ),
                        style="display: flex; align-items: center; padding-top: 1rem;",
                        cls="hidden sm:flex",
                    ),
                    # Step 3
                    Div(
                        Div(
                            "3",
                            style="width: 2.5rem; height: 2.5rem; border-radius: 50%; "
                            "border: 1.5px solid var(--fc-brown); display: flex; "
                            "align-items: center; justify-content: center; "
                            "font-size: 1rem; color: var(--fc-warm); margin: 0 auto 0.75rem;",
                            cls="fc-serif",
                        ),
                        P(
                            "Discover",
                            style="font-size: 1.1rem; font-weight: 600; color: var(--fc-cream); margin: 0;",
                            cls="fc-serif",
                        ),
                        P(
                            "Matches with names, dates, and stories",
                            style="font-size: 0.85rem; color: #94a3b8; margin-top: 0.3rem;",
                        ),
                        style="text-align: center; flex: 1; min-width: 140px;",
                    ),
                    style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;",
                ),
                style="max-width: 42rem; margin: 0 auto;",
            ),
            style="padding: 3rem 1.5rem; border-top: 1px solid rgba(139, 111, 71, 0.1);",
            data_testid="fc-how-it-works",
        ),
        # Footer
        Footer(
            Div(
                Div(
                    A(
                        "Explore the full archive",
                        href="/",
                        style="color: var(--fc-warm); text-decoration: none; font-size: 0.85rem;",
                        cls="hover:underline",
                    ),
                    Span("·", style="color: #4a3f34; margin: 0 0.75rem;"),
                    A(
                        "About this project",
                        href="/about",
                        style="color: var(--fc-warm); text-decoration: none; font-size: 0.85rem;",
                        cls="hover:underline",
                    ),
                    style="display: flex; justify-content: center; align-items: center; flex-wrap: wrap;",
                ),
                P(
                    "Your photo is processed in real time and not stored permanently. "
                    "Only comparison results are saved for sharing.",
                    style="font-size: 0.75rem; color: #64748b; text-align: center; margin-top: 0.75rem;",
                ),
                style="max-width: 48rem; margin: 0 auto; padding: 2rem 1.5rem;",
            ),
            style="border-top: 1px solid rgba(139, 111, 71, 0.1);",
        ),
        # Auto-submit JS + drag-and-drop
        Script("""
            document.addEventListener('change', function(e) {
                if (e.target.matches('[data-testid="fc-file-input"]')) {
                    var form = e.target.closest('form');
                    if (form) htmx.trigger(form, 'submit');
                }
            });
            document.addEventListener('dragover', function(e) {
                var zone = document.getElementById('fc-upload-zone');
                if (zone && zone.contains(e.target)) {
                    e.preventDefault();
                    zone.classList.add('dragover');
                }
            });
            document.addEventListener('dragleave', function(e) {
                var zone = document.getElementById('fc-upload-zone');
                if (zone && !zone.contains(e.relatedTarget)) {
                    zone.classList.remove('dragover');
                }
            });
            document.addEventListener('drop', function(e) {
                var zone = document.getElementById('fc-upload-zone');
                if (zone && zone.contains(e.target)) {
                    e.preventDefault();
                    zone.classList.remove('dragover');
                    var input = zone.querySelector('input[type="file"]');
                    if (input && e.dataTransfer.files.length > 0) {
                        input.files = e.dataTransfer.files;
                        var form = input.closest('form');
                        if (form) htmx.trigger(form, 'submit');
                    }
                }
            });
        """),
        Style("@keyframes spin { to { transform: rotate(360deg); } }"),
    )


@rt("/api/facecompare/upload")
async def post(photo: UploadFile = None, request=None):
    """Upload a photo for standalone face comparison.

    Runs InsightFace (detection + embeddings), CORAL (date estimation),
    and similarity search against the archive.
    No login required.
    """
    # Rate limiting
    client_ip = request.client.host if request and request.client else "unknown"
    if not check_rate_limit(client_ip):
        return StarletteResponse("Rate limit exceeded", status_code=429)

    import time as _time

    t0 = _time.time()

    if not photo:
        return Div(P("No photo uploaded.", style="color: #fbbf24; text-align: center; padding: 1rem;"), id="fc-results")

    from pathlib import Path as _Path

    content = await photo.read()
    original_filename = photo.filename or "upload.jpg"
    suffix = _Path(original_filename).suffix.lower() or ".jpg"

    # Validate file type
    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        return Div(
            P("Please upload a JPEG, PNG, or WebP image.", style="color: #ef4444; text-align: center; padding: 1rem;"),
            id="fc-results",
        )

    # Validate file size (10 MB)
    if len(content) > 10 * 1024 * 1024:
        return Div(
            P("File is too large (max 10 MB).", style="color: #ef4444; text-align: center; padding: 1rem;"),
            id="fc-results",
        )

    # Check InsightFace availability
    has_insightface = False
    try:
        import cv2
        from insightface.app import FaceAnalysis  # noqa: F401
        from core.ingest_inbox import extract_faces_hybrid

        has_insightface = True
    except ImportError:
        pass

    if not has_insightface:
        return Div(
            P(
                "Face comparison is currently being set up.",
                style="font-size: 1.1rem; color: var(--fc-cream); text-align: center;",
                cls="fc-serif",
            ),
            P(
                "Check back soon — we're bringing the ML models online.",
                style="font-size: 0.9rem; color: #94a3b8; text-align: center; margin-top: 0.5rem;",
            ),
            style="padding: 3rem 1rem;",
            id="fc-results",
        )

    import tempfile

    # Save original for display, ML copy for processing
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = _Path(tmp.name)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as ml_tmp:
        ml_tmp.write(content)
        ml_path = _Path(ml_tmp.name)

    try:
        timings = {}

        # Resize for ML (AD-110: max 640px)
        t1 = _time.time()
        img = cv2.imread(str(ml_path))
        if img is not None:
            h, w = img.shape[:2]
            if max(h, w) > 640:
                scale = 640 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                cv2.imwrite(str(ml_path), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        timings["prep"] = _time.time() - t1

        # Face detection (hybrid — AD-114)
        t1 = _time.time()
        faces, _, _ = extract_faces_hybrid(ml_path)
        timings["detect"] = _time.time() - t1
        print(f"[facecompare] Detection: {timings['detect']:.2f}s ({len(faces)} faces)")

        if not faces:
            return Div(
                P(
                    "No faces detected",
                    style="font-size: 1.1rem; color: var(--fc-cream); text-align: center;",
                    cls="fc-serif",
                ),
                P(
                    "Try a clearer photo with faces visible and well-lit.",
                    style="font-size: 0.9rem; color: #94a3b8; text-align: center; margin-top: 0.5rem;",
                ),
                Div(
                    A(
                        "Try again",
                        href="/facecompare",
                        style="display: inline-block; padding: 0.6rem 1.5rem; "
                        "background: var(--fc-brown); color: var(--fc-cream); "
                        "border-radius: 0.5rem; text-decoration: none;",
                    ),
                    style="text-align: center; margin-top: 1.5rem;",
                ),
                style="padding: 3rem 1rem;",
                id="fc-results",
                data_testid="fc-no-faces",
            )

        # CORAL date estimation
        t1 = _time.time()
        date_info = None
        try:
            from rhodesli_ml.date_inference.inference import predict_date
            from PIL import Image as _PILImage

            pil_img = _PILImage.open(io.BytesIO(content)).convert("RGB")
            rgb_array = np.array(pil_img)
            date_info = predict_date(rgb_array)
        except Exception as e:
            print(f"[facecompare] CORAL error: {e}")
        timings["coral"] = _time.time() - t1

        # Save upload (local filesystem for standalone)
        upload_id = str(uuid.uuid4())[:12]
        upload_dir = _Path("uploads/facecompare")
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / f"{upload_id}{suffix}").write_bytes(content)

        # Save face data for multi-face selection
        import pickle

        face_save_data = [
            {
                "mu": f["mu"].tolist(),
                "bbox": f.get("bbox", [0, 0, 0, 0]).tolist()
                if hasattr(f.get("bbox", []), "tolist")
                else list(f.get("bbox", [0, 0, 0, 0])),
            }
            for f in faces
        ]
        (upload_dir / f"{upload_id}_faces.pkl").write_bytes(pickle.dumps(face_save_data))

        # Save date info
        if date_info:
            (upload_dir / f"{upload_id}_date.json").write_text(json.dumps(date_info, indent=2, default=str))

        # If multiple faces, show face selector
        if len(faces) > 1:
            upload_image_url = f"/uploads/facecompare/{upload_id}{suffix}"

            face_buttons = []
            for i, face in enumerate(faces):
                bbox = face.get("bbox", [0, 0, 0, 0])
                if hasattr(bbox, "tolist"):
                    bbox = bbox.tolist()

                face_buttons.append(
                    Button(
                        f"Face {i + 1}",
                        hx_post=f"/api/facecompare/select?upload_id={upload_id}&face_idx={i}",
                        hx_target="#fc-results",
                        hx_swap="innerHTML",
                        hx_indicator="#fc-loading-select",
                        style="padding: 0.5rem 1rem; border-radius: 0.5rem; cursor: pointer; "
                        f"{'background: var(--fc-brown); color: var(--fc-cream); border: none;' if i == 0 else 'background: transparent; color: var(--fc-warm); border: 1px solid var(--fc-brown);'}",
                        data_testid=f"fc-face-select-{i}",
                    )
                )

            # Date estimation context
            date_el = None
            if date_info and date_info.get("predicted_decade"):
                date_el = P(
                    f"Your photo appears to be from the {date_info['predicted_decade']}s",
                    style="font-size: 1rem; color: var(--fc-warm); text-align: center; margin-top: 1rem;",
                    cls="fc-serif",
                    data_testid="fc-date-estimate",
                )

            return Div(
                Div(
                    Img(
                        src=upload_image_url,
                        style="max-height: 200px; border-radius: 0.5rem; object-fit: contain;",
                        alt="Your uploaded photo",
                    ),
                    style="display: flex; justify-content: center; margin-bottom: 1rem;",
                ),
                P(
                    f"{len(faces)} faces detected — select one to compare:",
                    style="font-size: 1rem; color: var(--fc-cream); text-align: center;",
                    cls="fc-serif",
                ),
                date_el,
                Div(
                    *face_buttons,
                    style="display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap; margin-top: 1rem;",
                ),
                Div(
                    P(
                        "Searching the archive...",
                        style="font-size: 0.9rem; color: var(--fc-brown); text-align: center; padding: 1.5rem;",
                    ),
                    id="fc-loading-select",
                    cls="htmx-indicator",
                ),
                style="padding: 2rem 1rem;",
                id="fc-results",
                data_testid="fc-face-selector",
            )

        # Single face — run comparison directly
        t1 = _time.time()
        query_embedding = faces[0]["mu"]
        face_data = _main_mod.get_face_data()
        registry = _main_mod.load_registry()
        crop_files = _main_mod.get_crop_files()

        from core.neighbors import find_similar_faces

        results = find_similar_faces(
            query_embedding,
            face_data,
            registry=registry,
            limit=20,
        )
        timings["compare"] = _time.time() - t1

        # Filter to displayable tiers only
        displayable = [r for r in results if r.get("tier") in ("STRONG MATCH", "POSSIBLE MATCH", "SIMILAR")]

        # Save comparison result for sharing
        result_id = _main_mod._generate_result_id()
        _main_mod._save_comparison_result(
            {
                "result_id": result_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "query_type": "facecompare_upload",
                "upload_id": upload_id,
                "face_index": 0,
                "date_estimation": date_info,
                "matches": [
                    {
                        "face_id": r["face_id"],
                        "identity_id": r.get("identity_id", ""),
                        "identity_name": r.get("identity_name", ""),
                        "distance": r["distance"],
                        "confidence_pct": r.get("confidence_pct", 0),
                        "tier": r.get("tier", "WEAK"),
                    }
                    for r in displayable[:10]
                ],
                "responses": [],
            }
        )

        upload_image_url = f"/uploads/facecompare/{upload_id}{suffix}"

        timings["total"] = _time.time() - t0
        print(f"[facecompare] TOTAL: {' | '.join(f'{k}={v:.2f}s' for k, v in timings.items())}")

        return _fc_results_section(
            displayable,
            crop_files,
            date_info=date_info,
            upload_image_url=upload_image_url,
            face_count=len(faces),
            result_id=result_id,
        )

    except Exception as e:
        print(f"[facecompare] Error: {e}")
        import traceback

        traceback.print_exc()
        return Div(
            P(
                "Something went wrong processing your photo.",
                style="color: #ef4444; text-align: center; padding: 1rem;",
            ),
            P(
                "Try again with a different image.",
                style="color: #94a3b8; text-align: center; font-size: 0.85rem; margin-top: 0.5rem;",
            ),
            id="fc-results",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
        ml_path.unlink(missing_ok=True)


@rt("/api/facecompare/select")
def post(upload_id: str = "", face_idx: int = 0):
    """Select a specific face from a multi-face upload for comparison."""
    from pathlib import Path as _Path
    import pickle

    if not upload_id or not _SAFE_UPLOAD_ID.match(upload_id):
        return Div(P("Invalid upload ID.", style="color: #ef4444; text-align: center; padding: 1rem;"), id="fc-results")

    # Load face data
    faces_path = _Path("uploads/facecompare") / f"{upload_id}_faces.pkl"
    if not faces_path.exists():
        return Div(
            P("Upload not found. Please try again.", style="color: #ef4444; text-align: center; padding: 1rem;"),
            id="fc-results",
        )

    faces_data = pickle.loads(faces_path.read_bytes())
    if face_idx >= len(faces_data):
        return Div(
            P("Invalid face selection.", style="color: #ef4444; text-align: center; padding: 1rem;"), id="fc-results"
        )

    # Load date info
    date_info = None
    date_path = _Path("uploads/facecompare") / f"{upload_id}_date.json"
    if date_path.exists():
        date_info = json.loads(date_path.read_text())

    # Run comparison
    query_embedding = np.array(faces_data[face_idx]["mu"])
    face_data = _main_mod.get_face_data()
    registry = _main_mod.load_registry()
    crop_files = _main_mod.get_crop_files()

    from core.neighbors import find_similar_faces

    results = find_similar_faces(
        query_embedding,
        face_data,
        registry=registry,
        limit=20,
    )

    displayable = [r for r in results if r.get("tier") in ("STRONG MATCH", "POSSIBLE MATCH", "SIMILAR")]

    # Save result
    result_id = _main_mod._generate_result_id()
    _main_mod._save_comparison_result(
        {
            "result_id": result_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "query_type": "facecompare_upload",
            "upload_id": upload_id,
            "face_index": face_idx,
            "date_estimation": date_info,
            "matches": [
                {
                    "face_id": r["face_id"],
                    "identity_id": r.get("identity_id", ""),
                    "identity_name": r.get("identity_name", ""),
                    "distance": r["distance"],
                    "confidence_pct": r.get("confidence_pct", 0),
                    "tier": r.get("tier", "WEAK"),
                }
                for r in displayable[:10]
            ],
            "responses": [],
        }
    )

    # Find upload image
    upload_dir = _Path("uploads/facecompare")
    upload_image_url = ""
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if (upload_dir / f"{upload_id}{ext}").exists():
            upload_image_url = f"/uploads/facecompare/{upload_id}{ext}"
            break

    return _fc_results_section(
        displayable,
        crop_files,
        date_info=date_info,
        upload_image_url=upload_image_url,
        face_count=len(faces_data),
        result_id=result_id,
    )


@rt("/facecompare/result/{result_id}")
def get(result_id: str):
    """Redirect /facecompare/result/{id} → /compare/result/{id} (ROUTE-001).

    Preserves shareable links while consolidating to canonical compare routes.
    """
    from starlette.responses import RedirectResponse

    return RedirectResponse(f"/compare/result/{result_id}", status_code=301)


def _facecompare_result_DEPRECATED(result_id: str):  # noqa: N802
    """Original shareable face compare result page — deprecated."""
    data = _main_mod._load_comparison_results()
    result = data.get("results", {}).get(result_id)

    if not result:
        return _fc_page(
            "Result Not Found — Face Compare",
            Header(
                Div(
                    A(
                        "Face Compare",
                        href="/facecompare",
                        style="font-size: 1.1rem; font-weight: 700; color: var(--fc-cream); text-decoration: none;",
                        cls="fc-serif",
                    ),
                    style="max-width: 48rem; margin: 0 auto; padding: 1rem 1.5rem;",
                ),
                style="border-bottom: 1px solid rgba(139, 111, 71, 0.15);",
            ),
            Div(
                P(
                    "Result not found",
                    style="font-size: 1.5rem; color: var(--fc-cream); text-align: center;",
                    cls="fc-serif",
                ),
                P(
                    "This comparison result may have expired or the link may be incorrect.",
                    style="color: #94a3b8; text-align: center; margin-top: 0.5rem;",
                ),
                A(
                    "Try Face Compare",
                    href="/facecompare",
                    style="display: inline-block; margin-top: 1.5rem; padding: 0.6rem 1.5rem; "
                    "background: var(--fc-brown); color: var(--fc-cream); "
                    "border-radius: 0.5rem; text-decoration: none;",
                ),
                style="padding: 4rem 1.5rem; text-align: center;",
            ),
        )

    # Reconstruct results for display
    crop_files = _main_mod.get_crop_files()
    matches = result.get("matches", [])
    date_info = result.get("date_estimation")

    # Add display fields to matches
    registry = _main_mod.load_registry()
    display_matches = []
    for m in matches:
        fid = m.get("face_id", "")
        ident_id = m.get("identity_id", "")
        state = ""
        if ident_id:
            ident = registry.get_identity(ident_id)
            if ident:
                state = ident.get("state", "")
        display_matches.append(
            {
                "face_id": fid,
                "distance": m.get("distance", 99),
                "tier": m.get("tier", "WEAK"),
                "confidence_pct": m.get("confidence_pct", 0),
                "identity_id": ident_id,
                "identity_name": m.get("identity_name", ""),
                "state": state,
            }
        )

    share_url = f"{_main_mod.SITE_URL}/facecompare/result/{result_id}"

    _og_desc = f"Found {len(matches)} potential match{'es' if len(matches) != 1 else ''} in a historical archive."

    return _fc_page(
        "Face Compare Result",
        # Header
        Header(
            Div(
                A(
                    "Face Compare",
                    href="/facecompare",
                    style="font-size: 1.1rem; font-weight: 700; color: var(--fc-cream); text-decoration: none;",
                    cls="fc-serif",
                ),
                style="max-width: 48rem; margin: 0 auto; padding: 1rem 1.5rem;",
            ),
            style="border-bottom: 1px solid rgba(139, 111, 71, 0.15);",
        ),
        # Results
        Div(
            _fc_results_section(
                display_matches,
                crop_files,
                date_info=date_info,
                result_id=result_id,
            ),
            style="max-width: 48rem; margin: 0 auto;",
        ),
        # Footer
        Footer(
            Div(
                A(
                    "Try your own photo",
                    href="/facecompare",
                    style="color: var(--fc-warm); text-decoration: none; font-size: 0.9rem;",
                    cls="hover:underline",
                ),
                Span("·", style="color: #4a3f34; margin: 0 0.75rem;"),
                A(
                    "Explore the archive",
                    href="/",
                    style="color: var(--fc-warm); text-decoration: none; font-size: 0.9rem;",
                    cls="hover:underline",
                ),
                style="display: flex; justify-content: center; align-items: center; padding: 2rem 1.5rem;",
            ),
            style="border-top: 1px solid rgba(139, 111, 71, 0.1);",
        ),
        og_title="Face Compare — Match Found in Historical Archive",
        og_desc=_og_desc,
    )


# Serve uploaded facecompare images (local dev)
@rt("/uploads/facecompare/{filename:path}")
def get(filename: str):
    """Serve uploaded facecompare images from local filesystem."""
    from pathlib import Path as _Path

    file_path = _Path("uploads/facecompare") / filename
    if not file_path.exists() or not file_path.is_file():
        return HTMLResponse("Not found", status_code=404)
    import mimetypes

    content_type = mimetypes.guess_type(str(file_path))[0] or "image/jpeg"
    return FileResponse(str(file_path), media_type=content_type)
