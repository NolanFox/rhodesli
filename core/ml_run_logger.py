"""ML Run Logger — Standardized provenance tracking for ML pipeline runs.

Every ML pipeline execution (clustering, cross-batch matching, calibration,
face detection, etc.) should log to the ml_runs table with full provenance:
- What environment ran it (local laptop, Railway web, Railway ML service)
- What ML models and versions were used
- What community/scope it targeted
- Duration and result summary

Usage:
    from core.ml_run_logger import log_ml_run, complete_ml_run, fail_ml_run

    run_id = log_ml_run(
        supabase_client=client,
        pipeline_type="clustering",
        config={"threshold": 1.05, "algorithm": "complete_linkage"},
        triggered_by="upload_webhook",
        community_id="uuid-of-community",
    )
    try:
        result = run_pipeline(...)
        complete_ml_run(client, run_id, result_summary={"proposals": 42}, duration_ms=1234)
    except Exception as e:
        fail_ml_run(client, run_id, error=str(e), duration_ms=1234)

Schema (AD-227, Session 115):
    ml_runs table columns:
    - run_id UUID (PK)
    - created_at TIMESTAMPTZ
    - pipeline_type TEXT (clustering, cross_batch, calibration, detection, etc.)
    - config_json JSONB
    - status TEXT (running, completed, failed)
    - result_summary JSONB
    - duration_ms INT
    - triggered_by TEXT (manual, upload_webhook, scheduled, admin_recluster)
    - parent_run_id UUID (FK to ml_runs for sub-runs)
    - execution_environment TEXT (local_laptop, railway_web, railway_ml_service, ci, test)
    - model_versions JSONB ({"insightface": "0.7.3", "buffalo": "buffalo_l", ...})
    - community_id UUID (NULL = global/cross-community)
    - scope_filter JSONB ({"photo_ids": [...]} or {"batch_id": "..."} or NULL = full population)
"""

import logging
import os
import time

logger = logging.getLogger(__name__)


def get_execution_environment() -> str:
    """Detect the current execution environment from env vars."""
    return os.getenv("EXECUTION_ENVIRONMENT", "local_laptop")


def get_model_versions() -> dict:
    """Detect installed ML model versions at runtime.

    Returns a dict of model name → version string. Gracefully handles
    missing packages (e.g., when running on web-only Railway service).
    """
    versions = {}
    try:
        import insightface

        versions["insightface"] = insightface.__version__
    except ImportError:
        pass

    try:
        import onnxruntime

        versions["onnxruntime"] = onnxruntime.__version__
    except ImportError:
        pass

    try:
        import numpy

        versions["numpy"] = numpy.__version__
    except ImportError:
        pass

    # Add detection model info if InsightFace is available
    if "insightface" in versions:
        versions["detection_model"] = os.getenv("INSIGHTFACE_MODEL", "buffalo_l")

    return versions


def log_ml_run(
    supabase_client,
    pipeline_type: str,
    config: dict | None = None,
    triggered_by: str = "manual",
    community_id: str | None = None,
    scope_filter: dict | None = None,
    parent_run_id: str | None = None,
) -> str | None:
    """Create an ml_runs record with full provenance. Returns run_id.

    Args:
        supabase_client: Supabase client instance
        pipeline_type: Type of pipeline (clustering, cross_batch, calibration,
                       detection, batch_gemini, recalibration, etc.)
        config: Pipeline-specific configuration dict
        triggered_by: What triggered this run (manual, upload_webhook,
                      scheduled, admin_recluster, test)
        community_id: UUID of target community (None = global/cross-community)
        scope_filter: Fine-grained targeting dict:
                      {"photo_ids": [...]}  — specific photos
                      {"identity_ids": [...]}  — specific identities
                      {"batch_id": "..."}  — specific upload batch
                      {"exclude_confirmed": true}  — skip confirmed
                      None = entire population for community_id
        parent_run_id: UUID of parent run (for sub-runs)

    Returns:
        run_id string if successful, None if logging failed
    """
    if supabase_client is None:
        logger.warning("No Supabase client — ml_run not logged")
        return None

    run_data = {
        "pipeline_type": pipeline_type,
        "config_json": config or {},
        "triggered_by": triggered_by,
        "status": "running",
        "execution_environment": get_execution_environment(),
        "model_versions": get_model_versions(),
    }

    # Only include nullable fields if set (avoids Supabase column errors if migration hasn't run)
    if community_id is not None:
        run_data["community_id"] = community_id
    if scope_filter is not None:
        run_data["scope_filter"] = scope_filter
    if parent_run_id is not None:
        run_data["parent_run_id"] = parent_run_id

    try:
        result = supabase_client.table("ml_runs").insert(run_data).execute()
        if result.data:
            run_id = result.data[0]["run_id"]
            logger.info(
                "ML run started: %s pipeline=%s env=%s community=%s",
                run_id,
                pipeline_type,
                run_data["execution_environment"],
                community_id or "global",
            )
            return run_id
    except Exception as e:
        logger.error("Failed to log ml_run: %s", e)

    return None


