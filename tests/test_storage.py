"""Tests for core.storage URL generation."""

import pytest
from unittest.mock import patch

import core.storage as storage


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

    def test_extracts_basename_from_path(self):
        """get_photo_url should extract the filename from a path."""
        with patch.object(storage, "STORAGE_MODE", "local"), \
             patch.object(storage, "R2_PUBLIC_URL", ""):
            url = storage.get_photo_url("raw_photos/file.jpg")
            assert url == "/photos/file.jpg"

    def test_r2_mode_encodes_special_chars(self):
        """Filenames with spaces are URL-encoded."""
        with patch.object(storage, "STORAGE_MODE", "r2"), \
             patch.object(storage, "R2_PUBLIC_URL", "https://pub-test.r2.dev"):
            url = storage.get_photo_url("photo name (1).jpg")
            assert "photo%20name%20%281%29.jpg" in url


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
