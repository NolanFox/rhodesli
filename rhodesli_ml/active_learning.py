"""Active-learning queue, label persistence, and review helpers.

This module keeps heavy queue construction offline while making review labels
replayable through the same lineage model used by recalibration.
"""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from core.auto_cluster import TIER_1_THRESHOLD, TIER_2_THRESHOLD
from core.config import DATA_DIR
from core.embeddings_io import load_face_data
from core.identity_scoring import (
    build_identity_embedding_index,
    extract_face_ids,
    get_photo_id,
    score_identity_distances,
)
from rhodesli_ml.calibration_lineage import (
    LABEL_TYPE_EXPLICIT_NEGATIVE,
    LABEL_TYPE_EXPLICIT_POSITIVE,
    build_calibration_pair_row,
    normalize_pair_row,
    pair_key,
    record_calibration_pair,
    record_pair_state_event,
    revert_calibration_pair,
    utcnow_iso,
)

logger = logging.getLogger(__name__)

ACTIVE_LEARNING_LABEL_SCHEMA_VERSION = 1
ACTIVE_LEARNING_QUEUE_SCHEMA_VERSION = 1
DEFAULT_LABELS_FILENAME = "active_learning_labels.json"
DEFAULT_QUEUE_FILENAME = "active_learning_queue.json"

