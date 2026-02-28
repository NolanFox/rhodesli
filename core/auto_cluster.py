"""
Two-tier auto-clustering for the Rhodesli upload pipeline.

Tier 1 (distance < 0.85): Auto-add face to confirmed cluster as candidate_id.
Tier 2 (0.85 <= distance < 1.10): Surface as Discovery suggestion for admin review.

Every action is logged to data/discovery_log.json for ML signal collection.
Threshold values validated against 982 same-person pairs:
    mean=1.01, std=0.19, p5=0.70, p25=0.88

Design principles:
- NEVER modifies anchor_ids — auto-clustered faces go to candidate_ids
- provenance="model" on all auto-clustered faces
- Dedup pass removes exact face_id duplicates (inbox identity whose face
  already lives in a confirmed identity)
- All actions logged for threshold recalibration

See: AD-179 (Two-Tier Auto-Clustering at Upload Time)
"""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist

# Thresholds (AD-179)
TIER_1_THRESHOLD = 0.85  # Auto-add: well below p25=0.88 of same-person pairs
TIER_2_THRESHOLD = 1.10  # Suggest: covers bulk of same-person distribution

_log_lock = threading.Lock()


def auto_cluster_face(face_id, face_mu, confirmed_clusters, face_data):
    """
    Classify a face against confirmed identities using best-linkage distance.

    Args:
        face_id: The face identifier string
        face_mu: numpy array, 512-dim embedding (mu vector)
        confirmed_clusters: dict of {identity_id: {
            "name": str,
            "embeddings": np.ndarray (N x 512),
            "face_ids": list[str],
        }}
        face_data: dict of {face_id: {"mu": array}} — used for co-occurrence checks

    Returns:
        tuple: (tier, target_identity_id, distance)
            tier: "tier_1" | "tier_2" | "no_match"
            target_identity_id: UUID string or None
            distance: float or None
    """
    if face_mu is None or len(confirmed_clusters) == 0:
        return ("no_match", None, None)

    query = np.asarray(face_mu, dtype=np.float32).reshape(1, -1)

    best_distance = float("inf")
    best_identity_id = None

    for identity_id, cluster_info in confirmed_clusters.items():
        embs = cluster_info["embeddings"]
        if embs is None or embs.size == 0:
            continue

        # Best-linkage: min distance to any face in the cluster (AD-001)
        dists = cdist(query, embs, metric="euclidean")
        min_dist = float(np.min(dists))

        if min_dist < best_distance:
            best_distance = min_dist
            best_identity_id = identity_id

    if best_identity_id is None:
        return ("no_match", None, None)

    if best_distance < TIER_1_THRESHOLD:
        return ("tier_1", best_identity_id, best_distance)
    elif best_distance < TIER_2_THRESHOLD:
        return ("tier_2", best_identity_id, best_distance)
    else:
        return ("no_match", None, None)


def log_discovery(entry: dict, log_path="data/discovery_log.json"):
    """Append an entry to the discovery log (thread-safe).

    Creates the log file if it doesn't exist. The log schema is:
    {
        "schema_version": 1,
        "entries": [...]
    }
    """
    with _log_lock:
        log_file = Path(log_path)
        if log_file.exists():
            with open(log_file) as f:
                data = json.load(f)
        else:
            data = {"schema_version": 1, "entries": []}

        data["entries"].append(entry)

        # Atomic write
        tmp_path = str(log_file) + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(log_file))


def _extract_face_ids(identity):
    """Extract all face IDs from an identity (anchors + candidates).

    Handles both string and dict anchor formats.
    """
    face_ids = []
    for anchor in identity.get("anchor_ids", []):
        if isinstance(anchor, str):
            face_ids.append(anchor)
        elif isinstance(anchor, dict):
            face_ids.append(anchor["face_id"])
    face_ids.extend(identity.get("candidate_ids", []))
    return face_ids


