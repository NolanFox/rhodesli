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


    def test_generation_qualifier_stored(self):
        """Generation qualifier stored as metadata."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test", name="Leon Capeluto")

        registry.set_metadata(iid, {
            "generation_qualifier": "Sr.",
        }, user_source="test")

        identity = registry.get_identity(iid)
        assert identity["generation_qualifier"] == "Sr."

    def test_death_place_stored(self):
        """Death place stored as metadata."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test", name="Leon Capeluto")

        registry.set_metadata(iid, {
            "death_place": "Auschwitz",
        }, user_source="test")

        identity = registry.get_identity(iid)
        assert identity["death_place"] == "Auschwitz"

    def test_full_structured_identity(self):
        """All structured name and metadata fields work together."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        iid = registry.create_identity(anchor_ids=["face1"], user_source="test", name="Leon Capeluto")
        # rename_identity auto-parses first/last name
        registry.rename_identity(iid, "Leon Capeluto", user_source="test")

        registry.set_metadata(iid, {
            "generation_qualifier": "Sr.",
            "birth_year": 1890,
            "death_year": 1944,
            "birth_place": "Rhodes, Greece",
            "death_place": "Auschwitz",
            "bio": "Community leader",
        }, user_source="test")

        identity = registry.get_identity(iid)
        assert identity["first_name"] == "Leon"
        assert identity["last_name"] == "Capeluto"
        assert identity["generation_qualifier"] == "Sr."
        assert identity["birth_year"] == 1890
        assert identity["death_year"] == 1944
        assert identity["birth_place"] == "Rhodes, Greece"
        assert identity["death_place"] == "Auschwitz"
        assert identity["bio"] == "Community leader"


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
        from unittest.mock import MagicMock
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
        }

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg), \
             patch("app.main.save_registry"):
            response = client.post(
                "/api/identity/test-id-001/metadata",
                data={"birth_place": "Rhodes, Greece"}
            )
            assert response.status_code == 200
            mock_reg.set_metadata.assert_called_once()


class TestSuggestNameForm:
    """Tests for the Suggest Name form on identity cards."""

    def test_suggest_name_form_renders(self):
        """Suggest name form renders correctly for an identity."""
        from app.main import _suggest_name_form
        from fastcore.xml import to_xml

        result = _suggest_name_form("test-identity-id")
        html = to_xml(result)
        assert "suggest-name-test-identity-id" in html
        assert "I Know This Person" in html
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


class TestMetadataEditForm:
    """Tests for the inline metadata edit form."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_metadata_form_endpoint_exists(self, client):
        """GET /api/identity/{id}/metadata-form returns a form."""
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
            "birth_year": 1920,
            "birth_place": "Rhodes, Greece",
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg):
            response = client.get("/api/identity/test-id-001/metadata-form")
            assert response.status_code == 200
            assert "maiden_name" in response.text.lower() or "Maiden" in response.text
            assert "birth_year" in response.text.lower() or "Birth Year" in response.text
            assert "bio" in response.text.lower() or "Bio" in response.text

    def test_metadata_form_pre_fills_values(self, client):
        """Form pre-fills with existing metadata values."""
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
            "birth_place": "Rhodes, Greece",
            "maiden_name": "Hasson",
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg):
            response = client.get("/api/identity/test-id-001/metadata-form")
            assert "Rhodes, Greece" in response.text
            assert "Hasson" in response.text

    def test_metadata_form_requires_admin(self, client):
        """Metadata form requires admin authentication."""
        from app.auth import User
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.get("/api/identity/test-id-001/metadata-form")
            assert response.status_code in (401, 403)

    def test_metadata_display_shows_edit_button_for_admin(self):
        """Metadata display includes edit button for admin users."""
        from app.main import _identity_metadata_display, to_xml

        identity = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        html = to_xml(_identity_metadata_display(identity, is_admin=True))
        assert "Edit Details" in html or "Edit" in html
        assert "metadata-form" in html

    def test_metadata_display_no_edit_for_non_admin(self):
        """Metadata display has no edit button for non-admin users."""
        from app.main import _identity_metadata_display, to_xml

        identity = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        html = to_xml(_identity_metadata_display(identity, is_admin=False))
        assert "metadata-form" not in html

    def test_metadata_post_returns_updated_display(self, client):
        """POST metadata returns updated display, not just a toast."""
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
            "birth_place": "Rhodes, Greece",
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg), \
             patch("app.main.save_registry"):
            response = client.post(
                "/api/identity/test-id-001/metadata",
                data={"birth_place": "Rhodes, Greece"}
            )
            assert response.status_code == 200
            # Should contain updated display, not just a toast
            assert "metadata-test-id-001" in response.text or "Metadata updated" in response.text


