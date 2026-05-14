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
    # Session 133: admin links must also use nav_prefix
    (r'href\s*=\s*["\']\/admin\/(?!communities)', 'href="/admin/..." without nav_prefix'),
    (r'href\s*=\s*f["\']\/admin\/(?!communities)', 'href=f"/admin/..." without nav_prefix'),
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
    # hx_post to admin action endpoints — these target entities by ID, not community-scoped
    # (Session 133 audit: acceptable because operations are entity-targeted)
    if "hx_post=" in stripped and "/admin/" in stripped:
        return True
    # Admin GEDCOM POST handler responses (no request param, global operations)
    if filepath.name == "admin_routes.py" and "hx_post=" in stripped:
        return True
    # /api/ routes returning href links to admin pages (switcher dropdown, etc.)
    if filepath.name == "admin_routes.py" and "/admin/communities" in stripped:
        return True
    # Birth year accept-all-high response (API route, no request param)
    if filepath.name == "admin_routes.py" and "admin/review/birth-years" in stripped:
        return True
    # GEDCOM apply success response (POST handler without request, links to /admin/gedcom)
    if filepath.name == "admin_routes.py" and 'href="/admin/gedcom"' in stripped:
        return True
    # Session 161: /admin/rhodes-inbox is local-dev-only + admin-only
    # (gated by is_rhodes_wiki_available which returns False on Railway).
    # Community-agnostic by design — admin reviews rhodes-wiki inbox JSONs
    # regardless of community prefix. Hardcoded paths are correct here.
    if filepath.name == "admin_rhodes_inbox_routes.py" and "/admin/rhodes-inbox" in stripped:
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
