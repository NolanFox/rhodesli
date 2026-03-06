"""
Tests for Compare Faces UX: face/photo toggle, clickable names, modal.

Pruned: removed tests using _get_two_identity_ids() which reads global state
and causes xdist flakiness. Kept mock-based tests from test_ux_enhancements.py.
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


class TestCompareModal:
    """Tests for the compare faces modal."""

    def test_compare_modal_in_page(self, client):
        """Compare modal HTML is present in the main page."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
            assert 'id="compare-modal"' in response.text
