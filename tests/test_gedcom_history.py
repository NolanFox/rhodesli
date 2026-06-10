"""Tests for the GEDCOM R2 history artifact layer (Session 164, PRD-064).

Pure mocks/fakes only — NO network, NO live Supabase. Validates:
- snapshot round-trip
- diff artifact losslessness (typed before/after + hashes survive gzip)
- diff_summary is IDs-only
- upload_and_verify raises on hash mismatch
- artifact_prefix format
"""

from __future__ import annotations

import gzip
import json

import pytest

from rhodesli_ml.importers import gedcom_history as gh
from rhodesli_ml.importers.gedcom_snapshot import canonical_payload_hash, diff_entity_maps


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeR2:
    """In-memory S3/R2-style client."""

    def __init__(self, corrupt: bool = False):
        self.store: dict[str, bytes] = {}
        self.corrupt = corrupt

    def put_object(self, Bucket: str, Key: str, Body: bytes):
        self.store[(Bucket, Key)] = Body

    def get_object(self, Bucket: str, Key: str):
        data = self.store[(Bucket, Key)]
        if self.corrupt:
            data = data + b"\x00corrupt"
        return {"Body": FakeBody(data)}


def _payload(entity_id: str, value):
    """Build a minimal payload with a carried canonical payload_hash."""
    payload = {"id": entity_id, "value": value}
    payload["payload_hash"] = canonical_payload_hash(payload)
    return payload


class FakeBundle:
    """Stands in for a GedcomSnapshotBundle (only the dict attrs are read)."""

    def __init__(self, **entity_maps):
        for entity_type in gh.SNAPSHOT_ENTITY_TYPES:
            setattr(self, entity_type, entity_maps.get(entity_type, {}))


# --------------------------------------------------------------------------- #
# artifact_prefix
# --------------------------------------------------------------------------- #
def test_artifact_prefix_format():
    prefix = gh.artifact_prefix("rhodesli", 9, "f778abcdef0123456789")
    assert prefix == "gedcom-history/rhodesli/v0009-f778abcdef01/"


def test_artifact_prefix_synthetic_when_no_hash():
    prefix = gh.artifact_prefix("rhodesli", 12, None)
    assert prefix == "gedcom-history/rhodesli/v0012-synthetic/"


# --------------------------------------------------------------------------- #
# snapshot round-trip
# --------------------------------------------------------------------------- #
def test_snapshot_round_trip():
    bundle = FakeBundle(
        individuals={
            "@I2@": _payload("@I2@", "two"),
            "@I1@": _payload("@I1@", "one"),
        },
        families={"@F1@": _payload("@F1@", "fam")},
        relationships={"edge1": _payload("edge1", "rel")},
    )
    gz = gh.build_snapshot_jsonl_gz(bundle)
    reconstructed = gh.reconstruct_version_from_snapshot(gz)

    assert reconstructed["individuals"]["@I1@"] == bundle.individuals["@I1@"]
    assert reconstructed["individuals"]["@I2@"] == bundle.individuals["@I2@"]
    assert reconstructed["families"]["@F1@"] == bundle.families["@F1@"]
    assert reconstructed["relationships"]["edge1"] == bundle.relationships["edge1"]


def test_snapshot_is_deterministic():
    bundle_a = FakeBundle(individuals={"@I2@": _payload("@I2@", "b"), "@I1@": _payload("@I1@", "a")})
    bundle_b = FakeBundle(individuals={"@I1@": _payload("@I1@", "a"), "@I2@": _payload("@I2@", "b")})
    assert gh.build_snapshot_jsonl_gz(bundle_a) == gh.build_snapshot_jsonl_gz(bundle_b)


def test_snapshot_carries_payload_hash_not_rehashed():
    payload = _payload("@I1@", "one")
    bundle = FakeBundle(individuals={"@I1@": payload})
    gz = gh.build_snapshot_jsonl_gz(bundle)
    text = gzip.decompress(gz).decode("utf-8").strip()
    record = json.loads(text)
    assert record["payload_hash"] == payload["payload_hash"]


