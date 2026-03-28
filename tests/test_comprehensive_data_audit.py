"""Tests for scripts/comprehensive_data_audit.py.

Each check is tested independently with mocked Supabase responses.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.comprehensive_data_audit import (
    AuditResult,
    check_birth_year_estimates,
    check_community_coverage,
    check_date_labels_vs_gemini,
    check_face_alignment_completeness,
    check_gedcom_face_links,
    check_identity_faces_exist,
    check_identities_integrity,
    check_merge_chain_integrity,
    check_multi_claimed_faces,
    check_orphaned_faces,
    check_photo_faces_coverage,
    check_photo_locations_completeness,
    check_table_counts,
)


def _make_client(table_data: dict[str, list[dict]]) -> MagicMock:
    """Create a mock Supabase client that returns predefined data per table."""
    client = MagicMock()

    def table_fn(table_name):
        mock_table = MagicMock()
        rows = table_data.get(table_name, [])

        # Support .select().range().execute() pattern (paginated)
        def select_fn(*args, **kwargs):
            mock_query = MagicMock()

            def range_fn(start, end):
                mock_range = MagicMock()
                result = MagicMock()
                result.data = rows[start : end + 1]
                result.count = len(rows)
                mock_range.execute.return_value = result
                return mock_range

            mock_query.range = range_fn

            # Also support .limit(0).execute() for count
            def limit_fn(n):
                mock_limit = MagicMock()
                result = MagicMock()
                result.data = rows[:n] if n > 0 else []
                result.count = len(rows)
                mock_limit.execute.return_value = result
                return mock_limit

            mock_query.limit = limit_fn
            mock_query.execute.return_value = MagicMock(data=rows, count=len(rows))
            return mock_query

        mock_table.select = select_fn
        return mock_table

    client.table = table_fn
    return client


class TestAuditResult:
    def test_pass_by_default(self):
        r = AuditResult("test")
        assert r.passed is True

    def test_fail_sets_passed_false(self):
        r = AuditResult("test")
        r.fail("something wrong")
        assert r.passed is False
        assert "FAIL" in str(r)

    def test_warn_does_not_fail(self):
        r = AuditResult("test")
        r.warn("just a warning")
        assert r.passed is True

    def test_counts_in_output(self):
        r = AuditResult("test")
        r.set_count("items", 42)
        assert "items=42" in str(r)


class TestTableCounts:
    def test_passes_with_sufficient_data(self):
        data = {
            "identities": [{"id": i} for i in range(200)],
            "photos": [{"id": i} for i in range(200)],
            "photo_faces": [{"id": i} for i in range(200)],
            "communities": [{"id": 1}],
            "photo_communities": [{"id": 1}],
            "identity_communities": [{"id": 1}],
            "annotations": [],
            "relationships": [],
            "gedcom_matches": [],
            "date_labels": [],
            "photo_locations": [],
            "face_gemini_alignments": [],
            "gemini_api_calls": [],
            "birth_year_estimates": [],
            "person_comments": [],
            "audit_log": [],
            "ml_runs": [],
            "ml_proposals": [],
            "notifications": [],
            "pending_uploads": [],
            "gedcom_face_links": [],
        }
        client = _make_client(data)
        result = check_table_counts(client, verbose=False)
        assert result.passed is True

    def test_fails_with_empty_critical_table(self):
        data = {
            "identities": [],  # Empty!
            "photos": [{"id": i} for i in range(200)],
            "photo_faces": [{"id": i} for i in range(200)],
            "communities": [{"id": 1}],
            "photo_communities": [{"id": 1}],
            "identity_communities": [{"id": 1}],
            "annotations": [],
            "relationships": [],
            "gedcom_matches": [],
            "date_labels": [],
            "photo_locations": [],
            "face_gemini_alignments": [],
            "gemini_api_calls": [],
            "birth_year_estimates": [],
            "person_comments": [],
            "audit_log": [],
            "ml_runs": [],
            "ml_proposals": [],
            "notifications": [],
            "pending_uploads": [],
            "gedcom_face_links": [],
        }
        client = _make_client(data)
        result = check_table_counts(client, verbose=False)
        assert result.passed is False
        assert any("identities" in m for m in result.messages)


class TestIdentitiesIntegrity:
    def test_valid_identities_pass(self):
        data = {
            "identities": [
                {
                    "identity_id": "id1",
                    "name": "Alice",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "merged_into": None,
                },
                {
                    "identity_id": "id2",
                    "name": "Bob",
                    "state": "PROPOSED",
                    "anchor_ids": [],
                    "candidate_ids": ["f2"],
                    "negative_ids": [],
                    "merged_into": None,
                },
            ]
        }
        client = _make_client(data)
        result = check_identities_integrity(client, verbose=False)
        assert result.passed is True

    def test_invalid_state_fails(self):
        data = {
            "identities": [
                {
                    "identity_id": "id1",
                    "name": "Bad",
                    "state": "INVALID",
                    "anchor_ids": [],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "merged_into": None,
                },
            ]
        }
        client = _make_client(data)
        result = check_identities_integrity(client, verbose=False)
        assert result.passed is False

    def test_confirmed_without_anchors_fails(self):
        data = {
            "identities": [
                {
                    "identity_id": "id1",
                    "name": "Empty Confirmed",
                    "state": "CONFIRMED",
                    "anchor_ids": [],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "merged_into": None,
                },
            ]
        }
        client = _make_client(data)
        result = check_identities_integrity(client, verbose=False)
        assert result.passed is False

    def test_confirmed_merged_with_no_anchors_ok(self):
        """Merged CONFIRMED identities don't need anchors."""
        data = {
            "identities": [
                {
                    "identity_id": "id1",
                    "name": "Merged",
                    "state": "CONFIRMED",
                    "anchor_ids": [],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "merged_into": "id2",
                },
            ]
        }
        client = _make_client(data)
        result = check_identities_integrity(client, verbose=False)
        assert result.passed is True


