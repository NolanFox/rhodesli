"""Tests for sync API endpoints.

Tests the permission matrix and response format for:
- GET /api/sync/status (public)
- GET /api/sync/identities (token-authenticated)
- GET /api/sync/photo-index (token-authenticated)
- GET /api/sync/annotations (token-authenticated)
- POST /api/sync/push (token-authenticated, writes data)
"""

import json

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# /api/sync/status — public, no auth needed
# ---------------------------------------------------------------------------

class TestSyncStatus:
    """Status endpoint is public and returns data stats."""

    def test_status_returns_200(self, client):
        """Status endpoint is accessible without any auth."""
        response = client.get("/api/sync/status")
        assert response.status_code == 200

    def test_status_contains_expected_fields(self, client):
        """Status response includes identity and photo counts."""
        response = client.get("/api/sync/status")
        data = response.json()
        assert "identities" in data
        assert "confirmed" in data
        assert "proposed" in data
        assert "inbox" in data
        assert "photos" in data
        assert "timestamp" in data

    def test_status_works_with_auth_enabled(self, client, auth_enabled, no_user):
        """Status endpoint works even when auth is enabled and no user is logged in."""
        response = client.get("/api/sync/status")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# /api/sync/identities — requires valid RHODESLI_SYNC_TOKEN
# ---------------------------------------------------------------------------

class TestSyncIdentities:
    """Identities endpoint requires a valid sync token."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get("/api/sync/identities")
        assert response.status_code == 401

    def test_rejects_wrong_token(self, client):
        """Request with wrong token gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get(
                "/api/sync/identities",
                headers={"Authorization": "Bearer wrong-token"},
            )
        assert response.status_code == 401

    def test_returns_503_when_token_not_configured(self, client):
        """When RHODESLI_SYNC_TOKEN is empty, returns 503."""
        with patch("app.main.SYNC_API_TOKEN", ""):
            response = client.get(
                "/api/sync/identities",
                headers={"Authorization": "Bearer some-token"},
            )
        assert response.status_code == 503

    def test_returns_data_with_valid_token(self, client, tmp_path):
        """Valid token returns identities JSON."""
        test_data = {
            "schema_version": 1,
            "identities": {"id-1": {"name": "Test Person", "state": "CONFIRMED"}},
        }
        (tmp_path / "identities.json").write_text(json.dumps(test_data))

        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/identities",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["schema_version"] == 1
        assert "id-1" in data["identities"]

    def test_returns_404_when_file_missing(self, client, tmp_path):
        """Returns 404 when identities.json doesn't exist."""
        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/identities",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/sync/photo-index — requires valid RHODESLI_SYNC_TOKEN
# ---------------------------------------------------------------------------

class TestSyncPhotoIndex:
    """Photo index endpoint requires a valid sync token."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get("/api/sync/photo-index")
        assert response.status_code == 401

    def test_rejects_wrong_token(self, client):
        """Request with wrong token gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get(
                "/api/sync/photo-index",
                headers={"Authorization": "Bearer wrong-token"},
            )
        assert response.status_code == 401

    def test_returns_data_with_valid_token(self, client, tmp_path):
        """Valid token returns photo index JSON."""
        test_data = {
            "schema_version": 1,
            "photos": {"photo-1": {"path": "test.jpg", "face_ids": []}},
            "face_to_photo": {},
        }
        (tmp_path / "photo_index.json").write_text(json.dumps(test_data))

        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/photo-index",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "photos" in data
        assert "photo-1" in data["photos"]

    def test_returns_404_when_file_missing(self, client, tmp_path):
        """Returns 404 when photo_index.json doesn't exist."""
        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/photo-index",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/sync/push — push data to production (token-authenticated)
# ---------------------------------------------------------------------------

