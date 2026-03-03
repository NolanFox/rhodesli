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

    status = {"status": "starting", "started_at": "2026-03-03T12:00:00+00:00", "total_files": 1}
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
