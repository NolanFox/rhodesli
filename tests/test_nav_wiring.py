"""Tests for Session 102 Track C — Navigation Wiring (FB-125/134-138)."""

import inspect
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient


def _get_test_client():
    import app.main as main_mod

    return TestClient(main_mod.app)


def _mock_registry_with_identities(identities_dict):
    """Return a context manager that mocks the registry with given identities."""
    mock_reg = MagicMock()
    mock_reg._identities = identities_dict
    mock_reg.get_identity.side_effect = lambda iid: identities_dict.get(iid)

    def _get(iid):
        return identities_dict.get(iid)

    mock_reg.get = _get
    mock_reg.__iter__ = lambda self: iter(identities_dict)
    mock_reg.__len__ = lambda self: len(identities_dict)
    return patch("app.page_routes._main_mod.load_registry", return_value=mock_reg)


def _make_identity(
    identity_id="test-id-123",
    name="Unidentified Person 42",
    state="INBOX",
    anchor_ids=None,
    candidate_ids=None,
):
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": anchor_ids or ["face1"],
        "candidate_ids": candidate_ids or [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


class TestIdentifyModeButtonCode:
    """C1: Verify Identify Mode code has admin -> seq=1 link and non-admin -> toggle."""

    def test_identify_mode_code_has_admin_seq_link(self):
        """The photo page code should have seq=1 link for admin identify mode."""
        import app.main as main_mod

        source = inspect.getsource(main_mod.public_photo_page)
        # Admin path: A(..., href=".../photo/{photo_id}?seq=1")
        assert "?seq=1" in source
        assert "identify-mode-toggle" in source

    def test_identify_mode_code_has_nonadmin_toggle(self):
        """The photo page code should have toggle button for non-admin."""
        import app.main as main_mod

        source = inspect.getsource(main_mod.public_photo_page)
        # Non-admin path: Button with data_action="toggle-identify-mode"
        assert 'data_action="toggle-identify-mode"' in source

    def test_identify_mode_admin_guard(self):
        """Admin and non-admin code paths are guarded by is_admin."""
        import app.main as main_mod

        source = inspect.getsource(main_mod.public_photo_page)
        # Should have conditional: if is_admin -> A(...seq=1) else Button(toggle)
        assert "if is_admin" in source
        assert "toggle-identify-mode" in source


class TestFaceClickAdminCode:
    """C2: Admin face bbox clicks navigate to Speed Loop at that face."""

    def test_face_click_code_has_admin_seq_path(self):
        """Unidentified face click for admin should go to seq=1 with face param."""
        import app.main as main_mod

        source = inspect.getsource(main_mod.public_photo_page)
        # Admin path for unidentified face: ?seq=1&face={face_id}
        assert "seq=1" in source
        # The code should have a face_param construct
        assert "face=" in source or "_face_param" in source


class TestSpeedLoopBackToQueue:
    """C3: Speed Loop shows 'Back to Review Queue' when from_queue=1."""

    def test_from_queue_param_accepted_by_route(self):
        """The /photo/{photo_id} route should accept from_queue parameter."""
        import app.main as main_mod

        # Check the route handler function signature
        source = inspect.getsource(main_mod.public_photo_page)
        assert "from_queue" in source

    def test_photo_view_content_has_from_queue_param(self):
        """photo_view_content function should accept from_queue."""
        import app.main as main_mod

        sig = inspect.signature(main_mod.photo_view_content)
        assert "from_queue" in sig.parameters

    def test_back_to_review_queue_in_code(self):
        """Code should render 'Back to Review Queue' when from_queue and seq_mode."""
        import app.main as main_mod

        source = inspect.getsource(main_mod.photo_view_content)
        assert "Back to Review Queue" in source
        assert "back-to-review-queue" in source
        assert "from_queue" in source


class TestIdentifyPageAdminEnrichment:
    """C4: Admin sees enrichment tools on /identify/ page."""

    def test_identify_page_admin_sees_enrichment(self):
        """Admin viewing identify page sees name input + merge search."""
        client = _get_test_client()
        identity = _make_identity(identity_id="person-1", state="PROPOSED", name="Unidentified Person 99")
        with ExitStack() as stack:
            stack.enter_context(patch("app.page_routes._main_mod.is_auth_enabled", return_value=True))
            from app.auth import User

            admin_user = User(id="admin-1", email="NolanFox@gmail.com", is_admin=True)
            stack.enter_context(patch("app.page_routes._main_mod.get_current_user", return_value=admin_user))
            stack.enter_context(_mock_registry_with_identities({"person-1": identity}))
            stack.enter_context(patch("app.page_routes._main_mod._build_caches"))
            stack.enter_context(patch("app.page_routes._main_mod._photo_cache", {}))
            stack.enter_context(patch("app.page_routes._main_mod.get_crop_files", return_value={}))
            stack.enter_context(
                patch("app.page_routes._main_mod.resolve_face_image_url", return_value="/static/crops/test.jpg")
            )
            stack.enter_context(patch("app.page_routes._main_mod.get_best_face_id", return_value="face1"))
            mock_photo_reg = MagicMock(
                get_photos_for_faces=MagicMock(return_value=["photo-1"]),
                get_photo_for_face=MagicMock(return_value="photo-1"),
                _photos={"photo-1": {"path": "raw_photos/test.jpg", "collection": "Test"}},
            )
            stack.enter_context(patch("app.page_routes._main_mod.load_photo_registry", return_value=mock_photo_reg))
            stack.enter_context(patch("app.page_routes._main_mod.get_photo_id_for_face", return_value="photo-1"))
            stack.enter_context(patch("app.page_routes._main_mod.storage"))
            stack.enter_context(patch("app.page_routes._main_mod.SITE_URL", "https://test.example.com"))
            stack.enter_context(patch("app.page_routes._main_mod._public_nav_links", return_value=[]))
            stack.enter_context(patch("app.page_routes._main_mod._admin_bar", return_value=None))
            stack.enter_context(patch("app.page_routes._main_mod._share_script", return_value=None))
            stack.enter_context(patch("app.page_routes._main_mod._section_for_state", return_value="to_review"))
            stack.enter_context(patch("app.page_routes._main_mod.community_url_prefix", return_value=""))
            stack.enter_context(patch("core.neighbors.find_nearest_neighbors", return_value=[]))

            resp = client.get("/identify/person-1")
            html = resp.text

            assert resp.status_code == 200
            assert "identify-admin-enrichment" in html
            assert "Admin Tools" in html
            assert "admin-identify-name-input" in html
            assert "Search confirmed identities" in html

    def test_identify_page_nonadmin_no_enrichment(self):
        """Non-admin does not see admin enrichment panel."""
        client = _get_test_client()
        identity = _make_identity(identity_id="person-1", state="PROPOSED", name="Unidentified Person 99")
        with ExitStack() as stack:
            stack.enter_context(patch("app.page_routes._main_mod.is_auth_enabled", return_value=True))
            from app.auth import User

            user = User(id="user-1", email="user@example.com", is_admin=False)
            stack.enter_context(patch("app.page_routes._main_mod.get_current_user", return_value=user))
            stack.enter_context(_mock_registry_with_identities({"person-1": identity}))
            stack.enter_context(patch("app.page_routes._main_mod._build_caches"))
            stack.enter_context(patch("app.page_routes._main_mod._photo_cache", {}))
            stack.enter_context(patch("app.page_routes._main_mod.get_crop_files", return_value={}))
            stack.enter_context(
                patch("app.page_routes._main_mod.resolve_face_image_url", return_value="/static/crops/test.jpg")
            )
            stack.enter_context(patch("app.page_routes._main_mod.get_best_face_id", return_value="face1"))
            mock_photo_reg = MagicMock(
                get_photos_for_faces=MagicMock(return_value=["photo-1"]),
                get_photo_for_face=MagicMock(return_value="photo-1"),
                _photos={"photo-1": {"path": "raw_photos/test.jpg", "collection": "Test"}},
            )
            stack.enter_context(patch("app.page_routes._main_mod.load_photo_registry", return_value=mock_photo_reg))
            stack.enter_context(patch("app.page_routes._main_mod.get_photo_id_for_face", return_value="photo-1"))
            stack.enter_context(patch("app.page_routes._main_mod.storage"))
            stack.enter_context(patch("app.page_routes._main_mod.SITE_URL", "https://test.example.com"))
            stack.enter_context(patch("app.page_routes._main_mod._public_nav_links", return_value=[]))
            stack.enter_context(patch("app.page_routes._main_mod._admin_bar", return_value=None))
            stack.enter_context(patch("app.page_routes._main_mod._share_script", return_value=None))
            stack.enter_context(patch("app.page_routes._main_mod._section_for_state", return_value="to_review"))
            stack.enter_context(patch("app.page_routes._main_mod.community_url_prefix", return_value=""))
            stack.enter_context(patch("core.neighbors.find_nearest_neighbors", return_value=[]))

            resp = client.get("/identify/person-1")
            html = resp.text

            assert resp.status_code == 200
            assert "identify-admin-enrichment" not in html


class TestSpeedRunFaceLinksCommunityPrefix:
    """C5: Speed-run face crop links include community prefix."""

    def test_speed_run_face_links_include_community_prefix(self):
        """Face crop photo links in speed-run should include /c/{slug}/ prefix."""
        from app.cluster_review_routes import _get_photo_url_for_face

        with ExitStack() as stack:
            mock_photo_reg = MagicMock()
            mock_photo_reg.get_photo_for_face.return_value = "photo-abc"
            stack.enter_context(
                patch("app.cluster_review_routes._main_mod.load_photo_registry", return_value=mock_photo_reg)
            )
            stack.enter_context(
                patch("app.cluster_review_routes._main_mod.community_url_prefix", return_value="/c/fox-family")
            )

            url = _get_photo_url_for_face("face-123", community_slug="fox-family")
            assert url == "/c/fox-family/photo/photo-abc"

    def test_speed_run_face_links_no_prefix_when_empty_slug(self):
        """Without community slug, links have no prefix."""
        from app.cluster_review_routes import _get_photo_url_for_face

        with ExitStack() as stack:
            mock_photo_reg = MagicMock()
            mock_photo_reg.get_photo_for_face.return_value = "photo-abc"
            stack.enter_context(
                patch("app.cluster_review_routes._main_mod.load_photo_registry", return_value=mock_photo_reg)
            )

            url = _get_photo_url_for_face("face-123", community_slug="")
            assert url == "/photo/photo-abc"

    def test_face_match_card_uses_nav_prefix(self):
        """_face_match_card passes nav_prefix to photo links."""
        from app.cluster_review_routes import _face_match_card

        proposal = {
            "face_id": "face-abc",
            "distance": 0.5,
            "source_identity_name": "Unknown",
        }
        with ExitStack() as stack:
            stack.enter_context(
                patch("app.cluster_review_routes._get_crop_url_for_face", return_value="/static/crops/test.jpg")
            )
            mock_photo_reg = MagicMock()
            mock_photo_reg.get_photo_for_face.return_value = "photo-xyz"
            stack.enter_context(
                patch("app.cluster_review_routes._main_mod.load_photo_registry", return_value=mock_photo_reg)
            )

            card = _face_match_card(proposal, "Test Identity", "id-1", nav_prefix="/c/fox-family")
            html = repr(card)  # Lesson 83: use repr() for FastHTML elements
            assert "/c/fox-family/photo/photo-xyz" in html
