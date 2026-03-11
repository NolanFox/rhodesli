"""Shared offline scoring helpers for identity matching."""

from __future__ import annotations

from typing import Iterable

import numpy as np
from scipy.spatial.distance import cdist


def extract_face_ids(identity: dict) -> list[str]:
    """Extract all face IDs from an identity (anchors + candidates)."""
    face_ids = []

    for anchor in identity.get("anchor_ids", []):
        if isinstance(anchor, str):
            face_ids.append(anchor)
        elif isinstance(anchor, dict) and anchor.get("face_id"):
            face_ids.append(anchor["face_id"])

    face_ids.extend(identity.get("candidate_ids", []))
    return face_ids


def get_photo_id(face_id: str) -> str | None:
    """Extract photo identifier from face_id (everything before `:faceN`)."""
    if ":" in face_id:
        return face_id.rsplit(":", 1)[0]
    return None


def collect_identity_embeddings(face_ids: list[str], face_data: dict) -> tuple[np.ndarray | None, list[str]]:
    """Collect valid embeddings for one identity without averaging anchors."""
    embeddings = []
    valid_fids = []
    for fid in face_ids:
        face = face_data.get(fid)
        if face is None or face.get("mu") is None:
            continue
        embeddings.append(np.asarray(face["mu"], dtype=np.float32))
        valid_fids.append(fid)

    if not embeddings:
        return None, []

    return np.vstack(embeddings), valid_fids


def compute_min_distance(face_embedding, identity_embeddings) -> float:
    """Compute best-linkage Euclidean distance from one face to one identity."""
    face_matrix = np.asarray(face_embedding, dtype=np.float32).reshape(1, -1)
    dists = cdist(face_matrix, identity_embeddings, metric="euclidean")
    return float(np.min(dists))


def score_identity_distances(
    face_embedding,
    identity_index: dict[str, dict],
    *,
    excluded_identity_ids: set[str] | None = None,
    excluded_photo_ids: set[str] | None = None,
) -> list[dict]:
    """Return all candidate identity distances for one face, sorted best-first."""
    excluded_identity_ids = excluded_identity_ids or set()
    excluded_photo_ids = excluded_photo_ids or set()

    candidates = []
    for identity_id, identity_info in identity_index.items():
        if identity_id in excluded_identity_ids:
            continue
        if excluded_photo_ids and excluded_photo_ids.intersection(identity_info.get("photo_ids", set())):
            continue

        distance = compute_min_distance(face_embedding, identity_info["embeddings"])
        candidates.append(
            {
                "identity_id": identity_id,
                "distance": distance,
                "name": identity_info.get("name", f"Unknown ({identity_id[:8]})"),
                "face_count": identity_info.get("face_count", len(identity_info.get("face_ids", []))),
                "photo_ids": identity_info.get("photo_ids", set()),
            }
        )

    candidates.sort(key=lambda candidate: candidate["distance"])
    for index, candidate in enumerate(candidates, start=1):
        candidate["baseline_rank"] = index
    return candidates


def build_identity_embedding_index(
    identities_data: dict,
    face_data: dict,
    *,
    states: Iterable[str] = ("CONFIRMED",),
) -> dict[str, dict]:
    """Build a reusable identity -> embedding index for offline scorers."""
    identities = identities_data.get("identities", {})
    allowed_states = set(states)
    index = {}

    for identity_id, identity in identities.items():
        if identity.get("state") not in allowed_states:
            continue
        if identity.get("merged_into"):
            continue

        face_ids = extract_face_ids(identity)
        if not face_ids:
            continue

        emb_matrix, valid_fids = collect_identity_embeddings(face_ids, face_data)
        if emb_matrix is None:
            continue

        photo_ids = {
            photo_id
            for fid in valid_fids
            for photo_id in [get_photo_id(fid)]
            if photo_id
        }

        index[identity_id] = {
            "name": identity.get("name", f"Unknown ({identity_id[:8]})"),
            "embeddings": emb_matrix,
            "face_ids": valid_fids,
            "face_count": len(valid_fids),
            "photo_ids": photo_ids,
        }

    return index


