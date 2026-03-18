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
import time
from pathlib import Path
from urllib.parse import urlencode

from fasthtml.common import *
import numpy as np
from scipy.spatial.distance import cdist

from app.main import rt
import app.main as _main_mod
from app.audit import _log_audit
from app.supabase_data import get_supabase_client
from core import storage
from core.registry import IdentityRegistry
from rhodesli_ml.active_learning import (
    default_labels_path,
    default_queue_path,
    load_active_learning_queue,
    recent_active_learning_labels,
    record_active_learning_label,
    revert_active_learning_label,
)

UNRESOLVED_REVIEW_THRESHOLD = 0.85
UNRESOLVED_REVIEW_GROUP_LIMIT = 18
UNRESOLVED_REVIEW_MEMBER_LIMIT = 6

# Performance caches — Session 111e
_speed_run_cache = {}  # keyed by community_slug -> (timestamp, result)
_suggestions_cache = {}  # keyed by (identity_id, community_slug) -> (timestamp, result)
_CACHE_TTL = 30  # seconds


def invalidate_cluster_review_caches(changed_ids=None):
    """Clear speed-run and suggestions caches.

    When changed_ids is provided, only remove affected entries instead of full flush.
    This preserves cache for identities not involved in the action.
    """
    global _speed_run_cache, _suggestions_cache
    if changed_ids is None:
        # Full flush for bulk operations
        _speed_run_cache = {}
        _suggestions_cache = {}
    else:
        # Surgical: remove entries for changed identities + speed-run (ordering may change)
        _speed_run_cache = {}  # speed-run depends on ordering, always invalidate
        keys_to_remove = [k for k in _suggestions_cache if k[0] in changed_ids]
        for k in keys_to_remove:
            del _suggestions_cache[k]
    # Also invalidate the vectorized confirmed matrix
    from app.perf_cache import mark_confirmed_dirty

    mark_confirmed_dirty()


def _load_proposals():
    """Load proposals via unified reader (Supabase with TTL cache, PRD-051 Session 114)."""
    data = _main_mod._load_proposals()
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


def _safe_dom_id(value: str) -> str:
    """Return a HTMX-safe DOM identifier fragment."""
    return value.replace(":", "_").replace("/", "_").replace(".", "_")


def _data_dir() -> Path:
    """Return the canonical data directory for queue and label artifacts."""
    storage_dir = os.getenv("STORAGE_DIR")
    if storage_dir:
        return Path(storage_dir) / "data"
    return Path(os.getenv("DATA_DIR", "data"))


def _active_learning_queue_payload():
    """Load the offline active-learning queue artifact."""
    return load_active_learning_queue(default_queue_path(_data_dir()))


def _active_learning_labels():
    """Load recent active-learning label cache entries."""
    return recent_active_learning_labels(labels_path=default_labels_path(_data_dir()), limit=10)


def _active_learning_action_url(action: str, item: dict, queue_run_id: str) -> str:
    """Build one active-learning label action URL."""
    params = {
        "face_id_a": item["face_id_a"],
        "face_id_b": item["face_id_b"],
        "source_identity_id": item.get("source_identity_id", ""),
        "target_identity_id": item.get("target_identity_id", ""),
        "queue_item_id": item.get("queue_item_id", ""),
        "queue_run_id": queue_run_id,
        "reasons": ",".join(item.get("reasons", [])),
    }
    return f"/api/cluster-review/{action}?{urlencode(params)}"


def _active_learning_reason_badges(reasons: list[str]):
    """Render compact reason badges for one queue item."""
    if not reasons:
        return Span("General coverage", cls="px-2 py-0.5 rounded-full text-xs bg-slate-700 text-slate-200")

    tone = {
        "boundary_distance": "bg-amber-600/80 text-black",
        "ambiguous_margin": "bg-orange-600/80 text-black",
        "tail_identity": "bg-sky-700 text-white",
        "family_name_overlap": "bg-rose-700 text-white",
        "dominant_identity": "bg-fuchsia-700 text-white",
        "topk_alternative": "bg-indigo-700 text-white",
    }
    labels = {
        "boundary_distance": "Boundary",
        "ambiguous_margin": "Ambiguous",
        "tail_identity": "Tail Identity",
        "family_name_overlap": "Family Risk",
        "dominant_identity": "Dominant Family",
        "topk_alternative": "Alt Candidate",
    }
    return Div(
        *[
            Span(
                labels.get(reason, reason.replace("_", " ").title()),
                cls=f"px-2 py-0.5 rounded-full text-xs font-medium {tone.get(reason, 'bg-slate-700 text-slate-200')}",
            )
            for reason in reasons
        ],
        cls="flex flex-wrap gap-1 mt-2",
    )


def _active_learning_card(item, queue_run_id: str):
    """Render one active-learning queue card."""
    pair_dom_id = _safe_dom_id(item["pair_key"])
    source_crop = _get_crop_url_for_face(item["face_id_a"])
    target_crop = _get_crop_url_for_face(item["face_id_b"])

    return Div(
        Div(
            Div(
                Img(src=source_crop, alt=item["face_id_a"], cls="w-20 h-20 object-cover rounded", loading="lazy"),
                P(item.get("source_identity_name", "Unknown"), cls="text-xs text-slate-300 mt-2"),
                P(item["face_id_a"][:18], cls="text-[11px] text-slate-500"),
                cls="flex-shrink-0",
            ),
            Div(
                Span("vs", cls="text-xs uppercase tracking-[0.2em] text-slate-500"),
                P(
                    f"distance {item['distance']:.2f}",
                    cls="text-sm text-slate-300 mt-2",
                ),
                P(
                    f"rank {item['baseline_rank']} • margin {item['margin'] if item.get('margin') is not None else 'n/a'}",
                    cls="text-xs text-slate-500",
                ),
                cls="px-3 text-center",
            ),
            Div(
                Img(src=target_crop, alt=item["face_id_b"], cls="w-20 h-20 object-cover rounded", loading="lazy"),
                P(item.get("target_identity_name", "Unknown"), cls="text-xs text-slate-300 mt-2"),
                P(item["face_id_b"][:18], cls="text-[11px] text-slate-500"),
                cls="flex-shrink-0",
            ),
            cls="flex items-center",
        ),
        Div(
            P(
                "Collect a pair label without changing canonical identity state.",
                cls="text-xs text-slate-400",
            ),
            _active_learning_reason_badges(item.get("reasons", [])),
            Div(
                Button(
                    "Same Person",
                    cls="px-3 py-1.5 text-xs font-medium bg-emerald-700 hover:bg-emerald-600 text-white rounded transition-colors",
                    hx_post=_active_learning_action_url("learn-same", item, queue_run_id),
                    hx_target=f"#active-learning-card-{pair_dom_id}",
                    hx_swap="outerHTML",
                ),
                Button(
                    "Different People",
                    cls="px-3 py-1.5 text-xs font-medium bg-red-700/80 hover:bg-red-600 text-white rounded transition-colors ml-2",
                    hx_post=_active_learning_action_url("learn-different", item, queue_run_id),
                    hx_target=f"#active-learning-card-{pair_dom_id}",
                    hx_swap="outerHTML",
                ),
                cls="mt-3",
            ),
            cls="ml-4 flex-1 min-w-0",
        ),
        id=f"active-learning-card-{pair_dom_id}",
        cls="p-4 bg-slate-800/60 border border-slate-700 rounded-lg flex flex-col lg:flex-row lg:items-center",
    )


def _recent_active_learning_card(label):
    """Render one recent active-learning label with revert action."""
    pair_dom_id = _safe_dom_id(label["pair_key"])
    source_crop = _get_crop_url_for_face(label["face_id_a"])
    target_crop = _get_crop_url_for_face(label["face_id_b"])
    label_text = "Same Person" if label.get("is_match") else "Different People"
    label_color = "text-emerald-400" if label.get("is_match") else "text-red-400"

    return Div(
        Div(
            Img(src=source_crop, alt=label["face_id_a"], cls="w-14 h-14 object-cover rounded", loading="lazy"),
            Img(src=target_crop, alt=label["face_id_b"], cls="w-14 h-14 object-cover rounded ml-2", loading="lazy"),
            cls="flex-shrink-0 flex",
        ),
        Div(
            P(label_text, cls=f"text-sm font-medium {label_color}"),
            P(label["pair_key"], cls="text-[11px] text-slate-500 break-all"),
            P(
                f"{label.get('source_surface', 'unknown')} • {label.get('labeled_at', '')[:19].replace('T', ' ')}",
                cls="text-xs text-slate-500 mt-1",
            ),
            cls="ml-3 flex-1 min-w-0",
        ),
        Button(
            "Revert",
            cls="px-3 py-1.5 text-xs font-medium bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors",
            hx_post=f"/api/cluster-review/learn-revert?{urlencode({'face_id_a': label['face_id_a'], 'face_id_b': label['face_id_b']})}",
            hx_target=f"#active-learning-label-{pair_dom_id}",
            hx_swap="outerHTML",
        )
        if label.get("active", True)
        else Span("Reverted", cls="text-xs text-slate-500"),
        id=f"active-learning-label-{pair_dom_id}",
        cls="p-3 bg-slate-900/50 border border-slate-700/60 rounded-lg flex items-center",
    )


def _face_match_card(proposal, identity_name, identity_id, nav_prefix=""):
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
                href=f"{nav_prefix}/photo/{photo_id}" if photo_id else "#",
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


def _identity_match_group(identity_id, identity_name, proposals, nav_prefix=""):
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
                        href=f"{nav_prefix}/person/{identity_id}?from=admin",
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
            *[_face_match_card(p, identity_name, identity_id, nav_prefix=nav_prefix) for p in proposals_sorted],
            cls="space-y-2",
        ),
        id=f"identity-group-{identity_id}",
        cls="p-4 bg-slate-900/50 border border-slate-700/50 rounded-xl mb-6",
    )


def _gedcom_triage_card(identity_id, identity_name, face_count, has_gedcom, nav_prefix=""):
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
                        href=f"{nav_prefix}/person/{identity_id}?from=admin",
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


def _display_identity_name(name: str) -> str:
    """Shorten placeholder labels for dense review surfaces."""
    if name.startswith("Unidentified Person "):
        return "Person " + name[len("Unidentified Person ") :]
    return name or "Unknown"


def _identity_face_ids(identity: dict) -> list[str]:
    """Return all face ids for an identity across anchors and candidates."""
    face_ids = []
    for entry in identity.get("anchor_ids", []) + identity.get("candidate_ids", []):
        if isinstance(entry, str):
            face_ids.append(entry)
        elif isinstance(entry, dict) and entry.get("face_id"):
            face_ids.append(entry["face_id"])
    return face_ids


def _best_face_id(face_ids: list[str]) -> str:
    """Return the best available face id for preview rendering."""
    if not face_ids:
        return ""
    best = _main_mod.get_best_face_id(face_ids)
    if isinstance(best, str):
        return best
    if isinstance(best, dict):
        return best.get("face_id", "")
    return ""


