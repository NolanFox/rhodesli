"""Tests for face alignment API endpoints — PRD-015 Phase 3."""

from unittest.mock import AsyncMock, patch



class TestFaceAlignmentGetEndpoint:
    """GET /api/face-alignment/{photo_id} — public endpoint."""

    def test_returns_not_aligned_when_no_data(self, client):
        """Returns status: not_aligned when photo has no alignment."""
        with (
            patch("app.face_alignment.get_cached_alignment", return_value=None),
            patch("app.face_alignment.load_alignments_from_file", return_value={}),
        ):
            resp = client.get("/api/face-alignment/test_photo_id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_aligned"

    def test_returns_cached_result(self, client):
        """Returns cached alignment if available."""
        from app.face_alignment import AlignmentResult

        mock_result = AlignmentResult(
            photo_id="test_photo",
            faces_detected=3,
            faces_described=3,
            model_used="gemini-pro",
        )
        with patch("app.face_alignment.get_cached_alignment", return_value=mock_result):
            resp = client.get("/api/face-alignment/test_photo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["photo_id"] == "test_photo"
        assert data["faces_detected"] == 3

    def test_returns_file_result(self, client):
        """Returns result from file when not in cache."""
        stored = {
            "stored_photo": {
                "photo_id": "stored_photo",
                "faces_detected": 5,
                "model_used": "gemini-pro",
            }
        }
        with (
            patch("app.face_alignment.get_cached_alignment", return_value=None),
            patch("app.face_alignment.load_alignments_from_file", return_value=stored),
        ):
            resp = client.get("/api/face-alignment/stored_photo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["faces_detected"] == 5


class TestFaceAlignmentPostEndpoint:
    """POST /api/face-alignment/{photo_id} — admin-only endpoint."""

    def test_requires_admin(self, client, auth_enabled, regular_user):
        """Non-admin users get 403."""
        resp = client.post("/api/face-alignment/any_photo")
        assert resp.status_code in (401, 403)

    def test_requires_login(self, client, auth_enabled, no_user):
        """Anonymous users get 401."""
        resp = client.post("/api/face-alignment/any_photo")
        assert resp.status_code == 401

    def test_admin_can_trigger(self, client, admin_user, auth_enabled):
        """Admin can trigger face alignment."""
        from app.face_alignment import AlignmentResult

        mock_photo = {
            "filename": "test.jpg",
            "faces": [
                {"face_id": "f1", "bbox": [10, 20, 100, 200], "face_index": 0, "det_score": 0.95, "quality": 80},
            ],
        }
        mock_result = AlignmentResult(
            photo_id="test_photo",
            faces_detected=1,
            faces_described=1,
            model_used="gemini-pro",
        )

        with (
            patch("app.main.get_photo_metadata", return_value=mock_photo),
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", return_value=None),
            patch("app.main._load_photo_bytes", return_value=b"fake_image_bytes"),
            patch("os.getenv", side_effect=lambda k, d="": "fake-key" if k == "GEMINI_API_KEY" else d),
            patch("app.face_alignment.run_face_alignment", new_callable=AsyncMock) as mock_run,
            patch("app.face_alignment.cache_alignment"),
            patch("app.face_alignment.save_alignment_to_file"),
        ):
            mock_run.return_value = mock_result
            resp = client.post("/api/face-alignment/test_photo")

        assert resp.status_code == 200
        # Route returns rendered HTML (for HTMX swap) after successful alignment
        text = resp.text
        assert "Face Analysis" in text or "face-alignment" in text

    def test_photo_not_found(self, client, admin_user, auth_enabled):
        """Returns 404 for unknown photo."""
        with patch("app.main.get_photo_metadata", return_value=None):
            resp = client.post("/api/face-alignment/nonexistent")
        assert resp.status_code == 404

    def test_no_faces(self, client, admin_user, auth_enabled):
        """Returns 400 when photo has no detected faces."""
        mock_photo = {
            "filename": "test.jpg",
            "faces": [],
        }
        with patch("app.main.get_photo_metadata", return_value=mock_photo), patch("app.main.load_registry"):
            resp = client.post("/api/face-alignment/empty_photo")
        assert resp.status_code == 400
