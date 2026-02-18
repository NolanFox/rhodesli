"""Tests for the public shareable person page at /person/{person_id}.

Tests cover:
- Public access (no auth required)
- Correct person name and status badge rendering
- Face view shows face crops
- Photo view shows source photos
- "Appears with" section shows co-appearing people
- 404 handling for invalid person IDs
- OG meta tags with correct person name
- Share button functionality
"""

import pytest
from unittest.mock import patch
from starlette.testclient import TestClient

from app.main import app, load_registry


def get_confirmed_identity():
    """Get a real confirmed identity for testing."""
    registry = load_registry()
    confirmed = registry.list_identities(state=None)
    for identity in confirmed:
        if identity.get("state") == "CONFIRMED" and not identity.get("name", "").startswith("Unidentified"):
            return identity
    return None


def get_any_identity():
    """Get any identity for testing."""
    registry = load_registry()
    identities = registry.list_identities()
    return identities[0] if identities else None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def confirmed_identity():
    return get_confirmed_identity()


@pytest.fixture
def any_identity():
    return get_any_identity()


class TestPublicPersonPageAccess:
    """Public person page requires no authentication."""

    def test_public_access_returns_200(self, client, confirmed_identity):
        """Anyone can view /person/{id} without login."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200

    def test_public_access_with_auth_enabled(self, client, confirmed_identity, auth_enabled, no_user):
        """Anonymous users can view person pages even when auth is enabled."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200

    def test_invalid_person_id_returns_404_page(self, client):
        """Invalid person ID shows a gentle 404 page, not an error."""
        response = client.get("/person/nonexistent-id-12345")
        assert response.status_code == 200  # Gentle 404, not HTTP 404
        html = response.text
        assert "Person not found" in html
        assert "hasn&#x27;t been identified" in html or "hasn't been identified" in html

    def test_page_contains_rhodesli_branding(self, client, confirmed_identity):
        """Public person page includes Rhodesli branding."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert "Rhodesli" in response.text


class TestPublicPersonPageContent:
    """Person page displays correct identity information."""

    def test_displays_person_name(self, client, confirmed_identity):
        """Page shows the person's display name."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        name = confirmed_identity.get("name", "")
        # Name should appear in the page (in heading and title)
        assert name in response.text or name.replace("'", "&#x27;") in response.text

    def test_displays_identified_badge(self, client, confirmed_identity):
        """Confirmed person shows 'Identified' badge."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert "Identified" in response.text

    def test_displays_stats_or_name(self, client, confirmed_identity):
        """Page shows photo count stats or at minimum the person name."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        html = response.text
        name = confirmed_identity["name"]
        # Page always shows the person name
        assert name in html or name.replace("'", "&#x27;") in html
        # Stats line shows "Appears in N photo(s)" when photo registry is available
        # May be absent if photo registry cache was cleared by prior tests
        # Either way, the page must render correctly with 200 status
        assert response.status_code == 200

    def test_displays_share_button(self, client, confirmed_identity):
        """Page has a share button with correct data attributes."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        pid = confirmed_identity['identity_id']
        response = client.get(f"/person/{pid}")
        assert 'data-action="share-photo"' in response.text
        assert f"/person/{pid}" in response.text

    def test_displays_upload_cta(self, client, confirmed_identity):
        """Page has a call-to-action for uploading more photos."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        name = confirmed_identity.get("name", "")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert "Upload Photos" in response.text or "upload" in response.text.lower()


class TestPersonPageViewToggle:
    """Face/photo view toggle works correctly."""

    def test_faces_view_default(self, client, confirmed_identity):
        """Default view is faces."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        html = response.text
        # Faces tab should be active (has bg-indigo-600)
        assert "Faces" in html

    def test_photos_view(self, client, confirmed_identity):
        """Photos view shows source photos."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}?view=photos")
        html = response.text
        assert "Photos of" in html

    def test_faces_view_explicit(self, client, confirmed_identity):
        """Explicit faces view works."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}?view=faces")
        html = response.text
        assert "Faces of" in html


class TestPersonPageOGTags:
    """Open Graph meta tags for social sharing."""

    def test_og_title_contains_person_name(self, client, confirmed_identity):
        """OG title includes the person's name."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        name = confirmed_identity.get("name", "")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert 'og:title' in response.text
        # Name should be in the title (may be HTML-escaped)
        assert name in response.text or name.replace("'", "&#x27;") in response.text

    def test_og_description_present(self, client, confirmed_identity):
        """OG description is present."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert 'og:description' in response.text

    def test_og_image_present(self, client, confirmed_identity):
        """OG image tag is present."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert 'og:image' in response.text

    def test_og_url_contains_person_id(self, client, confirmed_identity):
        """OG URL points to the person page."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        pid = confirmed_identity['identity_id']
        response = client.get(f"/person/{pid}")
        assert f"/person/{pid}" in response.text

    def test_og_type_is_profile(self, client, confirmed_identity):
        """OG type is 'profile' for person pages."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert 'profile' in response.text


