"""
Engagement routes extracted from app/main.py.

Annotation submission/review, contributions, activity feed,
proposed matches, and associated annotation helpers.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fasthtml.common import *
from starlette.responses import RedirectResponse, Response

from core.ui_safety import ensure_utf8_display

from app.main import rt

import app.main as _main_mod

logger = logging.getLogger(__name__)

# =============================================================================
# ROUTES - PROPOSED MATCHES
# =============================================================================


@rt("/api/identity/{identity_id}/propose-match")
def post(identity_id: str, target_id: str, note: str = "", sess=None):
    """Propose a match between two identities without executing it. Requires admin."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    user_email = ""
    if sess:
        user = _main_mod.get_current_user(sess)
        if user:
            user_email = user.email

    try:
        registry = _main_mod.load_registry()
        proposal = registry.add_proposed_match(identity_id, target_id, note=note, author=user_email)
        _main_mod.save_registry(registry)
    except KeyError:
        return _main_mod.toast("Identity not found.", "error")
    except Exception as e:
        return _main_mod.toast(f"Failed to propose match: {e}", "error")

    return _main_mod.toast("Match proposed!", "success")


@rt("/api/proposed-matches")
def get(community_slug: str = "", page: int = 1):
    """List all pending proposed matches, optionally filtered by community.

    Combines two data sources:
    1. registry.list_proposed_matches() — user-submitted proposals
    2. proposals.json — ML clustering proposals (from cluster_new_faces + cross-batch)
    """
    try:
        registry = _main_mod.load_registry()
    except Exception:
        registry = None

    # Source 1: User-submitted proposals from registry
    user_proposals = []
    if registry and hasattr(registry, "list_proposed_matches"):
        user_proposals = registry.list_proposed_matches()

    # Source 2: ML proposals from proposals.json (clustering + cross-batch)
    ml_proposals = []
    try:
        proposals_data = _main_mod._load_proposals()
        for p in proposals_data.get("proposals", []):
            ml_proposals.append(
                {
                    "source_id": p.get("source_identity_id", ""),
                    "target_id": p.get("target_identity_id", ""),
                    "source_name": p.get("source_identity_name", ""),
                    "target_name": p.get("target_identity_name", ""),
                    "distance": p.get("distance", 0),
                    "confidence_tier": p.get("confidence_tier", ""),
                    "match_type": p.get("match_type", "clustering"),
                    "id": f"ml_{p.get('source_identity_id', '')[:8]}_{p.get('target_identity_id', '')[:8]}",
                    "author": "ML pipeline",
                    "note": f"Distance: {p.get('distance', 0):.2f}" if p.get("distance") else "",
                    "timestamp": proposals_data.get("generated_at", ""),
                }
            )
    except Exception:
        pass

    # Combine both sources
    proposals = user_proposals + ml_proposals

    # Community filtering
    if community_slug:
        from app.supabase_data import get_community_by_slug

        community = get_community_by_slug(community_slug)
        community_identity_ids = _main_mod._get_community_identity_ids(community)
        if community_identity_ids is not None:
            proposals = [
                p
                for p in proposals
                if p.get("source_id") in community_identity_ids or p.get("target_id") in community_identity_ids
            ]

    # Sort by distance (lowest first = best matches)
    proposals.sort(key=lambda p: p.get("distance", 999))

    if not proposals:
        return Div(P("No pending proposals.", cls="text-slate-400 italic text-sm"), cls="text-center py-8")

    # Paginate — show 50 per page to avoid slow renders
    page_size = 50
    total = len(proposals)
    start = (page - 1) * page_size
    end = start + page_size
    page_proposals = proposals[start:end]

    crop_files = _main_mod.get_crop_files()
    items = []
    for p in page_proposals:
        source_id = p.get("source_id", "")
        target_id = p.get("target_id", "")
        source_name = ensure_utf8_display(p.get("source_name")) or f"Person {source_id[:8]}..."
        target_name = ensure_utf8_display(p.get("target_name")) or f"Person {target_id[:8]}..."
        distance = p.get("distance")
        tier = p.get("confidence_tier", "")

        # Confidence badge
        tier_colors = {"very_high": "bg-red-500", "high": "bg-orange-500", "moderate": "bg-yellow-600"}
        tier_labels = {"very_high": "Very High", "high": "High", "moderate": "Moderate"}
        badge = None
        if tier:
            badge = Span(
                tier_labels.get(tier, tier),
                cls=f"px-1.5 py-0.5 text-xs rounded {tier_colors.get(tier, 'bg-slate-600')} text-white ml-2",
            )

        items.append(
            Div(
                Div(
                    Span(source_name, cls="text-sm font-medium text-slate-200"),
                    Span(" → ", cls="text-slate-500 mx-1"),
                    Span(target_name, cls="text-sm font-medium text-slate-200"),
                    badge,
                    Span(f"Dist: {distance:.2f}", cls="text-xs text-slate-500 ml-2") if distance else None,
                    cls="flex items-center gap-1 flex-wrap",
                ),
                Div(
                    Span(f"by {p.get('author', 'ML pipeline')}", cls="text-xs text-slate-500"),
                    cls="mt-1",
                ),
                Div(
                    A(
                        "View Source",
                        href=f"/person/{source_id}",
                        cls="px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500",
                    ),
                    A(
                        "View Target",
                        href=f"/person/{target_id}",
                        cls="px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-500 ml-1",
                    ),
                    cls="flex gap-2 mt-2",
                ),
                cls="p-3 bg-slate-800 border border-slate-700 rounded-lg mb-2",
            )
        )

    # Pagination controls
    pagination = None
    if total > page_size:
        pages = (total + page_size - 1) // page_size
        page_links = []
        for pg in range(1, pages + 1):
            if pg == page:
                page_links.append(Span(str(pg), cls="px-2 py-1 bg-indigo-600 text-white rounded text-xs"))
            else:
                page_links.append(
                    A(
                        str(pg),
                        href=f"?page={pg}",
                        cls="px-2 py-1 bg-slate-700 text-slate-300 rounded text-xs hover:bg-slate-600",
                        hx_get=f"/api/proposed-matches?community_slug={community_slug}&page={pg}",
                        hx_target="#proposed-matches-list",
                        hx_swap="innerHTML",
                    )
                )
        pagination = Div(
            P(f"Showing {start + 1}-{min(end, total)} of {total} proposals", cls="text-xs text-slate-400 mb-2"),
            Div(*page_links, cls="flex gap-1 flex-wrap"),
            cls="mt-4 text-center",
        )

    result_items = items + ([pagination] if pagination else [])
    return Div(*result_items, id="proposed-matches-list")


