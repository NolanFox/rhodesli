"""Route tests for admin force-state transitions."""

from unittest.mock import patch

from core.registry import IdentityRegistry, IdentityState

HTMX_HEADERS = {"HX-Request": "true"}


def test_force_state_route_rejects_anonymous(client, auth_enabled, no_user):
    response = client.post("/api/admin/force-state/test-id/SKIPPED", headers=HTMX_HEADERS)
    assert response.status_code == 401


def test_force_state_route_rejects_non_admin(client, auth_enabled, regular_user):
    response = client.post("/api/admin/force-state/test-id/SKIPPED", headers=HTMX_HEADERS)
    assert response.status_code == 403


def test_force_state_route_records_history(client, auth_enabled, admin_user):
    registry = IdentityRegistry()
    identity_id = registry.create_identity(
        anchor_ids=["face_001"],
        user_source="test",
        state=IdentityState.CONFIRMED,
    )

    with (
        patch("app.identity_routes._main_mod.load_registry", return_value=registry),
        patch("app.identity_routes._main_mod.save_registry"),
    ):
        response = client.post(f"/api/admin/force-state/{identity_id}/SKIPPED", headers=HTMX_HEADERS)

    assert response.status_code == 200
    assert registry.get_identity(identity_id)["state"] == IdentityState.SKIPPED.value

    history = registry.get_history(identity_id)
    assert history[-1]["action"] == "state_change"
    assert history[-1]["metadata"]["forced"] is True
    assert history[-1]["metadata"]["previous_state"] == IdentityState.CONFIRMED.value
    assert history[-1]["metadata"]["new_state"] == IdentityState.SKIPPED.value
