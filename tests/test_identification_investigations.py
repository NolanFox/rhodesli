"""Tests for identification_investigations Supabase helpers (Session 149).

Tests log_identification_investigation(), get_investigations_for_family(),
and get_investigation() with mocked Supabase client.
"""

from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_sb():
    """Mock Supabase client with chained method support."""
    client = MagicMock()
    mock_result = MagicMock()
    mock_result.data = []
    # insert chain
    client.table.return_value.insert.return_value.execute.return_value = mock_result
    # select chains
    client.table.return_value.select.return_value.ilike.return_value.order.return_value.execute.return_value = (
        mock_result
    )
    client.table.return_value.select.return_value.ilike.return_value.eq.return_value.order.return_value.execute.return_value = mock_result
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_result
    return client


@pytest.fixture
def sample_investigation_data():
    """Minimal valid investigation data."""
    return {
        "investigation_name": "Test Investigation",
        "session_id": "149",
        "target_name": "Jane Doe",
        "community_id": "test-community",
        "target_birth_year": 1920,
        "target_death_year": 1990,
        "target_relationship": "Mother of John Doe",
        "target_spouse": "Richard Doe",
        "target_geography": "New York",
        "known_references": [{"identity_id": "test-id-1", "name": "John Doe", "anchor_count": 10, "role": "son"}],
        "methodology_steps": [{"step_number": 1, "description": "Built centroid", "outcome": "10-face centroid"}],
        "candidates": [
            {
                "face_id": "inbox_test123",
                "photo_id": "ABCD1234",
                "embedding_distance": 0.87,
                "decision": "ACCEPT",
                "evidence": "Strong visual match",
            }
        ],
        "clusters": [
            {
                "cluster_name": "cluster_1",
                "face_count": 5,
                "photo_count": 3,
                "status": "CANDIDATE",
            }
        ],
        "outcome": "CONFIRMED",
        "confidence_overall": "VERY_HIGH",
        "signals_used": {"event_context": {"strength": "STRONG"}},
        "also_identified": [],
        "feature_ideas": ["Idea 1"],
        "investigator": "claude",
    }


# =========================================================================
# log_identification_investigation tests
# =========================================================================


