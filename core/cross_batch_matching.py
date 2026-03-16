"""
Cross-batch matching for PRD-049.

Compares new face IDs against ALL existing identities (INBOX, PROPOSED,
CONFIRMED, SKIPPED) to surface matches across upload batches.

Unlike find_candidate_matches() which only matches against CONFIRMED,
this matches against everything for comprehensive coverage.

All cross-batch matches are proposals — no auto-merge.

See: docs/prds/049_cross_batch_clustering.md, AD-226
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from core.config import (
    MATCH_THRESHOLD_HIGH,
    MATCH_THRESHOLD_VERY_HIGH,
)
from core.identity_scoring import (
    build_identity_embedding_index,
    collect_identity_embeddings,
    compute_min_distance,
    extract_face_ids,
    get_photo_id,
)

if TYPE_CHECKING:
    from core.photo_registry import PhotoRegistry

logger = logging.getLogger(__name__)

# Cross-batch threshold: proposals only, no auto-merge.
# 1.05 catches ~55% of same-person pairs with moderate false positives.
# All results require human review. See AD-226.
CROSS_BATCH_THRESHOLD = 1.05


def _get_confidence_tier(distance: float) -> str:
    """Assign confidence tier based on distance."""
    if distance < MATCH_THRESHOLD_VERY_HIGH:
        return "very_high"
    elif distance < MATCH_THRESHOLD_HIGH:
        return "high"
    else:
        return "moderate"


def find_cross_batch_matches(
    new_face_ids: list[str],
    identities: dict,
    face_data: dict,
    photo_registry: PhotoRegistry,
    threshold: float = CROSS_BATCH_THRESHOLD,
    community_id: str | None = None,
) -> list[dict]:
    """
    Compare new faces against ALL existing identities.

    Args:
        new_face_ids: Face IDs from a recent upload to match.
        identities: Full identities data dict (with "identities" key).
        face_data: Dict of face_id -> {"mu": embedding, ...}.
        photo_registry: For co-occurrence checks.
        threshold: Max distance for proposals (default 1.05).
        community_id: If set, only match against identities in this community.

    Returns:
        List of match dicts sorted by distance, each containing:
        - source_face_id, source_identity_id, target_identity_id
        - distance, confidence_tier, match_type
    """
    if not new_face_ids:
        return []

    all_identities = identities.get("identities", {})
    if not all_identities:
        return []

    # Build index of ALL non-merged identities (not just CONFIRMED)
    identity_index = build_identity_embedding_index(
        identities,
        face_data,
        states=("CONFIRMED", "PROPOSED", "INBOX", "SKIPPED"),
    )
    if not identity_index:
        return []

    # Resolve which identities the new faces belong to, so we can skip self-matches
    new_face_identity_map = {}
    for iid, identity in all_identities.items():
        if identity.get("merged_into"):
            continue
        for fid in extract_face_ids(identity):
            if fid in new_face_ids:
                new_face_identity_map[fid] = iid

    # Community filtering: build set of identity IDs in this community
    community_identity_ids = None
    if community_id:
        community_identity_ids = set()
        for iid, identity in all_identities.items():
            if identity.get("merged_into"):
                continue
            identity_communities = identity.get("identity_communities", [])
            if community_id in identity_communities:
                community_identity_ids.add(iid)

    # Build face-to-photo map for co-occurrence checks
    face_to_photo = {}
    if photo_registry:
        face_to_photo = getattr(photo_registry, "face_to_photo", {})
        if not face_to_photo:
            face_to_photo = getattr(photo_registry, "_face_to_photo", {})

    matches = []
    seen_pairs = set()  # (source_identity_id, target_identity_id) dedup

    for face_id in new_face_ids:
        face = face_data.get(face_id)
        if face is None or face.get("mu") is None:
            continue

        source_identity_id = new_face_identity_map.get(face_id)
        if not source_identity_id:
            continue

        # Get photo IDs for the source face (for co-occurrence check)
        source_photo_id = get_photo_id(face_id)
        if not source_photo_id and face_to_photo:
            source_photo_id = face_to_photo.get(face_id)

        face_embedding = np.asarray(face["mu"], dtype=np.float32).reshape(1, -1)

        for target_iid, target_info in identity_index.items():
            # Skip self
            if target_iid == source_identity_id:
                continue

            # Community filter
            if community_identity_ids is not None:
                if target_iid not in community_identity_ids:
                    continue

            # Deduplicate: only keep best match per identity pair
            pair_key = tuple(sorted([source_identity_id, target_iid]))
            if pair_key in seen_pairs:
                continue

            # Co-occurrence check: skip if any target face shares a photo with source
            if source_photo_id:
                target_photo_ids = target_info.get("photo_ids", set())
                if source_photo_id in target_photo_ids:
                    continue
                # Also check via face_to_photo map (for inbox-style face IDs
                # where get_photo_id returns None)
                if face_to_photo:
                    for tfid in target_info.get("face_ids", []):
                        if face_to_photo.get(tfid) == source_photo_id:
                            target_photo_ids = None  # signal to skip
                            break
                    if target_photo_ids is None:
                        continue

            distance = compute_min_distance(face_embedding, target_info["embeddings"])
            if distance >= threshold:
                continue

            seen_pairs.add(pair_key)

            # Determine match type
            target_identity = all_identities.get(target_iid, {})
            target_state = target_identity.get("state", "INBOX")
            if target_state == "CONFIRMED":
                match_type = "cross_batch_vs_confirmed"
            else:
                match_type = "cross_batch_vs_inbox"

            matches.append(
                {
                    "source_face_id": face_id,
                    "source_identity_id": source_identity_id,
                    "source_identity_name": all_identities.get(source_identity_id, {}).get(
                        "name", f"Unknown ({source_identity_id[:8]})"
                    ),
                    "target_identity_id": target_iid,
                    "target_identity_name": target_info.get("name", f"Unknown ({target_iid[:8]})"),
                    "target_state": target_state,
                    "distance": round(distance, 6),
                    "confidence_tier": _get_confidence_tier(distance),
                    "match_type": match_type,
                }
            )

    matches.sort(key=lambda m: m["distance"])
    return matches
