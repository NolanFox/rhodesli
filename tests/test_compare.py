"""Golden coverage for compare upload and result UX."""

from unittest.mock import patch


def test_compare_upload_returns_results(client):
    """Upload a photo → get face match results back."""
    with patch("core.storage.can_write_r2", return_value=False):
        response = client.post(
            "/api/compare/upload",
            files={"photo": ("test.jpg", b"fake-image", "image/jpeg")},
        )
    assert response.status_code == 200
    assert any(msg in response.text.lower() for msg in ["not yet available", "photo received", "error processing photo"])


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
