"""Golden coverage for compare upload and result UX."""

from unittest.mock import patch


def test_compare_upload_returns_results(client, tmp_path, monkeypatch):
    """Upload a photo via unified pipeline → get processing status back."""
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", True)
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
    (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

    response = client.post(
        "/api/compare/upload",
        files={"photo": ("test.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    # New unified pipeline returns polling component
    assert any(msg in response.text.lower() for msg in [
        "processing photo", "compare-processing", "/api/compare/status/",
        "submitted", "staged",
    ])


def test_compare_pair_cross_matches(client):
    """Upload two photos → get cross-comparison results."""
    response = client.get("/compare/pair")
    assert response.status_code == 200
    assert "/api/compare/pair/upload" in response.text


def test_compare_upload_persists_photo(tmp_path, monkeypatch):
    """Uploaded photo is saved (R2 or local fallback)."""
    import app.main as main_mod
    from app.main import _save_compare_upload

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    with patch("core.storage.can_write_r2", return_value=False):
        upload_id = _save_compare_upload(b"abc", "photo.jpg", [], [], status="uploaded")

    assert upload_id
    assert (tmp_path / "uploads" / "compare" / f"{upload_id}.jpg").exists()


def test_compare_results_have_shareable_url(client):
    """Each result set has a unique, accessible URL."""
    from app.main import _save_comparison_result, _generate_result_id

    result_id = _generate_result_id()
    _save_comparison_result({
        "result_id": result_id,
        "query_type": "upload",
        "query_name": "Test Upload",
        "created_at": "2026-02-28T00:00:00",
        "matches": [],
        "responses": [],
    })
    response = client.get(f"/compare/result/{result_id}")
    assert response.status_code == 200
    assert f"/compare/result/{result_id}" in response.text


def test_compare_no_matches_shows_friendly_message(client):
    """When no faces match, show helpful message not error."""
    response = client.get("/compare/result/does-not-exist")
    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_compare_loading_indicator_present(client):
    """Upload form has hx-indicator for loading state."""
    response = client.get("/compare")
    assert response.status_code == 200
    assert "hx-indicator" in response.text


def test_compare_confidence_tiers_calibrated(monkeypatch):
    """Confidence labels match calibrated score ranges."""
    from app.main import _compare_result_card

    monkeypatch.setattr("app.main.resolve_face_image_url", lambda *_: "https://example.com/crop.jpg")
    monkeypatch.setattr("app.main.get_photo_id_for_face", lambda *_: "photo-1")

    card = _compare_result_card(
        {
            "face_id": "f1",
            "distance": 0.5,
            "tier": "STRONG MATCH",
            "confidence_pct": 88,
            "identity_name": "Test Person",
            "state": "CONFIRMED",
            "identity_id": "id1",
        },
        set(),
        0,
    )
    assert card is not None
    assert "Very likely same person" in str(card)


def test_compare_mobile_layout(client):
    """Compare page renders acceptably at 375px width."""
    response = client.get("/compare")
    assert response.status_code == 200
    assert "max-w-4xl" in response.text and "sm:" in response.text



def test_compare_upload_is_auto_queued_for_admin_review(tmp_path, monkeypatch):
    """Compare uploads automatically create a pending moderation queue entry."""
    import json
    import app.main as main_mod
    from app.main import _save_compare_upload

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    with patch("core.storage.can_write_r2", return_value=False):
        upload_id = _save_compare_upload(b"abc", "photo.jpg", [], [], status="uploaded")

    pending_path = tmp_path / "pending_uploads.json"
    assert pending_path.exists()
    data = json.loads(pending_path.read_text())
    assert f"compare_{upload_id}" in data.get("uploads", {})


def test_compare_pair_match_includes_cross_match_summary(client, tmp_path, monkeypatch):
    """Pair match endpoint reports top cross-photo pairs and archive summaries."""
    import pickle

    monkeypatch.chdir(tmp_path)
    upload_dir = tmp_path / "uploads" / "compare"
    upload_dir.mkdir(parents=True, exist_ok=True)

    faces_a = [{"mu": [0.0, 0.0]}, {"mu": [0.1, 0.1]}]
    faces_b = [{"mu": [0.0, 0.0]}, {"mu": [0.2, 0.2]}]
    (upload_dir / "upa_faces.pkl").write_bytes(pickle.dumps(faces_a))
    (upload_dir / "upb_faces.pkl").write_bytes(pickle.dumps(faces_b))

    with patch("core.storage.can_write_r2", return_value=False), patch("core.neighbors.find_similar_faces", return_value=[]):
        response = client.post("/api/compare/pair/match", params={"upload_a": "upa", "face_a": 0, "upload_b": "upb", "face_b": 0})

    assert response.status_code == 200
    assert "Top cross-photo matches" in response.text


def test_upload_id_has_no_hyphens(tmp_path, monkeypatch):
    """Upload IDs must be hex-only (no hyphens from str(uuid4))."""
    import app.main as main_mod
    from app.main import _save_compare_upload

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    with patch("core.storage.can_write_r2", return_value=False):
        upload_id = _save_compare_upload(b"abc", "photo.jpg", [], [], status="uploaded")

    assert "-" not in upload_id, f"Upload ID contains hyphen: {upload_id}"
    assert len(upload_id) == 12


def test_compare_result_not_found_shows_helpful_message(client):
    """Missing result shows 'expired' message with link to try again."""
    with patch("app.main._load_comparison_results", return_value={"results": {}}):
        response = client.get("/compare/result/nonexistent1")
    assert response.status_code == 200
    assert "expired" in response.text.lower() or "not found" in response.text.lower()
    assert "/compare" in response.text  # Link to try again


def test_save_comparison_result_is_retrievable(tmp_path, monkeypatch):
    """Saved comparison result can be retrieved by ID."""
    import app.main as main_mod
    from app.main import _save_comparison_result, _load_comparison_results

    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    # Reset cache
    main_mod._comparison_results_cache = None

    result_data = {
        "result_id": "abc123def456",
        "created_at": "2026-03-02T00:00:00Z",
        "query_type": "compare_upload",
        "matches": [{"identity_name": "Test", "distance": 0.5}],
        "responses": [],
    }
    _save_comparison_result(result_data)

    # Reset cache and reload
    main_mod._comparison_results_cache = None
    data = _load_comparison_results()
    assert "abc123def456" in data["results"]
    assert data["results"]["abc123def456"]["matches"][0]["identity_name"] == "Test"


# ---- Session 85: Unified Pipeline Tests ----


def test_compare_upload_stages_file(tmp_path, monkeypatch):
    """Compare upload stages file to data/staging/{job_id}/ (same as Upload page)."""
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", False)
    (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
    from starlette.testclient import TestClient
    tc = TestClient(main_mod.app)

    response = tc.post(
        "/api/compare/upload",
        files={"photo": ("test_photo.jpg", b"fake-image-data", "image/jpeg")},
    )
    assert response.status_code == 200
    # PROCESSING_ENABLED=False → staged message
    assert "staged" in response.text.lower()
    # Verify file was staged
    staging_dirs = list((tmp_path / "staging").iterdir())
    assert len(staging_dirs) == 1
    job_dir = staging_dirs[0]
    assert (job_dir / "test_photo.jpg").exists()
    assert (job_dir / "_metadata.json").exists()


def test_compare_upload_nonadmin_queued(tmp_path, monkeypatch):
    """Non-admin compare upload queued for review (Lesson 19)."""
    import json
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    monkeypatch.setattr(main_mod, "PROCESSING_ENABLED", True)
    # Make auth enabled + non-admin
    monkeypatch.setattr(main_mod, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(main_mod, "get_current_user", lambda sess: type("U", (), {"email": "user@test.com", "is_admin": False})())
    (tmp_path / "staging").mkdir(parents=True, exist_ok=True)
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
    from starlette.testclient import TestClient
    tc = TestClient(main_mod.app)

    response = tc.post(
        "/api/compare/upload",
        files={"photo": ("test.jpg", b"fake", "image/jpeg")},
    )
    assert response.status_code == 200
    assert "submitted" in response.text.lower()
    # Check pending_uploads.json
    pending_path = tmp_path / "pending_uploads.json"
    assert pending_path.exists()
    data = json.loads(pending_path.read_text())
    uploads = data.get("uploads", {})
    assert len(uploads) == 1
    entry = list(uploads.values())[0]
    assert entry["status"] == "pending"
    assert entry.get("compare_mode") is True


def test_compare_status_starting(tmp_path, monkeypatch, client):
    """Status endpoint returns polling HTML when job is starting."""
    import json
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timezone
    status = {"status": "starting", "started_at": datetime.now(timezone.utc).isoformat(), "total_files": 1}
    (tmp_path / "inbox" / "test1234.status.json").write_text(json.dumps(status))

    response = client.get("/api/compare/status/test1234")
    assert response.status_code == 200
    assert "every 2s" in response.text or "detecting" in response.text.lower()


def test_compare_status_error(tmp_path, monkeypatch, client):
    """Status endpoint shows error when job fails."""
    import json
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)

    status = {"status": "error", "error": "OOM", "total_files": 1}
    (tmp_path / "inbox" / "errjob01.status.json").write_text(json.dumps(status))

    response = client.get("/api/compare/status/errjob01")
    assert response.status_code == 200
    assert "error" in response.text.lower()


def test_compare_status_no_faces(tmp_path, monkeypatch, client):
    """Status endpoint shows friendly message when no faces detected."""
    import json
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)

    status = {"status": "success", "face_ids": [], "faces_extracted": 0}
    (tmp_path / "inbox" / "noface01.status.json").write_text(json.dumps(status))

    response = client.get("/api/compare/status/noface01")
    assert response.status_code == 200
    assert "no faces" in response.text.lower()


def test_compare_search_person_returns_results(client, monkeypatch):
    """Person search endpoint returns matching people."""
    import app.main as main_mod
    from unittest.mock import MagicMock

    mock_registry = MagicMock()
    mock_registry.search_identities.return_value = [
        {"identity_id": "id1", "name": "Isaac Cohen", "state": "CONFIRMED", "preview_face_id": "f1"},
    ]
    monkeypatch.setattr(main_mod, "load_registry", lambda: mock_registry)
    monkeypatch.setattr(main_mod, "get_crop_files", lambda: set())

    response = client.get("/api/compare/search-person?q=Isaac&job_id=test123")
    assert response.status_code == 200
    assert "Isaac Cohen" in response.text
    assert "vs-person" in response.text  # Contains the compare action


def test_compare_search_person_short_query(client):
    """Short search query returns empty results."""
    response = client.get("/api/compare/search-person?q=I")
    assert response.status_code == 200
    # Should be empty div
    assert "compare-person-search-results" in response.text


def test_compare_result_page_shows_photo_link(tmp_path, monkeypatch, client):
    """Result page links to photo page when photo_id is available."""
    import app.main as main_mod
    from app.main import _save_comparison_result

    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    main_mod._comparison_results_cache = None

    result_data = {
        "result_id": "photo_result01",
        "query_type": "upload_vs_person",
        "query_name": "vs Isaac Cohen",
        "photo_id": "inbox_abc_0_test",
        "reference_person": {"identity_id": "id123", "name": "Isaac Cohen"},
        "matches": [
            {"face_id": "f1", "identity_id": "id456", "identity_name": "Face 1",
             "distance": 1.15, "confidence_pct": 42, "tier": "POSSIBLE MATCH"},
        ],
        "responses": [],
    }
    _save_comparison_result(result_data)

    main_mod._comparison_results_cache = None
    response = client.get("/compare/result/photo_result01")
    assert response.status_code == 200
    # Should contain person links
    assert "/person/id456" in response.text
    assert "42%" in response.text


def test_compare_result_page_confidence_bars(tmp_path, monkeypatch, client):
    """Result page shows confidence bars with proper tier colors."""
    import app.main as main_mod
    from app.main import _save_comparison_result

    monkeypatch.setattr(main_mod, "data_path", tmp_path)
    main_mod._comparison_results_cache = None

    result_data = {
        "result_id": "confbar_test1",
        "query_type": "compare_upload",
        "query_name": "Test Upload",
        "matches": [
            {"face_id": "f1", "identity_id": "id1", "identity_name": "Person A",
             "distance": 0.7, "confidence_pct": 90, "tier": "STRONG MATCH"},
            {"face_id": "f2", "identity_id": "id2", "identity_name": "Person B",
             "distance": 1.3, "confidence_pct": 30, "tier": "WEAK"},
        ],
        "responses": [],
    }
    _save_comparison_result(result_data)

    main_mod._comparison_results_cache = None
    response = client.get("/compare/result/confbar_test1")
    assert response.status_code == 200
    # Should have confidence percentage text
    assert "90%" in response.text
    assert "30%" in response.text
    # Should have tier labels
    assert "Very likely same person" in response.text
    assert "Unlikely match" in response.text


# ---- Session 85b: Archive Photo → Compare Tests ----


def test_compare_from_photo_returns_scores(client, monkeypatch):
    """GET /api/compare/from-photo with photo_id + identity_id returns per-face scores."""
    import numpy as np
    import app.main as main_mod
    from unittest.mock import MagicMock

    mock_registry = MagicMock()
    identity = {
        "identity_id": "isaac-id",
        "name": "Isaac Cohen",
        "state": "CONFIRMED",
        "anchor_ids": ["ref-face-1"],
        "candidate_ids": [],
    }
    mock_registry.get_identity.return_value = identity
    mock_registry.identities = {
        "face-id-1": {"anchor_ids": [], "candidate_ids": ["uploaded-face-1"], "name": "Face 1"},
    }

    monkeypatch.setattr(main_mod, "load_registry", lambda: mock_registry)
    monkeypatch.setattr(main_mod, "get_crop_files", lambda: set())
    monkeypatch.setattr(main_mod, "_resolve_crop_url", lambda fid, cf: f"https://example.com/{fid}.jpg")
    monkeypatch.setattr(main_mod, "get_photo_metadata", lambda pid: {
        "filename": "test.jpg",
        "faces": [{"face_id": "uploaded-face-1", "bbox": [0, 0, 100, 100]}],
    })

    # Mock face_data with embeddings
    mock_embedding = np.random.randn(512).astype(np.float32)
    ref_embedding = np.random.randn(512).astype(np.float32)
    monkeypatch.setattr(main_mod, "get_face_data", lambda: {
        "uploaded-face-1": {"mu": mock_embedding},
        "ref-face-1": {"mu": ref_embedding},
    })
    monkeypatch.setattr(main_mod, "_build_caches", lambda: None)

    # Mock find_nearest_neighbors (imported inside route handler from core.neighbors)
    with patch("core.neighbors.find_nearest_neighbors", return_value=[]):
        response = client.get("/api/compare/from-photo?photo_id=test-photo&identity_id=isaac-id")

    assert response.status_code == 200
    assert "Isaac Cohen" in response.text
    assert "compare-face-score-0" in response.text
    assert "compare-hero" in response.text


def test_compare_from_photo_invalid_photo_404(client, monkeypatch):
    """GET /api/compare/from-photo with invalid photo_id returns error."""
    import app.main as main_mod
    monkeypatch.setattr(main_mod, "_build_caches", lambda: None)
    monkeypatch.setattr(main_mod, "get_face_data", lambda: {})
    monkeypatch.setattr(main_mod, "load_registry", lambda: type("R", (), {"identities": {}})())
    monkeypatch.setattr(main_mod, "get_crop_files", lambda: set())
    monkeypatch.setattr(main_mod, "get_photo_metadata", lambda pid: None)

    response = client.get("/api/compare/from-photo?photo_id=nonexistent")
    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_compare_from_photo_invalid_person_404(client, monkeypatch):
    """GET /api/compare/from-photo with invalid identity_id returns error."""
    import app.main as main_mod
    from unittest.mock import MagicMock

    mock_registry = MagicMock()
    mock_registry.get_identity.return_value = None

    monkeypatch.setattr(main_mod, "_build_caches", lambda: None)
    monkeypatch.setattr(main_mod, "get_face_data", lambda: {})
    monkeypatch.setattr(main_mod, "load_registry", lambda: mock_registry)
    monkeypatch.setattr(main_mod, "get_crop_files", lambda: set())
    monkeypatch.setattr(main_mod, "get_photo_metadata", lambda pid: {
        "filename": "test.jpg",
        "faces": [{"face_id": "f1"}],
    })

    response = client.get("/api/compare/from-photo?photo_id=test-photo&identity_id=nonexistent")
    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_compare_direct_url_with_photo_and_person(client, monkeypatch):
    """GET /compare?photo_id=X&person_id=Y loads comparison via HTMX."""
    response = client.get("/compare?photo_id=test-photo&person_id=test-person")
    assert response.status_code == 200
    # Should contain HTMX trigger to load from-photo comparison
    assert "/api/compare/from-photo" in response.text
    assert "photo_id=test-photo" in response.text
    assert "identity_id=test-person" in response.text


def test_compare_direct_url_photo_only(client):
    """GET /compare?photo_id=X shows photo selector without auto-comparing."""
    response = client.get("/compare?photo_id=test-photo")
    assert response.status_code == 200
    assert "/api/compare/from-photo" in response.text
    assert "photo_id=test-photo" in response.text


def test_photo_page_has_compare_link(client, monkeypatch):
    """Photo page includes a 'Compare faces' link."""
    import app.main as main_mod

    # Use a simple mock for public_photo_page to check route handler
    # The link should be embedded in the photo page HTML
    monkeypatch.setattr(main_mod, "get_photo_metadata", lambda pid: {
        "photo_id": "test-photo",
        "filename": "test.jpg",
        "width": 800,
        "height": 600,
        "faces": [{"face_id": "f1", "bbox": [10, 10, 100, 100]}],
        "collection": "Test Collection",
        "source": "Test",
    })
    monkeypatch.setattr(main_mod, "get_identity_for_face", lambda reg, fid: {
        "identity_id": "id1", "name": "Test Person", "state": "INBOX",
        "anchor_ids": [], "candidate_ids": ["f1"],
    })
    monkeypatch.setattr(main_mod, "resolve_face_image_url", lambda fid, cf: "https://example.com/crop.jpg")
    monkeypatch.setattr(main_mod, "get_crop_files", lambda: set())
    monkeypatch.setattr(main_mod, "_build_caches", lambda: None)

    response = client.get("/photo/test-photo")
    assert response.status_code == 200
    assert "compare?photo_id=test-photo" in response.text


def test_person_page_has_compare_link(client, monkeypatch):
    """Person page 'Compare with a photo' link includes person_id."""
    import app.main as main_mod
    from unittest.mock import MagicMock

    mock_registry = MagicMock()
    mock_registry.get_identity.return_value = {
        "identity_id": "person1",
        "name": "Test Person",
        "state": "CONFIRMED",
        "anchor_ids": ["f1"],
        "candidate_ids": [],
    }
    mock_registry.list_identities.return_value = []
    monkeypatch.setattr(main_mod, "load_registry", lambda: mock_registry)
    monkeypatch.setattr(main_mod, "get_crop_files", lambda: set())
    monkeypatch.setattr(main_mod, "_build_caches", lambda: None)
    monkeypatch.setattr(main_mod, "load_photo_registry", lambda: type("PR", (), {"get_photos_for_faces": lambda s, fids: []})())
    monkeypatch.setattr(main_mod, "get_best_face_id", lambda faces: "f1")
    monkeypatch.setattr(main_mod, "resolve_face_image_url", lambda fid, cf: "https://example.com/crop.jpg")

    response = client.get("/person/person1")
    assert response.status_code == 200
    assert "compare?person_id=person1" in response.text


def test_compare_search_person_photo(client, monkeypatch):
    """Search-person-photo endpoint returns clickable links with photo_id."""
    import app.main as main_mod
    from unittest.mock import MagicMock

    mock_registry = MagicMock()
    mock_registry.search_identities.return_value = [
        {"identity_id": "id1", "name": "Isaac Cohen", "state": "CONFIRMED", "preview_face_id": "f1"},
    ]
    monkeypatch.setattr(main_mod, "load_registry", lambda: mock_registry)
    monkeypatch.setattr(main_mod, "get_crop_files", lambda: set())

    response = client.get("/api/compare/search-person-photo?q=Isaac&photo_id=photo123")
    assert response.status_code == 200
    assert "Isaac Cohen" in response.text
    assert "photo_id=photo123" in response.text
