"""Regression tests for photo faces preserved outside embeddings artifacts."""

import json
from unittest.mock import MagicMock

from starlette.testclient import TestClient

import app.main as main_mod
import app.page_routes as page_routes
from app.main import app, generate_photo_id
from core.photo_registry import PhotoRegistry


def _write_photo_index(tmp_path):
    data = {
        "schema_version": 1,
        "photos": {
            "inbox_job_123_photo": {
                "path": "raw_photos/photo.jpg",
                "face_ids": ["face_kept", "face_missing"],
                "source": "Test Source",
                "collection": "Test Collection",
                "source_url": "",
                "width": 800,
                "height": 600,
                "upload_date": "2026-03-10T00:00:00+00:00",
                "job_id": "job_123",
            }
        },
        "face_to_photo": {
            "face_kept": "inbox_job_123_photo",
            "face_missing": "inbox_job_123_photo",
        },
    }
    (tmp_path / "photo_index.json").write_text(json.dumps(data))


def test_get_photo_metadata_preserves_photo_index_faces_missing_from_embeddings(tmp_path, monkeypatch):
    _write_photo_index(tmp_path)
    cache_id = generate_photo_id("photo.jpg")
    embedding_cache = {
        cache_id: {
            "filename": "photo.jpg",
            "faces": [
                {
                    "face_id": "face_kept",
                    "bbox": [10, 20, 30, 40],
                    "face_index": 0,
                    "det_score": 0.99,
                    "quality": 25.0,
                }
            ],
        }
    }

    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    monkeypatch.setattr(main_mod, "load_embeddings_for_photos", lambda: embedding_cache)

    main_mod._invalidate_all_caches()
    try:
        photo = main_mod.get_photo_metadata("inbox_job_123_photo")
        assert photo is not None
        assert [face["face_id"] for face in photo["faces"]] == ["face_kept", "face_missing"]
        assert photo["missing_face_artifacts"] == 1
        assert photo["faces"][1]["missing_artifacts"] is True
        assert photo["faces"][1]["bbox"] == []
        assert main_mod.get_photo_id_for_face("face_missing") == cache_id
    finally:
        main_mod._invalidate_all_caches()


def test_api_photo_skips_faces_without_bbox(monkeypatch):
    photo = {
        "filename": "photo.jpg",
        "faces": [
            {"face_id": "face_kept", "bbox": [10, 20, 40, 60]},
            {"face_id": "face_missing", "bbox": [], "missing_artifacts": True},
        ],
    }

    monkeypatch.setattr(page_routes._main_mod, "get_photo_metadata", lambda photo_id: photo)
    monkeypatch.setattr(page_routes._main_mod, "get_photo_dimensions", lambda filename: (800, 600))
    monkeypatch.setattr(page_routes._main_mod, "load_registry", lambda: MagicMock())
    monkeypatch.setattr(
        page_routes._main_mod,
        "get_identity_for_face",
        lambda registry, face_id: {"identity_id": f"id-{face_id}", "name": "Known Person"},
    )

    with TestClient(app) as client:
        response = client.get("/api/photo/test-photo")

    assert response.status_code == 200
    data = response.json()
    assert [face["face_id"] for face in data["faces"]] == ["face_kept"]


def test_get_photo_metadata_prefers_loaded_registry_values_in_postgres_mode(tmp_path, monkeypatch):
    # Ensure no stale cache from prior tests (especially test_api_photo which uses TestClient)
    main_mod._invalidate_all_caches()

    stale_data = {
        "schema_version": 1,
        "photos": {
            "pg_photo": {
                "path": "raw_photos/photo.jpg",
                "face_ids": ["face_kept"],
                "source": "Stale Source",
                "collection": "Stale Collection",
                "source_url": "",
            }
        },
        "face_to_photo": {"face_kept": "pg_photo"},
    }
    (tmp_path / "photo_index.json").write_text(json.dumps(stale_data))

    cache_id = generate_photo_id("photo.jpg")
    embedding_cache = {
        cache_id: {
            "filename": "photo.jpg",
            "faces": [
                {
                    "face_id": "face_kept",
                    "bbox": [10, 20, 30, 40],
                    "face_index": 0,
                    "det_score": 0.99,
                    "quality": 25.0,
                }
            ],
        }
    }

    registry = PhotoRegistry()
    registry.register_face(
        "pg_photo", "raw_photos/photo.jpg", "face_kept", source="Fresh Source", collection="Fresh Collection"
    )
    registry.set_source_url("pg_photo", "https://fresh.example/source")

    # Monkeypatch BEFORE invalidating caches so _build_caches() uses our mocks
    monkeypatch.setattr(main_mod, "DATA_SOURCE", "postgres")
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    monkeypatch.setattr(main_mod, "load_embeddings_for_photos", lambda: embedding_cache)
    monkeypatch.setattr(main_mod, "load_photo_registry", lambda: registry)

    # Acquire cache lock to ensure no background prewarm thread is building
    # caches with un-monkeypatched data, then clear and release
    with main_mod._cache_lock:
        main_mod._photo_cache = None
        main_mod._face_to_photo_cache = None
        main_mod._photo_id_aliases = None
        main_mod._photo_registry_cache = None
        main_mod._face_data_cache = None
    try:
        photo = main_mod.get_photo_metadata("pg_photo")
        assert photo is not None
        assert photo["source"] == "Fresh Source"
        assert photo["collection"] == "Fresh Collection"
        assert photo["source_url"] == "https://fresh.example/source"
    finally:
        main_mod._invalidate_all_caches()