class TestLogIdentificationInvestigation:
    """Tests for log_identification_investigation."""

    def test_logs_successful_investigation(self, mock_sb, sample_investigation_data):
        """Inserts a row with all provided fields."""
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_identification_investigation

            result = log_identification_investigation(sample_investigation_data)

        assert result is True
        mock_sb.table.assert_called_with("identification_investigations")
        call_row = mock_sb.table.return_value.insert.call_args[0][0]
        assert call_row["investigation_name"] == "Test Investigation"
        assert call_row["session_id"] == "149"
        assert call_row["target_name"] == "Jane Doe"
        assert call_row["target_birth_year"] == 1920
        assert call_row["community_id"] == "test-community"
        assert call_row["outcome"] == "CONFIRMED"
        assert call_row["confidence_overall"] == "VERY_HIGH"
        assert len(call_row["candidates"]) == 1
        assert call_row["candidates"][0]["face_id"] == "inbox_test123"

    def test_logs_minimal_investigation(self, mock_sb):
        """Inserts with only required fields."""
        data = {
            "investigation_name": "Minimal",
            "session_id": "149",
            "target_name": "Unknown Person",
        }
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_identification_investigation

            result = log_identification_investigation(data)

        assert result is True
        call_row = mock_sb.table.return_value.insert.call_args[0][0]
        assert call_row["investigation_name"] == "Minimal"
        assert call_row["session_id"] == "149"
        assert call_row["target_name"] == "Unknown Person"
        # Optional fields should not be present
        assert "community_id" not in call_row
        assert "target_birth_year" not in call_row

    def test_returns_false_missing_investigation_name(self, mock_sb):
        """Returns False when investigation_name is missing."""
        data = {"session_id": "149", "target_name": "Jane Doe"}
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_identification_investigation

            result = log_identification_investigation(data)

        assert result is False
        mock_sb.table.return_value.insert.assert_not_called()

    def test_returns_false_missing_session_id(self, mock_sb):
        """Returns False when session_id is missing."""
        data = {"investigation_name": "Test", "target_name": "Jane Doe"}
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_identification_investigation

            result = log_identification_investigation(data)

        assert result is False

    def test_returns_false_missing_target_name(self, mock_sb):
        """Returns False when target_name is missing."""
        data = {"investigation_name": "Test", "session_id": "149"}
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_identification_investigation

            result = log_identification_investigation(data)

        assert result is False

    def test_returns_false_when_supabase_unavailable(self):
        """Returns False when no Supabase client."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import log_identification_investigation

            result = log_identification_investigation(
                {"investigation_name": "X", "session_id": "1", "target_name": "Y"}
            )

        assert result is False

    def test_returns_false_on_supabase_error(self, mock_sb):
        """Returns False when Supabase insert raises an error."""
        mock_sb.table.return_value.insert.return_value.execute.side_effect = ConnectionError("fail")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_identification_investigation

            result = log_identification_investigation(
                {"investigation_name": "X", "session_id": "1", "target_name": "Y"}
            )

        assert result is False

    def test_skips_none_optional_fields(self, mock_sb):
        """None values for optional fields are excluded from the row."""
        data = {
            "investigation_name": "Test",
            "session_id": "149",
            "target_name": "Jane",
            "community_id": None,
            "target_birth_year": None,
        }
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_identification_investigation

            log_identification_investigation(data)

        call_row = mock_sb.table.return_value.insert.call_args[0][0]
        assert "community_id" not in call_row
        assert "target_birth_year" not in call_row


# =========================================================================
# get_investigations_for_family tests
# =========================================================================


class TestGetInvestigationsForFamily:
    """Tests for get_investigations_for_family."""

    def test_returns_matching_investigations(self, mock_sb):
        """Returns investigations matching target name."""
        mock_result = MagicMock()
        mock_result.data = [
            {"id": "uuid-1", "investigation_name": "Nellie Kubrin", "target_name": "Nellie Kubrin"},
        ]
        mock_sb.table.return_value.select.return_value.ilike.return_value.order.return_value.execute.return_value = (
            mock_result
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import get_investigations_for_family

            results = get_investigations_for_family("Nellie")

        assert len(results) == 1
        assert results[0]["target_name"] == "Nellie Kubrin"
        # Verify ilike was called with wildcard pattern
        mock_sb.table.return_value.select.return_value.ilike.assert_called_with("target_name", "%Nellie%")

    def test_filters_by_community(self, mock_sb):
        """Applies community filter when provided."""
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb.table.return_value.select.return_value.ilike.return_value.eq.return_value.order.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import get_investigations_for_family

            get_investigations_for_family("Fader", community_id="fader")

        mock_sb.table.return_value.select.return_value.ilike.return_value.eq.assert_called_with("community_id", "fader")

    def test_returns_empty_list_when_supabase_unavailable(self):
        """Returns empty list when no Supabase client."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import get_investigations_for_family

            results = get_investigations_for_family("Anyone")

        assert results == []

    def test_returns_empty_list_on_error(self, mock_sb):
        """Returns empty list on Supabase error."""
        mock_sb.table.return_value.select.return_value.ilike.return_value.order.return_value.execute.side_effect = (
            ConnectionError("fail")
        )
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import get_investigations_for_family

            results = get_investigations_for_family("Anyone")

        assert results == []

    def test_returns_empty_list_when_no_data(self, mock_sb):
        """Returns empty list when query returns None data."""
        mock_result = MagicMock()
        mock_result.data = None
        mock_sb.table.return_value.select.return_value.ilike.return_value.order.return_value.execute.return_value = (
            mock_result
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import get_investigations_for_family

            results = get_investigations_for_family("Ghost")

        assert results == []


# =========================================================================
# get_investigation tests
# =========================================================================


class TestGetInvestigation:
    """Tests for get_investigation."""

    def test_returns_investigation_by_id(self, mock_sb):
        """Returns single investigation dict when found."""
        mock_result = MagicMock()
        mock_result.data = [{"id": "uuid-123", "investigation_name": "Test", "target_name": "Jane Doe"}]
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            mock_result
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import get_investigation

            result = get_investigation("uuid-123")

        assert result is not None
        assert result["id"] == "uuid-123"
        assert result["investigation_name"] == "Test"

    def test_returns_none_when_not_found(self, mock_sb):
        """Returns None when ID does not match any row."""
        mock_result = MagicMock()
        mock_result.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            mock_result
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import get_investigation

            result = get_investigation("nonexistent-uuid")

        assert result is None

    def test_returns_none_when_supabase_unavailable(self):
        """Returns None when no Supabase client."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import get_investigation

            result = get_investigation("any-uuid")

        assert result is None

    def test_returns_none_on_error(self, mock_sb):
        """Returns None on Supabase error."""
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = (
            ConnectionError("fail")
        )
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import get_investigation

            result = get_investigation("any-uuid")

        assert result is None
