"""Structural tests for the Session 171 investigation run contract."""

from unittest.mock import MagicMock

import pytest

from app.investigation_runs import (
    create_run,
    record_adjudication,
    seal_verdicts,
    transition_status,
)


def build_recording_client(rows=None, *, upsert_error=None):
    """Build a Supabase mock that records table access and every write verb."""
    client = MagicMock()
    table_calls = []
    write_calls = []
    rows = list(rows or [])

    def table(name):
        table_calls.append(name)
        query = MagicMock()

        def record_write(verb):
            def invoke(*args, **kwargs):
                write_calls.append((name, verb, args, kwargs))
                builder = MagicMock()
                result = MagicMock()
                result.data = [args[0]] if args and verb != "delete" else []
                if verb == "upsert" and upsert_error is not None:
                    builder.execute.side_effect = upsert_error
                else:
                    builder.execute.return_value = result
                builder.eq.return_value = builder
                return builder

            return invoke

        query.insert.side_effect = record_write("insert")
        query.upsert.side_effect = record_write("upsert")
        query.update.side_effect = record_write("update")
        query.delete.side_effect = record_write("delete")

        select_builder = MagicMock()
        select_result = MagicMock()
        select_result.data = rows
        select_builder.eq.return_value = select_builder
        select_builder.limit.return_value = select_builder
        select_builder.execute.return_value = select_result
        query.select.return_value = select_builder
        return query

    client.table.side_effect = table
    client.table_calls = table_calls
    client.write_calls = write_calls
    return client


def test_failed_create_is_one_atomic_write_with_zero_followup_writes():
    sb = build_recording_client(upsert_error=ConnectionError("write failed"))

    result = create_run("case-1", {"packet_hash": "abc"}, "manifest-hash", sb=sb)

    assert result is None
    assert len(sb.write_calls) <= 1
    assert [(table, verb) for table, verb, _args, _kwargs in sb.write_calls] == [
        ("investigation_runs", "upsert")
    ]


def test_helpers_never_write_confirmed_identity_or_other_tables():
    pending = {"id": "run-1", "status": "pending", "status_history": []}
    assembling = {"id": "run-1", "status": "assembling", "status_history": []}
    investigating = {"id": "run-1", "status": "investigating", "status_history": []}
    sealed = {"id": "run-1", "status": "sealed", "status_history": []}

    clients = [
        build_recording_client(),
        build_recording_client([investigating]),
        build_recording_client([pending]),
        build_recording_client([sealed]),
        build_recording_client([assembling]),
    ]
    create_run("case-1", {}, "hash-1", sb=clients[0])
    seal_verdicts("run-1", [{"model": "model-a", "verdict": "match"}], sb=clients[1])
    transition_status("run-1", "assembling", sb=clients[2])
    record_adjudication("run-1", {"decision": "accept"}, sb=clients[3])
    transition_status("run-1", "investigating", sb=clients[4])

    writes = [call for client in clients for call in client.write_calls]
    assert writes
    assert all(table == "investigation_runs" for table, _verb, _args, _kwargs in writes)
    assert not {"identities", "photo_faces"}.intersection(
        table for client in clients for table in client.table_calls
    )


def test_create_run_uses_idempotent_upsert_and_stable_key():
    sb = build_recording_client()

    first = create_run("case-1", {"packet_hash": "abc"}, "same-hash", sb=sb)
    second = create_run("case-1", {"packet_hash": "abc"}, "same-hash", sb=sb)

    upserts = [call for call in sb.write_calls if call[1] == "upsert"]
    assert len(upserts) == 2
    for table, _verb, _args, kwargs in upserts:
        assert table == "investigation_runs"
        assert kwargs == {
            "on_conflict": "idempotency_key",
            "ignore_duplicates": True,
        }
    assert first["idempotency_key"] == second["idempotency_key"] == "case-1:same-hash"


def test_create_run_rejects_more_than_three_decisions_before_db_call():
    sb = build_recording_client()

    with pytest.raises(ValueError, match="more than three"):
        create_run("case-1", {}, "hash", requested_decisions=[1, 2, 3, 4], sb=sb)

    assert sb.table_calls == []
    assert sb.write_calls == []


def test_illegal_transition_is_rejected_without_a_write():
    sb = build_recording_client([{"id": "run-1", "status": "pending", "status_history": []}])

    with pytest.raises(ValueError, match="pending -> reviewed"):
        transition_status("run-1", "reviewed", sb=sb)

    assert sb.write_calls == []
