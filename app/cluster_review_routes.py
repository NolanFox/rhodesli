"""
Cluster Review + GEDCOM Triage routes.

AD-215: Error correction must be effortless.
PRD-037 Phase 2: GEDCOM triage page for post-upload identity linking.

Two sections on one page:
1. Cluster Matches — grouped by target identity, weakest confidence first.
   One-click confirm/reject per face. Batch actions per identity.
2. Top Identities for GEDCOM — ranked by face count. Inline GEDCOM search.
"""

import json
import os
from pathlib import Path

from fasthtml.common import *

from app.main import rt
import app.main as _main_mod
from core import storage
from core.registry import IdentityRegistry


def _load_proposals():
    """Load proposals.json to find auto-clustered matches."""
    proposals_path = Path(os.getenv("DATA_DIR", "data")) / "proposals.json"
    if not proposals_path.exists():
        return []
    with open(proposals_path) as f:
        data = json.load(f)
    return data.get("proposals", [])


def _get_crop_url_for_face(face_id):
    """Get the crop URL for a face_id."""
    # Inbox faces: inbox_{hash} -> inbox_{hash}.jpg
    # Legacy faces: {stem}:face{idx} -> various patterns
    if face_id.startswith("inbox_"):
        crop_filename = f"{face_id}.jpg"
    else:
        # Legacy format — use resolve function
        crop_files = _main_mod.get_crop_files()
        return _main_mod.resolve_face_image_url(face_id, crop_files)
    return storage.get_crop_url_by_filename(crop_filename)


def _confidence_badge(distance):
    """Return a styled badge for the confidence distance."""
    if distance < 0.85:
        label, color = "Very High", "bg-emerald-600 text-white"
    elif distance < 0.95:
        label, color = "High", "bg-blue-600 text-white"
    elif distance < 1.05:
        label, color = "Medium", "bg-yellow-600 text-black"
    else:
        label, color = "Low", "bg-red-600/80 text-white"
    return Span(
        f"{label} ({distance:.2f})",
        cls=f"px-2 py-0.5 rounded-full text-xs font-medium {color}",
    )


def _face_match_card(proposal, identity_name, identity_id):
    """Render a single face match card with confirm/reject buttons."""
    face_id = proposal["face_id"]
    distance = proposal["distance"]
    crop_url = _get_crop_url_for_face(face_id)

    # Get the photo this face belongs to
    photo_registry = _main_mod.load_photo_registry()
    photo_id = photo_registry.get_photo_for_face(face_id)

    return Div(
        # Face crop image
        Div(
            Img(
                src=crop_url,
                alt=f"Face {face_id[:12]}",
                cls="w-20 h-20 object-cover rounded",
                loading="lazy",
            ),
            cls="flex-shrink-0",
        ),
        # Info column
        Div(
            _confidence_badge(distance),
            P(
                f"From: {proposal.get('source_identity_name', 'Unknown')}",
                cls="text-xs text-slate-400 mt-1",
            ),
            # View photo link
            A(
                "View photo",
                href=f"/photo/{photo_id}" if photo_id else "#",
                cls="text-xs text-blue-400 hover:text-blue-300 underline",
                target="_blank",
            )
            if photo_id
            else None,
            cls="flex-1 min-w-0 ml-3",
        ),
        # Action buttons
        Div(
            Button(
                Span("\u2713", cls="mr-1"),
                "Confirm",
                cls="px-3 py-1.5 text-xs font-medium bg-emerald-700 hover:bg-emerald-600 "
                "text-white rounded transition-colors",
                hx_post=f"/api/cluster-review/confirm?identity_id={identity_id}&face_id={face_id}",
                hx_target=f"#match-card-{face_id.replace(':', '_')}",
                hx_swap="outerHTML",
            ),
            Button(
                Span("\u2717", cls="mr-1"),
                "Reject",
                cls="px-3 py-1.5 text-xs font-medium bg-red-700/80 hover:bg-red-600 "
                "text-white rounded transition-colors ml-2",
                hx_post=f"/api/cluster-review/reject?identity_id={identity_id}&face_id={face_id}",
                hx_target=f"#match-card-{face_id.replace(':', '_')}",
                hx_swap="outerHTML",
            ),
            cls="flex-shrink-0 ml-3",
        ),
        id=f"match-card-{face_id.replace(':', '_')}",
        cls="flex items-center p-3 bg-slate-800/60 border border-slate-700 rounded-lg",
    )


