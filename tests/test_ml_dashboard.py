"""
Tests for ML evaluation dashboard (ML-013).
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch


class TestMLDashboard:
    """Tests for /admin/ml-dashboard route."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_ml_dashboard_requires_admin(self, client):
        """ML dashboard returns 401/403 for non-admin users."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.get("/admin/ml-dashboard")
            assert response.status_code in (401, 403)

    def test_ml_dashboard_renders(self, client):
        """ML dashboard renders without error for admin."""
        # Auth disabled = admin access
        response = client.get("/admin/ml-dashboard")
        assert response.status_code == 200
        assert "ML Evaluation Dashboard" in response.text

    def test_ml_dashboard_shows_identity_stats(self, client):
        """ML dashboard displays identity state counts."""
        response = client.get("/admin/ml-dashboard")
        assert response.status_code == 200
        assert "Confirmed" in response.text
        assert "Skipped" in response.text
        assert "New Matches" in response.text

    def test_ml_dashboard_shows_thresholds(self, client):
        """ML dashboard displays calibrated thresholds."""
        response = client.get("/admin/ml-dashboard")
        assert "VERY HIGH" in response.text
        assert "HIGH" in response.text
        assert "AD-013" in response.text

    def test_ml_dashboard_shows_golden_set(self, client):
        """ML dashboard shows golden set stats if available."""
        response = client.get("/admin/ml-dashboard")
        assert "Golden Set" in response.text

    def test_ml_dashboard_shows_diversity(self, client):
        """ML dashboard shows golden set diversity analysis (ML-011)."""
        response = client.get("/admin/ml-dashboard")
        assert response.status_code == 200
        # Diversity section should show identity distribution info
        assert "Diversity" in response.text or "diversity" in response.text