def dedup_inbox(identities_data, dry_run=True):
    """
    Find and remove inbox identities whose faces are already in confirmed clusters.

    An inbox identity is a duplicate if ALL of its face_ids also appear
    in a confirmed identity's anchor_ids or candidate_ids.

    Args:
        identities_data: The full identities.json data dict
        dry_run: If True, only report; if False, mark duplicates as merged

    Returns:
        list of (inbox_identity_id, confirmed_identity_id, shared_face_ids)
    """
    identities = identities_data.get("identities", {})

    # Build confirmed face lookup: face_id -> confirmed identity_id
    confirmed_face_lookup = {}
    for identity_id, identity in identities.items():
        if identity.get("state") != "CONFIRMED":
            continue
        if identity.get("merged_into"):
            continue
        for fid in _extract_face_ids(identity):
            confirmed_face_lookup[fid] = identity_id

    # Find inbox duplicates
    duplicates = []
    for identity_id, identity in list(identities.items()):
        if identity.get("state") not in ("INBOX", "PROPOSED", "SKIPPED"):
            continue
        if identity.get("merged_into"):
            continue

        face_ids = _extract_face_ids(identity)
        if not face_ids:
            continue

        # Check which faces are already in confirmed identities
        shared = []
        confirmed_targets = set()
        for fid in face_ids:
            if fid in confirmed_face_lookup:
                shared.append(fid)
                confirmed_targets.add(confirmed_face_lookup[fid])

        # Only dedup if ALL faces are already in confirmed clusters
        if shared and len(shared) == len(face_ids) and len(confirmed_targets) == 1:
            target_id = confirmed_targets.pop()
            duplicates.append((identity_id, target_id, shared))

            if not dry_run:
                now = datetime.now(timezone.utc).isoformat()
                identity["merged_into"] = target_id
                identity["version_id"] = identity.get("version_id", 1) + 1
                identity["updated_at"] = now

    return duplicates


def build_confirmed_clusters(identities_data, face_data):
    """
    Build the confirmed cluster lookup from identities and face embeddings.

    Returns:
        dict of {identity_id: {
            "name": str,
            "embeddings": np.ndarray,
            "face_ids": list[str],
        }}
    """
    identities = identities_data.get("identities", {})
    clusters = {}

    for identity_id, identity in identities.items():
        if identity.get("state") != "CONFIRMED":
            continue
        if identity.get("merged_into"):
            continue

        face_ids = _extract_face_ids(identity)
        if not face_ids:
            continue

        embeddings = []
        valid_fids = []
        for fid in face_ids:
            if fid in face_data and "mu" in face_data[fid]:
                embeddings.append(face_data[fid]["mu"])
                valid_fids.append(fid)

        if not embeddings:
            continue

        clusters[identity_id] = {
            "name": identity.get("name", f"Unknown ({identity_id[:8]})"),
            "embeddings": np.vstack(embeddings),
            "face_ids": valid_fids,
        }

    return clusters