def score_best_identity_match(
    face_embedding,
    identity_index: dict[str, dict],
    *,
    excluded_identity_ids: set[str] | None = None,
    excluded_photo_ids: set[str] | None = None,
) -> dict:
    """Return the best and second-best identity distances for one face."""
    candidates = score_identity_distances(
        face_embedding,
        identity_index,
        excluded_identity_ids=excluded_identity_ids,
        excluded_photo_ids=excluded_photo_ids,
    )
    best = candidates[0] if candidates else None
    second = candidates[1] if len(candidates) > 1 else None

    return {
        "best_match": best["identity_id"] if best else None,
        "best_distance": best["distance"] if best else float("inf"),
        "second_best_distance": second["distance"] if second else float("inf"),
        "ranked_candidates": candidates,
    }


def find_candidate_matches(
    identities_data: dict,
    face_data: dict,
    threshold: float,
    *,
    unresolved_states: Iterable[str] = ("INBOX", "PROPOSED", "SKIPPED"),
    ambiguous_margin_threshold: float = 0.15,
    reranker=None,
    reranker_top_k: int = 5,
) -> list[dict]:
    """Find best-linkage candidate matches for unresolved identities."""
    identities = identities_data.get("identities", {})
    confirmed_index = build_identity_embedding_index(identities_data, face_data, states=("CONFIRMED",))
    if not confirmed_index:
        return []

    suggestions = []
    unresolved_state_set = set(unresolved_states)

    for identity_id, identity in identities.items():
        if identity.get("state") not in unresolved_state_set:
            continue
        if identity.get("merged_into"):
            continue

        face_ids = extract_face_ids(identity)
        if not face_ids:
            continue

        source_negative_ids = set(identity.get("negative_ids", []))
        source_photo_ids = {
            photo_id
            for fid in face_ids
            for photo_id in [get_photo_id(fid)]
            if photo_id
        }

        for face_id in face_ids:
            face = face_data.get(face_id)
            if face is None or face.get("mu") is None:
                continue

            score = score_best_identity_match(
                face["mu"],
                confirmed_index,
                excluded_identity_ids={
                    negative.split(":", 1)[1]
                    for negative in source_negative_ids
                    if negative.startswith("identity:")
                },
                excluded_photo_ids=source_photo_ids,
            )
            ranked_candidates = score["ranked_candidates"]

            if reranker is not None and ranked_candidates:
                shortlist = ranked_candidates[:reranker_top_k]
                reranked_candidates = reranker.rerank(
                    face_id,
                    face,
                    shortlist,
                    confirmed_index,
                    source_identity=identity,
                )
            else:
                reranked_candidates = ranked_candidates

            best_candidate = reranked_candidates[0] if reranked_candidates else None
            second_candidate = reranked_candidates[1] if len(reranked_candidates) > 1 else None
            best_match = best_candidate["identity_id"] if best_candidate else None
            best_distance = best_candidate["distance"] if best_candidate else float("inf")
            second_best_distance = second_candidate["distance"] if second_candidate else float("inf")

            if best_match is None or best_distance >= threshold:
                continue

            margin = (
                (second_best_distance - best_distance) / best_distance
                if np.isfinite(second_best_distance) and best_distance > 0
                else float("inf")
            )
            suggestions.append(
                {
                    "face_id": face_id,
                    "source_identity_id": identity_id,
                    "source_identity_name": identity.get("name", f"Unknown ({identity_id[:8]})"),
                    "source_state": identity.get("state", "INBOX"),
                    "target_identity_id": best_match,
                    "target_identity_name": confirmed_index[best_match]["name"],
                    "distance": best_distance,
                    "target_face_count": confirmed_index[best_match]["face_count"],
                    "baseline_rank": best_candidate.get("baseline_rank", 1),
                    "reranker_score": best_candidate.get("reranker_score"),
                    "scorer_variant": best_candidate.get("scorer_variant", "baseline"),
                    "margin": round(margin, 3),
                    "ambiguous": margin < ambiguous_margin_threshold and second_best_distance < threshold,
                }
            )

    suggestions.sort(key=lambda suggestion: suggestion["distance"])
    return suggestions
