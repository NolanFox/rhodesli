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


def get_confirmed_identity(registry):
    """Get a real confirmed identity for testing."""
    confirmed = registry.list_identities(state=None)
    for identity in confirmed:
        if identity.get("state") == "CONFIRMED" and not identity.get("name", "").startswith("Unidentified"):
            return identity
    return None


def get_any_identity(registry):
    """Get any identity for testing."""
    identities = registry.list_identities()
    return identities[0] if identities else None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def registry_snapshot(monkeypatch):
    registry = load_registry()
    monkeypatch.setattr("app.main.load_registry", lambda: registry)
    return registry


@pytest.fixture
def confirmed_identity(registry_snapshot):
    return get_confirmed_identity(registry_snapshot)


@pytest.fixture
def any_identity(registry_snapshot):
    return get_any_identity(registry_snapshot)


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
        """Invalid person ID returns HTTP 404 with a friendly page."""
        response = client.get("/person/nonexistent-id-12345")
        assert response.status_code == 404
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

    def test_displays_confirmed_badge(self, client, confirmed_identity):
        """Confirmed person shows 'Identified' badge (FB-113: changed from 'Confirmed')."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        # FB-113: CONFIRMED state now shows "Identified" in public view
        assert "Identified" in response.text or "Confirmed" in response.text

    def test_displays_share_button(self, client, confirmed_identity):
        """Page has a share button with correct data attributes."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        pid = confirmed_identity["identity_id"]
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


