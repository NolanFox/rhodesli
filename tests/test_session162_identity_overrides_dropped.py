"""Session 162 Phase 3 — regression guards for identity_overrides DROP.

Static guards run in offline CI. The live-DB guard requires RUN_LIVE_DB_TESTS=1.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_no_active_python_queries_identity_overrides():
    """No live-code .table('identity_overrides') queries.

    Allow exceptions for:
    - Deprecation stubs in app/supabase_data.py (kept for backwards-compat)
    - tests/ that enforce the invariant
    - scripts/_archive/ (intentionally retired callers)
    - Comments and docstrings (text-only references)
    """
    allowed_prefixes = (
        "scripts/_archive/",
    )
    allowed_files = {
        "app/supabase_data.py",
        "tests/test_data_layer_invariants.py",
        "tests/test_session162_identity_overrides_dropped.py",
        "tests/test_session162_view_and_fallback.py",
    }
    py_files = list(REPO_ROOT.glob("app/**/*.py")) + list(REPO_ROOT.glob("scripts/**/*.py"))

    offenders = []
    for f in py_files:
        rel = f.relative_to(REPO_ROOT).as_posix()
        if rel in allowed_files or any(rel.startswith(p) for p in allowed_prefixes):
            continue
        src = f.read_text()
        for line_no, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Live query patterns: .table("identity_overrides") or .from_("identity_overrides")
            if re.search(r'\.(table|from_)\(\s*[\'"]identity_overrides[\'"]', stripped):
                offenders.append(f"{rel}:{line_no}: {stripped[:120]}")

    assert not offenders, (
        "Live code in app/ or scripts/ still queries identity_overrides:\n"
        + "\n".join(offenders)
        + "\n\nThe table was DROPped in Session 162 (OD-014). Either remove the "
        + "call, or move the file under scripts/_archive/."
    )


def test_migrate_to_supabase_archived():
    """The Session 59C one-shot migration tool must not be at scripts/migrate_to_supabase.py.

    It writes to identity_overrides and would error post-DROP.
    """
    live = REPO_ROOT / "scripts" / "migrate_to_supabase.py"
    archived = REPO_ROOT / "scripts" / "_archive" / "migrate_to_supabase_session59C.py"
    assert not live.exists(), (
        f"{live} should be archived to scripts/_archive/ — it writes to identity_overrides"
    )
    assert archived.exists(), f"expected archived copy at {archived}"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="Live-DB introspection skipped unless RUN_LIVE_DB_TESTS=1",
)
def test_live_identity_overrides_absent():
    """When RUN_LIVE_DB_TESTS=1, verify identity_overrides is absent from Supabase."""
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
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='identity_overrides')"
        )
        exists = cur.fetchone()[0]
        assert not exists, "Live identity_overrides still exists — Phase 3 regressed"
    finally:
        conn.close()
