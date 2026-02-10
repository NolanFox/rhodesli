"""
Regression tests for UI stabilization sprint.

These tests verify fixes for critical bugs discovered in the UI/integration layer:
1. Photo 404s - StaticFiles mounting issue
2. Outlier sort returning empty - Centroid computation for PROPOSED identities
3. No centroid errors - Same root cause as #2
4. MLS score discrimination - Scalar sigma formula
"""

import pytest
from pathlib import Path
from urllib.parse import quote

import numpy as np

# Test setup
@pytest.fixture
def test_client():
    """Create test client for the FastHTML app."""
    import sys
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    from starlette.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def registry():
    """Load the identity registry."""
    import sys
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    from app.main import load_registry
    return load_registry()


@pytest.fixture
def face_data():
    """Load face embeddings data."""
    import sys
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    from app.main import get_face_data
    return get_face_data()


class TestPhotoUrlsResolve:
    """
    Regression test for Bug 1: Photo 404s.

    Verifies that photo URLs correctly resolve to existing files,
    including filenames with spaces and special characters.
    """

    def test_simple_filename_resolves(self, test_client):
        """Photos with simple filenames return 200."""
        # Find a photo file
        photos_dir = Path(__file__).resolve().parent.parent / "raw_photos"
        if not photos_dir.exists():
            pytest.skip("raw_photos directory not found")

        files = list(photos_dir.iterdir())
        if not files:
            pytest.skip("No photos in raw_photos directory")

        # Test first photo
        filename = files[0].name
        url = f"/photos/{quote(filename)}"
        resp = test_client.get(url)

        assert resp.status_code == 200, f"Photo {filename} returned {resp.status_code}"

    def test_filename_with_spaces_resolves(self, test_client):
        """Photos with spaces in filename return 200."""
        photos_dir = Path(__file__).resolve().parent.parent / "raw_photos"
        if not photos_dir.exists():
            pytest.skip("raw_photos directory not found")

        # Find a file with spaces
        files_with_spaces = [f for f in photos_dir.iterdir() if " " in f.name]
        if not files_with_spaces:
            pytest.skip("No photos with spaces in filename")

        filename = files_with_spaces[0].name
        url = f"/photos/{quote(filename)}"
        resp = test_client.get(url)

        assert resp.status_code == 200, f"Photo with spaces '{filename}' returned {resp.status_code}"

    def test_all_photos_resolve(self, test_client):
        """All photos in raw_photos directory return 200."""
        photos_dir = Path(__file__).resolve().parent.parent / "raw_photos"
        if not photos_dir.exists():
            pytest.skip("raw_photos directory not found")

        files = [f for f in photos_dir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
        if not files:
            pytest.skip("No image files in raw_photos directory")

        errors = []
        for photo_file in files[:10]:  # Test first 10
            url = f"/photos/{quote(photo_file.name)}"
            resp = test_client.get(url)
            if resp.status_code != 200:
                errors.append(f"{photo_file.name}: {resp.status_code}")

        assert not errors, f"Photo resolution failures:\n" + "\n".join(errors)


class TestSortReturnsFullDicts:
    """
    Regression test for Bug 2: Sort by outlier returns empty.

    Verifies that all sorting options return full face data,
    not empty lists or incomplete dictionaries.
    """

    def test_default_sort_returns_faces(self, test_client, registry):
        """Default sort returns non-empty face list."""
        identities = registry.list_identities()
        if not identities:
            pytest.skip("No identities in registry")

        identity_id = identities[0]["identity_id"]
        url = f"/api/identity/{identity_id}/faces"
        resp = test_client.get(url)

        assert resp.status_code == 200
        # Response should contain grid (face cards)
        assert "grid" in resp.text, "Response should contain face cards in grid"

    def test_outlier_sort_returns_faces(self, test_client, registry):
        """Outlier sort returns non-empty face list for PROPOSED identities."""
        identities = registry.list_identities()
        if not identities:
            pytest.skip("No identities in registry")

        # Find an identity with multiple faces
        identity = None
        for i in identities:
            face_count = len(i.get("anchor_ids", [])) + len(i.get("candidate_ids", []))
            if face_count >= 2:
                identity = i
                break

        if not identity:
            pytest.skip("No identity with multiple faces")

        url = f"/api/identity/{identity['identity_id']}/faces?sort=outlier"
        resp = test_client.get(url)

        assert resp.status_code == 200
        assert "grid" in resp.text, "Outlier sort should return face cards"
        assert len(resp.text) > 100, "Response should have substantial content"

    def test_sort_response_has_consistent_structure(self, test_client, registry):
        """All sort options return the same HTML structure."""
        identities = registry.list_identities()
        if not identities:
            pytest.skip("No identities in registry")

        identity_id = identities[0]["identity_id"]

        for sort_option in ["date", "outlier"]:
            url = f"/api/identity/{identity_id}/faces?sort={sort_option}"
            resp = test_client.get(url)

            assert resp.status_code == 200, f"Sort={sort_option} failed"
            # All responses should be HTML with grid structure
            assert f'id="faces-{identity_id}"' in resp.text, \
                f"Sort={sort_option} missing faces container"


class TestMlsDiscriminatesFaces:
    """
    Regression test for Bug 4: MLS score discrimination.

    Verifies that MLS scores have sufficient range to discriminate
    between similar and dissimilar faces.
    """

    def test_mls_score_range_exceeds_threshold(self, face_data):
        """MLS scores span at least 2.0 points (enough for clustering)."""
        import sys
        project_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(project_root))

        from core.pfe import mutual_likelihood_score

        if len(face_data) < 2:
            pytest.skip("Need at least 2 faces for MLS comparison")

        face_ids = list(face_data.keys())
        scores = []

        # Compute MLS for all pairs
        for i in range(len(face_ids)):
            for j in range(i + 1, len(face_ids)):
                f1 = face_data[face_ids[i]]
                f2 = face_data[face_ids[j]]
                mls = mutual_likelihood_score(
                    f1["mu"], f1["sigma_sq"],
                    f2["mu"], f2["sigma_sq"]
                )
                scores.append(mls)

        if not scores:
            pytest.skip("No face pairs to compare")

        score_range = max(scores) - min(scores)
        assert score_range >= 2.0, \
            f"MLS score range ({score_range:.2f}) too narrow for discrimination"

    def test_mls_uses_single_log_term(self, face_data):
        """MLS formula uses single log term for scalar sigma (not 512 terms)."""
        import sys
        project_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(project_root))

        from core.pfe import mutual_likelihood_score, _is_scalar_sigma

        if len(face_data) < 2:
            pytest.skip("Need at least 2 faces for MLS comparison")

        face_ids = list(face_data.keys())
        f1 = face_data[face_ids[0]]
        f2 = face_data[face_ids[1]]

        # Verify sigma is scalar (uniform)
        assert _is_scalar_sigma(f1["sigma_sq"]), "sigma_sq should be scalar"

        # Compute MLS
        mls = mutual_likelihood_score(
            f1["mu"], f1["sigma_sq"],
            f2["mu"], f2["sigma_sq"]
        )

        # With scalar sigma, MLS should be in reasonable range (-50 to 0)
        # The broken formula (512 log terms) would give values around 300-600
        assert mls < 10, \
            f"MLS ({mls:.1f}) too high - possible 512-term log bug"
        assert mls > -100, \
            f"MLS ({mls:.1f}) too low - unexpected"

    def test_mls_scores_are_negative(self, face_data):
        """All MLS scores are negative (log-likelihood property)."""
        import sys
        project_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(project_root))

        from core.pfe import mutual_likelihood_score

        face_ids = list(face_data.keys())[:5]  # Test first 5 faces

        for i in range(len(face_ids)):
            for j in range(i + 1, len(face_ids)):
                f1 = face_data[face_ids[i]]
                f2 = face_data[face_ids[j]]
                mls = mutual_likelihood_score(
                    f1["mu"], f1["sigma_sq"],
                    f2["mu"], f2["sigma_sq"]
                )
                # MLS is a log-likelihood, should be <= 0
                # (with small positive tolerance for numerical errors)
                assert mls <= 1.0, f"MLS should be negative, got {mls}"


