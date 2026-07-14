"""Supabase helpers for the Research Desk investigation run contract."""

from datetime import datetime, timezone
import logging

from app.supabase_data import get_supabase_client


logger = logging.getLogger(__name__)

ALLOWED_STATUSES = {
    "pending",
    "assembling",
    "investigating",
    "sealed",
    "reviewed",
    "failed",
}
ALLOWED_TRANSITIONS = {
    "pending": {"assembling", "failed"},
    "assembling": {"investigating", "failed"},
    "investigating": {"sealed", "failed"},
    "sealed": {"reviewed", "failed"},
    "reviewed": set(),
    "failed": set(),
}
RIGHTS_STATES = {"private", "archive_only", "publishable"}


def _now_iso() -> str:
    """Return a timezone-aware timestamp suitable for JSONB history."""
    return datetime.now(timezone.utc).isoformat()


def _client(sb):
    return sb if sb is not None else get_supabase_client()


def _first_row(result) -> dict | None:
    data = getattr(result, "data", None)
    return data[0] if data else None


def compute_idempotency_key(case_ref: str, input_manifest_hash: str) -> str:
    """Build the stable run key from its opaque case reference and manifest."""
    return f"{case_ref}:{input_manifest_hash}"


def create_run(
    case_ref,
    input_manifest,
    input_manifest_hash,
    *,
    community_id=None,
    claims=None,
    candidates=None,
    contradictions=None,
    requested_decisions=None,
    sealed_verdicts=None,
    models_used=None,
    total_tokens=0,
    total_cost_usd=0.0,
    rights_state="private",
    status="pending",
    worth_opening=None,
    sb=None,
) -> dict | None:
    """Create one run using a single idempotent, atomic Supabase upsert."""
    decisions = requested_decisions or []
    if len(decisions) > 3:
        raise ValueError("requested_decisions cannot contain more than three items")
    if rights_state not in RIGHTS_STATES:
        raise ValueError(f"invalid rights_state: {rights_state}")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid run status: {status}")

    client = _client(sb)
    if not client:
        logger.warning("Supabase unavailable; investigation run was not created")
        return None

    now = _now_iso()
    row = {
        "case_ref": case_ref,
        "community_id": community_id,
        "input_manifest": input_manifest,
        "input_manifest_hash": input_manifest_hash,
        "idempotency_key": compute_idempotency_key(case_ref, input_manifest_hash),
        "status": status,
        "status_history": [{"status": status, "at": now}],
        "claims": claims or [],
        "candidates": candidates or [],
        "contradictions": contradictions or [],
        "requested_decisions": decisions,
        "sealed_verdicts": sealed_verdicts or [],
        "models_used": models_used or [],
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
        "rights_state": rights_state,
        "worth_opening": worth_opening,
    }
    try:
        result = (
            client.table("investigation_runs")
            .upsert(
                row,
                on_conflict="idempotency_key",
                ignore_duplicates=True,
            )
            .execute()
        )
        return _first_row(result) or row
    except Exception as exc:
        logger.warning("Supabase investigation run create failed: %s", exc)
        return None


def get_run(run_id=None, *, case_ref=None, idempotency_key=None, sb=None) -> dict | None:
    """Fetch one run by ID, case reference, or idempotency key."""
    if run_id is None and case_ref is None and idempotency_key is None:
        raise ValueError("one run lookup key is required")

    client = _client(sb)
    if not client:
        return None

    column, value = (
        ("id", run_id)
        if run_id is not None
        else ("case_ref", case_ref)
        if case_ref is not None
        else ("idempotency_key", idempotency_key)
    )
    try:
        result = (
            client.table("investigation_runs")
            .select("*")
            .eq(column, value)
            .limit(1)
            .execute()
        )
        return _first_row(result)
    except Exception as exc:
        logger.warning("Supabase investigation run lookup failed: %s", exc)
        return None


def _transition_update(
    run_id,
    new_status,
    *,
    extra_fields=None,
    sb=None,
) -> dict | None:
    """Validate a transition and apply it with any accompanying run fields."""
    if new_status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid run status: {new_status}")

    client = _client(sb)
    if not client:
        return None
    current_run = get_run(run_id, sb=client)
    if current_run is None:
        return None

    current = current_run.get("status")
    if current not in ALLOWED_TRANSITIONS:
        raise ValueError(f"invalid current run status: {current}")
    if new_status not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"illegal run status transition: {current} -> {new_status}")

    now = _now_iso()
    history = list(current_run.get("status_history") or [])
    history.append({"from": current, "to": new_status, "at": now})
    update = dict(extra_fields or {})
    update.update({"status": new_status, "status_history": history})
    if new_status == "sealed":
        update["sealed_at"] = now
    elif new_status == "reviewed":
        update["reviewed_at"] = now

    try:
        result = (
            client.table("investigation_runs")
            .update(update)
            .eq("id", run_id)
            .execute()
        )
        return _first_row(result) or {**current_run, **update}
    except Exception as exc:
        logger.warning("Supabase investigation run transition failed: %s", exc)
        return None


def transition_status(run_id, new_status, *, sb=None) -> dict | None:
    """Move a run through the allowed lifecycle and append its history."""
    return _transition_update(run_id, new_status, sb=sb)


def seal_verdicts(
    run_id,
    verdicts,
    *,
    total_tokens=0,
    total_cost_usd=0.0,
    models_used=None,
    sb=None,
) -> dict | None:
    """Store sealed model verdicts and move an investigating run to sealed."""
    sealed = [{**verdict, "sealed": True} for verdict in verdicts]
    return _transition_update(
        run_id,
        "sealed",
        extra_fields={
            "sealed_verdicts": sealed,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost_usd,
            "models_used": models_used or [],
        },
        sb=sb,
    )


def record_adjudication(
    run_id,
    adjudication: dict,
    *,
    worth_opening=None,
    sb=None,
) -> dict | None:
    """Store human adjudication and move a sealed run to reviewed."""
    return _transition_update(
        run_id,
        "reviewed",
        extra_fields={
            "adjudication": adjudication,
            "worth_opening": worth_opening,
        },
        sb=sb,
    )