def test_empty_bundle_snapshot_round_trips():
    bundle = FakeBundle()
    gz = gh.build_snapshot_jsonl_gz(bundle)
    assert gh.reconstruct_version_from_snapshot(gz) == {}


# --------------------------------------------------------------------------- #
# diff artifact losslessness
# --------------------------------------------------------------------------- #
def _build_diffs(old_individuals, new_individuals):
    return {
        "individuals": diff_entity_maps("individuals", old_individuals, new_individuals),
        "families": diff_entity_maps("families", {}, {}),
        "relationships": diff_entity_maps("relationships", {}, {}),
        "sources": diff_entity_maps("sources", {}, {}),
        "media_objects": diff_entity_maps("media_objects", {}, {}),
    }


def test_diff_artifact_lossless_added_removed_modified():
    i_keep_old = _payload("@I1@", "v1")
    i_keep_new = _payload("@I1@", "v2")  # modified
    i_removed = _payload("@I2@", "gone")  # removed
    i_added = _payload("@I3@", "new")  # added

    old_map = {"@I1@": i_keep_old, "@I2@": i_removed}
    new_map = {"@I1@": i_keep_new, "@I3@": i_added}

    diffs = _build_diffs(old_map, new_map)
    gz = gh.build_diff_json_gz(
        diffs,
        version_number=10,
        base_version=9,
        source_hash="abc123",
        generated_at="2026-06-09T00:00:00Z",
    )
    doc = gh.parse_diff_json_gz(gz)

    assert doc["schema_version"] == 1
    assert doc["version_number"] == 10
    assert doc["base_version"] == 9
    assert doc["source_hash"] == "abc123"
    assert doc["generated_at"] == "2026-06-09T00:00:00Z"

    indiv = doc["entities"]["individuals"]

    # added: before=null, after=full payload, hashes consistent
    assert len(indiv["added"]) == 1
    added = indiv["added"][0]
    assert added["entity_id"] == "@I3@"
    assert added["change_type"] == "added"
    assert added["before"] is None
    assert added["before_hash"] is None
    assert added["after"] == i_added
    assert added["after_hash"] == i_added["payload_hash"]

    # removed: after=null, before=full payload
    assert len(indiv["removed"]) == 1
    removed = indiv["removed"][0]
    assert removed["entity_id"] == "@I2@"
    assert removed["change_type"] == "removed"
    assert removed["after"] is None
    assert removed["after_hash"] is None
    assert removed["before"] == i_removed
    assert removed["before_hash"] == i_removed["payload_hash"]

    # modified: both before+after
    assert len(indiv["modified"]) == 1
    modified = indiv["modified"][0]
    assert modified["entity_id"] == "@I1@"
    assert modified["change_type"] == "modified"
    assert modified["before"] == i_keep_old
    assert modified["after"] == i_keep_new
    assert modified["before_hash"] == i_keep_old["payload_hash"]
    assert modified["after_hash"] == i_keep_new["payload_hash"]


def test_diff_typed_values_survive_gzip():
    """Typed (non-stringified) values must round-trip through gzip."""
    payload = {"id": "@I1@", "count": 7, "flag": True, "nested": {"a": [1, 2, 3]}}
    payload["payload_hash"] = canonical_payload_hash(payload)
    diffs = _build_diffs({}, {"@I1@": payload})
    gz = gh.build_diff_json_gz(diffs, 1, None, "h", "2026-06-09T00:00:00Z")
    doc = gh.parse_diff_json_gz(gz)
    after = doc["entities"]["individuals"]["added"][0]["after"]
    assert after["count"] == 7
    assert after["flag"] is True
    assert after["nested"] == {"a": [1, 2, 3]}


