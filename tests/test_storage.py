"""Tests for core.storage URL generation."""

import pytest
from unittest.mock import patch

import core.storage as storage


class TestGetUploadPhotoUrl:
    """Test get_upload_photo_url in both local and R2 modes."""

    def test_local_mode_returns_local_route(self):
        """Uploaded photos served via local /photos/ route in local mode."""
        with patch.object(storage, "STORAGE_MODE", "local"), \
             patch.object(storage, "R2_PUBLIC_URL", ""):
            url = storage.get_upload_photo_url("data/uploads/b5e8a89e/603575867.895093.jpg")
            assert url == "/photos/603575867.895093.jpg"

    def test_r2_mode_returns_r2_url(self):
        """Uploaded photos served from R2 raw_photos/ prefix in R2 mode."""
        with patch.object(storage, "STORAGE_MODE", "r2"), \
             patch.object(storage, "R2_PUBLIC_URL", "https://pub-test.r2.dev"):
            url = storage.get_upload_photo_url("data/uploads/b5e8a89e/603575867.895093.jpg")
            assert url == "https://pub-test.r2.dev/raw_photos/603575867.895093.jpg"

    def test_r2_mode_encodes_special_chars(self):
        """Filenames with spaces are URL-encoded in R2 mode."""
        with patch.object(storage, "STORAGE_MODE", "r2"), \
             patch.object(storage, "R2_PUBLIC_URL", "https://pub-test.r2.dev"):
            url = storage.get_upload_photo_url("data/uploads/abc/photo name (1).jpg")
            assert "photo%20name%20%281%29.jpg" in url

    def test_extracts_filename_from_nested_path(self):
        """Should extract just the filename regardless of path depth."""
        with patch.object(storage, "STORAGE_MODE", "local"), \
             patch.object(storage, "R2_PUBLIC_URL", ""):
            url = storage.get_upload_photo_url("data/uploads/deep/nested/path/file.jpg")
            assert url == "/photos/file.jpg"


class TestGetPhotoUrl:
    """Test get_photo_url in both modes."""

    def test_local_mode(self):
        with patch.object(storage, "STORAGE_MODE", "local"), \
             patch.object(storage, "R2_PUBLIC_URL", ""):
            url = storage.get_photo_url("Image 001_compress.jpg")
            assert url == "/photos/Image%20001_compress.jpg"

    def test_r2_mode(self):
        with patch.object(storage, "STORAGE_MODE", "r2"), \
             patch.object(storage, "R2_PUBLIC_URL", "https://pub-test.r2.dev"):
            url = storage.get_photo_url("Image 001_compress.jpg")
            assert url == "https://pub-test.r2.dev/raw_photos/Image%20001_compress.jpg"


class TestIsR2Mode:
    """Test is_r2_mode detection."""

    def test_local_mode_default(self):
        with patch.object(storage, "STORAGE_MODE", "local"), \
             patch.object(storage, "R2_PUBLIC_URL", ""):
            assert not storage.is_r2_mode()

    def test_r2_mode_with_url(self):
        with patch.object(storage, "STORAGE_MODE", "r2"), \
             patch.object(storage, "R2_PUBLIC_URL", "https://pub-test.r2.dev"):
            assert storage.is_r2_mode()

    def test_r2_mode_without_url(self):
        with patch.object(storage, "STORAGE_MODE", "r2"), \
             patch.object(storage, "R2_PUBLIC_URL", ""):
            assert not storage.is_r2_mode()
