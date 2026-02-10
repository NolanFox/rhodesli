"""
Tests for identity-level annotations display (AN-012–AN-014).
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient
from fastcore.xml import to_xml


class TestIdentityMetadataDisplay:
    """AN-012: Identity metadata display on detail views."""

    def test_displays_bio(self):
        """Bio field renders on identity card."""
        from app.main import _identity_metadata_display
        identity = {"bio": "Founder of the Rhodes community center"}
        html = to_xml(_identity_metadata_display(identity))
        assert "Bio" in html
        assert "Founder of the Rhodes community center" in html

    def test_displays_birth_death_years(self):
        """Birth and death years render."""
        from app.main import _identity_metadata_display
        identity = {"birth_year": 1920, "death_year": 2005}
        html = to_xml(_identity_metadata_display(identity))
        assert "1920" in html
        assert "2005" in html

    def test_displays_birth_place(self):
        """Birth place renders."""
        from app.main import _identity_metadata_display
        identity = {"birth_place": "Rhodes, Greece"}
        html = to_xml(_identity_metadata_display(identity))
        assert "Rhodes, Greece" in html

    def test_displays_maiden_name(self):
        """Maiden name renders."""
        from app.main import _identity_metadata_display
        identity = {"maiden_name": "Capeluto"}
        html = to_xml(_identity_metadata_display(identity))
        assert "Capeluto" in html

    def test_displays_relationship_notes(self):
        """Relationship notes render."""
        from app.main import _identity_metadata_display
        identity = {"relationship_notes": "Sister of Vida Capeluto"}
        html = to_xml(_identity_metadata_display(identity))
        assert "Sister of Vida Capeluto" in html

    def test_empty_when_no_metadata(self):
        """Returns empty span when no metadata fields present."""
        from app.main import _identity_metadata_display
        identity = {"name": "Test Person", "state": "CONFIRMED"}
        html = to_xml(_identity_metadata_display(identity))
        assert "Bio" not in html
        assert "Birth" not in html

    def test_displays_multiple_fields(self):
        """Multiple metadata fields all display."""
        from app.main import _identity_metadata_display
        identity = {
            "bio": "A teacher",
            "birth_year": 1910,
            "birth_place": "Istanbul",
            "maiden_name": "Franco",
        }
        html = to_xml(_identity_metadata_display(identity))
        assert "A teacher" in html
        assert "1910" in html
        assert "Istanbul" in html
        assert "Franco" in html


class TestIdentityAnnotationsSection:
    """AN-013/AN-014: Identity annotations display and submission form."""

    def test_renders_empty_state(self):
        """No annotations shows the add form but no items."""
        from app.main import _identity_annotations_section
        with patch("app.main._load_annotations", return_value={"annotations": {}}):
            html = to_xml(_identity_annotations_section("test-id", is_admin=False))
            assert "Add annotation" in html
            assert "identity-annotations-test-id" in html

    def test_shows_approved_annotations(self):
        """Approved identity annotations are displayed."""
        from app.main import _identity_annotations_section
        mock_annotations = {
            "annotations": {
                "ann-1": {
                    "target_type": "identity",
                    "target_id": "test-id",
                    "type": "bio",
                    "value": "Born in Rhodes, immigrated to NYC",
                    "status": "approved",
                    "submitted_at": "2026-01-01T00:00:00",
                },
            }
        }
        with patch("app.main._load_annotations", return_value=mock_annotations):
            html = to_xml(_identity_annotations_section("test-id"))
            assert "Born in Rhodes, immigrated to NYC" in html

    def test_hides_pending_from_non_admin(self):
        """Pending annotations are not shown to non-admin users."""
        from app.main import _identity_annotations_section
        mock_annotations = {
            "annotations": {
                "ann-1": {
                    "target_type": "identity",
                    "target_id": "test-id",
                    "type": "bio",
                    "value": "Pending bio",
                    "status": "pending",
                    "submitted_at": "2026-01-01T00:00:00",
                },
            }
        }
        with patch("app.main._load_annotations", return_value=mock_annotations):
            html = to_xml(_identity_annotations_section("test-id", is_admin=False))
            assert "Pending bio" not in html

    def test_admin_sees_pending_badge(self):
        """Admin users see pending count badge."""
        from app.main import _identity_annotations_section
        mock_annotations = {
            "annotations": {
                "ann-1": {
                    "target_type": "identity",
                    "target_id": "test-id",
                    "type": "relationship",
                    "value": "Brother of X",
                    "status": "pending",
                    "submitted_at": "2026-01-01T00:00:00",
                },
            }
        }
        with patch("app.main._load_annotations", return_value=mock_annotations):
            html = to_xml(_identity_annotations_section("test-id", is_admin=True))
            assert "pending" in html.lower()

    def test_form_has_identity_types(self):
        """Submission form includes identity-specific annotation types."""
        from app.main import _identity_annotations_section
        with patch("app.main._load_annotations", return_value={"annotations": {}}):
            html = to_xml(_identity_annotations_section("test-id"))
            assert "Bio" in html or "bio" in html
            assert "Relationship" in html or "relationship" in html
            assert "Story" in html or "story" in html

    def test_form_posts_to_correct_endpoint(self):
        """Form submits to annotation API."""
        from app.main import _identity_annotations_section
        with patch("app.main._load_annotations", return_value={"annotations": {}}):
            html = to_xml(_identity_annotations_section("test-id"))
            assert "/api/annotations/submit" in html

    def test_shows_multiple_annotation_types(self):
        """Multiple approved annotation types display with labels."""
        from app.main import _identity_annotations_section
        mock_annotations = {
            "annotations": {
                "ann-1": {
                    "target_type": "identity",
                    "target_id": "test-id",
                    "type": "bio",
                    "value": "A teacher from Rhodes",
                    "status": "approved",
                    "submitted_at": "2026-01-01T00:00:00",
                },
                "ann-2": {
                    "target_type": "identity",
                    "target_id": "test-id",
                    "type": "relationship",
                    "value": "Mother of Nace Capeluto",
                    "status": "approved",
                    "submitted_at": "2026-01-02T00:00:00",
                },
            }
        }
        with patch("app.main._load_annotations", return_value=mock_annotations):
            html = to_xml(_identity_annotations_section("test-id"))
            assert "A teacher from Rhodes" in html
            assert "Mother of Nace Capeluto" in html