@rt("/api/proposed-matches/{source_id}/{proposal_id}/accept")
def post(source_id: str, proposal_id: str, sess=None):
    """Accept a proposed match — execute the merge."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    try:
        registry = _main_mod.load_registry()
        photo_registry = _main_mod.load_photo_registry()

        # Get the proposal to find target_id
        identity = registry.get_identity(source_id)
        proposal = None
        for pm in identity.get("proposed_matches", []):
            if pm["id"] == proposal_id:
                proposal = pm
                break

        if not proposal:
            return _main_mod.toast("Proposal not found.", "error")

        target_id = proposal["target_id"]

        # Execute the merge
        result = registry.merge_identities(
            source_id=source_id,
            target_id=target_id,
            user_source="proposed_match",
            photo_registry=photo_registry,
        )

        if result["success"]:
            registry.resolve_proposed_match(source_id, proposal_id, "accepted")
            _main_mod.save_registry(registry)
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
            _main_mod.toast(f"Error: {e}", "error"),
            hx_swap_oob="beforeend:#toast-container",
        )

    # Re-render the proposals list
    proposals = registry.list_proposed_matches()
    if not proposals:
        return (
            Div(
                P("No pending proposals.", cls="text-slate-400 italic text-sm"),
                cls="text-center py-8",
                id="proposed-matches-list",
            ),
            oob_toast,
        )

    # Return a placeholder that triggers reload of the proposals list
    return (
        Div(
            P("Refreshing...", cls="text-slate-400"),
            hx_get="/api/proposed-matches",
            hx_trigger="load",
            hx_swap="outerHTML",
            id="proposed-matches-list",
        ),
        oob_toast,
    )


@rt("/api/proposed-matches/{source_id}/{proposal_id}/reject")
def post(source_id: str, proposal_id: str, sess=None):
    """Reject a proposed match."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    try:
        registry = _main_mod.load_registry()
        registry.resolve_proposed_match(source_id, proposal_id, "rejected")
        _main_mod.save_registry(registry)
    except Exception as e:
        return _main_mod.toast(f"Error: {e}", "error")

    # Re-render with reload trigger
    return Div(
        P("Refreshing...", cls="text-slate-400"),
        hx_get="/api/proposed-matches",
        hx_trigger="load",
        hx_swap="outerHTML",
        id="proposed-matches-list",
    )


# =============================================================================
# Auth routes moved to auth_routes.py


# --- Admin Data Export Endpoints ---


_annotations_cache = None


def _load_annotations() -> dict:
    """Load annotations from data file.

    When DATA_SOURCE=postgres, loads from Supabase with JSON fallback.
    When DATA_SOURCE=json (default), loads from JSON file.

    Returns default empty structure if file is missing or corrupted,
    so the server never crashes on bad annotation data.
    """
    global _annotations_cache
    if _annotations_cache is not None:
        return _annotations_cache

    if _main_mod.DATA_SOURCE == "postgres":
        try:
            from app.supabase_data import load_annotations_from_supabase

            result = load_annotations_from_supabase()
            if result is not None:
                logging.info(f"Loaded {len(result.get('annotations', {}))} annotations from Postgres")
                _annotations_cache = result
                return _annotations_cache
            logging.warning("Postgres annotations load returned None, falling back to JSON")
        except Exception as e:
            logging.warning(f"Postgres annotations load failed, falling back to JSON: {e}")

    ann_path = _main_mod.data_path / "annotations.json"
    default = {"schema_version": 1, "annotations": {}}
    if ann_path.exists():
        import json as _json

        try:
            with open(ann_path) as f:
                _annotations_cache = _json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logging.error(f"Failed to load annotations from {ann_path}: {e}")
            _annotations_cache = default
    else:
        _annotations_cache = default
    return _annotations_cache