class TestPhotoFacesCoverage:
    def test_complete_coverage_passes(self):
        data = {
            "photos": [
                {"photo_id": "p1", "face_count": 2},
            ],
            "photo_faces": [
                {"photo_id": "p1", "face_id": "f1"},
                {"photo_id": "p1", "face_id": "f2"},
            ],
        }
        client = _make_client(data)
        result = check_photo_faces_coverage(client, verbose=False)
        assert result.passed is True

    def test_missing_photo_faces_fails(self):
        data = {
            "photos": [
                {"photo_id": "p1", "face_count": 2},
            ],
            "photo_faces": [],  # No entries!
        }
        client = _make_client(data)
        result = check_photo_faces_coverage(client, verbose=False)
        assert result.passed is False

    def test_photos_with_no_faces_ok(self):
        data = {
            "photos": [
                {"photo_id": "p1", "face_count": 0},
            ],
            "photo_faces": [],
        }
        client = _make_client(data)
        result = check_photo_faces_coverage(client, verbose=False)
        assert result.passed is True


class TestIdentityFacesExist:
    def test_all_faces_exist_passes(self):
        data = {
            "identities": [
                {"identity_id": "id1", "name": "A", "state": "CONFIRMED", "anchor_ids": ["f1"], "merged_into": None},
            ],
            "photo_faces": [{"face_id": "f1"}],
        }
        client = _make_client(data)
        result = check_identity_faces_exist(client, verbose=False)
        assert result.passed is True

    def test_missing_face_fails(self):
        data = {
            "identities": [
                {
                    "identity_id": "id1",
                    "name": "A",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f1", "f_missing"],
                    "merged_into": None,
                },
            ],
            "photo_faces": [{"face_id": "f1"}],
        }
        client = _make_client(data)
        result = check_identity_faces_exist(client, verbose=False)
        assert result.passed is False
        assert result.counts["orphan_anchor_faces"] == 1


class TestOrphanedFaces:
    def test_all_claimed_passes(self):
        data = {
            "photo_faces": [{"face_id": "f1"}],
            "identities": [
                {"identity_id": "id1", "anchor_ids": ["f1"], "candidate_ids": [], "merged_into": None},
            ],
        }
        client = _make_client(data)
        result = check_orphaned_faces(client, verbose=False)
        assert result.counts["orphaned_faces"] == 0

    def test_orphaned_face_warns(self):
        data = {
            "photo_faces": [{"face_id": "f1"}, {"face_id": "f_orphan"}],
            "identities": [
                {"identity_id": "id1", "anchor_ids": ["f1"], "candidate_ids": [], "merged_into": None},
            ],
        }
        client = _make_client(data)
        result = check_orphaned_faces(client, verbose=False)
        assert result.counts["orphaned_faces"] == 1