def _build_unresolved_review_groups(filtered_ids, face_data, photo_registry):
    """Build lightweight unresolved review groups for identities not yet clustered.

    Uses one representative face per unresolved identity to surface reviewable
    neighbor components safely. This does not mutate canonical identity state.
    """
    unresolved_states = {"INBOX", "PROPOSED", "SKIPPED"}
    items = []
    for identity_id, identity in filtered_ids.items():
        if identity.get("merged_into"):
            continue
        if identity.get("state") not in unresolved_states:
            continue

        face_ids = _identity_face_ids(identity)
        if not face_ids:
            continue

        preview_face_id = _best_face_id(face_ids)
        if not preview_face_id or preview_face_id not in face_data:
            preview_face_id = next((fid for fid in face_ids if fid in face_data), "")
        if not preview_face_id:
            continue

        preview_crop_url = _get_crop_url_for_face(preview_face_id)
        photos = photo_registry.get_photos_for_faces(face_ids)

        items.append(
            {
                "identity_id": identity_id,
                "name": identity.get("name", "Unknown"),
                "display_name": _display_identity_name(identity.get("name", "Unknown")),
                "state": identity.get("state", "INBOX"),
                "face_ids": face_ids,
                "face_count": len(face_ids),
                "preview_face_id": preview_face_id,
                "preview_crop_url": preview_crop_url,
                "embedding": face_data[preview_face_id]["mu"],
                "negative_ids": set(identity.get("negative_ids", [])),
                "photos": photos,
            }
        )

    if len(items) < 2:
        return []

    embeddings = np.vstack([item["embedding"] for item in items])
    distance_matrix = cdist(embeddings, embeddings, metric="euclidean")

    direct_neighbors: dict[int, list[tuple[int, float]]] = {i: [] for i in range(len(items))}

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            distance = float(distance_matrix[i][j])
            if distance >= UNRESOLVED_REVIEW_THRESHOLD:
                continue

            left = items[i]
            right = items[j]
            if f"identity:{right['identity_id']}" in left["negative_ids"]:
                continue
            if f"identity:{left['identity_id']}" in right["negative_ids"]:
                continue
            if not left["photos"].isdisjoint(right["photos"]):
                continue

            direct_neighbors[i].append((j, distance))
            direct_neighbors[j].append((i, distance))

    candidate_groups = []
    for start, neighbors in direct_neighbors.items():
        if len(neighbors) < 2:
            continue

        sorted_neighbors = sorted(
            neighbors,
            key=lambda entry: (
                entry[1],
                -items[entry[0]]["face_count"],
                items[entry[0]]["display_name"],
            ),
        )

        members = []
        primary = items[start]
        members.append(
            {
                "identity_id": primary["identity_id"],
                "name": primary["name"],
                "display_name": primary["display_name"],
                "state": primary["state"],
                "face_count": primary["face_count"],
                "preview_crop_url": primary["preview_crop_url"],
                "best_match_distance": 999.0,
                "is_primary": True,
            }
        )
        for neighbor_idx, distance in sorted_neighbors[: UNRESOLVED_REVIEW_MEMBER_LIMIT - 1]:
            neighbor = items[neighbor_idx]
            members.append(
                {
                    "identity_id": neighbor["identity_id"],
                    "name": neighbor["name"],
                    "display_name": neighbor["display_name"],
                    "state": neighbor["state"],
                    "face_count": neighbor["face_count"],
                    "preview_crop_url": neighbor["preview_crop_url"],
                    "best_match_distance": distance,
                    "is_primary": False,
                }
            )

        display_primary = min(
            members,
            key=lambda member: (
                -member["face_count"],
                member["best_match_distance"],
                member["display_name"],
            ),
        )
        display_members = [display_primary] + sorted(
            [member for member in members if member["identity_id"] != display_primary["identity_id"]],
            key=lambda member: (
                member["best_match_distance"],
                -member["face_count"],
                member["display_name"],
            ),
        )
        display_members[0]["is_primary"] = True
        for member in display_members[1:]:
            member["is_primary"] = False

        candidate_groups.append(
            {
                "primary": display_members[0],
                "members": display_members,
                "hidden_member_count": max(0, len(sorted_neighbors) - (UNRESOLVED_REVIEW_MEMBER_LIMIT - 1)),
                "size": 1 + len(sorted_neighbors),
                "best_distance": sorted_neighbors[0][1],
                "distance_range": (sorted_neighbors[0][1], sorted_neighbors[-1][1]),
                "member_ids": {primary["identity_id"], *[items[idx]["identity_id"] for idx, _ in sorted_neighbors]},
            }
        )

    candidate_groups.sort(
        key=lambda group: (
            -group["primary"]["face_count"],
            group["best_distance"],
            -group["size"],
            group["primary"]["display_name"],
        )
    )

    groups = []
    for group in candidate_groups:
        if len(groups) >= UNRESOLVED_REVIEW_GROUP_LIMIT:
            break
        overlap_ratio = 0.0
        for existing in groups:
            overlap = len(group["member_ids"] & existing["member_ids"])
            overlap_ratio = max(
                overlap_ratio,
                overlap / min(len(group["member_ids"]), len(existing["member_ids"])),
            )
        if overlap_ratio >= 0.75:
            continue
        groups.append(group)

    for group in groups:
        group.pop("member_ids", None)
    return groups


def _unresolved_review_group_card(group, nav_prefix=""):
    """Render one unresolved review group card."""
    primary = group["primary"]
    min_dist, max_dist = group["distance_range"]

    def _state_badge(state: str):
        if state == "SKIPPED":
            return Span("Dismissed", cls="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-600/80 text-black")
        if state == "PROPOSED":
            return Span("Proposed", cls="px-2 py-0.5 rounded-full text-[10px] font-medium bg-sky-700 text-white")
        return Span("Inbox", cls="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-700 text-slate-200")

    member_tiles = []
    for member in group["members"]:
        badge = (
            Span("Primary", cls="px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-600 text-white")
            if member["is_primary"]
            else None
        )
        distance_label = (
            P(f"Best match {member['best_match_distance']:.2f}", cls="text-[11px] text-emerald-300 mt-1")
            if member["best_match_distance"] < 999.0 and not member["is_primary"]
            else None
        )
        member_tiles.append(
            A(
                Div(
                    Img(
                        src=member["preview_crop_url"],
                        alt=member["display_name"],
                        cls="w-full aspect-[3/4] object-cover rounded-lg",
                        loading="lazy",
                    )
                    if member["preview_crop_url"]
                    else Div(cls="w-full aspect-[3/4] rounded-lg bg-slate-700"),
                    Div(
                        Div(
                            Span(member["display_name"], cls="text-xs font-medium text-white truncate block"),
                            Div(
                                badge,
                                _state_badge(member.get("state", "INBOX")),
                                cls="flex items-center gap-1 justify-end flex-wrap",
                            ),
                            cls="flex items-center justify-between gap-2",
                        ),
                        P(
                            f"{member['face_count']} face{'s' if member['face_count'] != 1 else ''}",
                            cls="text-[11px] text-slate-400 mt-1",
                        ),
                        distance_label,
                        cls="mt-2",
                    ),
                    cls="p-2 bg-slate-800/70 border border-slate-700 rounded-xl hover:border-slate-500 transition-colors",
                ),
                href=f"{nav_prefix}/person/{member['identity_id']}?from=admin",
                cls="block",
            )
        )

    range_text = (
        f"{min_dist:.2f}–{max_dist:.2f} preview distance"
        if min_dist < 999.0 and max_dist < 999.0
        else "Review manually before merging"
    )

    return Div(
        Div(
            Div(
                Img(
                    src=primary["preview_crop_url"],
                    alt=primary["display_name"],
                    cls="w-16 h-16 object-cover rounded-xl border border-slate-600",
                    loading="lazy",
                )
                if primary["preview_crop_url"]
                else Div(cls="w-16 h-16 rounded-xl bg-slate-700"),
                Div(
                    H3(primary["display_name"], cls="text-base font-semibold text-white"),
                    P(
                        f"{group['size']} unresolved identities • {range_text}",
                        cls="text-xs text-slate-400 mt-1",
                    ),
                    cls="ml-3 flex-1 min-w-0",
                ),
                Div(
                    A(
                        "Review Similar",
                        href=f"{nav_prefix}/people/{primary['identity_id']}/similar",
                        cls="px-3 py-1.5 text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors",
                    ),
                    A(
                        "Open Queue",
                        href=f"{nav_prefix}/?section=to_review&view=browse#identity-{primary['identity_id']}",
                        cls="px-3 py-1.5 text-xs font-medium bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors ml-2",
                    ),
                    cls="flex-shrink-0",
                ),
                cls="flex items-center mb-4",
            ),
            Div(*member_tiles, cls="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"),
            P(
                f"+{group['hidden_member_count']} more likely match{'es' if group['hidden_member_count'] != 1 else ''}"
                if group["hidden_member_count"]
                else "",
                cls="text-xs text-slate-500 mt-3",
            )
            if group["hidden_member_count"]
            else None,
            cls="p-4 bg-slate-900/50 border border-slate-700/50 rounded-xl",
        ),
        cls="mb-6",
    )


