"""Tests for the R2 upload helper used by upload approval/repair flows."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_upload_new_files_to_r2_reads_job_from_data_uploads_dir(tmp_path):
    """Repair/approval uploads stored under data/uploads should still reach R2."""
    from app.main import _upload_new_files_to_r2

    data_dir = tmp_path / "data"
    uploads_dir = data_dir / "uploads" / "job123"
    uploads_dir.mkdir(parents=True)
    (uploads_dir / "unknown.jpg").write_bytes(b"fake image")

    photo_index = {
        "schema_version": 1,
        "photos": {
            "inbox_job123_0_unknown": {
                "path": "raw_photos/unknown.jpg",
                "face_ids": ["face123"],
                "source": "Unknown",
                "collection": "Unknown",
            }
        },
        "face_to_photo": {"face123": "inbox_job123_0_unknown"},
    }
    (data_dir / "photo_index.json").write_text(json.dumps(photo_index))
    crops_dir = data_dir / "crops"
    crops_dir.mkdir(parents=True)
    (crops_dir / "face123.jpg").write_bytes(b"fake crop")

    mock_s3 = MagicMock()
    with patch.dict(
        "os.environ",
        {
            "R2_PUBLIC_URL": "https://example.r2.dev",
            "R2_ACCESS_KEY_ID": "key",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_ACCOUNT_ID": "acct",
            "R2_BUCKET_NAME": "bucket",
        },
        clear=False,
    ), patch("boto3.client", return_value=mock_s3):
        _upload_new_files_to_r2(data_dir, "job123")

    uploaded_keys = [call.args[2] for call in mock_s3.upload_file.call_args_list]
    assert "raw_photos/unknown.jpg" in uploaded_keys
    assert "crops/face123.jpg" in uploaded_keys


def test_upload_new_files_to_r2_falls_back_to_canonical_raw_photo_path(tmp_path):
    """When the job directory is gone, repair-upload should use raw_photos/ from photo_index."""
    from app.main import _upload_new_files_to_r2

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    raw_dir = tmp_path / "raw_photos"
    raw_dir.mkdir(parents=True)
    (raw_dir / "unknown.jpg").write_bytes(b"recovered image")

    photo_index = {
        "schema_version": 1,
        "photos": {
            "inbox_job123_0_unknown": {
                "path": "raw_photos/unknown.jpg",
                "face_ids": [],
                "source": "Unknown",
                "collection": "Unknown",
            }
        },
        "face_to_photo": {},
    }
    (data_dir / "photo_index.json").write_text(json.dumps(photo_index))

    mock_s3 = MagicMock()
    with patch.dict(
        "os.environ",
        {
            "R2_PUBLIC_URL": "https://example.r2.dev",
            "R2_ACCESS_KEY_ID": "key",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_ACCOUNT_ID": "acct",
            "R2_BUCKET_NAME": "bucket",
        },
        clear=False,
    ), patch("boto3.client", return_value=mock_s3):
        _upload_new_files_to_r2(data_dir, "job123")

    raw_upload_calls = [call for call in mock_s3.upload_file.call_args_list if call.args[2] == "raw_photos/unknown.jpg"]
    assert len(raw_upload_calls) == 1
    assert Path(raw_upload_calls[0].args[0]) == raw_dir / "unknown.jpg"