class TestNeighborsGracefulDegradation:
    """
    Regression test: Neighbors endpoint graceful degradation.

    Verifies that the neighbors endpoint returns empty list (not crash)
    when centroid cannot be computed.
    """

    def test_neighbors_returns_valid_html(self, test_client, registry):
        """Neighbors endpoint returns valid HTML response."""
        identities = registry.list_identities()
        if not identities:
            pytest.skip("No identities in registry")

        identity_id = identities[0]["identity_id"]
        url = f"/api/identity/{identity_id}/neighbors"
        resp = test_client.get(url)

        assert resp.status_code == 200, f"Neighbors endpoint failed with {resp.status_code}"
        # Response should be HTML (either neighbor cards or "no similar" message)
        assert "neighbors-sidebar" in resp.text or "No similar" in resp.text

    def test_neighbors_does_not_crash_on_error(self, test_client):
        """Neighbors endpoint handles missing identity gracefully."""
        url = "/api/identity/nonexistent-id/neighbors"
        resp = test_client.get(url)

        # Should return error response, not 500
        assert resp.status_code in (404, 200), \
            f"Expected graceful handling, got {resp.status_code}"


class TestModalAndScriptInclusion:
    """
    Regression tests for UI interaction requirements.

    Verifies that required JavaScript libraries are included and
    modal structure is correct for visibility.
    """

    def test_hyperscript_is_included(self, test_client):
        """Hyperscript library must be included for modal interactions."""
        resp = test_client.get("/?section=to_review")
        assert resp.status_code == 200

        # Hyperscript is required for _="on click..." modal interactions
        assert "hyperscript" in resp.text.lower(), \
            "Hyperscript library not included - modal interactions will fail"

    def test_htmx_is_included(self, test_client):
        """HTMX library must be included for dynamic content loading."""
        resp = test_client.get("/?section=to_review")
        assert resp.status_code == 200

        assert "htmx" in resp.text.lower(), \
            "HTMX library not included - dynamic content will not load"

    def test_photo_modal_has_high_z_index(self, test_client):
        """Photo modal must have z-index above other UI elements."""
        resp = test_client.get("/?section=to_review")
        assert resp.status_code == 200

        # Modal should have very high z-index to be above toasts (z-50)
        assert 'id="photo-modal"' in resp.text, "Photo modal not found in page"
        # Check for z-[9999] or similar high value
        assert "z-[9999]" in resp.text or "z-9999" in resp.text, \
            "Photo modal needs high z-index (z-[9999]) to display above other elements"

    def test_modal_backdrop_uses_absolute_positioning(self, test_client):
        """Modal backdrop should use absolute (not fixed) positioning."""
        resp = test_client.get("/?section=to_review")
        assert resp.status_code == 200

        # The backdrop should be absolute within the fixed modal container
        # Look for the backdrop class pattern
        assert "absolute inset-0 bg-black" in resp.text, \
            "Modal backdrop should use 'absolute inset-0' not 'fixed'"