class TestSyncPush:
    """Push endpoint writes identities and/or photo_index to the data volume."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.post(
                "/api/sync/push",
                json={"identities": {"identities": {}}},
            )
        assert response.status_code == 401

    def test_rejects_wrong_token(self, client):
        """Request with wrong token gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer wrong-token"},
                json={"identities": {"identities": {}}},
            )
        assert response.status_code == 401

    def test_returns_503_when_token_not_configured(self, client):
        """When RHODESLI_SYNC_TOKEN is empty, returns 503."""
        with patch("app.main.SYNC_API_TOKEN", ""):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer some-token"},
                json={"identities": {"identities": {}}},
            )
        assert response.status_code == 503

    def test_rejects_empty_body(self, client, tmp_path):
        """Returns 400 when neither identities nor photo_index provided."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={},
            )
        assert response.status_code == 400

    def test_pushes_identities(self, client, tmp_path):
        """Writes identities.json when identities key provided."""
        # Seed existing file so backup can be created
        existing = {"schema_version": 1, "identities": {"old": {"state": "CONFIRMED"}}}
        (tmp_path / "identities.json").write_text(json.dumps(existing))

        new_data = {
            "schema_version": 1,
            "identities": {
                "id-1": {"name": "Alice", "state": "CONFIRMED"},
                "id-2": {"name": "Bob", "state": "INBOX"},
            },
        }

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"identities": new_data},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["results"]["identities"]["status"] == "written"
        assert data["results"]["identities"]["count"] == 2

        # Verify file was written
        written = json.loads((tmp_path / "identities.json").read_text())
        assert "id-1" in written["identities"]
        assert "id-2" in written["identities"]

        # Verify backup was created
        backups = list(tmp_path.glob("identities.json.bak.*"))
        assert len(backups) == 1

    def test_pushes_photo_index(self, client, tmp_path):
        """Writes photo_index.json when photo_index key provided."""
        existing = {"schema_version": 1, "photos": {}, "face_to_photo": {}}
        (tmp_path / "photo_index.json").write_text(json.dumps(existing))

        new_data = {
            "schema_version": 1,
            "photos": {
                "photo-1": {"path": "test.jpg", "face_ids": ["f1"]},
                "photo-2": {"path": "test2.jpg", "face_ids": ["f2"]},
            },
            "face_to_photo": {"f1": "photo-1", "f2": "photo-2"},
        }

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"photo_index": new_data},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["results"]["photo_index"]["count"] == 2

        # Verify file was written
        written = json.loads((tmp_path / "photo_index.json").read_text())
        assert "photo-1" in written["photos"]

    def test_pushes_both(self, client, tmp_path):
        """Can push both identities and photo_index in one request."""
        (tmp_path / "identities.json").write_text('{"identities": {}}')
        (tmp_path / "photo_index.json").write_text('{"photos": {}, "face_to_photo": {}}')

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "identities": {"identities": {"id-1": {"state": "INBOX"}}},
                    "photo_index": {"photos": {"p-1": {"path": "x.jpg"}}, "face_to_photo": {}},
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "identities" in data["results"]
        assert "photo_index" in data["results"]

    def test_creates_backup_before_overwrite(self, client, tmp_path):
        """Existing files are backed up before being overwritten."""
        original = {"identities": {"orig": {"state": "CONFIRMED", "name": "Original"}}}
        (tmp_path / "identities.json").write_text(json.dumps(original))

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"identities": {"identities": {"new": {"state": "INBOX"}}}},
            )
        assert response.status_code == 200

        # Backup contains original data
        backups = list(tmp_path.glob("identities.json.bak.*"))
        assert len(backups) == 1
        backup_data = json.loads(backups[0].read_text())
        assert "orig" in backup_data["identities"]

    def test_works_without_existing_file(self, client, tmp_path):
        """Push works even when files don't exist yet (no backup needed)."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"identities": {"identities": {"id-1": {"state": "INBOX"}}}},
            )
        assert response.status_code == 200
        assert (tmp_path / "identities.json").exists()

    def test_pushes_annotations(self, client, tmp_path):
        """Writes annotations.json when annotations key provided."""
        from app.main import _invalidate_annotations_cache
        existing = {"schema_version": 1, "annotations": {}}
        (tmp_path / "annotations.json").write_text(json.dumps(existing))

        new_data = {
            "schema_version": 1,
            "annotations": {
                "ann-1": {
                    "annotation_id": "ann-1",
                    "type": "story",
                    "target_type": "identity",
                    "target_id": "test-id",
                    "value": "Test annotation",
                    "status": "pending",
                    "submitted_by": "test@example.com",
                },
            },
        }

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"annotations": new_data},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["results"]["annotations"]["status"] == "written"
        assert data["results"]["annotations"]["count"] == 1

        # Verify file was written
        written = json.loads((tmp_path / "annotations.json").read_text())
        assert "ann-1" in written["annotations"]

        # Verify backup was created
        backups = list(tmp_path.glob("annotations.json.bak.*"))
        assert len(backups) == 1

    def test_push_annotations_only_accepted(self, client, tmp_path):
        """Push request with only annotations (no identities/photo_index) is valid."""
        (tmp_path / "annotations.json").write_text('{"schema_version": 1, "annotations": {}}')

        from app.main import _invalidate_annotations_cache
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"annotations": {"schema_version": 1, "annotations": {"a": {"type": "story"}}}},
            )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/sync/annotations — requires valid RHODESLI_SYNC_TOKEN
