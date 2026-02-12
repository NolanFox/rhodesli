"""
Tests for data integrity checker and test isolation verification.

These tests ensure:
1. The integrity checker catches test contamination
2. The integrity checker passes on clean data
3. Running the test suite does not modify real data files
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestIntegrityChecker:
    """Tests for scripts/check_data_integrity.py checks."""

    def test_catches_test_collection(self, tmp_path):
        """Integrity checker flags 'Test Collection' as contamination."""
        pi = {
            "photos": {
                "photo1": {"path": "test.jpg", "collection": "Test Collection", "source": "Test"}
            },
            "face_to_photo": {},
        }
        (tmp_path / "photo_index.json").write_text(json.dumps(pi))
        (tmp_path / "identities.json").write_text(json.dumps({"identities": {}}))

        # Import the module functions and override data_dir
        import scripts.check_data_integrity as checker
        original_data_dir = checker.data_dir
        checker.data_dir = tmp_path
        checker.errors = []
        checker.warnings = []

        try:
            checker.check_no_test_contamination()
            assert len(checker.errors) > 0
            assert "TEST CONTAMINATION" in checker.errors[0]
        finally:
            checker.data_dir = original_data_dir

    def test_passes_clean_data(self, tmp_path):
        """Integrity checker passes on valid data."""
        pi = {
            "photos": {
                "photo1": {"path": "img.jpg", "collection": "Family Album", "source": "Scan"},
            },
            "face_to_photo": {},
        }
        ids = {
            "identities": {
                "id1": {"name": "John Doe", "state": "CONFIRMED"},
            },
        }
        (tmp_path / "photo_index.json").write_text(json.dumps(pi))
        (tmp_path / "identities.json").write_text(json.dumps(ids))

        import scripts.check_data_integrity as checker
        original_data_dir = checker.data_dir
        checker.data_dir = tmp_path
        checker.errors = []
        checker.warnings = []

        try:
            checker.check_no_test_contamination()
            checker.check_identity_integrity()
            checker.check_photo_count_consistency()
            checker.check_face_to_photo_consistency()
            assert len(checker.errors) == 0
        finally:
            checker.data_dir = original_data_dir

    def test_catches_test_identity_name(self, tmp_path):
        """Integrity checker flags test-related identity names."""
        ids = {
            "identities": {
                "id1": {"name": "Test Person Name", "state": "CONFIRMED"},
            },
        }
        (tmp_path / "identities.json").write_text(json.dumps(ids))

        import scripts.check_data_integrity as checker
        original_data_dir = checker.data_dir
        checker.data_dir = tmp_path
        checker.errors = []
        checker.warnings = []

        try:
            checker.check_identity_integrity()
            assert len(checker.errors) > 0
            assert "TEST CONTAMINATION" in checker.errors[0]
        finally:
            checker.data_dir = original_data_dir

    def test_catches_invalid_state(self, tmp_path):
        """Integrity checker flags invalid identity states."""
        ids = {
            "identities": {
                "id1": {"name": "Jane Doe", "state": "INVALID_STATE"},
            },
        }
        (tmp_path / "identities.json").write_text(json.dumps(ids))

        import scripts.check_data_integrity as checker
        original_data_dir = checker.data_dir
        checker.data_dir = tmp_path
        checker.errors = []
        checker.warnings = []

        try:
            checker.check_identity_integrity()
            assert len(checker.errors) > 0
            assert "INVALID STATE" in checker.errors[0]
        finally:
            checker.data_dir = original_data_dir


class TestRealDataIntegrity:
    """Verify real data files pass integrity checks."""

    def test_production_data_passes_integrity_check(self):
        """Real data files in data/ pass all integrity checks."""
        result = subprocess.run(
            [sys.executable, "scripts/check_data_integrity.py"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Integrity check failed:\n{result.stdout}"

    def test_no_test_collection_in_real_data(self):
        """No photos in data/photo_index.json have test-related values."""
        pi_path = Path("data/photo_index.json")
        if not pi_path.exists():
            pytest.skip("No data/photo_index.json")

        pi = json.loads(pi_path.read_text())
        photos = pi.get("photos", pi)

        for pid, p in photos.items():
            if not isinstance(p, dict):
                continue
            for field in ("collection", "source"):
                val = p.get(field, "")
                assert "test" not in val.lower(), (
                    f"Photo {pid} has {field}='{val}' — test contamination!"
                )

    def test_no_test_data_in_annotations(self):
        """No test-created annotations exist in production annotations.json."""
        ann_path = Path("data/annotations.json")
        if not ann_path.exists():
            pytest.skip("No data/annotations.json")

        ann = json.loads(ann_path.read_text())
        annotations = ann.get("annotations", {})

        test_patterns = ["test@test.com", "user@test.com", "admin@test.com",
                         "target-123", "target-id", "source-456"]

        for ann_id, a in annotations.items():
            ann_str = json.dumps(a)
            for pattern in test_patterns:
                assert pattern not in ann_str, (
                    f"Annotation {ann_id} contains test pattern '{pattern}'"
                )

    def test_no_test_data_in_identity_history(self):
        """No test-created entries exist in production identity history."""
        ids_path = Path("data/identities.json")
        if not ids_path.exists():
            pytest.skip("No data/identities.json")

        data = json.loads(ids_path.read_text())
        history = data.get("history", [])

        test_patterns = ["Test Person Name", "restoration_note", "test@test.com"]

        for i, h in enumerate(history):
            meta_str = json.dumps(h.get("metadata", {}))
            for pattern in test_patterns:
                assert pattern not in meta_str, (
                    f"History entry [{i}] contains test pattern '{pattern}'"
                )