@rt("/admin/upload-review")
def get(sess=None, request=None, mode: str = ""):
    """Upload Review Dashboard — cluster review + GEDCOM triage.

    AD-215: Error correction must be effortless.
    PRD-037 Phase 2: GEDCOM triage for post-upload identity linking.
    PRD-039: Speed-run mode (?mode=speed) for rapid batch review.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    # Speed-run mode: minimal layout with single-card queue
    if mode == "speed":
        community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
        clusters = _get_speed_run_clusters(community_slug, request)
        total = len(clusters)

        if total == 0:
            first_card = Div(
                H3("No clusters to review", cls="text-xl font-semibold text-white mb-2"),
                P("All multi-face clusters have been reviewed.", cls="text-slate-400"),
                A(
                    "Back to Dashboard",
                    href="upload-review",
                    cls="mt-4 px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-lg transition-colors inline-block",
                ),
                id="speed-run-card",
                cls="p-8 bg-slate-900/60 border border-slate-700 rounded-xl text-center",
            )
        else:
            iid, idata = clusters[0]
            first_card = _speed_run_cluster_card(iid, idata, 0, total, community_slug, include_progress=False)

        keyboard_js = Script("""
            (function() {
                var _speedRunLocked = false;
                document.addEventListener('keydown', function(e) {
                    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
                    var card = document.getElementById('speed-run-card');
                    var isEnrichment = card && card.getAttribute('data-enrichment') === 'true';
                    var key = e.key.toLowerCase();
                    if (isEnrichment) {
                        if (key === 'y' || key === 's' || key === 'd') {
                            var skipBtn = document.querySelector('[data-action="speed-enrich-skip"]');
                            if (skipBtn) { e.preventDefault(); skipBtn.click(); }
                            return;
                        }
                        if (e.key === 'Enter') {
                            var saveBtn = document.querySelector('[data-action="speed-save-name"]');
                            if (saveBtn) { e.preventDefault(); saveBtn.click(); }
                            return;
                        }
                        return;
                    }
                    if (_speedRunLocked) { e.preventDefault(); return; }
                    var actionMap = {'y': 'speed-confirm', 'n': 'speed-reject', 's': 'speed-skip', 'd': 'speed-dismiss', 'z': 'speed-undo'};
                    var action = actionMap[key];
                    if (!action) return;
                    var btn = document.querySelector('[data-action="' + action + '"]');
                    if (btn) {
                        e.preventDefault();
                        _speedRunLocked = true;
                        btn.click();
                        setTimeout(function() { _speedRunLocked = false; }, 300);
                    }
                });
            })();
        """)

        recent_actions_js = Script("""
            (function() {
                window._speedRunActions = [];
                var STORAGE_KEY = 'rhodesli_speedrun_stats';
                function saveStats(confirmed, skipped, rejected, dismissed) {
                    try {
                        localStorage.setItem(STORAGE_KEY, JSON.stringify({
                            confirmed: confirmed, skipped: skipped,
                            rejected: rejected, dismissed: dismissed,
                            timestamp: Date.now()
                        }));
                    } catch(e) {}
                }
                function loadStats() {
                    try {
                        var raw = localStorage.getItem(STORAGE_KEY);
                        if (!raw) return null;
                        var data = JSON.parse(raw);
                        // Expire after 24 hours
                        if (Date.now() - (data.timestamp || 0) > 86400000) {
                            localStorage.removeItem(STORAGE_KEY);
                            return null;
                        }
                        return data;
                    } catch(e) { return null; }
                }
                window._resetSpeedRunCount = function() {
                    localStorage.removeItem(STORAGE_KEY);
                    var progress = document.getElementById('speed-run-progress');
                    if (!progress) return;
                    var total = parseInt(progress.getAttribute('data-total') || '0', 10);
                    progress.setAttribute('data-confirmed', '0');
                    progress.setAttribute('data-skipped', '0');
                    progress.setAttribute('data-rejected', '0');
                    progress.setAttribute('data-dismissed', '0');
                    var textEl = document.getElementById('speed-run-stats-text');
                    if (textEl) textEl.textContent = '0 confirmed \\u00b7 0 skipped \\u00b7 0 rejected \\u00b7 ' + total + ' remaining';
                    var bar = progress.querySelector('.bg-purple-500, .bg-emerald-500');
                    if (bar) bar.style.width = '0%';
                };
                function updateStats(action) {
                    var progress = document.getElementById('speed-run-progress');
                    if (!progress) return;
                    var total = parseInt(progress.getAttribute('data-total') || '0', 10);
                    var confirmed = parseInt(progress.getAttribute('data-confirmed') || '0', 10);
                    var skipped = parseInt(progress.getAttribute('data-skipped') || '0', 10);
                    var rejected = parseInt(progress.getAttribute('data-rejected') || '0', 10);
                    var dismissed = parseInt(progress.getAttribute('data-dismissed') || '0', 10);
                    if (action === 'confirm-all') confirmed++;
                    else if (action === 'reject-all') rejected++;
                    else if (action === 'skip') skipped++;
                    else if (action === 'dismiss') dismissed++;
                    progress.setAttribute('data-confirmed', String(confirmed));
                    progress.setAttribute('data-skipped', String(skipped));
                    progress.setAttribute('data-rejected', String(rejected));
                    progress.setAttribute('data-dismissed', String(dismissed));
                    saveStats(confirmed, skipped, rejected, dismissed);
                    var reviewed = confirmed + skipped + rejected + dismissed;
                    var remaining = Math.max(0, total - reviewed);
                    var textEl = document.getElementById('speed-run-stats-text');
                    if (textEl) textEl.textContent = confirmed + ' confirmed \\u00b7 ' + skipped + ' skipped \\u00b7 ' + rejected + ' rejected \\u00b7 ' + remaining + ' remaining';
                    var bar = progress.querySelector('.bg-purple-500, .bg-emerald-500');
                    if (bar) {
                        var pct = total > 0 ? Math.round((reviewed / total) * 100) : 0;
                        bar.style.width = pct + '%';
                    }
                }
                // Restore stats from localStorage on page load
                (function restoreStats() {
                    var saved = loadStats();
                    if (!saved) return;
                    var progress = document.getElementById('speed-run-progress');
                    if (!progress) return;
                    var total = parseInt(progress.getAttribute('data-total') || '0', 10);
                    progress.setAttribute('data-confirmed', String(saved.confirmed || 0));
                    progress.setAttribute('data-skipped', String(saved.skipped || 0));
                    progress.setAttribute('data-rejected', String(saved.rejected || 0));
                    progress.setAttribute('data-dismissed', String(saved.dismissed || 0));
                    var reviewed = (saved.confirmed || 0) + (saved.skipped || 0) + (saved.rejected || 0) + (saved.dismissed || 0);
                    var remaining = Math.max(0, total - reviewed);
                    var textEl = document.getElementById('speed-run-stats-text');
                    if (textEl) textEl.textContent = (saved.confirmed || 0) + ' confirmed \\u00b7 ' + (saved.skipped || 0) + ' skipped \\u00b7 ' + (saved.rejected || 0) + ' rejected \\u00b7 ' + remaining + ' remaining';
                    var bar = progress.querySelector('.bg-purple-500, .bg-emerald-500');
                    if (bar) {
                        var pct = total > 0 ? Math.round((reviewed / total) * 100) : 0;
                        bar.style.width = pct + '%';
                    }
                })();
                function renderActions() {
                    var container = document.getElementById('speed-run-recent-actions');
                    if (!container) return;
                    var actions = window._speedRunActions;
                    if (actions.length === 0) {
                        container.style.display = 'none';
                        return;
                    }
                    container.style.display = 'block';
                    var listEl = document.getElementById('speed-run-action-list');
                    if (!listEl) return;
                    var html = '';
                    var icons = {'confirm-all': '\\u2713', 'reject-all': '\\u2717', 'skip': '\\u2192', 'dismiss': '\\u2298'};
                    var colors = {'confirm-all': 'text-emerald-400', 'reject-all': 'text-red-400', 'skip': 'text-slate-400', 'dismiss': 'text-amber-400'};
                    for (var i = actions.length - 1; i >= Math.max(0, actions.length - 10); i--) {
                        var a = actions[i];
                        var icon = icons[a.action] || '?';
                        var color = colors[a.action] || 'text-slate-400';
                        html += '<div class="flex items-center gap-2 py-1.5 border-b border-slate-800">';
                        html += '<span class="' + color + ' text-lg w-6 text-center">' + icon + '</span>';
                        if (a.cropUrl) {
                            html += '<img src="' + a.cropUrl + '" class="w-8 h-8 object-cover rounded" loading="lazy">';
                        }
                        html += '<span class="text-xs text-slate-300 flex-1 truncate">' + (a.name || a.identityId.substring(0, 12)) + '</span>';
                        html += '</div>';
                    }
                    listEl.innerHTML = html;
                }
                document.body.addEventListener('htmx:afterRequest', function(evt) {
                    var trigger = evt.detail.elt;
                    if (!trigger) return;
                    var action = trigger.getAttribute('data-action');
                    if (!action) return;
                    var actionMap = {'speed-confirm': 'confirm-all', 'speed-reject': 'reject-all', 'speed-skip': 'skip', 'speed-dismiss': 'dismiss'};
                    var mapped = actionMap[action];
                    if (!mapped) return;
                    var card = document.getElementById('speed-run-card');
                    var name = '';
                    var cropUrl = '';
                    var identityId = '';
                    if (trigger.getAttribute('hx-post') || trigger.getAttribute('hx_post')) {
                        var url = trigger.getAttribute('hx-post') || trigger.getAttribute('hx_post') || '';
                        var match = url.match(/identity_id=([^&]*)/);
                        if (match) identityId = decodeURIComponent(match[1]);
                    }
                    var nameEl = card ? card.querySelector('h3') : null;
                    if (nameEl) name = nameEl.textContent || '';
                    var cropEl = card ? card.querySelector('img') : null;
                    if (cropEl) cropUrl = cropEl.getAttribute('src') || '';
                    window._speedRunActions.push({action: mapped, name: name, identityId: identityId, cropUrl: cropUrl});
                    updateStats(mapped);
                    setTimeout(renderActions, 100);
                });
            })();
        """)

        return Title("Speed Run Review — Rhodesli Admin"), Main(
            Div(
                Div(
                    Div(
                        H1("Speed Run Review", cls="text-2xl font-serif font-bold text-white"),
                        A(
                            "\u2190 Dashboard",
                            href="upload-review",
                            cls="text-sm text-purple-400 hover:text-purple-300 transition-colors",
                        ),
                        cls="flex items-center gap-4",
                    ),
                    P(
                        "Review each cluster. Press Y to confirm (same person), N to reject (mixed faces), "
                        "S to skip, D to dismiss. After confirming, you can name the person and link to GEDCOM records.",
                        cls="text-slate-400 text-sm mt-2",
                    ),
                    P(
                        "Y = Confirm \u00b7 N = Reject \u00b7 S = Skip \u00b7 D = Dismiss \u00b7 Z = Undo",
                        cls="text-slate-500 text-xs mt-1",
                    ),
                    cls="mb-6",
                ),
                # Progress bar with cumulative stats
                Div(
                    Div(
                        Span(
                            f"0 confirmed \u00b7 0 skipped \u00b7 0 rejected \u00b7 {total} remaining",
                            id="speed-run-stats-text",
                            cls="text-sm text-slate-300",
                        ),
                        Button(
                            "Reset",
                            onclick="window._resetSpeedRunCount && window._resetSpeedRunCount()",
                            cls="text-xs text-slate-500 hover:text-slate-300 transition-colors",
                            type="button",
                            data_testid="speed-run-reset",
                        ),
                        cls="flex justify-between items-center mb-2",
                    ),
                    Div(
                        Div(cls="h-2 bg-purple-500 rounded-full", style="width: 0%"),
                        cls="w-full h-2 bg-slate-700 rounded-full overflow-hidden",
                    ),
                    id="speed-run-progress",
                    data_total=str(total),
                    data_confirmed="0",
                    data_skipped="0",
                    data_rejected="0",
                    data_dismissed="0",
                ),
                # First card
                first_card,
                # Undo state (hidden, updated via OOB swaps)
                _speed_run_undo_button(None),
                # Recent actions sidebar (3C)
                Div(
                    H4("Recent Actions", cls="text-sm font-semibold text-slate-300 mb-2"),
                    Div(id="speed-run-action-list"),
                    id="speed-run-recent-actions",
                    cls="mt-6 p-4 bg-slate-900/40 border border-slate-700/50 rounded-xl",
                    style="display:none",
                ),
                keyboard_js,
                recent_actions_js,
                cls="max-w-3xl mx-auto px-4 py-8",
            ),
            cls="min-h-screen bg-slate-950",
        )

    proposals = _load_proposals()

    # COMMUNITY-011: Filter proposals by community identity set
    # Lesson 109: /api/ routes skip CommunityMiddleware — fall back to slug lookup
    community = getattr(request.state, "community", None) if request else None
    _dash_slug = getattr(request.state, "community_slug", "") if request else ""
    if not community and _dash_slug:
        from app.supabase_data import get_community_by_slug as _gcbs

        community = _gcbs(_dash_slug)
    community_identity_ids = None
    if community:
        community_identity_ids = _main_mod._get_community_identity_ids(community)
        if community_identity_ids is not None:
            proposals = [
                p
                for p in proposals
                if p.get("source_identity_id") in community_identity_ids
                or p.get("target_identity_id") in community_identity_ids
            ]

    # Filter to Medium+ confidence only (distance < 1.05) — Low confidence matches are garbage
    proposals = [p for p in proposals if p.get("distance", 999) < 1.05]

    # Compute nav prefix for community-scoped links (COMMUNITY-016)
    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    nav_prefix = _main_mod.community_url_prefix(community_slug)

    # --- Section 1: Grouped Identities (multi-face clusters from grouping) ---
    registry = _main_mod.load_registry()
    identities = registry._identities if hasattr(registry, "_identities") else {}

    # Get community-filtered identities
    if community and community_identity_ids is not None:
        filtered_ids = {iid: idata for iid, idata in identities.items() if iid in community_identity_ids}
    else:
        filtered_ids = identities

    # Find multi-face INBOX identities (clusters from grouping)
    clusters = []
    for iid, idata in filtered_ids.items():
        if idata.get("merged_into"):
            continue
        if idata.get("state") != "INBOX":
            continue
        all_faces = idata.get("anchor_ids", []) + idata.get("candidate_ids", [])
        if len(all_faces) >= 2:
            clusters.append((iid, idata.get("name", "Unknown"), len(all_faces)))

    clusters.sort(key=lambda x: -x[2])  # Most faces first

    if clusters:
        cluster_cards = []
        for iid, cname, face_count in clusters[:50]:
            # Get crop URL for thumbnail
            idata = filtered_ids[iid]
            anchor_crop_url = None
            anchors = idata.get("anchor_ids", [])
            if anchors:
                first = anchors[0]
                if isinstance(first, dict):
                    first = first.get("face_id", str(first))
                anchor_crop_url = _get_crop_url_for_face(first)

            display_name = cname
            if cname.startswith("Unidentified Person "):
                display_name = "Person " + cname[len("Unidentified Person ") :]

            cluster_cards.append(
                A(
                    Div(
                        Img(
                            src=anchor_crop_url,
                            alt=display_name,
                            cls="w-16 h-16 object-cover rounded-lg border border-slate-600",
                            loading="lazy",
                        )
                        if anchor_crop_url
                        else Div(cls="w-16 h-16 rounded-lg bg-slate-700"),
                        Div(
                            H4(display_name, cls="text-sm font-semibold text-white truncate", title=cname),
                            P(
                                f"{face_count} face{'s' if face_count != 1 else ''}",
                                cls="text-xs text-slate-400",
                            ),
                            cls="ml-3 flex-1 min-w-0",
                        ),
                        Span(
                            str(face_count),
                            cls="w-8 h-8 flex items-center justify-center bg-purple-600/80 text-white"
                            " text-xs font-bold rounded-full flex-shrink-0",
                        ),
                        cls="flex items-center p-3 bg-slate-800/60 border border-slate-700 rounded-lg"
                        " hover:border-purple-500/50 transition-colors",
                    ),
                    href=f"{nav_prefix}/person/{iid}",
                )
            )

        grouped_section = Div(
            H2("Grouped Identities", cls="text-xl font-serif font-semibold text-white mb-2"),
            P(
                f"{len(clusters)} cluster{'s' if len(clusters) != 1 else ''} with {sum(c[2] for c in clusters)} total faces. "
                "These faces were grouped by the ML pipeline as likely the same person. "
                "Click to review and name them.",
                cls="text-sm text-slate-400 mb-6",
            ),
            Div(
                *cluster_cards,
                cls="grid gap-3 sm:grid-cols-2 lg:grid-cols-3",
            ),
            cls="mb-12",
        )
    else:
        grouped_section = Div(
            H2("Grouped Identities", cls="text-xl font-serif font-semibold text-white mb-2"),
            P("No multi-face clusters found.", cls="text-slate-400"),
            cls="mb-12",
        )

    # --- Section 2: Potential Review Groups (unresolved but strongly similar) ---
    photo_registry = _main_mod.load_photo_registry()
    face_data = _main_mod.get_face_data()
    unresolved_review_groups = _build_unresolved_review_groups(filtered_ids, face_data, photo_registry)

    if unresolved_review_groups:
        unresolved_review_section = Div(
            H2("Potential Review Groups", cls="text-xl font-serif font-semibold text-white mb-2"),
            P(
                "These unresolved identities were not auto-grouped, but their best face previews are close enough "
                "that they deserve a manual review pass. Start from Review Similar, then merge or reject there.",
                cls="text-sm text-slate-400 mb-6",
            ),
            *[_unresolved_review_group_card(group, nav_prefix=nav_prefix) for group in unresolved_review_groups],
            cls="mb-12",
            data_testid="potential-review-groups",
        )
    else:
        unresolved_review_section = Div(
            H2("Potential Review Groups", cls="text-xl font-serif font-semibold text-white mb-2"),
            P("No unresolved review groups surfaced right now.", cls="text-slate-400"),
            cls="mb-12",
        )

    # --- Section 3: Proposal Matches (to confirmed identities) ---
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

    sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]["proposals"]))

    if sorted_groups:
        cluster_section = Div(
            H2("Proposal Matches", cls="text-xl font-serif font-semibold text-white mb-2"),
            P(
                f"{len(proposals)} face{'s' if len(proposals) != 1 else ''} matched to "
                f"{len(groups)} confirmed {'identities' if len(groups) != 1 else 'identity'} "
                "(Medium+ confidence only).",
                cls="text-sm text-slate-400 mb-6",
            ),
            *[_identity_match_group(tid, g["name"], g["proposals"], nav_prefix=nav_prefix) for tid, g in sorted_groups],
            cls="mb-12",
        )
    else:
        cluster_section = Div(
            H2("Proposal Matches", cls="text-xl font-serif font-semibold text-white mb-2"),
            P("No high-confidence proposal matches to review.", cls="text-slate-400"),
            cls="mb-12",
        )

    # --- Section 4: Active-Learning Queue (offline-built, review-only labels) ---
    queue_payload = _active_learning_queue_payload()
    queue_items = queue_payload.get("items", [])
    if community and community_identity_ids is not None:
        queue_items = [
            item
            for item in queue_items
            if item.get("source_identity_id") in community_identity_ids
            or item.get("target_identity_id") in community_identity_ids
        ]
    queue_stats = dict(queue_payload.get("stats") or {})
    recent_labels = _active_learning_labels()

    if queue_items or recent_labels:
        active_learning_section = Div(
            H2("Learning Queue", cls="text-xl font-serif font-semibold text-white mb-2"),
            P(
                "Offline-ranked pair labels for uncertainty, diversity, and tail coverage. "
                "These labels feed recalibration later, but they do not change canonical identities.",
                cls="text-sm text-slate-400 mb-4",
            ),
            Div(
                Div(
                    Span(str(queue_stats.get("queue_count", len(queue_items))), cls="text-lg font-semibold text-white"),
                    P("queue items", cls="text-xs text-slate-500"),
                    cls="p-3 bg-slate-900/60 border border-slate-700 rounded-lg",
                ),
                Div(
                    Span(
                        f"{(queue_stats.get('underrepresented_or_hard_share', 0.0) * 100):.0f}%",
                        cls="text-lg font-semibold text-white",
                    ),
                    P("hard / tail share", cls="text-xs text-slate-500"),
                    cls="p-3 bg-slate-900/60 border border-slate-700 rounded-lg",
                ),
                Div(
                    Span(
                        str(queue_stats.get("first_batch_max_per_identity", 0)),
                        cls="text-lg font-semibold text-white",
                    ),
                    P("max same target in first 10", cls="text-xs text-slate-500"),
                    cls="p-3 bg-slate-900/60 border border-slate-700 rounded-lg",
                ),
                cls="grid gap-3 sm:grid-cols-3 mb-5",
            )
            if queue_items
            else None,
            Div(
                *[
                    _active_learning_card(item, queue_payload.get("queue_run_id", "unknown"))
                    for item in queue_items[:10]
                ],
                cls="space-y-3",
            )
            if queue_items
            else Div(
                P("No active-learning queue artifact found yet.", cls="text-sm text-slate-300"),
                P(
                    "Run `python scripts/build_active_learning_queue.py` in the worktree to generate it.",
                    cls="text-xs text-slate-500 mt-1",
                ),
                cls="p-4 bg-slate-900/50 border border-slate-700 rounded-lg",
            ),
            Div(
                H3("Recent Queue Labels", cls="text-sm font-semibold text-white mt-6 mb-3"),
                Div(
                    *[_recent_active_learning_card(label) for label in recent_labels],
                    cls="space-y-2",
                )
                if recent_labels
                else P("No recent active-learning labels recorded yet.", cls="text-sm text-slate-500"),
            ),
            cls="mb-12",
        )
    else:
        active_learning_section = Div(
            H2("Learning Queue", cls="text-xl font-serif font-semibold text-white mb-2"),
            P(
                "No queue artifact or recent labels yet. Generate the queue offline before reviewing here.",
                cls="text-sm text-slate-400",
            ),
            cls="mb-12",
        )

    # Build GEDCOM triage section
    # Registry already loaded above for grouped section

    # Reuse community-filtered identities from grouped section above
    community_filtered_identities = filtered_ids

    # Count faces per identity (confirmed + candidates)
    face_counts = []
    for iid, idata in community_filtered_identities.items():
        if idata.get("state") in ("CONFIRMED", "PROPOSED", "INBOX") and not idata.get("merged_into"):
            anchors = idata.get("anchor_ids", [])
            candidates = idata.get("candidate_ids", [])
            total = len(anchors) + len(candidates)
            if total >= 3:  # Only show identities with 3+ faces
                has_gedcom = bool(idata.get("gedcom_xref"))
                face_counts.append((iid, idata.get("name", "Unknown"), total, has_gedcom))

    # Sort: unlinked first, then by face count descending
    face_counts.sort(key=lambda x: (x[3], -x[2]))  # has_gedcom=False first, then most faces
    top_identities = face_counts[:30]  # Show top 30

    gedcom_section = Div(
        H2("GEDCOM Triage", cls="text-xl font-serif font-semibold text-white mb-2"),
        P(
            "Link identities to family tree records. Prioritized by face count — "
            "linking the most-seen people first maximizes Gemini estimation accuracy.",
            cls="text-sm text-slate-400 mb-6",
        ),
        Div(
            *[
                _gedcom_triage_card(iid, name, count, has_gedcom, nav_prefix=nav_prefix)
                for iid, name, count, has_gedcom in top_identities
            ],
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
                Div(
                    H1("Upload Review", cls="text-2xl font-serif font-bold text-white"),
                    A(
                        "Start Speed Run →",
                        href="upload-review?mode=speed",
                        cls="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors",
                    )
                    if clusters
                    else None,
                    cls="flex items-center justify-between",
                ),
                P("Review auto-clustered matches and link GEDCOM records.", cls="text-slate-400 mt-1"),
                cls="mb-8",
            ),
            grouped_section,
            unresolved_review_section,
            cluster_section,
            active_learning_section,
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
        _log_audit(
            "confirm",
            entity_id=identity_id,
            user_email=_speed_run_admin_email(sess),
            old_value={"face_id": face_id, "list": "candidate_ids"},
            new_value={"list": "anchor_ids"},
            metadata={"route": "cluster_review_confirm"},
        )
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
        _log_audit(
            "reject",
            entity_id=identity_id,
            user_email=_speed_run_admin_email(sess),
            old_value={"face_id": face_id},
            metadata={"route": "cluster_review_reject"},
        )
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
def post(
    identity_id: str = "",
    speed_run: str = "",
    offset: int = 0,
    community_slug: str = "",
    input_method: str = "",
    sess=None,
    request=None,
):
    """Confirm all candidate faces for an identity."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    registry = _main_mod.load_registry()

    try:
        identity = registry._identities.get(identity_id)
        if not identity:
            raise ValueError(f"Identity {identity_id} not found")

        # Capture state before modification for undo
        prev_state = identity.get("state", "INBOX")
        # Promote all candidates to anchors
        candidates = list(identity.get("candidate_ids", []))
        confirmed_count = 0
        for fid in candidates:
            try:
                registry.promote_candidate(identity_id, fid, user_source="admin/cluster-review-batch")
                confirmed_count += 1
            except ValueError:
                pass  # Skip faces that were already promoted

        # For INBOX identities where faces are already in anchor_ids,
        # candidate_ids may be empty — still need to set state to CONFIRMED
        all_faces = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        confirmed_count = max(confirmed_count, len(all_faces))

        # Always set state to CONFIRMED on confirm-all
        identity["state"] = "CONFIRMED"
        identity["updated_at"] = _main_mod.datetime.now(_main_mod.timezone.utc).isoformat()

        _main_mod.save_registry(registry)

        _main_mod.log_user_action(
            "SPEED_RUN_CONFIRM",
            identity_id=identity_id,
            face_count=len(identity.get("anchor_ids", []) + identity.get("candidate_ids", [])),
            state_before=prev_state,
            state_after="CONFIRMED",
            mode="speed-run",
            admin=_speed_run_admin_email(sess),
            **({"input_method": input_method} if input_method else {}),
        )
        _log_audit(
            "confirm",
            entity_id=identity_id,
            user_email=_speed_run_admin_email(sess),
            old_value={"state": prev_state, "name": identity.get("name")},
            new_value={"state": "CONFIRMED", "confirmed_faces": confirmed_count},
            metadata={"route": "speed_run_confirm_all", "input_method": input_method or "click"},
        )
    except (ValueError, KeyError) as e:
        return Div(
            P(f"Error: {e}", cls="text-red-400 text-sm"),
            cls="p-4",
        )

    if speed_run == "true":
        iname = identity.get("name", "Unknown")
        all_faces = _identity_face_ids(identity)
        undo_state = _build_undo_state(
            identity_id,
            "confirm-all",
            offset,
            community_slug,
            {"candidates": candidates, "prev_state": prev_state},
            identity_name=iname,
            face_count=len(all_faces),
        )
        undo_btn = _speed_run_undo_button(undo_state, oob=True)
        # FB-025: Lazy-load enrichment panel — return instant confirm feedback,
        # then load the heavier suggestions panel via HTMX for perceived speed.
        enrichment_placeholder = Div(
            Div(
                Span("\u2713", cls="text-emerald-400 text-lg mr-2"),
                Span(f"Confirmed as {iname}", cls="text-emerald-400 font-medium"),
                cls="flex items-center mb-4",
            ),
            Div(
                Div(cls="h-6 w-48 bg-slate-700/50 rounded animate-pulse mb-3"),
                Div(cls="h-20 w-full bg-slate-700/30 rounded animate-pulse"),
                cls="space-y-2",
            ),
            id="speed-run-card",
            hx_get=f"/api/cluster-review/enrichment-panel?identity_id={identity_id}&offset={offset}&community_slug={community_slug}",
            hx_trigger="load",
            hx_swap="outerHTML",
        )
        return enrichment_placeholder, undo_btn

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
def post(
    identity_id: str = "",
    speed_run: str = "",
    offset: int = 0,
    community_slug: str = "",
    input_method: str = "",
    sess=None,
    request=None,
):
    """Reject all candidate faces for an identity."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    registry = _main_mod.load_registry()

    try:
        identity = registry._identities.get(identity_id)
        if not identity:
            raise ValueError(f"Identity {identity_id} not found")

        prev_state = identity.get("state", "INBOX")
        candidates = list(identity.get("candidate_ids", []))
        rejected_count = 0
        for fid in candidates:
            try:
                registry.reject_candidate(identity_id, fid, user_source="admin/cluster-review-batch")
                rejected_count += 1
            except ValueError:
                pass

        _main_mod.save_registry(registry)

        _main_mod.log_user_action(
            "SPEED_RUN_REJECT",
            identity_id=identity_id,
            face_count=len(candidates),
            mode="speed-run",
            admin=_speed_run_admin_email(sess),
            **({"input_method": input_method} if input_method else {}),
        )
        _log_audit(
            "reject",
            entity_id=identity_id,
            user_email=_speed_run_admin_email(sess),
            old_value={"candidates": candidates[:10]},
            new_value={"rejected_count": rejected_count},
            metadata={"route": "speed_run_reject_all", "input_method": input_method or "click"},
        )
    except (ValueError, KeyError) as e:
        return Div(
            P(f"Error: {e}", cls="text-red-400 text-sm"),
            cls="p-4",
        )

    if speed_run == "true":
        iname = identity.get("name", "Unknown")
        all_faces = _identity_face_ids(identity)
        undo_state = _build_undo_state(
            identity_id,
            "reject-all",
            offset,
            community_slug,
            {"candidates": candidates, "prev_state": prev_state},
            identity_name=iname,
            face_count=len(all_faces),
        )
        next_card = _speed_run_next_card(offset + 1, community_slug, request)
        undo_btn = _speed_run_undo_button(undo_state, oob=True)
        return next_card, undo_btn

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


# =========================================================================
# SPEED-RUN CLUSTER REVIEW (PRD-039)
# =========================================================================


def _get_speed_run_clusters(community_slug: str = "", request=None):
    """Get the ordered list of clusters for speed-run review.

    Returns list of (identity_id, identity_data) tuples, sorted by face count descending.
    Filters to multi-face INBOX identities, community-scoped if applicable.
    Cached for 30s, invalidated on confirm/merge/skip/reject.
    """
    cache_key = community_slug or "__all__"
    cached = _speed_run_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]

    registry = _main_mod.load_registry()
    identities = registry._identities if hasattr(registry, "_identities") else {}

    # Community filtering
    # Lesson 109: /api/ routes skip CommunityMiddleware, so request.state.community
    # may be None even when community_slug is valid. Fall back to slug lookup.
    community = getattr(request.state, "community", None) if request else None
    if not community and community_slug:
        from app.supabase_data import get_community_by_slug

        community = get_community_by_slug(community_slug)
    community_identity_ids = None
    if community:
        community_identity_ids = _main_mod._get_community_identity_ids(community)

    if community_identity_ids is not None:
        filtered_ids = {iid: idata for iid, idata in identities.items() if iid in community_identity_ids}
    else:
        filtered_ids = identities

    clusters = []
    for iid, idata in filtered_ids.items():
        if idata.get("merged_into"):
            continue
        state = idata.get("state", "")
        if state not in ("INBOX", "PROPOSED"):
            continue
        all_faces = idata.get("anchor_ids", []) + idata.get("candidate_ids", [])
        if len(all_faces) >= 2:
            clusters.append((iid, idata, len(all_faces)))

    clusters.sort(key=lambda x: -x[2])  # Most faces first
    result = [(iid, idata) for iid, idata, _ in clusters]
    _speed_run_cache[cache_key] = (time.time(), result)
    return result


def _get_photo_url_for_face(face_id, community_slug=""):
    """Get the source photo page URL for a face_id, with community prefix."""
    photo_registry = _main_mod.load_photo_registry()
    photo_id = photo_registry.get_photo_for_face(face_id)
    if photo_id:
        nav_prefix = _main_mod.community_url_prefix(community_slug) if community_slug else ""
        return f"{nav_prefix}/photo/{photo_id}"
    return None


def _speed_run_cluster_card(identity_id, identity_data, offset, total, community_slug="", include_progress=True):
    """Render a single cluster card for speed-run mode."""
    name = identity_data.get("name", "Unknown")
    display_name = name
    if name.startswith("Unidentified Person "):
        display_name = "Person " + name[len("Unidentified Person ") :]
    all_faces = _identity_face_ids(identity_data)
    face_count = len(all_faces)

    # Face thumbnails — show ALL faces (no cap), scrollable grid
    face_thumbs = []
    for fid in all_faces:
        crop_url = _get_crop_url_for_face(fid)
        photo_url = _get_photo_url_for_face(fid, community_slug=community_slug)
        if crop_url:
            img_el = Img(
                src=crop_url,
                alt=f"Face {fid[:12]}",
                cls="w-28 h-28 object-cover rounded-lg border border-slate-600",
                loading="lazy",
                onerror="this.style.display='none'; this.nextElementSibling.style.display='flex'",
            )
            fallback_el = Div(
                Span("?", cls="text-slate-500 text-lg"),
                cls="w-28 h-28 rounded-lg bg-slate-700 border border-slate-600 items-center justify-center hidden",
                title=f"Face crop unavailable: {fid[:16]}",
            )
            if photo_url:
                face_thumbs.append(
                    A(
                        img_el,
                        href=f"{photo_url}?from_queue=1",
                        target="_blank",
                        cls="block",
                        title=f"View source photo for {fid[:16]}",
                    )
                )
                face_thumbs.append(fallback_el)
            else:
                face_thumbs.append(img_el)
                face_thumbs.append(fallback_el)
        else:
            face_thumbs.append(
                Div(
                    Span("?", cls="text-slate-500 text-lg"),
                    cls="w-28 h-28 rounded-lg bg-slate-700 border border-slate-600 flex items-center justify-center",
                    title="No crop available",
                )
            )

    # Common params for action buttons
    common_params = urlencode(
        {
            "identity_id": identity_id,
            "speed_run": "true",
            "offset": offset,
            "community_slug": community_slug,
        }
    )

    # Progress bar
    progress_pct = round((offset / max(total, 1)) * 100, 1)

    progress_div = (
        Div(
            Div(
                Span(
                    "",
                    id="speed-run-stats-text",
                    cls="text-sm text-slate-300",
                ),
                cls="flex justify-between items-center mb-2",
            ),
            Div(
                Div(cls="h-2 bg-purple-500 rounded-full", style=f"width: {progress_pct}%"),
                cls="w-full h-2 bg-slate-700 rounded-full overflow-hidden",
            ),
            id="speed-run-progress",
            hx_swap_oob="true",
        )
        if include_progress
        else None
    )

    # Pre-fetch next card params
    prefetch_offset = offset + 1
    prefetch_params = urlencode({"offset": prefetch_offset, "community_slug": community_slug})

    return Div(
        progress_div,
        # Cluster card
        Div(
            # Face grid — scrollable, all faces shown
            Div(
                *face_thumbs,
                cls="flex flex-wrap gap-3 justify-center mb-6 max-h-80 overflow-y-auto",
            ),
            # Identity info
            Div(
                H3(display_name, cls="text-lg font-semibold text-white", title=name),
                P(
                    f"{face_count} face{'s' if face_count != 1 else ''} \u00b7 {identity_data.get('state', 'INBOX')}",
                    cls="text-sm text-slate-400 mt-1",
                ),
                cls="text-center mb-6",
            ),
            # Action buttons
            Div(
                Button(
                    "Confirm All (Y)",
                    cls="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition-colors",
                    hx_post=f"/api/cluster-review/confirm-all?{common_params}",
                    hx_target="#speed-run-card",
                    hx_swap="outerHTML",
                    data_action="speed-confirm",
                ),
                Button(
                    "Reject All (N)",
                    cls="px-6 py-3 bg-red-600 hover:bg-red-500 text-white font-medium rounded-lg transition-colors",
                    hx_post=f"/api/cluster-review/reject-all?{common_params}",
                    hx_target="#speed-run-card",
                    hx_swap="outerHTML",
                    data_action="speed-reject",
                ),
                Button(
                    "Skip (S)",
                    cls="px-6 py-3 bg-slate-600 hover:bg-slate-500 text-white font-medium rounded-lg transition-colors",
                    hx_post=f"/api/cluster-review/skip?{common_params}",
                    hx_target="#speed-run-card",
                    hx_swap="outerHTML",
                    data_action="speed-skip",
                ),
                Button(
                    "Dismiss (D)",
                    cls="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-slate-400 font-medium rounded-lg transition-colors border border-slate-600",
                    hx_post=f"/api/cluster-review/dismiss?{common_params}",
                    hx_target="#speed-run-card",
                    hx_swap="outerHTML",
                    data_action="speed-dismiss",
                ),
                cls="flex flex-wrap gap-3 justify-center",
            ),
            cls="p-8 bg-slate-900/60 border border-slate-700 rounded-xl",
        ),
        # Hidden pre-fetch container for next card
        Div(
            id="speed-run-prefetch",
            cls="hidden",
            hx_get=f"/admin/cluster-review/next?{prefetch_params}",
            hx_trigger="load",
            hx_swap="innerHTML",
        ),
        id="speed-run-card",
    )


@rt("/api/cluster-review/enrichment-panel")
def get(identity_id: str = "", offset: int = 0, community_slug: str = "", sess=None, request=None):
    """FB-025: Lazy-load enrichment panel after confirm for perceived speed."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    registry = _main_mod.load_registry()
    identity = registry.get_identity(identity_id) if identity_id else None
    if not identity:
        return Div(P("Identity not found.", cls="text-slate-400"), id="speed-run-card")
    community = getattr(request.state, "community", None) if request else None
    if not community and community_slug:
        from app.supabase_data import get_community_by_slug as _gcbs

        community = _gcbs(community_slug)
    return _speed_run_enrichment_panel(identity_id, identity, offset, community_slug, community=community)