def _save_annotations(data: dict):
    """Save annotations atomically + sync to Supabase (AD-135)."""
    global _annotations_cache
    ann_path = _main_mod.data_path / "annotations.json"
    import json as _json
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(_main_mod.data_path), suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            _json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(ann_path))
        _annotations_cache = data
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    # Sync annotations to Supabase (non-blocking on failure)
    try:
        from app.supabase_data import sync_annotations

        sync_annotations(data.get("annotations", {}))
    except Exception as e:
        logging.warning(f"Supabase annotation sync failed (degraded mode): {e}")


def _invalidate_annotations_cache():
    """Clear annotations cache after write."""
    global _annotations_cache
    _annotations_cache = None


def _create_merge_suggestion(
    target_id: str, source_id: str, submitted_by: str, confidence: str = "likely", reason: str = ""
) -> str:
    """Create a merge_suggestion annotation. Returns the annotation ID."""

    ann_id = str(uuid.uuid4())
    annotations = _main_mod._load_annotations()
    annotations["annotations"][ann_id] = {
        "annotation_id": ann_id,
        "type": "merge_suggestion",
        "target_type": "identity",
        "target_id": target_id,
        "value": json.dumps({"source_id": source_id, "target_id": target_id}),
        "confidence": confidence,
        "reason": reason,
        "submitted_by": submitted_by,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    _main_mod._save_annotations(annotations)
    return ann_id


def _photo_metadata_display(photo: dict):
    """Display stored photo metadata fields (BE-012)."""
    metadata_fields = {
        "date_taken": "Date",
        "location": "Location",
        "caption": "Caption",
        "occasion": "Occasion",
        "donor": "Donor",
        "camera": "Camera",
    }
    items = []
    for key, label in metadata_fields.items():
        value = photo.get(key)
        if value:
            items.append(
                P(Span(f"{label}: ", cls="text-slate-500"), Span(str(value), cls="text-slate-300"), cls="text-xs")
            )
    if not items:
        return Span()
    return Div(*items, cls="mt-2 space-y-0.5")


def _photo_annotations_section(photo_id: str, is_admin: bool = False):
    """
    AN-002–AN-006: Show approved photo annotations and a form to add new ones.
    Displays captions, dates, locations, stories, source attributions.
    """
    try:
        annotations = _main_mod._load_annotations()
    except Exception:
        annotations = {"annotations": {}}

    # Get approved annotations for this photo
    photo_anns = [
        ann
        for ann in annotations.get("annotations", {}).values()
        if ann.get("target_type") == "photo" and ann.get("target_id") == photo_id and ann.get("status") == "approved"
    ]

    # Also get pending count for admin badge (includes guest submissions)
    pending_count = sum(
        1
        for ann in annotations.get("annotations", {}).values()
        if ann.get("target_type") == "photo"
        and ann.get("target_id") == photo_id
        and ann.get("status") in ("pending", "pending_unverified")
    )

    # Display approved annotations grouped by type
    type_labels = {
        "caption": "Caption",
        "date": "Date",
        "location": "Location",
        "story": "Story",
        "source": "Source",
    }
    ann_items = []
    for ann in sorted(photo_anns, key=lambda a: a.get("submitted_at", "")):
        label = type_labels.get(ann["type"], ann["type"].title())
        ann_items.append(
            Div(
                Span(f"{label}: ", cls="text-slate-400 text-xs font-medium"),
                Span(ann["value"], cls="text-slate-300 text-xs"),
                cls="py-1",
            )
        )

    # Annotation submission form (available to any logged-in user)
    form = Div(
        Details(
            Summary("Add annotation", cls="text-xs text-indigo-400 hover:text-indigo-300 cursor-pointer"),
            Form(
                Input(type="hidden", name="target_type", value="photo"),
                Input(type="hidden", name="target_id", value=photo_id),
                Div(
                    Select(
                        Option("Caption", value="caption"),
                        Option("Date", value="date"),
                        Option("Location", value="location"),
                        Option("Story", value="story"),
                        Option("Source/Donor", value="source"),
                        name="annotation_type",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1 w-full",
                    ),
                    cls="mt-2",
                ),
                Div(
                    Textarea(
                        name="value",
                        placeholder="Enter annotation...",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1 w-full h-16 resize-none",
                        required=True,
                    ),
                    cls="mt-1",
                ),
                Div(
                    Select(
                        Option("Certain", value="certain"),
                        Option("Likely", value="likely", selected=True),
                        Option("Guess", value="guess"),
                        name="confidence",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1",
                    ),
                    Button(
                        "Submit",
                        type="submit",
                        cls="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1 rounded",
                    ),
                    cls="mt-1 flex gap-2 items-center",
                ),
                hx_post="/api/annotations/submit",
                hx_target=f"#photo-annotations-{photo_id}",
                hx_swap="outerHTML",
                cls="mt-2",
            ),
            cls="mt-2",
        ),
        cls="mt-2",
    )

    pending_badge = (
        Span(f" ({pending_count} pending)", cls="text-amber-400 text-xs") if pending_count and is_admin else None
    )

    return Div(
        *ann_items,
        form,
        pending_badge,
        id=f"photo-annotations-{photo_id}",
        cls="mt-3 border-t border-slate-700 pt-2" if ann_items else "mt-2",
    )


# --- Person Comments ---

_person_comments_cache = None


def _load_person_comments() -> dict:
    """Load person comments from data file."""
    global _person_comments_cache
    if _person_comments_cache is not None:
        return _person_comments_cache
    path = _main_mod.data_path / "person_comments.json"
    default = {"schema_version": 1, "comments": {}}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                _person_comments_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            _person_comments_cache = default
    else:
        _person_comments_cache = default
    return _person_comments_cache


def _save_person_comments(data: dict):
    """Save person comments atomically."""
    global _person_comments_cache
    path = _main_mod.data_path / "person_comments.json"
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(_main_mod.data_path), suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, str(path))
        _person_comments_cache = data
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _identity_metadata_display(identity: dict, is_admin: bool = False):
    """AN-012: Display identity metadata fields (bio, birth/death, relationships)."""
    identity_id = identity.get("identity_id", "")

    # Build compact summary line: "~1890–1944 · Rhodes → Auschwitz"
    summary_parts = []
    # Check metadata first, then ML estimates for birth year
    birth_year, by_source, _by_conf = _main_mod._get_birth_year(identity_id, identity)
    death_year = identity.get("death_year")
    if birth_year and death_year:
        prefix = "~" if by_source == "ml_inferred" else ""
        summary_parts.append(f"{prefix}{birth_year}–{death_year}")
    elif birth_year:
        prefix = "~" if by_source == "ml_inferred" else ""
        summary_parts.append(f"b. {prefix}{birth_year}")
    elif death_year:
        summary_parts.append(f"d. {death_year}")

    birth_place = identity.get("birth_place")
    death_place = identity.get("death_place")
    if birth_place and death_place:
        summary_parts.append(f"{birth_place} \u2192 {death_place}")
    elif birth_place:
        summary_parts.append(birth_place)
    elif death_place:
        summary_parts.append(death_place)

    maiden_name = identity.get("maiden_name")
    if maiden_name:
        summary_parts.append(f"n\u00e9e {maiden_name}")

    items = []
    if summary_parts:
        items.append(P(" \u00b7 ".join(summary_parts), cls="text-xs text-slate-400 italic"))

    # Additional fields shown below the summary
    detail_fields = {
        "relationship_notes": "Relationships",
        "bio": "Bio",
    }
    for key, label in detail_fields.items():
        value = identity.get(key)
        if value:
            items.append(
                P(Span(f"{label}: ", cls="text-slate-500"), Span(str(value), cls="text-slate-300"), cls="text-xs")
            )

    # Edit button for admins
    edit_btn = None
    if is_admin and identity_id:
        edit_btn = Button(
            "Edit Details" if not items else "Edit",
            cls="text-xs text-indigo-400 hover:text-indigo-300 underline",
            hx_get=f"/api/identity/{identity_id}/metadata-form",
            hx_target=f"#metadata-{identity_id}",
            hx_swap="innerHTML",
            type="button",
        )

    if not items and not edit_btn:
        return Span()

    return Div(
        Div(*items, cls="space-y-0.5") if items else None,
        edit_btn,
        id=f"metadata-{identity_id}",
        cls="mt-2",
    )


