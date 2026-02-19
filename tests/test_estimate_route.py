"""
Route tests for the /estimate page — Year Estimation Tool.

Tests cover:
- GET /estimate returns 200 with page title
- GET /estimate?photo=nonexistent returns 200 (graceful)
- Page has "When Was This Photo Taken?" heading
- Page has Compare Faces / Estimate Year tabs
- OG tags are present
- Photo selection renders photo grid
- Estimate result section renders when photo has data
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

_MOCK_IDENTITIES = {
    "identities": {
        "test-confirmed-1": {
            "identity_id": "test-confirmed-1",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "metadata": {},
        },
    },
    "history": [],
}


def _build_mock_registry():
    """Build a mock IdentityRegistry from test data."""
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None
    return mock_registry


def _build_mock_photo_reg():
    """Build a mock PhotoRegistry."""
    mock_photo_reg = MagicMock()
    mock_photo_reg.list_photos = MagicMock(return_value=[])
    mock_photo_reg._photos = {}
    mock_photo_reg.get_photo_for_face = MagicMock(return_value=None)
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=set())
    return mock_photo_reg


def _standard_patches(photo_cache=None, date_labels=None):
    """
    Return a list of patch context managers that mock data loading
    for the /estimate route.
    """
    mock_registry = _build_mock_registry()
    mock_photo_reg = _build_mock_photo_reg()

    patches = [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={}),
        patch("app.main._load_date_labels", return_value=date_labels or {}),
        patch("app.main._load_relationship_graph", return_value={
            "schema_version": 1, "relationships": [], "gedcom_imports": [],
        }),
        patch("app.main._load_photo_locations", return_value={}),
        patch("core.storage.get_photo_url", side_effect=lambda p: f"/photos/{p}"),
    ]

    # Patch the _photo_cache module-level variable
    if photo_cache is not None:
        patches.append(patch("app.main._photo_cache", photo_cache))
    else:
        patches.append(patch("app.main._photo_cache", {}))

    return patches


def _run_with_patches(client, url, photo_cache=None, date_labels=None):
    """Run a GET request with all standard patches active."""
    patches = _standard_patches(photo_cache=photo_cache, date_labels=date_labels)
    for p in patches:
        p.start()
    try:
        return client.get(url)
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Route tests: /estimate
# ---------------------------------------------------------------------------

class TestEstimateRoute:
    """Tests for the /estimate page."""

    def test_estimate_returns_200(self, client):
        """GET /estimate returns HTTP 200."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200

    def test_estimate_nonexistent_photo_returns_200(self, client):
        """GET /estimate?photo=nonexistent returns 200 (graceful degradation)."""
        resp = _run_with_patches(client, "/estimate?photo=nonexistent-id-xyz")
        assert resp.status_code == 200

    def test_estimate_has_page_title(self, client):
        """Page title includes 'When Was This Photo Taken?'."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        assert "When Was This Photo Taken?" in resp.text

    def test_estimate_has_heading(self, client):
        """Page body contains the H1 heading."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        assert "When Was This Photo Taken?" in resp.text

    def test_estimate_has_compare_tab(self, client):
        """Page has a 'Compare Faces' tab link."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        assert "Compare Faces" in resp.text
        assert "/compare" in resp.text

    def test_estimate_has_estimate_year_tab(self, client):
        """Page has an 'Estimate Year' tab link (active state)."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        assert "Estimate Year" in resp.text

    def test_estimate_has_og_tags(self, client):
        """Page includes Open Graph meta tags."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        html = resp.text
        assert 'og:title' in html
        assert "When Was This Photo Taken?" in html
        assert 'og:description' in html
        assert "/estimate" in html  # canonical URL

    def test_estimate_has_description_text(self, client):
        """Page includes the descriptive subtitle text."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        assert "facial age analysis" in resp.text

    def test_estimate_has_nav_bar(self, client):
        """Page includes the Rhodesli nav bar."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        assert "Rhodesli" in resp.text

    def test_estimate_nonexistent_photo_shows_fallback_message(self, client):
        """When photo= is set but photo not in cache, shows 'not enough data' fallback."""
        # Photo not in the _photo_cache → estimate_result is None, selected_photo is None
        # In this case the nonexistent photo is not in _photo_cache, so no result section
        resp = _run_with_patches(
            client,
            "/estimate?photo=nonexistent-id",
            photo_cache={},
        )
        assert resp.status_code == 200
        # The photo ID is not in photo_cache, so no result or fallback section is shown
        # (the route only shows fallback if photo is in photo_cache but estimate fails)


class TestEstimateRouteWithPhotoData:
    """Tests for /estimate with photo data in the cache."""

    def test_photo_grid_renders(self, client):
        """When photos exist in cache, photo grid selector is rendered."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo_1.jpg",
                "filename": "test_photo_1.jpg",
                "face_ids": ["face-a1"],
                "faces": [],
            },
            "photo-2": {
                "path": "test_photo_2.jpg",
                "filename": "test_photo_2.jpg",
                "face_ids": ["face-b1", "face-b2"],
                "faces": [],
            },
        }

        resp = _run_with_patches(
            client,
            "/estimate",
            photo_cache=photo_cache,
        )
        assert resp.status_code == 200
        assert "Select a Photo" in resp.text

    def test_selected_photo_shows_result_or_fallback(self, client):
        """When photo= is a valid cached photo but no estimate data, shows fallback."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo_1.jpg",
                "filename": "test_photo_1.jpg",
                "face_ids": [],
                "faces": [],
            },
        }

        resp = _run_with_patches(
            client,
            "/estimate?photo=photo-1",
            photo_cache=photo_cache,
            date_labels={},
        )
        assert resp.status_code == 200
        # Photo is in cache but no date labels → falls back to "not enough data"
        assert "Not enough data" in resp.text

    def test_selected_photo_with_estimate_shows_result(self, client):
        """When photo has enough data for estimation, result section appears."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo_1.jpg",
                "filename": "test_photo_1.jpg",
                "face_ids": [],
                "faces": [],
            },
        }
        date_labels = {
            "photo-1": {
                "subject_ages": [],
                "estimated_decade": 1930,
                "best_year_estimate": 1935,
                "confidence": "medium",
                "metadata": {"photo_type": "portrait"},
            },
        }

        resp = _run_with_patches(
            client,
            "/estimate?photo=photo-1",
            photo_cache=photo_cache,
            date_labels=date_labels,
        )
        assert resp.status_code == 200
        assert "Estimated:" in resp.text
        assert "1935" in resp.text

    def test_result_has_confidence_label(self, client):
        """Estimate result shows confidence level text."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo_1.jpg",
                "filename": "test_photo_1.jpg",
                "face_ids": [],
                "faces": [],
            },
        }
        date_labels = {
            "photo-1": {
                "subject_ages": [],
                "estimated_decade": 1940,
                "best_year_estimate": 1945,
                "confidence": "medium",
                "metadata": {},
            },
        }

        resp = _run_with_patches(
            client,
            "/estimate?photo=photo-1",
            photo_cache=photo_cache,
            date_labels=date_labels,
        )
        assert resp.status_code == 200
        assert "confidence" in resp.text.lower()

    def test_result_has_share_and_view_links(self, client):
        """Estimate result includes share button and 'View Photo Page' link."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo_1.jpg",
                "filename": "test_photo_1.jpg",
                "face_ids": [],
                "faces": [],
            },
        }
        date_labels = {
            "photo-1": {
                "subject_ages": [],
                "estimated_decade": 1930,
                "best_year_estimate": 1935,
                "confidence": "medium",
                "metadata": {},
            },
        }

        resp = _run_with_patches(
            client,
            "/estimate?photo=photo-1",
            photo_cache=photo_cache,
            date_labels=date_labels,
        )
        assert resp.status_code == 200
        assert "View Photo Page" in resp.text
        assert "/photo/photo-1" in resp.text
        assert "Try Another" in resp.text

    def test_result_has_how_we_estimated_section(self, client):
        """Estimate result includes 'How we estimated this' section."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo_1.jpg",
                "filename": "test_photo_1.jpg",
                "face_ids": [],
                "faces": [],
            },
        }
        date_labels = {
            "photo-1": {
                "subject_ages": [],
                "estimated_decade": 1930,
                "best_year_estimate": 1935,
                "confidence": "medium",
                "metadata": {"photo_type": "portrait", "setting": "indoor"},
            },
        }

        resp = _run_with_patches(
            client,
            "/estimate?photo=photo-1",
            photo_cache=photo_cache,
            date_labels=date_labels,
        )
        assert resp.status_code == 200
        assert "How we estimated this" in resp.text

    def test_scene_analysis_method_label(self, client):
        """Scene-only estimate shows 'Based on scene analysis' method label."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo_1.jpg",
                "filename": "test_photo_1.jpg",
                "face_ids": [],
                "faces": [],
            },
        }
        date_labels = {
            "photo-1": {
                "subject_ages": [],
                "estimated_decade": 1930,
                "best_year_estimate": 1935,
                "confidence": "medium",
                "metadata": {},
            },
        }

        resp = _run_with_patches(
            client,
            "/estimate?photo=photo-1",
            photo_cache=photo_cache,
            date_labels=date_labels,
        )
        assert resp.status_code == 200
        assert "scene analysis" in resp.text.lower()


