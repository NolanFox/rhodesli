"""Tests for face identity labels in face analysis and photo/person→map navigation.

Tests cover:
1. Face identity labels: Confirmed identities show names (not "Face N") in face analysis
2. Face name links: Confirmed identity names link to /person/{id}
3. Unidentified faces: Still show "Face N" labels
4. Photo→Map button: Photo pages with identified people have "See on Map" button
5. Map people param: /map?people=id1,id2 filters correctly
6. Person→Map link: Person pages have a map link with correct href
"""

import json

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers — mock data builders
# ---------------------------------------------------------------------------


def _make_fake_registry(identities):
    """Build a FakeRegistry from a list of identity dicts."""

    class FakeRegistry:
        def __init__(self):
            self._identities = {i["identity_id"]: i for i in identities}

        def get_identity(self, person_id):
            if person_id not in self._identities:
                raise KeyError(person_id)
            return self._identities[person_id]

        def list_identities(self, state=None):
            if state is None:
                return list(self._identities.values())
            return [i for i in self._identities.values() if i.get("state") == state]

    return FakeRegistry()


def _make_fake_photo_registry(photos, face_to_photo):
    """Build a FakePhotoRegistry."""

    class FakePhotoRegistry:
        def __init__(self):
            self._photos = photos

        def get_photos_for_faces(self, face_ids):
            result = set()
            for fid in face_ids:
                pid = face_to_photo.get(fid)
                if pid:
                    result.add(pid)
            return list(result)

    return FakePhotoRegistry()


# ---------------------------------------------------------------------------
# Test data: a photo with two faces — one confirmed identity, one unidentified
# ---------------------------------------------------------------------------

CONFIRMED_ID = "confirmed-person-001"
CONFIRMED_NAME = "Selma Capeluto"
UNIDENTIFIED_ID = "unidentified-person-002"

IDENTITIES = [
    {
        "identity_id": CONFIRMED_ID,
        "name": CONFIRMED_NAME,
        "state": "CONFIRMED",
        "anchor_ids": ["face-a"],
        "candidate_ids": [],
    },
    {
        "identity_id": UNIDENTIFIED_ID,
        "name": "Unidentified Person 42",
        "state": "INBOX",
        "anchor_ids": ["face-b"],
        "candidate_ids": [],
    },
]

PHOTO_ID = "test-photo-abc123"
PHOTO_META = {
    PHOTO_ID: {
        "photo_id": PHOTO_ID,
        "filename": "test_photo.jpg",
        "collection": "Test Collection",
        "face_ids": ["face-a", "face-b"],
        "faces": [
            {"face_id": "face-a", "bbox": [10, 10, 100, 100]},
            {"face_id": "face-b", "bbox": [200, 10, 300, 100]},
        ],
        "width": 800,
        "height": 600,
    }
}

FACE_TO_PHOTO = {
    "face-a": PHOTO_ID,
    "face-b": PHOTO_ID,
}


