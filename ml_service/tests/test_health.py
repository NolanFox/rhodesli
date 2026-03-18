"""Tests for the health endpoint."""


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_has_required_fields(client):
    resp = client.get("/health")
    data = resp.json()
    assert "status" in data
    assert "version" in data
    assert "execution_environment" in data
    assert "models_loaded" in data
    assert "uptime_seconds" in data
    assert data["status"] == "ok"


def test_health_works_without_auth(client):
    """Health endpoint should be public — no Authorization header needed."""
    resp = client.get("/health")
    assert resp.status_code == 200
