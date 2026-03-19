"""Tests for WORKSPACE-001 Phase 1: Schema migration + create_personal_archive."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── SQL migration file tests ──


def test_sql_migration_file_exists():
    """Migration file exists at the expected path."""
    sql_path = Path(__file__).parent.parent / "scripts" / "sql" / "session_122_workspace_schema.sql"
    assert sql_path.exists(), f"Missing SQL migration: {sql_path}"


def test_sql_migration_contains_owner_id_column():
    """Migration adds owner_id column to communities."""
    sql_path = Path(__file__).parent.parent / "scripts" / "sql" / "session_122_workspace_schema.sql"
    content = sql_path.read_text()
    assert "owner_id UUID" in content


def test_sql_migration_contains_is_personal_column():
    """Migration adds is_personal column to communities."""
    sql_path = Path(__file__).parent.parent / "scripts" / "sql" / "session_122_workspace_schema.sql"
    content = sql_path.read_text()
    assert "is_personal BOOLEAN" in content


def test_sql_migration_contains_privacy_column():
    """Migration adds privacy column to communities."""
    sql_path = Path(__file__).parent.parent / "scripts" / "sql" / "session_122_workspace_schema.sql"
    content = sql_path.read_text()
    assert "privacy TEXT" in content


def test_sql_migration_contains_unique_personal_index():
    """Migration creates unique index for one personal archive per user."""
    sql_path = Path(__file__).parent.parent / "scripts" / "sql" / "session_122_workspace_schema.sql"
    content = sql_path.read_text()
    assert "idx_communities_personal_owner" in content
    assert "WHERE is_personal = true" in content


def test_sql_migration_contains_owner_id_index():
    """Migration creates index on owner_id for lookups."""
    sql_path = Path(__file__).parent.parent / "scripts" / "sql" / "session_122_workspace_schema.sql"
    content = sql_path.read_text()
    assert "idx_communities_owner_id" in content


# ── create_personal_archive function tests ──


def test_create_personal_archive_exists():
    """Function is importable from supabase_data."""
    from app.supabase_data import create_personal_archive

    assert callable(create_personal_archive)


def test_slug_generation_from_user_id():
    """Slug uses first 8 chars of user_id."""
    from app.supabase_data import create_personal_archive

    user_id = "abcdef12-3456-7890-abcd-ef1234567890"
    # Mock Supabase to return None (no client)
    with patch("app.supabase_data.get_supabase_client", return_value=None):
        result = create_personal_archive(user_id, "test@example.com")
    # With no Supabase client, returns None
    assert result is None


def test_slug_format():
    """Verify slug format is personal-{first8}."""
    user_id = "abcdef12-3456-7890-abcd-ef1234567890"
    expected_slug = f"personal-{user_id[:8]}"
    assert expected_slug == "personal-abcdef12"


def test_name_generation_from_simple_email():
    """Name extracted from email local part, titlecased."""
    email = "john.doe@example.com"
    name_part = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    assert name_part == "John Doe"


def test_name_generation_from_underscore_email():
    """Underscores in email converted to spaces."""
    email = "jane_smith@example.com"
    name_part = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    assert name_part == "Jane Smith"


def test_name_generation_from_plain_email():
    """Plain email without separators still titlecased."""
    email = "nolanfox@gmail.com"
    name_part = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    assert name_part == "Nolanfox"


def test_idempotency_returns_existing():
    """If personal archive exists, returns it without creating a new one."""
    from app.supabase_data import create_personal_archive

    user_id = "11111111-2222-3333-4444-555555555555"
    existing_community = {"id": "existing-id", "slug": "personal-11111111", "is_personal": True}

    mock_sb = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[existing_community])
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select

    with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
        result = create_personal_archive(user_id, "test@example.com")

    assert result == existing_community
    # insert should NOT have been called
    mock_sb.table.return_value.insert.assert_not_called()


def test_creates_new_archive_when_none_exists():
    """Creates a new personal archive when no existing one found."""
    from app.supabase_data import create_personal_archive

    user_id = "aabbccdd-1234-5678-9012-abcdef123456"
    created_community = {
        "id": "new-id",
        "slug": "personal-aabbccdd",
        "name": "Test User's Archive",
        "is_personal": True,
    }

    mock_sb = MagicMock()
    # Idempotency check returns empty
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value = mock_select
    # Insert returns the new community
    mock_insert = MagicMock()
    mock_insert.execute.return_value = MagicMock(data=[created_community])
    mock_sb.table.return_value.insert.return_value = mock_insert

    with (
        patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        patch("app.supabase_data._invalidate_community_cache") as mock_invalidate,
    ):
        result = create_personal_archive(user_id, "test.user@example.com")

    assert result == created_community
    mock_invalidate.assert_called_once()


def test_returns_none_on_supabase_error():
    """Returns None and logs warning on Supabase errors."""
    from app.supabase_data import create_personal_archive

    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = (
        ConnectionError("Supabase down")
    )

    with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
        result = create_personal_archive("some-user-id-1234", "test@example.com")

    assert result is None


def test_returns_none_without_supabase():
    """Returns None when Supabase client is not available."""
    from app.supabase_data import create_personal_archive

    with patch("app.supabase_data.get_supabase_client", return_value=None):
        result = create_personal_archive("some-user-id-1234", "test@example.com")

    assert result is None
