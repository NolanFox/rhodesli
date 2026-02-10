"""
Tests for contributor and trusted contributor roles (ROLE-002, ROLE-003).
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


class TestUserRole:
    """ROLE-002: User model has role field."""

    def test_admin_user_has_admin_role(self):
        """Admin users have role='admin'."""
        from app.auth import User, ADMIN_EMAILS
        with patch.object(User, '__module__', 'app.auth'):
            user = User(id="1", email="nolanfox@gmail.com", is_admin=True, role="admin")
            assert user.role == "admin"
            assert user.is_admin

    def test_contributor_user_has_contributor_role(self):
        """Contributor users have role='contributor'."""
        from app.auth import User
        user = User(id="2", email="helper@test.com", is_admin=False, role="contributor")
        assert user.role == "contributor"
        assert not user.is_admin

    def test_viewer_is_default_role(self):
        """Default role is 'viewer' for logged-in non-admin users."""
        from app.auth import User
        user = User(id="3", email="viewer@test.com", is_admin=False)
        assert user.role == "viewer"

    def test_from_session_assigns_admin_role(self):
        """from_session gives admin role to admin emails."""
        from app.auth import User
        with patch("app.auth.ADMIN_EMAILS", {"admin@test.com"}), \
             patch("app.auth.CONTRIBUTOR_EMAILS", set()):
            user = User.from_session({"id": "1", "email": "admin@test.com"})
            assert user.role == "admin"
            assert user.is_admin

    def test_from_session_assigns_contributor_role(self):
        """from_session gives contributor role to contributor emails."""
        from app.auth import User
        with patch("app.auth.ADMIN_EMAILS", set()), \
             patch("app.auth.CONTRIBUTOR_EMAILS", {"helper@test.com"}):
            user = User.from_session({"id": "2", "email": "helper@test.com"})
            assert user.role == "contributor"
            assert not user.is_admin

    def test_from_session_default_viewer(self):
        """from_session defaults to viewer for unknown emails."""
        from app.auth import User
        with patch("app.auth.ADMIN_EMAILS", set()), \
             patch("app.auth.CONTRIBUTOR_EMAILS", set()):
            user = User.from_session({"id": "3", "email": "nobody@test.com"})
            assert user.role == "viewer"


class TestCheckContributor:
    """ROLE-002: _check_contributor permission helper."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_check_contributor_allows_admin(self):
        """Admin passes contributor check."""
        from app.main import _check_contributor
        from app.auth import User
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(
                 id="1", email="admin@test.com", is_admin=True, role="admin")):
            result = _check_contributor({"auth": {"id": "1", "email": "admin@test.com"}})
            assert result is None  # None means allowed

    def test_check_contributor_allows_contributor(self):
        """Contributor role passes contributor check."""
        from app.main import _check_contributor
        from app.auth import User
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(
                 id="2", email="helper@test.com", is_admin=False, role="contributor")):
            result = _check_contributor({"auth": {"id": "2", "email": "helper@test.com"}})
            assert result is None

    def test_check_contributor_rejects_viewer(self):
        """Viewer role is rejected by contributor check."""
        from app.main import _check_contributor
        from app.auth import User
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=User(
                 id="3", email="viewer@test.com", is_admin=False, role="viewer")):
            result = _check_contributor({"auth": {"id": "3", "email": "viewer@test.com"}})
            assert result is not None
            assert result.status_code == 403

    def test_check_contributor_rejects_anonymous(self):
        """Anonymous users are rejected with 401."""
        from app.main import _check_contributor
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            result = _check_contributor({})
            assert result is not None
            assert result.status_code == 401

    def test_check_contributor_allows_all_when_auth_disabled(self):
        """When auth is disabled, contributor check passes."""
        from app.main import _check_contributor
        with patch("app.main.is_auth_enabled", return_value=False):
            result = _check_contributor({})
            assert result is None


class TestTrustedContributor:
    """ROLE-003: Trusted contributor auto-promotion."""

    def test_trusted_threshold_default(self):
        """Trusted contributor threshold has a default value."""
        from app.auth import TRUSTED_CONTRIBUTOR_THRESHOLD
        assert TRUSTED_CONTRIBUTOR_THRESHOLD >= 1

    def test_is_trusted_contributor_with_enough_approvals(self):
        """Users with enough approved annotations qualify as trusted."""
        from app.auth import is_trusted_contributor
        mock_annotations = {
            "annotations": {
                f"ann-{i}": {
                    "submitted_by": "helper@test.com",
                    "status": "approved",
                } for i in range(5)
            }
        }
        assert is_trusted_contributor("helper@test.com", mock_annotations) is True

    def test_is_trusted_contributor_not_enough_approvals(self):
        """Users with too few approved annotations don't qualify."""
        from app.auth import is_trusted_contributor
        mock_annotations = {
            "annotations": {
                "ann-1": {
                    "submitted_by": "newbie@test.com",
                    "status": "approved",
                },
                "ann-2": {
                    "submitted_by": "newbie@test.com",
                    "status": "pending",
                },
            }
        }
        assert is_trusted_contributor("newbie@test.com", mock_annotations) is False

    def test_is_trusted_contributor_counts_only_approved(self):
        """Only 'approved' status counts, not 'pending' or 'rejected'."""
        from app.auth import is_trusted_contributor
        mock_annotations = {
            "annotations": {
                f"ann-{i}": {
                    "submitted_by": "mixed@test.com",
                    "status": "approved" if i < 3 else "rejected",
                } for i in range(10)
            }
        }
        # Only 3 approved — below default threshold of 5
        assert is_trusted_contributor("mixed@test.com", mock_annotations) is False


class TestContributorUI:
    """ROLE-002: Contributors see appropriate UI elements."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_my_contributions_page_accessible(self, client):
        """Contributors can access /my-contributions page."""
        response = client.get("/my-contributions")
        assert response.status_code == 200

    def test_contributor_sees_annotation_forms(self, client):
        """Identity cards show annotation submission form."""
        # Auth disabled = admin access, but annotation forms should be visible
        from app.main import _identity_annotations_section
        with patch("app.main._load_annotations", return_value={"annotations": {}}):
            from fastcore.xml import to_xml
            html = to_xml(_identity_annotations_section("test-id", is_admin=False))
            assert "Add annotation" in html