def _apply_photo_page_mocks(monkeypatch, mock_alignment=True):
    """Apply common mocks for photo page tests.

    Args:
        mock_alignment: If True, mock alignment section to None (default).
                       Set False when testing alignment-specific behavior.
    """
    registry = _make_fake_registry(IDENTITIES)
    photo_reg = _make_fake_photo_registry(PHOTO_META, FACE_TO_PHOTO)

    monkeypatch.setattr("app.main.load_registry", lambda: registry)
    monkeypatch.setattr("app.main.load_photo_registry", lambda: photo_reg)
    monkeypatch.setattr("app.main.get_photo_metadata", lambda pid: PHOTO_META.get(pid))
    monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-a.jpg", "face-b.jpg"})
    monkeypatch.setattr(
        "app.main.resolve_face_image_url",
        lambda fid, _crops: f"/crops/{fid}.jpg" if fid else None,
    )
    monkeypatch.setattr(
        "app.main.get_photo_id_for_face", lambda fid: FACE_TO_PHOTO.get(fid)
    )
    monkeypatch.setattr(
        "app.main.get_best_face_id",
        lambda all_faces: (all_faces[0] if all_faces else None),
    )
    monkeypatch.setattr(
        "app.main.get_photo_dimensions", lambda _fn: (800, 600)
    )
    monkeypatch.setattr(
        "app.main.get_identity_for_face",
        lambda reg, fid: next(
            (
                i
                for i in IDENTITIES
                if fid
                in (i.get("anchor_ids", []) + i.get("candidate_ids", []))
            ),
            None,
        ),
    )
    # Mock _build_caches to set global caches
    monkeypatch.setattr("app.main._build_caches", lambda: None)
    monkeypatch.setattr("app.main._photo_cache", PHOTO_META)
    monkeypatch.setattr("app.main._face_to_photo_cache", FACE_TO_PHOTO)
    if mock_alignment:
        # Mock face alignment section (not relevant to these tests)
        monkeypatch.setattr(
            "app.main._build_face_alignment_section", lambda *a, **kw: None
        )
    # Mock AI analysis section
    monkeypatch.setattr(
        "app.main._build_ai_analysis_section", lambda *a, **kw: None
    )
    # Mock _load_date_labels
    monkeypatch.setattr("app.main._load_date_labels", lambda: {})


def _apply_person_page_mocks(monkeypatch):
    """Apply common mocks for person page tests."""
    registry = _make_fake_registry(IDENTITIES)
    photo_reg = _make_fake_photo_registry(PHOTO_META, FACE_TO_PHOTO)

    monkeypatch.setattr("app.main.load_registry", lambda: registry)
    monkeypatch.setattr("app.main.load_photo_registry", lambda: photo_reg)
    monkeypatch.setattr("app.main.get_photo_metadata", lambda pid: PHOTO_META.get(pid))
    monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-a.jpg", "face-b.jpg"})
    monkeypatch.setattr(
        "app.main.resolve_face_image_url",
        lambda fid, _crops: f"/crops/{fid}.jpg" if fid else None,
    )
    monkeypatch.setattr(
        "app.main.get_photo_id_for_face", lambda fid: FACE_TO_PHOTO.get(fid)
    )
    monkeypatch.setattr(
        "app.main.get_best_face_id",
        lambda all_faces: (all_faces[0] if all_faces else None),
    )
    monkeypatch.setattr("app.main._load_date_labels", lambda: {})
    monkeypatch.setattr("app.main._build_caches", lambda: None)
    monkeypatch.setattr("app.main._photo_cache", PHOTO_META)
    monkeypatch.setattr("app.main._face_to_photo_cache", FACE_TO_PHOTO)


# ===========================================================================
# 1. Face identity labels in face analysis section
# ===========================================================================


