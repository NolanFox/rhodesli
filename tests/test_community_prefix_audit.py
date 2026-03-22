"""
Regression test: all user-facing links in route files must use nav_prefix.
Greps for common hardcoded link patterns and fails if found.
Prevents the community prefix whack-a-mole pattern (Lessons 109, 111).
"""

import re
from pathlib import Path

import pytest

ROUTE_FILES_DIR = Path(__file__).parent.parent / "app"

# Patterns that indicate a hardcoded link missing nav_prefix.
# Each tuple: (regex pattern, description)
HARDCODED_PATTERNS = [
    (r'href\s*=\s*["\']\/person\/', 'href="/person/..." without nav_prefix'),
    (r'href\s*=\s*["\']\/photo\/', 'href="/photo/..." without nav_prefix'),
    (r'href\s*=\s*["\']\/compare\?', 'href="/compare?..." without nav_prefix'),
    (r'href\s*=\s*["\']\/identify\/', 'href="/identify/..." without nav_prefix'),
    (r'href\s*=\s*["\']\/timeline', 'href="/timeline..." without nav_prefix'),
    (r'href\s*=\s*f["\']\/person\/', 'href=f"/person/..." without nav_prefix'),
    (r'href\s*=\s*f["\']\/photo\/', 'href=f"/photo/..." without nav_prefix'),
    (r'href\s*=\s*f["\']\/compare', 'href=f"/compare..." without nav_prefix'),
    (r'href\s*=\s*f["\']\/identify\/', 'href=f"/identify/..." without nav_prefix'),
    (r'href\s*=\s*f["\']\/timeline', 'href=f"/timeline..." without nav_prefix'),
    (r'HX-Redirect",\s*"\/person\/', 'HX-Redirect to "/person/..." without nav_prefix'),
    (r'HX-Redirect",\s*f"\/person\/', 'HX-Redirect to f"/person/..." without nav_prefix'),
    (r'HX-Redirect",\s*"\/\?', 'HX-Redirect to "/?" without nav_prefix'),
    (r'HX-Redirect",\s*f"\/\?', 'HX-Redirect to f"/?" without nav_prefix'),
]

# Known exceptions — lines that legitimately have hardcoded paths.
# Format: (filename_stem, line_content_substring)
KNOWN_EXCEPTIONS = [
    # Test files or comments are fine
    ("__init__", ""),
    # Static asset links, login/logout, API endpoints are fine
    # tools_routes.py search results — community-agnostic by design (TOOLS-004)
    ("tools_routes", "/person/{item"),
    ("tools_routes", "/photo/{item"),
]


def _is_exception(filepath: Path, line: str) -> bool:
    """Check if a line is a known exception."""
    stripped = line.strip()
    # Comments
    if stripped.startswith("#"):
        return True
    # String literals in docstrings/comments
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return True
    # API endpoints (skipped by CommunityMiddleware)
    if "/api/" in stripped and "href" not in stripped.lower():
        return True
    # Login/logout/auth paths
    if any(p in stripped for p in ["/login", "/logout", "/auth/", "/signup"]):
        return True
    # Static assets
    if "/static/" in stripped:
        return True
    # Test assertions that check for the pattern
    if "assert" in stripped:
        return True
    # Known exceptions list
    for filename_stem, content_substr in KNOWN_EXCEPTIONS:
        if filename_stem and filename_stem in filepath.stem and content_substr in stripped:
            return True
    return False


def test_no_hardcoded_community_links_in_routes():
    """All user-facing links in route files must use nav_prefix, not hardcoded paths."""
    violations = []
    route_files = sorted(ROUTE_FILES_DIR.glob("*_routes.py"))
    assert len(route_files) > 5, f"Expected 5+ route files, found {len(route_files)}"

    for filepath in route_files:
        lines = filepath.read_text().splitlines()
        for line_num, line in enumerate(lines, 1):
            if _is_exception(filepath, line):
                continue
            for pattern, description in HARDCODED_PATTERNS:
                if re.search(pattern, line):
                    violations.append(f"  {filepath.name}:{line_num} — {description}\n    {line.strip()}")

    if violations:
        msg = (
            f"Found {len(violations)} hardcoded community links without nav_prefix:\n"
            + "\n".join(violations)
            + '\n\nFix: use f"{nav_prefix}/person/..." instead of "/person/..."'
        )
        pytest.fail(msg)
