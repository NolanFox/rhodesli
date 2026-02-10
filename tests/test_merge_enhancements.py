"""
Tests for merge system enhancements (BE-001–BE-006).

BE-001–BE-004: Already implemented (direction, history, undo, name conflict).
BE-005: Source snapshot in merge_history for audit trail.
BE-006: Annotation retargeting when identities merge.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestMergeAuditSnapshot:
    """BE-005: Merge history records source snapshot for full audit trail."""

    def _make_registry(self, tmp_path):
        from core.registry import IdentityRegistry
        data = {
            "schema_version": 1,
            "history": [],
            "identities": {
                "target-1": {
                    "identity_id": "target-1",
                    "name": "Leon Capeluto",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-a"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "history": [],
                },
                "source-1": {
                    "identity_id": "source-1",
                    "name": "Unidentified Person 099",
                    "state": "PROPOSED",
                    "anchor_ids": ["face-b"],
                    "candidate_ids": ["face-c"],
                    "negative_ids": ["identity:rejected-1"],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "history": [],
                },
            },
        }
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        return IdentityRegistry.load(path)

    def _make_photo_registry(self, tmp_path):
        from core.photo_registry import PhotoRegistry
        data = {
            "schema_version": 1,
            "photos": {
                "photo-1": {"path": "img1.jpg", "face_ids": ["face-a"], "source": "test"},
                "photo-2": {"path": "img2.jpg", "face_ids": ["face-b", "face-c"], "source": "test"},
            },
            "face_to_photo": {
                "face-a": "photo-1",
                "face-b": "photo-2",
                "face-c": "photo-2",
            },
        }
        path = tmp_path / "photo_index.json"
        path.write_text(json.dumps(data))
        return PhotoRegistry.load(path)

    def test_merge_history_has_source_snapshot(self, tmp_path):
        """Merge history entry includes source_snapshot with full identity state."""
        registry = self._make_registry(tmp_path)
        photo_reg = self._make_photo_registry(tmp_path)

        result = registry.merge_identities(
            source_id="source-1", target_id="target-1",
            user_source="test", photo_registry=photo_reg
        )
        assert result["success"]

        target = registry.get_identity("target-1")
        entry = target["merge_history"][-1]
        assert "source_snapshot" in entry
        assert entry["source_snapshot"]["anchor_ids"] == ["face-b"]
        assert entry["source_snapshot"]["candidate_ids"] == ["face-c"]
        assert entry["source_snapshot"]["negative_ids"] == ["identity:rejected-1"]
        assert entry["source_snapshot"]["name"] == "Unidentified Person 099"
        assert entry["source_snapshot"]["state"] == "PROPOSED"

    def test_merge_history_has_target_snapshot_before(self, tmp_path):
        """Merge history includes target state BEFORE the merge."""
        registry = self._make_registry(tmp_path)
        photo_reg = self._make_photo_registry(tmp_path)

        result = registry.merge_identities(
            source_id="source-1", target_id="target-1",
            user_source="test", photo_registry=photo_reg
        )
        assert result["success"]

        target = registry.get_identity("target-1")
        entry = target["merge_history"][-1]
        assert "target_snapshot_before" in entry
        assert entry["target_snapshot_before"]["anchor_count"] == 1  # Had 1 before merge
        assert entry["target_snapshot_before"]["name"] == "Leon Capeluto"
        assert entry["target_snapshot_before"]["state"] == "CONFIRMED"

    def test_merge_history_snapshot_survives_undo(self, tmp_path):
        """After undo, the popped merge entry had full snapshots."""
        registry = self._make_registry(tmp_path)
        photo_reg = self._make_photo_registry(tmp_path)

        registry.merge_identities(
            source_id="source-1", target_id="target-1",
            user_source="test", photo_registry=photo_reg
        )

        # Capture the merge entry before undo
        target = registry.get_identity("target-1")
        entry = target["merge_history"][-1]
        assert "source_snapshot" in entry

        # Undo
        undo_result = registry.undo_merge("target-1", user_source="test")
        assert undo_result["success"]

        # Source is restored
        source = registry.get_identity("source-1")
        assert "merged_into" not in source


class TestAnnotationMerging:
    """BE-006: Annotations retarget when identities merge."""

    def test_merge_retargets_annotations(self, tmp_path):
        """Annotations targeting source identity move to target after merge."""
        from app.main import _merge_annotations, _invalidate_annotations_cache

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "ann-1": {
                    "annotation_id": "ann-1",
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "source-id",
                    "value": "Leon",
                    "confidence": "certain",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                },
                "ann-2": {
                    "annotation_id": "ann-2",
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Beach photo",
                    "confidence": "likely",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved",
                    "reviewed_by": None,
                    "reviewed_at": None,
                },
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            _merge_annotations("source-id", "target-id")

        saved = json.loads(ann_path.read_text())
        # Identity annotation was retargeted
        assert saved["annotations"]["ann-1"]["target_id"] == "target-id"
        # Photo annotation was NOT retargeted
        assert saved["annotations"]["ann-2"]["target_id"] == "photo-1"

    def test_merge_no_annotations_file(self, tmp_path):
        """_merge_annotations doesn't crash when annotations.json doesn't exist."""
        from app.main import _merge_annotations, _invalidate_annotations_cache

        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            # Should not raise
            _merge_annotations("source-id", "target-id")

    def test_merge_preserves_annotation_status(self, tmp_path):
        """Retargeted annotations keep their status (pending, approved, rejected)."""
        from app.main import _merge_annotations, _invalidate_annotations_cache

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "ann-approved": {
                    "annotation_id": "ann-approved",
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "source-id",
                    "value": "Victoria",
                    "confidence": "certain",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved",
                    "reviewed_by": "admin@test.com",
                    "reviewed_at": "2026-02-10T01:00:00Z",
                },
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        _invalidate_annotations_cache()

        with patch("app.main.data_path", tmp_path):
            _merge_annotations("source-id", "target-id")

        saved = json.loads(ann_path.read_text())
        assert saved["annotations"]["ann-approved"]["status"] == "approved"
        assert saved["annotations"]["ann-approved"]["target_id"] == "target-id"


class TestMergeSystemVerification:
    """Verification tests for existing BE-001–BE-004 functionality."""

    def _make_registry(self, tmp_path, identities):
        from core.registry import IdentityRegistry
        data = {"schema_version": 1, "history": [], "identities": identities}
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        return IdentityRegistry.load(path)

    def _make_photo_registry(self, tmp_path, photos, face_to_photo):
        from core.photo_registry import PhotoRegistry
        data = {"schema_version": 1, "photos": photos, "face_to_photo": face_to_photo}
        path = tmp_path / "photo_index.json"
        path.write_text(json.dumps(data))
        return PhotoRegistry.load(path)

    def test_co_occurrence_blocks_merge(self, tmp_path):
        """Two identities with faces in the same photo cannot merge."""
        registry = self._make_registry(tmp_path, {
            "id-a": {
                "identity_id": "id-a", "name": "A", "state": "CONFIRMED",
                "anchor_ids": ["face-1"], "candidate_ids": [], "negative_ids": [],
                "version_id": 1, "created_at": "2026-01-01", "updated_at": "2026-01-01", "history": [],
            },
            "id-b": {
                "identity_id": "id-b", "name": "B", "state": "CONFIRMED",
                "anchor_ids": ["face-2"], "candidate_ids": [], "negative_ids": [],
                "version_id": 1, "created_at": "2026-01-01", "updated_at": "2026-01-01", "history": [],
            },
        })
        photo_reg = self._make_photo_registry(tmp_path, {
            "photo-1": {"path": "img.jpg", "face_ids": ["face-1", "face-2"], "source": "test"},
        }, {"face-1": "photo-1", "face-2": "photo-1"})

        result = registry.merge_identities("id-a", "id-b", "test", photo_reg)
        assert not result["success"]
        assert result["reason"] == "co_occurrence"

    def test_undo_restores_source_identity(self, tmp_path):
        """Undo merge fully restores the source identity."""
        registry = self._make_registry(tmp_path, {
            "target": {
                "identity_id": "target", "name": "Leon", "state": "CONFIRMED",
                "anchor_ids": ["face-a"], "candidate_ids": [], "negative_ids": [],
                "version_id": 1, "created_at": "2026-01-01", "updated_at": "2026-01-01", "history": [],
            },
            "source": {
                "identity_id": "source", "name": "Unidentified Person 099", "state": "INBOX",
                "anchor_ids": ["face-b"], "candidate_ids": [], "negative_ids": [],
                "version_id": 1, "created_at": "2026-01-01", "updated_at": "2026-01-01", "history": [],
            },
        })
        photo_reg = self._make_photo_registry(tmp_path, {
            "p1": {"path": "a.jpg", "face_ids": ["face-a"], "source": "test"},
            "p2": {"path": "b.jpg", "face_ids": ["face-b"], "source": "test"},
        }, {"face-a": "p1", "face-b": "p2"})

        # source is unnamed, target is named — source should get absorbed
        registry.merge_identities("source", "target", "test", photo_reg)
        assert "merged_into" in registry._identities["source"]

        result = registry.undo_merge("target", "test")
        assert result["success"]
        assert "merged_into" not in registry._identities["source"]
        assert "face-b" not in registry._identities["target"]["anchor_ids"]

    def test_named_identity_always_survives(self, tmp_path):
        """Named identity becomes target even if passed as source (direction auto-correction)."""
        registry = self._make_registry(tmp_path, {
            "named": {
                "identity_id": "named", "name": "Victoria", "state": "CONFIRMED",
                "anchor_ids": ["face-a"], "candidate_ids": [], "negative_ids": [],
                "version_id": 1, "created_at": "2026-01-01", "updated_at": "2026-01-01", "history": [],
            },
            "unnamed": {
                "identity_id": "unnamed", "name": "Unidentified Person 001", "state": "INBOX",
                "anchor_ids": ["face-b"], "candidate_ids": [], "negative_ids": [],
                "version_id": 1, "created_at": "2026-01-01", "updated_at": "2026-01-01", "history": [],
            },
        })
        photo_reg = self._make_photo_registry(tmp_path, {
            "p1": {"path": "a.jpg", "face_ids": ["face-a"], "source": "test"},
            "p2": {"path": "b.jpg", "face_ids": ["face-b"], "source": "test"},
        }, {"face-a": "p1", "face-b": "p2"})

        # Pass named as source — should be auto-corrected to target
        result = registry.merge_identities("named", "unnamed", "test", photo_reg)
        assert result["success"]
        assert result["target_id"] == "named"
        assert result["direction_swapped"]