def _identity_annotations_section(identity_id: str, is_admin: bool = False):
    """
    AN-013/AN-014: Show approved identity annotations and submission form.
    Displays bio, relationship, story, and other identity-level annotations.
    """
    try:
        annotations = _main_mod._load_annotations()
    except Exception:
        annotations = {"annotations": {}}

    # Get approved annotations for this identity
    identity_anns = [
        ann
        for ann in annotations.get("annotations", {}).values()
        if ann.get("target_type") == "identity"
        and ann.get("target_id") == identity_id
        and ann.get("status") == "approved"
    ]

    # Pending count for admin badge (includes guest submissions)
    pending_count = sum(
        1
        for ann in annotations.get("annotations", {}).values()
        if ann.get("target_type") == "identity"
        and ann.get("target_id") == identity_id
        and ann.get("status") in ("pending", "pending_unverified")
    )

    # Display approved annotations grouped by type
    type_labels = {
        "bio": "Bio",
        "relationship": "Relationship",
        "story": "Story",
        "name_suggestion": "Name Suggestion",
        "caption": "Caption",
    }
    ann_items = []
    for ann in sorted(identity_anns, key=lambda a: a.get("submitted_at", "")):
        label = type_labels.get(ann["type"], ann["type"].title())
        ann_items.append(
            Div(
                Span(f"{label}: ", cls="text-slate-400 text-xs font-medium"),
                Span(ann["value"], cls="text-slate-300 text-xs"),
                cls="py-1",
            )
        )

    # Annotation submission form
    form = Div(
        Details(
            Summary("Add annotation", cls="text-xs text-indigo-400 hover:text-indigo-300 cursor-pointer"),
            Form(
                Input(type="hidden", name="target_type", value="identity"),
                Input(type="hidden", name="target_id", value=identity_id),
                Div(
                    Select(
                        Option("Bio", value="bio"),
                        Option("Relationship", value="relationship"),
                        Option("Story", value="story"),
                        Option("Caption", value="caption"),
                        name="annotation_type",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1 w-full",
                    ),
                    cls="mt-2",
                ),
                Div(
                    Textarea(
                        name="value",
                        placeholder="Enter annotation...",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1 w-full h-16 resize-none",
                        required=True,
                    ),
                    cls="mt-1",
                ),
                Div(
                    Select(
                        Option("Certain", value="certain"),
                        Option("Likely", value="likely", selected=True),
                        Option("Guess", value="guess"),
                        name="confidence",
                        cls="bg-slate-700 text-white text-xs rounded px-2 py-1",
                    ),
                    Button(
                        "Submit",
                        type="submit",
                        cls="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-1 rounded",
                    ),
                    cls="mt-1 flex gap-2 items-center",
                ),
                hx_post="/api/annotations/submit",
                hx_target=f"#identity-annotations-{identity_id}",
                hx_swap="outerHTML",
                cls="mt-2",
            ),
            cls="mt-2",
        ),
        cls="mt-2",
    )

    pending_badge = (
        Span(f" ({pending_count} pending)", cls="text-amber-400 text-xs") if pending_count and is_admin else None
    )

    return Div(
        *ann_items,
        form,
        pending_badge,
        id=f"identity-annotations-{identity_id}",
        cls="mt-3 border-t border-slate-700 pt-2" if ann_items else "mt-2",
    )


