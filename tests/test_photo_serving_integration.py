"""
Integration test - exercises real file paths, no mocking.
Tests that photos in data/uploads/ can be served via /photos/ endpoint.
"""
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient


# Path setup
project_root = Path(__file__).resolve().parent.parent
data_path = project_root / "data"


@pytest.fixture
def client():
    """Create test client, forcing cache reload."""
    from app.main import app, _load_photo_path_cache

    # Reload cache to ensure test sees current state
    _load_photo_path_cache()

    return TestClient(app)


def test_photo_serves_from_uploads(client):
    """Photos in data/uploads should be servable via /photos/ endpoint."""
    photo_index_path = data_path / "photo_index.json"
    if not photo_index_path.exists():
        pytest.skip("No photo_index.json found")

    with open(photo_index_path) as f:
        index = json.load(f)

    # Find an inbox photo (absolute path)
    inbox_photo = None
    for photo_id, photo_data in index.get("photos", {}).items():
        path = Path(photo_data.get("path", ""))
        if path.is_absolute() and path.exists():
            inbox_photo = (photo_id, photo_data, path)
            break

    if not inbox_photo:
        pytest.skip("No inbox photos with existing files found")

    photo_id, photo_data, photo_path = inbox_photo
    filename = photo_path.name

    # Request it via /photos/ endpoint
    response = client.get(f"/photos/{filename}")

    # Should succeed
    assert response.status_code == 200, f"Failed to serve {filename}: {response.status_code} - {response.text}"
    assert len(response.content) > 0, "Response body is empty"


def test_photo_serves_legacy_raw_photos(client):
    """Legacy photos in raw_photos/ should still be servable."""
    raw_photos_path = project_root / "raw_photos"
    if not raw_photos_path.exists():
        pytest.skip("raw_photos directory does not exist")

    # Find any jpg file
    jpg_files = list(raw_photos_path.glob("*.jpg"))[:1]
    if not jpg_files:
        pytest.skip("No jpg files in raw_photos/")

    filename = jpg_files[0].name

    response = client.get(f"/photos/{filename}")

    assert response.status_code == 200, f"Failed to serve legacy photo {filename}: {response.status_code}"


def test_photo_index_paths_exist():
    """All paths in photo_index should exist on disk."""
    photo_index_path = data_path / "photo_index.json"
    if not photo_index_path.exists():
        pytest.skip("No photo_index.json")

    with open(photo_index_path) as f:
        index = json.load(f)

    missing = []
    for photo_id, photo_data in index.get("photos", {}).items():
        path_str = photo_data.get("path", "")
        path = Path(path_str)

        # Check absolute paths directly
        if path.is_absolute():
            if not path.exists():
                missing.append(path_str)
        else:
            # Check relative paths: resolve against project root
            full_path = project_root / path_str
            if not full_path.exists():
                # Also try raw_photos/ fallback for legacy entries
                raw_path = project_root / "raw_photos" / path.name
                if not raw_path.exists():
                    missing.append(path_str)

    assert not missing, f"Missing {len(missing)} files: {missing[:5]}"


def test_nonexistent_photo_returns_404(client):
    """Requesting a nonexistent photo should return 404."""
    response = client.get("/photos/definitely_does_not_exist_12345.jpg")

    assert response.status_code == 404


def test_full_user_flow_view_photo(client):
    """
    THE test - verifies the core user flow works.

    If this test passes, "View Photo" works for inbox uploads.
    Tests: photo_path_cache populated → all cached photos servable
    """
    from app.main import _photo_path_cache, _load_photo_path_cache

    # Reload cache to ensure test sees current state
    _load_photo_path_cache()

    if not _photo_path_cache:
        pytest.skip("No inbox photos in cache")

    # Test ALL cached photos are servable
    failed = []
    for filename, path in list(_photo_path_cache.items())[:10]:  # Test up to 10
        response = client.get(f"/photos/{filename}")
        if response.status_code != 200:
            failed.append(f"{filename}: {response.status_code}")

    assert not failed, f"Failed to serve photos: {failed}"
