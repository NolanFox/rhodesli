"""Tests for BUG-004: Collection stats consistency.

Ensures that photo counts, face counts, and identified counts are computed
by ONE canonical function and used consistently across gallery, sidebar,
and landing page views.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_photo_cache(entries):
    """Build a _photo_cache dict from a list of (photo_id, filename, source, face_ids) tuples."""
    cache = {}
    for photo_id, filename, source, face_ids in entries:
        cache[photo_id] = {
            "filename": filename,
            "source": source,
            "faces": [{"face_id": fid} for fid in face_ids],
        }
    return cache


def _make_registry_mock(identities=None):
    """Build a MagicMock registry with controllable identity lists."""
    registry = MagicMock()
    identities = identities or []
    registry.list_identities.return_value = identities
    if hasattr(registry, 'list_proposed_matches'):
        registry.list_proposed_matches.return_value = []
    return registry


# ---------------------------------------------------------------------------
# Test: canonical function exists and returns correct values
# ---------------------------------------------------------------------------

class TestComputeSidebarCounts:
    """Tests for the canonical _compute_sidebar_counts function."""

    def test_function_exists(self):
        """_compute_sidebar_counts is importable from app.main."""
        from app.main import _compute_sidebar_counts
        assert callable(_compute_sidebar_counts)

    def test_returns_expected_keys(self):
        """The returned dict has all required sidebar keys."""
        from app.main import _compute_sidebar_counts
        import app.main as main_module

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "Coll A", ["f1"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"):
            counts = _compute_sidebar_counts(registry)

        for key in ("to_review", "confirmed", "skipped", "rejected", "photos",
                     "pending_uploads", "proposals"):
            assert key in counts, f"Missing key: {key}"

    def test_photo_count_matches_cache_size(self):
        """photos count equals the number of entries in _photo_cache."""
        from app.main import _compute_sidebar_counts
        import app.main as main_module

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "A", []),
            ("p2", "img2.jpg", "A", ["f1"]),
            ("p3", "img3.jpg", "B", ["f2", "f3"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"):
            counts = _compute_sidebar_counts(registry)

        assert counts["photos"] == 3

    def test_empty_cache(self):
        """With no photos, counts['photos'] is 0."""
        from app.main import _compute_sidebar_counts
        import app.main as main_module

        registry = _make_registry_mock()

        with patch.object(main_module, "_photo_cache", {}), \
             patch.object(main_module, "_build_caches"):
            counts = _compute_sidebar_counts(registry)

        assert counts["photos"] == 0

    def test_none_cache(self):
        """With _photo_cache = None, counts['photos'] is 0."""
        from app.main import _compute_sidebar_counts
        import app.main as main_module

        registry = _make_registry_mock()

        with patch.object(main_module, "_photo_cache", None), \
             patch.object(main_module, "_build_caches"):
            counts = _compute_sidebar_counts(registry)

        assert counts["photos"] == 0


# ---------------------------------------------------------------------------
# Test: gallery and sidebar use the same photo count
# ---------------------------------------------------------------------------

class TestStatsConsistencyAcrossViews:
    """Gallery, sidebar, and landing page must report consistent numbers."""

    def test_gallery_collection_stats_face_count(self):
        """Gallery per-collection face_count matches sum of faces in photos."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "Coll A", ["f1", "f2"]),
            ("p2", "img2.jpg", "Coll A", ["f3"]),
            ("p3", "img3.jpg", "Coll B", ["f4"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        # Coll A: 2 photos, 3 faces. Coll B: 1 photo, 1 face.
        assert "2 photos" in html  # Coll A
        assert "3 faces" in html   # Coll A
        assert "1 face" in html    # Coll B

    def test_gallery_identified_count_uses_identity_lookup(self):
        """Gallery identified_count counts faces with non-Unidentified identity names."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        def mock_identity(registry, face_id):
            if face_id == "f1":
                return {"name": "Alice Smith", "identity_id": "id1", "state": "CONFIRMED"}
            return None

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "Coll A", ["f1", "f2"]),
            ("p2", "img2.jpg", "Coll B", ["f3"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", side_effect=mock_identity):
            html = to_xml(render_photos_section({}, registry, set()))

        # Coll A has 1 identified face out of 2
        assert "1 identified" in html

    def test_sidebar_photo_count_matches_gallery_total(self):
        """Sidebar 'Photos' count equals total photos shown in gallery."""
        from app.main import _compute_sidebar_counts, render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "Coll A", ["f1"]),
            ("p2", "img2.jpg", "Coll B", ["f2"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"):
            counts = _compute_sidebar_counts(registry)

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section(counts, registry, set()))

        # Sidebar says 2 photos, gallery subtitle says "2 photos"
        assert counts["photos"] == 2
        assert "2 photos" in html


# ---------------------------------------------------------------------------
# Test: per-collection stats edge cases
# ---------------------------------------------------------------------------

class TestCollectionStatsEdgeCases:
    """Edge cases for per-collection stats computation."""

    def test_empty_collection(self):
        """A collection with 0 faces still shows correct photo count."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "Empty Coll", []),
            ("p2", "img2.jpg", "Has Faces", ["f1"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        assert "Empty Coll" in html
        assert "Has Faces" in html

    def test_uncategorized_photos(self):
        """Photos with empty source appear under 'Uncategorized'."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "", ["f1"]),
            ("p2", "img2.jpg", "Named", ["f2"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        # Empty source becomes "Uncategorized" in stats
        assert "Uncategorized" in html

    def test_collection_with_zero_identified(self):
        """Collection with faces but 0 identified shows '0 identified'."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "Coll A", ["f1", "f2"]),
            ("p2", "img2.jpg", "Coll B", ["f3"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        assert "0 identified" in html

    def test_many_collections_use_horizontal_scroll(self):
        """5+ collections render with horizontal scroll layout."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        entries = []
        for i in range(6):
            entries.append((f"p{i}", f"img{i}.jpg", f"Collection {i}", [f"f{i}"]))
        cache = _make_photo_cache(entries)

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        # With 6 collections, should use flex scroll layout
        assert "overflow-x-auto" in html

    def test_few_collections_use_grid(self):
        """4 or fewer collections render with grid layout."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        entries = []
        for i in range(3):
            entries.append((f"p{i}", f"img{i}.jpg", f"Collection {i}", [f"f{i}"]))
        cache = _make_photo_cache(entries)

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        # With 3 collections, should use grid layout
        assert "grid-cols-2" in html

    def test_singular_photo_in_collection_stats(self):
        """Collection with 1 photo shows '1 photo' not '1 photos'."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        cache = _make_photo_cache([
            ("p1", "img1.jpg", "Coll A", ["f1"]),
            ("p2", "img2.jpg", "Coll B", ["f2", "f3"]),
            ("p3", "img3.jpg", "Coll B", ["f4"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        # Coll A: "1 photo" (singular), Coll B: "2 photos" (plural)
        assert "1 photo" in html
        # "1 photos" should NOT appear
        assert "1 photos" not in html

    def test_collection_name_not_truncated_in_stats_cards(self):
        """Collection stat cards should NOT use CSS truncate on the name."""
        from app.main import render_photos_section, to_xml
        import app.main as main_module

        registry = _make_registry_mock()
        long_name = "Vida Capeluto NYC Collection"
        cache = _make_photo_cache([
            ("p1", "img1.jpg", long_name, ["f1"]),
            ("p2", "img2.jpg", "Betty Capeluto Miami Collection", ["f2"]),
        ])

        with patch.object(main_module, "_photo_cache", cache), \
             patch.object(main_module, "_build_caches"), \
             patch("app.main.get_identity_for_face", return_value=None):
            html = to_xml(render_photos_section({}, registry, set()))

        # The full collection name should appear in the HTML
        assert long_name in html
        # The collection name element should NOT use truncate class
        # (it uses leading-snug for wrapping instead)
        import re
        # Find the <p> tag containing the collection name and check its class
        name_pattern = re.findall(r'<p[^>]*class="[^"]*"[^>]*>' + re.escape(long_name), html)
        for match in name_pattern:
            assert "truncate" not in match, f"Collection name still has truncate class: {match}"