def _merge_annotations(source_id: str, target_id: str):
    """
    BE-006: When identities merge, retarget annotations from source to target.
    Annotations that targeted the source identity are updated to point at the target.
    This preserves contributor work across merges.
    """
    try:
        annotations = _main_mod._load_annotations()
        changed = False
        for ann in annotations.get("annotations", {}).values():
            if ann.get("target_type") == "identity" and ann.get("target_id") == source_id:
                ann["target_id"] = target_id
                changed = True
        if changed:
            _main_mod._save_annotations(annotations)
    except Exception:
        # Non-critical — don't block the merge
        pass


def _fire_recalibration_hook(action: str, id_a: str, id_b: str = None, anchor_face_ids: list = None):
    """Fire recalibration hook after merge/reject/confirm (AD-150).

    Best-effort: never blocks the primary action. Uses asyncio.run()
    because route handlers are sync but hooks are async.
    Production behavior is write-only: pair lineage is recorded, but fitting stays local.
    """
    import asyncio

    try:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return

        from rhodesli_ml.recalibration_hooks import (
            on_face_merge,
            on_identity_confirm,
            on_match_reject,
        )

        if action == "merge" and id_b:
            asyncio.run(
                on_face_merge(
                    id_a,
                    id_b,
                    supabase_client=sb,
                    source_surface="app.engagement_routes._fire_recalibration_hook",
                )
            )
        elif action == "reject" and id_b:
            asyncio.run(
                on_match_reject(
                    id_a,
                    id_b,
                    supabase_client=sb,
                    source_surface="app.engagement_routes._fire_recalibration_hook",
                )
            )
        elif action == "confirm" and anchor_face_ids:
            asyncio.run(
                on_identity_confirm(
                    id_a,
                    anchor_face_ids,
                    supabase_client=sb,
                    source_surface="app.engagement_routes._fire_recalibration_hook",
                )
            )
    except Exception as e:
        logger.warning(f"Recalibration hook ({action}) non-critical failure: {e}")


