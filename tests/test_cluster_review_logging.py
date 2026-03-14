"""Tests for log_user_action calls in speed-run cluster review actions."""

import json
import os
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STORAGE_MODE", "local")


def _get_test_client():
    from starlette.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _admin_session():
    return patch("app.cluster_review_routes._main_mod._check_admin", return_value=None)


def _mock_admin_email(email="admin@test.com"):
    return patch("app.cluster_review_routes._speed_run_admin_email", return_value=email)


def _mock_registry_with_identity(identity_id="test-id-123", state="INBOX"):
    """Create a mock registry with a single test identity."""
    mock_reg = MagicMock()
    identity = {
        "identity_id": identity_id,
        "name": "Test Person",
        "state": state,
        "anchor_ids": ["face_a", "face_b"],
        "candidate_ids": ["face_c", "face_d"],
        "negative_ids": [],
    }
    mock_reg._identities = {identity_id: identity}
    mock_reg.promote_candidate = MagicMock()
    mock_reg.reject_candidate = MagicMock()
    return patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg)


def _mock_speed_run_helpers():
    """Patches for speed-run card rendering helpers."""
    return [
        patch("app.cluster_review_routes._speed_run_next_card", return_value="<div>next</div>"),
        patch("app.cluster_review_routes._speed_run_undo_button", return_value="<div>undo</div>"),
    ]


class TestConfirmAllLogging:
    def test_confirm_all_calls_log_user_action(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry_with_identity())
            stack.enter_context(_mock_admin_email("nolan@test.com"))
            mock_log = stack.enter_context(patch("app.cluster_review_routes._main_mod.log_user_action"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.datetime"))
            for p in _mock_speed_run_helpers():
                stack.enter_context(p)

            client.post(
                "/api/cluster-review/confirm-all",
                data={
                    "identity_id": "test-id-123",
                    "speed_run": "true",
                    "offset": "0",
                    "community_slug": "",
                },
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[0][0] == "SPEED_RUN_CONFIRM"
            assert call_kwargs[1]["identity_id"] == "test-id-123"
            assert call_kwargs[1]["state_before"] == "INBOX"
            assert call_kwargs[1]["state_after"] == "CONFIRMED"
            assert call_kwargs[1]["mode"] == "speed-run"
            assert call_kwargs[1]["admin"] == "nolan@test.com"
            assert "face_count" in call_kwargs[1]


class TestRejectAllLogging:
    def test_reject_all_calls_log_user_action(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry_with_identity())
            stack.enter_context(_mock_admin_email("nolan@test.com"))
            mock_log = stack.enter_context(patch("app.cluster_review_routes._main_mod.log_user_action"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            for p in _mock_speed_run_helpers():
                stack.enter_context(p)

            client.post(
                "/api/cluster-review/reject-all",
                data={
                    "identity_id": "test-id-123",
                    "speed_run": "true",
                    "offset": "0",
                    "community_slug": "",
                },
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[0][0] == "SPEED_RUN_REJECT"
            assert call_kwargs[1]["identity_id"] == "test-id-123"
            assert call_kwargs[1]["mode"] == "speed-run"
            assert call_kwargs[1]["admin"] == "nolan@test.com"
            assert "face_count" in call_kwargs[1]


class TestSkipLogging:
    def test_skip_calls_log_user_action(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_admin_email("nolan@test.com"))
            mock_log = stack.enter_context(patch("app.cluster_review_routes._main_mod.log_user_action"))
            for p in _mock_speed_run_helpers():
                stack.enter_context(p)

            client.post(
                "/api/cluster-review/skip",
                data={
                    "identity_id": "test-id-123",
                    "offset": "0",
                    "community_slug": "",
                },
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[0][0] == "SPEED_RUN_SKIP"
            assert call_kwargs[1]["identity_id"] == "test-id-123"
            assert call_kwargs[1]["mode"] == "speed-run"
            assert call_kwargs[1]["admin"] == "nolan@test.com"


class TestDismissLogging:
    def test_dismiss_calls_log_user_action(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry_with_identity())
            stack.enter_context(_mock_admin_email("nolan@test.com"))
            mock_log = stack.enter_context(patch("app.cluster_review_routes._main_mod.log_user_action"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            for p in _mock_speed_run_helpers():
                stack.enter_context(p)

            client.post(
                "/api/cluster-review/dismiss",
                data={
                    "identity_id": "test-id-123",
                    "offset": "0",
                    "community_slug": "",
                    "speed_run": "true",
                },
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[0][0] == "SPEED_RUN_DISMISS"
            assert call_kwargs[1]["identity_id"] == "test-id-123"
            assert call_kwargs[1]["mode"] == "speed-run"
            assert call_kwargs[1]["admin"] == "nolan@test.com"


class TestUndoLogging:
    def test_undo_calls_log_user_action(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry_with_identity())
            stack.enter_context(_mock_admin_email("nolan@test.com"))
            mock_log = stack.enter_context(patch("app.cluster_review_routes._main_mod.log_user_action"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_speed_run_clusters",
                    return_value=[
                        ("test-id-123", {"name": "Test", "state": "INBOX", "anchor_ids": ["f1"], "candidate_ids": []})
                    ],
                )
            )
            for p in _mock_speed_run_helpers():
                stack.enter_context(p)
            # Mock _speed_run_cluster_card since it's called by undo
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._speed_run_cluster_card",
                    return_value="<div>card</div>",
                )
            )

            face_data = json.dumps({"prev_state": "INBOX", "candidates": ["face_c"]})
            client.post(
                "/api/cluster-review/undo",
                data={
                    "identity_id": "test-id-123",
                    "action": "confirm-all",
                    "offset": "0",
                    "community_slug": "",
                    "face_data": face_data,
                },
            )

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[0][0] == "SPEED_RUN_UNDO"
            assert call_kwargs[1]["identity_id"] == "test-id-123"
            assert call_kwargs[1]["original_action"] == "confirm-all"
            assert call_kwargs[1]["mode"] == "speed-run"
            assert call_kwargs[1]["admin"] == "nolan@test.com"


class TestAdminEmailResolution:
    def test_speed_run_admin_email_returns_email_when_auth_enabled(self):
        from app.cluster_review_routes import _speed_run_admin_email

        mock_user = MagicMock()
        mock_user.email = "admin@example.com"

        with (
            patch("app.cluster_review_routes._main_mod.is_auth_enabled", return_value=True),
            patch("app.cluster_review_routes._main_mod.get_current_user", return_value=mock_user),
        ):
            result = _speed_run_admin_email({"session": "data"})
            assert result == "admin@example.com"

    def test_speed_run_admin_email_returns_fallback_when_no_auth(self):
        from app.cluster_review_routes import _speed_run_admin_email

        with patch("app.cluster_review_routes._main_mod.is_auth_enabled", return_value=False):
            result = _speed_run_admin_email({})
            assert result == "admin"