class TestRenameIdentity:
    """
    Tests for identity rename functionality.

    Verifies that:
    1. Rename endpoint updates identity name
    2. Empty names are rejected
    3. Name persists after rename
    """

    def _make_mock_registry(self):
        """Create a mock registry with a test identity for rename tests."""
        from unittest.mock import MagicMock
        mock_reg = MagicMock()
        mock_reg.get_identity.return_value = {
            "identity_id": "test-id-001",
            "name": "Original Name",
            "state": "CONFIRMED",
        }
        mock_reg.rename_identity.return_value = "Original Name"
        mock_reg.list_identities.return_value = [
            {"identity_id": "test-id-001", "name": "Original Name", "state": "CONFIRMED"}
        ]
        return mock_reg

    def test_rename_identity(self, test_client):
        """Rename endpoint updates identity name."""
        from unittest.mock import patch
        mock_reg = self._make_mock_registry()

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg), \
             patch("app.main.save_registry"):
            response = test_client.post(
                "/api/identity/test-id-001/rename",
                data={"name": "Test Person Name"}
            )
            assert response.status_code == 200
            mock_reg.rename_identity.assert_called_once_with(
                "test-id-001", "Test Person Name", user_source="web"
            )

    def test_rename_empty_rejected(self, test_client):
        """Empty names should be rejected."""
        from unittest.mock import patch
        mock_reg = self._make_mock_registry()

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=mock_reg), \
             patch("app.main.save_registry"):
            response = test_client.post(
                "/api/identity/test-id-001/rename",
                data={"name": "   "}
            )
            assert response.status_code == 400

    def test_rename_form_endpoint(self, test_client, registry):
        """Rename form endpoint returns editable form."""
        identities = registry.list_identities()
        if not identities:
            pytest.skip("No identities in registry")

        identity_id = identities[0]["identity_id"]

        response = test_client.get(f"/api/identity/{identity_id}/rename-form")
        assert response.status_code == 200

        # Form should have input and buttons
        assert "input" in response.text.lower()
        assert "Save" in response.text
        assert "Cancel" in response.text

    def test_name_display_endpoint(self, test_client, registry):
        """Name display endpoint returns name component."""
        identities = registry.list_identities()
        if not identities:
            pytest.skip("No identities in registry")

        identity_id = identities[0]["identity_id"]

        response = test_client.get(f"/api/identity/{identity_id}/name-display")
        assert response.status_code == 200

        # Should have the name container ID
        assert f'id="name-{identity_id}"' in response.text


