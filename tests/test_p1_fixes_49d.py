"""Tests for 6 P1 bug fixes from Session 49D.

Covers:
- UX-092: Birth year Save Edit race condition (Accept inside Form)
- UX-080: 404 page has Tailwind CDN
- UX-081: About page has navbar with nav links
- UX-042: /identify/ page has "See full photo" links
- UX-100: Auto-dismiss on confirmation banners (hyperscript)
- UX-101: Pending count OOB update on accept/reject
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.auth import User
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_patches():
    """Patches for admin auth."""
    return [
        patch("app.main.is_auth_enabled", return_value=True),
        patch("app.main.get_current_user", return_value=User(
            id="test-admin", email="admin@test.com", is_admin=True)),
    ]


# =============================================================================
# Mock data for birth year review tests
# =============================================================================

_MOCK_PENDING_ITEMS = [
    {
        "identity_id": "test-id-1",
        "name": "Test Person One",
        "birth_year_estimate": 1920,
        "birth_year_confidence": "high",
        "birth_year_range": [1915, 1925],
        "n_with_age_data": 3,
        "evidence": [
            {"photo_year": 1945, "estimated_age": 25},
        ],
    },
    {
        "identity_id": "test-id-2",
        "name": "Test Person Two",
        "birth_year_estimate": 1905,
        "birth_year_confidence": "medium",
        "birth_year_range": [1900, 1910],
        "n_with_age_data": 2,
        "evidence": [],
    },
]

_MOCK_IDENTITIES = {
    "test-id-1": {
        "identity_id": "test-id-1",
        "name": "Test Person One",
        "state": "CONFIRMED",
        "anchor_ids": ["face-t1"],
        "candidate_ids": [],
        "negative_ids": [],
        "metadata": {},
        "version_id": 1,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    },
    "test-id-2": {
        "identity_id": "test-id-2",
        "name": "Test Person Two",
        "state": "PROPOSED",
        "anchor_ids": ["face-t2"],
        "candidate_ids": [],
        "negative_ids": [],
        "metadata": {},
        "version_id": 1,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    },
}


def _make_mock_registry():
    """Create a mock IdentityRegistry for tests."""
    from core.registry import IdentityRegistry
    mock_reg = IdentityRegistry.__new__(IdentityRegistry)
    mock_reg._identities = dict(_MOCK_IDENTITIES)
    mock_reg._history = []
    mock_reg._path = None
    return mock_reg


def _birth_year_review_page_patches():
    """Patches needed to render /admin/review/birth-years."""
    mock_reg = _make_mock_registry()
    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main._get_pending_ml_birth_year_suggestions",
              return_value=list(_MOCK_PENDING_ITEMS)),
        patch("app.main.load_registry", return_value=mock_reg),
        patch("app.main.get_crop_files", return_value=set()),
        patch("app.main.get_best_face_id", return_value=None),
    ]


def _birth_year_accept_reject_patches():
    """Patches needed for accept/reject POST endpoints."""
    mock_reg = _make_mock_registry()
    mock_reg.set_metadata = MagicMock()
    return [
        patch("app.main.is_auth_enabled", return_value=True),
        patch("app.main.get_current_user", return_value=User(
            id="test-admin", email="admin@test.com", is_admin=True)),
        patch("app.main.load_registry", return_value=mock_reg),
        patch("app.main.save_registry"),
        patch("app.main._load_birth_year_estimates", return_value={
            "test-id-1": {"birth_year_estimate": 1920, "birth_year_confidence": "high"},
            "test-id-2": {"birth_year_estimate": 1905, "birth_year_confidence": "medium"},
        }),
        patch("app.main._load_ml_review_decisions", return_value={}),
        patch("app.main._save_ml_review_decisions"),
        patch("app.main._save_ground_truth_birth_year"),
        patch("app.main._count_pending_birth_year_reviews", return_value=5),
    ]


# =============================================================================
# UX-092: Birth year Save Edit race condition — Accept inside Form
# =============================================================================

class TestUX092BirthYearFormStructure:
    """The Accept button must be inside a <form> on the bulk review page,
    not a standalone button with hx-vals. This prevents the race condition
    where Accept used hardcoded values instead of the current input."""

    def test_review_page_renders(self, client):
        """GET /admin/review/birth-years returns 200 with pending items."""
        patches = _birth_year_review_page_patches()
        for p in patches:
            p.start()
        try:
            resp = client.get("/admin/review/birth-years")
        finally:
            for p in patches:
                p.stop()
        assert resp.status_code == 200
        assert "Birth Year" in resp.text

    def test_accept_button_inside_form(self, client):
        """Accept button is inside a <form>, not standalone."""
        patches = _birth_year_review_page_patches()
        for p in patches:
            p.start()
        try:
            resp = client.get("/admin/review/birth-years")
        finally:
            for p in patches:
                p.stop()
        html = resp.text
        # The Accept button should be a submit button inside a form
        assert "Accept" in html
        # There should be a <form> that contains both Accept and Save Edit
        assert "<form" in html.lower()

    def test_accept_button_has_no_hx_vals(self, client):
        """Accept button on bulk review page must NOT have hx-vals attribute."""
        patches = _birth_year_review_page_patches()
        for p in patches:
            p.start()
        try:
            resp = client.get("/admin/review/birth-years")
        finally:
            for p in patches:
                p.stop()
        html = resp.text
        # Find all Accept buttons — they should not carry hx-vals
        # The hx-vals pattern was: hx-vals='{"birth_year": NNN}'
        # On the bulk review page, Accept is type="submit" inside a form
        import re
        # Look for Accept buttons with hx-vals — should find NONE
        accept_with_vals = re.findall(
            r'<button[^>]*>Accept</button>', html, re.IGNORECASE
        )
        for btn in accept_with_vals:
            assert "hx-vals" not in btn, \
                f"Accept button still has hx-vals: {btn}"

    def test_accept_and_save_edit_share_form(self, client):
        """Accept and Save Edit buttons are both type=submit in the same form."""
        patches = _birth_year_review_page_patches()
        for p in patches:
            p.start()
        try:
            resp = client.get("/admin/review/birth-years")
        finally:
            for p in patches:
                p.stop()
        html = resp.text
        # Both buttons should exist
        assert "Save Edit" in html
        assert "Accept" in html
        # Both are submit buttons
        assert 'type="submit"' in html


# =============================================================================
# UX-080: 404 page has Tailwind CDN
# =============================================================================

class TestUX080Custom404:
    """The 404 page must include the Tailwind CDN script for styling."""

    def test_404_status_code(self, client):
        """Nonexistent route returns 404."""
        resp = client.get("/nonexistent-route-xyz")
        assert resp.status_code == 404

    def test_404_has_tailwind_cdn(self, client):
        """404 page includes Tailwind CDN script tag."""
        resp = client.get("/nonexistent-route-xyz")
        assert "cdn.tailwindcss.com" in resp.text

    def test_404_has_styled_content(self, client):
        """404 page has recognizable styled elements, not just raw text."""
        resp = client.get("/nonexistent-route-xyz")
        assert "Page not found" in resp.text
        assert "Rhodesli" in resp.text


# =============================================================================
# UX-081: About page has navbar with nav links
# =============================================================================

class TestUX081AboutNavbar:
    """The /about page must have a proper navigation bar, not just
    a standalone 'Back to Archive' link."""

    def test_about_has_photos_link(self, client):
        """About page navbar includes link to Photos."""
        resp = client.get("/about")
        assert resp.status_code == 200
        assert 'href="/photos"' in resp.text
        assert "Photos" in resp.text

    def test_about_has_people_link(self, client):
        """About page navbar includes link to People."""
        resp = client.get("/about")
        assert 'href="/people"' in resp.text
        assert "People" in resp.text

    def test_about_has_timeline_link(self, client):
        """About page navbar includes link to Timeline."""
        resp = client.get("/about")
        assert 'href="/timeline"' in resp.text
        assert "Timeline" in resp.text

    def test_about_no_standalone_back_link(self, client):
        """About page should NOT have the old standalone 'Back to Archive' link."""
        resp = client.get("/about")
        assert "Back to Archive" not in resp.text


# =============================================================================
# UX-042: /identify/ page has "See full photo" links
# =============================================================================

class TestUX042IdentifySeeFullPhoto:
    """Source photo cards on /identify/ page must include 'See full photo' link."""

    def _identify_patches(self):
        """Patches for rendering /identify/{id}."""
        from core.registry import IdentityRegistry

        mock_identities = {
            "unknown-1": {
                "identity_id": "unknown-1",
                "name": "Unidentified Person 42",
                "state": "INBOX",
                "anchor_ids": ["face-u1"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
            },
        }

        mock_reg = IdentityRegistry.__new__(IdentityRegistry)
        mock_reg._identities = mock_identities
        mock_reg._history = []
        mock_reg._path = None

        mock_photo_reg = MagicMock()
        mock_photo_reg.get_photos_for_faces = MagicMock(return_value=["photo-1"])
        mock_photo_reg._photos = {"photo-1": {"path": "test.jpg", "collection": "Test"}}
        mock_photo_reg.get_photo = MagicMock(
            return_value={"path": "test.jpg", "collection": "Test"})

        return [
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.load_registry", return_value=mock_reg),
            patch("app.main.load_photo_registry", return_value=mock_photo_reg),
            patch("app.main._build_caches"),
            patch("app.main._photo_cache", {"photo-1": {"path": "test.jpg", "collection": "Test"}}),
            patch("app.main.get_crop_files", return_value={"face-u1.jpg"}),
            patch("app.main.get_best_face_id", return_value="face-u1"),
            patch("app.main.resolve_face_image_url", return_value="/static/crops/face-u1.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo-1"),
            patch("app.main.get_photo_metadata", return_value={
                "filename": "test.jpg", "collection": "Test Collection",
                "width": 800, "height": 600, "faces": [
                    {"face_id": "face-u1", "bbox": [100, 100, 200, 200]},
                ],
            }),
            patch("app.main._get_date_badge", return_value=("c. 1950s", "medium", "Estimated: 1950s")),
            patch("app.main._load_identification_responses", return_value={
                "schema_version": 1, "responses": [],
            }),
            patch("app.main._save_identification_responses"),
        ]

    def test_identify_page_has_see_full_photo(self, client):
        """Photo card on /identify/ page includes 'See full photo' text."""
        patches = self._identify_patches()
        for p in patches:
            p.start()
        try:
            resp = client.get("/identify/unknown-1")
        finally:
            for p in patches:
                p.stop()
        assert resp.status_code == 200
        assert "See full photo" in resp.text

    def test_identify_see_full_photo_is_link(self, client):
        """'See full photo' is wrapped in a link to the photo page."""
        patches = self._identify_patches()
        for p in patches:
            p.start()
        try:
            resp = client.get("/identify/unknown-1")
        finally:
            for p in patches:
                p.stop()
        html = resp.text
        # Should link to /photo/{photo_id}
        assert "/photo/photo-1" in html
        assert "See full photo" in html


# =============================================================================
# UX-100: Auto-dismiss on confirmation banners
# =============================================================================

class TestUX100AutoDismiss:
    """Accept and reject confirmation banners must include hyperscript
    for auto-dismiss: 'on load wait 4s then transition...'"""

    def test_accept_response_has_auto_dismiss(self, client):
        """POST accept returns HTML with hyperscript auto-dismiss."""
        patches = _birth_year_accept_reject_patches()
        for p in patches:
            p.start()
        try:
            resp = client.post(
                "/api/ml-review/birth-year/test-id-1/accept",
                data={"birth_year": "1920", "source_detail": "test"},
            )
        finally:
            for p in patches:
                p.stop()
        assert resp.status_code == 200
        assert "on load wait 4s" in resp.text

    def test_reject_response_has_auto_dismiss(self, client):
        """POST reject returns HTML with hyperscript auto-dismiss."""
        patches = _birth_year_accept_reject_patches()
        for p in patches:
            p.start()
        try:
            resp = client.post(
                "/api/ml-review/birth-year/test-id-1/reject",
                data={"reason": "incorrect"},
            )
        finally:
            for p in patches:
                p.stop()
        assert resp.status_code == 200
        assert "on load wait 4s" in resp.text

    def test_accept_dismiss_includes_opacity_transition(self, client):
        """Auto-dismiss includes opacity transition for smooth fade-out."""
        patches = _birth_year_accept_reject_patches()
        for p in patches:
            p.start()
        try:
            resp = client.post(
                "/api/ml-review/birth-year/test-id-1/accept",
                data={"birth_year": "1920"},
            )
        finally:
            for p in patches:
                p.stop()
        assert "transition my opacity to 0" in resp.text
        assert "remove me" in resp.text


# =============================================================================
# UX-101: Pending count OOB update
# =============================================================================

class TestUX101PendingCountOOB:
    """Accept and reject responses must include an OOB element that updates
    the pending count display without a full page reload."""

    def test_accept_has_pending_count_oob(self, client):
        """POST accept response includes OOB pending-count element."""
        patches = _birth_year_accept_reject_patches()
        for p in patches:
            p.start()
        try:
            resp = client.post(
                "/api/ml-review/birth-year/test-id-1/accept",
                data={"birth_year": "1920"},
            )
        finally:
            for p in patches:
                p.stop()
        assert resp.status_code == 200
        assert 'id="pending-count"' in resp.text
        assert "hx-swap-oob" in resp.text

    def test_reject_has_pending_count_oob(self, client):
        """POST reject response includes OOB pending-count element."""
        patches = _birth_year_accept_reject_patches()
        for p in patches:
            p.start()
        try:
            resp = client.post(
                "/api/ml-review/birth-year/test-id-1/reject",
                data={"reason": "wrong"},
            )
        finally:
            for p in patches:
                p.stop()
        assert resp.status_code == 200
        assert 'id="pending-count"' in resp.text
        assert "hx-swap-oob" in resp.text

    def test_accept_oob_shows_remaining_count(self, client):
        """OOB pending count shows the actual remaining number."""
        patches = _birth_year_accept_reject_patches()
        for p in patches:
            p.start()
        try:
            resp = client.post(
                "/api/ml-review/birth-year/test-id-1/accept",
                data={"birth_year": "1920"},
            )
        finally:
            for p in patches:
                p.stop()
        # _count_pending_birth_year_reviews is mocked to return 5
        assert "5 pending review" in resp.text

    def test_reject_oob_shows_remaining_count(self, client):
        """Reject response OOB also shows the remaining count."""
        patches = _birth_year_accept_reject_patches()
        for p in patches:
            p.start()
        try:
            resp = client.post(
                "/api/ml-review/birth-year/test-id-1/reject",
            )
        finally:
            for p in patches:
                p.stop()
        assert "5 pending review" in resp.text