# Legacy uncertain-pair defaults preserved for Session 92 coverage.
UNCERTAIN_LOW = 0.4
UNCERTAIN_HIGH = 0.6


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def resolve_git_commit() -> str | None:
    """Return the current git commit when available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def default_labels_path(data_dir: str | Path | None = None) -> Path:
    """Return the default current-state cache for active-learning labels."""
    base = Path(data_dir or DATA_DIR)
    return base / DEFAULT_LABELS_FILENAME


def default_queue_path(data_dir: str | Path | None = None) -> Path:
    """Return the default offline queue artifact path."""
    base = Path(data_dir or DATA_DIR)
    return base / DEFAULT_QUEUE_FILENAME


def load_active_learning_labels(path: str | Path | None = None) -> dict[str, Any]:
    """Load the current-state active-learning label cache."""
    label_path = Path(path or default_labels_path())
    if not label_path.exists():
        return {
            "schema_version": ACTIVE_LEARNING_LABEL_SCHEMA_VERSION,
            "updated_at": None,
            "labels": {},
        }

    try:
        payload = json.loads(label_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Active-learning label cache unreadable at %s; starting fresh", label_path)
        return {
            "schema_version": ACTIVE_LEARNING_LABEL_SCHEMA_VERSION,
            "updated_at": None,
            "labels": {},
        }

    labels = {}
    for raw_row in (payload.get("labels") or {}).values():
        try:
            row = normalize_pair_row(raw_row)
        except Exception:
            continue
        labels[row["pair_key"]] = row

    return {
        "schema_version": payload.get("schema_version", ACTIVE_LEARNING_LABEL_SCHEMA_VERSION),
        "updated_at": payload.get("updated_at"),
        "labels": labels,
    }


def save_active_learning_labels(payload: dict[str, Any], path: str | Path | None = None) -> None:
    """Persist the current-state active-learning label cache."""
    label_path = Path(path or default_labels_path())
    serializable = {
        "schema_version": payload.get("schema_version", ACTIVE_LEARNING_LABEL_SCHEMA_VERSION),
        "updated_at": payload.get("updated_at") or utcnow_iso(),
        "labels": payload.get("labels", {}),
    }
    _atomic_write_json(label_path, serializable)


def load_active_learning_queue(path: str | Path | None = None) -> dict[str, Any]:
    """Load the offline-generated active-learning queue artifact."""
    queue_path = Path(path or default_queue_path())
    if not queue_path.exists():
        return {
            "schema_version": ACTIVE_LEARNING_QUEUE_SCHEMA_VERSION,
            "generated_at": None,
            "items": [],
            "stats": {},
        }
    return json.loads(queue_path.read_text(encoding="utf-8"))


def save_active_learning_queue(payload: dict[str, Any], path: str | Path | None = None) -> None:
    """Persist the offline-generated active-learning queue artifact."""
    queue_path = Path(path or default_queue_path())
    _atomic_write_json(queue_path, payload)


def load_known_pair_keys(
    *,
    labels_path: str | Path | None = None,
    extra_pairs: list[dict[str, Any]] | None = None,
) -> set[str]:
    """Return active pair keys that should be excluded from new queue items."""
    label_cache = load_active_learning_labels(labels_path)
    keys = {
        row["pair_key"]
        for row in label_cache.get("labels", {}).values()
        if row.get("active", True)
    }
    for raw_row in extra_pairs or []:
        row = normalize_pair_row(raw_row)
        if row["active"]:
            keys.add(row["pair_key"])
    return keys


def _identity_family_key(identity: dict[str, Any]) -> str:
    """Return a coarse family key for one identity."""
    name = (identity.get("name") or "").strip()
    if not name or name.startswith("Unidentified Person "):
        return ""
    parts = [part for part in name.split() if part]
    if len(parts) < 2:
        return ""
    return parts[-1].lower()


def _target_reference_face_id(
    candidate: dict[str, Any],
    confirmed_index: dict[str, dict[str, Any]],
    face_data: dict[str, dict[str, Any]],
    query_mu: np.ndarray,
) -> str | None:
    """Choose one target face to pair-label against the query face."""
    face_ids = confirmed_index.get(candidate["identity_id"], {}).get("face_ids", [])
    best_face_id = None
    best_distance = float("inf")
    for face_id in face_ids:
        face = face_data.get(face_id)
        if face is None or face.get("mu") is None:
            continue
        distance = float(np.linalg.norm(np.asarray(face["mu"], dtype=np.float32) - query_mu))
        if distance < best_distance:
            best_face_id = face_id
            best_distance = distance
    return best_face_id


def _current_batch_counter(selected_items: list[dict[str, Any]], batch_size: int) -> Counter[str]:
    """Return target-identity counts for the current queue batch."""
    batch_start = (len(selected_items) // batch_size) * batch_size
    return Counter(item["target_identity_id"] for item in selected_items[batch_start:])


def _select_with_diversity(
    candidates: list[dict[str, Any]],
    *,
    limit: int,
    per_identity_cap: int,
    batch_size: int,
    seed_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Greedily pick queue items while capping repeated identities per batch."""
    selected: list[dict[str, Any]] = list(seed_items or [])
    for item in candidates:
        counter = _current_batch_counter(selected, batch_size)
        if counter[item["target_identity_id"]] >= per_identity_cap:
            continue
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _compute_queue_stats(
    queue_items: list[dict[str, Any]],
    *,
    batch_size: int,
    per_identity_cap: int,
) -> dict[str, Any]:
    """Return diversity and slice stats for one queue artifact."""
    first_batch = queue_items[:batch_size]
    first_batch_counts = Counter(item["target_identity_id"] for item in first_batch)
    hard_count = sum(1 for item in queue_items if item.get("is_underrepresented_or_hard"))
    return {
        "queue_count": len(queue_items),
        "first_batch_max_per_identity": max(first_batch_counts.values(), default=0),
        "first_batch_identity_cap_passes": max(first_batch_counts.values(), default=0) <= per_identity_cap,
        "underrepresented_or_hard_count": hard_count,
        "underrepresented_or_hard_share": round(hard_count / len(queue_items), 4) if queue_items else 0.0,
    }