class TestPersonPageOrdering:
    """Ordering controls for person page galleries."""

    def _mock_person_data(self, monkeypatch):
        class FakeRegistry:
            def get_identity(self, person_id):
                return {
                    "identity_id": person_id,
                    "name": "Test Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-a", "face-b", "face-c"],
                    "candidate_ids": [],
                }

        class FakePhotoRegistry:
            def get_photos_for_faces(self, _face_ids):
                return ["photo-1", "photo-2", "photo-3"]

        photo_meta = {
            "photo-1": {
                "photo_id": "photo-1",
                "filename": "photo-1.jpg",
                "collection": "C1",
                "created_at": "2025-01-01T00:00:00+00:00",
            },
            "photo-2": {
                "photo_id": "photo-2",
                "filename": "photo-2.jpg",
                "collection": "C1",
                "created_at": "2023-01-01T00:00:00+00:00",
            },
            "photo-3": {
                "photo_id": "photo-3",
                "filename": "photo-3.jpg",
                "collection": "C1",
                "created_at": "2024-01-01T00:00:00+00:00",
            },
        }
        face_to_photo = {"face-a": "photo-1", "face-b": "photo-2", "face-c": "photo-3"}

        monkeypatch.setattr("app.main.load_registry", lambda: FakeRegistry())
        monkeypatch.setattr("app.main.load_photo_registry", lambda: FakePhotoRegistry())
        monkeypatch.setattr("app.main.get_photo_metadata", lambda pid: photo_meta.get(pid))
        monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-a.jpg", "face-b.jpg", "face-c.jpg"})
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda fid, _crops: f"/crops/{fid}.jpg" if fid else None)
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda fid: face_to_photo.get(fid))
        monkeypatch.setattr("app.main.get_best_face_id", lambda all_faces: all_faces[0] if all_faces else None)
        monkeypatch.setattr(
            "app.main._load_date_labels",
            lambda: {
                "photo-1": {"best_year_estimate": 1940},
                "photo-2": {"best_year_estimate": 1960},
                "photo-3": {"best_year_estimate": 1950},
            },
        )

    def test_default_order_uses_earliest_first(self, client, monkeypatch):
        self._mock_person_data(monkeypatch)
        response = client.get("/person/test-person?view=photos")
        html = response.text
        assert html.index("/photo/photo-1") < html.index("/photo/photo-3") < html.index("/photo/photo-2")

    def test_uploaded_sort_orders_by_created_at(self, client, monkeypatch):
        self._mock_person_data(monkeypatch)
        response = client.get("/person/test-person?view=photos&sort_by=uploaded_desc")
        html = response.text
        assert html.index("/photo/photo-1") < html.index("/photo/photo-3") < html.index("/photo/photo-2")
        assert "Newest Uploads" in html

    def test_faces_toggle_preserves_sort_choice(self, client, monkeypatch):
        self._mock_person_data(monkeypatch)
        response = client.get("/person/test-person?view=faces&sort_by=date_desc")
        html = response.text
        assert "view=photos&amp;sort_by=date_desc" in html
        assert "Earliest Last" in html

    def test_community_photo_links_preserve_person_context(self, client, monkeypatch):
        self._mock_person_data(monkeypatch)
        with patch(
            "app.supabase_data.get_community_by_slug",
            return_value={"slug": "fox-family", "name": "Fox Family Archive"},
        ):
            response = client.get("/c/fox-family/person/test-person?view=photos&sort_by=date_asc")
        html = response.text
        assert "/c/fox-family/photo/photo-1?identity_id=test-person&amp;sort_by=date_asc" in html

    def test_person_gallery_exposes_speed_loop_entry(self, client, monkeypatch, auth_disabled):
        del auth_disabled

        class FakeRegistry:
            def get_identity(self, person_id):
                return {
                    "identity_id": person_id,
                    "name": "Roland Fox",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-a", "face-b"],
                    "candidate_ids": [],
                }

        class FakePhotoRegistry:
            def get_photos_for_faces(self, _face_ids):
                return ["photo-1", "photo-2"]

        photo_meta = {
            "photo-1": {
                "photo_id": "photo-1",
                "filename": "photo-1.jpg",
                "collection": "C1",
                "created_at": "2025-01-01T00:00:00+00:00",
                "faces": [{"face_id": "face-a", "bbox": [0, 0, 50, 50]}],
            },
            "photo-2": {
                "photo_id": "photo-2",
                "filename": "photo-2.jpg",
                "collection": "C1",
                "created_at": "2024-01-01T00:00:00+00:00",
                "faces": [{"face_id": "face-b", "bbox": [0, 0, 50, 50]}],
            },
        }
        face_to_photo = {"face-a": "photo-1", "face-b": "photo-2"}

        monkeypatch.setattr("app.main.load_registry", lambda: FakeRegistry())
        monkeypatch.setattr("app.main.load_photo_registry", lambda: FakePhotoRegistry())
        monkeypatch.setattr("app.main.get_photo_metadata", lambda pid: photo_meta.get(pid))
        monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-a.jpg", "face-b.jpg"})
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda fid, _crops: f"/crops/{fid}.jpg" if fid else None)
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda fid: face_to_photo.get(fid))
        monkeypatch.setattr("app.main.get_best_face_id", lambda all_faces: all_faces[0] if all_faces else None)
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})
        monkeypatch.setattr(
            "app.main.get_identity_for_face",
            lambda _registry, _face_id: {
                "identity_id": "unknown-1",
                "name": "Unidentified Person 1",
                "state": "INBOX",
            },
        )

        response = client.get("/api/person/test-person/gallery?view=photos&sort_by=date_asc")
        assert response.status_code == 200
        html = response.text

        assert "Start Speed Loop" in html
        assert 'data-testid="person-speed-loop"' in html
        assert "/photo/photo-1" in html
        assert "identity_id=test-person" in html
        assert "sort_by=date_asc" in html
        assert "seq=1" in html

    def test_person_gallery_flags_conflicted_photo_context(self, client, monkeypatch, auth_disabled):
        # auth_disabled: the "Needs review"/conflict flag is admin-only (Session 165);
        # CI enables auth so the client is non-admin and the flag is hidden (Lesson 181).
        class FakeRegistry:
            def get_identity(self, person_id):
                return {
                    "identity_id": person_id,
                    "name": "Jacob Cohen",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-a"],
                    "candidate_ids": [],
                }

        class FakePhotoRegistry:
            def get_photos_for_faces(self, _face_ids):
                return ["photo-1"]

        photo_meta = {
            "photo-1": {
                "photo_id": "photo-1",
                "filename": "photo-1.jpg",
                "collection": "Franco Family",
                "created_at": "2025-01-01T00:00:00+00:00",
                "faces": [
                    {"face_id": "face-a", "bbox": [100, 100, 200, 240]},
                    {"face_id": "face-b", "bbox": [108, 108, 198, 235]},
                ],
            }
        }
        face_to_photo = {"face-a": "photo-1"}

        monkeypatch.setattr("app.main.load_registry", lambda: FakeRegistry())
        monkeypatch.setattr("app.main.load_photo_registry", lambda: FakePhotoRegistry())
        monkeypatch.setattr("app.main.get_photo_metadata", lambda pid: photo_meta.get(pid))
        monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-a.jpg"})
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda fid, _crops: f"/crops/{fid}.jpg" if fid else None)
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda fid: face_to_photo.get(fid))
        monkeypatch.setattr("app.main.get_best_face_id", lambda all_faces: all_faces[0] if all_faces else None)
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})

        def _identity_for_face(_registry, face_id):
            if face_id == "face-a":
                return {"identity_id": "test-person", "name": "Jacob Cohen", "state": "CONFIRMED"}
            return {"identity_id": "other-person", "name": "Caden Franco Sadis", "state": "CONFIRMED"}

        monkeypatch.setattr("app.main.get_identity_for_face", _identity_for_face)

        response = client.get("/person/test-person?view=photos&sort_by=date_asc")
        assert response.status_code == 200
        html = response.text

        assert "Needs review" in html
        assert 'data-testid="person-gallery-conflict"' in html


