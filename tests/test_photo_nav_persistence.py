"""Tests for photo navigation persistence (BUG-006).

Root cause: Duplicate keyboard handlers caused double navigation.
Pruned: tests that mutate global _photo_cache state (xdist-unsafe).
"""

import pytest
from starlette.testclient import TestClient


class TestNoDuplicateKeyboardHandler:
    """Photo grid must NOT register its own keyboard handler (global handles it)."""

    @pytest.fixture
    def client(self):
        from app.main import app

        return TestClient(app)

    def test_photo_nav_script_has_no_keyboard_listener(self, client):
        """The photo_nav_script must not add its own keydown listener."""
        response = client.get("/?section=photos")
        assert response.status_code == 200

        keydown_count = response.text.count("addEventListener('keydown'")
        keydown_count += response.text.count('addEventListener("keydown"')
        assert keydown_count == 1, (
            f"Found {keydown_count} keydown event listeners — expected exactly 1 (global delegation)."
        )

    def test_photoNavTo_function_defined(self, client):
        """photoNavTo must be defined in the photo grid page."""
        response = client.get("/?section=photos")
        assert "function photoNavTo" in response.text