def build_active_learning_queue(
    identities_data: dict[str, Any],
    face_data: dict[str, dict[str, Any]],
    *,
    labels_path: str | Path | None = None,
    extra_pairs: list[dict[str, Any]] | None = None,
    unresolved_states: tuple[str, ...] = ("INBOX", "PROPOSED", "SKIPPED"),
    limit: int = 20,
    top_k: int = 3,
    lower_distance: float = TIER_1_THRESHOLD,
    upper_distance: float = TIER_2_THRESHOLD,
    ambiguous_margin_threshold: float = 0.15,
    tail_face_limit: int = 4,
    per_identity_cap: int = 2,
    batch_size: int = 10,
    minimum_hard_share: float = 0.3,
) -> dict[str, Any]:
    """Build a diverse queue of face-pair labels for active review."""
    identities = identities_data.get("identities", {})
    known_pair_keys = load_known_pair_keys(labels_path=labels_path, extra_pairs=extra_pairs)
    confirmed_index = build_identity_embedding_index(identities_data, face_data, states=("CONFIRMED",))
    dominant_identity_ids = [
        identity_id
        for identity_id, _ in sorted(
            confirmed_index.items(),
            key=lambda item: item[1].get("face_count", 0),
            reverse=True,
        )[:3]
    ]
    tail_identity_ids = {
        identity_id
        for identity_id, item in confirmed_index.items()
        if item.get("face_count", 0) <= tail_face_limit
    }

    midpoint = (lower_distance + upper_distance) / 2.0
    candidates: list[dict[str, Any]] = []

    for source_identity_id, identity in identities.items():
        if identity.get("state") not in unresolved_states or identity.get("merged_into"):
            continue

        face_ids = extract_face_ids(identity)
        source_photo_ids = {
            photo_id
            for face_id in face_ids
            for photo_id in [get_photo_id(face_id)]
            if photo_id
        }
        source_family = _identity_family_key(identity)

        for face_id in face_ids:
            face = face_data.get(face_id)
            if face is None or face.get("mu") is None:
                continue

            ranked = score_identity_distances(
                face["mu"],
                confirmed_index,
                excluded_photo_ids=source_photo_ids,
            )
            if not ranked:
                continue

            best = ranked[0]
            second = ranked[1] if len(ranked) > 1 else None
            margin = (
                (second["distance"] - best["distance"]) / best["distance"]
                if second is not None and best["distance"] > 0
                else float("inf")
            )

            for candidate in ranked[:top_k]:
                if candidate["distance"] < lower_distance or candidate["distance"] > upper_distance:
                    continue

                reference_face_id = _target_reference_face_id(candidate, confirmed_index, face_data, face["mu"])
                if not reference_face_id:
                    continue

                candidate_pair_key = pair_key(face_id, reference_face_id)
                if candidate_pair_key in known_pair_keys:
                    continue

                target_identity = identities.get(candidate["identity_id"], {})
                target_family = _identity_family_key(target_identity)
                reasons: list[str] = []
                if candidate["baseline_rank"] > 1:
                    reasons.append("topk_alternative")
                if candidate["distance"] >= midpoint:
                    reasons.append("boundary_distance")
                if margin < ambiguous_margin_threshold:
                    reasons.append("ambiguous_margin")
                if candidate["identity_id"] in dominant_identity_ids:
                    reasons.append("dominant_identity")
                if candidate["identity_id"] in tail_identity_ids:
                    reasons.append("tail_identity")
                if source_family and target_family and source_family == target_family:
                    reasons.append("family_name_overlap")

                is_hard = any(
                    reason in {
                        "boundary_distance",
                        "ambiguous_margin",
                        "tail_identity",
                        "family_name_overlap",
                        "topk_alternative",
                    }
                    for reason in reasons
                )
                priority = (
                    max(0.0, 1.2 - abs(candidate["distance"] - midpoint)) * 4.0
                    + (1.2 if "ambiguous_margin" in reasons else 0.0)
                    + (0.8 if candidate["baseline_rank"] > 1 else 0.0)
                    + (0.7 if "tail_identity" in reasons else 0.0)
                    + (0.5 if "family_name_overlap" in reasons else 0.0)
                    - (0.2 if "dominant_identity" in reasons and not is_hard else 0.0)
                )

                candidates.append(
                    {
                        "queue_item_id": f"{candidate_pair_key}:{candidate['identity_id']}",
                        "pair_key": candidate_pair_key,
                        "face_id_a": face_id,
                        "face_id_b": reference_face_id,
                        "source_identity_id": source_identity_id,
                        "source_identity_name": identity.get("name", f"Unknown ({source_identity_id[:8]})"),
                        "source_state": identity.get("state", "INBOX"),
                        "target_identity_id": candidate["identity_id"],
                        "target_identity_name": candidate["name"],
                        "target_face_count": candidate.get("face_count", 0),
                        "target_reference_face_id": reference_face_id,
                        "distance": round(float(candidate["distance"]), 4),
                        "baseline_rank": candidate["baseline_rank"],
                        "margin": round(float(margin), 4) if math.isfinite(margin) else None,
                        "priority": round(float(priority), 4),
                        "reasons": reasons,
                        "is_underrepresented_or_hard": is_hard,
                        "source_photo_id": get_photo_id(face_id),
                        "target_photo_id": get_photo_id(reference_face_id),
                    }
                )

    candidates.sort(
        key=lambda item: (
            -int(item["is_underrepresented_or_hard"]),
            -item["priority"],
            item["distance"],
            item["target_identity_name"],
        )
    )

    hard_quota = min(len(candidates), math.ceil(limit * minimum_hard_share))
    hard_candidates = [item for item in candidates if item["is_underrepresented_or_hard"]]
    soft_candidates = [item for item in candidates if not item["is_underrepresented_or_hard"]]

    selected = _select_with_diversity(
        hard_candidates,
        limit=hard_quota,
        per_identity_cap=per_identity_cap,
        batch_size=batch_size,
    )
    selected_ids = {item["queue_item_id"] for item in selected}
    remainder = [item for item in candidates if item["queue_item_id"] not in selected_ids]
    selected = _select_with_diversity(
        remainder,
        limit=limit,
        per_identity_cap=per_identity_cap,
        batch_size=batch_size,
        seed_items=selected,
    )
    selected = selected[:limit]

    stats = _compute_queue_stats(selected, batch_size=batch_size, per_identity_cap=per_identity_cap)
    stats["candidate_count"] = len(candidates)
    stats["dominant_identity_ids"] = dominant_identity_ids
    stats["tail_identity_ids"] = sorted(tail_identity_ids)

    return {
        "schema_version": ACTIVE_LEARNING_QUEUE_SCHEMA_VERSION,
        "generated_at": utcnow_iso(),
        "git_commit": resolve_git_commit(),
        "queue_run_id": f"active-learning:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "config": {
            "limit": limit,
            "top_k": top_k,
            "lower_distance": lower_distance,
            "upper_distance": upper_distance,
            "ambiguous_margin_threshold": ambiguous_margin_threshold,
            "tail_face_limit": tail_face_limit,
            "per_identity_cap": per_identity_cap,
            "batch_size": batch_size,
            "minimum_hard_share": minimum_hard_share,
        },
        "stats": stats,
        "items": selected,
    }