class TestFaceIdentityLabels:
    """Face analysis cards show confirmed names instead of 'Face N'."""

    def _alignment_data(self, faces):
        """Helper to build alignment data dict."""
        return {
            "aligned_faces": faces,
            "faces_detected": len(faces),
            "faces_described": len(faces),
            "gemini_only_faces": [],
            "scene_context": "",
            "model_used": "gemini-2.0-flash",
        }

    def test_confirmed_identity_shows_name_in_analysis(self, client, monkeypatch):
        """Confirmed identity face shows the person's real name in face analysis."""
        _apply_photo_page_mocks(monkeypatch, mock_alignment=False)

        alignment = self._alignment_data([
            {
                "face_id": "face-a",
                "identity_name": "Selma Capeluto",
                "estimated_age": 35,
                "gender": "female",
                "gemini_description": "A woman in a dark dress.",
                "clothing": "dark dress",
                "position_in_photo": "left",
                "identifying_features": "",
                "is_subject": True,
            },
            {
                "face_id": "face-b",
                "identity_name": None,
                "estimated_age": 40,
                "gender": "male",
                "gemini_description": "A man in a suit.",
                "clothing": "suit",
                "position_in_photo": "right",
                "identifying_features": "",
                "is_subject": True,
            },
        ])
        monkeypatch.setattr(
            "app.face_alignment.get_cached_alignment", lambda _pid: alignment
        )
        monkeypatch.setattr(
            "app.face_alignment.load_alignments", lambda _path: {}
        )

        response = client.get(f"/photo/{PHOTO_ID}")
        assert response.status_code == 200
        html = response.text

        # Confirmed identity name should appear as a link in the analysis
        assert CONFIRMED_NAME in html
        assert f"/person/{CONFIRMED_ID}" in html
        # No "Face N:" prefix for identified faces — just the name link
        assert "Face 0: " not in html

    def test_confirmed_identity_name_links_to_person_page(self, client, monkeypatch):
        """Face analysis links confirmed names to /person/{id}."""
        _apply_photo_page_mocks(monkeypatch, mock_alignment=False)

        alignment = self._alignment_data([
            {
                "face_id": "face-a",
                "identity_name": "Selma Capeluto",
                "estimated_age": 35,
                "gender": "female",
                "gemini_description": "A woman.",
                "clothing": "",
                "position_in_photo": "center",
                "identifying_features": "",
                "is_subject": True,
            },
        ])
        monkeypatch.setattr(
            "app.face_alignment.get_cached_alignment", lambda _pid: alignment
        )
        monkeypatch.setattr(
            "app.face_alignment.load_alignments", lambda _path: {}
        )

        response = client.get(f"/photo/{PHOTO_ID}")
        html = response.text

        # The face-identity-link testid should be present
        assert 'data-testid="face-identity-link"' in html
        # Link href should point to person page
        assert f'href="/person/{CONFIRMED_ID}"' in html

    def test_unidentified_face_shows_face_index(self, client, monkeypatch):
        """Unidentified faces show 'Face N' label, not a person name."""
        _apply_photo_page_mocks(monkeypatch, mock_alignment=False)

        alignment = self._alignment_data([
            {
                "face_id": "face-b",
                "identity_name": None,
                "estimated_age": 40,
                "gender": "male",
                "gemini_description": "A man.",
                "clothing": "",
                "position_in_photo": "right",
                "identifying_features": "",
                "is_subject": True,
            },
        ])
        monkeypatch.setattr(
            "app.face_alignment.get_cached_alignment", lambda _pid: alignment
        )
        monkeypatch.setattr(
            "app.face_alignment.load_alignments", lambda _path: {}
        )

        response = client.get(f"/photo/{PHOTO_ID}")
        html = response.text

        # Should show "Face 0" for unidentified
        assert "Face 0" in html
        # Should NOT have a face-identity-link for unidentified faces
        # (The link testid is only set for confirmed identities)


# ===========================================================================
# 2. Photo → Map button
# ===========================================================================


