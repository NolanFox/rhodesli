"""
Face grouping for clustering.

Two levels of grouping:
1. Ingestion-time: group_faces() clusters faces within a single upload batch
2. Post-ingestion: group_inbox_identities() clusters existing INBOX identities
   across all photos by comparing face embeddings pairwise
3. Global: group_all_unresolved() clusters ALL unresolved faces (INBOX + SKIPPED)
   with promotion tracking when SKIPPED faces gain new matches

Design principles:
- Conservative: Under-grouping is better than over-grouping
- Simple: Union-Find with pairwise Euclidean distance (no clustering libraries)
- Safety: Co-occurrence check prevents merging faces from the same photo
- Inclusive: SKIPPED means "deferred," not "excluded from ML forever"

See docs/adr_008_ingestion_grouping.md for design rationale.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from scipy.spatial.distance import cdist

from core.config import GROUPING_THRESHOLD

logger = logging.getLogger(__name__)


def group_faces(faces: list[dict]) -> list[list[dict]]:
    """
    Group faces by embedding similarity using union-find.

    Faces with Euclidean distance < GROUPING_THRESHOLD are grouped together.
    Grouping is transitive: if A~B and B~C, then A,B,C are in the same group.

    Args:
        faces: List of face dicts, each containing:
            - face_id: Unique identifier
            - mu: 512-dimensional embedding vector (np.ndarray)

    Returns:
        List of groups, where each group is a list of face dicts.
        Original face dicts are preserved (not copies).

    Example:
        >>> faces = [{"face_id": "f1", "mu": emb1}, {"face_id": "f2", "mu": emb2}]
        >>> groups = group_faces(faces)
        >>> # If emb1 and emb2 are similar: [[face1, face2]]
        >>> # If different: [[face1], [face2]]
    """
    n = len(faces)

    if n == 0:
        return []

    if n == 1:
        return [faces]

    # Extract embeddings into matrix for efficient distance computation
    embeddings = np.array([f["mu"] for f in faces])

    # Compute all pairwise Euclidean distances
    # distances[i][j] = distance between face i and face j
    distances = cdist(embeddings, embeddings, metric="euclidean")

    # Union-Find data structure for transitive grouping
    parent = list(range(n))

    def find(x: int) -> int:
        """Find root with path compression."""
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        """Union two sets."""
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Group faces below threshold
    for i in range(n):
        for j in range(i + 1, n):
            if distances[i][j] < GROUPING_THRESHOLD:
                union(i, j)

    # Collect groups by root
    groups_by_root: dict[int, list[dict]] = {}
    for i in range(n):
        root = find(i)
        if root not in groups_by_root:
            groups_by_root[root] = []
        groups_by_root[root].append(faces[i])

    return list(groups_by_root.values())


def group_inbox_identities(
    registry,
    face_data: dict,
    photo_registry,
    threshold: float = None,
    dry_run: bool = True,
) -> dict:
    """
    Group similar INBOX identities by comparing face embeddings pairwise.

    Compares ALL inbox single-identity faces against each other using
    best-linkage (min distance across all face pairs). Groups below
    threshold are merged using registry.merge_identities(), which
    handles co-occurrence validation and merge history.

    Args:
        registry: IdentityRegistry with loaded identities
        face_data: dict of face_id -> {"mu": embedding, "sigma_sq": ...}
        photo_registry: PhotoRegistry for co-occurrence checks during merge
        threshold: Distance threshold (default: GROUPING_THRESHOLD from config)
        dry_run: If True, only report what would be merged

    Returns:
        {
            "groups": [{"primary_id": str, "primary_name": str,
                        "member_ids": [str], "member_names": [str],
                        "size": int, "avg_distance": float}],
            "total_groups": int,
            "total_merged": int,
            "identities_before": int,
            "identities_after": int,
            "merge_results": list[dict],  # only in execute mode
            "skipped_co_occurrence": int,
        }
    """
    from core.registry import IdentityState

    if threshold is None:
        threshold = GROUPING_THRESHOLD

    # 1. Collect all INBOX identities (not merged) with their embeddings
    inbox_items = []
    for identity in registry.list_identities(state=IdentityState.INBOX, include_merged=False):
        iid = identity["identity_id"]
        face_ids = registry.get_all_face_ids(iid)
        if not face_ids:
            continue

        embeddings = []
        valid_fids = []
        for fid in face_ids:
            if fid in face_data:
                embeddings.append(face_data[fid]["mu"])
                valid_fids.append(fid)

        if not embeddings:
            continue

        inbox_items.append({
            "identity_id": iid,
            "name": identity.get("name", ""),
            "face_ids": valid_fids,
            "embeddings": np.vstack(embeddings),
        })

    n = len(inbox_items)
    identities_before = n

    if n < 2:
        return {
            "groups": [],
            "total_groups": 0,
            "total_merged": 0,
            "identities_before": identities_before,
            "identities_after": identities_before,
            "merge_results": [],
            "skipped_co_occurrence": 0,
        }

    # 2. Pairwise min-distances between identities (best linkage, AD-001)
    parent = list(range(n))
    pair_distances = {}  # (i, j) -> min_distance for reporting

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            dists = cdist(
                inbox_items[i]["embeddings"],
                inbox_items[j]["embeddings"],
                metric="euclidean",
            )
            min_dist = float(np.min(dists))
            if min_dist < threshold:
                pair_distances[(i, j)] = min_dist
                union(i, j)

    # 3. Collect groups
    groups_by_root = defaultdict(list)
    for i in range(n):
        root = find(i)
        groups_by_root[root].append(i)

    multi_groups = [indices for indices in groups_by_root.values() if len(indices) > 1]

    if not multi_groups:
        return {
            "groups": [],
            "total_groups": 0,
            "total_merged": 0,
            "identities_before": identities_before,
            "identities_after": identities_before,
            "merge_results": [],
            "skipped_co_occurrence": 0,
        }

    # 4. For each group, pick primary (most faces) and merge others into it
    results = {
        "groups": [],
        "total_groups": len(multi_groups),
        "total_merged": 0,
        "identities_before": identities_before,
        "identities_after": identities_before,
        "merge_results": [],
        "skipped_co_occurrence": 0,
    }

    for group_indices in multi_groups:
        # Sort by face count descending (most faces = primary)
        group_indices.sort(
            key=lambda i: len(inbox_items[i]["face_ids"]), reverse=True
        )

        primary_idx = group_indices[0]
        primary = inbox_items[primary_idx]

        # Compute average intra-group distance for reporting
        intra_dists = []
        for a in range(len(group_indices)):
            for b in range(a + 1, len(group_indices)):
                key = (min(group_indices[a], group_indices[b]),
                       max(group_indices[a], group_indices[b]))
                if key in pair_distances:
                    intra_dists.append(pair_distances[key])

        member_indices = group_indices[1:]
        group_info = {
            "primary_id": primary["identity_id"],
            "primary_name": primary["name"],
            "member_ids": [inbox_items[i]["identity_id"] for i in member_indices],
            "member_names": [inbox_items[i]["name"] for i in member_indices],
            "size": len(group_indices),
            "avg_distance": round(np.mean(intra_dists), 4) if intra_dists else 0.0,
        }
        results["groups"].append(group_info)

        if not dry_run:
            for other_idx in member_indices:
                other = inbox_items[other_idx]
                merge_result = registry.merge_identities(
                    source_id=other["identity_id"],
                    target_id=primary["identity_id"],
                    user_source="batch_grouping",
                    photo_registry=photo_registry,
                    auto_correct_direction=False,  # We already picked the primary
                )
                results["merge_results"].append(merge_result)
                if merge_result.get("success"):
                    results["total_merged"] += 1
                elif merge_result.get("reason") == "co_occurrence":
                    results["skipped_co_occurrence"] += 1
                    logger.info(
                        "Skipped merge %s -> %s: co-occurrence (same photo)",
                        other["identity_id"][:8],
                        primary["identity_id"][:8],
                    )

    results["identities_after"] = identities_before - results["total_merged"]
    return results


def group_all_unresolved(
    registry,
    face_data: dict,
    photo_registry,
    threshold: float = None,
    include_skipped: bool = True,
    dry_run: bool = True,
) -> dict:
    """
    Group ALL unresolved identities (INBOX + SKIPPED) by embedding similarity.

    Like group_inbox_identities() but also includes SKIPPED faces. When a SKIPPED
    face matches an INBOX face (or another SKIPPED face), it is promoted back to
    INBOX with tracking fields so the UI can highlight it as "rediscovered."

    SKIPPED means "I can't identify this right now" — not "exclude from ML forever."
    Every major photo system (Apple Photos, Google Photos, Immich) continuously
    re-evaluates all unresolved faces as new data arrives.

    Args:
        registry: IdentityRegistry with loaded identities
        face_data: dict of face_id -> {"mu": embedding, "sigma_sq": ...}
        photo_registry: PhotoRegistry for co-occurrence checks during merge
        threshold: Distance threshold (default: GROUPING_THRESHOLD from config)
        include_skipped: If True (default), include SKIPPED faces in grouping
        dry_run: If True, only report what would be merged

    Returns:
        {
            "groups": [...],  # same format as group_inbox_identities
            "total_groups": int,
            "total_merged": int,
            "identities_before": int,
            "identities_after": int,
            "merge_results": list[dict],
            "skipped_co_occurrence": int,
            "inbox_count": int,
            "skipped_count": int,
            "promotions": [{"identity_id": str, "name": str, "reason": str}],
        }
    """
    from core.registry import IdentityState

    if threshold is None:
        threshold = GROUPING_THRESHOLD

    # 1. Collect unresolved identities with their embeddings and original state
    items = []
    inbox_count = 0
    skipped_count = 0

    states_to_include = [IdentityState.INBOX]
    if include_skipped:
        states_to_include.append(IdentityState.SKIPPED)

    for state in states_to_include:
        for identity in registry.list_identities(state=state, include_merged=False):
            iid = identity["identity_id"]
            face_ids = registry.get_all_face_ids(iid)
            if not face_ids:
                continue

            # Collect negative_ids for co-occurrence block checking
            negative_ids = set(identity.get("negative_ids", []))

            embeddings = []
            valid_fids = []
            for fid in face_ids:
                if fid in face_data:
                    embeddings.append(face_data[fid]["mu"])
                    valid_fids.append(fid)

            if not embeddings:
                continue

            original_state = identity.get("state", "INBOX")
            if original_state == "INBOX":
                inbox_count += 1
            elif original_state == "SKIPPED":
                skipped_count += 1

            items.append({
                "identity_id": iid,
                "name": identity.get("name", ""),
                "face_ids": valid_fids,
                "embeddings": np.vstack(embeddings),
                "original_state": original_state,
                "negative_ids": negative_ids,
            })

    n = len(items)
    identities_before = n

    empty_result = {
        "groups": [],
        "total_groups": 0,
        "total_merged": 0,
        "identities_before": identities_before,
        "identities_after": identities_before,
        "merge_results": [],
        "skipped_co_occurrence": 0,
        "inbox_count": inbox_count,
        "skipped_count": skipped_count,
        "promotions": [],
    }

    if n < 2:
        return empty_result

    # 2. Pairwise min-distances with co-occurrence block checking
    parent = list(range(n))
    pair_distances = {}

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            # Check co-occurrence blocks (negative_ids with identity: prefix)
            iid_i = items[i]["identity_id"]
            iid_j = items[j]["identity_id"]
            if f"identity:{iid_j}" in items[i]["negative_ids"]:
                continue
            if f"identity:{iid_i}" in items[j]["negative_ids"]:
                continue

            dists = cdist(
                items[i]["embeddings"],
                items[j]["embeddings"],
                metric="euclidean",
            )
            min_dist = float(np.min(dists))
            if min_dist < threshold:
                pair_distances[(i, j)] = min_dist
                union(i, j)

    # 3. Collect groups
    groups_by_root = defaultdict(list)
    for i in range(n):
        root = find(i)
        groups_by_root[root].append(i)

    multi_groups = [indices for indices in groups_by_root.values() if len(indices) > 1]

    if not multi_groups:
        return empty_result

    # 4. For each group, determine promotions and merge
    results = {
        "groups": [],
        "total_groups": len(multi_groups),
        "total_merged": 0,
        "identities_before": identities_before,
        "identities_after": identities_before,
        "merge_results": [],
        "skipped_co_occurrence": 0,
        "inbox_count": inbox_count,
        "skipped_count": skipped_count,
        "promotions": [],
    }

    now = datetime.now(timezone.utc).isoformat()

    for group_indices in multi_groups:
        # Sort by face count descending (most faces = primary)
        group_indices.sort(
            key=lambda i: len(items[i]["face_ids"]), reverse=True
        )

        primary_idx = group_indices[0]
        primary = items[primary_idx]

        # Determine member states for promotion logic
        member_states = {items[i]["original_state"] for i in group_indices}
        has_inbox = "INBOX" in member_states
        all_skipped = member_states == {"SKIPPED"}

        # Track promotions: SKIPPED faces that get grouped
        for idx in group_indices:
            item = items[idx]
            if item["original_state"] == "SKIPPED":
                if has_inbox:
                    reason = "new_face_match"
                elif all_skipped:
                    reason = "group_discovery"
                else:
                    reason = "group_discovery"

                results["promotions"].append({
                    "identity_id": item["identity_id"],
                    "name": item["name"],
                    "reason": reason,
                })

        # Compute average intra-group distance
        intra_dists = []
        for a in range(len(group_indices)):
            for b in range(a + 1, len(group_indices)):
                key = (min(group_indices[a], group_indices[b]),
                       max(group_indices[a], group_indices[b]))
                if key in pair_distances:
                    intra_dists.append(pair_distances[key])

        member_indices = group_indices[1:]
        group_info = {
            "primary_id": primary["identity_id"],
            "primary_name": primary["name"],
            "member_ids": [items[i]["identity_id"] for i in member_indices],
            "member_names": [items[i]["name"] for i in member_indices],
            "size": len(group_indices),
            "avg_distance": round(np.mean(intra_dists), 4) if intra_dists else 0.0,
            "member_states": [items[i]["original_state"] for i in group_indices],
        }
        results["groups"].append(group_info)

        if not dry_run:
            # Build context strings for promotion banners
            group_names = [items[i]["name"] for i in group_indices]

            # Before merging, promote SKIPPED members to INBOX
            for idx in group_indices:
                item = items[idx]
                if item["original_state"] == "SKIPPED":
                    identity = registry._identities.get(item["identity_id"])
                    if identity:
                        identity["state"] = "INBOX"
                        identity["promoted_from"] = "SKIPPED"
                        identity["promoted_at"] = now
                        # Build context from the OTHER members in the group
                        other_names = [n for n in group_names if n != item["name"]]
                        others_str = ", ".join(other_names[:3])
                        if has_inbox:
                            identity["promotion_reason"] = "new_face_match"
                            identity["promotion_context"] = f"Matches with {others_str} from recently uploaded photos"
                        else:
                            identity["promotion_reason"] = "group_discovery"
                            identity["promotion_context"] = f"Groups with {others_str} — previously unidentified faces that appear to be the same person"

            # Now merge members into primary
            for other_idx in member_indices:
                other = items[other_idx]
                merge_result = registry.merge_identities(
                    source_id=other["identity_id"],
                    target_id=primary["identity_id"],
                    user_source="batch_grouping",
                    photo_registry=photo_registry,
                    auto_correct_direction=False,
                )
                results["merge_results"].append(merge_result)
                if merge_result.get("success"):
                    results["total_merged"] += 1
                elif merge_result.get("reason") == "co_occurrence":
                    results["skipped_co_occurrence"] += 1
                    logger.info(
                        "Skipped merge %s -> %s: co-occurrence (same photo)",
                        other["identity_id"][:8],
                        primary["identity_id"][:8],
                    )

            # Transfer promotion fields to the primary if it was SKIPPED
            primary_identity = registry._identities.get(primary["identity_id"])
            if primary_identity and primary["original_state"] == "SKIPPED":
                other_names = [items[i]["name"] for i in member_indices]
                others_str = ", ".join(other_names[:3])
                primary_identity["promoted_from"] = "SKIPPED"
                primary_identity["promoted_at"] = now
                if has_inbox:
                    primary_identity["promotion_reason"] = "new_face_match"
                    primary_identity["promotion_context"] = f"Matches with {others_str} from recently uploaded photos"
                else:
                    primary_identity["promotion_reason"] = "group_discovery"
                    primary_identity["promotion_context"] = f"Groups with {others_str} — previously unidentified faces that appear to be the same person"

    results["identities_after"] = identities_before - results["total_merged"]
    return results