def _compute_similarity(face_id_a: str, face_id_b: str, *, embeddings_path: str | Path | None = None) -> float:
    """Compute cosine similarity for two faces from the shared embedding store."""
    face_data = load_face_data(Path(embeddings_path or Path(DATA_DIR) / "embeddings.npy"))
    face_a = face_data.get(face_id_a)
    face_b = face_data.get(face_id_b)
    if face_a is None or face_b is None or face_a.get("mu") is None or face_b.get("mu") is None:
        raise KeyError(f"Missing embedding for {face_id_a} or {face_id_b}")

    emb_a = np.asarray(face_a["mu"], dtype=np.float32)
    emb_b = np.asarray(face_b["mu"], dtype=np.float32)
    denom = float(np.linalg.norm(emb_a) * np.linalg.norm(emb_b))
    if denom <= 1e-10:
        return 0.0
    return float(np.dot(emb_a, emb_b) / denom)


def _minimal_before_state(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the lineage-relevant subset of a stored label row."""
    if not row:
        return None
    return {
        "is_match": row.get("is_match"),
        "label_type": row.get("label_type"),
        "active": row.get("active"),
        "state_event_id": row.get("state_event_id"),
    }


def record_active_learning_label(
    face_id_a: str,
    face_id_b: str,
    *,
    is_same_person: bool,
    actor_id: str = "admin",
    source_surface: str = "app.cluster_review_routes.active_learning",
    labels_path: str | Path | None = None,
    supabase_client=None,
    metadata: dict[str, Any] | None = None,
    similarity_score: float | None = None,
    embeddings_path: str | Path | None = None,
) -> dict[str, Any]:
    """Persist one active-learning label with current-state and lineage."""
    cache = load_active_learning_labels(labels_path)
    normalized_path = Path(labels_path or default_labels_path())
    existing = cache.get("labels", {}).get(pair_key(face_id_a, face_id_b))
    similarity = similarity_score if similarity_score is not None else _compute_similarity(
        face_id_a,
        face_id_b,
        embeddings_path=embeddings_path,
    )
    row = build_calibration_pair_row(
        face_id_a,
        face_id_b,
        similarity_score=similarity,
        is_match=is_same_person,
        source="active_learning_same" if is_same_person else "active_learning_different",
        label_type=LABEL_TYPE_EXPLICIT_POSITIVE if is_same_person else LABEL_TYPE_EXPLICIT_NEGATIVE,
        state_event_action="active_learning_label",
        actor_id=actor_id,
        source_surface=source_surface,
        linked_event_id=existing.get("state_event_id") if existing else None,
        metadata=metadata or {},
    )

    if supabase_client is not None:
        row = record_calibration_pair(
            supabase_client,
            row,
            source_surface=source_surface,
            actor_id=actor_id,
            action="active_learning_label",
            before_state=_minimal_before_state(existing),
        )
    else:
        record_pair_state_event(
            row,
            source_surface=source_surface,
            actor_id=actor_id,
            action="active_learning_label",
            before_state=_minimal_before_state(existing),
            linked_event_id=existing.get("state_event_id") if existing else None,
        )

    cache["labels"][row["pair_key"]] = row
    cache["updated_at"] = utcnow_iso()
    save_active_learning_labels(cache, normalized_path)
    logger.info("Recorded active-learning label %s same=%s", row["pair_key"], is_same_person)
    return row


def revert_active_learning_label(
    face_id_a: str,
    face_id_b: str,
    *,
    actor_id: str = "admin",
    source_surface: str = "app.cluster_review_routes.active_learning",
    labels_path: str | Path | None = None,
    supabase_client=None,
) -> dict[str, Any] | None:
    """Revert one active-learning label before recalibration consumes it."""
    cache = load_active_learning_labels(labels_path)
    normalized_path = Path(labels_path or default_labels_path())
    existing = cache.get("labels", {}).get(pair_key(face_id_a, face_id_b))
    if existing is None:
        return None

    if supabase_client is not None:
        reverted = revert_calibration_pair(
            supabase_client,
            face_id_a,
            face_id_b,
            actor_id=actor_id,
            source_surface=source_surface,
            reason_code="active_learning_revert",
            linked_event_id=existing.get("state_event_id"),
        )
        if reverted is None:
            return None
    else:
        if not existing.get("active", True):
            return existing
        event_id = os.urandom(16).hex()
        reverted = dict(existing)
        reverted["active"] = False
        reverted["linked_event_id"] = existing.get("state_event_id")
        reverted["reversed_by_event_id"] = event_id
        reverted["state_event_action"] = "revert"
        reverted["state_event_id"] = event_id
        reverted["labeled_at"] = utcnow_iso()
        record_pair_state_event(
            reverted,
            source_surface=source_surface,
            actor_id=actor_id,
            action="revert",
            before_state=_minimal_before_state(existing),
            linked_event_id=existing.get("state_event_id"),
        )

    cache["labels"][reverted["pair_key"]] = normalize_pair_row(reverted)
    cache["updated_at"] = utcnow_iso()
    save_active_learning_labels(cache, normalized_path)
    logger.info("Reverted active-learning label %s", reverted["pair_key"])
    return cache["labels"][reverted["pair_key"]]


def recent_active_learning_labels(
    *,
    labels_path: str | Path | None = None,
    limit: int = 10,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    """Return recent label rows sorted newest-first."""
    cache = load_active_learning_labels(labels_path)
    rows = list(cache.get("labels", {}).values())
    if active_only:
        rows = [row for row in rows if row.get("active", True)]
    rows.sort(key=lambda row: row.get("labeled_at") or "", reverse=True)
    return rows[:limit]


def find_uncertain_pairs(
    embeddings_cache: dict,
    identities: dict,
    low: float = UNCERTAIN_LOW,
    high: float = UNCERTAIN_HIGH,
    max_pairs: int = 50,
) -> list[dict]:
    """Find face pairs near the decision boundary for admin labeling."""
    face_ids = list(embeddings_cache.keys())
    if len(face_ids) < 2:
        return []

    face_to_identity = {}
    for identity_id, data in identities.items():
        if data.get("merged_into"):
            continue
        for fid in data.get("anchor_ids", []) + data.get("candidate_ids", []):
            face_to_identity[fid] = identity_id

    sample_ids = face_ids
    if len(face_ids) > 200:
        rng = np.random.default_rng(42)
        sample_ids = list(rng.choice(face_ids, size=200, replace=False))

    midpoint = (low + high) / 2
    candidates = []

    for i, fid_a in enumerate(sample_ids):
        emb_a = embeddings_cache.get(fid_a)
        if emb_a is None:
            continue
        emb_a_flat = np.array(emb_a).flatten()

        for fid_b in sample_ids[i + 1 :]:
            emb_b = embeddings_cache.get(fid_b)
            if emb_b is None:
                continue
            emb_b_flat = np.array(emb_b).flatten()

            dist = float(np.linalg.norm(emb_a_flat - emb_b_flat))
            if low <= dist <= high:
                id_a = face_to_identity.get(fid_a)
                id_b = face_to_identity.get(fid_b)
                if id_a and id_b and id_a == id_b:
                    continue

                candidates.append(
                    {
                        "face_id_a": fid_a,
                        "face_id_b": fid_b,
                        "distance": round(dist, 4),
                        "identity_a": id_a,
                        "identity_b": id_b,
                        "distance_from_midpoint": round(abs(dist - midpoint), 4),
                    }
                )

    candidates.sort(key=lambda x: x["distance_from_midpoint"])
    return candidates[:max_pairs]


def add_labeled_pair(
    labeled_pairs: list[dict],
    face_id_a: str,
    face_id_b: str,
    is_same_person: bool,
    labeled_by: str = "admin",
) -> list[dict]:
    """Record an admin-labeled pair for active learning."""
    if face_id_a > face_id_b:
        face_id_a, face_id_b = face_id_b, face_id_a

    for existing in labeled_pairs:
        if existing.get("face_id_a") == face_id_a and existing.get("face_id_b") == face_id_b:
            existing["is_same_person"] = is_same_person
            existing["labeled_by"] = labeled_by
            existing["labeled_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("Updated label for pair (%s, %s): %s", face_id_a, face_id_b, is_same_person)
            return labeled_pairs

    labeled_pairs.append(
        {
            "face_id_a": face_id_a,
            "face_id_b": face_id_b,
            "is_same_person": is_same_person,
            "labeled_by": labeled_by,
            "labeled_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    logger.info("Added label for pair (%s, %s): %s", face_id_a, face_id_b, is_same_person)
    return labeled_pairs
