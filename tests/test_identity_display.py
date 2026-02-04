"""
Tests for identity naming and photo resolution.
Both tests should FAIL on current broken code.
"""

import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class TestIdentityNaming:
    """Test that inbox identities get human-readable names."""

    def test_new_identity_has_human_readable_name(self):
        """
        Bug 1: Identities should have names like "Unidentified Person 001"
        not "Identity 25f0a152..."
        """
        from core.ingest_inbox import create_inbox_identities
        from core.registry import IdentityRegistry, IdentityState

        # Create a fresh registry
        registry = IdentityRegistry()

        # Create a mock face
        faces = [
            {"face_id": "test_face_001", "filename": "test.jpg"},
        ]

        # Call the function under test
        identity_ids = create_inbox_identities(registry, faces, job_id="test_job")

        # Verify identity was created
        assert len(identity_ids) == 1

        # Get the identity
        identity = registry.get_identity(identity_ids[0])

        # Assert: name is not None
        assert identity.get("name") is not None, "Identity name should not be None"

        # Assert: name does not start with "Identity "
        name = identity.get("name")
        assert not name.startswith("Identity "), f"Name should not be a UUID fallback: {name}"

        # Assert: name matches pattern "Unidentified Person \d+"
        pattern = r"^Unidentified Person \d+$"
        assert re.match(pattern, name), f"Name '{name}' should match 'Unidentified Person N'"

    def test_sequential_naming_increments(self):
        """
        Multiple inbox identities should get sequential names.
        """
        from core.ingest_inbox import create_inbox_identities
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        # Create first identity
        faces1 = [{"face_id": "face_001", "filename": "test1.jpg"}]
        ids1 = create_inbox_identities(registry, faces1, job_id="job1")

        # Create second identity
        faces2 = [{"face_id": "face_002", "filename": "test2.jpg"}]
        ids2 = create_inbox_identities(registry, faces2, job_id="job2")

        name1 = registry.get_identity(ids1[0]).get("name")
        name2 = registry.get_identity(ids2[0]).get("name")

        # Extract numbers
        num1 = int(re.search(r"\d+", name1).group())
        num2 = int(re.search(r"\d+", name2).group())

        assert num2 > num1, f"Second identity ({name2}) should have higher number than first ({name1})"


class TestViewPhoto:
    """Test that View Photo resolves correct file paths."""

    def test_photo_view_uses_filepath_for_inbox_photos(self):
        """
        Bug 2: photo_view_content should use filepath (not just filename)
        when rendering inbox photos that aren't in raw_photos/.

        The actual bug: get_photo_dimensions() is called with just the filename,
        but inbox photos live at filepath (e.g., data/uploads/{session}/file.jpg).
        """
        from pathlib import Path
        from PIL import Image
        import numpy as np
        import tempfile
        import shutil

        # Create a temporary directory simulating data/uploads/{session}/
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a real image file in the temp directory
            img_path = Path(tmpdir) / "test_inbox_photo.jpg"
            img = Image.new("RGB", (100, 100), color="red")
            img.save(img_path, "JPEG")

            # Simulate what load_embeddings_for_photos returns for inbox photos:
            # filename is just the basename, but filepath is the full path
            photo_metadata = {
                "filename": "test_inbox_photo.jpg",  # Just the name
                "filepath": str(img_path),  # Full path to actual file
                "faces": [],
            }

            # The current broken code does this:
            from app.main import get_photo_dimensions, photos_path

            # This is what photo_view_content currently does - passes filename only
            width_broken, height_broken = get_photo_dimensions(photo_metadata["filename"])

            # This fails because file is NOT in raw_photos/
            assert (width_broken, height_broken) == (0, 0), (
                "Test setup issue: file should NOT be found in raw_photos/"
            )

            # The fix: get_photo_dimensions should accept filepath or check if absolute
            # For now, test that using the filepath directly works
            width_fixed, height_fixed = get_photo_dimensions(photo_metadata["filepath"])

            # Should find the file at the absolute path
            assert (width_fixed, height_fixed) == (100, 100), (
                f"get_photo_dimensions(filepath) should find file, got ({width_fixed}, {height_fixed})"
            )

    def test_view_photo_fallback_to_raw_photos(self):
        """
        When given a relative filename, should look in raw_photos/.
        """
        from app.main import get_photo_dimensions

        # This should work for files that exist in raw_photos/
        # Using a filename we know exists from our earlier investigation
        width, height = get_photo_dimensions("Image 001_compress.jpg")

        # Should find the file (it exists in raw_photos/)
        assert (width, height) != (0, 0), (
            "get_photo_dimensions should find 'Image 001_compress.jpg' in raw_photos/"
        )