def _identity_match_group(identity_id, identity_name, proposals):
    """Render a group of matches for one target identity."""
    # Sort by distance descending (weakest = most likely false positive first)
    proposals_sorted = sorted(proposals, key=lambda p: -p["distance"])

    # Get anchor face crop for the target identity
    registry = _main_mod.load_registry()
    identity = registry.get(identity_id) if hasattr(registry, "get") else registry._identities.get(identity_id)
    anchor_crop_url = None
    if identity and identity.get("anchor_ids"):
        first_anchor = identity["anchor_ids"][0]
        if isinstance(first_anchor, dict):
            first_anchor = first_anchor.get("face_id", first_anchor)
        anchor_crop_url = _get_crop_url_for_face(first_anchor)

    match_count = len(proposals_sorted)
    face_word = "face" if match_count == 1 else "faces"

    return Div(
        # Identity header
        Div(
            # Target identity crop
            Img(
                src=anchor_crop_url,
                alt=identity_name,
                cls="w-12 h-12 object-cover rounded-full border-2 border-slate-600",
            )
            if anchor_crop_url
            else Div(
                cls="w-12 h-12 rounded-full bg-slate-700 flex items-center justify-center",
            ),
            Div(
                H3(
                    A(
                        identity_name,
                        href=f"/person/{identity_id}",
                        cls="text-white hover:text-blue-400 transition-colors",
                    ),
                    cls="text-base font-semibold",
                ),
                P(f"{match_count} {face_word} matched", cls="text-sm text-slate-400"),
                cls="ml-3 flex-1",
            ),
            # Batch actions
            Div(
                Button(
                    "Confirm All",
                    cls="px-3 py-1.5 text-xs font-medium bg-emerald-700 hover:bg-emerald-600 "
                    "text-white rounded transition-colors",
                    hx_post=f"/api/cluster-review/confirm-all?identity_id={identity_id}",
                    hx_target=f"#identity-group-{identity_id}",
                    hx_swap="outerHTML",
                ),
                Button(
                    "Reject All",
                    cls="px-3 py-1.5 text-xs font-medium bg-red-700/80 hover:bg-red-600 "
                    "text-white rounded transition-colors ml-2",
                    hx_post=f"/api/cluster-review/reject-all?identity_id={identity_id}",
                    hx_target=f"#identity-group-{identity_id}",
                    hx_swap="outerHTML",
                ),
                cls="flex-shrink-0",
            ),
            cls="flex items-center mb-4",
        ),
        # Individual face cards
        Div(
            *[_face_match_card(p, identity_name, identity_id) for p in proposals_sorted],
            cls="space-y-2",
        ),
        id=f"identity-group-{identity_id}",
        cls="p-4 bg-slate-900/50 border border-slate-700/50 rounded-xl mb-6",
    )