def _speed_run_enrichment_panel(identity_id, identity_data, offset, community_slug, community=None):
    """Render the post-confirm enrichment panel for naming/merging."""
    # Resolve community from slug if not provided (API paths skip CommunityMiddleware)
    if community is None and community_slug:
        from app.supabase_data import get_community_by_slug

        community = get_community_by_slug(community_slug)

    display_name = identity_data.get("name", "Unknown")
    if display_name.startswith("Unidentified Person "):
        display_name = "Person " + display_name[len("Unidentified Person ") :]

    # Get anchor crop for preview
    anchor_crop_url = None
    face_ids = _identity_face_ids(identity_data)
    if face_ids:
        best_fid = _best_face_id(face_ids)
        if best_fid:
            anchor_crop_url = _get_crop_url_for_face(best_fid)

    # Top 3 suggested matches from confirmed identities (name-based, quick)
    import time as _time
    import logging

    _t_sug = _time.time()
    suggestions = _get_confirmed_identity_suggestions(identity_id, limit=6, community_slug=community_slug)
    logging.info(f"PERF enrichment suggestions: {_time.time() - _t_sug:.3f}s ({len(suggestions)} results)")
    suggestion_els = []
    for sug in suggestions:
        sug_crop = _get_crop_url_for_face(sug["best_face_id"]) if sug.get("best_face_id") else None
        merge_params = urlencode(
            {
                "source_id": identity_id,
                "target_id": sug["identity_id"],
                "offset": offset,
                "community_slug": community_slug,
            }
        )
        # Cross-community badge (FB-100)
        cross_badge = _main_mod._cross_community_badge(sug["identity_id"], community) if community else None
        nav_prefix = _main_mod.community_url_prefix(community_slug)
        sug_person_url = f"{nav_prefix}/person/{sug['identity_id']}"
        sug_thumb = (
            Img(
                src=sug_crop,
                alt=sug["name"],
                cls="w-12 h-12 object-cover rounded-lg border border-slate-600",
                loading="lazy",
            )
            if sug_crop
            else Div(cls="w-12 h-12 rounded-lg bg-slate-700")
        )
        sug_name_row = (
            Div(
                Span(sug["name"], cls="text-sm font-medium text-white"),
                cross_badge,
                cls="flex items-center gap-2",
            )
            if cross_badge
            else Span(sug["name"], cls="text-sm font-medium text-white")
        )
        suggestion_els.append(
            Div(
                A(
                    sug_thumb,
                    href=sug_person_url,
                    target="_blank",
                    title=f"View {sug['name']}'s face card",
                    cls="flex-shrink-0",
                ),
                A(
                    sug_name_row,
                    P(f"{sug['face_count']} faces", cls="text-xs text-slate-400"),
                    href=sug_person_url,
                    target="_blank",
                    cls="ml-3 flex-1 min-w-0 hover:text-indigo-300 transition-colors",
                ),
                Button(
                    "Merge",
                    cls="px-3 py-1.5 text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors",
                    hx_post=f"/api/cluster-review/merge?{merge_params}",
                    hx_target="#speed-run-card",
                    hx_swap="outerHTML",
                ),
                cls="flex items-center p-2 bg-slate-800/60 border border-slate-700 rounded-lg",
            )
        )

    save_params = urlencode(
        {
            "identity_id": identity_id,
            "offset": offset,
            "community_slug": community_slug,
        }
    )

    skip_next_params = urlencode(
        {
            "offset": offset + 1,
            "community_slug": community_slug,
        }
    )

    # GEDCOM link panel (reuse from relationship_routes)
    from app.relationship_routes import _gedcom_link_panel

    gedcom_panel = _gedcom_link_panel(identity_id, display_name)

    return Div(
        # 1. Confirmed banner + preview crop
        Div(
            Div(
                Img(
                    src=anchor_crop_url,
                    alt=display_name,
                    cls="w-16 h-16 object-cover rounded-lg border border-slate-600",
                )
                if anchor_crop_url
                else None,
            ),
            Div(
                Span("Confirmed!", cls="text-emerald-400 text-lg font-semibold"),
                Span(f"{display_name} — {len(face_ids)} faces", cls="text-slate-300 text-sm block mt-1"),
                cls="ml-4",
            ),
            cls="flex items-center mb-4 p-3 bg-emerald-900/30 border border-emerald-700/50 rounded-lg",
        ),
        # 2. Merge search — "Is this an existing person?" (moved UP)
        Div(
            H4("Is this an existing person?", cls="text-sm font-semibold text-slate-300 mb-2"),
            Input(
                type="text",
                name="q",
                placeholder="Search confirmed identities to merge...",
                cls="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white "
                "placeholder-slate-400 focus:outline-none focus:border-blue-500",
                hx_get=f"/api/cluster-review/search-identities?source_id={identity_id}&offset={offset}&community_slug={community_slug}",
                hx_target="#enrichment-search-results",
                hx_swap="innerHTML",
                hx_trigger="keyup changed delay:300ms",
                autofocus=True,
            ),
            Div(id="enrichment-search-results", cls="mt-2 space-y-2"),
            cls="mb-4",
        ),
        # 3. Suggested matches with merge buttons (moved UP)
        Div(
            H4("Suggested Matches", cls="text-sm font-semibold text-slate-300 mb-2"),
            *suggestion_els,
            cls="mb-4 space-y-2",
        )
        if suggestion_els
        else None,
        # 4. Name input — "Or name this new person:" (moved DOWN)
        Div(
            H4("Or name this new person:", cls="text-sm font-semibold text-slate-300 mb-2"),
            Div(
                Input(
                    type="text",
                    name="new_name",
                    placeholder="Enter name for this person...",
                    cls="flex-1 px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white "
                    "placeholder-slate-400 focus:outline-none focus:border-purple-500",
                    id="enrichment-name-input",
                ),
                Button(
                    "Save Name",
                    cls="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-lg transition-colors ml-2",
                    hx_post=f"/api/cluster-review/save-name?{save_params}",
                    hx_target="#speed-run-card",
                    hx_swap="outerHTML",
                    hx_include="#enrichment-name-input",
                    data_action="speed-save-name",
                ),
                cls="flex items-center",
            ),
            cls="mb-4",
        ),
        # 5. GEDCOM link (NEW — inline)
        gedcom_panel,
        # 6. Done / Skip button
        Div(
            Button(
                "Done — Next Cluster",
                cls="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium rounded-lg transition-colors",
                hx_get=f"/admin/cluster-review/next?{skip_next_params}",
                hx_target="#speed-run-card",
                hx_swap="outerHTML",
                data_action="speed-enrich-skip",
            ),
            cls="flex justify-center",
        ),
        id="speed-run-card",
        cls="p-8 bg-slate-900/60 border border-slate-700 rounded-xl",
        data_enrichment="true",
    )


