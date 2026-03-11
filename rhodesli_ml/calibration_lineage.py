"""Shared calibration-label lineage, filtering, and safety checks.

This module is the Phase 1 source of truth for:
- canonical calibration pair identity
- label provenance taxonomy
- state-event envelopes for calibration writes
- reverted-label exclusion
- logical consistency checks before recalibration
"""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import DATA_DIR

logger = logging.getLogger(__name__)

LABEL_TYPE_EXPLICIT_POSITIVE = "explicit_positive"
LABEL_TYPE_EXPLICIT_NEGATIVE = "explicit_negative"
LABEL_TYPE_IMPLICIT_NEGATIVE = "implicit_negative"
LABEL_TYPE_DISCOVERY_CONFIRMED = "discovery_confirmed"

LABEL_TYPES = {
    LABEL_TYPE_EXPLICIT_POSITIVE,
    LABEL_TYPE_EXPLICIT_NEGATIVE,
    LABEL_TYPE_IMPLICIT_NEGATIVE,
    LABEL_TYPE_DISCOVERY_CONFIRMED,
}

CALIBRATION_TARGET_TYPE = "calibration_pair"
STATE_EVENT_SCHEMA_VERSION = 1


def utcnow_iso() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _append_local_audit_entry(event: dict[str, Any], *, actor_id: str) -> None:
    """Append one calibration event to the local audit log cache."""
    audit_path = Path(DATA_DIR) / "audit_log.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)

    audit = {"entries": []}
    if audit_path.exists():
        try:
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            audit = {"entries": []}

    audit["entries"].append(
        {
            "action": event.get("action"),
            "target_id": event.get("target_id"),
            "target_type": event.get("target_type"),
            "actor": actor_id,
            "admin": actor_id,
            "timestamp": event.get("created_at") or utcnow_iso(),
            "details": event.get("reason_code", ""),
            "data": event,
        }
    )
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")


def canonicalize_pair(face_id_a: str, face_id_b: str) -> tuple[str, str]:
    """Return the canonical `(a, b)` ordering for a face pair."""
    return (min(face_id_a, face_id_b), max(face_id_a, face_id_b))


def pair_key(face_id_a: str, face_id_b: str) -> str:
    """Stable string identifier for a canonical face pair."""
    a, b = canonicalize_pair(face_id_a, face_id_b)
    return f"{a}::{b}"


def infer_label_type(
    is_match: bool,
    *,
    source: str | None = None,
    state_event_action: str | None = None,
) -> str:
    """Infer the Phase 1 label taxonomy from action/source context."""
    action = (state_event_action or "").strip().lower()
    source_l = (source or "").strip().lower()

    if action == "merge" or "merge" in source_l:
        return LABEL_TYPE_EXPLICIT_POSITIVE
    if action == "reject" or "reject" in source_l:
        return LABEL_TYPE_EXPLICIT_NEGATIVE
    if action == "confirm" or "implicit_confirm" in source_l or "implicit_different" in source_l:
        return LABEL_TYPE_IMPLICIT_NEGATIVE
    if "discovery" in source_l and is_match:
        return LABEL_TYPE_DISCOVERY_CONFIRMED

    if is_match:
        return LABEL_TYPE_EXPLICIT_POSITIVE
    return LABEL_TYPE_EXPLICIT_NEGATIVE


def default_weight_for_label_type(label_type: str) -> float:
    """Return the default pair weight for one label type."""
    if label_type == LABEL_TYPE_EXPLICIT_NEGATIVE:
        return 1.5
    return 1.0


