import pytest
from fastapi.testclient import TestClient

from ml_service.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer dev-token"}
