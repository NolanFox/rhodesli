"""Track and report Gemini API costs per labeling run."""
import json
import os
from datetime import datetime, timezone

COST_LOG = "rhodesli_ml/data/api_cost_log.json"

# Pricing per 1M tokens (update these when models change)
MODEL_PRICING = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-3-pro-preview": {"input": 1.25, "output": 5.00},
    "gemini-3-flash-preview": {"input": 0.15, "output": 0.60},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = MODEL_PRICING.get(model, {"input": 1.25, "output": 5.00})
    return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000


def log_api_call(model: str, photo_id: str, input_tokens: int, output_tokens: int):
    cost = estimate_cost(model, input_tokens, output_tokens)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "photo_id": photo_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": cost,
    }

    log = []
    if os.path.exists(COST_LOG):
        with open(COST_LOG) as f:
            log = json.load(f)
    log.append(entry)
    os.makedirs(os.path.dirname(COST_LOG), exist_ok=True)
    with open(COST_LOG, "w") as f:
        json.dump(log, f, indent=2)
    return cost


def get_session_total() -> dict:
    if not os.path.exists(COST_LOG):
        return {"total_cost": 0, "total_calls": 0}
    with open(COST_LOG) as f:
        log = json.load(f)
    total = sum(e["estimated_cost"] for e in log)
    return {
        "total_cost": total,
        "total_calls": len(log),
        "avg_cost_per_photo": total / len(log) if log else 0,
    }


def check_cost_spike(cost: float, model: str, threshold_multiplier: float = 3.0) -> bool:
    """Return True if this call's cost is suspiciously high."""
    if not os.path.exists(COST_LOG):
        return False
    with open(COST_LOG) as f:
        log = json.load(f)
    same_model = [e for e in log if e["model"] == model]
    if len(same_model) < 2:
        return False
    avg = sum(e["estimated_cost"] for e in same_model) / len(same_model)
    return cost > avg * threshold_multiplier
