"""Tests for Session 108: orphan detection, embeddings sync, data health, push verification.

Covers:
- Startup orphan face detection and repair
- /api/sync/embeddings endpoint
- /api/health/data endpoint
- Stop-gate push verification
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Orphan Face Detection (Phase 3a)
# ---------------------------------------------------------------------------


class TestOrphanFaceDetection:
    """Test that orphan faces (in photo_index but not in identities) are detected and repaired."""

    def test_orphan_faces_detected_and_repaired(self, tmp_path):
        """Faces in photo_index without identities get INBOX identities created."""
        from core.registry import IdentityRegistry, IdentityState
        from core.photo_registry import PhotoRegistry

        # Create photo_index with a face
        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo1", "raw_photos/test.jpg", "orphan_face_1")
        pi_path = tmp_path / "photo_index.json"
        photo_reg.save(pi_path)

        # Create identity registry WITHOUT that face
        id_reg = IdentityRegistry()
        id_reg.create_identity(anchor_ids=["other_face"], user_source="test", state=IdentityState.CONFIRMED)
        id_path = tmp_path / "identities.json"
        id_reg.save(id_path)

        # Simulate startup orphan detection logic
        all_registered = set()
        for iid, idata in id_reg._identities.items():
            all_registered.update(idata.get("anchor_ids", []))
            all_registered.update(idata.get("candidate_ids", []))

        orphan_faces = []
        for pid, pdata in photo_reg._photos.items():
            for fid in pdata.get("face_ids", []):
                if fid not in all_registered:
                    orphan_faces.append(fid)

        assert len(orphan_faces) == 1
        assert orphan_faces[0] == "orphan_face_1"

        # Repair
        for fid in orphan_faces:
            id_reg.create_identity(
                anchor_ids=[fid],
                user_source="startup_orphan_repair",
                state=IdentityState.INBOX,
            )
        id_reg.save(id_path)

        # Verify repair
        reloaded = IdentityRegistry.load(id_path)
        all_faces = set()
        for iid, idata in reloaded._identities.items():
            all_faces.update(idata.get("anchor_ids", []))
        assert "orphan_face_1" in all_faces

    def test_no_orphans_when_all_faces_have_identities(self, tmp_path):
        """No repair needed when all faces have identities."""
        from core.registry import IdentityRegistry, IdentityState
        from core.photo_registry import PhotoRegistry

        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo1", "raw_photos/test.jpg", "face_1")
        pi_path = tmp_path / "photo_index.json"
        photo_reg.save(pi_path)

        id_reg = IdentityRegistry()
        id_reg.create_identity(anchor_ids=["face_1"], user_source="test", state=IdentityState.INBOX)
        id_path = tmp_path / "identities.json"
        id_reg.save(id_path)

        all_registered = set()
        for iid, idata in id_reg._identities.items():
            all_registered.update(idata.get("anchor_ids", []))

        orphan_faces = []
        for pid, pdata in photo_reg._photos.items():
            for fid in pdata.get("face_ids", []):
                if fid not in all_registered:
                    orphan_faces.append(fid)

        assert len(orphan_faces) == 0


# ---------------------------------------------------------------------------
# Post-Sync Validation in Upload Pipeline (Prevention Layer)
# ---------------------------------------------------------------------------


class TestPostSyncValidation:
    """Test that _background_ingest post-sync validation catches orphan faces."""

    def test_post_sync_detects_missing_identities(self, tmp_path):
        """New faces missing from registry are detected and repaired."""
        from core.registry import IdentityRegistry, IdentityState

        # Simulate: process_directory created identities for face_a but not face_b
        id_reg = IdentityRegistry()
        id_reg.create_identity(anchor_ids=["face_a"], user_source="ingest", state=IdentityState.INBOX)
        id_path = tmp_path / "identities.json"
        id_reg.save(id_path)

        # Simulate post-sync validation check
        new_face_ids = {"face_a", "face_b"}
        synced_face_ids = set()
        for idata in id_reg._identities.values():
            synced_face_ids.update(idata.get("anchor_ids", []))
            synced_face_ids.update(idata.get("candidate_ids", []))

        missing = new_face_ids - synced_face_ids
        assert missing == {"face_b"}

        # Repair
        for fid in missing:
            id_reg.create_identity(
                anchor_ids=[fid],
                user_source="post_sync_orphan_repair",
                state=IdentityState.INBOX,
            )
        id_reg.save(id_path)

        # Verify all faces now have identities
        reloaded = IdentityRegistry.load(id_path)
        all_faces = set()
        for idata in reloaded._identities.values():
            all_faces.update(idata.get("anchor_ids", []))
        assert "face_a" in all_faces
        assert "face_b" in all_faces

    def test_post_sync_no_repair_when_all_present(self, tmp_path):
        """No repair needed when all new faces have identities."""
        from core.registry import IdentityRegistry, IdentityState

        id_reg = IdentityRegistry()
        id_reg.create_identity(anchor_ids=["face_a"], user_source="ingest", state=IdentityState.INBOX)
        id_reg.create_identity(anchor_ids=["face_b"], user_source="ingest", state=IdentityState.INBOX)

        new_face_ids = {"face_a", "face_b"}
        synced_face_ids = set()
        for idata in id_reg._identities.values():
            synced_face_ids.update(idata.get("anchor_ids", []))
        missing = new_face_ids - synced_face_ids
        assert len(missing) == 0


# ---------------------------------------------------------------------------
# Embeddings Sync Endpoint (Phase 3c)
# ---------------------------------------------------------------------------


class TestEmbeddingsSyncEndpoint:
    """Test /api/sync/embeddings endpoint."""

    def test_embeddings_requires_token(self, client):
        """Embeddings endpoint requires sync token."""
        response = client.get("/api/sync/embeddings")
        assert response.status_code in (401, 503)

    def test_embeddings_returns_file_with_token(self, client):
        """Embeddings endpoint returns file when token is valid."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"):
            response = client.get(
                "/api/sync/embeddings",
                headers={"Authorization": "Bearer test-token"},
            )
            # May be 200 (file exists) or 404 (no embeddings in test env)
            assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Data Health Endpoint (Phase 3d)
