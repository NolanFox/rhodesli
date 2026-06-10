"""GEDCOM R2 history artifact layer (PRD-064 Option B-plus, Session 164).

This module is the *lossless source of truth* for GEDCOM history. The canonical
Supabase tables hold only current-state (one row per entity); the full payload
history lives in content-addressed R2 artifacts produced here.

Three artifact types per applied version, under
``gedcom-history/<community>/v<NNNN>-<source_hash12>/``:

- ``raw.ged.gz``      — original uploaded GEDCOM bytes (omitted for compensating
                        / unwind versions, which correspond to no GEDCOM file).
- ``snapshot.jsonl.gz`` — canonical current-state at the version: one JSON line
                        per entity for ALL bundle types, ``{entity_type,
                        entity_id, payload, payload_hash}``. Lossless.
- ``diff.json.gz``    — typed diff vs the base version (added/modified/removed
                        with full before/after payloads + hashes).

THE HASH contract (Codex P1-2 / plan R2):
- entity ``payload_hash`` = ``gedcom_snapshot.canonical_payload_hash`` as already
  computed at bundle build time. We NEVER re-hash a payload here; we reuse the
  ``payload_hash`` key carried on each payload.
- artifact SHA-256 = ``hashlib.sha256`` of the COMPRESSED ``.gz`` bytes.

All functions are pure except the R2 helpers, which take an injectable client
(so tests mock it). boto3 / network imports stay lazy — this module imports
cleanly with no env vars and no network.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from typing import Any

from rhodesli_ml.importers.gedcom_snapshot import canonical_json_dumps


# The entity types carried in a GedcomSnapshotBundle, in deterministic order.
SNAPSHOT_ENTITY_TYPES: tuple[str, ...] = (
    "individuals",
    "families",
    "relationships",
    "sources",
    "media_objects",
    "events",
    "records",
)

# The entity types for which we emit a typed diff. events/records are derived /
# raw (preserved in snapshot + raw.ged.gz) so they are NOT diffed (plan R4).
DIFF_ENTITY_TYPES: tuple[str, ...] = (
    "individuals",
    "families",
    "relationships",
    "sources",
    "media_objects",
)

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# Hash helpers
# --------------------------------------------------------------------------- #
def sha256_bytes(data: bytes) -> str:
    """SHA-256 of raw bytes (used for compressed-artifact hashing)."""
    return hashlib.sha256(data).hexdigest()


def _payload_hash(payload: dict[str, Any] | None) -> str | None:
    """Return the payload's carried canonical hash (never re-hashes)."""
    if payload is None:
        return None
    return payload.get("payload_hash")


def _gzip_bytes(text: str) -> bytes:
    """Deterministic gzip (mtime=0) of a UTF-8 string."""
    return gzip.compress(text.encode("utf-8"), mtime=0)


def _gunzip_text(data: bytes) -> str:
    return gzip.decompress(data).decode("utf-8")


# --------------------------------------------------------------------------- #
# Snapshot artifact (lossless current-state)
# --------------------------------------------------------------------------- #
def build_snapshot_jsonl_gz(bundle) -> bytes:
    """Gzip of JSONL, one line per entity for ALL bundle entity types.

    Each line: ``{"entity_type", "entity_id", "payload", "payload_hash"}``.
    Ordering is deterministic (entity_type order, then entity_id sorted) so the
    compressed bytes are reproducible for the same bundle.
    """
    lines: list[str] = []
    for entity_type in SNAPSHOT_ENTITY_TYPES:
        entity_map: dict[str, dict[str, Any]] = getattr(bundle, entity_type, {}) or {}
        for entity_id in sorted(entity_map):
            payload = entity_map[entity_id]
            record = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": payload,
                "payload_hash": _payload_hash(payload),
            }
            lines.append(canonical_json_dumps(record))
    text = "\n".join(lines)
    if text:
        text += "\n"
    return _gzip_bytes(text)