# ---------------------------------------------------------------------------

class TestSyncAnnotations:
    """Annotations endpoint requires a valid sync token."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get("/api/sync/annotations")
        assert response.status_code == 401

    def test_returns_annotations_with_valid_token(self, client, tmp_path):
        """Valid token returns annotations JSON."""
        from app.main import _invalidate_annotations_cache
        test_data = {
            "schema_version": 1,
            "annotations": {
                "ann-1": {
                    "annotation_id": "ann-1",
                    "type": "story",
                    "value": "Test story",
                    "status": "pending",
                },
            },
        }
        (tmp_path / "annotations.json").write_text(json.dumps(test_data))

        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.get(
                "/api/sync/annotations",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["schema_version"] == 1
        assert "ann-1" in data["annotations"]

    def test_returns_empty_when_no_annotations(self, client, tmp_path):
        """Returns default empty structure when annotations.json is empty."""
        from app.main import _invalidate_annotations_cache
        (tmp_path / "annotations.json").write_text('{"schema_version": 1, "annotations": {}}')

        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.get(
                "/api/sync/annotations",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["annotations"] == {}


# ---------------------------------------------------------------------------
# Deployment Safety — annotations must NOT be overwritten from bundle
# ---------------------------------------------------------------------------

class TestAnnotationDeploySafety:
    """Verify annotations.json is not in deploy/push paths that overwrite production."""

    def test_annotations_not_in_optional_sync_files(self):
        """annotations.json must NOT be in OPTIONAL_SYNC_FILES (would overwrite on deploy)."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES
        assert "annotations.json" not in OPTIONAL_SYNC_FILES, \
            "annotations.json must NOT be in OPTIONAL_SYNC_FILES — it is production-origin data"

    def test_annotations_not_in_required_data_files(self):
        """annotations.json must NOT be in REQUIRED_DATA_FILES."""
        from scripts.init_railway_volume import REQUIRED_DATA_FILES
        assert "annotations.json" not in REQUIRED_DATA_FILES, \
            "annotations.json must NOT be in REQUIRED_DATA_FILES — it is production-origin data"

    def test_annotations_not_in_push_data_files(self):
        """annotations.json must NOT be pushed by push_to_production.py."""
        import ast
        from pathlib import Path
        script_path = Path(__file__).parent.parent / "scripts" / "push_to_production.py"
        source = script_path.read_text()
        assert "annotations.json" not in source or "NOT pushed" in source, \
            "push_to_production.py must NOT include annotations.json in DATA_FILES"


class TestCorrectionsLogDeploySafety:
    """Verify corrections_log.json is not in deploy/push paths that overwrite production.

    corrections_log.json is production-origin data — written by users submitting date
    corrections via the UI. Must NEVER be overwritten by deploy pipeline.
    """

    def test_corrections_log_not_in_optional_sync_files(self):
        """corrections_log.json must NOT be in OPTIONAL_SYNC_FILES."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES
        assert "corrections_log.json" not in OPTIONAL_SYNC_FILES, \
            "corrections_log.json must NOT be in OPTIONAL_SYNC_FILES — it is production-origin data"

    def test_corrections_log_not_in_required_data_files(self):
        """corrections_log.json must NOT be in REQUIRED_DATA_FILES."""
        from scripts.init_railway_volume import REQUIRED_DATA_FILES
        assert "corrections_log.json" not in REQUIRED_DATA_FILES, \
            "corrections_log.json must NOT be in REQUIRED_DATA_FILES — it is production-origin data"

    def test_corrections_log_not_in_push_data_files(self):
        """corrections_log.json must NOT be pushed by push_to_production.py."""
        from pathlib import Path
        script_path = Path(__file__).parent.parent / "scripts" / "push_to_production.py"
        source = script_path.read_text()
        assert "corrections_log.json" not in source or "NOT pushed" in source, \
            "push_to_production.py must NOT include corrections_log.json in DATA_FILES"


class TestMLReviewDecisionsDeploySafety:
    """Verify ml_review_decisions.json is not in deploy/push paths.

    ml_review_decisions.json is production-origin data — written by admin
    accept/reject actions on ML birth year estimates. Must NEVER be overwritten.
    """

    def test_ml_review_decisions_not_in_optional_sync_files(self):
        """ml_review_decisions.json must NOT be in OPTIONAL_SYNC_FILES."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES
        assert "ml_review_decisions.json" not in OPTIONAL_SYNC_FILES, \
            "ml_review_decisions.json must NOT be in OPTIONAL_SYNC_FILES — it is production-origin data"

    def test_ml_review_decisions_not_in_required_data_files(self):
        """ml_review_decisions.json must NOT be in REQUIRED_DATA_FILES."""
        from scripts.init_railway_volume import REQUIRED_DATA_FILES
        assert "ml_review_decisions.json" not in REQUIRED_DATA_FILES, \
            "ml_review_decisions.json must NOT be in REQUIRED_DATA_FILES — it is production-origin data"


