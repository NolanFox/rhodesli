"""Session 162 regression guards.

Two structural guards baked in:

1. Static guard against the bad WHERE clause in the forward migration SQL —
   if anyone reintroduces ``OR is_current IS NULL`` in
   ``scripts/session162a_replace_view.sql`` we fail the test fast.

2. Static guard against the raw-table fallback paths in
   ``app/relationship_routes.py`` losing their ``is_current = true`` filter.
   The two known fallback sites are at the lines added in Session 162 Phase 1a.

A live-DB guard (verifies ``pg_get_viewdef``) is opt-in via the
``RUN_LIVE_DB_TESTS=1`` env var and skipped in offline CI to avoid coupling
test runs to Supabase availability.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_session162_forward_sql_drops_or_is_null():
    """The migration SQL must not contain the bad ``OR is_current IS NULL`` clause."""
    sql_path = REPO_ROOT / "scripts" / "session162a_replace_view.sql"
    assert sql_path.exists(), f"missing forward migration: {sql_path}"
    sql = sql_path.read_text()
    body = sql.split("CREATE OR REPLACE VIEW current_gedcom_relationships", 1)[1]
    assert "is_current IS NULL" not in body, (
        "Session 162 view definition must NOT contain 'is_current IS NULL' — "
        "that clause defeats idx_gedcom_relationships_current."
    )
    assert "is_current = true" in body, (
        "Session 162 view must still filter to current rows via is_current = true."
    )


def test_relationship_routes_fallback_filters_is_current():
    """Both raw-table fallbacks in app/relationship_routes.py MUST filter is_current = true.

    Without the filter, a PostgREST schema-cache flake silently re-introduces
    the same IO regression we're closing in Session 162.
    """
    src = (REPO_ROOT / "app" / "relationship_routes.py").read_text()

    # Match multi-line chained Supabase calls — each fluent call may span
    # several lines via Python implicit continuation inside parens.
    raw_table_fallbacks = re.findall(
        r'sb\.table\("gedcom_relationships"\)(?:\s*\.\w+\([^)]*\))+\s*\.execute\(\)',
        src,
        flags=re.DOTALL,
    )
    fallback_via_helper = re.findall(
        r'_load_gedcom_rows\(\s*sb\s*,\s*"gedcom_relationships"[\s\S]*?\)',
        src,
    )

    assert raw_table_fallbacks or fallback_via_helper, (
        "Expected at least one raw-table fallback in relationship_routes.py; "
        "if you removed them entirely that's also fine — delete this assertion."
    )

    for call in raw_table_fallbacks:
        assert '.eq("is_current", True)' in call, (
            f"Raw-table fallback missing .eq('is_current', True):\n  {call.strip()}"
        )

    for call in fallback_via_helper:
        assert 'filters={"is_current": True}' in call, (
            f"Raw-table helper fallback missing filters=is_current=True:\n  {call.strip()}"
        )


def test_session162b_sql_does_not_drop_not_null():
    """The Phase 1b migration SQL must SET NOT NULL — never DROP NOT NULL.

    Cheap structural guard to prevent a future contributor "fixing" a perceived
    NULL bug by reverting the constraint and re-defeating the partial index.
    """
    sql_path = REPO_ROOT / "scripts" / "session162b_set_not_null.sql"
    assert sql_path.exists(), f"missing Phase 1b migration: {sql_path}"
    sql = sql_path.read_text()
    assert "SET NOT NULL" in sql, "Phase 1b SQL must add NOT NULL constraint"
    assert "DROP NOT NULL" not in sql, (
        "Phase 1b SQL must NOT contain DROP NOT NULL — that's a rollback, "
        "which belongs in a separate companion script if needed."
    )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="Live-DB introspection skipped unless RUN_LIVE_DB_TESTS=1",
)
def test_live_view_definition_uses_partial_index_predicate():
    """When RUN_LIVE_DB_TESTS=1, verify pg_get_viewdef matches the new definition.

    Requires SUPABASE_DB_PASSWORD in env; uses the us-west-2 pooler.
    """
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    import psycopg2  # type: ignore

    project_ref = "fvynibivlphxwfowzkjl"
    conn = psycopg2.connect(
        host="aws-0-us-west-2.pooler.supabase.com",
        port=5432,
        dbname="postgres",
        user=f"postgres.{project_ref}",
        password=os.environ["SUPABASE_DB_PASSWORD"],
        connect_timeout=10,
        sslmode="require",
    )
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT pg_get_viewdef('current_gedcom_relationships'::regclass, true)"
        )
        viewdef = cur.fetchone()[0]
        assert "is_current IS NULL" not in viewdef, (
            "Live view still has IS NULL clause — Phase 1a regressed."
        )
        assert "is_current = true" in viewdef, (
            "Live view missing is_current = true filter."
        )
    finally:
        conn.close()