class TestMergeRemovesSourceCard:
    """
    Tests for merge UI behavior.

    Verifies that merge response includes OOB swap to remove
    the source identity card from the DOM.

    Uses mock registries with Unidentified Person names to avoid
    name conflict modals, sends HTMX headers for partial responses,
    and disables auth to bypass admin checks.
    """

    @pytest.fixture
    def merge_setup(self):
        """Create mock registries with two mergeable identities."""
        from unittest.mock import patch
        from core.registry import IdentityRegistry, IdentityState
        from core.photo_registry import PhotoRegistry

        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_a")
        photo_reg.register_face("photo_2", "/path/photo_2.jpg", "face_b")

        identity_reg = IdentityRegistry()
        target_id = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            state=IdentityState.PROPOSED,
        )
        source_id = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            state=IdentityState.PROPOSED,
        )

        with patch("app.main.load_registry", return_value=identity_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._merge_annotations"), \
             patch("app.main._post_merge_suggestions", return_value=""), \
             patch("app.main.is_auth_enabled", return_value=False):
            from app.main import app
            from starlette.testclient import TestClient
            client = TestClient(app)
            yield client, target_id, source_id

    def test_merge_response_includes_oob_delete(self, merge_setup):
        """After merge, response should include hx-swap-oob=delete for source."""
        client, target_id, source_id = merge_setup

        response = client.post(
            f"/api/identity/{target_id}/merge/{source_id}",
            headers={"HX-Request": "true"},
        )

        assert response.status_code == 200, \
            f"Expected 200 but got {response.status_code}: {response.text[:500]}"
        # Response should include hx-swap-oob="delete" for source card
        assert 'hx-swap-oob="delete"' in response.text, \
            "Merge response missing OOB delete for source card"
        assert f'id="identity-{source_id}"' in response.text, \
            "Merge response missing source identity ID in OOB element"

    def test_merge_updates_target_card(self, merge_setup):
        """After merge, response should include updated target card."""
        client, target_id, source_id = merge_setup

        response = client.post(
            f"/api/identity/{target_id}/merge/{source_id}",
            headers={"HX-Request": "true"},
        )

        assert response.status_code == 200, \
            f"Expected 200 but got {response.status_code}: {response.text[:500]}"
        # Response should include the target identity card
        assert f'id="identity-{target_id}"' in response.text, \
            "Merge response missing updated target card"
