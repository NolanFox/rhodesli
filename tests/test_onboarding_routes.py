"""
Route tests for the self-service archive onboarding flow (PRD-060 / TOOLS-006).

Session 167, Track C. Covers:
- GET /create-archive renders (coming-soon when flag OFF; form when ON)
- POST validation (missing name, name too long, bad contact email)
- POST happy path (flag ON) -> create_community called -> 303 redirect
- POST flag OFF -> no write (coming-soon)
- Per-user rate limit (3 archives) when authenticated
- _slugify / _dedupe_slug units
- Regression: route is registered + main.py made ZERO behavior change by default
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.main import app
import app.onboarding_routes as onboarding


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """The create-archive IP throttle is a module-global; reset between tests
    so accumulated POSTs from the shared TestClient host don't trip it."""
    from app.rate_limit import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setenv("SELF_SERVICE_ARCHIVE_ENABLED", "true")


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.delenv("SELF_SERVICE_ARCHIVE_ENABLED", raising=False)


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------

def test_get_renders_landing(client, flag_off):
    resp = client.get("/create-archive")
    assert resp.status_code == 200
    assert "Create Your Archive" in resp.text


def test_get_flag_off_shows_coming_soon(client, flag_off):
    resp = client.get("/create-archive")
    assert resp.status_code == 200
    assert "create-archive-coming-soon" in resp.text
    # The actual form must NOT render when the feature is disabled.
    assert "create-archive-form" not in resp.text


def test_get_flag_on_shows_form(client, flag_on):
    resp = client.get("/create-archive")
    assert resp.status_code == 200
    assert "create-archive-form" in resp.text
    assert "create-archive-name" in resp.text


# ---------------------------------------------------------------------------
# POST — validation (happy + failure)
# ---------------------------------------------------------------------------

def test_post_flag_off_refuses_write(client, flag_off):
    with patch("app.supabase_data.create_community") as mock_create:
        resp = client.post("/create-archive", data={"name": "Cohen Family"})
    assert resp.status_code == 200
    assert "create-archive-coming-soon" in resp.text
    mock_create.assert_not_called()


def test_post_missing_name_reforms_with_error(client, flag_on):
    with patch("app.supabase_data.create_community") as mock_create, patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        resp = client.post("/create-archive", data={"name": "   "})
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text
    mock_create.assert_not_called()


def test_post_name_too_long_reforms_with_error(client, flag_on):
    long_name = "x" * (onboarding.MAX_NAME_LEN + 5)
    with patch("app.supabase_data.create_community") as mock_create, patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        resp = client.post("/create-archive", data={"name": long_name})
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text
    mock_create.assert_not_called()


def test_post_bad_contact_email_reforms_with_error(client, flag_on):
    with patch("app.supabase_data.create_community") as mock_create, patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        resp = client.post(
            "/create-archive",
            data={"name": "Cohen Family", "contact": "not-an-email"},
        )
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text
    mock_create.assert_not_called()


