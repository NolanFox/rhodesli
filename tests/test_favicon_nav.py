"""Phase-2 Track B: favicon route + nav-contrast regression (Fable eval V2-10 / V2-6)."""

from starlette.testclient import TestClient

from app.main import app
from app.components.nav import _public_nav_links


def test_favicon_route_returns_svg_not_404():
    # Fable V2-10: /favicon.ico used to 404 on every page.
    client = TestClient(app)
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers.get("content-type", "")
    assert b"<svg" in r.content


def test_nav_links_use_readable_contrast():
    # Fable V2-6: inactive nav links were text-amber-900/60 (near-invisible on the
    # slate-900 nav bar). They must now be a light, readable amber.
    html = "".join(repr(link) for link in _public_nav_links(active="photos"))
    assert "amber-200" in html, "inactive nav links should use a light amber for contrast"
    assert "amber-900/60" not in html, "the near-invisible dark-amber class must be gone"
