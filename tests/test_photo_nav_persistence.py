"""Tests for photo navigation persistence (BUG-006).

Root cause: Duplicate keyboard handlers in photo_nav_script and global
event delegation both fired on every keydown, causing double navigation
per key press. User reached end of photo list in 2-3 presses.

Tests cover:
1. No duplicate keyboard handlers in photo grid page
2. Global delegation handler is present
3. photoNavTo function is defined
4. Navigation buttons have correct data-action attributes
5. Photo partial includes prev/next buttons when nav context provided
"""

import pytest
import re
from starlette.testclient import TestClient


class TestNoDuplicateKeyboardHandler:
    """Photo grid must NOT register its own keyboard handler (global handles it)."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_photo_nav_script_has_no_keyboard_listener(self, client):
        """The photo_nav_script must not add its own keydown listener.

        Regression: duplicate listeners caused double-fire on ArrowLeft/Right,
        advancing 2 photos per key press and reaching the end after 2-3 presses.
        """
        response = client.get("/?section=photos")
        assert response.status_code == 200

        # Count how many times addEventListener('keydown'...) appears
        # There should be exactly ONE global handler, not one in photo_nav_script too
        keydown_count = response.text.count("addEventListener('keydown'")
        keydown_count += response.text.count('addEventListener("keydown"')
        assert keydown_count == 1, (
            f"Found {keydown_count} keydown event listeners — "
            f"expected exactly 1 (global delegation). "
            f"Duplicate handlers cause double-fire navigation."
        )

    def test_photoNavTo_function_defined(self, client):
        """photoNavTo must be defined in the photo grid page."""
        response = client.get("/?section=photos")
        assert "function photoNavTo" in response.text

    def test_photo_nav_ids_array_set(self, client):
        """window._photoNavIds must be set for client-side navigation."""
        response = client.get("/?section=photos")
        assert "_photoNavIds" in response.text


class TestPhotoPartialNavButtons:
    """Photo partial must include nav buttons when context is provided."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_partial_has_prev_next_buttons(self, client):
        """Partial with prev_id and next_id should have navigation buttons."""
        import app.main as main
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache")

        # Get first 3 photo IDs
        photo_ids = list(main._photo_cache.keys())[:3]
        if len(photo_ids) < 3:
            pytest.skip("Need at least 3 photos")

        # Request middle photo with nav context
        response = client.get(
            f"/photo/{photo_ids[1]}/partial"
            f"?prev_id={photo_ids[0]}&next_id={photo_ids[2]}"
            f"&nav_idx=1&nav_total=3"
        )
        assert response.status_code == 200
        assert 'data-action="photo-nav-prev"' in response.text, "Missing prev button"
        assert 'data-action="photo-nav-next"' in response.text, "Missing next button"

    def test_partial_without_nav_context_has_no_buttons(self, client):
        """Partial without prev_id/next_id should not have nav buttons."""
        import app.main as main
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache")

        photo_id = list(main._photo_cache.keys())[0]
        response = client.get(f"/photo/{photo_id}/partial")
        assert response.status_code == 200
        # No nav buttons when no context
        assert 'data-action="photo-nav-prev"' not in response.text
        assert 'data-action="photo-nav-next"' not in response.text

    def test_partial_nav_counter_shows_position(self, client):
        """Nav counter must show 'N / M' when nav_idx and nav_total provided."""
        import app.main as main
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache")

        photo_ids = list(main._photo_cache.keys())[:3]
        if len(photo_ids) < 3:
            pytest.skip("Need at least 3 photos")

        response = client.get(
            f"/photo/{photo_ids[1]}/partial"
            f"?prev_id={photo_ids[0]}&next_id={photo_ids[2]}"
            f"&nav_idx=1&nav_total=3"
        )
        assert "2 / 3" in response.text, "Nav counter should show '2 / 3' for idx=1, total=3"
