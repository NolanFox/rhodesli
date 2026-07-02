"""QW-1 regression: /photos must fail CLOSED on transient community-scope loss.

Root cause (Fable eval W4/W2, Lesson 151): app/browse_routes.py only applied the
community photo filter `if community_photo_ids is not None`, so when scoping could
not be computed during a Supabase blip the page rendered the FULL multi-community
corpus (fail-open cross-community leak). The identity path already failed closed
(app/main.py:_get_community_photo_ids callers); the photos path did not.

The fix must fail closed ONLY for a real transient error — never break local dev /
tests where Supabase is legitimately absent and scope is None by design.
"""

from unittest.mock import patch

from app.browse_routes import _community_scope_failed


def test_root_no_community_never_fails_closed():
    # community is None (root / unscoped) -> no filter, unchanged behavior.
    assert _community_scope_failed(None, None) is False


def test_scope_present_never_fails_closed():
    # A computed scope set -> normal filtering, not fail-closed.
    assert _community_scope_failed({"id": "c1"}, {"photo_a", "photo_b"}) is False


def test_transient_error_with_supabase_available_fails_closed():
    # Community set + scope None + Supabase reachable => transient error => fail closed.
    with patch("app.supabase_data.get_supabase_client", return_value=object()):
        assert _community_scope_failed({"id": "c1"}, None) is True


def test_supabase_absent_does_not_fail_closed():
    # Local dev / tests: Supabase absent => scope legitimately None => no filter.
    with patch("app.supabase_data.get_supabase_client", return_value=None):
        assert _community_scope_failed({"id": "c1"}, None) is False


def test_photos_route_scope_failure_renders_without_error_or_sentinel():
    # P3 (Fable fix-audit): route-level property — a scope-failed community page
    # must render (no 500 from the fail-closed `break`) and must NOT emit the
    # next-page lazy sentinel (which would loop) or leak the full corpus.
    from starlette.testclient import TestClient

    from app.main import app

    fox = {"id": "fox-1", "slug": "fox-family", "name": "Fox Family"}
    with (
        patch("app.supabase_data.get_community_by_slug", return_value=fox),
        patch("app.main._get_community_photo_ids", return_value=None),
        patch("app.supabase_data.get_supabase_client", return_value=object()),
    ):
        r = TestClient(app).get("/c/fox-family/photos")
    assert r.status_code == 200
    assert "photos-lazy-sentinel" not in r.text
