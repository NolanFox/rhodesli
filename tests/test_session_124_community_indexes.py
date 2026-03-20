"""Tests for Session 124 community index SQL."""

from pathlib import Path


def test_community_indexes_sql_exists():
    sql_file = Path("scripts/sql/session_124_community_indexes.sql")
    assert sql_file.exists(), "Community indexes SQL file missing"
    content = sql_file.read_text()
    assert "idx_photo_communities_community_id" in content
    assert "idx_identity_communities_community_id" in content
    assert "CREATE INDEX IF NOT EXISTS" in content