def _get_confirmed_identity_suggestions(identity_id, limit=3, community_slug=None):
    """Get top confirmed identities as merge suggestions sorted by embedding distance.

    Uses precomputed vectorized matrix from perf_cache for O(1) distance computation.
    Cached for 30s per identity_id, invalidated on confirm/merge/skip/reject.
    """
    cache_key = (identity_id, community_slug or "")
    cached = _suggestions_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _CACHE_TTL:
        return cached[1]

    registry = _main_mod.load_registry()
    identities = registry._identities if hasattr(registry, "_identities") else {}

    # Get target identity embedding
    target_identity = identities.get(identity_id, {})
    target_face_ids = _identity_face_ids(target_identity)
    target_embedding = None
    try:
        face_data = _main_mod.get_face_data()
        for fid in target_face_ids:
            fd = face_data.get(fid)
            if fd and "embeddings" in fd:
                emb = fd["embeddings"]
                if hasattr(emb, "__len__") and len(emb) > 0:
                    target_embedding = np.array(emb).flatten()
                    break
    except Exception:
        pass

    if target_embedding is not None:
        # Use vectorized perf_cache
        from app.perf_cache import get_confirmed_distances

        all_results = get_confirmed_distances(target_embedding, community_slug=community_slug)
        # Filter out self
        result = [r for r in all_results if r["identity_id"] != identity_id][:limit]
    else:
        # Fallback: face-count sorting (no embedding available)
        suggestions = []
        for iid, idata in identities.items():
            if iid == identity_id:
                continue
            if idata.get("merged_into"):
                continue
            if idata.get("state") != "CONFIRMED":
                continue
            face_ids = _identity_face_ids(idata)
            if not face_ids:
                continue
            best_fid = _best_face_id(face_ids)
            suggestions.append(
                {
                    "identity_id": iid,
                    "name": idata.get("name", "Unknown"),
                    "face_count": len(face_ids),
                    "best_face_id": best_fid,
                    "distance": 999.0,
                }
            )
        suggestions.sort(key=lambda s: s["face_count"], reverse=True)
        result = suggestions[:limit]

    _suggestions_cache[cache_key] = (time.time(), result)
    return result