class TestMultiClaimedFaces:
    def test_no_multi_claim_passes(self):
        data = {
            "identities": [
                {
                    "identity_id": "id1",
                    "name": "A",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f1"],
                    "candidate_ids": [],
                    "merged_into": None,
                },
                {
                    "identity_id": "id2",
                    "name": "B",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f2"],
                    "candidate_ids": [],
                    "merged_into": None,
                },
            ],
        }
        client = _make_client(data)
        result = check_multi_claimed_faces(client, verbose=False)
        assert result.passed is True

    def test_multi_claim_fails(self):
        data = {
            "identities": [
                {
                    "identity_id": "id1",
                    "name": "A",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f1"],
                    "candidate_ids": [],
                    "merged_into": None,
                },
                {
                    "identity_id": "id2",
                    "name": "B",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f1"],
                    "candidate_ids": [],
                    "merged_into": None,
                },
            ],
        }
        client = _make_client(data)
        result = check_multi_claimed_faces(client, verbose=False)
        assert result.passed is False
        assert result.counts["multi_claimed_faces"] == 1


class TestDateLabelsVsGemini:
    def test_matching_counts_pass(self):
        data = {
            "date_labels": [{"photo_id": "p1"}],
            "gemini_api_calls": [
                {
                    "photo_id": "p1",
                    "call_type": "date_estimation",
                    "status": "success",
                    "gemini_config": {"call_type": "date_estimation"},
                },
            ],
        }
        client = _make_client(data)
        result = check_date_labels_vs_gemini(client, verbose=False)
        assert result.passed is True

    def test_missing_date_label_fails(self):
        data = {
            "date_labels": [],  # No labels!
            "gemini_api_calls": [
                {
                    "photo_id": "p1",
                    "call_type": "date_estimation",
                    "status": "success",
                    "gemini_config": {"call_type": "date_estimation"},
                },
            ],
        }
        client = _make_client(data)
        result = check_date_labels_vs_gemini(client, verbose=False)
        assert result.passed is False
        assert result.counts["gemini_calls_without_date_labels"] == 1


class TestCommunityCoverage:
    def test_all_assigned_passes(self):
        data = {
            "photos": [{"photo_id": "p1"}],
            "photo_communities": [{"photo_id": "p1"}],
            "identities": [{"identity_id": "id1", "merged_into": None}],
            "identity_communities": [{"identity_id": "id1"}],
        }
        client = _make_client(data)
        result = check_community_coverage(client, verbose=False)
        assert result.counts["photos_without_community"] == 0
        assert result.counts["identities_without_community"] == 0

    def test_missing_community_warns(self):
        data = {
            "photos": [{"photo_id": "p1"}, {"photo_id": "p2"}],
            "photo_communities": [{"photo_id": "p1"}],
            "identities": [{"identity_id": "id1", "merged_into": None}],
            "identity_communities": [],
        }
        client = _make_client(data)
        result = check_community_coverage(client, verbose=False)
        assert result.counts["photos_without_community"] == 1
        assert result.counts["identities_without_community"] == 1