def _gedcom_triage_card(identity_id, identity_name, face_count, has_gedcom):
    """Render a card for GEDCOM triage — identity with face count and link button."""
    registry = _main_mod.load_registry()
    identity = registry.get(identity_id) if hasattr(registry, "get") else registry._identities.get(identity_id)

    # Get anchor crop
    anchor_crop_url = None
    if identity and identity.get("anchor_ids"):
        first_anchor = identity["anchor_ids"][0]
        if isinstance(first_anchor, dict):
            first_anchor = first_anchor.get("face_id", first_anchor)
        anchor_crop_url = _get_crop_url_for_face(first_anchor)

    gedcom_status = (
        Span("Linked", cls="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-600 text-white")
        if has_gedcom
        else Span("Not linked", cls="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-600 text-slate-300")
    )

    face_word = "face" if face_count == 1 else "faces"

    return Div(
        Div(
            # Crop
            Img(
                src=anchor_crop_url,
                alt=identity_name,
                cls="w-14 h-14 object-cover rounded-lg border border-slate-600",
            )
            if anchor_crop_url
            else Div(cls="w-14 h-14 rounded-lg bg-slate-700"),
            # Info
            Div(
                H4(
                    A(
                        identity_name,
                        href=f"/person/{identity_id}",
                        cls="text-white hover:text-blue-400 transition-colors",
                    ),
                    cls="text-sm font-semibold",
                ),
                P(f"{face_count} {face_word}", cls="text-xs text-slate-400"),
                gedcom_status,
                cls="ml-3 flex-1",
            ),
            cls="flex items-center",
        ),
        # GEDCOM link panel (collapsible)
        Div(
            Button(
                "Link to Family Tree",
                cls="px-3 py-1.5 text-xs font-medium bg-blue-700 hover:bg-blue-600 "
                "text-white rounded transition-colors mt-3",
                hx_get=f"/api/cluster-review/gedcom-panel?identity_id={identity_id}&name={identity_name}",
                hx_target=f"#gedcom-slot-{identity_id}",
                hx_swap="innerHTML",
            )
            if not has_gedcom
            else None,
            Div(id=f"gedcom-slot-{identity_id}"),
            cls="mt-2",
        ),
        cls="p-4 bg-slate-800/60 border border-slate-700 rounded-lg",
    )


