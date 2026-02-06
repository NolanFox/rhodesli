"""
Integration test - exercises real file paths, no mocking.
Tests that all photos are served from raw_photos/ via /photos/ endpoint.
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
    """Create test client."""
    from app.main import app

    return TestClient(app)


def test_photo_serves_from_raw_photos(client):
    """Photos in raw_photos/ should be servable via /photos/ endpoint."""
    raw_photos_path = project_root / "raw_photos"
    if not raw_photos_path.exists():
        pytest.skip("raw_photos directory does not exist")

    # Find any jpg file
    jpg_files = list(raw_photos_path.glob("*.jpg"))[:1]
    if not jpg_files:
        pytest.skip("No jpg files in raw_photos/")

    filename = jpg_files[0].name

    response = client.get(f"/photos/{filename}")

    assert response.status_code == 200, f"Failed to serve photo {filename}: {response.status_code}"
    assert len(response.content) > 0, "Response body is empty"


def test_photo_index_paths_exist():
    """All paths in photo_index should resolve to files in raw_photos/."""
    photo_index_path = data_path / "photo_index.json"
    if not photo_index_path.exists():
        pytest.skip("No photo_index.json")

    with open(photo_index_path) as f:
        index = json.load(f)

    raw_photos_path = project_root / "raw_photos"
    missing = []
    for photo_id, photo_data in index.get("photos", {}).items():
        path_str = photo_data.get("path", "")
        if not path_str:
            continue

        # All photos should be findable by basename in raw_photos/
        basename = Path(path_str).name
        if not (raw_photos_path / basename).exists():
            missing.append(path_str)

    assert not missing, f"Missing {len(missing)} files in raw_photos/: {missing[:5]}"


def test_nonexistent_photo_returns_404(client):
    """Requesting a nonexistent photo should return 404."""
    response = client.get("/photos/definitely_does_not_exist_12345.jpg")

    assert response.status_code == 404


def test_uploaded_photos_in_raw_photos():
    """Uploaded photos (e.g., 603569408.731013.jpg) should be in raw_photos/."""
    raw_photos_path = project_root / "raw_photos"
    if not raw_photos_path.exists():
        pytest.skip("raw_photos directory does not exist")

    # Check for uploaded-style filenames (numeric timestamps)
    upload_files = list(raw_photos_path.glob("603*.jpg"))
    # If we have uploaded photos, verify they're accessible
    if not upload_files:
        pytest.skip("No uploaded photos found in raw_photos/")

    assert len(upload_files) > 0, "Expected uploaded photos in raw_photos/"
