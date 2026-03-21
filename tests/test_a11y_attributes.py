"""Tests for image alt text and button aria-label accessibility attributes.

Session 128 Subagent E: Verify that face crop images have alt text,
archive photo images have alt text, and icon-only buttons have aria-label.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read_file(relpath: str) -> str:
    """Read a source file relative to project root."""
    return (PROJECT_ROOT / relpath).read_text()


class TestImgAltTextCoverage:
    """Verify Img() calls have alt= attributes across key route files."""

    def test_main_py_img_calls_have_alt(self):
        """Most Img() calls in main.py should have alt= attribute."""
        content = _read_file("app/main.py")
        lines = content.split("\n")
        missing = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "Img(" in stripped:
                # Collect multi-line call
                block = stripped
                j = i + 1
                paren_count = block.count("(") - block.count(")")
                while paren_count > 0 and j < len(lines) and j < i + 15:
                    block += " " + lines[j].strip()
                    paren_count += lines[j].count("(") - lines[j].count(")")
                    j += 1
                if "alt=" not in block:
                    missing.append(i + 1)
        # Allow some missing (decorative images), but main.py should have very few
        assert len(missing) <= 5, f"main.py has {len(missing)} Img() calls without alt= at lines: {missing}"

    def test_browse_routes_photo_grid_has_alt(self):
        """Photo grid images in browse_routes.py should have alt text."""
        content = _read_file("app/browse_routes.py")
        # The photo grid Img should have alt
        assert 'alt=f"Archive photo {photo' in content, "Photo grid images should have descriptive alt text"

    def test_page_routes_photo_grid_has_alt(self):
        """Photo grid images in page_routes.py should have alt text."""
        content = _read_file("app/page_routes.py")
        assert 'alt=f"Archive photo {photo' in content or 'alt=f"Archive photo {entry' in content, (
            "Photo grid images should have descriptive alt text"
        )

    def test_identity_routes_face_thumbs_have_alt(self):
        """Face thumbnails in identity_routes.py should have alt text."""
        content = _read_file("app/identity_routes.py")
        assert content.count('alt="Face thumbnail"') >= 3, (
            "Identity route face thumbnails should have alt='Face thumbnail'"
        )

    def test_compare_routes_face_images_have_alt(self):
        """Compare route face images should have alt text."""
        content = _read_file("app/compare_routes.py")
        # Pair comparison faces
        assert 'alt="Face from Photo A"' in content
        assert 'alt="Face from Photo B"' in content

    def test_main_py_face_avatar_has_alt(self):
        """Face avatar images in photo cards should have alt text."""
        content = _read_file("app/main.py")
        assert 'alt=f"Face of {face[' in content, "Face avatars should have alt='Face of {name}'"

    def test_admin_routes_photo_thumb_has_alt(self):
        """Admin photo thumbnails should have alt text."""
        content = _read_file("app/admin_routes.py")
        assert 'alt="Archive photo"' in content


class TestIconOnlyButtonAriaLabels:
    """Verify icon-only buttons have aria-label."""

    def test_lightbox_close_button_person_routes(self):
        """Lightbox close button in person_routes should have aria-label."""
        content = _read_file("app/person_routes.py")
        assert 'aria_label="Close lightbox"' in content

    def test_lightbox_close_button_page_routes(self):
        """Lightbox close button in page_routes should have aria-label."""
        content = _read_file("app/page_routes.py")
        assert 'aria_label="Close lightbox"' in content

    def test_hamburger_button_page_routes(self):
        """Hamburger menu button in page_routes should have aria-label."""
        content = _read_file("app/page_routes.py")
        assert 'aria_label="Toggle sidebar menu"' in content

    def test_hamburger_button_admin_routes(self):
        """Hamburger menu button in admin_routes should have aria-label."""
        content = _read_file("app/admin_routes.py")
        assert 'aria_label="Toggle sidebar menu"' in content

    def test_carousel_buttons_have_aria_label(self):
        """Face carousel prev/next buttons should have aria-label."""
        content = _read_file("app/page_routes.py")
        assert 'aria_label="Previous face"' in content
        assert 'aria_label="Next face"' in content

    def test_close_panel_button_browse_routes(self):
        """Close panel button in browse_routes should have aria-label."""
        content = _read_file("app/browse_routes.py")
        assert 'aria_label="Close"' in content

    def test_close_panel_button_page_routes(self):
        """Close panel button in page_routes should have aria-label."""
        content = _read_file("app/page_routes.py")
        assert 'aria_label="Close"' in content

    def test_close_panel_button_main_py(self):
        """Close panel button in main.py should have aria-label."""
        content = _read_file("app/main.py")
        assert 'aria_label="Close"' in content

    def test_quick_identify_button_has_aria_label(self):
        """Quick-identify button in page_routes should have aria-label."""
        content = _read_file("app/page_routes.py")
        assert 'aria_label="Quick identify this face"' in content

    def test_toggle_face_section_has_aria_label(self):
        """Compare routes face section toggle should have aria-label."""
        content = _read_file("app/compare_routes.py")
        assert 'aria_label="Toggle face section"' in content


class TestMinimumAltTextCount:
    """Verify minimum alt text additions across all files."""

    def test_at_least_15_alt_attributes_across_key_files(self):
        """Key route files should have at least 15 total alt= on Img() calls."""
        files = [
            "app/main.py",
            "app/browse_routes.py",
            "app/page_routes.py",
            "app/identity_routes.py",
            "app/compare_routes.py",
            "app/admin_routes.py",
            "app/person_routes.py",
        ]
        total_alt = 0
        for f in files:
            content = _read_file(f)
            total_alt += len(re.findall(r"\balt=", content))
        assert total_alt >= 15, f"Expected at least 15 alt= attributes across key files, found {total_alt}"

    def test_at_least_8_aria_labels_on_buttons(self):
        """Key route files should have at least 8 aria_label additions on buttons."""
        files = [
            "app/main.py",
            "app/page_routes.py",
            "app/browse_routes.py",
            "app/admin_routes.py",
            "app/person_routes.py",
            "app/compare_routes.py",
        ]
        total = 0
        for f in files:
            content = _read_file(f)
            total += len(re.findall(r"aria_label=", content))
        assert total >= 8, f"Expected at least 8 aria_label attributes across button files, found {total}"