class TestPersonPageOGTags:
    """Open Graph meta tags for social sharing."""

    def _render_mock_person_page(self, monkeypatch, tmp_path, avatar_url):
        """Render a mocked person page with a deterministic avatar URL."""
        from fastcore.xml import to_xml

        from app.person_routes import public_person_page

        person_id = "person-og-test"
        identity = {
            "identity_id": person_id,
            "name": "OG Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-og-1"],
            "candidate_ids": [],
            "negative_ids": [],
            "metadata": {},
        }

        class FakeRegistry:
            def get_identity(self, requested_id):
                if requested_id == person_id:
                    return identity
                raise KeyError(requested_id)

            def list_identities(self, state=None):
                return [identity]

        class FakePhotoRegistry:
            def get_photos_for_faces(self, _face_ids):
                return ["photo-og-1"]

        photo_meta = {
            "photo_id": "photo-og-1",
            "filename": "photo-og-1.jpg",
            "collection": "OG Test Collection",
            "created_at": "2026-01-01T00:00:00+00:00",
            "faces": [{"face_id": "face-og-1", "bbox": [0, 0, 50, 50]}],
        }

        monkeypatch.setattr("app.main.data_path", tmp_path)
        monkeypatch.setattr("app.main.load_registry", lambda: FakeRegistry())
        monkeypatch.setattr("app.main.load_photo_registry", lambda: FakePhotoRegistry())
        monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-og-1.jpg"})
        monkeypatch.setattr("app.main.get_best_face_id", lambda _face_ids: "face-og-1")
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda _face_id, _crops: avatar_url)
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda _face_id: "photo-og-1")
        monkeypatch.setattr("app.main.get_photo_metadata", lambda _photo_id: photo_meta)
        monkeypatch.setattr("app.main.get_identity_for_face", lambda _registry, _face_id: identity)
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})
        monkeypatch.setattr("app.main._load_relationship_graph", lambda: {"relationships": []})
        monkeypatch.setattr("app.main._load_annotations", lambda: {"annotations": {}})
        monkeypatch.setattr("app.main._get_birth_year", lambda *_args, **_kwargs: (None, None, None))
        monkeypatch.setattr("app.main._public_nav_links", lambda **_kwargs: [])
        monkeypatch.setattr("app.main._admin_bar", lambda *_args, **_kwargs: None)
        monkeypatch.setattr("app.main._place_datalist", lambda: None)
        monkeypatch.setattr("app.main._share_script", lambda: None)
        monkeypatch.setattr("app.main.compare_modal", lambda: None)
        monkeypatch.setattr("app.main.confirm_modal", lambda: None)
        monkeypatch.setattr("app.main.login_modal", lambda: None)
        monkeypatch.setattr("app.main.toast_container", lambda: None)
        monkeypatch.setattr("app.person_routes._life_events_section", lambda *_args, **_kwargs: None)
        monkeypatch.setattr("app.person_routes._person_comments_section", lambda *_args, **_kwargs: None)

        return to_xml(public_person_page(person_id, is_admin=False))

    def test_og_title_contains_person_name(self, client, confirmed_identity):
        """OG title includes the person's name."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        name = confirmed_identity.get("name", "")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert "og:title" in response.text
        # Name should be in the title (may be HTML-escaped)
        assert name in response.text or name.replace("'", "&#x27;") in response.text

    def test_og_description_present(self, client, confirmed_identity):
        """OG description is present."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert "og:description" in response.text

    def test_og_image_never_emitted_empty(self, client, confirmed_identity):
        """G8: og:image/twitter:image are CONDITIONAL — present with a real URL when an
        avatar resolves, omitted otherwise, but NEVER emitted with empty content (an empty
        og:image makes FB skip image selection). This invariant holds in every environment
        (CI may lack crop data → no avatar → tags omitted, which is correct). Deterministic
        avatar-present / avatar-absent coverage lives in the mocked _render_mock_person_page tests.
        """
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert 'property="og:image" content=""' not in response.text
        assert 'name="twitter:image" content=""' not in response.text

    def test_og_url_contains_person_id(self, client, confirmed_identity):
        """OG URL points to the person page."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        pid = confirmed_identity["identity_id"]
        response = client.get(f"/person/{pid}")
        assert f"/person/{pid}" in response.text

    def test_avatar_person_og_image_uses_large_twitter_card(self, monkeypatch, tmp_path):
        """Person page with an avatar emits image tags and a large Twitter card."""
        html = self._render_mock_person_page(monkeypatch, tmp_path, "/static/crops/face-og-1.jpg")

        assert (
            'property="og:image" content="https://rhodesli.nolanandrewfox.com/static/crops/face-og-1.jpg"'
            in html
        )
        assert (
            'name="twitter:image" content="https://rhodesli.nolanandrewfox.com/static/crops/face-og-1.jpg"' in html
        )
        assert 'name="twitter:card" content="summary_large_image"' in html

    def test_person_without_avatar_omits_image_tags_and_uses_summary_card(self, monkeypatch, tmp_path):
        """Person page without an avatar omits empty image tags so crawlers can fall back."""
        html = self._render_mock_person_page(monkeypatch, tmp_path, "")

        assert 'property="og:image"' not in html
        assert 'name="twitter:image"' not in html
        assert 'name="twitter:card" content="summary"' in html


class TestPersonPhotoGalleryShareRoute:
    """PRD-065 / FB-004 — dedicated shareable person-photo gallery."""

    def test_photos_route_returns_200(self, client, confirmed_identity):
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        pid = confirmed_identity["identity_id"]
        response = client.get(f"/person/{pid}/photos")
        assert response.status_code == 200

    def test_photos_route_og_title_is_photos_of(self, client, confirmed_identity):
        """The dedicated gallery reframes OG/title as 'Photos of <Name>'."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        pid = confirmed_identity["identity_id"]
        response = client.get(f"/person/{pid}/photos")
        assert "Photos of" in response.text
        assert "og:title" in response.text

    def test_photos_route_og_url_points_to_photos_path(self, client, confirmed_identity):
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        pid = confirmed_identity["identity_id"]
        response = client.get(f"/person/{pid}/photos")
        assert f"/person/{pid}/photos" in response.text

    def test_person_page_share_button_targets_photos_link(self, client, confirmed_identity):
        """The person page Share button points at the unambiguous /photos link."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        pid = confirmed_identity["identity_id"]
        response = client.get(f"/person/{pid}")
        # Share button data-share-url is the person-photos gallery link.
        assert f"/person/{pid}/photos" in response.text

    def test_photos_route_invalid_id_404(self, client):
        response = client.get("/person/nonexistent-person-xyz/photos")
        assert response.status_code == 404

    def test_anonymous_gallery_hides_review_language(
        self, client, confirmed_identity, monkeypatch, auth_enabled, no_user
    ):
        """Codex P2 (Session 165): the public shareable gallery must NEVER show
        admin review language ('Needs review' / 'Conflicting face assignment'),
        even when a photo's face context conflicts. Force every card conflicted."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        import app.person_routes as pr

        monkeypatch.setattr(pr, "_photo_context_conflict", lambda *a, **k: True)
        pid = confirmed_identity["identity_id"]
        response = client.get(f"/person/{pid}/photos")
        assert response.status_code == 200
        assert "Needs review" not in response.text
        assert "Conflicting face assignment" not in response.text

    def test_admin_gallery_shows_review_language_when_conflicted(
        self, client, confirmed_identity, monkeypatch, auth_disabled
    ):
        """Admin counterpart: with auth disabled (admin) and a forced conflict on
        a person who has gallery items, the review badge IS rendered."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        import app.person_routes as pr

        monkeypatch.setattr(pr, "_photo_context_conflict", lambda *a, **k: True)
        pid = confirmed_identity["identity_id"]
        response = client.get(f"/person/{pid}/photos")
        assert response.status_code == 200
        # If the person has any gallery cards, the admin badge appears. If the
        # person has no photos/faces, neither branch renders — that's acceptable.
        if 'data-testid="person-gallery-item' in response.text:
            assert "Needs review" in response.text


class TestPersonPageAppearsWithSection:
    """The 'Appears with' section for co-appearing people."""

    def _mock_person_with_companions(self, monkeypatch):
        """Set up mocked data so person-A co-appears with person-B in a shared photo."""
        identities = {
            "person-A": {
                "identity_id": "person-A",
                "name": "Test Person A",
                "state": "CONFIRMED",
                "anchor_ids": ["face-a1"],
                "candidate_ids": [],
            },
            "person-B": {
                "identity_id": "person-B",
                "name": "Companion Person B",
                "state": "CONFIRMED",
                "anchor_ids": ["face-b1"],
                "candidate_ids": [],
            },
        }

        class FakeRegistry:
            def get_identity(self, pid):
                if pid in identities:
                    return identities[pid]
                raise KeyError(pid)

            def list_identities(self, state=None):
                return list(identities.values())

        class FakePhotoRegistry:
            def get_photos_for_faces(self, _face_ids):
                return ["photo-shared"]

        photo_meta = {
            "photo-shared": {
                "photo_id": "photo-shared",
                "filename": "shared.jpg",
                "collection": "Test Collection",
                "created_at": "2025-01-01T00:00:00+00:00",
                "faces": [
                    {"face_id": "face-a1", "bbox": [10, 10, 50, 50]},
                    {"face_id": "face-b1", "bbox": [60, 10, 100, 50]},
                ],
                "face_ids": ["face-a1", "face-b1"],
            },
        }
        face_to_identity = {"face-a1": identities["person-A"], "face-b1": identities["person-B"]}

        monkeypatch.setattr("app.main.load_registry", lambda: FakeRegistry())
        monkeypatch.setattr("app.main.load_photo_registry", lambda: FakePhotoRegistry())
        monkeypatch.setattr("app.main.get_photo_metadata", lambda pid: photo_meta.get(pid))
        monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-a1.jpg", "face-b1.jpg"})
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda fid, _crops: f"/crops/{fid}.jpg" if fid else None)
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda fid: "photo-shared")
        monkeypatch.setattr("app.main.get_best_face_id", lambda faces: faces[0] if faces else None)
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})
        monkeypatch.setattr(
            "app.main.get_identity_for_face",
            lambda _reg, fid: face_to_identity.get(fid),
        )

    def test_appears_with_section_rendered(self, client, monkeypatch):
        """If a person appears with other confirmed people, the section renders."""
        self._mock_person_with_companions(monkeypatch)
        response = client.get("/person/person-A")
        assert response.status_code == 200
        assert "Often appears with" in response.text
        assert "/person/" in response.text

    def test_appears_with_links_to_person_pages(self, client, monkeypatch):
        """Companion links go to /person/{id}."""
        self._mock_person_with_companions(monkeypatch)
        response = client.get("/person/person-A")
        html = response.text
        idx = html.index("Often appears with")
        section = html[idx : idx + 2000]
        assert "/person/person-B" in section


class TestPersonPageAnnotations:
    """Approved annotations display on public person page."""

    def test_approved_annotation_displays(self, client, tmp_path, any_identity):
        """Approved annotations show in 'Community Notes' section."""
        import json
        from app.main import _invalidate_annotations_cache

        identity = any_identity
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

    def test_pending_annotations_hidden(self, client, tmp_path, any_identity):
        """Pending annotations do NOT show on public page."""
        import json
        from app.main import _invalidate_annotations_cache

        identity = any_identity
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

    def test_duplicate_annotations_deduplicated(self, client, tmp_path, any_identity):
        """Duplicate annotation values are shown only once."""
        import json
        from app.main import _invalidate_annotations_cache

        identity = any_identity
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

    def test_person_with_family_shows_tree_link(self, client, registry_snapshot):
        """Person with family relationships shows 'View in Family Tree' link."""
        # Get two real confirmed identities to make the relationship graph work
        confirmed = [
            i
            for i in registry_snapshot.list_identities(state=None)
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
        with (
            patch("app.main._load_relationship_graph", return_value=mock_graph),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
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
        with (
            patch("app.main._load_relationship_graph", return_value=mock_graph),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
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

    def test_life_details_shows_unknown_for_missing_fields(self, client, confirmed_identity, auth_disabled):
        """Missing birth/death fields show 'Unknown' placeholder (admin view; public hides Unknown — Lesson 181)."""
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


class TestPersonMetadataEdit:
    """Admin inline metadata editing on person page."""

    def test_admin_sees_metadata_edit(self, client, confirmed_identity, auth_disabled):
        """Admin (auth disabled) sees metadata edit form for confirmed person."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200
        assert 'data-testid="person-metadata-edit"' in response.text

    def test_metadata_edit_has_birth_year(self, client, confirmed_identity, auth_disabled):
        """Metadata edit form has birth year input."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert 'name="birth_year"' in response.text

    def test_metadata_edit_has_birth_place(self, client, confirmed_identity, auth_disabled):
        """Metadata edit form has birth place input with datalist."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert 'name="birth_place"' in response.text
        assert 'list="places-list"' in response.text

    def test_anonymous_no_metadata_edit(self, client, confirmed_identity, auth_enabled, no_user):
        """Anonymous users do not see metadata edit form."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200
        assert 'data-testid="person-metadata-edit"' not in response.text


class TestMergedIdentityRedirect:
    """UX-038: Visiting a merged person's URL redirects to the canonical identity."""

    def test_merged_person_redirects_to_canonical(self, client, registry_snapshot):
        """Visiting /person/{merged_id} returns 301 to canonical person."""
        all_ids = registry_snapshot.list_identities()
        merged = [i for i in all_ids if i.get("merged_into")]
        if not merged:
            pytest.skip("No merged identities in test data")
        merged_id = merged[0]["identity_id"]
        canonical_id = merged[0]["merged_into"]
        response = client.get(f"/person/{merged_id}", follow_redirects=False)
        assert response.status_code == 301
        assert f"/person/{canonical_id}" in response.headers.get("location", "")

    def test_merged_person_redirect_follow(self, client, registry_snapshot):
        """Following the redirect from a merged person shows the canonical page."""
        all_ids = registry_snapshot.list_identities()
        merged = [i for i in all_ids if i.get("merged_into")]
        if not merged:
            pytest.skip("No merged identities in test data")
        merged_id = merged[0]["identity_id"]
        response = client.get(f"/person/{merged_id}", follow_redirects=True)
        assert response.status_code == 200