def test_post_happy_path_creates_and_redirects(client, flag_on):
    created = {"slug": "cohen-family", "name": "Cohen Family"}
    with patch("app.supabase_data.create_community", return_value=created) as mock_create, patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        resp = client.post(
            "/create-archive",
            data={"name": "Cohen Family", "description": "Our photos"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/c/cohen-family/"
    mock_create.assert_called_once()
    payload = mock_create.call_args.args[0]
    assert payload["slug"] == "cohen-family"
    assert payload["name"] == "Cohen Family"
    assert payload["is_personal"] is False
    assert payload["privacy"] == "unlisted"
    assert payload["r2_prefix"] == "archives/cohen-family"


def test_post_slug_deduped_against_existing(client, flag_on):
    existing = [{"slug": "cohen-family"}]
    captured = {}

    def _fake_create(payload):
        captured.update(payload)
        return {"slug": payload["slug"]}

    with patch("app.supabase_data.create_community", side_effect=_fake_create), patch(
        "app.supabase_data.load_communities", return_value=existing
    ):
        resp = client.post(
            "/create-archive", data={"name": "Cohen Family"}, follow_redirects=False
        )
    assert resp.status_code == 303
    assert captured["slug"] == "cohen-family-2"


def test_post_create_failure_reforms_with_error(client, flag_on):
    with patch("app.supabase_data.create_community", return_value=None), patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        resp = client.post("/create-archive", data={"name": "Cohen Family"})
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text


def test_post_create_exception_reforms_with_error(client, flag_on):
    with patch(
        "app.supabase_data.create_community", side_effect=RuntimeError("boom")
    ), patch("app.supabase_data.load_communities", return_value=[]):
        resp = client.post("/create-archive", data={"name": "Cohen Family"})
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text


def test_post_fails_closed_when_community_load_fails(client, flag_on):
    # load_communities() returns None on Supabase failure -> must NOT write.
    with patch("app.supabase_data.create_community") as mock_create, patch(
        "app.supabase_data.load_communities", return_value=None
    ):
        resp = client.post("/create-archive", data={"name": "Cohen Family"})
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text
    mock_create.assert_not_called()


def test_post_description_too_long_reforms_with_error(client, flag_on):
    long_desc = "x" * (onboarding.MAX_DESCRIPTION_LEN + 1)
    with patch("app.supabase_data.create_community") as mock_create, patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        resp = client.post(
            "/create-archive", data={"name": "Cohen Family", "description": long_desc}
        )
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text
    mock_create.assert_not_called()


@pytest.mark.parametrize("bad_email", ["no-at-sign", "a@b", "a@b c.com", "x@y.com\nBcc: z@z.com"])
def test_post_rejects_malformed_contact(client, flag_on, bad_email):
    with patch("app.supabase_data.create_community") as mock_create, patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        resp = client.post(
            "/create-archive", data={"name": "Cohen Family", "contact": bad_email}
        )
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text
    mock_create.assert_not_called()


def test_post_rejected_name_is_html_escaped(client, flag_on):
    # A rejected (too-long) name is re-rendered into the form input value; it
    # must be HTML-escaped, never reflected as raw markup (XSS regression).
    payload = '"><script>alert(1)</script>' + "x" * onboarding.MAX_NAME_LEN
    with patch("app.supabase_data.create_community"), patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        resp = client.post("/create-archive", data={"name": payload})
    assert resp.status_code == 200
    assert "<script>alert(1)</script>" not in resp.text
    assert "&lt;script&gt;" in resp.text


def test_post_ip_throttle_blocks_after_limit(client, flag_on):
    with patch("app.supabase_data.create_community", return_value={"slug": "x"}) as mock_create, patch(
        "app.supabase_data.load_communities", return_value=[]
    ):
        last = None
        for i in range(12):
            last = client.post(
                "/create-archive", data={"name": f"Archive {i}"}, follow_redirects=False
            )
        # After 10 allowed in an hour, further attempts are throttled (200 + error).
        assert last.status_code == 200
        assert "create-archive-error" in last.text
        assert mock_create.call_count <= 10


def test_get_flag_off_with_auth_shows_coming_soon_not_signin(client, flag_off):
    # Gate order: flag-off wins over the auth check (Codex P3).
    with patch("app.main.is_auth_enabled", return_value=True), patch(
        "app.main.get_current_user", return_value=None
    ):
        resp = client.get("/create-archive")
    assert resp.status_code == 200
    assert "create-archive-coming-soon" in resp.text
    assert "create-archive-auth-required" not in resp.text


# ---------------------------------------------------------------------------
# POST — authenticated paths (auth gate + rate limit + owner_id)
# ---------------------------------------------------------------------------

def test_post_rate_limit_blocks_fourth_archive(client, flag_on):
    user = SimpleNamespace(id="user-1", email="owner@example.com", is_admin=False)
    owned = [
        {"slug": f"a{i}", "owner_id": "user-1", "is_personal": False} for i in range(3)
    ]
    with patch("app.main.is_auth_enabled", return_value=True), patch(
        "app.main.get_current_user", return_value=user
    ), patch("app.supabase_data.load_communities", return_value=owned), patch(
        "app.supabase_data.create_community"
    ) as mock_create:
        resp = client.post("/create-archive", data={"name": "Fourth Archive"})
    assert resp.status_code == 200
    assert "create-archive-error" in resp.text
    mock_create.assert_not_called()


def test_post_authenticated_sets_owner_and_admin_emails(client, flag_on):
    user = SimpleNamespace(id="user-1", email="owner@example.com", is_admin=False)
    captured = {}

    def _fake_create(payload):
        captured.update(payload)
        return {"slug": payload["slug"]}

    with patch("app.main.is_auth_enabled", return_value=True), patch(
        "app.main.get_current_user", return_value=user
    ), patch("app.supabase_data.load_communities", return_value=[]), patch(
        "app.supabase_data.create_community", side_effect=_fake_create
    ):
        resp = client.post(
            "/create-archive",
            data={"name": "Cohen Family", "contact": "cousin@example.com"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert captured["owner_id"] == "user-1"
    assert "owner@example.com" in captured["admin_emails"]
    assert "cousin@example.com" in captured["admin_emails"]


def test_post_auth_enabled_anonymous_gets_signin(client, flag_on):
    with patch("app.main.is_auth_enabled", return_value=True), patch(
        "app.main.get_current_user", return_value=None
    ), patch("app.supabase_data.create_community") as mock_create:
        resp = client.post("/create-archive", data={"name": "Cohen Family"})
    assert resp.status_code == 200
    assert "create-archive-auth-required" in resp.text
    mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,expected",
    [
        ("The Cohen Family of Rhodes", "the-cohen-family-of-rhodes"),
        ("  Béëtty's   Album!!  ", "b-tty-s-album"),
        ("UPPER CASE", "upper-case"),
        ("---weird---", "weird"),
        ("", ""),
        ("!!!", ""),
    ],
)
def test_slugify(name, expected):
    assert onboarding._slugify(name) == expected


def test_dedupe_slug_unique_passthrough():
    assert onboarding._dedupe_slug("cohen", set()) == "cohen"


def test_dedupe_slug_appends_suffix():
    assert onboarding._dedupe_slug("cohen", {"cohen"}) == "cohen-2"
    assert onboarding._dedupe_slug("cohen", {"cohen", "cohen-2"}) == "cohen-3"


def test_self_service_flag_default_off(monkeypatch):
    monkeypatch.delenv("SELF_SERVICE_ARCHIVE_ENABLED", raising=False)
    assert onboarding._self_service_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "on"])
def test_self_service_flag_truthy(monkeypatch, val):
    monkeypatch.setenv("SELF_SERVICE_ARCHIVE_ENABLED", val)
    assert onboarding._self_service_enabled() is True


# ---------------------------------------------------------------------------
# Regression
# ---------------------------------------------------------------------------

def test_route_is_registered():
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/create-archive" in paths
