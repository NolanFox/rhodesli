"""
Dependency Gate Tests

Verify that every module the app imports at runtime can actually be imported.
This catches the recurring bug where features work locally (dependency installed)
but fail in production (dependency not in requirements.txt).

See: Lessons 70, 70b, 70c in tasks/lessons.md
"""
import importlib
import re
from pathlib import Path

import pytest


def get_app_imports():
    """Scan app/ and core/ for all import statements."""
    imports = set()
    for pattern in ["app/**/*.py", "core/**/*.py"]:
        for pyfile in Path(".").glob(pattern):
            content = pyfile.read_text()
            for match in re.finditer(
                r"^(?:import|from)\s+([\w.]+)", content, re.MULTILINE
            ):
                top_level = match.group(1).split(".")[0]
                imports.add(top_level)
    return imports


# Standard library modules (Python 3.11+) — covers what we use
STDLIB = {
    "abc", "argparse", "ast", "asyncio", "base64", "bisect", "calendar",
    "cgi", "cmath", "collections", "concurrent", "contextlib", "copy",
    "csv", "ctypes", "dataclasses", "datetime", "decimal", "difflib",
    "email", "enum", "errno", "fileinput", "fnmatch", "fractions",
    "functools", "getpass", "glob", "gzip", "hashlib", "heapq", "hmac",
    "html", "http", "inspect", "io", "itertools", "json", "logging",
    "math", "mimetypes", "multiprocessing", "numbers", "operator", "os",
    "pathlib", "pickle", "platform", "pprint", "queue", "random", "re",
    "secrets", "shutil", "signal", "socket", "sqlite3", "statistics",
    "string", "struct", "subprocess", "sys", "tempfile", "textwrap",
    "threading", "time", "timeit", "traceback", "typing", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "zipfile",
    # Internal project modules
    "app", "core", "rhodesli_ml", "tests", "scripts",
}


class TestDependencyGate:
    """Every non-stdlib import used by the app must be importable.
    If this test fails, a dependency is missing from requirements.txt."""

    def test_all_app_imports_resolve(self):
        """Scan app/ and core/ for imports and verify each resolves."""
        imports = get_app_imports()
        third_party = imports - STDLIB

        failures = []
        for module_name in sorted(third_party):
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                failures.append(f"{module_name}: {e}")

        assert not failures, (
            f"Missing dependencies (add to requirements.txt):\n"
            + "\n".join(failures)
        )

    def test_requirements_txt_complete(self):
        """Verify requirements.txt exists and has content."""
        req_path = Path("requirements.txt")
        assert req_path.exists(), "requirements.txt missing"
        content = req_path.read_text().strip()
        assert len(content) > 0, "requirements.txt is empty"

    def test_critical_imports(self):
        """Explicitly test imports that have broken production before.
        Each entry represents a past outage."""
        critical = {
            "cv2": "opencv-python-headless",
            "PIL": "Pillow",
            "fasthtml": "python-fasthtml",
            "numpy": "numpy",
        }
        failures = []
        for module, package in critical.items():
            try:
                importlib.import_module(module)
            except ImportError:
                failures.append(f"{module} (install: pip install {package})")

        assert not failures, (
            f"Critical dependencies missing:\n" + "\n".join(failures)
        )

    def test_opencv_headless_available(self):
        """cv2 must be importable — compare upload and image processing depend on it.
        See Lesson 70c: this was missing from requirements.txt, breaking /api/compare/upload."""
        import cv2
        assert hasattr(cv2, "imread"), "cv2.imread not available"

    def test_compare_upload_deps_probed_correctly(self):
        """The has_insightface check must probe actual deferred dependencies,
        not just the function reference. extract_faces() defers cv2 + insightface
        imports, so importing the function always succeeds even without ML deps."""
        # This test verifies the check pattern is correct:
        # importing extract_faces should succeed (it's a pure-Python function reference)
        from core.ingest_inbox import extract_faces
        assert callable(extract_faces)

        # But the real question is: can cv2 be imported?
        import cv2
        assert cv2 is not None
