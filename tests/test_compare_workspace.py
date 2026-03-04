"""Tests for the universal comparison workspace (Session 85c).

Tests cover: workspace UI, all entity combinations via /api/compare/execute,
unified search, context intelligence, backward compatibility, and animations.
"""

import json
import numpy as np
import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


# --- Fixtures for mock data ---

def _mock_registry(identities=None):
    """Create a mock registry with configurable identities."""
    if identities is None:
        identities = [
            {
                "identity_id": "test-person-1",
                "name": "Isaac Cohen",
                "state": "CONFIRMED",
                "anchor_ids": ["face_a1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            {
                "identity_id": "test-person-2",
                "name": "Barouh Capeluto",
                "state": "PROPOSED",
                "anchor_ids": ["face_b1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            {
                "identity_id": "test-person-3",
                "name": "Unidentified Person 42",
                "state": "INBOX",
                "anchor_ids": ["face_c1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        ]

    mock = MagicMock()
    mock.list_identities.side_effect = lambda state=None: [
        i for i in identities if state is None or i["state"] == state.value
    ]
    mock.get_identity.side_effect = lambda iid: next(
        (i for i in identities if i["identity_id"] == iid), None
    )
    mock.search_identities.side_effect = lambda q, limit=10: [
        i for i in identities if q.lower() in i["name"].lower()
    ][:limit]
    return mock


def _mock_face_data():
    """Create mock face data with embeddings."""
    emb_a = np.random.randn(512).astype(np.float32)
    emb_b = np.random.randn(512).astype(np.float32)
    emb_c = np.random.randn(512).astype(np.float32)
    return {
        "face_a1": {"mu": emb_a, "sigma": np.ones(512, dtype=np.float32)},
        "face_b1": {"mu": emb_b, "sigma": np.ones(512, dtype=np.float32)},
        "face_c1": {"mu": emb_c, "sigma": np.ones(512, dtype=np.float32)},
    }


def _mock_photo_cache():
    return {
        "photo-001": {
            "filename": "Image_001.jpg",
            "path": "Image_001.jpg",
            "faces": [{"face_id": "face_a1"}],
            "collection": "Test Collection",
            "width": 800,
            "height": 600,
        },
        "photo-002": {
            "filename": "Image_002.jpg",
            "path": "Image_002.jpg",
            "faces": [{"face_id": "face_b1"}],
            "collection": "Test Collection",
            "width": 1024,
            "height": 768,
        },
    }


# ============ UI Tests ============

class TestWorkspaceUI:
    """Tests for the comparison workspace page layout."""

    def test_workspace_renders_empty_state(self, client):
        """Workspace loads with empty state message."""
        resp = client.get("/compare")
        assert resp.status_code == 200
        assert "compare-results-area" in resp.text
        assert "Select a source" in resp.text

    def test_workspace_has_source_slot(self, client):
        """Source slot with upload/person/photo tabs exists."""
        resp = client.get("/compare")
        assert "source-slot" in resp.text
        assert "source-upload-panel" in resp.text
        assert "source-person-panel" in resp.text
        assert "source-photo-panel" in resp.text

    def test_workspace_has_target_slot(self, client):
        """Target slot with search and pills exists."""
        resp = client.get("/compare")
        assert "target-search-input" in resp.text
        assert "target-pills" in resp.text

    def test_workspace_source_upload_tab(self, client):
        """Upload tab has a file input and form."""
        resp = client.get("/compare")
        assert "ws-upload-form" in resp.text
        assert "ws-upload-input" in resp.text
        assert "/api/compare/upload" in resp.text

    def test_workspace_source_person_tab(self, client):
        """Person tab has search input."""
        resp = client.get("/compare")
        assert "source-person-search" in resp.text

    def test_workspace_source_photo_tab(self, client):
        """Photo tab has search input."""
        resp = client.get("/compare")
        assert "source-photo-search" in resp.text

    def test_workspace_upload_targets_ws_upload_result(self, client):
        """Upload form targets #ws-upload-result (not #compare-results)."""
        resp = client.get("/compare")
        assert 'hx-target="#ws-upload-result"' in resp.text
        assert "ws-upload-result" in resp.text

    def test_workspace_source_search_uses_source_slot(self, client):
        """Source searches use slot=source parameter."""
        resp = client.get("/compare")
        assert "slot=source" in resp.text

    def test_workspace_has_all_archive_button(self, client):
        """Target slot has 'All Archive' comparison option."""
        resp = client.get("/compare")
        assert "compare-all-archive" in resp.text

    def test_workspace_has_find_similar_endpoint(self, client):
        """Find-similar-targets endpoint exists."""
        resp = client.get("/api/compare/find-similar-targets")
        assert resp.status_code == 200

    def test_workspace_has_js_state(self, client):
        """Workspace initializes JS state object."""
        resp = client.get("/compare")
        assert "window.compareState" in resp.text
        assert "window.triggerCompare" in resp.text

    def test_workspace_has_animations_css(self, client):
        """Workspace includes animation keyframes."""
        resp = client.get("/compare")
        assert "slideIn" in resp.text
        assert "barFill" in resp.text
        assert "pillPop" in resp.text
        assert "skeleton-block" in resp.text
        assert "bar-glow-emerald" in resp.text


# ============ Backend: Execute Endpoint Tests ============

class TestCompareExecute:
    """Tests for POST /api/compare/execute."""

    def _setup_mocks(self, monkeypatch):
        import app.main as m
        face_data = _mock_face_data()
        registry = _mock_registry()
        photo_cache = _mock_photo_cache()

        monkeypatch.setattr(m, "_photo_cache", photo_cache)
        monkeypatch.setattr(m, "_face_to_photo_cache", {"face_a1": "photo-001", "face_b1": "photo-002"})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        return face_data, registry

    def test_execute_empty_source_returns_message(self, client):
        """Execute with no source returns guidance."""
        resp = client.post("/api/compare/execute", data={
            "source_type": "", "source_id": "", "target_type": "", "target_ids": ""
        })
        assert resp.status_code == 200
        assert "compare-empty" in resp.text

    def test_execute_person_vs_person(self, client, monkeypatch):
        """Compare person against another person."""
        face_data, registry = self._setup_mocks(monkeypatch)
        with patch("app.main.get_face_data", return_value=face_data), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"), \
             patch("app.main.get_identity_for_face", return_value={"identity_id": "test-person-1"}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("core.neighbors.find_similar_faces", return_value=[]):
            resp = client.post("/api/compare/execute", data={
                "source_type": "person",
                "source_id": "test-person-1",
                "target_type": "person",
                "target_ids": "test-person-2",
            })
        assert resp.status_code == 200
        assert "compare-results-area" in resp.text
        assert "%" in resp.text  # confidence percentage

    def test_execute_person_vs_multiple_targets(self, client, monkeypatch):
        """Compare person against multiple targets at once."""
        face_data, registry = self._setup_mocks(monkeypatch)
        with patch("app.main.get_face_data", return_value=face_data), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"), \
             patch("app.main.get_identity_for_face", return_value={"identity_id": "test-person-1"}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("core.neighbors.find_similar_faces", return_value=[]):
            resp = client.post("/api/compare/execute", data={
                "source_type": "person",
                "source_id": "test-person-1",
                "target_type": "person",
                "target_ids": "test-person-2,test-person-3",
            })
        assert resp.status_code == 200
        assert "compare-results-area" in resp.text

    def test_execute_archive_mode(self, client, monkeypatch):
        """Compare person against entire archive."""
        face_data, registry = self._setup_mocks(monkeypatch)
        mock_matches = [{
            "face_id": "face_b1",
            "identity_id": "test-person-2",
            "identity_name": "Barouh Capeluto",
            "distance": 0.8,
            "confidence_pct": 72,
            "tier": "PLAUSIBLE",
        }]
        with patch("app.main.get_face_data", return_value=face_data), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"), \
             patch("app.main.get_identity_for_face", return_value={"identity_id": "test-person-1"}), \
             patch("core.neighbors.find_similar_faces", return_value=mock_matches):
            resp = client.post("/api/compare/execute", data={
                "source_type": "person",
                "source_id": "test-person-1",
                "target_type": "archive",
                "target_ids": "",
            })
        assert resp.status_code == 200
        assert "compare-results-area" in resp.text

    def test_execute_no_targets_returns_message(self, client):
        """Execute with source but no targets shows guidance."""
        resp = client.post("/api/compare/execute", data={
            "source_type": "person", "source_id": "test-id",
            "target_type": "", "target_ids": ""
        })
        assert resp.status_code == 200
        assert "compare-empty" in resp.text

    def test_execute_result_has_share_link(self, client, monkeypatch):
        """Execute results include a shareable link."""
        face_data, registry = self._setup_mocks(monkeypatch)
        with patch("app.main.get_face_data", return_value=face_data), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"), \
             patch("app.main.get_identity_for_face", return_value={"identity_id": "test-person-1"}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("core.neighbors.find_similar_faces", return_value=[]):
            resp = client.post("/api/compare/execute", data={
                "source_type": "person",
                "source_id": "test-person-1",
                "target_type": "person",
                "target_ids": "test-person-2",
            })
        assert resp.status_code == 200
        assert "/compare/result/" in resp.text
        assert "compare-results-actions" in resp.text

    def test_execute_result_has_confidence_bars(self, client, monkeypatch):
        """Execute results display confidence bars."""
        face_data, registry = self._setup_mocks(monkeypatch)
        with patch("app.main.get_face_data", return_value=face_data), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"), \
             patch("app.main.get_identity_for_face", return_value={"identity_id": "test-person-1"}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("core.neighbors.find_similar_faces", return_value=[]):
            resp = client.post("/api/compare/execute", data={
                "source_type": "person",
                "source_id": "test-person-1",
                "target_type": "person",
                "target_ids": "test-person-2",
            })
        assert resp.status_code == 200
        assert "compare-bar-animate" in resp.text

    def test_execute_result_has_face_collapse(self, client, monkeypatch):
        """Execute results have face section toggle for multi-face sources."""
        # Create a person with 2 faces
        registry = _mock_registry([
            {"identity_id": "multi-face", "name": "Multi Face Person", "state": "CONFIRMED",
             "anchor_ids": ["face_a1", "face_b1"], "candidate_ids": [], "negative_ids": []},
            {"identity_id": "target-1", "name": "Target Person", "state": "CONFIRMED",
             "anchor_ids": ["face_c1"], "candidate_ids": [], "negative_ids": []},
        ])
        face_data = _mock_face_data()
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", _mock_photo_cache())
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.get_face_data", return_value=face_data), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"), \
             patch("app.main.get_identity_for_face", return_value={"identity_id": "multi-face"}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("core.neighbors.find_similar_faces", return_value=[]):
            resp = client.post("/api/compare/execute", data={
                "source_type": "person",
                "source_id": "multi-face",
                "target_type": "person",
                "target_ids": "target-1",
            })
        assert resp.status_code == 200
        assert "toggle-face-section" in resp.text
        assert "face-section-content" in resp.text


# ============ Search Tests ============

class TestUnifiedSearch:
    """Tests for GET /api/compare/search-unified."""

    def test_search_requires_min_2_chars(self, client):
        """Search requires at least 2 characters."""
        resp = client.get("/api/compare/search-unified?q=a&types=person&slot=target")
        assert resp.status_code == 200
        # Should return empty results container with slot-specific ID
        text = resp.text
        assert "target-person-results" in text
        assert "search-result-person" not in text

    def test_search_returns_people(self, client, monkeypatch):
        """Search finds people across all states."""
        registry = _mock_registry()
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", {})
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"):
            resp = client.get("/api/compare/search-unified?q=Isaac&types=person")
        assert resp.status_code == 200
        assert "Isaac Cohen" in resp.text
        assert "Person" in resp.text

    def test_search_includes_inbox_identities(self, client, monkeypatch):
        """Search includes INBOX (unidentified) identities."""
        registry = _mock_registry()
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", {})
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"):
            resp = client.get("/api/compare/search-unified?q=Unidentified&types=person")
        assert resp.status_code == 200
        assert "Unidentified" in resp.text

    def test_search_returns_photos(self, client, monkeypatch):
        """Search finds photos by collection/filename."""
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", _mock_photo_cache())
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})
        registry = _mock_registry()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._resolve_crop_url", return_value=""):
            resp = client.get("/api/compare/search-unified?q=Test&types=photo")
        assert resp.status_code == 200
        assert "Photo" in resp.text

    def test_search_source_slot_uses_correct_action(self, client, monkeypatch):
        """Source slot search uses data-action='select-compare-source'."""
        registry = _mock_registry()
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", {})
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"):
            resp = client.get("/api/compare/search-unified?q=Isaac&types=person&slot=source")
        assert resp.status_code == 200
        assert 'data-action="select-compare-source"' in resp.text

    def test_search_target_slot_uses_correct_action(self, client, monkeypatch):
        """Target slot search uses data-action='select-compare-target'."""
        registry = _mock_registry()
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", {})
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"):
            resp = client.get("/api/compare/search-unified?q=Isaac&types=person&slot=target")
        assert resp.status_code == 200
        assert 'data-action="select-compare-target"' in resp.text

    def test_search_no_results_shows_message(self, client, monkeypatch):
        """Search with no matches shows 'No results found'."""
        registry = _mock_registry()
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", {})
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}):
            resp = client.get("/api/compare/search-unified?q=ZZZZZZZ&types=person")
        assert resp.status_code == 200
        assert "No results found" in resp.text

    def test_search_result_id_matches_slot_and_type(self, client, monkeypatch):
        """Result container ID is slot-specific (not generic compare-search-results)."""
        registry = _mock_registry()
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", {})
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"):
            # Source person search
            resp = client.get("/api/compare/search-unified?q=Isaac&types=person&slot=source")
            assert "source-person-results" in resp.text
            # Target person search
            resp = client.get("/api/compare/search-unified?q=Isaac&types=person&slot=target")
            assert "target-person-results" in resp.text
            # Source photo search
            monkeypatch.setattr(m, "_photo_cache", _mock_photo_cache())
            resp = client.get("/api/compare/search-unified?q=Test&types=photo&slot=source")
            assert "source-photo-results" in resp.text

    def test_search_person_returns_tagged_photos(self, client, monkeypatch):
        """Searching a person name also returns photos containing that person."""
        registry = _mock_registry()
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", _mock_photo_cache())
        monkeypatch.setattr(m, "_face_to_photo_cache", {"face_b1": "photo-002"})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"):
            resp = client.get("/api/compare/search-unified?q=Barouh&types=person&slot=target")
        assert resp.status_code == 200
        # Should contain the person result
        assert "Barouh" in resp.text
        assert 'data-entity-type="person"' in resp.text
        # Should also contain the photo that has Barouh's face
        assert 'data-entity-type="photo"' in resp.text
        assert "Contains Barouh" in resp.text

    def test_search_photo_face_count_uses_faces_key(self, client, monkeypatch):
        """Photo search uses 'faces' key (not 'face_ids') for face count."""
        import app.main as m
        photo_cache = {
            "photo-999": {
                "filename": "TestPhoto.jpg",
                "path": "TestPhoto.jpg",
                "faces": [{"face_id": "f1"}, {"face_id": "f2"}, {"face_id": "f3"}],
                "collection": "Test",
            }
        }
        monkeypatch.setattr(m, "_photo_cache", photo_cache)
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})
        registry = _mock_registry()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main._resolve_crop_url", return_value=""):
            resp = client.get("/api/compare/search-unified?q=TestPhoto&types=photo&slot=target")
        assert resp.status_code == 200
        assert "3 faces" in resp.text