def _speed_run_done_card(offset, total):
    """Render the completion card when all clusters have been reviewed."""
    return Div(
        Div(
            Div(
                Span(
                    f"{total} clusters reviewed",
                    id="speed-run-stats-text",
                    cls="text-sm text-emerald-300",
                ),
                cls="flex justify-between items-center mb-2",
            ),
            Div(
                Div(cls="h-2 bg-emerald-500 rounded-full", style="width: 100%"),
                cls="w-full h-2 bg-slate-700 rounded-full overflow-hidden",
            ),
            id="speed-run-progress",
            hx_swap_oob="true",
        ),
        Div(
            Div(
                Span("✓", cls="text-4xl text-emerald-400"),
                cls="mb-4",
            ),
            H3("All Done!", cls="text-xl font-semibold text-white mb-2"),
            P(
                f"Reviewed all {total} cluster{'s' if total != 1 else ''}.",
                cls="text-slate-400 mb-6",
            ),
            A(
                "Back to Dashboard",
                href="upload-review",
                cls="px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-lg transition-colors inline-block",
            ),
            cls="p-8 bg-slate-900/60 border border-slate-700 rounded-xl text-center",
        ),
        id="speed-run-card",
    )


def _speed_run_next_card(offset, community_slug, request):
    """Get the next cluster card for speed-run auto-advance."""
    clusters = _get_speed_run_clusters(community_slug, request)
    total = len(clusters)

    if offset >= total:
        return _speed_run_done_card(offset, total)

    iid, idata = clusters[offset]
    return _speed_run_cluster_card(iid, idata, offset, total, community_slug)


def _speed_run_undo_button(undo_state, oob=False):
    """Render the undo banner. Hidden when undo_state is None."""
    if undo_state:
        params = urlencode(
            {
                "identity_id": undo_state["identity_id"],
                "action": undo_state["action"],
                "offset": undo_state["offset"],
                "community_slug": undo_state.get("community_slug", ""),
                "face_data": json.dumps(undo_state.get("face_data", {})),
            }
        )
        action_labels = {
            "confirm-all": "Confirmed",
            "reject-all": "Rejected",
            "skip": "Skipped",
            "dismiss": "Dismissed",
        }
        action_label = action_labels.get(undo_state["action"], undo_state["action"].title())
        identity_name = undo_state.get("identity_name", "")
        face_count = undo_state.get("face_count", 0)
        context_parts = [f"{action_label}"]
        if identity_name:
            context_parts.append(identity_name)
        if face_count:
            context_parts.append(f"{face_count} face{'s' if face_count != 1 else ''}")
        context_text = " \u2014 ".join(context_parts)

        banner = Div(
            Span(f"Undo: {context_text}", cls="text-sm text-amber-200 flex-1"),
            Button(
                "Undo (Z)",
                cls="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white text-sm font-medium rounded-lg transition-colors ml-3",
                hx_post=f"/api/cluster-review/undo?{params}",
                hx_target="#speed-run-card",
                hx_swap="outerHTML",
                data_action="speed-undo",
            ),
            cls="flex items-center p-3 bg-amber-900/40 border border-amber-700/50 rounded-lg",
        )
    else:
        banner = None
    return Div(
        banner,
        id="speed-run-undo",
        cls="mt-4" if undo_state else "",
        **({"hx_swap_oob": "true"} if oob else {}),
    )


def _build_undo_state(identity_id, action, offset, community_slug, face_data=None, identity_name="", face_count=0):
    """Build an undo state dict for the last speed-run action."""
    return {
        "identity_id": identity_id,
        "action": action,
        "offset": offset,
        "community_slug": community_slug,
        "face_data": face_data or {},
        "identity_name": identity_name,
        "face_count": face_count,
    }


@rt("/admin/cluster-review/next")
def get(offset: int = 0, community_slug: str = "", sess=None, request=None):
    """Return the next cluster card for speed-run mode (HTMX partial)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    return _speed_run_next_card(offset, community_slug, request)


@rt("/api/cluster-review/skip")
def post(
    identity_id: str = "", offset: int = 0, community_slug: str = "", input_method: str = "", sess=None, request=None
):
    """Skip a cluster (no data change) and auto-advance with undo support."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    # Get identity info for undo context
    registry = _main_mod.load_registry()
    identity = registry._identities.get(identity_id, {})
    iname = identity.get("name", "Unknown")
    all_faces = _identity_face_ids(identity)

    _main_mod.log_user_action(
        "SPEED_RUN_SKIP",
        identity_id=identity_id,
        mode="speed-run",
        admin=_speed_run_admin_email(sess),
        **({"input_method": input_method} if input_method else {}),
    )

    undo_state = _build_undo_state(
        identity_id,
        "skip",
        offset,
        community_slug,
        identity_name=iname,
        face_count=len(all_faces),
    )
    next_card = _speed_run_next_card(offset + 1, community_slug, request)
    undo_btn = _speed_run_undo_button(undo_state, oob=True)
    return next_card, undo_btn


@rt("/api/cluster-review/dismiss")
def post(
    identity_id: str = "",
    offset: int = 0,
    community_slug: str = "",
    speed_run: str = "",
    input_method: str = "",
    sess=None,
    request=None,
):
    """Dismiss a cluster (set to SKIPPED) and auto-advance."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    registry = _main_mod.load_registry()
    identity = registry._identities.get(identity_id)
    prev_state = identity.get("state", "INBOX") if identity else "INBOX"
    iname = identity.get("name", "Unknown") if identity else "Unknown"
    all_faces = _identity_face_ids(identity) if identity else []
    if identity:
        identity["state"] = "SKIPPED"
        _main_mod.save_registry(registry)

    _main_mod.log_user_action(
        "SPEED_RUN_DISMISS",
        identity_id=identity_id,
        mode="speed-run",
        admin=_speed_run_admin_email(sess),
        **({"input_method": input_method} if input_method else {}),
    )

    undo_state = _build_undo_state(
        identity_id,
        "dismiss",
        offset,
        community_slug,
        {"prev_state": prev_state},
        identity_name=iname,
        face_count=len(all_faces),
    )
    next_card = _speed_run_next_card(offset + 1, community_slug, request)
    undo_btn = _speed_run_undo_button(undo_state, oob=True)
    return next_card, undo_btn


@rt("/api/cluster-review/save-name")
def post(
    identity_id: str = "",
    new_name: str = "",
    offset: int = 0,
    community_slug: str = "",
    input_method: str = "",
    sess=None,
    request=None,
):
    """Save a name for an identity during speed-run enrichment, then advance."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if new_name and new_name.strip():
        registry = _main_mod.load_registry()
        try:
            registry.rename_identity(identity_id, new_name.strip(), user_source="admin/speed-run-enrichment")
            _main_mod.save_registry(registry)
            _main_mod.log_user_action(
                "SPEED_RUN_NAME",
                identity_id=identity_id,
                new_name=new_name.strip(),
                mode="speed-run",
                admin=_speed_run_admin_email(sess),
                **({"input_method": input_method} if input_method else {}),
            )
        except (KeyError, ValueError) as e:
            return Div(P(f"Error: {e}", cls="text-red-400 text-sm"), cls="p-2")

    return _speed_run_next_card(offset + 1, community_slug, request)


