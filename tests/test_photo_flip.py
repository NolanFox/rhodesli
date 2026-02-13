"""Tests for front/back photo flip feature.

Tests cover:
- Photos without back_image: no flip UI shown
- Photos with back_image: flip button and back image rendered
- back_transcription display
- CSS flip classes present
- Metadata endpoint accepts back_image/back_transcription fields
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos


def get_real_photo_id():
    """Get a real photo_id from the embeddings for testing."""
    photos = load_embeddings_for_photos()
    if photos:
        return next(iter(photos.keys()))
    return None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_photo_id():
    return get_real_photo_id()


class TestFlipUIHidden:
    """Photos without back_image should not show flip UI."""

    def test_no_flip_button_without_back_image(self, client, real_photo_id):
        """Flip button element is NOT shown when photo has no back_image."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # The button element should not exist (JS may reference the text as strings)
        assert 'id="flip-photo-btn"' not in html

    def test_no_flip_container_without_back_image(self, client, real_photo_id):
        """Flip container class is not on the photo div when there's no back image."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # The actual DOM element with class photo-flip-container should not exist
        # (CSS rules may mention the class name in the style block, that's fine)
        assert 'class="photo-flip-container' not in html

    def test_no_writing_hint_without_back_image(self, client, real_photo_id):
        """No 'writing on the back' text when no back image."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "writing on the back" not in html


class TestFlipUIWithBackImage:
    """Photos with back_image should show flip UI."""

    def _patch_photo_with_back(self, photo_id):
        """Create a mock get_photo_metadata that adds back_image to a real photo."""
        from app.main import get_photo_metadata as real_get
        real_photo = real_get(photo_id)
        if not real_photo:
            return None
        # Add back_image to the photo data
        patched = dict(real_photo)
        patched["back_image"] = "test_photo_back.jpg"
        patched["back_transcription"] = "Written on back: To my dear family, 1935"
        return patched

    def test_flip_button_shown_with_back_image(self, client, real_photo_id):
        """Flip button IS shown when photo has a back_image."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = self._patch_photo_with_back(real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Turn Over" in html
        assert "flip-photo-btn" in html

    def test_back_image_rendered(self, client, real_photo_id):
        """Back image element is present in flip container."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = self._patch_photo_with_back(real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "photo-flip-back" in html
        assert "Back of photograph" in html

    def test_back_transcription_rendered(self, client, real_photo_id):
        """Transcription text is shown when back_transcription is set."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = self._patch_photo_with_back(real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "To my dear family, 1935" in html

    def test_flip_css_classes_present(self, client, real_photo_id):
        """CSS flip classes are included in the page."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = self._patch_photo_with_back(real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "photo-flip-container" in html
        assert "photo-flip-inner" in html
        assert "photo-flip-front" in html
        assert "is-flipped" in html  # Present in CSS/JS, not as active class

    def test_writing_hint_shown(self, client, real_photo_id):
        """Hint about writing on the back is displayed."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = self._patch_photo_with_back(real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "writing on the back" in html

    def test_flip_js_handler_present(self, client, real_photo_id):
        """Event delegation JS for flip button is included."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = self._patch_photo_with_back(real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "flip-photo" in html
        assert "is-flipped" in html


class TestBackImageMetadata:
    """Metadata endpoint accepts back_image and back_transcription."""

    def test_back_image_in_valid_metadata_keys(self):
        """back_image is an accepted metadata key in PhotoRegistry."""
        from core.photo_registry import PhotoRegistry
        reg = PhotoRegistry()
        reg.register_face("test-photo", "test.jpg", "face1", source="test", collection="test")
        result = reg.set_metadata("test-photo", {"back_image": "test_back.jpg"})
        assert result is True
        meta = reg.get_metadata("test-photo")
        assert meta.get("back_image") == "test_back.jpg"

    def test_back_transcription_in_valid_metadata_keys(self):
        """back_transcription is an accepted metadata key in PhotoRegistry."""
        from core.photo_registry import PhotoRegistry
        reg = PhotoRegistry()
        reg.register_face("test-photo", "test.jpg", "face1", source="test", collection="test")
        result = reg.set_metadata("test-photo", {
            "back_image": "back.jpg",
            "back_transcription": "Family photo, 1935"
        })
        assert result is True
        meta = reg.get_metadata("test-photo")
        assert meta.get("back_transcription") == "Family photo, 1935"


class TestPremiumFlipCSS:
    """Premium flip animation CSS features."""

    def test_perspective_on_container(self, client, real_photo_id):
        """Flip container has perspective for 3D depth."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = TestFlipUIWithBackImage._patch_photo_with_back(None, real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "perspective: 1200px" in html

    def test_shadow_dynamics(self, client, real_photo_id):
        """Flip animation includes dynamic shadow on flipped state."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = TestFlipUIWithBackImage._patch_photo_with_back(None, real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Lifted shadow when flipped
        assert "box-shadow" in html
        assert "scale(1.02)" in html

    def test_paper_texture_on_back(self, client, real_photo_id):
        """Back side has paper texture CSS."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = TestFlipUIWithBackImage._patch_photo_with_back(None, real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        # Paper color
        assert "#f5f0e8" in html

    def test_face_overlay_fade_css(self, client, real_photo_id):
        """Face overlays fade out during flip via CSS."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = TestFlipUIWithBackImage._patch_photo_with_back(None, real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "face-overlay-box" in html

    def test_turn_over_button_text(self, client, real_photo_id):
        """Flip button says 'Turn Over' not 'Flip Photo'."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = TestFlipUIWithBackImage._patch_photo_with_back(None, real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Turn Over" in html
        assert "View Front" in html  # In JS handler

    def test_view_front_in_flip_handler(self, client, real_photo_id):
        """JS handler toggles between 'Turn Over' and 'View Front'."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = TestFlipUIWithBackImage._patch_photo_with_back(None, real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "View Front" in html
        assert "Turn Over" in html
