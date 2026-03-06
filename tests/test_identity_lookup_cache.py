from app.main import get_identity_for_face, save_registry
from core.registry import IdentityRegistry, IdentityState


def test_get_identity_for_face_builds_lookup_once(monkeypatch):
    registry = IdentityRegistry()
    registry.create_identity(
        anchor_ids=["face-1"],
        candidate_ids=["face-2"],
        user_source="test",
        name="Test Person",
        state=IdentityState.CONFIRMED,
    )

    calls = 0
    original = registry.list_identities

    def counting_list_identities(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(registry, "list_identities", counting_list_identities)

    first = get_identity_for_face(registry, "face-1")
    second = get_identity_for_face(registry, "face-2")

    assert first["name"] == "Test Person"
    assert second["name"] == "Test Person"
    assert calls == 1


def test_save_registry_invalidates_face_lookup_cache(tmp_path, monkeypatch):
    registry = IdentityRegistry()
    registry.create_identity(
        anchor_ids=["face-1"],
        user_source="test",
        name="Test Person",
        state=IdentityState.CONFIRMED,
    )
    get_identity_for_face(registry, "face-1")
    assert hasattr(registry, "_face_identity_lookup_cache")

    monkeypatch.setattr("app.main.REGISTRY_PATH", tmp_path / "identities.json")
    monkeypatch.setattr("app.supabase_data.sync_identity_overrides", lambda identities: None)

    save_registry(registry)

    assert not hasattr(registry, "_face_identity_lookup_cache")