class TestMergeChainIntegrity:
    def test_clean_merges_pass(self):
        data = {
            "identities": [
                {"identity_id": "id1", "merged_into": "id2"},
                {"identity_id": "id2", "merged_into": None},
            ]
        }
        client = _make_client(data)
        result = check_merge_chain_integrity(client, verbose=False)
        assert result.counts["circular_merges"] == 0
        assert result.counts["dangling_merges"] == 0

    def test_dangling_merge_warns(self):
        data = {
            "identities": [
                {"identity_id": "id1", "merged_into": "nonexistent"},
            ]
        }
        client = _make_client(data)
        result = check_merge_chain_integrity(client, verbose=False)
        assert result.counts["dangling_merges"] == 1

    def test_multi_hop_merge_warns(self):
        data = {
            "identities": [
                {"identity_id": "id1", "merged_into": "id2"},
                {"identity_id": "id2", "merged_into": "id3"},
                {"identity_id": "id3", "merged_into": None},
            ]
        }
        client = _make_client(data)
        result = check_merge_chain_integrity(client, verbose=False)
        assert result.counts["multi_hop_merges"] == 1

    def test_circular_merge_fails(self):
        data = {
            "identities": [
                {"identity_id": "id1", "merged_into": "id2"},
                {"identity_id": "id2", "merged_into": "id1"},
            ]
        }
        client = _make_client(data)
        result = check_merge_chain_integrity(client, verbose=False)
        assert result.passed is False
        assert result.counts["circular_merges"] > 0


class TestGedcomFaceLinks:
    def test_valid_links_pass(self):
        data = {
            "gedcom_face_links": [
                {"identity_id": "id1", "gedcom_id": "g1"},
            ],
            "identities": [
                {"identity_id": "id1", "merged_into": None},
            ],
        }
        client = _make_client(data)
        result = check_gedcom_face_links(client, verbose=False)
        assert result.passed is True

    def test_dangling_link_fails(self):
        data = {
            "gedcom_face_links": [
                {"identity_id": "nonexistent", "gedcom_id": "g1"},
            ],
            "identities": [
                {"identity_id": "id1", "merged_into": None},
            ],
        }
        client = _make_client(data)
        result = check_gedcom_face_links(client, verbose=False)
        assert result.passed is False

    def test_link_to_merged_warns(self):
        data = {
            "gedcom_face_links": [
                {"identity_id": "id1", "gedcom_id": "g1"},
            ],
            "identities": [
                {"identity_id": "id1", "merged_into": "id2"},
                {"identity_id": "id2", "merged_into": None},
            ],
        }
        client = _make_client(data)
        result = check_gedcom_face_links(client, verbose=False)
        assert result.counts["links_to_merged"] == 1


class TestFaceAlignmentCompleteness:
    def test_with_data_passes(self):
        data = {
            "face_gemini_alignments": [{"photo_id": "p1"}],
            "photos": [{"id": i} for i in range(10)],
        }
        client = _make_client(data)
        result = check_face_alignment_completeness(client, verbose=True)
        assert result.passed is True

    def test_empty_warns(self):
        data = {
            "face_gemini_alignments": [],
            "photos": [{"id": i} for i in range(10)],
        }
        client = _make_client(data)
        result = check_face_alignment_completeness(client, verbose=False)
        assert any("WARN" in m for m in result.messages)


class TestBirthYearEstimates:
    def test_reports_coverage(self):
        data = {
            "birth_year_estimates": [{"identity_id": "id1"}],
            "identities": [
                {"identity_id": "id1", "state": "CONFIRMED", "merged_into": None},
                {"identity_id": "id2", "state": "CONFIRMED", "merged_into": None},
            ],
        }
        client = _make_client(data)
        result = check_birth_year_estimates(client, verbose=True)
        assert result.counts["confirmed_with_estimates"] == 1
        assert result.counts["confirmed_identities"] == 2


class TestStringEncodedArrays:
    """Verify checks handle string-encoded JSON arrays (Lesson 142)."""

    def test_string_anchor_ids_handled(self):
        data = {
            "identities": [
                {
                    "identity_id": "id1",
                    "name": "A",
                    "state": "CONFIRMED",
                    "anchor_ids": '["f1", "f2"]',
                    "candidate_ids": "[]",
                    "negative_ids": "[]",
                    "merged_into": None,
                },
            ]
        }
        client = _make_client(data)
        result = check_identities_integrity(client, verbose=False)
        # Should not fail — f1 and f2 are valid anchors
        assert result.passed is True

    def test_string_face_count_in_photos(self):
        """face_count stored as string should be handled gracefully."""
        data = {
            "photos": [
                {"photo_id": "p1", "face_count": "1"},
            ],
            "photo_faces": [
                {"photo_id": "p1", "face_id": "f1"},
            ],
        }
        client = _make_client(data)
        result = check_photo_faces_coverage(client, verbose=False)
        assert result.passed is True