def normalize_pair_row(pair: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized calibration pair row with canonical IDs and defaults."""
    raw = dict(pair)
    a, b = canonicalize_pair(raw["face_id_a"], raw["face_id_b"])
    normalized = deepcopy(raw)
    normalized["face_id_a"] = a
    normalized["face_id_b"] = b
    normalized["pair_key"] = raw.get("pair_key") or pair_key(a, b)
    normalized["is_match"] = bool(raw["is_match"])
    normalized["active"] = raw.get("active", True) is not False

    label_type = raw.get("label_type")
    if label_type not in LABEL_TYPES:
        label_type = infer_label_type(
            normalized["is_match"],
            source=raw.get("source"),
            state_event_action=raw.get("state_event_action"),
        )
    normalized["label_type"] = label_type

    weight = raw.get("weight")
    if weight is None:
        weight = default_weight_for_label_type(label_type)
    normalized["weight"] = float(weight)

    normalized["source"] = raw.get("source", "unknown")
    normalized["state_event_action"] = raw.get("state_event_action", "label_recorded")
    normalized["source_surface"] = raw.get("source_surface", "unknown")
    normalized["actor_id"] = raw.get("actor_id", "system")
    normalized["linked_event_id"] = raw.get("linked_event_id")
    normalized["reversed_by_event_id"] = raw.get("reversed_by_event_id")
    normalized["state_event_id"] = raw.get("state_event_id") or str(uuid.uuid4())
    normalized["labeled_at"] = raw.get("labeled_at") or raw.get("created_at") or utcnow_iso()
    metadata = raw.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {"raw_metadata": metadata}
    normalized["metadata"] = metadata
    return normalized


def build_calibration_pair_row(
    face_id_a: str,
    face_id_b: str,
    *,
    similarity_score: float,
    is_match: bool,
    source: str,
    label_type: str | None = None,
    weight: float | None = None,
    active: bool = True,
    state_event_id: str | None = None,
    state_event_action: str = "label_recorded",
    source_surface: str = "unknown",
    actor_id: str = "system",
    linked_event_id: str | None = None,
    reversed_by_event_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    labeled_at: str | None = None,
) -> dict[str, Any]:
    """Construct one calibration pair row with the required lineage fields."""
    a, b = canonicalize_pair(face_id_a, face_id_b)
    label_type = label_type or infer_label_type(
        is_match,
        source=source,
        state_event_action=state_event_action,
    )
    if weight is None:
        weight = default_weight_for_label_type(label_type)

    row = {
        "face_id_a": a,
        "face_id_b": b,
        "pair_key": pair_key(a, b),
        "similarity_score": round(float(similarity_score), 6),
        "is_match": bool(is_match),
        "source": source,
        "weight": float(weight),
        "label_type": label_type,
        "active": bool(active),
        "state_event_id": state_event_id or str(uuid.uuid4()),
        "state_event_action": state_event_action,
        "source_surface": source_surface,
        "actor_id": actor_id,
        "linked_event_id": linked_event_id,
        "reversed_by_event_id": reversed_by_event_id,
        "labeled_at": labeled_at or utcnow_iso(),
        "metadata": metadata or {},
    }
    return normalize_pair_row(row)


def build_state_event_envelope(
    *,
    target_id: str,
    action: str,
    actor_id: str,
    source_surface: str,
    before_state: dict[str, Any] | None,
    after_state: dict[str, Any] | None,
    reason_code: str,
    event_id: str | None = None,
    actor_type: str = "admin",
    community_id: str | None = None,
    request_id: str | None = None,
    linked_event_id: str | None = None,
    ml_run_id: str | None = None,
    prompt_manifest_id: str | None = None,
    reversed_by_event_id: str | None = None,
    target_type: str = CALIBRATION_TARGET_TYPE,
) -> dict[str, Any]:
    """Build the standard mutation-event envelope for a calibration write."""
    before = before_state or {}
    after = after_state or {}
    changed_fields = sorted(
        {
            *before.keys(),
            *after.keys(),
        }
    )
    return {
        "schema_version": STATE_EVENT_SCHEMA_VERSION,
        "event_id": event_id or str(uuid.uuid4()),
        "target_type": target_type,
        "target_id": target_id,
        "action": action,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "source_surface": source_surface,
        "community_id": community_id,
        "before_state": before,
        "after_state": after,
        "changed_fields": changed_fields,
        "reason_code": reason_code,
        "request_id": request_id,
        "linked_event_id": linked_event_id,
        "ml_run_id": ml_run_id,
        "prompt_manifest_id": prompt_manifest_id,
        "created_at": utcnow_iso(),
        "reversed_by_event_id": reversed_by_event_id,
    }


def record_pair_state_event(
    row: dict[str, Any],
    *,
    source_surface: str,
    actor_id: str,
    action: str,
    before_state: dict[str, Any] | None = None,
    linked_event_id: str | None = None,
) -> dict[str, Any]:
    """Mirror one calibration mutation to the audit log if available."""
    event = build_state_event_envelope(
        target_id=row["pair_key"],
        action=action,
        actor_id=actor_id,
        source_surface=source_surface,
        before_state=before_state,
        after_state={
            "is_match": row["is_match"],
            "label_type": row["label_type"],
            "active": row["active"],
            "state_event_id": row["state_event_id"],
        },
        reason_code=row["label_type"],
        event_id=row["state_event_id"],
        linked_event_id=linked_event_id or row.get("linked_event_id"),
        reversed_by_event_id=row.get("reversed_by_event_id"),
    )

    try:
        _append_local_audit_entry(event, actor_id=actor_id)
    except Exception as exc:
        logger.warning("Calibration pair local audit append failed for %s: %s", row["pair_key"], exc)

    try:
        from app.supabase_data import sync_audit_log_entry

        sync_audit_log_entry(
            action=event["action"],
            target_id=row["pair_key"],
            actor=actor_id,
            entry_data=event,
            target_type=CALIBRATION_TARGET_TYPE,
        )
    except Exception as exc:
        logger.warning("Calibration pair audit sync failed for %s: %s", row["pair_key"], exc)
    return event


def record_calibration_pair(
    supabase_client,
    row: dict[str, Any],
    *,
    source_surface: str,
    actor_id: str,
    action: str,
    before_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Upsert one calibration pair and mirror its mutation event to audit storage."""
    normalized = normalize_pair_row(row)
    supabase_client.table("calibration_pairs").upsert(
        normalized,
        on_conflict="face_id_a,face_id_b",
    ).execute()
    record_pair_state_event(
        normalized,
        source_surface=source_surface,
        actor_id=actor_id,
        action=action,
        before_state=before_state,
    )
    return normalized


def revert_calibration_pair(
    supabase_client,
    face_id_a: str,
    face_id_b: str,
    *,
    actor_id: str = "system",
    source_surface: str = "scripts.recalibrate",
    reason_code: str = "reverted",
    linked_event_id: str | None = None,
) -> dict[str, Any] | None:
    """Mark one calibration pair inactive and log the reversal envelope."""
    a, b = canonicalize_pair(face_id_a, face_id_b)
    result = (
        supabase_client.table("calibration_pairs")
        .select("*")
        .eq("face_id_a", a)
        .eq("face_id_b", b)
        .limit(1)
        .execute()
    )
    existing = (result.data or [None])[0]
    if not existing:
        return None

    before = normalize_pair_row(existing)
    if not before["active"]:
        return before

    event_id = str(uuid.uuid4())
    after = dict(before)
    after["active"] = False
    after["reversed_by_event_id"] = event_id
    after["linked_event_id"] = linked_event_id or before["state_event_id"]
    after["state_event_action"] = "revert"
    after["state_event_id"] = event_id
    after["labeled_at"] = utcnow_iso()

    supabase_client.table("calibration_pairs").upsert(
        after,
        on_conflict="face_id_a,face_id_b",
    ).execute()
    record_pair_state_event(
        after,
        source_surface=source_surface,
        actor_id=actor_id,
        action="revert",
        before_state={
            "is_match": before["is_match"],
            "label_type": before["label_type"],
            "active": before["active"],
            "state_event_id": before["state_event_id"],
        },
        linked_event_id=linked_event_id or before["state_event_id"],
    )
    return after


def prepare_pairs_for_recalibration(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """Filter inactive pairs and report logical conflicts for recalibration."""
    active_rows: list[dict[str, Any]] = []
    inactive_rows: list[dict[str, Any]] = []
    deduped: dict[str, dict[str, Any]] = {}
    direct_conflicts: list[dict[str, Any]] = []

    for raw_pair in pairs:
        pair = normalize_pair_row(raw_pair)
        if not pair["active"]:
            inactive_rows.append(pair)
            continue

        key = pair["pair_key"]
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = pair
            active_rows.append(pair)
            continue

        if existing["is_match"] != pair["is_match"]:
            direct_conflicts.append(
                {
                    "type": "direct_conflict",
                    "pair_key": key,
                    "existing_event_id": existing["state_event_id"],
                    "incoming_event_id": pair["state_event_id"],
                }
            )
            continue

        existing_ts = existing.get("labeled_at", "")
        incoming_ts = pair.get("labeled_at", "")
        if incoming_ts >= existing_ts:
            deduped[key] = pair

    normalized_active = list(deduped.values())

    parents: dict[str, str] = {}

    def find(node: str) -> str:
        parents.setdefault(node, node)
        if parents[node] != node:
            parents[node] = find(parents[node])
        return parents[node]

    def union(node_a: str, node_b: str) -> None:
        root_a = find(node_a)
        root_b = find(node_b)
        if root_a != root_b:
            parents[root_b] = root_a

    for pair in normalized_active:
        if pair["is_match"]:
            union(pair["face_id_a"], pair["face_id_b"])

    transitive_conflicts: list[dict[str, Any]] = []
    for pair in normalized_active:
        if pair["is_match"]:
            continue
        if find(pair["face_id_a"]) == find(pair["face_id_b"]):
            transitive_conflicts.append(
                {
                    "type": "transitive_conflict",
                    "pair_key": pair["pair_key"],
                    "state_event_id": pair["state_event_id"],
                }
            )

    label_counts = Counter(pair["label_type"] for pair in normalized_active)
    match_count = sum(1 for pair in normalized_active if pair["is_match"])
    nonmatch_count = len(normalized_active) - match_count

    return {
        "active_pairs": normalized_active,
        "inactive_pairs": inactive_rows,
        "conflicts": direct_conflicts + transitive_conflicts,
        "counts": {
            "active_pair_count": len(normalized_active),
            "inactive_pair_count": len(inactive_rows),
            "match_count": match_count,
            "nonmatch_count": nonmatch_count,
            "label_type_counts": dict(label_counts),
        },
    }


def assess_recalibration_need(
    prepared: dict[str, Any],
    model_report: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    new_pairs_threshold: int = 20,
    stale_days: int = 30,
    class_ratio_shift_threshold: float = 0.5,
) -> tuple[bool, str]:
    """Reproduce recalibration freshness checks from current active pairs."""
    active_pair_count = prepared["counts"]["active_pair_count"]
    match_count = prepared["counts"]["match_count"]
    nonmatch_count = prepared["counts"]["nonmatch_count"]

    if prepared["conflicts"]:
        return False, "blocked_by_conflicts"

    if not model_report or model_report.get("status") == "no_model":
        return True, "no_model_exists"

    previous_pair_count = int(model_report.get("pair_count") or 0)
    new_pairs = active_pair_count - previous_pair_count
    if new_pairs > new_pairs_threshold:
        return True, f"{new_pairs} new active pairs since last fit"

    created_at = model_report.get("created_at")
    if created_at:
        current_time = now or datetime.now(timezone.utc)
        try:
            model_age = current_time - datetime.fromisoformat(created_at)
            if model_age.days > stale_days:
                return True, f"model is {model_age.days} days old"
        except ValueError:
            logger.warning("Invalid calibration created_at timestamp: %s", created_at)

    old_nonmatch = int(model_report.get("nonmatch_count") or 0)
    old_match = int(model_report.get("match_count") or 0)
    if old_nonmatch > 0 and nonmatch_count > 0:
        old_ratio = old_match / old_nonmatch
        new_ratio = match_count / nonmatch_count
        if abs(new_ratio - old_ratio) / max(old_ratio, 0.01) > class_ratio_shift_threshold:
            return True, f"class ratio shifted from {old_ratio:.2f} to {new_ratio:.2f}"

    return False, "no trigger met"


def build_recalibration_status_report(
    pairs: list[dict[str, Any]],
    *,
    model_report: dict[str, Any] | None = None,
    git_commit: str | None = None,
    source: str = "unknown",
) -> dict[str, Any]:
    """Build one auditable status report for the current calibration snapshot."""
    prepared = prepare_pairs_for_recalibration(pairs)
    should_recalibrate, reason = assess_recalibration_need(prepared, model_report)

    return {
        "generated_at": utcnow_iso(),
        "git_commit": git_commit or resolve_git_commit(),
        "source": source,
        "status": "blocked" if prepared["conflicts"] else "ok",
        "should_recalibrate": should_recalibrate,
        "reason": reason,
        "counts": prepared["counts"],
        "conflicts": prepared["conflicts"],
        "current_model": model_report or {"status": "no_model"},
    }


def resolve_git_commit() -> str | None:
    """Return the current git HEAD if available."""
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


def load_pairs_from_json(path: str | Path) -> list[dict[str, Any]]:
    """Load calibration pairs from a JSON file created by scripts or reports."""
    with open(path) as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        if "pairs" in data and isinstance(data["pairs"], list):
            return data["pairs"]
        raise ValueError(f"Unsupported calibration pair JSON payload in {path}")
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported calibration pair JSON payload in {path}")


def load_pairs_from_supabase(supabase_client) -> list[dict[str, Any]]:
    """Load calibration pairs from Supabase with pagination."""
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        result = (
            supabase_client.table("calibration_pairs")
            .select("*")
            .range(offset, offset + 999)
            .execute()
        )
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return rows
