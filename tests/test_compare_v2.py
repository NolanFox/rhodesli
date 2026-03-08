"""Tests for Compare V2 stub routes (PRD-031)."""

import pytest

from app.compare_v2_routes import rt  # noqa: F401 — ensures routes registered


@pytest.fixture
def _register_v2_routes():
    """Import compare_v2_routes to register the stub endpoints."""
    import app.compare_v2_routes  # noqa: F401


class TestCompareV2Stub:
    """Compare V2 API returns not_implemented for all endpoints."""

    def test_status_returns_501(self, client, _register_v2_routes):
        """GET /api/v2/compare/status returns 501 with correct JSON."""
        resp = client.get("/api/v2/compare/status")
        assert resp.status_code == 501
        data = resp.json()
        assert data["status"] == "not_implemented"
        assert data["version"] == "v2"

    def test_embed_returns_501(self, client, _register_v2_routes):
        """POST /api/v2/compare/embed returns 501."""
        resp = client.post("/api/v2/compare/embed")
        assert resp.status_code == 501
        data = resp.json()
        assert data["status"] == "not_implemented"
        assert "ONNX" in data["message"]

    def test_compare_returns_501(self, client, _register_v2_routes):
        """POST /api/v2/compare returns 501."""
        resp = client.post("/api/v2/compare")
        assert resp.status_code == 501
        data = resp.json()
        assert data["status"] == "not_implemented"
        assert "ML service" in data["message"]