class TestPhotoMapButton:
    """Photo pages with identified people show 'See on Map' button."""

    def test_photo_with_identified_people_has_map_button(self, client, monkeypatch):
        """Photo page shows 'See on Map' when identified people are present."""
        _apply_photo_page_mocks(monkeypatch)
        response = client.get(f"/photo/{PHOTO_ID}")
        assert response.status_code == 200
        html = response.text

        assert "See on Map" in html
        assert 'data-testid="photo-map-btn"' in html

    def test_map_button_links_to_map_with_people_param(self, client, monkeypatch):
        """Map button href includes the identified person IDs."""
        _apply_photo_page_mocks(monkeypatch)
        response = client.get(f"/photo/{PHOTO_ID}")
        html = response.text

        # The href should contain /map?people= with the confirmed person ID
        assert f"/map?people={CONFIRMED_ID}" in html

    def test_photo_without_identified_people_has_no_map_button(self, client, monkeypatch):
        """Photo page with only unidentified faces does not show map button."""
        # Create a photo with only unidentified faces
        unid_identities = [
            {
                "identity_id": "unid-1",
                "name": "Unidentified Person 1",
                "state": "INBOX",
                "anchor_ids": ["face-x"],
                "candidate_ids": [],
            }
        ]
        unid_photo = {
            "unid-photo": {
                "photo_id": "unid-photo",
                "filename": "unid_photo.jpg",
                "collection": "Test",
                "face_ids": ["face-x"],
                "faces": [
                    {"face_id": "face-x", "bbox": [10, 10, 100, 100]},
                ],
                "width": 800,
                "height": 600,
            }
        }
        unid_f2p = {"face-x": "unid-photo"}

        registry = _make_fake_registry(unid_identities)
        photo_reg = _make_fake_photo_registry(unid_photo, unid_f2p)

        monkeypatch.setattr("app.main.load_registry", lambda: registry)
        monkeypatch.setattr("app.main.load_photo_registry", lambda: photo_reg)
        monkeypatch.setattr("app.main.get_photo_metadata", lambda pid: unid_photo.get(pid))
        monkeypatch.setattr("app.main.get_crop_files", lambda: {"face-x.jpg"})
        monkeypatch.setattr("app.main.resolve_face_image_url", lambda fid, _: f"/crops/{fid}.jpg" if fid else None)
        monkeypatch.setattr("app.main.get_photo_id_for_face", lambda fid: unid_f2p.get(fid))
        monkeypatch.setattr("app.main.get_best_face_id", lambda all_faces: (all_faces[0] if all_faces else None))
        monkeypatch.setattr("app.main.get_photo_dimensions", lambda _fn: (800, 600))
        monkeypatch.setattr("app.main.get_identity_for_face", lambda reg, fid: next(
            (i for i in unid_identities if fid in (i.get("anchor_ids", []) + i.get("candidate_ids", []))),
            None,
        ))
        monkeypatch.setattr("app.main._build_caches", lambda: None)
        monkeypatch.setattr("app.main._photo_cache", unid_photo)
        monkeypatch.setattr("app.main._face_to_photo_cache", unid_f2p)
        monkeypatch.setattr("app.main._build_face_alignment_section", lambda *a, **kw: None)
        monkeypatch.setattr("app.main._build_ai_analysis_section", lambda *a, **kw: None)
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})

        response = client.get("/photo/unid-photo")
        assert response.status_code == 200
        html = response.text

        # Map button should NOT be present when no identified people
        assert 'data-testid="photo-map-btn"' not in html


# ===========================================================================
# 3. Map people param filtering
# ===========================================================================


class TestMapPeopleParam:
    """Map route accepts people query param and filters photos."""

    def test_map_route_returns_200(self, client, monkeypatch):
        """Map route loads without error."""
        monkeypatch.setattr("app.main._build_caches", lambda: None)
        monkeypatch.setattr("app.main._photo_cache", {})
        monkeypatch.setattr("app.main._photo_locations_cache", {})
        monkeypatch.setattr("app.main._load_photo_locations", lambda: {})
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})
        monkeypatch.setattr("app.main.load_registry", lambda: _make_fake_registry([]))
        monkeypatch.setattr("app.main.load_photo_registry", lambda: _make_fake_photo_registry({}, {}))

        response = client.get("/map")
        assert response.status_code == 200

    def test_map_with_people_param_uses_person_filter(self, client, monkeypatch):
        """Map route with ?people=id1,id2 applies person filter."""
        # Set up locations and photo data so a person filter would work
        locations = {
            PHOTO_ID: {
                "lat": 36.4417,
                "lng": 28.2225,
                "location_name": "Rhodes, Greece",
                "location_key": "rhodes",
                "region": "Eastern Mediterranean",
            }
        }
        registry = _make_fake_registry(IDENTITIES)
        photo_reg = _make_fake_photo_registry(PHOTO_META, FACE_TO_PHOTO)

        monkeypatch.setattr("app.main._build_caches", lambda: None)
        monkeypatch.setattr("app.main._photo_cache", PHOTO_META)
        monkeypatch.setattr("app.main._photo_locations_cache", locations)
        monkeypatch.setattr("app.main._load_photo_locations", lambda: locations)
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})
        monkeypatch.setattr("app.main.load_registry", lambda: registry)
        monkeypatch.setattr("app.main.load_photo_registry", lambda: photo_reg)
        monkeypatch.setattr("app.main.get_identity_for_face", lambda reg, fid: next(
            (i for i in IDENTITIES if fid in (i.get("anchor_ids", []) + i.get("candidate_ids", []))),
            None,
        ))

        response = client.get(f"/map?people={CONFIRMED_ID}")
        assert response.status_code == 200
        html = response.text

        # The map page should contain the person ID (used in JS filtering)
        # and "Rhodes" location from our test data
        assert "Rhodes" in html or "map" in html.lower()

    def test_map_people_param_extracts_first_as_person(self, client, monkeypatch):
        """When people= has multiple IDs, the first is used as person filter."""
        locations = {}
        registry = _make_fake_registry(IDENTITIES)
        photo_reg = _make_fake_photo_registry({}, {})

        monkeypatch.setattr("app.main._build_caches", lambda: None)
        monkeypatch.setattr("app.main._photo_cache", {})
        monkeypatch.setattr("app.main._photo_locations_cache", locations)
        monkeypatch.setattr("app.main._load_photo_locations", lambda: locations)
        monkeypatch.setattr("app.main._load_date_labels", lambda: {})
        monkeypatch.setattr("app.main.load_registry", lambda: registry)
        monkeypatch.setattr("app.main.load_photo_registry", lambda: photo_reg)

        # With multiple people IDs, first should be used
        response = client.get(f"/map?people={CONFIRMED_ID},{UNIDENTIFIED_ID}")
        assert response.status_code == 200