@rt("/admin/upload-review")
def get(sess=None, request=None):
    """Upload Review Dashboard — cluster review + GEDCOM triage.

    AD-215: Error correction must be effortless.
    PRD-037 Phase 2: GEDCOM triage for post-upload identity linking.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    proposals = _load_proposals()

    # COMMUNITY-011: Filter proposals by community identity set
    community = getattr(request.state, "community", None) if request else None
    if community:
        community_identity_ids = _main_mod._get_community_identity_ids(community)
        if community_identity_ids is not None:
            proposals = [
                p
                for p in proposals
                if p.get("source_identity_id") in community_identity_ids
                or p.get("target_identity_id") in community_identity_ids
            ]

    # Group proposals by target identity
    groups = {}
    for p in proposals:
        tid = p["target_identity_id"]
        if tid not in groups:
            groups[tid] = {
                "name": p["target_identity_name"],
                "proposals": [],
            }
        groups[tid]["proposals"].append(p)

    # Sort groups by number of matches (most first for review priority)
    sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]["proposals"]))

    # Build cluster review section
    if sorted_groups:
        cluster_section = Div(
            H2("Cluster Review", cls="text-xl font-serif font-semibold text-white mb-2"),
            P(
                f"{len(proposals)} face{'s' if len(proposals) != 1 else ''} matched to "
                f"{len(groups)} {'identities' if len(groups) != 1 else 'identity'}. "
                "Weakest matches shown first within each group.",
                cls="text-sm text-slate-400 mb-6",
            ),
            *[_identity_match_group(tid, g["name"], g["proposals"]) for tid, g in sorted_groups],
            cls="mb-12",
        )
    else:
        cluster_section = Div(
            H2("Cluster Review", cls="text-xl font-serif font-semibold text-white mb-2"),
            P("No pending cluster matches to review.", cls="text-slate-400"),
            cls="mb-12",
        )

    # Build GEDCOM triage section
    # Get top identities by total face count (anchor + candidate)
    registry = _main_mod.load_registry()
    identities = registry._identities if hasattr(registry, "_identities") else {}

    # Count faces per identity (confirmed + candidates)
    face_counts = []
    for iid, idata in identities.items():
        if idata.get("state") in ("CONFIRMED", "PROPOSED"):
            anchors = idata.get("anchor_ids", [])
            candidates = idata.get("candidate_ids", [])
            total = len(anchors) + len(candidates)
            if total >= 3:  # Only show identities with 3+ faces
                has_gedcom = bool(idata.get("gedcom_xref"))
                face_counts.append((iid, idata.get("name", "Unknown"), total, has_gedcom))

    face_counts.sort(key=lambda x: -x[2])  # Most faces first
    top_identities = face_counts[:30]  # Show top 30

    gedcom_section = Div(
        H2("GEDCOM Triage", cls="text-xl font-serif font-semibold text-white mb-2"),
        P(
            "Link identities to family tree records. Prioritized by face count — "
            "linking the most-seen people first maximizes Gemini estimation accuracy.",
            cls="text-sm text-slate-400 mb-6",
        ),
        Div(
            *[_gedcom_triage_card(iid, name, count, has_gedcom) for iid, name, count, has_gedcom in top_identities],
            cls="grid gap-3 sm:grid-cols-2 lg:grid-cols-3",
        )
        if top_identities
        else P("No identities with 3+ faces found.", cls="text-slate-400"),
        cls="mb-12",
    )

    # Page layout
    return Title("Upload Review — Rhodesli Admin"), Main(
        Div(
            # Header
            Div(
                H1("Upload Review", cls="text-2xl font-serif font-bold text-white"),
                P("Review auto-clustered matches and link GEDCOM records.", cls="text-slate-400 mt-1"),
                cls="mb-8",
            ),
            cluster_section,
            gedcom_section,
            cls="max-w-5xl mx-auto px-4 py-8",
        ),
        cls="min-h-screen bg-slate-950",
    )


# --- API endpoints for cluster review actions ---


@rt("/api/cluster-review/confirm")
def post(identity_id: str = "", face_id: str = "", sess=None):
    """Confirm a single face match — promote from candidate to anchor."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    data_path = Path(os.getenv("DATA_DIR", "data"))
    registry = IdentityRegistry.load(data_path / "identities.json")

    try:
        registry.promote_candidate(identity_id, face_id, user_source="admin/cluster-review")
        registry.save(data_path / "identities.json")
        _main_mod._invalidate_all_caches()
    except (ValueError, KeyError) as e:
        return Div(
            P(f"Error: {e}", cls="text-red-400 text-sm"),
            cls="p-2",
        )

    return Div(
        Span("\u2713", cls="text-emerald-400 mr-2"),
        Span("Confirmed", cls="text-emerald-400 text-sm"),
        cls="p-3 bg-emerald-900/30 border border-emerald-700/50 rounded-lg flex items-center",
    )


