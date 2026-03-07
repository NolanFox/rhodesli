"""Tests for AD-209: Collection name should be weak provenance, not location signal.

Verifies that the Gemini prompt treats collection names as information about
who stored the photos, not where the photos were taken.
"""

from rhodesli_ml.gemini_extraction import build_extraction_prompt


class TestCollectionNameNotLocationSignal:
    """AD-209: Collection name must NOT be treated as a strong location signal."""

    def _build_prompt_with_collection(self, collection_name="Nace Capeluto Tampa Collection"):
        """Helper to build a prompt with a collection in photo_metadata."""
        return build_extraction_prompt(
            photo_metadata={"collection": collection_name},
        )

    def test_no_strong_location_language(self):
        """Anti-regression: prompt must NOT contain the old strong-signal language."""
        prompt = self._build_prompt_with_collection()
        assert "strongly suggests photos were taken" not in prompt
        assert "geographic origin of photos" not in prompt

    def test_weak_provenance_language_present(self):
        """Prompt MUST contain the corrected weak-provenance language."""
        prompt = self._build_prompt_with_collection()
        assert "WHO HAD these photos" in prompt
        assert "WEAK contextual evidence" in prompt
        assert "Do NOT assume the collection city is the photo location" in prompt

    def test_collection_name_appears_in_prompt(self):
        """The actual collection name should still appear in the prompt."""
        prompt = self._build_prompt_with_collection("Betty Capeluto Miami Collection")
        assert "Betty Capeluto Miami Collection" in prompt

    def test_no_metadata_section_when_none(self):
        """When photo_metadata is None, no metadata section should be added."""
        prompt = build_extraction_prompt(photo_metadata=None)
        assert "Photo Metadata Context" not in prompt
        assert "WEAK contextual evidence" not in prompt

    def test_no_metadata_section_when_empty(self):
        """When photo_metadata is empty dict, no metadata section should be added."""
        prompt = build_extraction_prompt(photo_metadata={})
        assert "WEAK contextual evidence" not in prompt or "Collection:" not in prompt