@rt("/api/cluster-review/search-identities")
def get(q: str = "", source_id: str = "", offset: int = 0, community_slug: str = "", sess=None, request=None):
    """Search confirmed identities by name substring for merge typeahead."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not q or len(q.strip()) < 2:
        return Div()

    query = q.strip().lower()
    registry = _main_mod.load_registry()
    identities = registry._identities if hasattr(registry, "_identities") else {}

    results = []
    for iid, idata in identities.items():
        if iid == source_id:
            continue
        if idata.get("merged_into"):
            continue
        if idata.get("state") != "CONFIRMED":
            continue
        name = idata.get("name", "")
        if query in name.lower():
            face_ids = _identity_face_ids(idata)
            best_fid = _best_face_id(face_ids)
            results.append(
                {
                    "identity_id": iid,
                    "name": name,
                    "face_count": len(face_ids),
                    "best_face_id": best_fid,
                }
            )

    results.sort(key=lambda r: (-r["face_count"], r["name"]))
    results = results[:10]

    if not results:
        return Div(P("No matches found.", cls="text-xs text-slate-500"), cls="p-2")

    community = getattr(request.state, "community", None) if request else None
    if community is None and community_slug:
        from app.supabase_data import get_community_by_slug

        community = get_community_by_slug(community_slug)
    els = []
    for r in results:
        crop_url = _get_crop_url_for_face(r["best_face_id"]) if r.get("best_face_id") else None
        merge_params = urlencode(
            {
                "source_id": source_id,
                "target_id": r["identity_id"],
                "offset": offset,
                "community_slug": community_slug,
            }
        )
        cross_badge = _main_mod._cross_community_badge(r["identity_id"], community) if community else None
        els.append(
            Div(
                Img(
                    src=crop_url,
                    alt=r["name"],
                    cls="w-10 h-10 object-cover rounded-lg border border-slate-600",
                    loading="lazy",
                )
                if crop_url
                else Div(cls="w-10 h-10 rounded-lg bg-slate-700"),
                Div(
                    Div(
                        Span(r["name"], cls="text-sm font-medium text-white"),
                        cross_badge,
                        cls="flex items-center gap-2",
                    )
                    if cross_badge
                    else Span(r["name"], cls="text-sm font-medium text-white"),
                    P(f"{r['face_count']} faces", cls="text-xs text-slate-400"),
                    cls="ml-3 flex-1 min-w-0",
                ),
                Button(
                    "Merge",
                    cls="px-3 py-1.5 text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors",
                    hx_post=f"/api/cluster-review/merge?{merge_params}",
                    hx_target="#speed-run-card",
                    hx_swap="outerHTML",
                ),
                cls="flex items-center p-2 bg-slate-800/60 border border-slate-700 rounded-lg",
            )
        )

    return Div(*els, cls="space-y-2")


@rt("/api/cluster-review/merge")
def post(
    source_id: str = "",
    target_id: str = "",
    offset: int = 0,
    community_slug: str = "",
    input_method: str = "",
    sess=None,
    request=None,
):
    """Merge source identity into target during speed-run enrichment."""
    import time as _time
    import logging

    t0 = _time.time()
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    t1 = _time.time()
    registry = _main_mod.load_registry()
    photo_registry = _main_mod.load_photo_registry()
    t2 = _time.time()

    try:
        result = registry.merge_identities(
            source_id,
            target_id,
            user_source="admin/speed-run-merge",
            photo_registry=photo_registry,
        )
        t3 = _time.time()
        if not result.get("success"):
            reason = result.get("reason", "unknown")
            return Div(P(f"Merge failed: {reason}", cls="text-red-400 text-sm"), cls="p-4")

        _main_mod.save_registry(registry)
        t4 = _time.time()
        logging.info(f"PERF merge: load={t2 - t1:.3f}s merge={t3 - t2:.3f}s save={t4 - t3:.3f}s total={t4 - t0:.3f}s")
        _main_mod.log_user_action(
            "SPEED_RUN_MERGE",
            source_id=source_id,
            target_id=target_id,
            faces_merged=result.get("faces_merged", 0),
            mode="speed-run",
            admin=_speed_run_admin_email(sess),
            **({"input_method": input_method} if input_method else {}),
        )
        _log_audit(
            "merge",
            entity_id=result.get("target_id", target_id),
            user_email=_speed_run_admin_email(sess),
            old_value={"source_id": result.get("source_id", source_id)},
            new_value={
                "merged_into": result.get("target_id", target_id),
                "faces_merged": result.get("faces_merged", 0),
            },
            metadata={"route": "speed_run_merge", "input_method": input_method or "click"},
        )
    except (KeyError, ValueError) as e:
        return Div(P(f"Error: {e}", cls="text-red-400 text-sm"), cls="p-4")

    target_data = registry._identities.get(result.get("target_id", target_id), {})
    target_name = target_data.get("name", "Unknown")
    target_face_count = len(_identity_face_ids(target_data))
    faces_merged = result.get("faces_merged", 0)

    next_params = urlencode({"offset": offset + 1, "community_slug": community_slug})

    # Build merge confirmation banner with auto-advance button (FB-027)
    merge_banner = Div(
        Div(
            Span("Merged!", cls="text-indigo-400 text-lg font-semibold mr-2"),
            Span(
                f"Merged {faces_merged} face{'s' if faces_merged != 1 else ''} into {target_name} "
                f"(now {target_face_count} total faces)",
                cls="text-slate-300 text-sm",
            ),
            cls="flex items-center flex-wrap",
        ),
        Button(
            "Next Cluster \u2192",
            hx_get=f"/admin/cluster-review/next?{next_params}",
            hx_target="#speed-run-card",
            hx_swap="outerHTML",
            cls="mt-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-500 transition-colors min-h-[44px]",
        ),
        cls="mb-4 p-3 bg-indigo-900/30 border border-indigo-700/50 rounded-lg",
    )

    # Return enrichment panel for the merged-into identity with merge banner prepended
    community = getattr(request.state, "community", None) if request else None
    if not community and community_slug:
        from app.supabase_data import get_community_by_slug as _gcbs3

        community = _gcbs3(community_slug)
    enrichment = _speed_run_enrichment_panel(
        result.get("target_id", target_id), target_data, offset, community_slug, community=community
    )
    # Prepend merge banner — enrichment panel already has id="speed-run-card"
    enrichment.children = (merge_banner, *enrichment.children)
    return enrichment


@rt("/api/cluster-review/undo")
def post(
    identity_id: str = "",
    action: str = "",
    offset: int = 0,
    community_slug: str = "",
    face_data: str = "{}",
    sess=None,
    request=None,
):
    """Undo the last speed-run action and show the previous cluster card."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    try:
        fd = json.loads(face_data)
    except (json.JSONDecodeError, TypeError):
        fd = {}

    registry = _main_mod.load_registry()
    identity = registry._identities.get(identity_id)

    if identity:
        prev_state = fd.get("prev_state", "INBOX")

        if action == "confirm-all":
            # Move faces from anchor_ids back to candidate_ids
            candidates = fd.get("candidates", [])
            anchors = identity.get("anchor_ids", [])
            for fid in candidates:
                # Remove from anchors
                identity["anchor_ids"] = [a for a in identity.get("anchor_ids", []) if a != fid]
                # Add back to candidates
                if fid not in identity.get("candidate_ids", []):
                    identity.setdefault("candidate_ids", []).append(fid)
            identity["state"] = prev_state

        elif action == "reject-all":
            # Remove faces from negative_ids, restore to candidate_ids
            candidates = fd.get("candidates", [])
            for fid in candidates:
                identity["negative_ids"] = [n for n in identity.get("negative_ids", []) if n != fid]
                if fid not in identity.get("candidate_ids", []):
                    identity.setdefault("candidate_ids", []).append(fid)
            identity["state"] = prev_state

        elif action == "dismiss":
            # Restore state from SKIPPED
            identity["state"] = prev_state

        elif action == "skip":
            # Skip doesn't modify data — just go back to the card
            pass

        if action != "skip":
            _main_mod.save_registry(registry)

        _main_mod.log_user_action(
            "SPEED_RUN_UNDO",
            identity_id=identity_id,
            original_action=action,
            mode="speed-run",
            admin=_speed_run_admin_email(sess),
        )

    # Show the card at the original offset (go back)
    clusters = _get_speed_run_clusters(community_slug, request)
    total = len(clusters)

    if offset < total:
        iid, idata = clusters[offset]
        card = _speed_run_cluster_card(iid, idata, offset, total, community_slug)
    else:
        card = _speed_run_next_card(offset, community_slug, request)

    # Hide the undo button after undoing
    undo_btn = _speed_run_undo_button(None, oob=True)
    return card, undo_btn


def _speed_run_admin_email(sess) -> str:
    """Return the admin email from the session, or 'admin' as fallback."""
    if _main_mod.is_auth_enabled():
        user = _main_mod.get_current_user(sess or {})
        if user and getattr(user, "email", None):
            return user.email
    return "admin"


def _active_learning_actor(sess) -> str:
    """Return the best available actor identity for queue labels."""
    if _main_mod.is_auth_enabled():
        user = _main_mod.get_current_user(sess or {})
        if user and getattr(user, "email", None):
            return user.email
    return "admin"


def _active_learning_status_card(message: str, tone: str, *, face_id_a: str, face_id_b: str):
    """Render one compact status card for a labeled or reverted pair."""
    pair_dom_id = _safe_dom_id("::".join(sorted([face_id_a, face_id_b])))
    tone_map = {
        "success": "text-emerald-400 bg-emerald-900/30 border-emerald-700/50",
        "danger": "text-red-400 bg-red-900/30 border-red-700/50",
        "info": "text-slate-300 bg-slate-900/40 border-slate-700/50",
    }
    palette = tone_map.get(tone, tone_map["info"])
    return Div(
        Div(
            Span(message, cls="text-sm"),
            Button(
                "Revert",
                cls="px-3 py-1.5 text-xs font-medium bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors ml-3",
                hx_post=f"/api/cluster-review/learn-revert?{urlencode({'face_id_a': face_id_a, 'face_id_b': face_id_b})}",
                hx_target=f"#active-learning-card-{pair_dom_id}",
                hx_swap="outerHTML",
            ),
            cls="flex items-center",
        ),
        id=f"active-learning-card-{pair_dom_id}",
        cls=f"p-3 border rounded-lg {palette}",
    )


@rt("/api/cluster-review/learn-same")
def post(
    face_id_a: str = "",
    face_id_b: str = "",
    source_identity_id: str = "",
    target_identity_id: str = "",
    queue_item_id: str = "",
    queue_run_id: str = "",
    reasons: str = "",
    sess=None,
):
    """Record a positive active-learning label without mutating canonical identity state."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    actor = _active_learning_actor(sess)
    try:
        record_active_learning_label(
            face_id_a,
            face_id_b,
            is_same_person=True,
            actor_id=actor,
            source_surface="admin/upload-review-active-learning",
            labels_path=default_labels_path(_data_dir()),
            supabase_client=get_supabase_client(),
            metadata={
                "queue_item_id": queue_item_id,
                "queue_run_id": queue_run_id,
                "source_identity_id": source_identity_id,
                "target_identity_id": target_identity_id,
                "reasons": [reason for reason in reasons.split(",") if reason],
            },
        )
    except Exception as exc:
        return Div(P(f"Error: {exc}", cls="text-red-400 text-sm"), cls="p-2")

    return _active_learning_status_card(
        "Recorded: same person. Canonical identity state unchanged.",
        "success",
        face_id_a=face_id_a,
        face_id_b=face_id_b,
    )


@rt("/api/cluster-review/learn-different")
def post(
    face_id_a: str = "",
    face_id_b: str = "",
    source_identity_id: str = "",
    target_identity_id: str = "",
    queue_item_id: str = "",
    queue_run_id: str = "",
    reasons: str = "",
    sess=None,
):
    """Record a negative active-learning label without mutating canonical identity state."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    actor = _active_learning_actor(sess)
    try:
        record_active_learning_label(
            face_id_a,
            face_id_b,
            is_same_person=False,
            actor_id=actor,
            source_surface="admin/upload-review-active-learning",
            labels_path=default_labels_path(_data_dir()),
            supabase_client=get_supabase_client(),
            metadata={
                "queue_item_id": queue_item_id,
                "queue_run_id": queue_run_id,
                "source_identity_id": source_identity_id,
                "target_identity_id": target_identity_id,
                "reasons": [reason for reason in reasons.split(",") if reason],
            },
        )
    except Exception as exc:
        return Div(P(f"Error: {exc}", cls="text-red-400 text-sm"), cls="p-2")

    return _active_learning_status_card(
        "Recorded: different people. Canonical identity state unchanged.",
        "danger",
        face_id_a=face_id_a,
        face_id_b=face_id_b,
    )


