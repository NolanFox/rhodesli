"""Tests that duplicate routes have been removed and canonical routes still work.

Session 128: reject-match, correct-date, and face-alignment had duplicate
definitions across route files. Duplicates removed; canonical handlers remain.
"""

import subprocess
import os


def test_no_duplicate_reject_match_route():
    """reject-match route should only be defined in identity_routes.py."""
    result = subprocess.run(
        ["grep", "-rn", "reject-match", "app/"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    lines = [l for l in result.stdout.strip().split("\n") if "reject-match" in l and not l.startswith("tests/")]
    # Route definitions: @rt(...) decorator lines containing reject-match
    route_defs = [l for l in lines if "@rt(" in l]
    assert len(route_defs) == 1, f"Expected 1 route definition, found: {route_defs}"
    assert "identity_routes.py" in route_defs[0], f"Route should be in identity_routes.py, found: {route_defs[0]}"


def test_no_duplicate_correct_date_route():
    """correct-date route should only be defined in photo_routes.py."""
    result = subprocess.run(
        ["grep", "-rn", "correct-date", "app/"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    lines = [l for l in result.stdout.strip().split("\n") if "@rt(" in l and "correct-date" in l]
    assert len(lines) == 1, f"Expected 1 route definition, found: {lines}"
    assert "photo_routes.py" in lines[0], f"Route should be in photo_routes.py, found: {lines[0]}"


def test_no_duplicate_face_alignment_route():
    """face-alignment route definitions should only be in photo_routes.py."""
    result = subprocess.run(
        ["grep", "-rn", "face-alignment.*photo_id", "app/"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    lines = [l for l in result.stdout.strip().split("\n") if "@rt(" in l and "face-alignment" in l]
    # photo_routes.py has both POST and GET handlers
    for line in lines:
        assert "photo_routes.py" in line, f"face-alignment route should only be in photo_routes.py, found: {line}"


def test_reject_match_canonical_handler_exists():
    """The canonical reject-match handler in identity_routes.py should exist."""
    from app import identity_routes

    # Verify the module has the route handler
    source_file = identity_routes.__file__
    with open(source_file) as f:
        source = f.read()
    assert "reject-match" in source
    assert "reject_identity_pair" in source


def test_correct_date_canonical_handler_exists():
    """The canonical correct-date handler in photo_routes.py should exist."""
    from app import photo_routes

    source_file = photo_routes.__file__
    with open(source_file) as f:
        source = f.read()
    assert "correct-date" in source
    assert "correction_year" in source


def test_face_alignment_canonical_handler_exists():
    """The canonical face-alignment handlers in photo_routes.py should exist."""
    from app import photo_routes

    source_file = photo_routes.__file__
    with open(source_file) as f:
        source = f.read()
    assert "face-alignment" in source
    assert "run_face_alignment" in source
    assert "get_cached_alignment" in source


def test_ml_service_token_warning_in_startup():
    """Startup code should warn when ML_SERVICE_TOKEN is default 'dev-token'."""
    from app import main

    source_file = main.__file__
    with open(source_file) as f:
        source = f.read()
    assert "ML_SERVICE_TOKEN" in source
    assert "dev-token" in source
    assert "logging.critical" in source
