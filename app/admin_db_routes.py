"""Admin DB-size monitoring endpoint (OD-013, Phase E3).

Exposes `GET /api/admin/db-size` returning current Supabase database size
plus the top-10 tables. Admin-gated via the canonical `_check_admin` helper.

Usage from `app/main.py`:

    from app.admin_db_routes import register_admin_db_routes
    register_admin_db_routes(app)

The route is registered only when `register_admin_db_routes(app)` is called.
The orchestrator (main thread) wires this in to avoid file-conflict with
parallel tracks that also edit `app/main.py`.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


def _query_db_size() -> dict[str, Any]:
    """Run the size queries against Supabase via session pooler.

    Returns a dict with keys:
      - total_bytes: int
      - total_pretty: str
      - top_tables: list of {name, bytes, pretty}
      - error: str (only if a fatal error occurred)
    """
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return {"error": "psycopg2 not installed"}

    project_ref = os.environ.get("SUPABASE_PROJECT_REF", "fvynibivlphxwfowzkjl")
    password = os.environ.get("SUPABASE_DB_PASSWORD")
    if not password:
        return {"error": "SUPABASE_DB_PASSWORD not set"}

    try:
        conn = psycopg2.connect(
            host="aws-0-us-west-2.pooler.supabase.com",
            port=5432,
            user=f"postgres.{project_ref}",
            password=password,
            dbname="postgres",
            connect_timeout=10,
            sslmode="require",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("admin db-size: connect failed: %s", exc)
        return {"error": f"connect failed: {exc}"}

    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT pg_database_size('postgres') AS bytes")
            total_bytes = int(cur.fetchone()["bytes"])

            cur.execute("SELECT pg_size_pretty(%s) AS pretty", (total_bytes,))
            total_pretty = cur.fetchone()["pretty"]

            cur.execute(
                """
                SELECT relname AS name,
                       pg_total_relation_size(relid) AS bytes,
                       pg_size_pretty(pg_total_relation_size(relid)) AS pretty,
                       n_live_tup AS approx_rows
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(relid) DESC
                LIMIT 10
                """
            )
            tables = [dict(r) for r in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001
        logger.warning("admin db-size: query failed: %s", exc)
        return {"error": f"query failed: {exc}"}
    finally:
        conn.close()

    # Convert bytes (Decimal) to plain int for JSON serialization
    for t in tables:
        t["bytes"] = int(t["bytes"])
        if t.get("approx_rows") is not None:
            t["approx_rows"] = int(t["approx_rows"])

    return {
        "total_bytes": total_bytes,
        "total_pretty": total_pretty,
        "top_tables": tables,
    }


def register_admin_db_routes(app) -> None:
    """Register `/api/admin/db-size` on the given FastHTML app.

    Imports `_check_admin` lazily to avoid a circular import at module load.
    """

    @app.get("/api/admin/db-size")
    def db_size_endpoint(sess):
        # Lazy import to avoid circular dep — app.main imports this module
        # back via register_admin_db_routes(app) at startup.
        from app.main import _check_admin  # noqa: PLC0415

        guard = _check_admin(sess)
        if guard is not None:
            return guard

        result = _query_db_size()
        # Surface error path with 503; don't leak credentials in the message.
        if "error" in result:
            safe_msg = result["error"]
            if "password" in safe_msg.lower() or "auth" in safe_msg.lower():
                safe_msg = "supabase admin connection failed"
            return JSONResponse({"error": safe_msg}, status_code=503)

        # Add OD-013 thresholds inline so the consumer can render a status.
        WARN_BYTES = 800 * 1024 * 1024
        CRITICAL_BYTES = 1_000 * 1024 * 1024
        CEILING_BYTES = 1_100 * 1024 * 1024
        if result["total_bytes"] >= CEILING_BYTES:
            status = "ceiling"
        elif result["total_bytes"] >= CRITICAL_BYTES:
            status = "critical"
        elif result["total_bytes"] >= WARN_BYTES:
            status = "warn"
        else:
            status = "ok"

        return JSONResponse({
            "total_bytes": result["total_bytes"],
            "total_pretty": result["total_pretty"],
            "top_tables": result["top_tables"],
            "thresholds": {
                "warn_bytes": WARN_BYTES,
                "critical_bytes": CRITICAL_BYTES,
                "ceiling_bytes": CEILING_BYTES,
            },
            "status": status,
        })
