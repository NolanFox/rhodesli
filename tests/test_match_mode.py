"""Tests for Phase 3: Match mode redesign — larger faces, confidence, clickable photos, logging."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestMatchModeUI:
    """Tests for the redesigned Match mode pair display."""

    def _mock_pair(self):
        """Create a mock match pair for testing."""
        identity_a = {
            "identity_id": "id-a",
            "name": "Alice",
            "state": "INBOX",
            "anchor_ids": ["face-a1", "face-a2"],
            "candidate_ids": [],
        }
        neighbor_b = {
            "identity_id": "id-b",
            "name": "Bob",
            "distance": 0.8,
            "face_count": 3,
        }
        return (identity_a, neighbor_b, 0.8)

    @patch("app.main._get_best_match_pair")
    @patch("app.main.get_crop_files", return_value=set())
    @patch("app.main.get_photo_id_for_face", return_value="photo-1")
    @patch("app.main.resolve_face_image_url", return_value="/crops/face.jpg")
    @patch("app.main.load_registry")
    def test_confidence_bar_displayed(self, mock_reg, mock_url, mock_photo, mock_crops, mock_pair):
        """Match mode shows confidence percentage and color bar."""
        from app.main import to_xml
        from starlette.testclient import TestClient
        from app.main import app

        mock_pair.return_value = self._mock_pair()
        reg = MagicMock()
        reg.get_identity.return_value = {
            "identity_id": "id-b", "name": "Bob",
            "anchor_ids": ["face-b1"], "candidate_ids": [],
        }
        mock_reg.return_value = reg

        client = TestClient(app)
        resp = client.get("/api/match/next-pair")
        html = resp.text

        assert "Match Confidence:" in html
        assert "%" in html

    @patch("app.main._get_best_match_pair")
    @patch("app.main.get_crop_files", return_value=set())
    @patch("app.main.get_photo_id_for_face", return_value="photo-1")
    @patch("app.main.resolve_face_image_url", return_value="/crops/face.jpg")
    @patch("app.main.load_registry")
    def test_faces_are_clickable(self, mock_reg, mock_url, mock_photo, mock_crops, mock_pair):
        """Each face in match mode is clickable to open source photo."""
        from starlette.testclient import TestClient
        from app.main import app

        mock_pair.return_value = self._mock_pair()
        reg = MagicMock()
        reg.get_identity.return_value = {
            "identity_id": "id-b", "name": "Bob",
            "anchor_ids": ["face-b1"], "candidate_ids": [],
        }
        mock_reg.return_value = reg

        client = TestClient(app)
        resp = client.get("/api/match/next-pair")
        html = resp.text

        # Should have clickable photo links
        assert "/photo/photo-1/partial" in html
        assert "Click to view" in html

    @patch("app.main._get_best_match_pair")
    @patch("app.main.get_crop_files", return_value=set())
    @patch("app.main.get_photo_id_for_face", return_value=None)
    @patch("app.main.resolve_face_image_url", return_value="/crops/face.jpg")
    @patch("app.main.load_registry")
    def test_no_photo_id_no_click(self, mock_reg, mock_url, mock_photo, mock_crops, mock_pair):
        """When no photo ID available, face is not clickable (no crash)."""
        from starlette.testclient import TestClient
        from app.main import app

        mock_pair.return_value = self._mock_pair()
        reg = MagicMock()
        reg.get_identity.return_value = {
            "identity_id": "id-b", "name": "Bob",
            "anchor_ids": ["face-b1"], "candidate_ids": [],
        }
        mock_reg.return_value = reg

        client = TestClient(app)
        resp = client.get("/api/match/next-pair")
        assert resp.status_code == 200

    @patch("app.main._get_best_match_pair", return_value=None)
    def test_no_pairs_shows_empty_state(self, mock_pair):
        """When no pairs available, shows empty state."""
        from starlette.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/match/next-pair")
        html = resp.text

        assert "No more pairs" in html
        assert "Focus mode" in html

    @patch("app.main._get_best_match_pair")
    @patch("app.main.get_crop_files", return_value=set())
    @patch("app.main.get_photo_id_for_face", return_value="photo-1")
    @patch("app.main.resolve_face_image_url", return_value="/crops/face.jpg")
    @patch("app.main.load_registry")
    def test_decision_passes_confidence(self, mock_reg, mock_url, mock_photo, mock_crops, mock_pair):
        """Decision buttons include confidence score in POST data."""
        from starlette.testclient import TestClient
        from app.main import app

        mock_pair.return_value = self._mock_pair()
        reg = MagicMock()
        reg.get_identity.return_value = {
            "identity_id": "id-b", "name": "Bob",
            "anchor_ids": ["face-b1"], "candidate_ids": [],
        }
        mock_reg.return_value = reg

        client = TestClient(app)
        resp = client.get("/api/match/next-pair")
        html = resp.text

        # Buttons should include confidence parameter
        assert "confidence=" in html


class TestMatchDecisionLogging:
    """Tests for match decision logging."""

    def test_log_match_decision_writes_jsonl(self, tmp_path):
        """Decisions are logged to match_decisions.jsonl."""
        from app.main import _log_match_decision

        with patch("app.main.DATA_DIR", str(tmp_path)), \
             patch("app.main.get_current_user", return_value=None):
            _log_match_decision("id-a", "id-b", "same", 75)

        log_path = tmp_path / "match_decisions.jsonl"
        assert log_path.exists()

        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["identity_a"] == "id-a"
        assert entry["identity_b"] == "id-b"
        assert entry["decision"] == "same"
        assert entry["confidence_pct"] == 75
        assert "timestamp" in entry

    def test_log_multiple_decisions(self, tmp_path):
        """Multiple decisions append to the same log file."""
        from app.main import _log_match_decision

        with patch("app.main.DATA_DIR", str(tmp_path)), \
             patch("app.main.get_current_user", return_value=None):
            _log_match_decision("id-1", "id-2", "same", 80)
            _log_match_decision("id-3", "id-4", "different", 45)

        log_path = tmp_path / "match_decisions.jsonl"
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 2

        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["decision"] == "same"
        assert second["decision"] == "different"


class TestConfidenceCalculation:
    """Tests for confidence percentage calculation."""

    @patch("app.main._get_best_match_pair")
    @patch("app.main.get_crop_files", return_value=set())
    @patch("app.main.get_photo_id_for_face", return_value=None)
    @patch("app.main.resolve_face_image_url", return_value=None)
    @patch("app.main.load_registry")
    def test_high_similarity_high_confidence(self, mock_reg, mock_url, mock_photo, mock_crops, mock_pair):
        """Distance 0.5 should show high confidence."""
        from starlette.testclient import TestClient
        from app.main import app

        pair = (
            {"identity_id": "a", "name": "A", "state": "INBOX", "anchor_ids": ["f1"], "candidate_ids": []},
            {"identity_id": "b", "name": "B", "distance": 0.5, "face_count": 1},
            0.5,
        )
        mock_pair.return_value = pair
        reg = MagicMock()
        reg.get_identity.return_value = {"identity_id": "b", "name": "B", "anchor_ids": ["f2"], "candidate_ids": []}
        mock_reg.return_value = reg

        client = TestClient(app)
        resp = client.get("/api/match/next-pair")
        html = resp.text

        # 0.5 distance → (1 - 0.5/2.0) * 100 = 75%
        assert "75%" in html
        assert "High" in html or "emerald" in html