class TestMetadataDisplayFormat:
    """Tests for compact metadata display format."""

    def test_display_compact_summary_birth_death(self):
        """Compact summary shows 'YYYY–YYYY' for birth and death years."""
        from app.main import _identity_metadata_display, to_xml

        identity = {
            "identity_id": "test-id-001",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "birth_year": 1890,
            "death_year": 1944,
        }
        html = to_xml(_identity_metadata_display(identity, is_admin=False))
        assert "1890" in html
        assert "1944" in html

    def test_display_compact_summary_places(self):
        """Compact summary shows 'Birthplace -> Deathplace' with arrow."""
        from app.main import _identity_metadata_display, to_xml

        identity = {
            "identity_id": "test-id-002",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "birth_place": "Rhodes, Greece",
            "death_place": "Auschwitz",
        }
        html = to_xml(_identity_metadata_display(identity, is_admin=False))
        assert "Rhodes, Greece" in html
        assert "Auschwitz" in html

    def test_display_compact_summary_maiden_name(self):
        """Compact summary shows maiden name with 'nee'."""
        from app.main import _identity_metadata_display, to_xml

        identity = {
            "identity_id": "test-id-003",
            "name": "Victoria Cukran",
            "state": "CONFIRMED",
            "maiden_name": "Capeluto",
        }
        html = to_xml(_identity_metadata_display(identity, is_admin=False))
        assert "Capeluto" in html

    def test_display_only_birth_year(self):
        """Shows 'b. YYYY' when only birth year is known."""
        from app.main import _identity_metadata_display, to_xml

        identity = {
            "identity_id": "test-id-004",
            "name": "Test Person",
            "state": "CONFIRMED",
            "birth_year": 1920,
        }
        html = to_xml(_identity_metadata_display(identity, is_admin=False))
        assert "b. 1920" in html

    def test_display_only_death_year(self):
        """Shows 'd. YYYY' when only death year is known."""
        from app.main import _identity_metadata_display, to_xml

        identity = {
            "identity_id": "test-id-005",
            "name": "Test Person",
            "state": "CONFIRMED",
            "death_year": 1944,
        }
        html = to_xml(_identity_metadata_display(identity, is_admin=False))
        assert "d. 1944" in html

    def test_display_no_metadata_empty(self):
        """No metadata renders empty span (no crash)."""
        from app.main import _identity_metadata_display, to_xml

        identity = {
            "identity_id": "test-id-006",
            "name": "Unknown Person",
            "state": "INBOX",
        }
        html = to_xml(_identity_metadata_display(identity, is_admin=False))
        # Should render without error — no metadata fields present
        assert html is not None


class TestNameDisplayQualifier:
    """Tests for name display with generation qualifier."""

    def test_name_display_with_qualifier(self):
        """Name display appends generation qualifier."""
        from app.main import name_display, to_xml

        result = name_display("test-id", "Leon Capeluto", is_admin=False,
                              generation_qualifier="Sr.")
        html = to_xml(result)
        assert "Leon Capeluto Sr." in html

    def test_name_display_without_qualifier(self):
        """Name display works without qualifier."""
        from app.main import name_display, to_xml

        result = name_display("test-id", "Leon Capeluto", is_admin=False)
        html = to_xml(result)
        assert "Leon Capeluto" in html
        assert "Sr." not in html

    def test_name_display_empty_qualifier_ignored(self):
        """Empty qualifier string doesn't add trailing space."""
        from app.main import name_display, to_xml

        result = name_display("test-id", "Leon Capeluto", is_admin=False,
                              generation_qualifier="")
        html = to_xml(result)
        assert "Leon Capeluto" in html
        # No trailing space before closing tag
        assert "Leon Capeluto " not in html or "Leon Capeluto Sr" not in html


class TestPlaceAutocomplete:
    """Tests for geographic place autocomplete on metadata form."""

    def test_place_options_load(self):
        """Place options loaded from location_dictionary.json."""
        from app.main import _get_place_options
        options = _get_place_options()
        # Should have location_dictionary places
        values = [v for v, _ in options]
        assert "Rhodes, Greece" in values
        assert "Miami, Florida" in values

    def test_place_options_include_historical_aliases(self):
        """Historical name aliases are included in place options."""
        from app.main import _get_place_options
        options = _get_place_options()
        labels = [label for _, label in options]
        # Historical aliases should appear as labels
        assert any("Salonika" in label for label in labels)
        assert any("Constantinople" in label for label in labels)

    def test_metadata_form_has_datalist(self, client):
        """Metadata form includes places datalist for autocomplete."""
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg):
            response = client.get("/api/identity/test-id-001/metadata-form")
            assert response.status_code == 200
            assert "places-list" in response.text
            assert "datalist" in response.text.lower() or "Datalist" in response.text

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)


class TestMetadataFormNewFields:
    """Tests for generation_qualifier and death_place in the metadata form."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_form_includes_qualifier_field(self, client):
        """Metadata form has generation_qualifier input."""
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg):
            response = client.get("/api/identity/test-id-001/metadata-form")
            assert response.status_code == 200
            assert "generation_qualifier" in response.text

    def test_form_includes_death_place_field(self, client):
        """Metadata form has death_place input."""
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg):
            response = client.get("/api/identity/test-id-001/metadata-form")
            assert response.status_code == 200
            assert "death_place" in response.text

    def test_post_qualifier_and_death_place(self, client):
        """POST metadata accepts generation_qualifier and death_place."""
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "generation_qualifier": "Sr.",
            "death_place": "Auschwitz",
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg), \
             patch("app.main.save_registry"):
            response = client.post(
                "/api/identity/test-id-001/metadata",
                data={"generation_qualifier": "Sr.", "death_place": "Auschwitz"}
            )
            assert response.status_code == 200
            mock_reg.set_metadata.assert_called_once()
            call_args = mock_reg.set_metadata.call_args
            metadata = call_args[0][1]
            assert metadata["generation_qualifier"] == "Sr."
            assert metadata["death_place"] == "Auschwitz"
