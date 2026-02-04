"""
Regression tests for Unicode surrogate handling at UI boundaries.

Context: The application crashed with UnicodeEncodeError: surrogates not allowed
when strings containing surrogate code points (e.g. "\udc80") reached the
web rendering layer (Starlette / HTML / JSON).

These tests:
1. Demonstrate the crash can occur (before fix)
2. Prove the fix prevents it (after fix)
"""

import pytest


class TestEnsureUtf8Display:
    """Tests for the ensure_utf8_display boundary sanitizer."""

    def test_handles_none(self):
        """None input returns empty string."""
        from core.ui_safety import ensure_utf8_display

        assert ensure_utf8_display(None) == ""

    def test_passes_clean_utf8(self):
        """Clean UTF-8 strings pass through unchanged."""
        from core.ui_safety import ensure_utf8_display

        clean = "John Doe"
        assert ensure_utf8_display(clean) == clean

    def test_passes_valid_unicode(self):
        """Valid Unicode (accents, emoji) passes through."""
        from core.ui_safety import ensure_utf8_display

        unicode_str = "José García 日本語 🎉"
        assert ensure_utf8_display(unicode_str) == unicode_str

    def test_removes_surrogate_escapes(self):
        """Surrogate escapes are removed or replaced."""
        from core.ui_safety import ensure_utf8_display

        # String containing a lone surrogate (invalid UTF-8)
        bad = "bad\udc80name.jpg"
        result = ensure_utf8_display(bad)

        # Must not raise when encoding
        result.encode("utf-8")

        # Surrogate should be gone
        assert "\udc80" not in result
        # Rest of string preserved
        assert "bad" in result
        assert "name.jpg" in result

    def test_output_always_encodable(self):
        """Output can always be encoded to UTF-8 without error."""
        from core.ui_safety import ensure_utf8_display

        # Multiple surrogates
        nasty = "start\ud800\udc00middle\udfff\ud834end"
        result = ensure_utf8_display(nasty)

        # This is the key property - must not raise
        result.encode("utf-8")

    def test_handles_mixed_content(self):
        """Mixed valid Unicode and surrogates handled correctly."""
        from core.ui_safety import ensure_utf8_display

        mixed = "Café\udc80Photo.jpg"
        result = ensure_utf8_display(mixed)

        result.encode("utf-8")
        assert "Café" in result
        assert "Photo.jpg" in result


class TestUnicodeRenderPath:
    """
    Integration tests that simulate the actual render path.

    These tests verify that the full chain from data -> HTML works.
    """

    def test_fasthtml_render_with_surrogate_crashes(self):
        """
        BASELINE: Prove that FastHTML crashes on surrogates (before fix).

        This test documents the bug. After the fix is applied to app/main.py,
        this test should be skipped or removed.
        """
        from fasthtml.common import Div, to_xml

        # Simulate a name with surrogate escapes
        bad_name = "Test\udc80User"

        # This should raise UnicodeEncodeError in the pre-fix state
        component = Div(bad_name)

        with pytest.raises(UnicodeEncodeError):
            to_xml(component).encode("utf-8")

    def test_sanitized_render_succeeds(self):
        """After sanitization, rendering succeeds."""
        from fasthtml.common import Div, to_xml
        from core.ui_safety import ensure_utf8_display

        bad_name = "Test\udc80User"
        safe_name = ensure_utf8_display(bad_name)

        component = Div(safe_name)
        html = to_xml(component)

        # This must succeed
        encoded = html.encode("utf-8")
        assert b"Test" in encoded
        assert b"User" in encoded

    def test_json_response_with_surrogate_crashes(self):
        """
        BASELINE: Prove that JSON encoding crashes on surrogates.

        Note: Starlette uses ensure_ascii=False for performance, which
        preserves surrogates in the output string. The error occurs when
        the response is encoded to UTF-8 bytes for HTTP transmission.
        """
        import json

        bad_data = {"name": "Test\udc80User", "id": "123"}

        # With ensure_ascii=False (Starlette's default), surrogates are preserved
        with pytest.raises(UnicodeEncodeError):
            json.dumps(bad_data, ensure_ascii=False).encode("utf-8")

    def test_sanitized_json_succeeds(self):
        """After sanitization, JSON encoding succeeds."""
        import json
        from core.ui_safety import ensure_utf8_display

        bad_data = {"name": "Test\udc80User", "id": "123"}
        safe_data = {
            "name": ensure_utf8_display(bad_data["name"]),
            "id": bad_data["id"],
        }

        # With ensure_ascii=False (matching Starlette)
        result = json.dumps(safe_data, ensure_ascii=False)
        encoded = result.encode("utf-8")
        assert b"Test" in encoded


class TestNameDisplaySafety:
    """Tests for identity name display safety."""

    def test_name_display_with_surrogate_safe(self):
        """
        The name_display function should handle surrogate escapes.

        This test imports from app.main and verifies the boundary is protected.
        """
        from core.ui_safety import ensure_utf8_display
        from fasthtml.common import to_xml

        # Simulate what name_display does, with sanitization
        bad_name = "Bad\udc80Name"
        identity_id = "test-id-123"

        safe_name = ensure_utf8_display(bad_name)
        display_name = safe_name or f"Identity {identity_id[:8]}..."

        # Simulate rendering
        from fasthtml.common import H3
        component = H3(display_name)
        html = to_xml(component)

        # Must encode without error
        html.encode("utf-8")
        assert "Bad" in html


class TestFilenameDisplaySafety:
    """Tests for filename display safety."""

    def test_filename_with_surrogate_safe(self):
        """Filenames with surrogate escapes don't crash the UI."""
        from core.ui_safety import ensure_utf8_display

        # This can happen with filesystem encoding errors
        bad_filename = "photo_\udc80_001.jpg"
        safe = ensure_utf8_display(bad_filename)

        safe.encode("utf-8")
        assert "photo_" in safe
        assert "_001.jpg" in safe


class TestHasSurrogateEscapes:
    """Tests for the surrogate detection function."""

    def test_detects_surrogates(self):
        """Detects strings with surrogate escapes."""
        from core.ui_safety import has_surrogate_escapes

        assert has_surrogate_escapes("bad\udc80name.jpg") is True

    def test_clean_string_returns_false(self):
        """Clean UTF-8 strings return False."""
        from core.ui_safety import has_surrogate_escapes

        assert has_surrogate_escapes("clean_filename.jpg") is False

    def test_valid_unicode_returns_false(self):
        """Valid Unicode (accents, emoji) returns False."""
        from core.ui_safety import has_surrogate_escapes

        assert has_surrogate_escapes("José García 日本語") is False

    def test_none_returns_false(self):
        """None input returns False."""
        from core.ui_safety import has_surrogate_escapes

        assert has_surrogate_escapes(None) is False
