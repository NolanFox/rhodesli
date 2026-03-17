"""
Audit logging for identity mutations.

Writes to the Supabase `audit_log` table. Fire-and-forget: failures are logged
but never crash the mutation.

Table schema: id, action, entity_type, entity_id, user_id, user_email,
              old_value (JSONB), new_value (JSONB), metadata (JSONB), created_at.
"""

import json
import logging

logger = logging.getLogger(__name__)


def _log_audit(
    action: str,
    entity_id: str,
    user_email: str | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
    metadata: dict | None = None,
) -> None:
    """Write an audit_log entry to Supabase. Fire-and-forget."""
    try:
        from app.supabase_data import get_supabase_client

        client = get_supabase_client()
        if not client:
            return

        row = {
            "action": action,
            "entity_type": "identity",
            "entity_id": str(entity_id),
            "user_email": user_email or "",
            "old_value": _safe_jsonb(old_value),
            "new_value": _safe_jsonb(new_value),
            "metadata": _safe_jsonb(metadata),
        }
        client.table("audit_log").insert(row).execute()
        logger.debug("audit_log: %s on %s", action, entity_id)
    except Exception:
        logger.error("audit_log write failed: action=%s entity=%s", action, entity_id, exc_info=True)


def _safe_jsonb(val: dict | None) -> dict:
    """Ensure value is JSON-serializable. Convert non-serializable types to strings."""
    if val is None:
        return {}
    try:
        json.dumps(val)
        return val
    except (TypeError, ValueError):
        # Fallback: stringify non-serializable values
        safe = {}
        for k, v in val.items():
            try:
                json.dumps(v)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = str(v)
        return safe