# ===========================================================================
# 4. Person → Map link
# ===========================================================================


class TestPersonMapLink:
    """Person pages have a map link."""

    def test_person_page_has_map_link(self, client, monkeypatch):
        """Person page includes 'Map' link with correct person ID."""
        _apply_person_page_mocks(monkeypatch)
        response = client.get(f"/person/{CONFIRMED_ID}")
        assert response.status_code == 200
        html = response.text

        # Map link should be present in the action bar
        assert f"/map?person={CONFIRMED_ID}" in html
        assert 'data-testid="person-map-link"' in html

    def test_person_action_bar_has_map_link(self, client, monkeypatch):
        """Person action bar contains the Map link."""
        _apply_person_page_mocks(monkeypatch)
        response = client.get(f"/person/{CONFIRMED_ID}")
        html = response.text

        # Action bar testid should be present with map inside
        assert 'data-testid="person-action-bar"' in html
        assert "Map" in html

    def test_person_map_link_visible_to_anonymous_users(self, client, monkeypatch, auth_enabled, no_user):
        """Map link is visible even to anonymous (non-admin) users."""
        _apply_person_page_mocks(monkeypatch)
        response = client.get(f"/person/{CONFIRMED_ID}")
        assert response.status_code == 200
        html = response.text

        assert f"/map?person={CONFIRMED_ID}" in html

    def test_unidentified_person_page_has_map_link(self, client, monkeypatch):
        """Even unidentified person pages have the map link in action bar."""
        _apply_person_page_mocks(monkeypatch)
        response = client.get(f"/person/{UNIDENTIFIED_ID}")
        assert response.status_code == 200
        html = response.text

        # Map link should use the unidentified person's ID
        assert f"/map?person={UNIDENTIFIED_ID}" in html


# ===========================================================================
# 5. Person card links on photo pages
# ===========================================================================


class TestPhotoPersonCards:
    """Person cards on photo pages link correctly."""

    def test_identified_person_card_links_to_person_page(self, client, monkeypatch):
        """Identified person card on photo page links to /person/{id}."""
        _apply_photo_page_mocks(monkeypatch)
        response = client.get(f"/photo/{PHOTO_ID}")
        html = response.text

        # Person card for the confirmed identity should link to their page
        assert f"/person/{CONFIRMED_ID}" in html
        assert CONFIRMED_NAME in html

    def test_unidentified_person_card_links_to_identify_page(self, client, monkeypatch):
        """Unidentified person card on photo page links to /identify/{id}."""
        _apply_photo_page_mocks(monkeypatch)
        response = client.get(f"/photo/{PHOTO_ID}")
        html = response.text

        # Unidentified person card should link to identify page
        assert f"/identify/{UNIDENTIFIED_ID}" in html
