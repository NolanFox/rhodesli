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


class TestIdentitiesHaveCentroids:
    """
    Regression test for Bug 3: No centroid for identity.

    Verifies that centroid computation succeeds for all identities,
    including PROPOSED identities with only candidates.
    """

    def test_proposed_identity_has_centroid(self, registry, face_data):
        """PROPOSED identities can compute centroids using candidates."""
        import sys
        project_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(project_root))

        from core.neighbors import compute_identity_centroid

        identities = registry.list_identities()
        if not identities:
            pytest.skip("No identities in registry")

        # Find a PROPOSED identity with candidates but no anchors
        proposed = [i for i in identities
                   if i.get("state") == "PROPOSED"
                   and len(i.get("candidate_ids", [])) > 0
                   and len(i.get("anchor_ids", [])) == 0]

        if not proposed:
            pytest.skip("No PROPOSED identities with only candidates")

        identity = proposed[0]
        centroid = compute_identity_centroid(registry, identity["identity_id"], face_data)

        assert centroid is not None, \
            f"PROPOSED identity {identity['identity_id'][:8]} should have centroid"

        mu, sigma_sq = centroid
        assert mu.shape == (512,), "Centroid mu should be 512-dimensional"
        assert sigma_sq.shape == (512,), "Centroid sigma_sq should be 512-dimensional"

    def test_all_identities_can_compute_centroid(self, registry, face_data):
        """All identities with faces can compute centroids."""
        import sys
        project_root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(project_root))

        from core.neighbors import compute_identity_centroid

        identities = registry.list_identities()
        if not identities:
            pytest.skip("No identities in registry")

        failures = []
        for identity in identities:
            face_count = len(identity.get("anchor_ids", [])) + len(identity.get("candidate_ids", []))
            if face_count == 0:
                continue  # Skip identities with no faces

            centroid = compute_identity_centroid(
                registry, identity["identity_id"], face_data
            )
            if centroid is None:
                failures.append(identity["identity_id"][:8])

        assert not failures, f"Identities without centroids: {failures}"


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
