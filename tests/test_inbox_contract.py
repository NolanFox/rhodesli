"""
Tests the core inbox visibility contract.

Invariant: If an identity exists with state=INBOX and its face crop exists,
           it MUST appear in the inbox UI response.

This test specifically validates that "clean" face_ids (inbox_xxxxx format)
are correctly resolved to their crop files.
"""

import pytest


class TestInboxContract:
    """Tests for inbox visibility invariant."""

    def test_resolve_face_image_url_handles_inbox_format(self):
        """
        resolve_face_image_url must return a valid URL for inbox face_ids.

        Inbox face_ids use format: inbox_{hash} (no ":face" suffix)
        Inbox crops use format: {face_id}.jpg

        This test MUST FAIL on broken code where resolve_face_image_url
        only handles the legacy ":face" format.
        """
        import sys
        sys.path.insert(0, ".")

        from app.main import resolve_face_image_url

        # Simulate inbox face_id and crop file
        face_id = "inbox_abc123def456"
        crop_files = {
            "inbox_abc123def456.jpg",  # Inbox crop exists
            "image_001_22.17_0.jpg",   # Legacy crop
        }

        result = resolve_face_image_url(face_id, crop_files)

        # This assertion will FAIL on broken code (returns None)
        assert result is not None, (
            f"resolve_face_image_url returned None for inbox face_id '{face_id}'. "
            f"Expected '/crops/inbox_abc123def456.jpg'"
        )
        assert result == "/crops/inbox_abc123def456.jpg", (
            f"Expected '/crops/inbox_abc123def456.jpg', got '{result}'"
        )

    def test_identity_card_renders_for_inbox_identity(self):
        """
        identity_card must return a valid card (not None) for inbox identities.

        When an inbox identity has a face_id with a matching crop file,
        identity_card must render it, not return None.
        """
        import sys
        sys.path.insert(0, ".")

        from app.main import identity_card

        identity = {
            "identity_id": "test-inbox-identity-123",
            "name": None,
            "state": "INBOX",
            "anchor_ids": ["inbox_testface123"],
            "candidate_ids": [],
        }

        crop_files = {
            "inbox_testface123.jpg",  # Crop exists for this face
        }

        result = identity_card(identity, crop_files, lane_color="blue", show_actions=True)

        # This assertion will FAIL on broken code (returns None)
        assert result is not None, (
            "identity_card returned None for inbox identity with existing crop. "
            "The inbox lane will be empty even though identities exist."
        )

    def test_legacy_face_id_still_works(self):
        """
        Ensure the fix doesn't break legacy face_id resolution.

        Legacy face_ids use format: {stem}:face{index}
        Legacy crops use format: {sanitized_stem}_{quality}_{index}.jpg
        """
        import sys
        sys.path.insert(0, ".")

        from app.main import resolve_face_image_url

        face_id = "Image 001_compress:face0"
        crop_files = {
            "image_001_compress_22.17_0.jpg",  # Legacy crop
            "inbox_abc123.jpg",  # Inbox crop (shouldn't match)
        }

        result = resolve_face_image_url(face_id, crop_files)

        assert result is not None, (
            f"resolve_face_image_url returned None for legacy face_id '{face_id}'"
        )
        assert result == "/crops/image_001_compress_22.17_0.jpg", (
            f"Expected '/crops/image_001_compress_22.17_0.jpg', got '{result}'"
        )
