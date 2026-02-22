"""MLflow experiment tracking for Gemini API calls and model comparisons.

Provides structured experiment tracking for:
- Individual Gemini API calls (date estimation, progressive refinement)
- Flash vs Pro model comparison runs
- Cost tracking across experiments

Storage: Local MLflow tracking at rhodesli_ml/mlruns/
See AD-140 for tracking strategy rationale.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

MLFLOW_DIR = str(Path(__file__).resolve().parent / "mlruns")

# Experiment names
EXPERIMENT_DATE_ESTIMATION = "rhodesli-date-estimation"
EXPERIMENT_MODEL_COMPARISON = "rhodesli-model-comparison"


def _get_mlflow():
    """Lazy import mlflow to avoid startup cost."""
    import mlflow
    return mlflow


def init_tracking(experiment_name: str = EXPERIMENT_DATE_ESTIMATION):
    """Initialize MLflow tracking with local file store."""
    mlflow = _get_mlflow()
    mlflow.set_tracking_uri(f"file://{MLFLOW_DIR}")
    mlflow.set_experiment(experiment_name)


def log_gemini_call(
    photo_id: str,
    model: str,
    prompt_text: str,
    response_text: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    verified_facts: dict | None = None,
    metadata: dict | None = None,
):
    """Log a single Gemini API call to MLflow.

    Args:
        photo_id: Photo identifier.
        model: Gemini model string.
        prompt_text: Full prompt sent to API.
        response_text: Raw response text.
        input_tokens: Input token count.
        output_tokens: Output token count.
        cost_usd: Estimated cost in USD.
        verified_facts: Dict of verified facts used in enriched prompt.
        metadata: Additional metadata dict.
    """
    mlflow = _get_mlflow()
    init_tracking(EXPERIMENT_DATE_ESTIMATION)

    run_name = f"{model}-{photo_id[:8]}-{datetime.now(timezone.utc).strftime('%H%M%S')}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("model", model)
        mlflow.log_param("photo_id", photo_id)
        mlflow.log_param("prompt_length", len(prompt_text))
        mlflow.log_param("timestamp", datetime.now(timezone.utc).isoformat())

        if verified_facts:
            fact_count = (
                len(verified_facts.get("confirmed_people", []))
                + len(verified_facts.get("birth_years", {}))
                + len(verified_facts.get("relationships", []))
                + len(verified_facts.get("annotations", []))
            )
            mlflow.log_param("has_enriched_prompt", True)
            mlflow.log_metric("verified_fact_count", fact_count)
        else:
            mlflow.log_param("has_enriched_prompt", False)

        if response_text:
            mlflow.log_param("response_length", len(response_text))
            try:
                result = json.loads(response_text) if isinstance(response_text, str) else response_text
                if result.get("best_year_estimate"):
                    mlflow.log_metric("estimated_year", result["best_year_estimate"])
                if result.get("estimated_decade"):
                    mlflow.log_metric("estimated_decade", result["estimated_decade"])
                confidence_map = {"high": 3, "medium": 2, "low": 1}
                if result.get("confidence") in confidence_map:
                    mlflow.log_metric("confidence_score", confidence_map[result["confidence"]])
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        mlflow.log_metric("input_tokens", input_tokens)
        mlflow.log_metric("output_tokens", output_tokens)
        mlflow.log_metric("cost_usd", cost_usd)

        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(f"meta_{k}", v)
                else:
                    mlflow.log_param(f"meta_{k}", str(v)[:250])


def log_model_comparison(
    model_a: str,
    model_b: str,
    results_a: dict,
    results_b: dict,
    photo_ids: list[str],
):
    """Log a Flash vs Pro comparison run to MLflow.

    Args:
        model_a: First model name.
        model_b: Second model name.
        results_a: Dict of photo_id -> result for model A.
        results_b: Dict of photo_id -> result for model B.
        photo_ids: List of photo IDs compared.
    """
    mlflow = _get_mlflow()
    init_tracking(EXPERIMENT_MODEL_COMPARISON)

    run_name = f"compare-{model_a[:20]}-vs-{model_b[:20]}"

    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("model_a", model_a)
        mlflow.log_param("model_b", model_b)
        mlflow.log_param("photo_count", len(photo_ids))
        mlflow.log_param("timestamp", datetime.now(timezone.utc).isoformat())

        # Decade agreement
        both_valid = [
            pid for pid in photo_ids
            if pid in results_a and pid in results_b
            and results_a[pid] is not None and results_b[pid] is not None
        ]
        if both_valid:
            agreements = sum(
                1 for pid in both_valid
                if results_a[pid].get("estimated_decade") == results_b[pid].get("estimated_decade")
            )
            mlflow.log_metric("decade_agreement_rate", agreements / len(both_valid))
            mlflow.log_metric("photos_compared", len(both_valid))
            mlflow.log_metric("decade_agreements", agreements)

            # Confidence comparison
            conf_map = {"high": 3, "medium": 2, "low": 1}
            a_conf = [conf_map.get(results_a[pid].get("confidence"), 0) for pid in both_valid]
            b_conf = [conf_map.get(results_b[pid].get("confidence"), 0) for pid in both_valid]
            if a_conf:
                mlflow.log_metric("avg_confidence_a", sum(a_conf) / len(a_conf))
                mlflow.log_metric("avg_confidence_b", sum(b_conf) / len(b_conf))

        # Save full comparison as artifact
        comparison = {
            "model_a": model_a,
            "model_b": model_b,
            "photo_ids": photo_ids,
            "results_a": {pid: results_a.get(pid) for pid in photo_ids},
            "results_b": {pid: results_b.get(pid) for pid in photo_ids},
        }
        artifact_path = Path("/tmp/mlflow_comparison.json")
        with open(artifact_path, "w") as f:
            json.dump(comparison, f, indent=2, default=str)
        mlflow.log_artifact(str(artifact_path))
