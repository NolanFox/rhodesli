from pathlib import Path
from unittest.mock import patch

from app.main import log_user_action


def test_log_user_action_dual_writes_to_supabase(tmp_path):
    with patch("app.main.logs_path", tmp_path), patch("app.supabase_data.sync_audit_log_entry") as sync_mock:
        log_user_action(
            "RENAME_IDENTITY",
            identity_id="person-1",
            admin="admin@example.com",
            previous_name="Old Name",
            new_name="New Name",
        )

    log_file = tmp_path / "user_actions.log"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "RENAME_IDENTITY" in contents
    assert "identity_id=person-1" in contents

    assert sync_mock.called
    kwargs = sync_mock.call_args.kwargs
    assert kwargs["action"] == "RENAME_IDENTITY"
    assert kwargs["target_id"] == "person-1"
    assert kwargs["actor"] == "admin@example.com"
    assert kwargs["target_type"] == "identity_action"
    assert kwargs["entry_data"]["new_name"] == "New Name"


def test_photo_metadata_routes_include_audit_logging():
    source = Path("app/page_routes.py").read_text(encoding="utf-8")
    assert "UPDATE_PHOTO_COLLECTION" in source
    assert "previous_collection" in source
    assert "new_collection" in source
    assert "UPDATE_PHOTO_SOURCE" in source
    assert "previous_source" in source
    assert "new_source" in source
    assert "UPDATE_PHOTO_SOURCE_URL" in source
    assert "previous_source_url" in source
    assert "new_source_url" in source


def test_identity_routes_include_rename_audit_logging():
    source = Path("app/identity_routes.py").read_text(encoding="utf-8")
    assert '"RENAME_IDENTITY"' in source
    assert 'source="web"' in source
    assert 'source="face_tag"' in source
    assert 'source="admin_web"' in source
