"""Tests for the ML Gatekeeper Pattern (AD-097).

Tests cover:
- _get_birth_year with include_unreviewed parameter
- ML suggestion card rendering for admin vs public
- Accept/reject/edit birth year review endpoints
- Bulk review page loading and actions
- Ground truth file creation on acceptance
- ML review decisions persistence
- Version display reads from CHANGELOG
- Public person page hides unreviewed ML estimates
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from starlette.testclient import TestClient


# ============================================================
# Test: _get_birth_year with include_unreviewed parameter
# ============================================================

class TestGetBirthYearGatekeeper:
    """Tests for the Gatekeeper-aware _get_birth_year."""

    def test_include_unreviewed_true_shows_ml(self):
        """With include_unreviewed=True (default), ML estimates are returned."""
        from app.main import _get_birth_year

        identity = {"metadata": {}}
        with patch("app.main._load_birth_year_estimates", return_value={
            "test-id": {"birth_year_estimate": 1907, "birth_year_confidence": "medium"}
        }), patch("app.main._load_ml_review_decisions", return_value={}):
            year, source, conf = _get_birth_year("test-id", identity, include_unreviewed=True)
        assert year == 1907
        assert source == "ml_inferred"

    def test_include_unreviewed_false_hides_ml(self):
        """With include_unreviewed=False, ML estimates are hidden."""
        from app.main import _get_birth_year

        identity = {"metadata": {}}
        with patch("app.main._load_birth_year_estimates", return_value={
            "test-id": {"birth_year_estimate": 1907, "birth_year_confidence": "medium"}
        }):
            year, source, conf = _get_birth_year("test-id", identity, include_unreviewed=False)
        assert year is None
        assert source is None

    def test_confirmed_shown_regardless_of_unreviewed_flag(self):
        """Confirmed metadata birth year shown whether include_unreviewed is True or False."""
        from app.main import _get_birth_year

        identity = {"birth_year": 1902}
        for flag in [True, False]:
            year, source, conf = _get_birth_year("test-id", identity, include_unreviewed=flag)
            assert year == 1902
            assert source == "confirmed"

    def test_rejected_ml_not_shown_even_with_unreviewed_true(self):
        """Rejected ML estimates are hidden even when include_unreviewed=True."""
        from app.main import _get_birth_year

        identity = {"metadata": {}}
        with patch("app.main._load_birth_year_estimates", return_value={
            "test-id": {"birth_year_estimate": 1907, "birth_year_confidence": "medium"}
        }), patch("app.main._load_ml_review_decisions", return_value={
            "test-id": {"action": "rejected"}
        }):
            year, source, conf = _get_birth_year("test-id", identity, include_unreviewed=True)
        assert year is None

    def test_default_is_include_unreviewed(self):
        """Default behavior (no flag) includes unreviewed ML estimates."""
        from app.main import _get_birth_year

        identity = {"metadata": {}}
        with patch("app.main._load_birth_year_estimates", return_value={
            "test-id": {"birth_year_estimate": 1907, "birth_year_confidence": "medium"}
        }), patch("app.main._load_ml_review_decisions", return_value={}):
            year, source, conf = _get_birth_year("test-id", identity)
        assert year == 1907
        assert source == "ml_inferred"


# ============================================================
# Test: ML Suggestion Card
# ============================================================

class TestMLSuggestionCard:
    """Tests for ML suggestion card on person page."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def confirmed_identity_no_birth_year(self):
        """A CONFIRMED identity WITHOUT a birth year."""
        return {
            "identity_id": "test-person-id",
            "name": "Big Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face1"],
            "candidate_ids": [],
            "negative_ids": [],
            "metadata": {},
            "version_id": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }

    def test_suggestion_card_shown_to_admin(self, client, confirmed_identity_no_birth_year):
        """Admin sees ML suggestion card when identity has no confirmed birth year."""
        from fastcore.xml import to_xml
        from app.main import public_person_page

        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.load_photo_registry") as mock_photo_reg, \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("app.main.get_best_face_id", return_value=None), \
             patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main.get_identity_for_face", return_value=None), \
             patch("app.main.get_photo_id_for_face", return_value=None), \
             patch("app.main._load_birth_year_estimates", return_value={
                 "test-person-id": {
                     "birth_year_estimate": 1907,
                     "birth_year_confidence": "medium",
                     "birth_year_range": [1901, 1914],
                     "n_with_age_data": 12,
                 }
             }), \
             patch("app.main._load_ml_review_decisions", return_value={}), \
             patch("app.main._load_annotations", return_value={"annotations": {}}):
            mock_reg.return_value.get_identity.return_value = confirmed_identity_no_birth_year
            mock_photo_reg.return_value.get_photos_for_faces.return_value = []

            result = public_person_page("test-person-id", is_admin=True)
            html = to_xml(result)
            assert "ML Estimate" in html
            assert "1907" in html
            assert "Accept" in html
            assert "Reject" in html

    def test_suggestion_card_hidden_from_public(self, client, confirmed_identity_no_birth_year):
        """Public users do NOT see ML suggestion card."""
        from fastcore.xml import to_xml
        from app.main import public_person_page

        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.load_photo_registry") as mock_photo_reg, \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("app.main.get_best_face_id", return_value=None), \
             patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main.get_identity_for_face", return_value=None), \
             patch("app.main.get_photo_id_for_face", return_value=None), \
             patch("app.main._load_birth_year_estimates", return_value={
                 "test-person-id": {
                     "birth_year_estimate": 1907,
                     "birth_year_confidence": "medium",
                     "birth_year_range": [1901, 1914],
                     "n_with_age_data": 12,
                 }
             }), \
             patch("app.main._load_ml_review_decisions", return_value={}), \
             patch("app.main._load_annotations", return_value={"annotations": {}}):
            mock_reg.return_value.get_identity.return_value = confirmed_identity_no_birth_year
            mock_photo_reg.return_value.get_photos_for_faces.return_value = []

            result = public_person_page("test-person-id", is_admin=False)
            html = to_xml(result)
            assert "ML Estimate" not in html
            assert "Accept" not in html

    def test_no_suggestion_when_birth_year_confirmed(self, client):
        """No ML suggestion card when identity already has confirmed birth year."""
        from fastcore.xml import to_xml
        from app.main import public_person_page

        identity = {
            "identity_id": "test-id",
            "name": "Big Leon",
            "state": "CONFIRMED",
            "anchor_ids": ["face1"],
            "candidate_ids": [],
            "negative_ids": [],
            "birth_year": 1902,
            "metadata": {},
            "version_id": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }

        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.load_photo_registry") as mock_photo_reg, \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.get_photo_metadata", return_value=None), \
             patch("app.main.get_best_face_id", return_value=None), \
             patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main.get_identity_for_face", return_value=None), \
             patch("app.main.get_photo_id_for_face", return_value=None), \
             patch("app.main._load_birth_year_estimates", return_value={}), \
             patch("app.main._load_ml_review_decisions", return_value={}), \
             patch("app.main._load_annotations", return_value={"annotations": {}}):
            mock_reg.return_value.get_identity.return_value = identity
            mock_photo_reg.return_value.get_photos_for_faces.return_value = []

            result = public_person_page("test-id", is_admin=True)
            html = to_xml(result)
            assert "ML Estimate" not in html
            assert "Born 1902" in html