class TestAdminControlsOnPersonPage:
    """UX-039: Admin controls visible on /person/ page for admins."""

    def test_admin_sees_controls(self, client, confirmed_identity, auth_disabled):
        """Admin user sees admin action buttons on person page."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200
        assert 'data-testid="admin-controls"' in response.text
        assert "Edit in Admin" in response.text
        assert "Find Similar" in response.text
        assert 'data-testid="person-similar-container"' in response.text

    def test_admin_confirmed_person_has_gedcom_shortcut(self, client, confirmed_identity, auth_disabled):
        """Confirmed admin person page exposes a direct shortcut to the GEDCOM section."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        with patch("app.main._load_gedcom_face_links", return_value={}):
            response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200
        assert 'data-testid="jump-to-gedcom-link"' in response.text
        assert "Needs Tree Link" in response.text
        assert 'href="#gedcom"' in response.text

    def test_admin_linked_person_shows_tree_linked_shortcut(self, client, confirmed_identity, auth_disabled):
        """Linked confirmed admin person page surfaces the linked-state shortcut."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        linked = {confirmed_identity["identity_id"]: {"gedcom_id": "@I1@"}}
        with patch("app.main._load_gedcom_face_links", return_value=linked):
            response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200
        assert "Tree Linked" in response.text

    def test_anonymous_no_admin_controls(self, client, confirmed_identity, auth_enabled, no_user):
        """Anonymous users do NOT see admin controls."""
        if not confirmed_identity:
            pytest.skip("No confirmed identities available")
        response = client.get(f"/person/{confirmed_identity['identity_id']}")
        assert response.status_code == 200
        assert 'data-testid="admin-controls"' not in response.text

    def test_community_admin_find_similar_panel_stays_in_community(self, client, monkeypatch, auth_disabled):
        del auth_disabled

        class FakeRegistry:
            def get_identity(self, person_id):
                return {
                    "identity_id": person_id,
                    "name": "Roland Fox",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-a"],
                    "candidate_ids": [],
                }

        class FakePhotoRegistry:
            def get_photos_for_faces(self, _face_ids):
                return ["photo-1"]

        monkeypatch.setattr("app.main.load_registry", lambda: FakeRegistry())
        monkeypatch.setattr("app.main.load_photo_registry", lambda: FakePhotoRegistry())
        monkeypatch.setattr(
            "app.main.get_photo_metadata",
            lambda _pid: {"photo_id": "photo-1", "filename": "photo-1.jpg", "collection": "Fox", "faces": []},
        )
        monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-a.jpg"})
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda fid, _crops=None: f"/crops/{fid}.jpg")
        monkeypatch.setattr("app.main.get_best_face_id", lambda all_faces: all_faces[0] if all_faces else None)
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda _fid: "photo-1")
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})
        monkeypatch.setattr("app.main._get_proposal_targets_for_identity", lambda _iid: [{"face_id": "inbox-1"}])

        with patch(
            "app.supabase_data.get_community_by_slug",
            return_value={"slug": "fox-family", "name": "Fox Family Archive"},
        ):
            response = client.get("/c/fox-family/person/test-person")

        assert (
            "/c/fox-family/api/identity/test-person/neighbors?container_id=person-similar-test-person" in response.text
        )
        assert 'id="person-similar-test-person"' in response.text
        assert "/c/fox-family/admin/upload-review#identity-group-test-person" in response.text


class TestConfirmedBadgeRegardlessOfName:
    """FB-113: CONFIRMED identities should show Confirmed badge regardless of name."""

    def _mock_person(self, monkeypatch, name, state):
        class FakeRegistry:
            def get_identity(self, person_id):
                return {
                    "identity_id": person_id,
                    "name": name,
                    "state": state,
                    "anchor_ids": ["face-a"],
                    "candidate_ids": [],
                }

        class FakePhotoRegistry:
            def get_photos_for_faces(self, _face_ids):
                return ["photo-1"]

        photo_meta = {
            "photo-1": {
                "photo_id": "photo-1",
                "filename": "photo-1.jpg",
                "collection": "C1",
                "created_at": "2025-01-01T00:00:00+00:00",
            },
        }
        face_to_photo = {"face-a": "photo-1"}

        monkeypatch.setattr("app.main.load_registry", lambda: FakeRegistry())
        monkeypatch.setattr("app.main.load_photo_registry", lambda: FakePhotoRegistry())
        monkeypatch.setattr("app.main.get_photo_metadata", lambda pid: photo_meta.get(pid))
        monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-a.jpg"})
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda fid, _crops: f"/crops/{fid}.jpg" if fid else None)
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda fid: face_to_photo.get(fid))
        monkeypatch.setattr("app.main.get_best_face_id", lambda all_faces: all_faces[0] if all_faces else None)
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})

    def test_confirmed_unnamed_shows_identified_badge(self, client, monkeypatch):
        """CONFIRMED identity with 'Unidentified Person' name shows Identified badge, not Under Review (FB-113)."""
        self._mock_person(monkeypatch, "Unidentified Person 2986", "CONFIRMED")
        response = client.get("/person/test-person-unnamed")
        html = response.text
        assert "Identified" in html or "Confirmed" in html
        assert "Under Review" not in html

    def test_confirmed_named_shows_identified_badge(self, client, monkeypatch):
        """CONFIRMED identity with a real name shows Identified badge (FB-113 regression test)."""
        self._mock_person(monkeypatch, "Leon Capeluto", "CONFIRMED")
        response = client.get("/person/test-person-named")
        html = response.text
        assert "Identified" in html or "Confirmed" in html
        assert "Under Review" not in html