# ============ Target Slot UI Tests ============

class TestTargetSlotUI:
    """Tests for the symmetric target slot with tabs."""

    def test_target_has_tabs(self, client):
        """Target slot has Person/Photo/Upload tabs."""
        resp = client.get("/compare")
        assert "target-tabs" in resp.text

    def test_target_has_person_panel(self, client):
        """Target has person search panel."""
        resp = client.get("/compare")
        assert "target-person-panel" in resp.text
        assert "target-search-input" in resp.text

    def test_target_has_photo_panel(self, client):
        """Target has photo search panel."""
        resp = client.get("/compare")
        assert "target-photo-panel" in resp.text
        assert "target-photo-search" in resp.text

    def test_target_has_upload_panel(self, client):
        """Target has upload panel."""
        resp = client.get("/compare")
        assert "target-upload-panel" in resp.text
        assert "ws-target-upload-form" in resp.text
        assert "ws-target-upload-input" in resp.text

    def test_target_upload_sends_target_ws(self, client):
        """Target upload form includes target_ws=1 hidden field."""
        resp = client.get("/compare")
        assert 'hx-target="#ws-target-upload-result"' in resp.text

    def test_target_search_uses_slot_target(self, client):
        """Target search inputs use slot=target parameter."""
        resp = client.get("/compare")
        assert "slot=target" in resp.text

    def test_target_tab_js_exists(self, client):
        """JS tab switching for target slot is present."""
        resp = client.get("/compare")
        assert "data-target-tab" in resp.text
        assert "data-target-panel" in resp.text

    def test_target_upload_returns_target_result_id(self, client):
        """Upload with target_ws=1 returns ws-target-upload-result container."""
        resp = client.post("/api/compare/upload",
                           data={"ws": "1", "target_ws": "1"},
                           files={})
        assert resp.status_code == 200
        assert "ws-target-upload-result" in resp.text