def run_backfill(identities_data, face_data, log_path="data/discovery_log.json",
                 dry_run=True):
    """
    Run auto-clustering on all current inbox/unresolved faces.

    1. First pass: dedup (remove exact duplicates)
    2. Second pass: distance-based Tier 1/Tier 2 classification

    Args:
        identities_data: The full identities.json data dict
        face_data: dict of {face_id: {"mu": array, ...}}
        log_path: Path for discovery log output
        dry_run: If True, only report; if False, apply changes

    Returns:
        dict with keys:
            - dedup_results: list of (inbox_id, confirmed_id, shared_faces)
            - tier_1_results: list of dicts
            - tier_2_results: list of dicts
            - no_match_count: int
            - total_processed: int
    """
    identities = identities_data.get("identities", {})
    now = datetime.now(timezone.utc).isoformat()

    # Pass 1: Dedup
    dedup_results = dedup_inbox(identities_data, dry_run=dry_run)

    # Log dedup results
    for inbox_id, confirmed_id, shared_faces in dedup_results:
        inbox_identity = identities.get(inbox_id, {})
        confirmed_identity = identities.get(confirmed_id, {})
        log_discovery({
            "face_id": shared_faces[0] if shared_faces else "unknown",
            "source_identity_id": inbox_id,
            "source_identity_name": inbox_identity.get("name", "Unknown"),
            "target_identity_id": confirmed_id,
            "target_identity_name": confirmed_identity.get("name", "Unknown"),
            "distance": 0.0,
            "tier": 0,
            "action": "dedup",
            "timestamp": now,
            "user_decision": None,
            "user_decision_timestamp": None,
        }, log_path=log_path)

    # Pass 2: Distance-based clustering
    # Build confirmed clusters (after dedup)
    confirmed_clusters = build_confirmed_clusters(identities_data, face_data)

    if not confirmed_clusters:
        return {
            "dedup_results": dedup_results,
            "tier_1_results": [],
            "tier_2_results": [],
            "no_match_count": 0,
            "total_processed": 0,
        }

    tier_1_results = []
    tier_2_results = []
    no_match_count = 0
    total_processed = 0

    # Process all unresolved identities
    unresolved_states = {"INBOX", "PROPOSED", "SKIPPED"}
    for identity_id, identity in list(identities.items()):
        if identity.get("state") not in unresolved_states:
            continue
        if identity.get("merged_into"):
            continue

        face_ids = _extract_face_ids(identity)
        if not face_ids:
            continue

        for fid in face_ids:
            if fid not in face_data:
                continue
            if "mu" not in face_data[fid]:
                continue

            total_processed += 1
            face_mu = face_data[fid]["mu"]

            tier, target_id, distance = auto_cluster_face(
                fid, face_mu, confirmed_clusters, face_data
            )

            if tier == "tier_1":
                target_identity = identities.get(target_id, {})
                result = {
                    "face_id": fid,
                    "source_identity_id": identity_id,
                    "source_identity_name": identity.get("name", "Unknown"),
                    "target_identity_id": target_id,
                    "target_identity_name": target_identity.get("name", "Unknown"),
                    "distance": distance,
                }
                tier_1_results.append(result)

                # Apply: add face as candidate on confirmed identity
                if not dry_run and target_id in identities:
                    target = identities[target_id]
                    if fid not in target.get("candidate_ids", []):
                        if "candidate_ids" not in target:
                            target["candidate_ids"] = []
                        target["candidate_ids"].append(fid)
                        target["version_id"] = target.get("version_id", 1) + 1
                        target["updated_at"] = now

                # Log discovery
                log_discovery({
                    "face_id": fid,
                    "source_identity_id": identity_id,
                    "source_identity_name": identity.get("name", "Unknown"),
                    "target_identity_id": target_id,
                    "target_identity_name": target_identity.get("name", "Unknown"),
                    "distance": round(distance, 4),
                    "tier": 1,
                    "action": "auto_clustered",
                    "timestamp": now,
                    "user_decision": None,
                    "user_decision_timestamp": None,
                }, log_path=log_path)

            elif tier == "tier_2":
                target_identity = identities.get(target_id, {})
                result = {
                    "face_id": fid,
                    "source_identity_id": identity_id,
                    "source_identity_name": identity.get("name", "Unknown"),
                    "target_identity_id": target_id,
                    "target_identity_name": target_identity.get("name", "Unknown"),
                    "distance": distance,
                }
                tier_2_results.append(result)

                # Log discovery
                log_discovery({
                    "face_id": fid,
                    "source_identity_id": identity_id,
                    "source_identity_name": identity.get("name", "Unknown"),
                    "target_identity_id": target_id,
                    "target_identity_name": target_identity.get("name", "Unknown"),
                    "distance": round(distance, 4),
                    "tier": 2,
                    "action": "suggested",
                    "timestamp": now,
                    "user_decision": None,
                    "user_decision_timestamp": None,
                }, log_path=log_path)

            else:
                no_match_count += 1

    return {
        "dedup_results": dedup_results,
        "tier_1_results": tier_1_results,
        "tier_2_results": tier_2_results,
        "no_match_count": no_match_count,
        "total_processed": total_processed,
    }
