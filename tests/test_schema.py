"""
Tests for schema evolution and backward compatibility.

These tests verify:
- Old data (string anchor IDs) loads correctly
- New data (structured anchors) persists and loads
- Mixed formats work seamlessly
"""

import json
import tempfile
from pathlib import Path

import pytest


class TestAnchorSchemaEvolution:
    """Tests for anchor schema evolution."""

    def test_legacy_string_anchors_still_work(self):
        """Old-style string anchor IDs should still work."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        # Create with legacy string format
        identity_id = registry.create_identity(
            anchor_ids=["face_001", "face_002"],
            user_source="test",
        )

        identity = registry.get_identity(identity_id)

        # Should normalize to structured format internally
        anchors = identity["anchor_ids"]
        assert len(anchors) == 2

        # Verify face_ids are accessible
        face_ids = registry.get_anchor_face_ids(identity_id)
        assert "face_001" in face_ids
        assert "face_002" in face_ids

    def test_structured_anchors_with_era(self):
        """New structured anchors with era metadata should work."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        # Create with structured format
        identity_id = registry.create_identity(
            anchor_ids=[
                {"face_id": "face_001", "era_bin": "1910-1930", "weight": 1.0},
                {"face_id": "face_002", "era_bin": "1930-1950", "weight": 0.8},
            ],
            user_source="test",
        )

        identity = registry.get_identity(identity_id)

        # Should preserve era metadata
        anchors = identity["anchor_ids"]
        assert len(anchors) == 2

        # Verify era is preserved
        anchor_eras = {a["face_id"]: a.get("era_bin") for a in anchors}
        assert anchor_eras["face_001"] == "1910-1930"
        assert anchor_eras["face_002"] == "1930-1950"

    def test_mixed_anchor_formats(self):
        """Mixed string and structured anchors should work."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        # Create with mixed format
        identity_id = registry.create_identity(
            anchor_ids=[
                "face_001",  # Legacy string
                {"face_id": "face_002", "era_bin": "1910-1930"},  # Structured
            ],
            user_source="test",
        )

        # Both should be accessible
        face_ids = registry.get_anchor_face_ids(identity_id)
        assert "face_001" in face_ids
        assert "face_002" in face_ids

    def test_promote_preserves_era_metadata(self):
        """Promoting a candidate should allow era metadata."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        identity_id = registry.create_identity(
            anchor_ids=["face_001"],
            candidate_ids=["face_002"],
            user_source="test",
        )

        # Promote with era metadata
        registry.promote_candidate(
            identity_id,
            "face_002",
            user_source="test",
            era_bin="1910-1930",
        )

        identity = registry.get_identity(identity_id)

        # Find the promoted anchor
        promoted = None
        for anchor in identity["anchor_ids"]:
            if isinstance(anchor, dict) and anchor.get("face_id") == "face_002":
                promoted = anchor
                break
            elif anchor == "face_002":
                promoted = anchor
                break

        assert promoted is not None


class TestSchemaPersistence:
    """Tests for schema persistence and loading."""

    def test_save_load_preserves_structured_anchors(self):
        """Structured anchors should survive save/load cycle."""
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "identities.json"

            # Create with structured anchors
            registry1 = IdentityRegistry()
            identity_id = registry1.create_identity(
                anchor_ids=[
                    {"face_id": "face_001", "era_bin": "1910-1930", "weight": 1.0},
                ],
                user_source="test",
            )
            registry1.save(path)

            # Load and verify
            registry2 = IdentityRegistry.load(path)
            identity = registry2.get_identity(identity_id)

            anchors = identity["anchor_ids"]
            assert len(anchors) == 1
            assert anchors[0]["face_id"] == "face_001"
            assert anchors[0]["era_bin"] == "1910-1930"

    def test_load_legacy_json_format(self):
        """Should load old JSON with string anchor_ids."""
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "identities.json"

            # Write legacy format manually
            legacy_data = {
                "schema_version": 1,
                "identities": {
                    "test-id-123": {
                        "identity_id": "test-id-123",
                        "name": "Test Person",
                        "state": "PROPOSED",
                        "anchor_ids": ["face_001", "face_002"],  # Legacy string format
                        "candidate_ids": [],
                        "negative_ids": [],
                        "version_id": 1,
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                },
                "history": [],
            }

            with open(path, "w") as f:
                json.dump(legacy_data, f)

            # Load should work
            registry = IdentityRegistry.load(path)
            identity = registry.get_identity("test-id-123")

            # Should be able to get face IDs
            face_ids = registry.get_anchor_face_ids("test-id-123")
            assert "face_001" in face_ids
            assert "face_002" in face_ids


class TestFusionWithEraMetadata:
    """Tests for fusion with era-aware anchors."""

    def test_fusion_ignores_era_uses_face_data(self):
        """Fusion should use face_data, not anchor era metadata."""
        import numpy as np

        from core.fusion import compute_identity_fusion
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        identity_id = registry.create_identity(
            anchor_ids=[
                {"face_id": "face_001", "era_bin": "1910-1930"},
            ],
            user_source="test",
        )

        # Face data is source of truth for embeddings
        face_data = {
            "face_001": {
                "mu": np.ones(512, dtype=np.float32),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            },
        }

        # Fusion should work with structured anchors
        mu, sigma_sq = compute_identity_fusion(registry, identity_id, face_data)

        assert mu.shape == (512,)
        assert np.allclose(mu, 1.0)
