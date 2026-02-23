"""Tests for EXIF orientation handler — PRD-015 face alignment."""

import io

import pytest
from PIL import Image


from app.exif_handler import (
    get_image_dimensions,
    has_exif_orientation,
    normalize_orientation,
)


def _make_image(width=100, height=200, fmt="JPEG", orientation=None):
    """Create a test image with optional EXIF orientation."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    output = io.BytesIO()
    exif_data = None
    if orientation is not None:
        import piexif
        exif_dict = {"0th": {piexif.ImageIFD.Orientation: orientation}}
        exif_data = piexif.dump(exif_dict)
        img.save(output, format=fmt, exif=exif_data)
    else:
        img.save(output, format=fmt)
    return output.getvalue()


def _make_image_simple(width=100, height=200, fmt="JPEG"):
    """Create a simple test image without EXIF."""
    img = Image.new("RGB", (width, height), color=(0, 255, 0))
    output = io.BytesIO()
    img.save(output, format=fmt)
    return output.getvalue()


class TestNormalizeOrientation:
    def test_no_exif_passes_through(self):
        """Image without EXIF passes through with same dimensions."""
        raw = _make_image_simple(100, 200)
        result = normalize_orientation(raw)
        # Should still be valid image with same dimensions
        img = Image.open(io.BytesIO(result))
        assert img.size == (100, 200)

    def test_normal_orientation_unchanged(self):
        """Orientation=1 (normal) doesn't change dimensions."""
        try:
            raw = _make_image(100, 200, orientation=1)
        except ImportError:
            pytest.skip("piexif not installed")
        result = normalize_orientation(raw)
        img = Image.open(io.BytesIO(result))
        assert img.size == (100, 200)

    def test_rotated_90_cw(self):
        """Orientation=6 (90 CW) swaps width and height."""
        try:
            raw = _make_image(100, 200, orientation=6)
        except ImportError:
            pytest.skip("piexif not installed")
        result = normalize_orientation(raw)
        img = Image.open(io.BytesIO(result))
        # 90 CW rotation: (100, 200) -> (200, 100)
        assert img.size == (200, 100)

    def test_rotated_180(self):
        """Orientation=3 (180) keeps same dimensions."""
        try:
            raw = _make_image(100, 200, orientation=3)
        except ImportError:
            pytest.skip("piexif not installed")
        result = normalize_orientation(raw)
        img = Image.open(io.BytesIO(result))
        assert img.size == (100, 200)

    def test_idempotent(self):
        """Normalizing twice gives same result."""
        raw = _make_image_simple(100, 200)
        result1 = normalize_orientation(raw)
        result2 = normalize_orientation(result1)
        img1 = Image.open(io.BytesIO(result1))
        img2 = Image.open(io.BytesIO(result2))
        assert img1.size == img2.size


class TestGetImageDimensions:
    def test_basic_dimensions(self):
        """Returns correct (width, height)."""
        raw = _make_image_simple(320, 240)
        w, h = get_image_dimensions(raw)
        assert (w, h) == (320, 240)

    def test_dimensions_after_rotation(self):
        """Dimensions reflect post-rotation size."""
        try:
            raw = _make_image(100, 200, orientation=6)
        except ImportError:
            pytest.skip("piexif not installed")
        w, h = get_image_dimensions(raw)
        assert (w, h) == (200, 100)


class TestHasExifOrientation:
    def test_no_exif(self):
        """Image without EXIF returns False."""
        raw = _make_image_simple()
        assert has_exif_orientation(raw) is False

    def test_normal_orientation(self):
        """Orientation=1 returns False (no transform needed)."""
        try:
            raw = _make_image(orientation=1)
        except ImportError:
            pytest.skip("piexif not installed")
        assert has_exif_orientation(raw) is False

    def test_rotated_orientation(self):
        """Orientation=6 returns True."""
        try:
            raw = _make_image(orientation=6)
        except ImportError:
            pytest.skip("piexif not installed")
        assert has_exif_orientation(raw) is True
