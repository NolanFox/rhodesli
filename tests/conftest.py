"""Shared test fixtures for auth, permission, and UI tests."""

import pytest
from unittest.mock import patch

from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Auto-mark slow tests by file path
# ---------------------------------------------------------------------------

_SLOW_PATH_PATTERNS = [
    "/e2e/",
    "/integration/",
    "/smoke/",
    "playwright",
    "browser",
    "test_gedcom",
    "test_upload",
    "test_photo_process",
    "test_deploy",
    "test_combined_pipeline",
    "test_regression",
    "test_ml_clustering",
    "test_cluster_new_faces",
    "test_temporal",
    "test_dependency_gate",
    "test_pending_uploads",
    "test_session_49b",
    "test_session_51B",
    "test_face_alignment",
    "test_face_comparison",
    "test_face_overlays",
    "test_facecompare",
    "test_compare_faces",
    "test_compare_intelligence",
    "test_photo_context",
    "test_photo_viewer",
    "test_identity_display",
    "test_share_download",
    "test_data_integrity",
    "test_auto_backup",
    "test_face_tagging",
    "test_year_estimation",
    "test_sync_api",
    "test_estimate_route",
    "test_supabase_data",
    "test_annotations",
    "test_session_57_coral",
    "test_session_51B",
    "test_smoke.py",
    "test_connect.py",
    "test_mobile.py",
    "test_ui_clarity",
    "test_face_count",
    "test_design_audit",
    "test_subprocess_entrypoint",
    "test_ingest_execution",
    "test_pipeline_scripts",
    "test_process_uploads",
]


def pytest_collection_modifyitems(config, items):
    """Auto-mark slow tests by location."""
    for item in items:
        path = str(item.fspath)
        if any(x in path for x in _SLOW_PATH_PATTERNS):
            item.add_marker(pytest.mark.slow)


# ---------------------------------------------------------------------------
# Supabase isolation (AD-135)
# Prevent real Supabase writes during tests. Tests that specifically test
# Supabase behavior should mock get_supabase_client themselves.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def disable_supabase_writes():
    """Disable all real Supabase writes during tests.

    This prevents save_registry() and _save_annotations() from hitting
    real Supabase when existing tests exercise write routes.
    Tests in test_supabase_data.py mock the client explicitly.
    """
    import app.supabase_data as sd

    old_available = sd._supabase_available
    old_client = sd._supabase_client
    sd._supabase_available = False
    sd._supabase_client = None
    yield
    sd._supabase_available = old_available
    sd._supabase_client = old_client


# ---------------------------------------------------------------------------
# Auth state fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a fresh test client for the FastHTML app."""
    from app.main import app

    return TestClient(app)


@pytest.fixture
def auth_enabled():
    """Mock auth as enabled (Supabase configured)."""
    with patch("app.main.is_auth_enabled", return_value=True), patch("app.auth.is_auth_enabled", return_value=True):
        yield


@pytest.fixture
def auth_disabled():
    """Mock auth as disabled (no Supabase configured)."""
    with patch("app.main.is_auth_enabled", return_value=False), patch("app.auth.is_auth_enabled", return_value=False):
        yield


@pytest.fixture
def no_user():
    """Mock no user logged in (anonymous)."""
    with patch("app.main.get_current_user", return_value=None):
        yield


@pytest.fixture
def regular_user():
    """Mock a logged-in non-admin user."""
    from app.auth import User

    user = User(id="test-user-1", email="user@example.com", is_admin=False)
    with patch("app.main.get_current_user", return_value=user):
        yield user


@pytest.fixture
def admin_user():
    """Mock a logged-in admin user."""
    from app.auth import User

    user = User(id="test-admin-1", email="admin@rhodesli.test", is_admin=True)
    with patch("app.main.get_current_user", return_value=user):
        yield user


@pytest.fixture
def google_oauth_enabled():
    """Mock Google OAuth as available."""
    with patch(
        "app.main.get_oauth_url",
        side_effect=lambda p: (
            "https://fvynibivlphxwfowzkjl.supabase.co/auth/v1/authorize?provider=google&redirect_to=https://rhodesli.nolanandrewfox.com/auth/callback"
            if p == "google"
            else None
        ),
    ):
        yield


@pytest.fixture
def google_oauth_disabled():
    """Mock Google OAuth as unavailable."""
    with patch("app.main.get_oauth_url", return_value=None):
        yield