def reconstruct_version_from_snapshot(
    snapshot_jsonl_gz_bytes: bytes,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Inverse of :func:`build_snapshot_jsonl_gz`.

    Returns ``{entity_type -> {entity_id -> payload}}``. Round-trips the
    snapshot artifact exactly.
    """
    text = _gunzip_text(snapshot_jsonl_gz_bytes)
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        entity_type = record["entity_type"]
        entity_id = record["entity_id"]
        result.setdefault(entity_type, {})[entity_id] = record["payload"]
    return result


# --------------------------------------------------------------------------- #
# Diff artifact (typed, lossless)
# --------------------------------------------------------------------------- #
def _diff_items_from_entity_diff(
    entity_type: str, entity_diff: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Convert a ``diff_entity_maps`` result into typed diff items.

    ``diff_entity_maps`` returns:
      added:    [{entity_id, new_payload}]
      removed:  [{entity_id, old_payload}]
      modified: [{entity_id, old_payload, new_payload, changes}]

    We map these to typed items carrying full before/after payloads + hashes.
    """
    added_items: list[dict[str, Any]] = []
    for entry in entity_diff.get("added", []):
        after = entry["new_payload"]
        added_items.append(
            {
                "entity_type": entity_type,
                "entity_id": entry["entity_id"],
                "change_type": "added",
                "before": None,
                "after": after,
                "before_hash": None,
                "after_hash": _payload_hash(after),
            }
        )

    removed_items: list[dict[str, Any]] = []
    for entry in entity_diff.get("removed", []):
        before = entry["old_payload"]
        removed_items.append(
            {
                "entity_type": entity_type,
                "entity_id": entry["entity_id"],
                "change_type": "removed",
                "before": before,
                "after": None,
                "before_hash": _payload_hash(before),
                "after_hash": None,
            }
        )

    modified_items: list[dict[str, Any]] = []
    for entry in entity_diff.get("modified", []):
        before = entry["old_payload"]
        after = entry["new_payload"]
        modified_items.append(
            {
                "entity_type": entity_type,
                "entity_id": entry["entity_id"],
                "change_type": "modified",
                "before": before,
                "after": after,
                "before_hash": _payload_hash(before),
                "after_hash": _payload_hash(after),
            }
        )

    return {"added": added_items, "modified": modified_items, "removed": removed_items}


def build_diff_json_gz(
    diffs_by_type: dict[str, dict[str, Any]],
    version_number: int,
    base_version: int | None,
    source_hash: str | None,
    generated_at: str,
) -> bytes:
    """Gzip of one JSON doc describing the typed diff for this version.

    ``diffs_by_type`` maps entity_type -> output of ``diff_entity_maps``.
    ``generated_at`` is passed in (ISO string) — we never call datetime.now().
    """
    entities: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for entity_type in DIFF_ENTITY_TYPES:
        entity_diff = diffs_by_type.get(entity_type)
        if entity_diff is None:
            continue
        entities[entity_type] = _diff_items_from_entity_diff(entity_type, entity_diff)

    doc = {
        "schema_version": SCHEMA_VERSION,
        "version_number": version_number,
        "base_version": base_version,
        "source_hash": source_hash,
        "generated_at": generated_at,
        "entities": entities,
    }
    return _gzip_bytes(canonical_json_dumps(doc))


def build_diff_summary(diffs_by_type: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Compact per-type summary: counts + changed entity IDs (IDs only).

    Returns ``{<type>: {added, modified, removed, ids: {added:[...],
    modified:[...], removed:[...]}}}``. Payloads stay in R2.
    """
    summary: dict[str, Any] = {}
    for entity_type in DIFF_ENTITY_TYPES:
        entity_diff = diffs_by_type.get(entity_type)
        if entity_diff is None:
            continue
        added_ids = [entry["entity_id"] for entry in entity_diff.get("added", [])]
        modified_ids = [entry["entity_id"] for entry in entity_diff.get("modified", [])]
        removed_ids = [entry["entity_id"] for entry in entity_diff.get("removed", [])]
        summary[entity_type] = {
            "added": len(added_ids),
            "modified": len(modified_ids),
            "removed": len(removed_ids),
            "ids": {
                "added": added_ids,
                "modified": modified_ids,
                "removed": removed_ids,
            },
        }
    return summary


def parse_diff_json_gz(diff_json_gz_bytes: bytes) -> dict[str, Any]:
    """Inverse of :func:`build_diff_json_gz` — returns the typed diff doc."""
    return json.loads(_gunzip_text(diff_json_gz_bytes))


# --------------------------------------------------------------------------- #
# R2 keys + upload/verify
# --------------------------------------------------------------------------- #
def artifact_prefix(community: str, version_number: int, source_hash: str | None) -> str:
    """Content-addressed R2 key prefix for a version's artifacts.

    ``gedcom-history/<community>/v<zero-padded-4>-<source_hash[:12]>/``.
    A missing source_hash (synthetic/compensating versions) uses ``synthetic``.
    """
    hash_prefix = (source_hash or "synthetic")[:12]
    return f"gedcom-history/{community}/v{version_number:04d}-{hash_prefix}/"


def upload_and_verify_artifacts(
    r2_client,
    bucket: str,
    prefix: str,
    artifacts: dict[str, bytes | None],
) -> dict[str, str]:
    """Upload each artifact then re-download + verify SHA-256 of compressed bytes.

    ``artifacts`` maps name -> compressed bytes. A ``None`` value (e.g.
    ``raw.ged.gz`` for compensating versions) is skipped. Returns name -> sha256
    of the verified compressed bytes. Raises ``ValueError`` on any mismatch.
    """
    result: dict[str, str] = {}
    for name, data in artifacts.items():
        if data is None:
            continue
        key = prefix + name
        local_sha = sha256_bytes(data)
        r2_client.put_object(Bucket=bucket, Key=key, Body=data)
        downloaded = _get_object_bytes(r2_client, bucket, key)
        downloaded_sha = sha256_bytes(downloaded)
        if downloaded_sha != local_sha:
            raise ValueError(
                f"R2 artifact verification failed for {key}: "
                f"uploaded sha256={local_sha} but downloaded sha256={downloaded_sha}"
            )
        result[name] = local_sha
    return result


def _get_object_bytes(r2_client, bucket: str, key: str) -> bytes:
    """Read an object's full bytes from an S3/R2-style client."""
    response = r2_client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    if hasattr(body, "read"):
        return body.read()
    return bytes(body)


def download_snapshot(r2_client, bucket: str, prefix: str) -> bytes:
    """Download the raw ``snapshot.jsonl.gz`` bytes for a version."""
    return _get_object_bytes(r2_client, bucket, prefix + "snapshot.jsonl.gz")


def download_diff(r2_client, bucket: str, prefix: str) -> dict[str, Any]:
    """Download + parse the ``diff.json.gz`` doc for a version."""
    data = _get_object_bytes(r2_client, bucket, prefix + "diff.json.gz")
    return parse_diff_json_gz(data)


def download_raw(r2_client, bucket: str, prefix: str) -> bytes:
    """Download the raw uncompressed GEDCOM bytes (gunzipped) for a version."""
    data = _get_object_bytes(r2_client, bucket, prefix + "raw.ged.gz")
    return gzip.decompress(data)


__all__ = [
    "SNAPSHOT_ENTITY_TYPES",
    "DIFF_ENTITY_TYPES",
    "SCHEMA_VERSION",
    "sha256_bytes",
    "build_snapshot_jsonl_gz",
    "reconstruct_version_from_snapshot",
    "build_diff_json_gz",
    "build_diff_summary",
    "parse_diff_json_gz",
    "artifact_prefix",
    "upload_and_verify_artifacts",
    "download_snapshot",
    "download_diff",
    "download_raw",
]
