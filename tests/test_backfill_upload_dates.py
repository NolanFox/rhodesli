"""Tests for scripts/backfill_upload_dates.py."""

import json
from pathlib import Path

from core.photo_registry import PhotoRegistry
from scripts.backfill_upload_dates import (
    apply_backfill,
    backfill_upload_dates,
    extract_job_id,
    infer_upload_metadata,
    plan_backfill,
)


def _write_registry(path: Path) -> None:
    registry = PhotoRegistry()
    registry.register_face("legacy123", "legacy.jpg", "face-1", source="Legacy", collection="Legacy")
    registry.register_face(
        "inbox_job123_0_family_photo",
        "family_photo.jpg",
        "face-2",
        source="Community Upload",
        collection="Community",
    )
    registry.save(path)


def test_extract_job_id_handles_inbox_ids():
    assert extract_job_id("inbox_job123_0_family_photo") == "job123"
    assert extract_job_id("legacy123") is None


def test_infer_upload_metadata_uses_job_history_for_inbox():
    lookup = lambda token: "2026-02-13" if token == "job123" else None
    inferred = infer_upload_metadata("inbox_job123_0_family_photo", git_date_lookup=lookup)
    assert inferred["job_id"] == "job123"
    assert inferred["upload_date"] == "2026-02-13T00:00:00+00:00"


def test_plan_backfill_updates_legacy_and_inbox_fields(tmp_path):
    photo_index = tmp_path / "photo_index.json"
    _write_registry(photo_index)
    registry = PhotoRegistry.load(photo_index)

    lookup = lambda token: "2026-02-14" if token == "job123" else None
    changes = plan_backfill(registry, git_date_lookup=lookup)

    assert len(changes) == 2
    legacy_change = next(c for c in changes if c["photo_id"] == "legacy123")
    inbox_change = next(c for c in changes if c["photo_id"].startswith("inbox_"))
    assert legacy_change["update"] == {"upload_date": "2026-02-10T00:00:00+00:00"}
    assert inbox_change["update"] == {
        "upload_date": "2026-02-14T00:00:00+00:00",
        "job_id": "job123",
    }


def test_apply_backfill_uses_registry_metadata_updates(tmp_path):
    photo_index = tmp_path / "photo_index.json"
    _write_registry(photo_index)
    registry = PhotoRegistry.load(photo_index)

    changes = [
        {"photo_id": "legacy123", "path": "legacy.jpg", "update": {"upload_date": "2026-02-10T00:00:00+00:00"}},
        {
            "photo_id": "inbox_job123_0_family_photo",
            "path": "family_photo.jpg",
            "update": {"upload_date": "2026-02-14T00:00:00+00:00", "job_id": "job123"},
        },
    ]
    applied = apply_backfill(registry, changes)

    assert applied == 2
    assert registry._photos["legacy123"]["upload_date"] == "2026-02-10T00:00:00+00:00"
    assert registry._photos["inbox_job123_0_family_photo"]["job_id"] == "job123"


def test_backfill_upload_dates_dry_run_does_not_modify_file(tmp_path):
    photo_index = tmp_path / "photo_index.json"
    _write_registry(photo_index)
    original = json.loads(photo_index.read_text())

    lookup = lambda token: "2026-02-14" if token == "job123" else None
    updated_count, changes = backfill_upload_dates(photo_index, dry_run=True, git_date_lookup=lookup)

    assert updated_count == 2
    assert len(changes) == 2
    assert json.loads(photo_index.read_text()) == original


def test_backfill_upload_dates_execute_writes_registry_and_backup(tmp_path):
    photo_index = tmp_path / "photo_index.json"
    _write_registry(photo_index)

    lookup = lambda token: "2026-02-14" if token == "job123" else None
    updated_count, changes = backfill_upload_dates(photo_index, dry_run=False, git_date_lookup=lookup)

    assert updated_count == 2
    assert len(changes) == 2

    updated = json.loads(photo_index.read_text())
    assert updated["photos"]["legacy123"]["upload_date"] == "2026-02-10T00:00:00+00:00"
    assert updated["photos"]["inbox_job123_0_family_photo"]["upload_date"] == "2026-02-14T00:00:00+00:00"
    assert updated["photos"]["inbox_job123_0_family_photo"]["job_id"] == "job123"

    backups = list(tmp_path.glob("photo_index.backup_*.json"))
    assert backups