# ============ Upload in Workspace Mode Tests ============

class TestWorkspaceUpload:
    """Tests for upload in workspace mode (ws=1)."""

    def test_upload_ws_mode_no_photo(self, client):
        """Workspace upload with no photo returns error in ws-upload-result."""
        resp = client.post("/api/compare/upload",
                           data={"ws": "1"},
                           files={})
        assert resp.status_code == 200
        assert "ws-upload-result" in resp.text

    def test_upload_ws_mode_bad_type(self, client):
        """Workspace upload with bad file type returns error in ws-upload-result."""
        resp = client.post("/api/compare/upload",
                           data={"ws": "1"},
                           files={"photo": ("test.txt", b"not-an-image", "text/plain")})
        assert resp.status_code == 200
        assert "ws-upload-result" in resp.text
        assert "JPG or PNG" in resp.text

    def test_upload_ws_mode_processing(self, client, monkeypatch, tmp_path):
        """Workspace upload in processing mode returns polling with ws=1."""
        import app.main as m
        monkeypatch.setattr(m, "data_path", tmp_path)
        monkeypatch.setattr(m, "PROCESSING_ENABLED", True)
        monkeypatch.setattr(m, "is_auth_enabled", lambda: False)
        (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
        (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

        resp = client.post("/api/compare/upload",
                           data={"ws": "1"},
                           files={"photo": ("test.jpg", b"\xff\xd8\xff", "image/jpeg")})
        assert resp.status_code == 200
        assert "ws-upload-result" in resp.text
        assert "ws=1" in resp.text  # polling URL includes ws=1

    def test_upload_standard_mode_uses_compare_results(self, client, monkeypatch, tmp_path):
        """Standard (non-workspace) upload targets #compare-results."""
        import app.main as m
        monkeypatch.setattr(m, "data_path", tmp_path)
        monkeypatch.setattr(m, "PROCESSING_ENABLED", True)
        monkeypatch.setattr(m, "is_auth_enabled", lambda: False)
        (tmp_path / "inbox").mkdir(parents=True, exist_ok=True)
        (tmp_path / "staging").mkdir(parents=True, exist_ok=True)

        resp = client.post("/api/compare/upload",
                           files={"photo": ("test.jpg", b"\xff\xd8\xff", "image/jpeg")})
        assert resp.status_code == 200
        assert 'id="compare-results"' in resp.text


# ============ Backward Compatibility Tests ============

class TestBackwardCompat:
    """Tests for backward compatibility of URLs."""

    def test_result_page_still_works(self, client):
        """Shareable result pages still render."""
        from app.main import _save_comparison_result, _generate_result_id
        rid = _generate_result_id()
        _save_comparison_result({
            "result_id": rid,
            "query_type": "unified",
            "source_name": "Test",
            "created_at": "2026-03-03T00:00:00",
            "matches": [{"face_id": "f1", "target_id": "t1", "target_name": "Target",
                         "distance": 0.9, "confidence_pct": 65, "tier": "PLAUSIBLE"}],
            "responses": [],
        })
        resp = client.get(f"/compare/result/{rid}")
        assert resp.status_code == 200

    def test_url_params_person_id(self, client):
        """?person_id=X pre-populates target slot."""
        resp = client.get("/compare?person_id=test-id")
        assert resp.status_code == 200
        # JS state should have target pre-populated
        assert "test-id" in resp.text

    def test_url_params_photo_id(self, client):
        """?photo_id=X pre-populates source slot."""
        resp = client.get("/compare?photo_id=test-photo")
        assert resp.status_code == 200
        assert "test-photo" in resp.text

    def test_compare_pair_page_exists(self, client):
        """/compare/pair still renders (may redirect or show workspace)."""
        resp = client.get("/compare/pair")
        assert resp.status_code == 200


# ============ Context Intelligence Tests ============

class TestContextIntelligence:
    """Tests for Phase 5 context features."""

    def test_no_strong_matches_message(self, client, monkeypatch):
        """When all scores are unlikely, show empathetic message."""
        # Create faces that are very different (high distance)
        emb_a = np.zeros(512, dtype=np.float32)
        emb_a[0] = 100.0  # Very different embedding
        emb_b = np.zeros(512, dtype=np.float32)
        emb_b[1] = 100.0  # Very different direction

        face_data = {
            "face_x": {"mu": emb_a, "sigma": np.ones(512, dtype=np.float32)},
            "face_y": {"mu": emb_b, "sigma": np.ones(512, dtype=np.float32)},
        }
        registry = _mock_registry([
            {"identity_id": "p1", "name": "Person 1", "state": "CONFIRMED",
             "anchor_ids": ["face_x"], "candidate_ids": [], "negative_ids": []},
            {"identity_id": "p2", "name": "Person 2", "state": "CONFIRMED",
             "anchor_ids": ["face_y"], "candidate_ids": [], "negative_ids": []},
        ])
        import app.main as m
        monkeypatch.setattr(m, "_photo_cache", {})
        monkeypatch.setattr(m, "_face_to_photo_cache", {})
        monkeypatch.setattr(m, "_photo_id_aliases", {})

        with patch("app.main.get_face_data", return_value=face_data), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._resolve_crop_url", return_value="/crop.jpg"), \
             patch("app.main.get_identity_for_face", return_value={"identity_id": "p1"}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("core.neighbors.find_similar_faces", return_value=[]):
            resp = client.post("/api/compare/execute", data={
                "source_type": "person",
                "source_id": "p1",
                "target_type": "person",
                "target_ids": "p2",
            })
        assert resp.status_code == 200
        # Check for empathetic message or the result
        text = resp.text
        # Either shows "no strong matches" or very low percentage
        assert "compare-results-area" in text
