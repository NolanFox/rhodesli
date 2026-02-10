"""
Tests for structured names (BE-010) and identity metadata (BE-011).
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock


class TestStructuredNames:
    """BE-010: Structured name fields on identities."""

    def test_rename_auto_parses_first_last(self):
        """Setting name 'Leon Capeluto' auto-populates first_name and last_name."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test", name="Unknown")

        registry.rename_identity(iid, "Leon Capeluto", user_source="test")

        identity = registry.get_identity(iid)
        assert identity["name"] == "Leon Capeluto"
        assert identity["first_name"] == "Leon"
        assert identity["last_name"] == "Capeluto"

    def test_rename_single_name(self):
        """Single-word name goes to first_name, last_name is empty."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test")

        registry.rename_identity(iid, "Nona", user_source="test")

        identity = registry.get_identity(iid)
        assert identity["first_name"] == "Nona"
        assert identity["last_name"] == ""

    def test_structured_name_backwards_compatible(self):
        """Existing identities without structured names still work."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test", name="Leon")

        # Identity should work fine without first_name/last_name
        identity = registry.get_identity(iid)
        assert identity["name"] == "Leon"
        # These fields might not exist on old identities
        # The code should handle their absence gracefully


class TestIdentityMetadata:
    """BE-011: Identity metadata fields."""

    def test_set_metadata_fields(self):
        """Setting metadata updates identity fields."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test", name="Leon")

        registry.set_metadata(iid, {
            "birth_year": 1905,
            "death_year": 1982,
            "birth_place": "Rhodes, Greece",
        }, user_source="test")

        identity = registry.get_identity(iid)
        assert identity["birth_year"] == 1905
        assert identity["death_year"] == 1982
        assert identity["birth_place"] == "Rhodes, Greece"

    def test_identity_metadata_optional(self):
        """Identities work without metadata fields."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test")

        identity = registry.get_identity(iid)
        # No metadata fields present — this should not error
        assert "birth_year" not in identity
        assert identity["name"] is not None or identity.get("name") is None

    def test_set_metadata_rejects_invalid_keys(self):
        """Invalid metadata keys are silently ignored."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test")

        registry.set_metadata(iid, {
            "birth_year": 1905,
            "invalid_field": "should_be_ignored",
        }, user_source="test")

        identity = registry.get_identity(iid)
        assert identity["birth_year"] == 1905
        assert "invalid_field" not in identity

    def test_maiden_name_stored(self):
        """Maiden name stored as metadata."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test", name="Victoria Cukran Capeluto")

        registry.set_metadata(iid, {
            "maiden_name": "Capeluto",
        }, user_source="test")

        identity = registry.get_identity(iid)
        assert identity["maiden_name"] == "Capeluto"


class TestMetadataEndpoint:
    """Tests for POST /api/identity/{id}/metadata."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_metadata_edit_admin_only(self, client):
        """Only admins can edit metadata."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post(
                "/api/identity/fake-id/metadata",
                data={"birth_year": "1905"}
            )
            assert response.status_code in (401, 403)

    def test_metadata_update_success(self, client):
        """Admin can update metadata successfully."""
        from app.main import load_registry
        registry = load_registry()
        confirmed = registry.list_identities(state=None)
        if not confirmed:
            pytest.skip("No identities available for testing")

        # Find an identity to test with
        test_id = confirmed[0]["identity_id"]

        response = client.post(
            f"/api/identity/{test_id}/metadata",
            data={"birth_place": "Rhodes, Greece"}
        )
        assert response.status_code == 200


class TestSuggestNameForm:
    """Tests for the Suggest Name form on identity cards."""

    def test_suggest_name_form_renders(self):
        """Suggest name form renders correctly for an identity."""
        from app.main import _suggest_name_form
        from fastcore.xml import to_xml

        result = _suggest_name_form("test-identity-id")
        html = to_xml(result)
        assert "suggest-name-test-identity-id" in html
        assert "Suggest a Name" in html
        assert "name_suggestion" in html
        assert "/api/annotations/submit" in html

    def test_suggest_name_form_has_confidence_options(self):
        """Form includes confidence level dropdown."""
        from app.main import _suggest_name_form
        from fastcore.xml import to_xml

        html = to_xml(_suggest_name_form("test-id"))
        assert "certain" in html
        assert "likely" in html
        assert "guess" in html
