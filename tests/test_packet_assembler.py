"""Hermetic tests for the read-only research-desk packet assembler."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from rhodesli_ml.research_desk.packet_assembler import (
    _pairwise_l2,
    _rank_external_matches,
    assemble_evidence_packet,
)


def build_recording_client(table_rows, *, honor_order=True):
    client = MagicMock()
    client.table_calls = []
    client.write_calls = []
    client.range_calls = []
    client.order_calls = []

    def table(name):
        client.table_calls.append(name)
        query = MagicMock()
        filters = []
        ordered_columns = []
        page = [None, None]

        def chain(*_args, **_kwargs):
            return query

        query.select.side_effect = chain
        query.eq.side_effect = lambda column, value: (filters.append(("eq", column, value)) or query)
        query.in_.side_effect = lambda column, values: (filters.append(("in", column, values)) or query)

        def order(column):
            client.order_calls.append((name, column))
            ordered_columns.append(column)
            return query

        query.order.side_effect = order

        def range_(start, end):
            client.range_calls.append((name, start, end))
            page[:] = [start, end]
            return query

        query.range.side_effect = range_

        for verb in ("insert", "upsert", "update", "delete"):
            def record(*args, _verb=verb, **kwargs):
                client.write_calls.append((name, _verb, args, kwargs))
                return query

            getattr(query, verb).side_effect = record

        def execute():
            rows = list(table_rows.get(name, []))
            for kind, column, value in filters:
                if kind == "eq":
                    rows = [row for row in rows if row.get(column) == value]
                else:
                    rows = [row for row in rows if row.get(column) in value]
            if honor_order:
                for column in reversed(ordered_columns):
                    rows.sort(key=lambda row: (row.get(column) is None, row.get(column)))
            if page[0] is not None:
                rows = rows[page[0] : page[1] + 1]
            response = MagicMock()
            response.data = rows
            return response

        query.execute.side_effect = execute
        return query

    client.table.side_effect = table
    return client


def test_pairwise_l2_identical_and_orthogonal():
    assert _pairwise_l2(np.array([1.0, 0.0]), np.array([1.0, 0.0])) == pytest.approx(0.0)
    assert _pairwise_l2(np.array([1.0, 0.0]), np.array([0.0, 1.0])) == pytest.approx(2**0.5)


def test_rank_external_matches_sorts_excludes_anchors_and_abstains():
    embeddings = {
        "anchor": np.array([1.0, 0.0]),
        "near": np.array([0.8, 0.6]),
        "far": np.array([0.0, 1.0]),
    }
    identities = {"near": "identity-near", "far": "identity-far"}

    result = _rank_external_matches({"anchor": embeddings["anchor"]}, embeddings, identities, 2)

    assert [row["face_id"] for row in result["matches"]] == ["near", "far"]
    assert result["nearest_l2"] == pytest.approx((0.4) ** 0.5)
    assert result["no_confident_match"] is False
    abstain = _rank_external_matches(
        {"anchor": embeddings["anchor"]},
        {"anchor": embeddings["anchor"], "far": embeddings["far"]},
        identities,
        1,
    )
    assert abstain["no_confident_match"] is True


def test_assemble_packet_is_stable_paged_and_never_writes(tmp_path):
    rows = {
        "identities": [
            {
                "identity_id": "subject",
                "name": "Mystery Person",
                "state": "INBOX",
                "anchor_ids": ["face-a", "face-b"],
                "candidate_ids": [],
            },
            {
                "identity_id": "neighbor",
                "name": "Known Neighbor",
                "state": "CONFIRMED",
                "anchor_ids": ["face-c"],
                "candidate_ids": [],
            },
        ],
        "photo_faces": [
            {"face_id": "face-a", "photo_id": "photo-1"},
            {"face_id": "face-b", "photo_id": "photo-2"},
            {"face_id": "face-c", "photo_id": "photo-1"},
        ],
        "gedcom_face_links": [
            {"identity_id": "subject", "gedcom_id": "@I1@", "confidence": 0.3},
            {"identity_id": "neighbor", "gedcom_id": "@I2@", "confidence": 1.0},
        ],
        "photos": [
            {"photo_id": "photo-1", "source": "Album", "collection": "Fox", "source_url": "u1"},
            {"photo_id": "photo-2", "source": "Album", "collection": "Fox", "source_url": "u2"},
        ],
        "date_labels": [
            {"photo_id": "photo-1", "data": {"reasoning": "clothes", "range": [1915, 1920]}},
            {"photo_id": "photo-2", "data": {"reasoning": "setting", "range": [1916, 1921]}},
        ],
        "photo_locations": [
            {"photo_id": "photo-1", "data": {"name": "Detroit", "confidence": "medium"}},
            {"photo_id": "photo-2", "data": {"name": "Detroit", "confidence": "high"}},
        ],
    }
    embeddings_path = tmp_path / "embeddings.npy"
    np.save(
        embeddings_path,
        np.array(
            [
                {"face_id": "face-a", "mu": np.array([1.0, 0.0]), "filename": "a.jpg"},
                {"face_id": "face-b", "mu": np.array([0.9, 0.1]), "filename": "b.jpg"},
                {"face_id": "face-c", "mu": np.array([0.0, 1.0]), "filename": "c.jpg"},
            ],
            dtype=object,
        ),
    )
    sb = build_recording_client(rows)
    gedcom = {
        "@I1@": {"name": "Candidate", "birth_date": "1881", "death_date": None},
        "@I2@": {"name": "Neighbor", "birth_date": "1898", "death_date": "1985"},
    }

    with patch("app.relationship_routes._load_gedcom_individual", side_effect=gedcom.get):
        first = assemble_evidence_packet("subject", sb=sb, embeddings_path=str(embeddings_path))
        second = assemble_evidence_packet("subject", sb=sb, embeddings_path=str(embeddings_path))

    expected_keys = {
        "case_ref", "subject", "anchor_faces", "internal_consistency", "external_match",
        "co_occurrence", "gedcom_context", "date_location", "provenance",
        "candidates_on_file", "manifest",
    }
    assert set(first) == expected_keys
    assert first["manifest"]["packet_sha256"] == second["manifest"]["packet_sha256"]
    assert first["date_location"][0]["location_low_confidence"] is True
    assert sb.write_calls == []
    assert ("identities", 0, 999) in sb.range_calls
    assert ("identities", "identity_id") in sb.order_calls
    assert ("photo_faces", "face_id") in sb.order_calls


def test_packet_seal_is_stable_when_list_reads_are_shuffled(tmp_path):
    rows = {
        "identities": [
            {
                "identity_id": "subject",
                "name": "Subject",
                "state": "INBOX",
                "anchor_ids": ["face-a"],
                "candidate_ids": [],
            },
            {
                "identity_id": "neighbor-a",
                "name": "Neighbor A",
                "state": "CONFIRMED",
                "anchor_ids": ["face-b"],
                "candidate_ids": [],
            },
            {
                "identity_id": "neighbor-b",
                "name": "Neighbor B",
                "state": "CONFIRMED",
                "anchor_ids": ["face-c"],
                "candidate_ids": [],
            },
        ],
        "photo_faces": [
            {"face_id": "face-a", "photo_id": "photo-1"},
            {"face_id": "face-b", "photo_id": "photo-1"},
            {"face_id": "face-c", "photo_id": "photo-1"},
        ],
        "gedcom_face_links": [
            {"identity_id": "subject", "gedcom_id": "@I2@", "confidence": 0.4},
            {"identity_id": "subject", "gedcom_id": "@I1@", "confidence": 0.3},
            {"identity_id": "neighbor-a", "gedcom_id": "@I4@", "confidence": 1.0},
            {"identity_id": "neighbor-b", "gedcom_id": "@I3@", "confidence": 1.0},
        ],
        "photos": [{"photo_id": "photo-1"}],
        "date_labels": [],
        "photo_locations": [],
    }
    sb = build_recording_client(rows, honor_order=False)
    gedcom = {gedcom_id: {"name": gedcom_id} for gedcom_id in ("@I1@", "@I2@", "@I3@", "@I4@")}

    with patch("app.relationship_routes._load_gedcom_individual", side_effect=gedcom.get):
        first = assemble_evidence_packet(
            "subject", sb=sb, embeddings_path=str(tmp_path / "missing.npy")
        )
        rows["photo_faces"] = [rows["photo_faces"][2], rows["photo_faces"][0], rows["photo_faces"][1]]
        rows["gedcom_face_links"] = list(reversed(rows["gedcom_face_links"]))
        second = assemble_evidence_packet(
            "subject", sb=sb, embeddings_path=str(tmp_path / "missing.npy")
        )

    assert first["manifest"]["packet_sha256"] == second["manifest"]["packet_sha256"]


def test_json_string_anchor_ids_are_coerced_to_a_list(tmp_path):
    rows = {
        "identities": [
            {
                "identity_id": "subject",
                "name": "Subject",
                "state": "INBOX",
                "anchor_ids": '["inbox_x"]',
                "candidate_ids": ["candidate-y"],
            }
        ],
        "photo_faces": [],
        "gedcom_face_links": [],
    }

    packet = assemble_evidence_packet(
        "subject", sb=build_recording_client(rows), embeddings_path=str(tmp_path / "missing.npy")
    )

    assert packet["subject"]["anchor_ids"] == ["inbox_x"]


def test_missing_embeddings_returns_empty_match_shapes(tmp_path):
    rows = {
        "identities": [
            {
                "identity_id": "subject",
                "name": "Subject",
                "state": "INBOX",
                "anchor_ids": ["face-a"],
                "candidate_ids": [],
            }
        ],
        "photo_faces": [{"face_id": "face-a", "photo_id": "photo-1"}],
        "gedcom_face_links": [],
        "photos": [{"photo_id": "photo-1"}],
        "date_labels": [],
        "photo_locations": [],
    }

    packet = assemble_evidence_packet(
        "subject", sb=build_recording_client(rows), embeddings_path=str(tmp_path / "missing.npy")
    )

    assert packet["internal_consistency"] == {"pairs": [], "l2": None, "same_person": None}
    assert packet["external_match"] == {
        "matches": [],
        "nearest_l2": None,
        "no_confident_match": True,
    }


def test_no_supabase_returns_empty_error_packet(tmp_path):
    with patch("app.supabase_data.get_supabase_client", return_value=None):
        packet = assemble_evidence_packet("case", embeddings_path=str(tmp_path / "missing.npy"))

    assert packet["error"] == "no supabase"
    assert packet["anchor_faces"] == []
    assert packet["manifest"]["assembled_utc"] is None