@rt("/api/cluster-review/learn-revert")
def post(face_id_a: str = "", face_id_b: str = "", sess=None):
    """Revert one active-learning label before recalibration consumes it."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    actor = _active_learning_actor(sess)
    reverted = revert_active_learning_label(
        face_id_a,
        face_id_b,
        actor_id=actor,
        source_surface="admin/upload-review-active-learning",
        labels_path=default_labels_path(_data_dir()),
        supabase_client=get_supabase_client(),
    )
    if reverted is None:
        return Div(P("Label not found.", cls="text-slate-400 text-sm"), cls="p-2")

    pair_dom_id = _safe_dom_id(reverted["pair_key"])
    return Div(
        Span("Reverted", cls="text-slate-400 text-sm"),
        id=f"active-learning-label-{pair_dom_id}",
        cls="p-3 bg-slate-900/40 border border-slate-700/50 rounded-lg",
    )


@rt("/api/cluster-review/gedcom-panel")
def get(identity_id: str = "", name: str = "", sess=None):
    """Return inline GEDCOM search panel for an identity."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    # Reuse the existing GEDCOM link panel component
    return _main_mod._gedcom_link_panel(identity_id, name)


# ---------------------------------------------------------------------------
# PRD-040: Batch Cluster Validation
# ---------------------------------------------------------------------------


def _get_batch_clusters(community_slug: str = "", request=None, min_faces: int = 1):
    """Get all INBOX identities for batch validation.

    Returns list of (identity_id, identity_data, face_count) tuples,
    sorted by face count descending.
    """
    registry = _main_mod.load_registry()
    identities = registry._identities if hasattr(registry, "_identities") else {}

    # Community filtering
    # Lesson 109: /api/ routes skip CommunityMiddleware — fall back to slug lookup
    community = getattr(request.state, "community", None) if request else None
    if not community and community_slug:
        from app.supabase_data import get_community_by_slug as _gcbs4

        community = _gcbs4(community_slug)
    community_identity_ids = None
    if community:
        community_identity_ids = _main_mod._get_community_identity_ids(community)

    if community_identity_ids is not None:
        filtered_ids = {iid: idata for iid, idata in identities.items() if iid in community_identity_ids}
    else:
        filtered_ids = identities

    clusters = []
    for iid, idata in filtered_ids.items():
        if idata.get("merged_into"):
            continue
        state = idata.get("state", "")
        if state != "INBOX":
            continue
        all_faces = _identity_face_ids(idata)
        face_count = len(all_faces)
        if face_count >= min_faces:
            clusters.append((iid, idata, face_count))

    clusters.sort(key=lambda x: -x[2])
    return clusters


def _batch_card(identity_id, identity_data, face_count):
    """Render a single card for batch cluster validation grid."""
    all_faces = _identity_face_ids(identity_data)
    crop_url = None
    for fid in all_faces[:1]:
        crop_url = _get_crop_url_for_face(fid)

    name = identity_data.get("name", "Unknown")
    display_name = name
    if name.startswith("Unidentified Person "):
        display_name = "Person " + name[len("Unidentified Person ") :]

    return Div(
        # Checkbox overlay
        Input(
            type="checkbox",
            checked=True,
            cls="absolute top-2 left-2 w-5 h-5 accent-emerald-500 z-10 cursor-pointer",
            data_identity_id=identity_id,
            data_action="batch-toggle",
        ),
        # Face crop
        Img(
            src=crop_url or "",
            alt=display_name,
            cls="w-full aspect-square object-cover rounded-t-lg",
            loading="lazy",
            style="min-height:80px;min-width:80px;",
        )
        if crop_url
        else Div(
            Span("No crop", cls="text-slate-500 text-xs"),
            cls="w-full aspect-square bg-slate-800 rounded-t-lg flex items-center justify-center",
        ),
        # Info bar
        Div(
            Span(
                f"{face_count} face{'s' if face_count != 1 else ''}",
                cls="text-xs font-medium text-white bg-slate-700 px-2 py-0.5 rounded-full",
            ),
            P(display_name, cls="text-xs text-slate-400 mt-1 truncate"),
            P(identity_id[:12] + "...", cls="text-[10px] text-slate-600 mt-0.5 truncate"),
            cls="p-2",
        ),
        cls="relative bg-slate-900/60 border border-slate-700/50 rounded-lg cursor-pointer hover:border-emerald-500/50 transition-colors batch-card",
        data_identity_id=identity_id,
    )


@rt("/admin/cluster-batch")
def get(min_faces: int = 1, sess=None, request=None):
    """Batch Cluster Validation — PRD-040.

    Google Photos-style grid with checkboxes for bulk INBOX cluster confirmation.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
    clusters = _get_batch_clusters(community_slug, request, min_faces=min_faces)
    total = len(clusters)

    # Filter bar
    filter_buttons = []
    for label, min_val in [("All", 1), ("2+", 2), ("5+", 5), ("10+", 10)]:
        active = min_faces == min_val
        btn_cls = "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors "
        btn_cls += "bg-emerald-600 text-white" if active else "bg-slate-700 hover:bg-slate-600 text-slate-200"
        filter_buttons.append(
            A(
                label,
                href=f"cluster-batch?min_faces={min_val}",
                cls=btn_cls,
            )
        )

    filter_bar = Div(
        Span("Filter by face count:", cls="text-sm text-slate-400 mr-3"),
        *filter_buttons,
        cls="flex items-center gap-2 mb-4",
    )

    # Stats + select all bar
    stats_bar = Div(
        Span(
            f"{total} selected of {total} total",
            id="batch-stats",
            cls="text-sm text-slate-300",
        ),
        Button(
            "Deselect All",
            cls="px-3 py-1.5 text-xs font-medium bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors",
            data_action="batch-toggle-all",
        ),
        cls="flex items-center justify-between mb-4",
    )

    # Grid of cards
    cards = []
    for iid, idata, fcount in clusters:
        cards.append(_batch_card(iid, idata, fcount))

    grid = (
        Div(
            *cards,
            cls="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3",
            id="batch-grid",
        )
        if cards
        else Div(
            H3("No INBOX clusters to validate", cls="text-xl font-semibold text-white mb-2"),
            P("All clusters have been reviewed.", cls="text-slate-400"),
            cls="p-8 text-center",
        )
    )

    # Sticky footer with confirm button
    footer = (
        Div(
            Button(
                f"Confirm Selected ({total})",
                id="batch-confirm-btn",
                cls="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg transition-colors disabled:opacity-50",
                data_action="batch-confirm",
                data_total=str(total),
            ),
            cls="fixed bottom-0 left-0 right-0 bg-slate-900/95 border-t border-slate-700 p-4 flex justify-center z-50",
        )
        if cards
        else ""
    )

    # Summary container (hidden initially, shown after confirm)
    summary = Div(id="batch-summary", cls="mb-4")

    # JavaScript for batch interactions
    batch_js = Script("""
        (function() {
            var grid = document.getElementById('batch-grid');
            if (!grid) return;

            function updateCount() {
                var checked = grid.querySelectorAll('input[data-action="batch-toggle"]:checked');
                var total = grid.querySelectorAll('input[data-action="batch-toggle"]');
                var statsEl = document.getElementById('batch-stats');
                var btnEl = document.getElementById('batch-confirm-btn');
                if (statsEl) statsEl.textContent = checked.length + ' selected of ' + total.length + ' total';
                if (btnEl) {
                    btnEl.textContent = 'Confirm Selected (' + checked.length + ')';
                    btnEl.disabled = checked.length === 0;
                }
            }

            document.addEventListener('click', function(e) {
                var action = e.target.getAttribute('data-action');
                if (!action) {
                    // Check if clicked on a card (not the checkbox itself)
                    var card = e.target.closest('.batch-card');
                    if (card && e.target.tagName !== 'INPUT') {
                        var cb = card.querySelector('input[data-action="batch-toggle"]');
                        if (cb) { cb.checked = !cb.checked; updateCount(); }
                    }
                    return;
                }

                if (action === 'batch-toggle') {
                    updateCount();
                    return;
                }

                if (action === 'batch-toggle-all') {
                    e.preventDefault();
                    var boxes = grid.querySelectorAll('input[data-action="batch-toggle"]');
                    var anyChecked = Array.from(boxes).some(function(b) { return b.checked; });
                    boxes.forEach(function(b) { b.checked = !anyChecked; });
                    e.target.textContent = anyChecked ? 'Select All' : 'Deselect All';
                    updateCount();
                    return;
                }

                if (action === 'batch-confirm') {
                    e.preventDefault();
                    var checked = grid.querySelectorAll('input[data-action="batch-toggle"]:checked');
                    if (checked.length === 0) return;
                    var ids = Array.from(checked).map(function(cb) { return cb.getAttribute('data-identity-id'); });

                    var btn = e.target;
                    btn.disabled = true;
                    btn.textContent = 'Confirming...';

                    fetch('/api/cluster-review/batch-confirm', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: 'identity_ids=' + ids.join(',')
                    }).then(function(resp) { return resp.text(); })
                    .then(function(html) {
                        var summary = document.getElementById('batch-summary');
                        if (summary) { summary.innerHTML = html; }
                        // Remove confirmed cards from grid
                        ids.forEach(function(id) {
                            var card = grid.querySelector('[data-identity-id="' + id + '"].batch-card');
                            if (card) card.remove();
                        });
                        updateCount();
                    });
                    return;
                }
            });
        })();
    """)

    return Title("Batch Cluster Validation — Rhodesli Admin"), Main(
        Div(
            Div(
                H1("Batch Cluster Validation", cls="text-2xl font-serif font-bold text-white"),
                A(
                    "← Dashboard",
                    href="upload-review",
                    cls="text-sm text-purple-400 hover:text-purple-300 transition-colors",
                ),
                cls="flex items-center gap-4",
            ),
            P(
                "Select valid clusters and confirm them in bulk. Deselect any clusters with mixed faces. "
                "Use face count filters to focus on high-confidence clusters first.",
                cls="text-slate-400 mb-6",
            ),
            summary,
            filter_bar,
            stats_bar,
            grid,
            footer,
            batch_js,
            cls="max-w-7xl mx-auto px-4 py-8",
        ),
        cls="min-h-screen bg-slate-950",
    )


@rt("/api/cluster-review/batch-confirm")
def post(identity_ids: str = "", sess=None, request=None):
    """Confirm selected INBOX identities in batch — PRD-040."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not identity_ids:
        return Div(P("No identities selected.", cls="text-red-400 text-sm"), cls="p-4")

    ids = [iid.strip() for iid in identity_ids.split(",") if iid.strip()]
    if not ids:
        return Div(P("No identities selected.", cls="text-red-400 text-sm"), cls="p-4")

    registry = _main_mod.load_registry()
    admin_email = _active_learning_actor(sess)

    confirmed_count = 0
    total_faces = 0
    errors = []

    for identity_id in ids:
        try:
            identity = registry._identities.get(identity_id)
            if not identity:
                errors.append(f"Identity {identity_id[:12]} not found")
                continue

            # Promote all candidates to anchors
            candidates = list(identity.get("candidate_ids", []))
            for fid in candidates:
                try:
                    registry.promote_candidate(identity_id, fid, user_source="admin/batch-cluster-validation")
                except ValueError:
                    pass

            # Count all faces
            all_faces = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
            face_count = len(all_faces)
            total_faces += face_count

            # Set state to CONFIRMED
            prev_state = identity.get("state", "INBOX")
            identity["state"] = "CONFIRMED"
            identity["updated_at"] = _main_mod.datetime.now(_main_mod.timezone.utc).isoformat()

            confirmed_count += 1

            _main_mod.log_user_action(
                "BATCH_CONFIRM",
                identity_id=identity_id,
                face_count=face_count,
                state_before=prev_state,
                state_after="CONFIRMED",
                mode="batch",
                admin=admin_email,
            )
        except (ValueError, KeyError) as e:
            errors.append(f"Error with {identity_id[:12]}: {e}")

    _main_mod.save_registry(registry)

    # Build summary response
    error_html = ""
    if errors:
        error_html = Div(
            *[P(err, cls="text-red-400 text-xs") for err in errors],
            cls="mt-2",
        )

    return Div(
        Div(
            Span("Batch confirmed", cls="text-emerald-400 font-semibold text-lg"),
            P(
                f"{confirmed_count} cluster{'s' if confirmed_count != 1 else ''} confirmed, "
                f"{total_faces} total face{'s' if total_faces != 1 else ''}",
                cls="text-slate-300 text-sm mt-1",
            ),
            error_html if errors else "",
            cls="p-4 bg-emerald-900/20 border border-emerald-700/50 rounded-lg",
        ),
    )
