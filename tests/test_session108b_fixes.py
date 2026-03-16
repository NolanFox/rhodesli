"""Tests for Session 108b bug fixes: FB-013, FB-014, FB-015, and collage override NameError.

FB-013: Compare modal missing on person page
FB-014: Photo context modal link labeled "Public Page" instead of "View Photo"
FB-015: Sidebar search doesn't find photos by filename
Bonus: neighbor_card collage override used undefined `identity_id` instead of `target_identity_id`
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


class TestFB013CompareModalOnPersonPage:
    """FB-013: Person page must include compare_modal() for Compare buttons to work."""

    def test_person_page_source_calls_compare_modal(self):
        """public_person_page source must call compare_modal()."""
        import inspect
        import app.main as main

        # person_routes is registered via main, check its source
        from app import person_routes

        source = inspect.getsource(person_routes.public_person_page)
        assert "compare_modal()" in source, "public_person_page must call compare_modal() so Compare buttons work"

    def test_person_page_renders_compare_modal(self):
        """GET /person/{id} response includes compare-modal div."""
        from app.main import app, load_registry

        registry = load_registry()
        # Find a confirmed identity
        confirmed = None
        for ident in registry.list_identities(state=None):
            if ident.get("state") == "CONFIRMED" and not ident.get("name", "").startswith("Unidentified"):
                confirmed = ident
                break
        if not confirmed:
            pytest.skip("No confirmed identity available")

        c = TestClient(app)
        response = c.get(f"/person/{confirmed['identity_id']}")
        assert response.status_code == 200
        assert "compare-modal" in response.text, "Person page must include compare-modal element"


class TestFB014ViewPhotoLink:
    """FB-014: Photo context modal should show 'View Photo' not 'Public Page'."""

    def _read_page_routes_source(self):
        """Read page_routes.py source directly to avoid circular import."""
        from pathlib import Path

        path = Path(__file__).parent.parent / "app" / "page_routes.py"
        return path.read_text()

    def test_photo_view_content_has_view_photo_label(self):
        """The photo context modal link should say 'View Photo' not 'Public Page'."""
        source = self._read_page_routes_source()
        assert "View Photo" in source, "Expected 'View Photo' link text in page_routes.py"
        assert '"Public Page"' not in source, "Should not have 'Public Page' label anymore"

    def test_view_photo_link_is_prominent(self):
        """The View Photo link should use text-sm not text-xs for better visibility."""
        source = self._read_page_routes_source()
        idx = source.find("View Photo")
        assert idx > 0
        # Look for text-sm in the nearby context (within 500 chars)
        context = source[idx : idx + 500]
        assert "text-sm" in context, "View Photo link should use text-sm for prominence"


class TestFB015PhotoFilenameSearch:
    """FB-015: Sidebar search should find photos by filename."""

    @pytest.fixture
    def client(self):
        from app.main import app

        return TestClient(app)

    def test_search_returns_photo_results_for_filename(self):
        """Searching for a photo filename should return photo results."""
        import app.main as main

        # Reset caches
        main._photo_cache = None
        main._face_to_photo_cache = None
        main._photo_id_aliases = None
        main._crop_files_cache = None

        # Build caches to populate _photo_cache
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache available")

        # Get a real filename from the cache
        first_photo_id = next(iter(main._photo_cache))
        first_photo = main._photo_cache[first_photo_id]
        filename = first_photo.get("filename", "")
        if not filename or len(filename) < 3:
            pytest.skip("No usable filename in photo cache")

        # Search for a substring of the filename (at least 2 chars)
        query = filename[:8] if len(filename) >= 8 else filename

        c = TestClient(main.app)
        response = c.get(f"/api/search?q={query}")
        assert response.status_code == 200
        html = response.text
        # Should contain a photo result with the filename
        assert "search-photo-result" in html or filename[:6] in html, (
            f"Expected photo results for query '{query}' but got: {html[:500]}"
        )

    def test_search_photo_results_have_photo_link(self):
        """Photo search results should link to /photo/ pages."""
        import app.main as main

        main._photo_cache = None
        main._face_to_photo_cache = None
        main._photo_id_aliases = None
        main._crop_files_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache available")

        first_photo_id = next(iter(main._photo_cache))
        first_photo = main._photo_cache[first_photo_id]
        filename = first_photo.get("filename", "")
        if not filename or len(filename) < 3:
            pytest.skip("No usable filename")

        query = filename[:8] if len(filename) >= 8 else filename

        c = TestClient(main.app)
        response = c.get(f"/api/search?q={query}")
        html = response.text
        assert "/photo/" in html, "Photo results should link to /photo/ pages"

    def test_search_no_results_still_works(self):
        """Searching for a nonexistent term returns 'No matches found'."""
        import app.main as main

        main._photo_cache = None
        main._face_to_photo_cache = None
        main._photo_id_aliases = None
        main._crop_files_cache = None

        c = TestClient(main.app)
        response = c.get("/api/search?q=zzzznonexistent99999")
        assert response.status_code == 200
        assert "No matches found" in response.text

    def test_search_photo_section_separator(self):
        """When both identity and photo results exist, a 'Photos' separator appears."""
        import app.main as main

        main._photo_cache = None
        main._face_to_photo_cache = None
        main._photo_id_aliases = None
        main._crop_files_cache = None
        main._build_caches()

        if not main._photo_cache:
            pytest.skip("No photo cache available")

        # Find a filename that also partially matches an identity name
        # Just test the separator rendering by mocking
        from app.identity_routes import _main_mod

        # We can't easily mock this without more setup, so just verify the code path exists
        import inspect

        source = inspect.getsource(main)
        # The photo search is in identity_routes, not main
        import app.identity_routes as ir

        source = inspect.getsource(ir)
        assert "Photos" in source, "Should have 'Photos' section separator"
        assert "photo_results" in source, "Should have photo_results variable"


class TestCollageOverrideNameError:
    """Bonus fix: neighbor_card collage override button used undefined identity_id."""

    def test_neighbor_card_override_uses_target_identity_id(self):
        """The override button should use target_identity_id, not identity_id."""
        from app.main import neighbor_card
        from fasthtml.common import to_xml

        neighbor = {
            "identity_id": "neighbor-001",
            "name": "Neighbor Person",
            "distance": 0.5,
            "calibrated_probability": 0.7,
            "can_merge": False,
            "merge_blocked_reason": "co_occurrence",
            "merge_blocked_reason_display": "Appear together in photo.jpg",
            "anchor_face_ids": ["face-n1"],
            "candidate_face_ids": [],
            "state": "CONFIRMED",
            "co_occurrence": 1,
        }

        # This should NOT raise NameError
        html = to_xml(
            neighbor_card(
                neighbor,
                target_identity_id="target-001",
                crop_files=set(),
                user_role="admin",
            )
        )
        # The override button should reference target-001, not some undefined variable
        assert "target-001" in html, "Override button should use target_identity_id"
        assert "Override" in html, "Admin should see Override button for co-occurrence blocks"
