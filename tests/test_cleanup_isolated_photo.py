import json
from pathlib import Path

import pytest


def _write_registry_payload(path: Path, photos: dict, face_to_photo: dict) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "photos": photos,
                "face_to_photo": face_to_photo,
            },
            indent=2,
        )
    )


def test_cleanup_isolated_photo_dry_run_keeps_files_unchanged(tmp_path):
    from scripts.cleanup_isolated_photo import cleanup_isolated_photo

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_registry_payload(
        data_dir / "photo_index.json",
        photos={
            "photo_keep": {
                "path": "raw_photos/shared.jpg",
                "face_ids": ["face_keep"],
                "source": "Archive",
                "collection": "Family Album",
                "source_url": "",
            },
            "photo_drop": {
                "path": "raw_photos/shared.jpg",
                "face_ids": ["face_drop"],
                "source": "Test Session",
                "collection": "Test Upload",
                "source_url": "",
            },
        },
        face_to_photo={"face_keep": "photo_keep", "face_drop": "photo_drop"},
    )
    (data_dir / "identities.json").write_text(json.dumps({"identities": {}, "history": []}))
    (data_dir / "annotations.json").write_text(json.dumps({"annotations": {}}))
    (data_dir / "orphaned_face_ids.json").write_text(
        json.dumps({"schema_version": 1, "orphaned_face_ids": [], "last_updated": None})
    )

    before = (data_dir / "photo_index.json").read_text()
    summary = cleanup_isolated_photo("photo_drop", data_dir=data_dir, dry_run=True)

    assert summary["face_ids_orphaned"] == ["face_drop"]
    assert summary["shared_photo_ids"] == ["photo_keep"]
    assert (data_dir / "photo_index.json").read_text() == before


def test_cleanup_isolated_photo_execute_removes_photo_and_tracks_orphan(tmp_path):
    from scripts.cleanup_isolated_photo import cleanup_isolated_photo

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_registry_payload(
        data_dir / "photo_index.json",
        photos={
            "photo_keep": {
                "path": "raw_photos/shared.jpg",
                "face_ids": ["face_keep"],
                "source": "Archive",
                "collection": "Family Album",
                "source_url": "",
            },
            "photo_drop": {
                "path": "raw_photos/shared.jpg",
                "face_ids": ["face_drop"],
                "source": "Test Session",
                "collection": "Test Upload",
                "source_url": "",
            },
        },
        face_to_photo={"face_keep": "photo_keep", "face_drop": "photo_drop"},
    )
    (data_dir / "identities.json").write_text(json.dumps({"identities": {}, "history": []}))
    (data_dir / "annotations.json").write_text(json.dumps({"annotations": {}}))
    (data_dir / "orphaned_face_ids.json").write_text(
        json.dumps({"schema_version": 1, "orphaned_face_ids": ["existing_face"], "last_updated": None})
    )

    summary = cleanup_isolated_photo("photo_drop", data_dir=data_dir, dry_run=False)

    registry = json.loads((data_dir / "photo_index.json").read_text())
    assert "photo_drop" not in registry["photos"]
    assert "face_drop" not in registry["face_to_photo"]
    assert "photo_keep" in registry["photos"]

    orphan_data = json.loads((data_dir / "orphaned_face_ids.json").read_text())
    assert orphan_data["orphaned_face_ids"] == ["existing_face", "face_drop"]
    assert summary["backup_path"] is not None
    assert Path(summary["backup_path"]).exists()


def test_cleanup_isolated_photo_refuses_identity_references(tmp_path):
    from scripts.cleanup_isolated_photo import cleanup_isolated_photo

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_registry_payload(
        data_dir / "photo_index.json",
        photos={
            "photo_keep": {
                "path": "raw_photos/shared.jpg",
                "face_ids": ["face_keep"],
                "source": "Archive",
                "collection": "Family Album",
                "source_url": "",
            },
            "photo_drop": {
                "path": "raw_photos/shared.jpg",
                "face_ids": ["face_drop"],
                "source": "Test Session",
                "collection": "Test Upload",
                "source_url": "",
            },
        },
        face_to_photo={"face_keep": "photo_keep", "face_drop": "photo_drop"},
    )
    (data_dir / "identities.json").write_text(
        json.dumps(
            {
                "identities": {
                    "id1": {
                        "identity_id": "id1",
                        "name": "Person",
                        "state": "INBOX",
                        "anchor_ids": ["face_drop"],
                        "candidate_ids": [],
                        "negative_ids": [],
                    }
                },
                "history": [],
            }
        )
    )
    (data_dir / "annotations.json").write_text(json.dumps({"annotations": {}}))

    with pytest.raises(ValueError, match="referenced by identities"):
        cleanup_isolated_photo("photo_drop", data_dir=data_dir, dry_run=False)