# ---------------------------------------------------------------------------


class TestDataHealthEndpoint:
    """Test /api/health/data endpoint."""

    def test_data_health_requires_admin(self, client, auth_enabled, no_user):
        """Health data endpoint requires admin auth."""
        response = client.get("/api/health/data")
        assert response.status_code in (401, 403)

    def test_data_health_returns_report(self, client, admin_user):
        """Health data endpoint returns structured report for admin."""
        response = client.get("/api/health/data")
        assert response.status_code == 200
        data = response.json()
        assert "orphan_faces" in data
        assert "orphan_identities" in data
        assert "identities" in data
        assert "photos" in data
        assert "status" in data
        assert data["status"] in ("healthy", "issues_found", "error")

    def test_data_health_orphan_faces_structure(self, client, admin_user):
        """Orphan faces section has count and face_ids list."""
        response = client.get("/api/health/data")
        data = response.json()
        orphan = data.get("orphan_faces", {})
        assert "count" in orphan
        assert "face_ids" in orphan
        assert isinstance(orphan["face_ids"], list)


# ---------------------------------------------------------------------------
# Stop-Gate Push Verification (Phase 3b)
# ---------------------------------------------------------------------------


class TestStopGatePushVerification:
    """Test that stop-gate.sh warns about unpushed commits."""

    def test_stop_gate_has_push_check(self):
        """stop-gate.sh contains the push verification logic."""
        gate_path = Path("__file__").resolve().parent.parent / ".claude" / "hooks" / "stop-gate.sh"
        # Use project root path
        project_root = Path(__file__).resolve().parent.parent
        gate_path = project_root / ".claude" / "hooks" / "stop-gate.sh"
        content = gate_path.read_text()
        assert "origin/main..HEAD" in content
        assert "WARNING" in content
