"""Tests for Session 92 Track D: UX bug fixes."""

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# Mock data for identify page tests
_MOCK_IDENTITIES = {
    "identities": {
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
    },
    "history": [],
}


def _patch_identify():
    """Patches for identify page tests."""
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=["photo-abc123"])
    mock_photo_reg._photos = {}

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main._photo_cache", {"photo-abc123": {"path": "test.jpg", "collection": "Test"}}),
        patch("app.main.get_crop_files", return_value={"face-u1.jpg"}),
        patch("app.main.get_best_face_id", return_value="face-u1"),
        patch("app.main.resolve_face_image_url", return_value="/static/crops/face-u1.jpg"),
        patch("app.main._load_identification_responses", return_value={"schema_version": 1, "responses": []}),
    ]


class TestD1IdentifySourcePhotoLink:
    """D1: /identify/{id} should have a 'View source photo' link."""

    def test_identify_has_source_photo_link(self, client):
        patches = _patch_identify()
        for p in patches:
            p.start()
        try:
            resp = client.get("/identify/unknown-1")
            assert resp.status_code == 200
            assert "/photo/photo-abc123" in resp.text
            assert "view-source-photo-link" in resp.text
        finally:
            for p in patches:
                p.stop()


class TestD2CompareUploadIndicator:
    """D2: Compare upload forms should have hx-indicator attributes."""

    def test_compare_upload_form_has_indicator(self, client):
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/compare")
        assert resp.status_code == 200
        assert "hx-indicator" in resp.text
        assert "ws-upload-spinner" in resp.text

    def test_compare_upload_result_has_auto_scroll(self, client):
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/compare")
        assert "hx-on::after-settle" in resp.text


class TestD3EstimateUploadIndicator:
    """D3: Estimate upload form should have hx-indicator and auto-scroll."""

    def test_estimate_upload_form_has_indicator(self, client):
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/estimate")
        assert resp.status_code == 200
        assert "hx-indicator" in resp.text
        assert "estimate-upload-spinner" in resp.text

    def test_estimate_upload_result_has_auto_scroll(self, client):
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/estimate")
        assert "hx-on::after-settle" in resp.text


class TestD4Custom404Page:
    """D4: 404 page should have Tailwind CDN and navbar."""

    def test_404_has_tailwind(self, client):
        resp = client.get("/nonexistent-page-xyz123")
        assert resp.status_code == 404
        assert "tailwindcss" in resp.text

    def test_404_has_navbar(self, client):
        resp = client.get("/nonexistent-page-xyz123")
        assert resp.status_code == 404
        assert "Rhodesli" in resp.text
        assert 'href="/"' in resp.text

    def test_404_has_message(self, client):
        resp = client.get("/nonexistent-page-xyz123")
        assert resp.status_code == 404
        assert "Page not found" in resp.text


class TestD5AboutPageNavbar:
    """D5: About page should have navbar."""

    def test_about_has_navbar(self, client):
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/about")
        assert resp.status_code == 200
        assert "Rhodesli" in resp.text
        assert "Photos" in resp.text
        assert "People" in resp.text


class TestD6BirthYearRaceCondition:
    """D6: Birth year save button should have event.stopPropagation() to prevent race condition."""

    def test_birth_year_save_has_stop_propagation(self):
        """The Save button in the birth year ML suggestion form must call stopPropagation."""
        import inspect

        import app.person_routes as pr

        source = inspect.getsource(pr.public_person_page)
        # The birth year accept form's Save button should have stopPropagation
        # to prevent the click event from bubbling up and triggering the parent
        # accordion toggle, which would race with the HTMX POST.
        assert "event.stopPropagation()" in source

    def test_metadata_save_has_stop_propagation(self):
        """The Save Metadata button should also have stopPropagation."""
        import inspect

        import app.person_routes as pr

        source = inspect.getsource(pr.public_person_page)
        # Count occurrences — should appear at least twice (birth year + metadata)
        count = source.count("event.stopPropagation()")
        assert count >= 2, f"Expected at least 2 stopPropagation calls, found {count}"


class TestD7CTAStandardization:
    """D7: Contribution CTAs should use 'Can you help?' not 'Do you know?'."""

    def test_no_do_you_know_in_person_page(self):
        """The person page should NOT contain 'Do you know?' CTA text."""
        import inspect

        import app.person_routes as pr

        source = inspect.getsource(pr.public_person_page)
        assert "Do you know?" not in source, (
            "Found 'Do you know?' in person page — should be standardized to 'Can you help?'"
        )

    def test_can_you_help_present_in_person_page(self):
        """The person page SHOULD contain 'Can you help?' CTA text."""
        import inspect

        import app.person_routes as pr

        source = inspect.getsource(pr.public_person_page)
        assert "Can you help?" in source


class TestD8IdentifiedTooltip:
    """D8: The 'Identified' badge on person page should have a title tooltip."""

    def test_identified_badge_has_title_attribute(self):
        """The Identified badge Span must have a title attribute for tooltip."""
        import inspect

        import app.person_routes as pr

        source = inspect.getsource(pr.public_person_page)
        # Find the section where the "Identified" badge is created
        # It should have a title= kwarg
        assert 'title="This person has been identified by an admin"' in source

    def test_under_review_badge_exists(self):
        """The Under Review badge should still exist as the alternative state."""
        import inspect

        import app.person_routes as pr

        source = inspect.getsource(pr.public_person_page)
        assert '"Under Review"' in source


class TestD9CollectionDropdown:
    """D9: Collection input should use placeholder instead of onfocus='this.select()'."""

    def test_collection_input_has_placeholder(self):
        """The collection input field should have a placeholder attribute."""
        import inspect

        import app.page_routes as pgr

        source = inspect.getsource(pgr.public_photo_page)
        assert 'placeholder="Select or type a collection"' in source

    def test_collection_input_no_onfocus(self):
        """The collection input should NOT have onfocus='this.select()' (replaced by placeholder)."""
        import inspect

        import app.page_routes as pgr

        source = inspect.getsource(pgr.public_photo_page)
        assert 'onfocus="this.select()"' not in source, (
            "Found onfocus='this.select()' in collection input — should be replaced with placeholder"
        )

    def test_collection_input_has_placeholder_styling(self):
        """The collection input should have placeholder-slate-500 styling class."""
        import inspect

        import app.page_routes as pgr

        source = inspect.getsource(pgr.public_photo_page)
        assert "placeholder-slate-500" in source


class TestD10EventsAdminBar:
    """D10: Events page should have exactly 1 admin bar (no duplicates)."""

    def test_events_page_no_duplicate_admin_bar(self, client):
        """Events page should not call _admin_bar separately from _public_page_nav."""
        import app.event_routes as er
        import inspect

        # Check that the /events GET function source code doesn't have
        # a standalone _admin_bar call outside of _public_page_nav
        source = inspect.getsource(er)
        # After fix, _admin_bar should not appear in event_routes.py
        # (it's included automatically by _public_page_nav)
        assert "_admin_bar" not in source
