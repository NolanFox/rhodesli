"""Log ALL Gemini API calls for analysis and progressive refinement tracking.

Every Gemini API call gets logged with full context:
- Timestamp, model version, photo ID
- Full prompt (or hash if too large) and response
- Token counts and cost estimate
- Input context (verified facts provided)
- Comparison to previous result (for re-analyses)

Storage: rhodesli_ml/data/api_logs/ as individual JSON files.
See AD-137 for design rationale.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from rhodesli_ml.gemini_config import get_model_pricing

LOG_DIR = Path("rhodesli_ml/data/api_logs")


def _ensure_log_dir():
    """Create log directory if it doesn't exist."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _make_log_filename(photo_id: str, model: str, timestamp: str) -> str:
    """Generate log filename: {timestamp}_{photo_id}_{model}.json"""
    # Sanitize for filename safety
    safe_photo = photo_id.replace("/", "_").replace(" ", "_")[:50]
    safe_model = model.replace("/", "_")
    safe_ts = timestamp.replace(":", "-").replace("+", "")[:19]
    return f"{safe_ts}_{safe_photo}_{safe_model}.json"


def log_api_call(
    photo_id: str,
    model: str,
    prompt: str,
    response_text: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    verified_facts: dict | None = None,
    previous_result: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    """Log a Gemini API call with full context.

    Args:
        photo_id: Identifier for the photo being analyzed.
        model: Gemini model string used.
        prompt: Full prompt text sent to the API.
        response_text: Raw response text from the API.
        input_tokens: Number of input tokens (from API response).
        output_tokens: Number of output tokens (from API response).
        verified_facts: Dict of verified facts provided as context.
        previous_result: Previous analysis result for comparison.
        metadata: Additional metadata to include.

    Returns:
        The log entry dict (also written to disk).
    """
    _ensure_log_dir()

    timestamp = datetime.now(timezone.utc).isoformat()
    pricing = get_model_pricing(model)
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    # Hash long prompts instead of storing full text
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
    store_prompt = prompt if len(prompt) < 5000 else f"[hash:{prompt_hash}] {prompt[:500]}..."

    # Build comparison if previous result exists
    comparison = None
    if previous_result:
        comparison = _compare_results(previous_result, response_text)

    entry = {
        "timestamp": timestamp,
        "photo_id": photo_id,
        "model": model,
        "prompt": store_prompt,
        "prompt_hash": prompt_hash,
        "response": response_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 6),
        "verified_facts": verified_facts or {},
        "previous_result": previous_result,
        "comparison": comparison,
        "metadata": metadata or {},
    }

    filename = _make_log_filename(photo_id, model, timestamp)
    filepath = LOG_DIR / filename
    with open(filepath, "w") as f:
        json.dump(entry, f, indent=2)

    return entry


def _compare_results(previous: dict, new_response_text: str) -> dict:
    """Compare previous and new analysis results.

    Returns a dict describing what changed.
    """
    try:
        new = json.loads(new_response_text) if isinstance(new_response_text, str) else new_response_text
    except (json.JSONDecodeError, TypeError):
        return {"error": "Could not parse new response as JSON"}

    prev = previous if isinstance(previous, dict) else {}
    changes = {}

    # Compare date estimates
    old_decade = prev.get("estimated_decade")
    new_decade = new.get("estimated_decade")
    if old_decade and new_decade and old_decade != new_decade:
        changes["decade_changed"] = {"from": old_decade, "to": new_decade}

    old_year = prev.get("estimated_year_range", {})
    new_year = new.get("estimated_year_range", {})
    if old_year != new_year:
        changes["year_range_changed"] = {"from": old_year, "to": new_year}

    # Compare confidence
    old_conf = prev.get("confidence")
    new_conf = new.get("confidence")
    if old_conf and new_conf and old_conf != new_conf:
        changes["confidence_changed"] = {"from": old_conf, "to": new_conf}

    # Summary
    changes["has_changes"] = bool(changes)
    changes["change_count"] = len([k for k in changes if k.endswith("_changed")])

    return changes


def load_logs(photo_id: str = None, model: str = None, limit: int = 100) -> list[dict]:
    """Load API logs, optionally filtered by photo_id or model.

    Args:
        photo_id: Filter to logs for this photo.
        model: Filter to logs from this model.
        limit: Maximum number of logs to return.

    Returns:
        List of log entry dicts, newest first.
    """
    if not LOG_DIR.exists():
        return []

    logs = []
    for filepath in sorted(LOG_DIR.glob("*.json"), reverse=True):
        if len(logs) >= limit:
            break
        try:
            with open(filepath) as f:
                entry = json.load(f)
            if photo_id and entry.get("photo_id") != photo_id:
                continue
            if model and entry.get("model") != model:
                continue
            logs.append(entry)
        except (json.JSONDecodeError, OSError):
            continue

    return logs


def get_cost_summary(since: str = None) -> dict:
    """Get cost summary across all logged API calls.

    Args:
        since: ISO timestamp — only count calls after this time.

    Returns:
        Dict with total_cost, total_calls, by_model breakdown.
    """
    logs = load_logs(limit=10000)

    if since:
        logs = [l for l in logs if l.get("timestamp", "") >= since]

    total_cost = sum(l.get("estimated_cost_usd", 0) for l in logs)
    total_calls = len(logs)

    by_model = {}
    for log in logs:
        m = log.get("model", "unknown")
        if m not in by_model:
            by_model[m] = {"calls": 0, "cost": 0, "tokens_in": 0, "tokens_out": 0}
        by_model[m]["calls"] += 1
        by_model[m]["cost"] += log.get("estimated_cost_usd", 0)
        by_model[m]["tokens_in"] += log.get("input_tokens", 0)
        by_model[m]["tokens_out"] += log.get("output_tokens", 0)

    return {
        "total_cost_usd": round(total_cost, 4),
        "total_calls": total_calls,
        "avg_cost_per_call": round(total_cost / total_calls, 6) if total_calls else 0,
        "by_model": by_model,
    }


def get_previous_result(photo_id: str) -> dict | None:
    """Get the most recent analysis result for a photo.

    Returns the parsed response from the most recent log entry,
    or None if no previous analysis exists.
    """
    logs = load_logs(photo_id=photo_id, limit=1)
    if not logs:
        return None

    response = logs[0].get("response", "")
    try:
        return json.loads(response) if isinstance(response, str) else response
    except (json.JSONDecodeError, TypeError):
        return None