class TestGroundTruthDeploySafety:
    """Verify ground_truth_birth_years.json is not in deploy/push paths.

    ground_truth_birth_years.json is production-origin data — written by admin
    when accepting ML birth year estimates. Must NEVER be overwritten.
    """

    def test_ground_truth_not_in_optional_sync_files(self):
        """ground_truth_birth_years.json must NOT be in OPTIONAL_SYNC_FILES."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES
        assert "ground_truth_birth_years.json" not in OPTIONAL_SYNC_FILES, \
            "ground_truth_birth_years.json must NOT be in OPTIONAL_SYNC_FILES — it is production-origin data"

    def test_ground_truth_not_in_required_data_files(self):
        """ground_truth_birth_years.json must NOT be in REQUIRED_DATA_FILES."""
        from scripts.init_railway_volume import REQUIRED_DATA_FILES
        assert "ground_truth_birth_years.json" not in REQUIRED_DATA_FILES, \
            "ground_truth_birth_years.json must NOT be in REQUIRED_DATA_FILES — it is production-origin data"


class TestDockerfileModuleCoverage:
    """Verify that all rhodesli_ml modules imported by the web app are in the Dockerfile.

    /connect and /tree were broken in production for 4 sessions because
    rhodesli_ml/ was not copied into the Docker image. This test prevents regression.
    """

    def test_dockerfile_copies_rhodesli_ml_graph(self):
        """Dockerfile must COPY rhodesli_ml/graph/ — needed by /connect and /tree."""
        from pathlib import Path
        dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
        assert "rhodesli_ml/graph/" in dockerfile, \
            "Dockerfile must COPY rhodesli_ml/graph/ — /connect and /tree import from it"

    def test_dockerfile_copies_rhodesli_ml_importers(self):
        """Dockerfile must COPY rhodesli_ml/importers/ — needed by /admin/gedcom."""
        from pathlib import Path
        dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
        assert "rhodesli_ml/importers/" in dockerfile, \
            "Dockerfile must COPY rhodesli_ml/importers/ — /admin/gedcom imports from it"

    def test_dockerfile_copies_rhodesli_ml_init(self):
        """Dockerfile must COPY rhodesli_ml/__init__.py — package must be importable."""
        from pathlib import Path
        dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
        assert "rhodesli_ml/__init__.py" in dockerfile, \
            "Dockerfile must COPY rhodesli_ml/__init__.py — package init required for imports"

    def test_rhodesli_ml_graph_modules_importable(self):
        """All graph modules imported by the web app must be importable."""
        from rhodesli_ml.graph.social_graph import build_social_graph, find_all_paths, export_for_d3
        from rhodesli_ml.graph.relationship_graph import build_family_tree, get_relationships_for_person
        # If these imports succeed, the modules are available

    def test_rhodesli_ml_importer_modules_importable(self):
        """All importer modules imported by the web app must be importable."""
        from rhodesli_ml.importers.gedcom_parser import parse_gedcom
        from rhodesli_ml.importers.identity_matcher import match_gedcom_to_identities
        from rhodesli_ml.importers.gedcom_matches import update_match_status
        # If these imports succeed, the modules are available