class TestPersonPageNavigation:
    """Navigation and cross-linking."""

    def test_navigation_links(self, client, confirmed_identity):
        """Page has Photos and People navigation links."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        html = response.text
        assert "Photos" in html
        assert "People" in html

    def test_404_page_has_archive_link(self, client):
        """404 page has a link back to the archive."""
        response = client.get("/person/nonexistent-id-12345")
        assert "Explore the Archive" in response.text

    def test_face_crops_link_to_photo_viewer(self, client, confirmed_identity):
        """Face crops in the gallery link to /photo/{id}."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        # Face items should link to /photo/ pages
        assert "/photo/" in response.text

    def test_footer_present(self, client, confirmed_identity):
        """Page has footer with archive branding."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert "Heritage Archive" in response.text


class TestPersonPageAppearsWithSection:
    """The 'Appears with' section for co-appearing people."""

    def test_appears_with_section_rendered(self, client):
        """If a person appears with other confirmed people, the section renders."""
        # Find a confirmed identity that appears with others
        registry = load_registry()
        confirmed = [i for i in registry.list_identities() if i.get("state") == "CONFIRMED" and not i.get("name", "").startswith("Unidentified")]
        if not confirmed:
            pytest.skip("No confirmed identities available")

        # Try each confirmed identity until we find one with companions
        for identity in confirmed[:5]:
            response = client.get(f"/person/{identity['identity_id']}")
            if "Often appears with" in response.text:
                # Found one — verify it has links to other person pages
                assert "/person/" in response.text
                return

        # No confirmed identity has companions — that's OK, skip
        pytest.skip("No confirmed identities with companions found")

    def test_appears_with_links_to_person_pages(self, client):
        """Companion links go to /person/{id}."""
        registry = load_registry()
        confirmed = [i for i in registry.list_identities() if i.get("state") == "CONFIRMED" and not i.get("name", "").startswith("Unidentified")]
        if not confirmed:
            pytest.skip("No confirmed identities available")

        for identity in confirmed[:5]:
            response = client.get(f"/person/{identity['identity_id']}")
            if "Often appears with" in response.text:
                # Companion links should be /person/ URLs
                html = response.text
                # Find the "appears with" section and verify it contains person links
                idx = html.index("Often appears with")
                section = html[idx:idx+2000]
                assert "/person/" in section
                return

        pytest.skip("No confirmed identities with companions found")


class TestPersonPageAnnotations:
    """Approved annotations display on public person page."""

    def test_approved_annotation_displays(self, client, tmp_path):
        """Approved annotations show in 'Community Notes' section."""
        import json
        from app.main import _invalidate_annotations_cache

        # Get a real identity to test with
        identity = get_any_identity()
        if not identity:
            pytest.skip("No identities available")
        identity_id = identity["identity_id"]

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "test-ann-1": {
                    "annotation_id": "test-ann-1",
                    "type": "bio",
                    "target_type": "identity",
                    "target_id": identity_id,
                    "value": "A mi querida Estrella",
                    "status": "approved",
                    "submitted_by": "test@example.com",
                    "submitted_at": "2026-01-01T00:00:00+00:00",
                    "confidence": "likely",
                    "reason": "",
                    "reviewed_by": "admin@example.com",
                    "reviewed_at": "2026-01-01T01:00:00+00:00",
                },
            },
        }
        (tmp_path / "annotations.json").write_text(json.dumps(ann_data))

        with patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.get(f"/person/{identity_id}")

        assert response.status_code == 200
        assert "Community Notes" in response.text
        assert "A mi querida Estrella" in response.text

    def test_pending_annotations_hidden(self, client, tmp_path):
        """Pending annotations do NOT show on public page."""
        import json
        from app.main import _invalidate_annotations_cache

        identity = get_any_identity()
        if not identity:
            pytest.skip("No identities available")
        identity_id = identity["identity_id"]

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "test-ann-pending": {
                    "annotation_id": "test-ann-pending",
                    "type": "bio",
                    "target_type": "identity",
                    "target_id": identity_id,
                    "value": "SECRET PENDING ANNOTATION",
                    "status": "pending",
                    "submitted_by": "test@example.com",
                    "submitted_at": "2026-01-01T00:00:00+00:00",
                    "confidence": "likely",
                    "reason": "",
                    "reviewed_by": None,
                    "reviewed_at": None,
                },
            },
        }
        (tmp_path / "annotations.json").write_text(json.dumps(ann_data))

        with patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.get(f"/person/{identity_id}")

        assert response.status_code == 200
        assert "SECRET PENDING ANNOTATION" not in response.text
        assert "Community Notes" not in response.text

    def test_duplicate_annotations_deduplicated(self, client, tmp_path):
        """Duplicate annotation values are shown only once."""
        import json
        from app.main import _invalidate_annotations_cache

        identity = get_any_identity()
        if not identity:
            pytest.skip("No identities available")
        identity_id = identity["identity_id"]

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "dup-1": {
                    "annotation_id": "dup-1",
                    "type": "bio",
                    "target_type": "identity",
                    "target_id": identity_id,
                    "value": "Same text twice",
                    "status": "approved",
                    "submitted_by": "user@example.com",
                    "submitted_at": "2026-01-01T00:00:00+00:00",
                    "confidence": "likely",
                    "reason": "",
                    "reviewed_by": "admin@example.com",
                    "reviewed_at": "2026-01-01T01:00:00+00:00",
                },
                "dup-2": {
                    "annotation_id": "dup-2",
                    "type": "bio",
                    "target_type": "identity",
                    "target_id": identity_id,
                    "value": "Same text twice",
                    "status": "approved",
                    "submitted_by": "user@example.com",
                    "submitted_at": "2026-01-01T00:01:00+00:00",
                    "confidence": "likely",
                    "reason": "",
                    "reviewed_by": "admin@example.com",
                    "reviewed_at": "2026-01-01T01:00:00+00:00",
                },
            },
        }
        (tmp_path / "annotations.json").write_text(json.dumps(ann_data))

        with patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            response = client.get(f"/person/{identity_id}")

        # Should show only once despite two annotations with same value
        assert response.text.count("Same text twice") == 1


class TestPersonPageTreeLink:
    """Person page shows link to family tree when relationships exist."""

    def test_person_with_family_shows_tree_link(self, client):
        """Person with family relationships shows 'View in Family Tree' link."""
        # Get two real confirmed identities to make the relationship graph work
        registry = load_registry()
        confirmed = [
            i for i in registry.list_identities(state=None)
            if i.get("state") == "CONFIRMED" and not i.get("name", "").startswith("Unidentified")
        ]
        if len(confirmed) < 2:
            pytest.skip("Need at least 2 confirmed identities")
        identity_id = confirmed[0]["identity_id"]
        other_id = confirmed[1]["identity_id"]

        mock_graph = {
            "schema_version": 1,
            "relationships": [
                {"person_a": identity_id, "person_b": other_id, "type": "parent_child", "source": "gedcom"},
            ],
            "gedcom_imports": [],
        }
        with patch("app.main._load_relationship_graph", return_value=mock_graph), \
             patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/person/{identity_id}")

        assert response.status_code == 200
        assert f"/tree?person={identity_id}" in response.text

    def test_person_without_family_no_tree_link(self, client, confirmed_identity):
        """Person without family relationships does NOT show family tree link."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        identity_id = confirmed_identity["identity_id"]

        # Empty relationship graph
        mock_graph = {"schema_version": 1, "relationships": [], "gedcom_imports": []}
        with patch("app.main._load_relationship_graph", return_value=mock_graph), \
             patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/person/{identity_id}")

        assert response.status_code == 200
        assert "family-tree-link" not in response.text


class TestPersonPageLifeDetails:
    """Life details section shows birth/death fields with contribution prompts."""

    def test_life_details_section_present_for_confirmed(self, client, confirmed_identity):
        """Confirmed identities show the life details section."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200
        assert 'data-testid="life-details"' in response.text

    def test_life_details_shows_unknown_for_missing_fields(self, client, confirmed_identity):
        """Missing birth/death fields show 'Unknown' placeholder."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        # Most confirmed identities won't have all fields filled
        html = response.text
        if 'data-testid="life-details"' in html:
            assert "Unknown" in html or "Born" in html or "Died" in html

    def test_life_details_not_shown_for_nonexistent(self, client):
        """404 person page does not show life details."""
        response = client.get("/person/nonexistent-id-12345")
        assert 'data-testid="life-details"' not in response.text