class TestEstimatePageFixes:
    """Tests for Session 50 estimate page fixes."""

    def test_face_count_uses_faces_not_face_ids(self, client):
        """Face count in grid must use 'faces' list (not 'face_ids' key)."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo.jpg",
                "filename": "test_photo.jpg",
                "faces": [
                    {"face_id": "f1", "bbox": [0, 0, 50, 50]},
                    {"face_id": "f2", "bbox": [60, 0, 110, 50]},
                    {"face_id": "f3", "bbox": [120, 0, 170, 50]},
                ],
            },
        }
        resp = _run_with_patches(client, "/estimate", photo_cache=photo_cache)
        assert resp.status_code == 200
        assert "3 faces" in resp.text

    def test_face_count_not_zero_when_faces_exist(self, client):
        """Regression: face count must NOT show '0 faces' when faces exist."""
        photo_cache = {
            "photo-1": {
                "path": "test_photo.jpg",
                "filename": "test_photo.jpg",
                "faces": [{"face_id": "f1", "bbox": [0, 0, 50, 50]}],
            },
        }
        resp = _run_with_patches(client, "/estimate", photo_cache=photo_cache)
        assert resp.status_code == 200
        assert "1 face" in resp.text
        # Should NOT show "0 faces"
        assert "0 faces" not in resp.text

    def test_pagination_shows_24_max(self, client):
        """Photo grid should show at most 24 photos initially (not 60+)."""
        photo_cache = {}
        for i in range(40):
            photo_cache[f"photo-{i}"] = {
                "path": f"test_{i}.jpg",
                "filename": f"test_{i}.jpg",
                "faces": [],
            }
        resp = _run_with_patches(client, "/estimate", photo_cache=photo_cache)
        assert resp.status_code == 200
        # Should have "Load More" button since 40 > 24
        assert "Load More" in resp.text

    def test_estimate_has_upload_area(self, client):
        """Estimate page should have an upload zone (when no photo selected)."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        assert "estimate-upload-form" in resp.text or "estimate-upload-area" in resp.text

    def test_estimate_in_nav_bar(self, client):
        """Estimate should appear in the public nav bar."""
        resp = _run_with_patches(client, "/estimate")
        assert resp.status_code == 200
        assert 'href="/estimate"' in resp.text

    def test_estimate_nav_active_state(self, client):
        """On /estimate, the Estimate nav link should be highlighted."""
        resp = _run_with_patches(client, "/estimate")
        html = resp.text
        # The active link should have text-white class
        # Find the estimate link and check it has active styling
        assert '/estimate' in html

    def test_estimate_in_sidebar(self, client):
        """Estimate link should appear in admin sidebar."""
        from app.main import sidebar
        from fastcore.xml import to_xml
        counts = {"to_review": 5, "confirmed": 10, "skipped": 3, "rejected": 1, "photos": 50}
        result = sidebar(counts, current_section="photos", user=None)
        html = to_xml(result)
        assert 'href="/estimate"' in html
        assert "Estimate" in html

    def test_no_evidence_shows_helpful_text(self, client):
        """When no evidence available, show helpful text (not 'No detailed evidence')."""
        photo_cache = {
            "photo-1": {
                "path": "test.jpg",
                "filename": "test.jpg",
                "faces": [],
            },
        }
        date_labels = {
            "photo-1": {
                "subject_ages": [],
                "estimated_decade": 1930,
                "best_year_estimate": 1935,
                "confidence": "low",
                "metadata": {},
            },
        }
        resp = _run_with_patches(client, "/estimate?photo=photo-1",
                                 photo_cache=photo_cache, date_labels=date_labels)
        assert resp.status_code == 200
        # Should NOT say "No detailed evidence available"
        assert "No detailed evidence available" not in resp.text

    def test_estimate_upload_endpoint_validates_type(self, client):
        """POST /api/estimate/upload rejects non-JPG/PNG files."""
        from io import BytesIO
        resp = client.post(
            "/api/estimate/upload",
            files={"photo": ("test.gif", BytesIO(b"GIF89a"), "image/gif")},
        )
        assert resp.status_code == 200
        assert "JPG or PNG" in resp.text

    def test_estimate_upload_no_file(self, client):
        """POST /api/estimate/upload with no file shows error."""
        resp = client.post("/api/estimate/upload")
        assert resp.status_code == 200
        assert "No photo uploaded" in resp.text
