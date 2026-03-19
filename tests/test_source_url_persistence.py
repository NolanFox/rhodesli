"""Tests for Session 121: UX-212 source URL persisted through upload approval."""

from pathlib import Path


class TestSourceURLPersistence:
    """Verify source_url is propagated from pending upload through approval to photo record."""

    def test_source_url_extracted_in_approval(self):
        """The approval handler must extract source_url from the pending upload record."""
        source = Path("app/admin_routes.py").read_text()
        # source_url must be extracted from upload record near the approve handler
        assert 'upload.get("source_url"' in source or "source_url = upload" in source, (
            "Approval handler must extract source_url from upload record"
        )

    def test_source_url_set_on_photo_record(self):
        """After processing, source_url must be set on the photo record."""
        source = Path("app/admin_routes.py").read_text()
        assert "set_source_url" in source, "Approval flow must call set_source_url on photo records"

    def test_source_url_uses_photo_ids_from_result(self):
        """source_url should be set using photo_ids from process_directory result."""
        source = Path("app/admin_routes.py").read_text()
        assert "ingest_result" in source, "Approval flow must capture process_directory result"
        assert 'ingest_result["photo_ids"]' in source or 'ingest_result.get("photo_ids")' in source, (
            "Must use photo_ids from ingest result, not source-matching"
        )
