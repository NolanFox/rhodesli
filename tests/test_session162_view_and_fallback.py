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


def test_relationship_routes_no_stale_is_current_filter():
    """Session 164 (PRD-064): the is_current column was DROPPED from
    gedcom_relationships and the current_gedcom_relationships view removed.

    The Session 162 raw-table fallbacks (which filtered .eq("is_current", True))
    no longer apply — the canonical table is current-only. This test guards the
    inverse: relationship reads must NOT reference is_current (a stale reference
    would error now that the column is gone) and must be community-scoped.
    """
    src = (REPO_ROOT / "app" / "relationship_routes.py").read_text()

    # Guard against the actual stale column reference in code (string literal),
    # not the word appearing in explanatory comments.
    assert '"is_current"' not in src, (
        "app/relationship_routes.py must not reference the is_current column after "
        "Session 164 (it was dropped from gedcom_relationships)."
    )
    assert 'table("current_gedcom_relationships")' not in src, (
        "app/relationship_routes.py must not read the dropped "
        "current_gedcom_relationships view after Session 164."
    )

    # Every gedcom_relationships read must be community-scoped.
    rel_reads = re.findall(
        r'(?:sb\.table\("gedcom_relationships"\)|_load_gedcom_rows\(\s*sb\s*,\s*"gedcom_relationships")[\s\S]*?\.execute\(\)|'
        r'_load_gedcom_rows\(\s*sb\s*,\s*"gedcom_relationships"[\s\S]*?\)',
        src,
    )
    assert rel_reads, "Expected at least one gedcom_relationships read in relationship_routes.py"
    for call in rel_reads:
        assert "_GEDCOM_COMMUNITY_ID" in call or "community_id" in call, (
            f"gedcom_relationships read not community-scoped:\n  {call.strip()}"
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