def complete_ml_run(
    supabase_client,
    run_id: str,
    result_summary: dict,
    duration_ms: int,
) -> bool:
    """Mark an ml_run as completed with results.

    Args:
        supabase_client: Supabase client instance
        run_id: The run_id returned by log_ml_run()
        result_summary: Dict of output metrics (proposals_count, matches_found, etc.)
        duration_ms: Total execution time in milliseconds

    Returns:
        True if update succeeded, False otherwise
    """
    if supabase_client is None or run_id is None:
        return False

    try:
        supabase_client.table("ml_runs").update(
            {
                "status": "completed",
                "result_summary": result_summary,
                "duration_ms": duration_ms,
            }
        ).eq("run_id", run_id).execute()
        logger.info("ML run completed: %s duration=%dms", run_id, duration_ms)
        return True
    except Exception as e:
        logger.error("Failed to complete ml_run %s: %s", run_id, e)
        return False


def fail_ml_run(
    supabase_client,
    run_id: str,
    error: str,
    duration_ms: int,
) -> bool:
    """Mark an ml_run as failed with error details.

    Args:
        supabase_client: Supabase client instance
        run_id: The run_id returned by log_ml_run()
        error: Error message or traceback summary
        duration_ms: Total execution time in milliseconds

    Returns:
        True if update succeeded, False otherwise
    """
    if supabase_client is None or run_id is None:
        return False

    try:
        supabase_client.table("ml_runs").update(
            {
                "status": "failed",
                "result_summary": {"error": error},
                "duration_ms": duration_ms,
            }
        ).eq("run_id", run_id).execute()
        logger.warning("ML run failed: %s error=%s", run_id, error)
        return True
    except Exception as e:
        logger.error("Failed to record ml_run failure %s: %s", run_id, e)
        return False


class MLRunContext:
    """Context manager for ML pipeline runs with automatic timing and status.

    Usage:
        with MLRunContext(client, "clustering", config={...}) as run:
            result = run_pipeline(...)
            run.set_result({"proposals": 42})
        # Automatically sets status=completed with duration

        # Or on failure:
        with MLRunContext(client, "clustering") as run:
            raise ValueError("bad data")
        # Automatically sets status=failed with error
    """

    def __init__(
        self,
        supabase_client,
        pipeline_type: str,
        config: dict | None = None,
        triggered_by: str = "manual",
        community_id: str | None = None,
        scope_filter: dict | None = None,
        parent_run_id: str | None = None,
    ):
        self.client = supabase_client
        self.pipeline_type = pipeline_type
        self.config = config
        self.triggered_by = triggered_by
        self.community_id = community_id
        self.scope_filter = scope_filter
        self.parent_run_id = parent_run_id
        self.run_id = None
        self._start_time = None
        self._result_summary = {}

    def __enter__(self):
        self._start_time = time.time()
        self.run_id = log_ml_run(
            self.client,
            pipeline_type=self.pipeline_type,
            config=self.config,
            triggered_by=self.triggered_by,
            community_id=self.community_id,
            scope_filter=self.scope_filter,
            parent_run_id=self.parent_run_id,
        )
        return self

    def set_result(self, result_summary: dict):
        """Set the result summary for this run."""
        self._result_summary = result_summary

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self._start_time) * 1000)
        if exc_type is not None:
            fail_ml_run(self.client, self.run_id, str(exc_val), duration_ms)
        else:
            complete_ml_run(self.client, self.run_id, self._result_summary, duration_ms)
        return False  # Don't suppress exceptions