def test_diff_covers_all_five_entity_types():
    diffs = {
        et: diff_entity_maps(et, {}, {f"x_{et}": _payload(f"x_{et}", et)})
        for et in gh.DIFF_ENTITY_TYPES
    }
    gz = gh.build_diff_json_gz(diffs, 1, None, "h", "2026-06-09T00:00:00Z")
    doc = gh.parse_diff_json_gz(gz)
    for et in gh.DIFF_ENTITY_TYPES:
        assert et in doc["entities"]
        assert len(doc["entities"][et]["added"]) == 1


# --------------------------------------------------------------------------- #
# diff_summary
# --------------------------------------------------------------------------- #
def test_diff_summary_ids_only():
    old_map = {"@I1@": _payload("@I1@", "v1"), "@I2@": _payload("@I2@", "gone")}
    new_map = {"@I1@": _payload("@I1@", "v2"), "@I3@": _payload("@I3@", "new")}
    diffs = _build_diffs(old_map, new_map)
    summary = gh.build_diff_summary(diffs)

    indiv = summary["individuals"]
    assert indiv["added"] == 1
    assert indiv["modified"] == 1
    assert indiv["removed"] == 1
    assert indiv["ids"]["added"] == ["@I3@"]
    assert indiv["ids"]["modified"] == ["@I1@"]
    assert indiv["ids"]["removed"] == ["@I2@"]
    # IDs only — no payloads leaked into the summary
    serialized = json.dumps(summary)
    assert "payload_hash" not in serialized
    assert '"value"' not in serialized


# --------------------------------------------------------------------------- #
# upload_and_verify
# --------------------------------------------------------------------------- #
def test_upload_and_verify_success():
    r2 = FakeR2()
    artifacts = {"snapshot.jsonl.gz": b"snapshot-bytes", "diff.json.gz": b"diff-bytes"}
    shas = gh.upload_and_verify_artifacts(r2, "bucket", "prefix/", artifacts)
    assert shas["snapshot.jsonl.gz"] == gh.sha256_bytes(b"snapshot-bytes")
    assert shas["diff.json.gz"] == gh.sha256_bytes(b"diff-bytes")
    assert ("bucket", "prefix/snapshot.jsonl.gz") in r2.store


def test_upload_and_verify_skips_none():
    r2 = FakeR2()
    artifacts = {"raw.ged.gz": None, "snapshot.jsonl.gz": b"snap"}
    shas = gh.upload_and_verify_artifacts(r2, "bucket", "prefix/", artifacts)
    assert "raw.ged.gz" not in shas
    assert "snapshot.jsonl.gz" in shas
    assert ("bucket", "prefix/raw.ged.gz") not in r2.store


def test_upload_and_verify_raises_on_hash_mismatch():
    r2 = FakeR2(corrupt=True)  # corrupts on download
    with pytest.raises(ValueError, match="verification failed"):
        gh.upload_and_verify_artifacts(r2, "bucket", "prefix/", {"snapshot.jsonl.gz": b"data"})


# --------------------------------------------------------------------------- #
# download helpers
# --------------------------------------------------------------------------- #
def test_download_snapshot_and_diff_round_trip_via_r2():
    r2 = FakeR2()
    bundle = FakeBundle(individuals={"@I1@": _payload("@I1@", "one")})
    snapshot_gz = gh.build_snapshot_jsonl_gz(bundle)
    diff_gz = gh.build_diff_json_gz(
        _build_diffs({}, {"@I1@": _payload("@I1@", "one")}),
        1,
        None,
        "h",
        "2026-06-09T00:00:00Z",
    )
    prefix = "gedcom-history/rhodesli/v0001-h/"
    gh.upload_and_verify_artifacts(
        r2, "bucket", prefix, {"snapshot.jsonl.gz": snapshot_gz, "diff.json.gz": diff_gz}
    )

    got_snapshot = gh.download_snapshot(r2, "bucket", prefix)
    assert gh.reconstruct_version_from_snapshot(got_snapshot)["individuals"]["@I1@"]["value"] == "one"

    got_diff = gh.download_diff(r2, "bucket", prefix)
    assert got_diff["entities"]["individuals"]["added"][0]["entity_id"] == "@I1@"
