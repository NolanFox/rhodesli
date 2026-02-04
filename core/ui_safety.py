"""
UI Boundary Safety Module.

This module provides sanitization functions that ensure strings are safe
for rendering in web contexts (HTML, JSON responses).

DESIGN PRINCIPLE:
- Sanitization is LOSSY and EXPLICIT
- It must ONLY be applied at presentation boundaries (UI/API responses)
- Internal data structures should NOT be sanitized
- This prevents silent data corruption while ensuring UI stability

The root issue: Python's filesystem APIs can return strings with "surrogate escapes"
(PEP 383) when encountering undecodable bytes. These surrogates are invalid UTF-8
and cause UnicodeEncodeError when passed to Starlette/JSON/HTML rendering.
"""


def ensure_utf8_display(value: str | None) -> str:
    """
    Returns a UTF-8 safe string for UI rendering.

    This function is intentionally lossy and MUST ONLY be used at
    presentation boundaries (HTML templates, JSON responses).

    Behavior:
    - None -> empty string
    - Valid UTF-8 -> unchanged
    - Surrogate escapes -> replaced with U+FFFD (replacement character)

    The output is GUARANTEED to be encodable as UTF-8.

    Args:
        value: Input string that may contain surrogate escapes

    Returns:
        UTF-8 safe string that will never raise UnicodeEncodeError
    """
    if value is None:
        return ""

    # Strategy: encode with surrogates allowed, then decode strictly
    # This replaces any surrogates with the replacement character
    try:
        # First, try direct encoding - if it works, string is clean
        value.encode("utf-8")
        return value
    except UnicodeEncodeError:
        # Contains surrogates - sanitize them
        # encode with surrogateescape to handle the surrogates,
        # then decode back, replacing errors
        return value.encode("utf-8", errors="replace").decode("utf-8")


def has_surrogate_escapes(value: str | None) -> bool:
    """
    Check if a string contains surrogate escape code points.

    Surrogate escapes (U+D800 to U+DFFF) are invalid in UTF-8 and will
    cause UnicodeEncodeError when the string reaches the web layer.

    This function is for DETECTION and LOGGING only - it does not modify
    the string. Use ensure_utf8_display() at the UI boundary to sanitize.

    Args:
        value: String to check

    Returns:
        True if string contains surrogate escapes, False otherwise
    """
    if value is None:
        return False

    try:
        value.encode("utf-8")
        return False
    except UnicodeEncodeError:
        return True
