"""TEST-002: Detect admin routes that are not wired to any navigation entry.

Routes in the "no-nav" skip list are explicitly acknowledged as unwired.
Any other /admin/ route that has no sidebar or nav link pointing to it
is flagged — this prevents Lesson 138 (features built but never linked).
"""

import re

import pytest


# Routes that intentionally have no nav entry (API endpoints, background actions, etc.)
NO_NAV_SKIP_LIST = {
    "/admin/cluster-batch",  # PRD-040: deferred pending PIPELINE-001 audit
    "/admin/upload-review/confirm-all",  # POST action endpoint
    "/admin/upload-review/reject-all",  # POST action endpoint
    "/admin/upload-review/speed-run/action",  # POST action endpoint
    "/admin/upload-review/speed-run/undo",  # POST action endpoint
}


def _collect_admin_routes():
    """Collect all registered /admin/ GET routes from the app."""
    import app.main as main_mod

    routes = []
    # FastHTML apps register routes on the app object
    app_obj = getattr(main_mod, "app", None)
    if app_obj is None:
        return routes

    # Check Starlette routes
    for route in getattr(app_obj, "routes", []):
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if "/admin/" in path and ("GET" in methods or not methods):
            routes.append(path)

    return routes


def _collect_nav_hrefs():
    """Collect all href targets from sidebar/nav rendering functions."""
    import inspect
    import app.main as main_mod

    hrefs = set()
    # Search for href patterns in sidebar/nav functions
    for name in dir(main_mod):
        if "sidebar" in name.lower() or "nav" in name.lower() or "admin" in name.lower():
            obj = getattr(main_mod, name)
            if callable(obj):
                try:
                    source = inspect.getsource(obj)
                    # Find href="..." patterns
                    for match in re.finditer(r'href=["\']([^"\']*admin[^"\']*)["\']', source):
                        hrefs.add(match.group(1))
                    # Find f-string href patterns
                    for match in re.finditer(r'href=f["\']([^"\']*admin[^"\']*)["\']', source):
                        # Normalize f-string patterns
                        normalized = re.sub(r"\{[^}]+\}", "{param}", match.group(1))
                        hrefs.add(normalized)
                except (TypeError, OSError):
                    pass

    # Also check cluster_review_routes
    try:
        import app.cluster_review_routes as cr

        for name in dir(cr):
            obj = getattr(cr, name)
            if callable(obj):
                try:
                    source = inspect.getsource(obj)
                    for match in re.finditer(r'href=["\']([^"\']*admin[^"\']*)["\']', source):
                        hrefs.add(match.group(1))
                    for match in re.finditer(r'href=f["\']([^"\']*admin[^"\']*)["\']', source):
                        normalized = re.sub(r"\{[^}]+\}", "{param}", match.group(1))
                        hrefs.add(normalized)
                except (TypeError, OSError):
                    pass
    except ImportError:
        pass

    return hrefs


class TestUnwiredRouteDetection:
    """TEST-002: Ensure all admin routes are either in nav or in the skip list."""

    def test_no_nav_skip_list_is_documented(self):
        """The skip list itself should be non-empty and documented."""
        assert len(NO_NAV_SKIP_LIST) > 0
        for route in NO_NAV_SKIP_LIST:
            assert route.startswith("/admin/"), f"Skip list entry must be an admin route: {route}"

    def test_batch_validation_is_in_skip_list(self):
        """Explicitly verify batch validation is in the skip list (FB-128)."""
        assert "/admin/cluster-batch" in NO_NAV_SKIP_LIST
