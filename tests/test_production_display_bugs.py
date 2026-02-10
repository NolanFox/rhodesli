"""
Tests for production display bugs (Session 13).

Regression tests for:
1. embeddings.npy must be in REQUIRED_DATA_FILES for production sync
2. face_card quality fallback to embeddings for inbox crops
3. Focus card shows crop image even without photo_id
"""

import re
from unittest.mock import patch, MagicMock


def test_embeddings_npy_in_required_data_files():
    """embeddings.npy MUST be in REQUIRED_DATA_FILES for production sync.

    Without this, new faces added locally won't appear on the live site
    after deploy — the production volume keeps the stale embeddings.npy.
    """
    from scripts.init_railway_volume import REQUIRED_DATA_FILES

    assert "embeddings.npy" in REQUIRED_DATA_FILES, (
        "embeddings.npy must be synced to production on every deploy. "
        "Without it, new photos and faces won't appear on the live site."
    )


def test_required_data_files_includes_all_essentials():
    """All three essential data files must be synced."""
    from scripts.init_railway_volume import REQUIRED_DATA_FILES

    assert "identities.json" in REQUIRED_DATA_FILES
    assert "photo_index.json" in REQUIRED_DATA_FILES
    assert "embeddings.npy" in REQUIRED_DATA_FILES


def test_parse_quality_from_filename_legacy_format():
    """Legacy crop filenames encode quality as {name}_{quality}_{index}.jpg."""
    from app.main import parse_quality_from_filename

    assert parse_quality_from_filename("brass_rail_21.98_0.jpg") == 21.98
    assert parse_quality_from_filename("Image_001_compress_15.50_2.jpg") == 15.50


def test_parse_quality_from_filename_inbox_format_returns_zero():
    """Inbox crop filenames don't encode quality — should return 0.0."""
    from app.main import parse_quality_from_filename

    assert parse_quality_from_filename("inbox_138d977cbce9.jpg") == 0.0
    assert parse_quality_from_filename("inbox_67d39ad2f197.jpg") == 0.0


def test_get_face_quality_returns_quality_from_cache():
    """get_face_quality looks up quality from _photo_cache."""
    import app.main as m

    mock_cache = {
        "photo123": {
            "filename": "test.jpg",
            "faces": [
                {"face_id": "inbox_abc123", "quality": 24.6, "bbox": [0, 0, 1, 1]},
            ],
        }
    }
    mock_face_to_photo = {"inbox_abc123": "photo123"}

    with patch.object(m, "_photo_cache", mock_cache), \
         patch.object(m, "_face_to_photo_cache", mock_face_to_photo):
        quality = m.get_face_quality("inbox_abc123")
        assert quality == 24.6


def test_get_face_quality_returns_none_for_unknown_face():
    """get_face_quality returns None for faces not in cache."""
    import app.main as m

    with patch.object(m, "_photo_cache", {}), \
         patch.object(m, "_face_to_photo_cache", {}):
        quality = m.get_face_quality("inbox_unknown")
        assert quality is None


def test_face_card_quality_fallback_for_inbox_crops():
    """face_card should show real quality for inbox crops, not 0.00.

    When quality is not in the filename, face_card should fall back
    to get_face_quality() which looks up from embeddings cache.
    """
    import app.main as m

    # Mock get_face_quality to return a non-zero value
    with patch.object(m, "get_face_quality", return_value=24.6):
        from fasthtml.common import to_xml
        card = m.face_card(
            face_id="inbox_abc123",
            crop_url="https://example.com/crops/inbox_abc123.jpg",
            # quality not passed — will parse filename (gets 0.0), then fallback
        )
        html = to_xml(card)
        assert "Quality: 24.60" in html
        assert "Quality: 0.00" not in html


def test_face_card_quality_from_filename_when_available():
    """face_card should parse quality from filename when it's encoded there."""
    import app.main as m

    with patch.object(m, "get_face_quality", return_value=None):
        from fasthtml.common import to_xml
        card = m.face_card(
            face_id="Image_001:face0",
            crop_url="/static/crops/Image_001_compress_21.98_0.jpg",
        )
        html = to_xml(card)
        assert "Quality: 21.98" in html


def test_identity_card_expanded_shows_crop_without_photo_id():
    """Focus card should show crop image even when photo_id is unavailable.

    Previously, if get_photo_id_for_face returned None (e.g., stale embeddings),
    the card showed a '?' even though the crop URL was resolvable.
    """
    import app.main as m

    identity = {
        "identity_id": "test-id-123",
        "name": "Test Person",
        "state": "INBOX",
        "anchor_ids": ["inbox_abc123"],
        "candidate_ids": [],
        "negative_ids": [],
        "provenance": "model",
    }

    # crop URL resolves, but photo_id is None (stale embeddings scenario)
    with patch.object(m, "resolve_face_image_url", return_value="https://r2.dev/crops/inbox_abc123.jpg"), \
         patch.object(m, "get_photo_id_for_face", return_value=None), \
         patch.object(m, "is_auth_enabled", return_value=False):
        from fasthtml.common import to_xml
        card = m.identity_card_expanded(identity, crop_files=set(), is_admin=True)
        html = to_xml(card)

        # Should show the crop image, not "?"
        assert "inbox_abc123.jpg" in html
        # Should NOT show the placeholder "?" for this face
        # (there may be other ? in the HTML, just check the crop is rendered)
        assert 'src="https://r2.dev/crops/inbox_abc123.jpg"' in html
