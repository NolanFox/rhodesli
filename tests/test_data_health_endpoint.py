"""Tests for /api/health/data endpoint — confirmed identity integrity.

Session 130: Data Integrity Deep Audit — Phase 4
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


def _make_id_reg(identities):
    """Create a mock identity registry with real dict access."""
    reg = MagicMock()
    reg._identities = identities
    reg.list_identities.return_value = [iid for iid in identities if not identities[iid].get("merged_into")]
    return reg


def _make_photo_reg(photos):
    """Create a mock photo registry."""
    reg = MagicMock()
    reg._photos = photos
    return reg


def _run_health_check(tmp_path, identities, photos):
    """Run /api/health/data with mocked registries and return JSON response."""
    id_reg = _make_id_reg(identities)
    photo_reg = _make_photo_reg(photos)

    # Write minimal files
    (tmp_path / "identities.json").write_text(json.dumps({"identities": {}}))
    (tmp_path / "photo_index.json").write_text(json.dumps({"photos": {}}))

    mock_id_cls = MagicMock()
    mock_id_cls.load.return_value = id_reg

    mock_photo_cls = MagicMock()
    mock_photo_cls.load.return_value = photo_reg

    with (
        patch("app.sync_routes._main_mod") as mock_main,
        patch("core.registry.IdentityRegistry", mock_id_cls),
        patch("core.photo_registry.PhotoRegistry", mock_photo_cls),
    ):
        mock_main._check_admin.return_value = None
        mock_main.data_path = tmp_path
        mock_main._load_proposals.return_value = {"proposals": []}

        client = TestClient(app)
        response = client.get("/api/health/data")

    return response


class TestDataHealthConfirmedIntegrity:
    """Test the confirmed identity face integrity check in /api/health/data."""

    def test_healthy_when_all_faces_present(self, tmp_path):
        identities = {
            "id1": {"state": "CONFIRMED", "name": "Test", "anchor_ids": ["face1", "face2"]},
        }
        photos = {"photo1": {"face_ids": {"face1", "face2"}}}

        response = _run_health_check(tmp_path, identities, photos)
        assert response.status_code == 200
        data = response.json()
        assert data["confirmed_integrity"]["issues"] == 0

    def test_detects_missing_confirmed_faces(self, tmp_path):
        identities = {
            "id1": {"state": "CONFIRMED", "name": "Missing", "anchor_ids": ["face1", "face2", "face3"]},
        }
        photos = {"photo1": {"face_ids": {"face1"}}}

        response = _run_health_check(tmp_path, identities, photos)
        assert response.status_code == 200
        data = response.json()
        assert data["confirmed_integrity"]["issues"] == 1
        assert data["confirmed_integrity"]["details"][0]["missing_faces"] == 2
        assert data["status"] == "critical"

    def test_ignores_merged_identities(self, tmp_path):
        identities = {
            "id1": {"state": "CONFIRMED", "name": "Merged", "anchor_ids": ["gone"], "merged_into": "id2"},
        }
        response = _run_health_check(tmp_path, identities, {})
        assert response.status_code == 200
        data = response.json()
        assert data["confirmed_integrity"]["issues"] == 0
