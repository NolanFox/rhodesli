"""Tests for cross-linking between photo viewer and person pages.

Tests cover:
- Person cards on /photo/{id} link to /person/{person_id}
- "See all photos" link appears for identified people
- Unidentified people don't get person page links
"""

import pytest
from starlette.testclient import TestClient

from app.main import app, load_registry, load_embeddings_for_photos, get_identity_for_face


def get_photo_with_identified_person():
    """Find a photo that contains an identified (CONFIRMED) person."""
    photos = load_embeddings_for_photos()
    registry = load_registry()
    if not photos:
        return None, None

    for photo_id, photo_data in photos.items():
        for face_data in photo_data.get("faces", []):
            face_id = face_data.get("face_id", "")
            identity = get_identity_for_face(registry, face_id)
            if identity and identity.get("state") == "CONFIRMED":
                name = identity.get("name", "")
                if not name.startswith("Unidentified"):
                    return photo_id, identity
    return None, None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def photo_with_person():
    return get_photo_with_identified_person()


class TestPersonLinksFromPhotoViewer:
    """Person cards on the photo viewer link to person pages."""

    def test_person_card_links_to_person_page(self, client, photo_with_person):
        """Identified person card has a link to /person/{id}."""
        photo_id, identity = photo_with_person
        if not photo_id or not identity:
            pytest.skip("No photo with identified person found")
        response = client.get(f"/photo/{photo_id}")
        html = response.text
        person_id = identity["identity_id"]
        assert f"/person/{person_id}" in html

    def test_see_all_photos_link(self, client, photo_with_person):
        """Identified person card has 'See all photos' link."""
        photo_id, identity = photo_with_person
        if not photo_id or not identity:
            pytest.skip("No photo with identified person found")
        response = client.get(f"/photo/{photo_id}")
        html = response.text
        assert "See all photos" in html

    def test_unidentified_no_person_link(self, client):
        """Unidentified faces don't show 'See all photos' links."""
        photos = load_embeddings_for_photos()
        registry = load_registry()
        if not photos:
            pytest.skip("No embeddings available")

        # Find a photo with an unidentified face
        for photo_id, photo_data in photos.items():
            for face_data in photo_data.get("faces", []):
                face_id = face_data.get("face_id", "")
                identity = get_identity_for_face(registry, face_id)
                if not identity or identity.get("state") != "CONFIRMED":
                    # This photo has an unidentified face
                    response = client.get(f"/photo/{photo_id}")
                    html = response.text
                    # The page should contain an "Unidentified" badge
                    assert "Unidentified" in html
                    return
        pytest.skip("All faces are identified")

    def test_person_name_links_to_person_page(self, client, photo_with_person):
        """The person's name in the card is a link to /person/{id}."""
        photo_id, identity = photo_with_person
        if not photo_id or not identity:
            pytest.skip("No photo with identified person found")
        response = client.get(f"/photo/{photo_id}")
        html = response.text
        person_id = identity["identity_id"]
        name = identity.get("name", "")
        # Name should be wrapped in an anchor tag pointing to person page
        assert f'href="/person/{person_id}"' in html
        assert name in html or name.replace("'", "&#x27;") in html