@rt("/api/annotations/submit")
def post(
    target_type: str,
    target_id: str,
    annotation_type: str,
    value: str,
    confidence: str = "likely",
    reason: str = "",
    sess=None,
):
    """
    Submit an annotation. Saves directly for all users — no modal interruption.
    Anonymous users save as pending_unverified; logged-in users save as pending.
    Types: name_suggestion, caption, date, location, story, relationship
    """
    # Validate value BEFORE auth check — empty input is always 400
    if not value or not value.strip():
        return Response(
            to_xml(_main_mod.toast("Please provide a value.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    user = _main_mod.get_current_user(sess) if sess is not None else None

    ann_id = str(uuid.uuid4())

    # Determine status and submitter based on auth state
    if user:
        submitted_by = user.email
        status = "pending"
    elif _main_mod.is_auth_enabled():
        submitted_by = "anonymous"
        status = "pending_unverified"
    else:
        submitted_by = "local_dev"
        status = "pending"

    annotations = _main_mod._load_annotations()

    # Dedup: check for existing annotation with same target + value + type (still pending)
    existing_ann = None
    for existing in annotations["annotations"].values():
        if (
            existing.get("target_id") == target_id
            and existing.get("type") == annotation_type
            and existing.get("value", "").strip().lower() == value.strip().lower()
            and existing.get("status") in ("pending", "pending_unverified")
        ):
            existing_ann = existing
            break

    if existing_ann:
        # Add a confirmation to the existing annotation instead of creating a new one
        if "confirmations" not in existing_ann:
            existing_ann["confirmations"] = []
        # Prevent same user from confirming twice
        already_confirmed = any(c.get("by") == submitted_by for c in existing_ann["confirmations"])
        # Also check if they are the original submitter
        is_original_submitter = existing_ann.get("submitted_by") == submitted_by
        if not already_confirmed and not is_original_submitter:
            existing_ann["confirmations"].append(
                {
                    "by": submitted_by,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        _main_mod._save_annotations(annotations)
        ann_id = existing_ann["annotation_id"]
    else:
        annotations["annotations"][ann_id] = {
            "annotation_id": ann_id,
            "type": annotation_type,
            "target_type": target_type,  # "identity" or "photo"
            "target_id": target_id,
            "value": value.strip(),
            "confidence": confidence,
            "reason": reason.strip() if reason else "",
            "submitted_by": submitted_by,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "reviewed_by": None,
            "reviewed_at": None,
            "confirmations": [],
        }
        _main_mod._save_annotations(annotations)

    # If submitted from face tag dropdown, return inline confirmation + OOB toast
    if reason and reason.startswith("face_tag:") and annotation_type == "name_suggestion":
        parts = reason.split(":")
        face_id_from_reason = parts[1] if len(parts) >= 2 else ""
        confirmation = Div(
            Div(
                Span("You suggested: ", cls="text-emerald-400 text-sm"),
                Span(value.strip(), cls="text-sm font-medium text-white"),
                cls="flex items-center gap-1",
            ),
            Span("Pending review", cls="text-xs text-slate-500"),
            cls="p-2 bg-emerald-900/20 border border-emerald-700/30 rounded-lg text-center",
        )
        oob_toast = Div(
            _main_mod.toast("Thanks! Your suggestion has been submitted for review.", "success"),
            id="toast-container",
            hx_swap_oob="beforeend",
        )
        return Response(to_xml(confirmation) + to_xml(oob_toast))

    return Response(
        to_xml(_main_mod.toast("Thanks! Your suggestion has been submitted for review.", "success")),
        headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
    )


def _submit_pending_annotation(sess, user) -> bool:
    """Submit a stashed annotation from session. Returns True if submitted."""
    pending = sess.get("pending_annotation")
    if not pending:
        return False

    ann_id = str(uuid.uuid4())

    annotations = _main_mod._load_annotations()
    annotations["annotations"][ann_id] = {
        "annotation_id": ann_id,
        "type": pending.get("annotation_type", "name_suggestion"),
        "target_type": pending.get("target_type", "identity"),
        "target_id": pending.get("target_id", ""),
        "value": pending.get("value", "").strip(),
        "confidence": pending.get("confidence", "likely"),
        "reason": pending.get("reason", "").strip(),
        "submitted_by": user.email,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    _main_mod._save_annotations(annotations)
    del sess["pending_annotation"]
    return True


@rt("/api/annotations/guest-submit")
def post(
    target_type: str, target_id: str, annotation_type: str, value: str, confidence: str = "likely", reason: str = ""
):
    """Save an annotation as anonymous guest. No auth required."""
    if not value or not value.strip():
        return Response(
            to_xml(_main_mod.toast("Please provide a value.", "warning")),
            status_code=400,
            headers={"HX-Reswap": "beforeend", "HX-Retarget": "#toast-container"},
        )

    ann_id = str(uuid.uuid4())

    annotations = _main_mod._load_annotations()
    annotations["annotations"][ann_id] = {
        "annotation_id": ann_id,
        "type": annotation_type,
        "target_type": target_type,
        "target_id": target_id,
        "value": value.strip(),
        "confidence": confidence,
        "reason": reason.strip() if reason else "",
        "submitted_by": "anonymous",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_unverified",
        "reviewed_by": None,
        "reviewed_at": None,
    }
    _main_mod._save_annotations(annotations)

    # Clear the modal and show toast
    return Response(
        to_xml(
            Div(
                _main_mod.toast("Thanks! Your suggestion is pending admin review.", "success"),
                id="guest-or-login-modal",
                hx_swap_oob="true",
            )
        ),
        headers={"HX-Retarget": "#guest-or-login-modal", "HX-Reswap": "innerHTML"},
    )


@rt("/api/annotations/stash-and-login")
def post(
    target_type: str,
    target_id: str,
    annotation_type: str,
    value: str,
    confidence: str = "likely",
    reason: str = "",
    sess=None,
):
    """Stash annotation in session and show login form."""
    if sess is not None:
        sess["pending_annotation"] = {
            "target_type": target_type,
            "target_id": target_id,
            "annotation_type": annotation_type,
            "value": value,
            "confidence": confidence,
            "reason": reason,
        }

    google_url = _main_mod.get_oauth_url("google")

    return Div(
        Div(
            H2("Sign in to save", cls="text-xl font-bold text-white"),
            Button(
                "X",
                cls="text-slate-400 hover:text-white text-xl font-bold",
                **{"_": "on click set #guest-or-login-modal's innerHTML to ''"},
                type="button",
                aria_label="Close",
            ),
            cls="flex justify-between items-center mb-4 pb-2 border-b border-slate-700",
        ),
        Div(
            P("Your suggestion:", cls="text-slate-500 text-xs"),
            P(f'"{value}"', cls="text-slate-300 text-sm font-medium"),
            cls="bg-slate-700/50 rounded p-3 mb-4",
        ),
        Form(
            Div(
                Label("Email", fr="guest-email", cls="block text-sm mb-1 text-slate-300"),
                Input(
                    type="email",
                    name="email",
                    id="guest-email",
                    required=True,
                    cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600",
                ),
                cls="mb-4",
            ),
            Div(
                Label("Password", fr="guest-password", cls="block text-sm mb-1 text-slate-300"),
                Input(
                    type="password",
                    name="password",
                    id="guest-password",
                    required=True,
                    cls="w-full p-2 rounded bg-slate-700 text-white border border-slate-600",
                ),
                cls="mb-4",
            ),
            Button(
                "Sign in & submit",
                type="submit",
                cls="w-full p-2 bg-blue-600 hover:bg-blue-700 rounded text-white font-medium",
            ),
            Div(id="guest-login-error", cls="text-red-400 text-sm mt-2"),
            hx_post="/api/annotations/login-and-submit",
            hx_target="#guest-login-error",
            hx_swap="innerHTML",
        ),
        # Google OAuth divider + button
        Div(
            Div(cls="flex-grow border-t border-slate-600"),
            Span("or", cls="px-4 text-slate-500 text-sm"),
            Div(cls="flex-grow border-t border-slate-600"),
            cls="flex items-center my-4",
        )
        if google_url
        else None,
        A(
            NotStr(
                '<svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>'
            ),
            Span("Sign in with Google"),
            href=google_url or "#",
            style="display: flex; align-items: center; gap: 12px; padding: 0 16px; height: 40px; "
            "background: white; border: 1px solid #dadce0; border-radius: 4px; cursor: pointer; "
            "font-family: 'Roboto', Arial, sans-serif; font-size: 14px; color: #3c4043; "
            "font-weight: 500; text-decoration: none; justify-content: center; width: 100%;",
        )
        if google_url
        else None,
        Div(
            P(
                "No account? ",
                A("Sign up with invite code", href="/signup", cls="text-blue-400 hover:underline"),
                cls="text-sm text-slate-400",
            ),
            cls="mt-4 text-center",
        ),
        cls="bg-slate-800 rounded-lg shadow-2xl max-w-md w-full p-4 sm:p-8 relative border border-slate-700",
    )


@rt("/api/annotations/login-and-submit")
async def post(email: str, password: str, sess):
    """Authenticate and submit the stashed annotation."""
    user, error = await _main_mod.login_with_supabase(email, password)
    if error:
        return error
    sess["auth"] = user
    _main_mod._submit_pending_annotation(sess, user)
    return Response("", headers={"HX-Refresh": "true"})


@rt("/my-contributions")
def get(sess=None):
    """User's contribution history — annotations AND uploads."""
    denied = _main_mod._check_login(sess)
    if denied:
        return RedirectResponse("/login", status_code=303)

    user = _main_mod.get_current_user(sess)
    if not user:
        return RedirectResponse("/login", status_code=303)

    # --- Annotation contributions ---
    annotations = _main_mod._load_annotations()
    my_anns = [a for a in annotations["annotations"].values() if a.get("submitted_by") == user.email]
    my_anns.sort(key=lambda a: a.get("submitted_at", ""), reverse=True)

    ann_rows = []
    ann_stats = {"pending": 0, "approved": 0, "rejected": 0}
    for a in my_anns:
        status = a.get("status", "pending")
        if status in ann_stats:
            ann_stats[status] += 1
        status_cls = {
            "pending": "text-amber-400 bg-amber-900/30",
            "pending_unverified": "text-amber-400 bg-amber-900/30",
            "approved": "text-emerald-400 bg-emerald-900/30",
            "rejected": "text-red-400 bg-red-900/30",
        }.get(status, "text-slate-400 bg-slate-800")

        ann_rows.append(
            Div(
                Div(
                    Span(a["type"].replace("_", " ").title(), cls="text-sm font-medium text-white"),
                    Span(status.upper(), cls=f"text-xs px-2 py-0.5 rounded ml-2 {status_cls}"),
                    cls="flex items-center",
                ),
                P(f'"{a["value"]}"', cls="text-sm text-slate-300 mt-1"),
                P(f"Submitted {a.get('submitted_at', '')[:10]}", cls="text-xs text-slate-500"),
                cls="bg-slate-800 rounded-lg p-4 border border-slate-700",
            )
        )

    # --- Upload contributions ---
    pending = _main_mod._load_pending_uploads()
    my_uploads = [
        u
        for u in pending.get("uploads", {}).values()
        if u.get("uploader_email") == user.email or u.get("uploaded_by") == user.email
    ]
    my_uploads.sort(key=lambda u: u.get("submitted_at", ""), reverse=True)

    upload_rows = []
    upload_stats = {"pending": 0, "approved": 0, "rejected": 0, "staged": 0, "processed": 0}
    for u in my_uploads:
        status = u.get("status", "pending")
        if status in upload_stats:
            upload_stats[status] += 1
        status_cls = {
            "pending": "text-amber-400 bg-amber-900/30",
            "staged": "text-amber-400 bg-amber-900/30",
            "approved": "text-emerald-400 bg-emerald-900/30",
            "processed": "text-emerald-400 bg-emerald-900/30",
            "rejected": "text-red-400 bg-red-900/30",
        }.get(status, "text-slate-400 bg-slate-800")

        file_count = u.get("file_count", len(u.get("files", [])))
        source = u.get("source", "Upload")
        upload_rows.append(
            Div(
                Div(
                    Span(f"{file_count} photo{'s' if file_count != 1 else ''}", cls="text-sm font-medium text-white"),
                    Span(status.upper(), cls=f"text-xs px-2 py-0.5 rounded ml-2 {status_cls}"),
                    cls="flex items-center",
                ),
                P(f"Source: {source}", cls="text-sm text-slate-300 mt-1") if source else None,
                P(f"Submitted {u.get('submitted_at', '')[:19].replace('T', ' ')}", cls="text-xs text-slate-500"),
                cls="bg-slate-800 rounded-lg p-4 border border-slate-700",
            )
        )

    # --- Summary stats ---
    total_anns = len(my_anns)
    total_uploads = len(my_uploads)
    summary = Div(
        Div(
            Div(
                P(str(total_anns), cls="text-2xl font-bold text-white"),
                P("Name Suggestions", cls="text-xs text-slate-400"),
                cls="text-center",
            ),
            Div(
                P(str(ann_stats["approved"]), cls="text-2xl font-bold text-emerald-400"),
                P("Approved", cls="text-xs text-slate-400"),
                cls="text-center",
            ),
            Div(
                P(str(ann_stats["pending"]), cls="text-2xl font-bold text-amber-400"),
                P("Pending", cls="text-xs text-slate-400"),
                cls="text-center",
            ),
            Div(
                P(str(total_uploads), cls="text-2xl font-bold text-white"),
                P("Photos Uploaded", cls="text-xs text-slate-400"),
                cls="text-center",
            ),
            cls="grid grid-cols-4 gap-4 mb-6",
        ),
        cls="bg-slate-800/50 rounded-lg p-4 border border-slate-700 mb-6",
    )

    # --- Sections ---
    sections = [summary]

    if ann_rows:
        sections.append(H2("Name Suggestions", cls="text-lg font-semibold text-white mb-3"))
        sections.append(Div(*ann_rows, cls="space-y-3 mb-6"))

    if upload_rows:
        sections.append(H2("Photo Uploads", cls="text-lg font-semibold text-white mb-3"))
        sections.append(Div(*upload_rows, cls="space-y-3 mb-6"))

    if not ann_rows and not upload_rows:
        sections.append(
            Div(
                P("No contributions yet.", cls="text-slate-400 text-lg"),
                P(
                    "Here's how to get started:",
                    cls="text-sm text-slate-500 mt-2 mb-4",
                ),
                Div(
                    A(
                        "Browse Photos",
                        href="/?section=photos",
                        cls="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 text-sm",
                    ),
                    A(
                        "Compare Faces",
                        href="/tools/compare",
                        cls="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 text-sm",
                    ),
                    A(
                        "Help Identify",
                        href="/?section=skipped",
                        cls="px-4 py-2 bg-amber-700 text-white rounded-lg hover:bg-amber-600 text-sm",
                    ),
                    cls="flex gap-3 justify-center",
                ),
                cls="text-center py-12",
            )
        )

    return Title("My Contributions — Rhodesli"), Div(
        Div(
            H1("My Contributions", cls="text-2xl font-bold text-white"),
            cls="mb-6",
        ),
        *sections,
        cls="max-w-3xl mx-auto p-6",
    )


@rt("/activity")
def get(sess=None):
    """
    Public activity feed showing recent identifications and contributions.
    Shows what's happening in the archive — motivates contributors.
    """
    actions = _main_mod._load_activity_feed(limit=50)

    rows = []
    for a in actions:
        action_type = a.get("type") or "unknown"
        description = a.get("description") or "Activity updated"
        timestamp = a.get("timestamp") or ""
        icon = {
            "MERGE": "🔗",
            "CONFIRM": "✓",
            "RENAME": "✏️",
            "SKIP": "⏭",
            "annotation_approved": "📝",
        }.get(action_type, "•")

        rows.append(
            Div(
                Span(icon, cls="text-lg mr-2"),
                Span(description, cls="text-sm text-slate-300"),
                Span(timestamp[:10], cls="text-xs text-slate-500 ml-auto"),
                cls="flex items-center gap-2 py-2 border-b border-slate-800",
            )
        )

    if not rows:
        rows = [
            Div(
                P("No activity yet. Be the first to identify someone!", cls="text-slate-400 text-center py-12"),
            )
        ]

    return Title("Activity — Rhodesli"), Div(
        Div(
            H1("Recent Activity", cls="text-2xl font-bold text-white"),
            A("Back to Archive", href="/", cls="text-sm text-indigo-400 hover:text-indigo-300"),
            cls="flex items-center justify-between mb-6",
        ),
        Div(*rows, cls="space-y-0"),
        cls="max-w-3xl mx-auto p-6",
    )
