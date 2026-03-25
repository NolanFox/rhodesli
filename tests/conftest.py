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
    "test_public_photo_viewer",
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
    # Integration-heavy tests that render full pages via TestClient
    "test_admin_dashboard",
    "test_timeline",
    "test_merged_identity_guard",
    "test_bulk_photos",
    "test_internal_photo_links",
    "test_back_image",
    "test_fuzzy_filter",
    "test_photo_nav_persistence",
    "test_estimate_gemini",
    "test_lazy_loading",
    "test_error_handling",
    "test_map",
    "test_critical_routes",
    # Heavy discovery/browse integration tests (6-8s each, 53+ tests)
    "test_discoveries",
    "test_inline_find_similar",
    "test_skipped_focus",
    "test_image_transform",
    "test_photo_flip",
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


@pytest.fixture(autouse=True)
def reset_registry_cache():
    """Reset ALL module-level caches after each test.

    Prevents one test from poisoning caches for other tests in the same
    xdist worker. Covers registry, photo, embeddings, proposals, discovery,
    and all other TTL/lazy caches in app.main and route modules.
    """
    yield
    import app.main as main_mod

    # Registry caches
    main_mod._registry_cache = None
    main_mod._registry_cache_ts = 0.0
    main_mod._registry_cache_key = None

    # Embeddings / face data caches
    main_mod._raw_embeddings_cache = None
    main_mod._face_data_cache = None

    # Photo registry / photo caches
    main_mod._photo_registry_cache = None
    main_mod._photo_cache = None
    main_mod._face_to_photo_cache = None
    main_mod._photo_id_aliases = None
    main_mod._photo_dimensions_cache = None
    main_mod._crop_files_cache = None

    # Community caches
    main_mod._community_photo_ids_cache = {}
    main_mod._community_identity_ids_cache = {}
    main_mod._community_ids_cache_ts = 0.0

    # Proposals caches
    main_mod._proposals_cache = None
    main_mod._proposals_cache_ts = 0.0
    main_mod._proposal_target_counts_cache = None

    # Discovery / skipped / misc caches
    main_mod._discovery_cache = None
    main_mod._discovery_cache_key = None
    main_mod._skipped_neighbor_cache = None
    main_mod._skipped_neighbor_cache_key = None
    main_mod._date_labels_cache = None
    main_mod._search_index_cache = None
    main_mod._birth_year_cache = None
    main_mod._ml_review_decisions_cache = None
    main_mod._context_events_cache = None
    main_mod._place_options_cache = None

    # Route module caches (aliased into main or independent)
    try:
        import app.cluster_review_routes as cr

        cr._speed_run_cache = {}
        cr._suggestions_cache = {}
        cr._review_groups_cache = {}
    except (ImportError, AttributeError):
        pass

    try:
        import app.identity_routes as ir

        ir._neighbors_cache = {}
    except (ImportError, AttributeError):
        pass

    try:
        import app.engagement_routes as er

        er._annotations_cache = None
        er._person_comments_cache = None
    except (ImportError, AttributeError):
        pass

    try:
        import app.relationship_routes as rr

        rr._gedcom_matches_cache = None
        rr._gedcom_tree_relationships_cache = None
        rr._relationship_graph_cache = None
        rr._gedcom_individuals_cache = None
        rr._gedcom_face_links_cache = None
        rr._gedcom_redirects_cache = None
    except (ImportError, AttributeError):
        pass

    try:
        import app.page_routes as pr

        pr._landing_stats_cache = None
        pr._identification_responses_cache = None
        pr._photo_locations_cache = None
        pr._comparison_results_cache = None
    except (ImportError, AttributeError):
        pass

    try:
        import app.supabase_data as sd

        sd._community_cache = {}
    except (ImportError, AttributeError):
        pass


@pytest.fixture(autouse=True)
def default_data_source_json():
    """Default DATA_SOURCE to 'json' for tests (PRD-051 Session 112).

    Production defaults to 'postgres' (Supabase single source of truth).
    Tests default to 'json' so they read from local JSON files without
    needing a live Supabase connection.

    Tests that specifically verify Supabase behavior should patch
    DATA_SOURCE to 'postgres' explicitly.
    """
    import app.main as main_mod

    old = main_mod.DATA_SOURCE
    main_mod.DATA_SOURCE = "json"
    yield
    main_mod.DATA_SOURCE = old


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset IP rate limits between tests to prevent cross-test interference."""
    from app.rate_limit import reset_rate_limits as _reset

    _reset()
    yield
    _reset()


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
    with (
        patch("app.main.get_current_user", return_value=user),
        patch("app.admin_routes.get_current_user", return_value=user),
    ):
        yield user


@pytest.fixture
def admin_user():
    """Mock a logged-in admin user."""
    from app.auth import User

    user = User(id="test-admin-1", email="admin@rhodesli.test", is_admin=True)
    with (
        patch("app.main.get_current_user", return_value=user),
        patch("app.admin_routes.get_current_user", return_value=user),
    ):
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
