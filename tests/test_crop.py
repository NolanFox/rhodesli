"""Tests for core/crop_faces.py - 10% padding logic and naming format."""

import pytest
from core.crop_faces import add_padding, sanitize_filename


class TestAddPadding:
    """Tests for the add_padding function."""

    def test_adds_10_percent_padding(self):
        """10% padding expands a 100x100 box by 10px on each side."""
        bbox = [100, 100, 200, 200]  # 100x100 box
        image_shape = (1000, 1000, 3)  # Large image, no clamping needed

        result = add_padding(bbox, image_shape, padding=0.10)

        # 10% of 100 = 10, so expand by 10 on each side
        assert result == (90, 90, 210, 210)

    def test_clamps_to_image_bounds_at_origin(self):
        """Padding near origin clamps to 0."""
        bbox = [5, 5, 105, 105]  # 100x100 box near origin
        image_shape = (1000, 1000, 3)

        result = add_padding(bbox, image_shape, padding=0.10)

        # x1-10=-5 -> clamps to 0, y1-10=-5 -> clamps to 0
        assert result[0] == 0  # x1 clamped
        assert result[1] == 0  # y1 clamped
        assert result[2] == 115  # x2 normal
        assert result[3] == 115  # y2 normal

    def test_clamps_to_image_bounds_at_edge(self):
        """Padding near image edge clamps to image dimensions."""
        bbox = [900, 900, 1000, 1000]  # 100x100 box at bottom-right
        image_shape = (1000, 1000, 3)

        result = add_padding(bbox, image_shape, padding=0.10)

        assert result[0] == 890  # x1 normal
        assert result[1] == 890  # y1 normal
        assert result[2] == 1000  # x2 clamped to width
        assert result[3] == 1000  # y2 clamped to height

    def test_returns_integers(self):
        """All returned coordinates must be integers."""
        bbox = [100.5, 100.5, 200.5, 200.5]
        image_shape = (1000, 1000, 3)

        result = add_padding(bbox, image_shape, padding=0.10)

        assert all(isinstance(coord, int) for coord in result)

    def test_custom_padding_percentage(self):
        """Supports custom padding percentage."""
        bbox = [100, 100, 200, 200]  # 100x100 box
        image_shape = (1000, 1000, 3)

        result = add_padding(bbox, image_shape, padding=0.20)  # 20%

        # 20% of 100 = 20, so expand by 20 on each side
        assert result == (80, 80, 220, 220)


class TestSanitizeFilename:
    """Tests for the sanitize_filename function."""

    def test_converts_to_lowercase(self):
        """Converts uppercase to lowercase."""
        assert sanitize_filename("Brass_Rail.jpg") == "brass_rail"

    def test_replaces_spaces_with_underscores(self):
        """Spaces become underscores."""
        assert sanitize_filename("My Photo.jpg") == "my_photo"

    def test_removes_extension(self):
        """File extension is removed."""
        assert sanitize_filename("photo.jpg") == "photo"
        assert sanitize_filename("photo.JPG") == "photo"

    def test_replaces_special_chars_with_underscores(self):
        """Special characters become underscores."""
        assert sanitize_filename("photo (1).jpg") == "photo_1"

    def test_strips_leading_trailing_underscores(self):
        """No leading or trailing underscores."""
        assert sanitize_filename("_photo_.jpg") == "photo"

    def test_collapses_multiple_underscores(self):
        """Multiple consecutive non-alphanumeric chars become single underscore."""
        assert sanitize_filename("photo---test.jpg") == "photo_test"

    def test_handles_complex_filename(self):
        """Complex real-world filename."""
        result = sanitize_filename("Brass_Rail_Restaurant_with_Leon_Capeluto_Picture.jpg")
        assert result == "brass_rail_restaurant_with_leon_capeluto_picture"

    def test_handles_parentheses_and_numbers(self):
        """Handles filenames with parentheses and numbers."""
        result = sanitize_filename("603569530.803296 (1).jpg")
        assert result == "603569530_803296_1"