# ============================================================
# Test: Accept/Reject endpoints
# ============================================================

class TestMLReviewEndpoints:
    """Tests for accept/reject ML birth year review endpoints."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_accept_requires_admin(self, client):
        """Accept endpoint requires admin auth."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post("/api/ml-review/birth-year/test-id/accept",
                             data={"birth_year": "1907"},
                             headers={"HX-Request": "true"})
        assert resp.status_code == 401

    def test_reject_requires_admin(self, client):
        """Reject endpoint requires admin auth."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post("/api/ml-review/birth-year/test-id/reject",
                             headers={"HX-Request": "true"})
        assert resp.status_code == 401

    def test_accept_writes_metadata(self, client):
        """Accept writes birth year to identity metadata."""
        from app.auth import User
        import app.main as main_module

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": [],
            "candidate_ids": [],
            "metadata": {},
            "version_id": 1,
        }

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(id="admin", email="admin@test.com", is_admin=True)), \
             patch("app.main.load_registry") as mock_reg, \
             patch("app.main.save_registry") as mock_save, \
             patch("app.main._load_birth_year_estimates", return_value={
                 "test-id": {"birth_year_estimate": 1907}
             }), \
             patch("app.main._load_ml_review_decisions", return_value={}), \
             patch("app.main._save_ml_review_decisions") as mock_save_decisions, \
             patch("app.main._save_ground_truth_birth_year") as mock_save_gt:
            mock_reg.return_value.get_identity.return_value = identity
            mock_reg.return_value.set_metadata = MagicMock()

            resp = client.post("/api/ml-review/birth-year/test-id/accept",
                             data={"birth_year": "1907"},
                             headers={"HX-Request": "true"})

            assert resp.status_code == 200
            # Verify metadata was set
            mock_reg.return_value.set_metadata.assert_called_once_with(
                "test-id", {"birth_year": 1907}, user_source="admin_ml_review"
            )
            mock_save.assert_called_once()
            mock_save_decisions.assert_called_once()
            mock_save_gt.assert_called_once()

    def test_accept_with_correction(self, client):
        """Edit & Accept records admin correction."""
        from app.auth import User

        identity = {
            "identity_id": "test-id",
            "name": "Big Leon",
            "state": "CONFIRMED",
            "anchor_ids": [],
            "candidate_ids": [],
            "metadata": {},
            "version_id": 1,
        }

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(id="admin", email="admin@test.com", is_admin=True)), \
             patch("app.main.load_registry") as mock_reg, \
             patch("app.main.save_registry"), \
             patch("app.main._load_birth_year_estimates", return_value={
                 "test-id": {"birth_year_estimate": 1907}
             }), \
             patch("app.main._load_ml_review_decisions", return_value={}), \
             patch("app.main._save_ml_review_decisions") as mock_save_decisions, \
             patch("app.main._save_ground_truth_birth_year") as mock_save_gt:
            mock_reg.return_value.get_identity.return_value = identity
            mock_reg.return_value.set_metadata = MagicMock()

            # Admin corrects ML estimate of 1907 to 1902
            resp = client.post("/api/ml-review/birth-year/test-id/accept",
                             data={"birth_year": "1902", "source_detail": "Italian census 1903"},
                             headers={"HX-Request": "true"})

            assert resp.status_code == 200
            # Verify correction was recorded
            mock_reg.return_value.set_metadata.assert_called_once_with(
                "test-id", {"birth_year": 1902}, user_source="admin_ml_review"
            )
            # Check the review decision has admin_correction source
            call_args = mock_save_decisions.call_args[0][0]
            assert call_args["test-id"]["source"] == "admin_correction"
            assert call_args["test-id"]["original_ml_estimate"] == 1907

    def test_reject_records_decision(self, client):
        """Reject records the decision and removes suggestion."""
        from app.auth import User

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(id="admin", email="admin@test.com", is_admin=True)), \
             patch("app.main._load_birth_year_estimates", return_value={
                 "test-id": {"birth_year_estimate": 1907}
             }), \
             patch("app.main._load_ml_review_decisions", return_value={}), \
             patch("app.main._save_ml_review_decisions") as mock_save:

            resp = client.post("/api/ml-review/birth-year/test-id/reject",
                             headers={"HX-Request": "true"})

            assert resp.status_code == 200
            mock_save.assert_called_once()
            decisions = mock_save.call_args[0][0]
            assert decisions["test-id"]["action"] == "rejected"


# ============================================================
# Test: Bulk Review Page
# ============================================================

class TestBulkReviewPage:
    """Tests for the admin bulk review page."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_bulk_review_requires_admin(self, client):
        """Bulk review page requires admin auth."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.get("/admin/review/birth-years")
        assert resp.status_code == 401

    def test_bulk_review_loads_for_admin(self, client):
        """Bulk review page loads successfully for admin."""
        from app.auth import User

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(id="admin", email="admin@test.com", is_admin=True)), \
             patch("app.main._get_pending_ml_birth_year_suggestions", return_value=[]), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.load_registry") as mock_reg:
            resp = client.get("/admin/review/birth-years")

        assert resp.status_code == 200
        assert "ML Birth Year Estimates" in resp.text
        assert "0 pending review" in resp.text

    def test_bulk_review_shows_pending(self, client):
        """Bulk review page shows pending suggestions."""
        from app.auth import User

        suggestions = [{
            "identity_id": "id-1",
            "name": "Big Leon",
            "state": "CONFIRMED",
            "birth_year_estimate": 1907,
            "birth_year_confidence": "high",
            "birth_year_range": [1901, 1914],
            "birth_year_std": 4.34,
            "n_appearances": 25,
            "n_with_age_data": 12,
            "evidence": [{"photo_year": 1924, "estimated_age": 19}],
        }]

        mock_identity = {
            "identity_id": "id-1",
            "name": "Big Leon",
            "anchor_ids": [],
            "candidate_ids": [],
        }

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(id="admin", email="admin@test.com", is_admin=True)), \
             patch("app.main._get_pending_ml_birth_year_suggestions", return_value=suggestions), \
             patch("app.main.get_crop_files", return_value={}), \
             patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_best_face_id", return_value=None), \
             patch("app.main.resolve_face_image_url", return_value=None):
            mock_reg.return_value.get_identity.return_value = mock_identity
            resp = client.get("/admin/review/birth-years")

        assert resp.status_code == 200
        assert "1 pending review" in resp.text
        assert "Big Leon" in resp.text
        assert "1907" in resp.text


# ============================================================
# Test: Pending suggestions helper
# ============================================================

class TestPendingSuggestions:
    """Tests for _get_pending_ml_birth_year_suggestions."""

    def test_excludes_already_reviewed(self):
        """Already-reviewed identities are excluded."""
        from app.main import _get_pending_ml_birth_year_suggestions

        with patch("app.main._load_birth_year_estimates", return_value={
            "id-1": {"birth_year_estimate": 1907, "birth_year_confidence": "high"},
        }), \
             patch("app.main._load_ml_review_decisions", return_value={
                 "id-1": {"action": "accepted"},
             }), \
             patch("app.main.load_registry") as mock_reg:
            result = _get_pending_ml_birth_year_suggestions()

        assert len(result) == 0

    def test_excludes_already_confirmed(self):
        """Identities with confirmed metadata birth year are excluded."""
        from app.main import _get_pending_ml_birth_year_suggestions

        identity = {
            "identity_id": "id-1",
            "name": "Test",
            "state": "CONFIRMED",
            "birth_year": 1902,
            "metadata": {},
        }

        with patch("app.main._load_birth_year_estimates", return_value={
            "id-1": {"birth_year_estimate": 1907, "birth_year_confidence": "high"},
        }), \
             patch("app.main._load_ml_review_decisions", return_value={}), \
             patch("app.main.load_registry") as mock_reg:
            mock_reg.return_value.get_identity.return_value = identity
            result = _get_pending_ml_birth_year_suggestions()

        assert len(result) == 0

    def test_sorts_by_confidence(self):
        """Suggestions are sorted by confidence (high first)."""
        from app.main import _get_pending_ml_birth_year_suggestions

        identity_a = {"identity_id": "id-a", "name": "A", "state": "CONFIRMED", "metadata": {}}
        identity_b = {"identity_id": "id-b", "name": "B", "state": "CONFIRMED", "metadata": {}}

        with patch("app.main._load_birth_year_estimates", return_value={
            "id-a": {"birth_year_estimate": 1907, "birth_year_confidence": "low", "n_with_age_data": 5},
            "id-b": {"birth_year_estimate": 1910, "birth_year_confidence": "high", "n_with_age_data": 15},
        }), \
             patch("app.main._load_ml_review_decisions", return_value={}), \
             patch("app.main.load_registry") as mock_reg:
            mock_reg.return_value.get_identity.side_effect = lambda iid: {
                "id-a": identity_a, "id-b": identity_b
            }[iid]
            result = _get_pending_ml_birth_year_suggestions()

        assert len(result) == 2
        assert result[0]["identity_id"] == "id-b"  # high confidence first
        assert result[1]["identity_id"] == "id-a"


# ============================================================
# Test: Version display
# ============================================================

class TestVersionDisplay:
    """Tests for dynamic version reading."""

    def test_version_reads_from_changelog(self):
        """APP_VERSION reads the first version from CHANGELOG.md."""
        from app.main import APP_VERSION
        assert APP_VERSION.startswith("v")
        assert "." in APP_VERSION
        # Should NOT be the old hardcoded value
        assert APP_VERSION != "v0.6.0"
        assert APP_VERSION != "v0.8.0"

    def test_version_in_sidebar(self):
        """Sidebar shows dynamic version, not hardcoded."""
        import app.main as main_module
        import inspect

        source = inspect.getsource(main_module)
        # Should use APP_VERSION, not hardcoded string
        assert 'Div("v0.6.0"' not in source
        assert 'Div("v0.8.0"' not in source
        assert "APP_VERSION" in source


# ============================================================
# Test: ML review decisions cache invalidation
# ============================================================

class TestCacheInvalidation:
    """Tests that ML review decisions cache is properly invalidated."""

    def test_ml_review_cache_in_sync_invalidation(self):
        """_ml_review_decisions_cache is reset in sync push handler."""
        import app.main as main_module
        import inspect

        assert hasattr(main_module, "_ml_review_decisions_cache")

        source = inspect.getsource(main_module)
        assert "_ml_review_decisions_cache = None" in source
        assert "_ml_review_decisions_cache" in source

    def test_admin_nav_includes_birth_years(self):
        """Admin nav bar includes Birth Years link."""
        from app.main import _admin_nav_bar
        from fastcore.xml import to_xml

        html = to_xml(_admin_nav_bar("birth-year-review"))
        assert "Birth Years" in html
        assert "/admin/review/birth-years" in html