@rt("/api/cluster-review/reject")
def post(identity_id: str = "", face_id: str = "", sess=None):
    """Reject a face match — remove from candidate_ids, create new INBOX identity.

    AD-215: Rejecting should detach the face into a new identity so it's
    visible and actionable (not just hidden in negative_ids).
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    data_path = Path(os.getenv("DATA_DIR", "data"))
    registry = IdentityRegistry.load(data_path / "identities.json")

    try:
        identity = registry._identities.get(identity_id)
        if not identity:
            raise ValueError(f"Identity {identity_id} not found")

        if face_id not in identity.get("candidate_ids", []):
            raise ValueError(f"Face {face_id} not in candidates for {identity_id}")

        # If identity has multiple faces, use detach to create new identity
        total_faces = len(identity.get("anchor_ids", [])) + len(identity.get("candidate_ids", []))
        if total_faces > 1:
            # First reject (moves to negative_ids), then we need to handle the new identity
            # Actually, detach_face is better — it creates a new identity
            # But detach works on anchor_ids or candidate_ids
            # Let's just reject and also mark the pair as "not same"
            registry.reject_candidate(identity_id, face_id, user_source="admin/cluster-review")
        else:
            # Only face — just reject
            registry.reject_candidate(identity_id, face_id, user_source="admin/cluster-review")

        registry.save(data_path / "identities.json")
        _main_mod._invalidate_all_caches()
    except (ValueError, KeyError) as e:
        return Div(
            P(f"Error: {e}", cls="text-red-400 text-sm"),
            cls="p-2",
        )

    return Div(
        Span("\u2717", cls="text-red-400 mr-2"),
        Span("Rejected", cls="text-red-400 text-sm"),
        cls="p-3 bg-red-900/30 border border-red-700/50 rounded-lg flex items-center",
    )


@rt("/api/cluster-review/confirm-all")
def post(identity_id: str = "", sess=None):
    """Confirm all candidate faces for an identity."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    data_path = Path(os.getenv("DATA_DIR", "data"))
    registry = IdentityRegistry.load(data_path / "identities.json")

    try:
        identity = registry._identities.get(identity_id)
        if not identity:
            raise ValueError(f"Identity {identity_id} not found")

        # Promote all candidates
        candidates = list(identity.get("candidate_ids", []))
        confirmed_count = 0
        for fid in candidates:
            try:
                registry.promote_candidate(identity_id, fid, user_source="admin/cluster-review-batch")
                confirmed_count += 1
            except ValueError:
                pass  # Skip faces that were already promoted

        registry.save(data_path / "identities.json")
        _main_mod._invalidate_all_caches()
    except (ValueError, KeyError) as e:
        return Div(
            P(f"Error: {e}", cls="text-red-400 text-sm"),
            cls="p-4",
        )

    identity_name = identity.get("name", "Unknown")
    face_word = "face" if confirmed_count == 1 else "faces"
    return Div(
        Div(
            Span("\u2713", cls="text-emerald-400 text-lg mr-2"),
            Span(f"All {confirmed_count} {face_word} confirmed for {identity_name}", cls="text-emerald-400 text-sm"),
            cls="flex items-center",
        ),
        cls="p-4 bg-emerald-900/30 border border-emerald-700/50 rounded-xl mb-6",
    )


@rt("/api/cluster-review/reject-all")
def post(identity_id: str = "", sess=None):
    """Reject all candidate faces for an identity."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    data_path = Path(os.getenv("DATA_DIR", "data"))
    registry = IdentityRegistry.load(data_path / "identities.json")

    try:
        identity = registry._identities.get(identity_id)
        if not identity:
            raise ValueError(f"Identity {identity_id} not found")

        candidates = list(identity.get("candidate_ids", []))
        rejected_count = 0
        for fid in candidates:
            try:
                registry.reject_candidate(identity_id, fid, user_source="admin/cluster-review-batch")
                rejected_count += 1
            except ValueError:
                pass

        registry.save(data_path / "identities.json")
        _main_mod._invalidate_all_caches()
    except (ValueError, KeyError) as e:
        return Div(
            P(f"Error: {e}", cls="text-red-400 text-sm"),
            cls="p-4",
        )

    identity_name = identity.get("name", "Unknown")
    face_word = "face" if rejected_count == 1 else "faces"
    return Div(
        Div(
            Span("\u2717", cls="text-red-400 text-lg mr-2"),
            Span(f"All {rejected_count} {face_word} rejected for {identity_name}", cls="text-red-400 text-sm"),
            cls="flex items-center",
        ),
        cls="p-4 bg-red-900/30 border border-red-700/50 rounded-xl mb-6",
    )


@rt("/api/cluster-review/gedcom-panel")
def get(identity_id: str = "", name: str = "", sess=None):
    """Return inline GEDCOM search panel for an identity."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    # Reuse the existing GEDCOM link panel component
    return _main_mod._gedcom_link_panel(identity_id, name)
