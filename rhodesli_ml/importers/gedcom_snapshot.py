"""Canonical GEDCOM snapshot + diff helpers.

These helpers turn a parsed GEDCOM into stable, hashable entity snapshots so
local audits, admin preview UIs, and Supabase imports all compare the same
payloads.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from rhodesli_ml.importers.gedcom_parser import (
    GedcomCitation,
    GedcomEvent,
    GedcomMediaRef,
    GedcomName,
    ParsedDate,
)


LEGACY_COMPARE_FIELDS = {
    "individuals": [
        "name",
        "given_name",
        "surname",
        "gender",
        "birth_date",
        "birth_place",
        "death_date",
        "death_place",
    ],
    "events": [
        "gedcom_individual_id",
        "event_type",
        "date",
        "place",
        "raw_date",
    ],
    "relationships": [
        "individual_gedcom_id",
        "related_gedcom_id",
        "relationship_type",
        "family_gedcom_id",
    ],
}


@dataclass
class GedcomSnapshotBundle:
    individuals: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: dict[str, dict[str, Any]] = field(default_factory=dict)
    families: dict[str, dict[str, Any]] = field(default_factory=dict)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    media_objects: dict[str, dict[str, Any]] = field(default_factory=dict)
    relationships: dict[str, dict[str, Any]] = field(default_factory=dict)
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "individuals": len(self.individuals),
            "events": len(self.events),
            "families": len(self.families),
            "sources": len(self.sources),
            "media_objects": len(self.media_objects),
            "relationships": len(self.relationships),
            "records": len(self.records),
        }


def canonical_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def canonical_payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_dumps(value).encode("utf-8")).hexdigest()


def _normalize_raw_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_raw_payload(child)
            for key, child in value.items()
            if key != "line_number"
        }
    if isinstance(value, list):
        return [_normalize_raw_payload(child) for child in value]
    return value


def serialize_parsed_date(parsed_date: ParsedDate | None) -> dict[str, Any] | None:
    if parsed_date is None:
        return None
    return {
        "year": parsed_date.year,
        "month": parsed_date.month,
        "day": parsed_date.day,
        "modifier": parsed_date.modifier,
        "confidence": parsed_date.confidence,
        "raw": parsed_date.raw,
        "year_end": parsed_date.year_end,
    }


def serialize_event(event, event_type_override: str | None = None) -> dict[str, Any]:
    return {
        "event_type": event_type_override or getattr(event, "event_type", None),
        "date": serialize_parsed_date(getattr(event, "date", None)),
        "place": getattr(event, "place", None),
        "raw_date": getattr(event, "raw_date", ""),
        "value": getattr(event, "value", None),
        "type_label": getattr(event, "type_label", None),
        "notes": list(getattr(event, "notes", []) or []),
        "citations": [serialize_citation(citation) for citation in getattr(event, "citations", []) or []],
        "media_refs": [serialize_media_ref(media_ref) for media_ref in getattr(event, "media_refs", []) or []],
        "raw_tag": getattr(event, "raw_tag", None),
        "raw_node": _normalize_raw_payload(getattr(event, "raw_node", {}) or {}),
    }


def serialize_citation(citation) -> dict[str, Any]:
    return {
        "source_xref": citation.source_xref,
        "page": citation.page,
        "data_text": citation.data_text,
        "data_date": citation.data_date,
        "url": citation.url,
        "apid": citation.apid,
        "note": citation.note,
        "raw_node": _normalize_raw_payload(citation.raw_node or {}),
    }


def serialize_media_ref(media_ref) -> dict[str, Any]:
    return {
        "object_xref": media_ref.object_xref,
        "title": media_ref.title,
        "is_primary": media_ref.is_primary,
        "crop": media_ref.crop or {},
        "raw_node": _normalize_raw_payload(media_ref.raw_node or {}),
    }


def serialize_name(name) -> dict[str, Any]:
    return {
        "full_name": name.full_name,
        "given_name": name.given_name,
        "surname": name.surname,
        "prefix": name.prefix,
        "suffix": name.suffix,
        "nickname": name.nickname,
        "is_primary": name.is_primary,
        "notes": list(name.notes or []),
        "citations": [serialize_citation(citation) for citation in name.citations or []],
        "media_refs": [serialize_media_ref(media_ref) for media_ref in name.media_refs or []],
        "raw_value": name.raw_value,
        "raw_node": _normalize_raw_payload(name.raw_node or {}),
    }


def serialize_record(record) -> dict[str, Any]:
    return {
        "record_key": record.record_key,
        "record_type": record.record_type,
        "xref_id": record.xref_id,
        "record_hash": record.record_hash,
        "raw_text": record.raw_text,
        "root": {
            "level": record.root.level,
            "tag": record.root.tag,
            "xref_id": record.root.xref_id,
            "value": record.root.value,
            "children": _serialize_nodes(record.root.children),
        },
    }


def _serialize_nodes(nodes: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "level": node.level,
            "tag": node.tag,
            "xref_id": node.xref_id,
            "value": node.value,
            "children": _serialize_nodes(node.children),
        }
        for node in nodes
    ]


def _build_individual_snapshot(xref_id: str, indi, source_file: str) -> dict[str, Any]:
    birth_event = serialize_event(indi.birth, event_type_override="birth") if getattr(indi, "birth", None) else None
    death_event = serialize_event(indi.death, event_type_override="death") if getattr(indi, "death", None) else None
    other_events = [serialize_event(event) for event in getattr(indi, "events", []) or []]
    payload = {
        "gedcom_id": xref_id,
        "name": indi.full_name or "Unknown",
        "given_name": indi.given_name or None,
        "surname": indi.surname or None,
        "gender": indi.gender or "U",
        "birth_date": indi.birth.raw_date if getattr(indi, "birth", None) else None,
        "birth_place": getattr(indi, "birth_place", None),
        "death_date": indi.death.raw_date if getattr(indi, "death", None) else None,
        "death_place": getattr(indi, "death_place", None),
        "birth_event_json": birth_event,
        "death_event_json": death_event,
        "events_json": other_events,
        "family_as_spouse_json": list(getattr(indi, "family_as_spouse", []) or []),
        "family_as_child_json": list(getattr(indi, "family_as_child", []) or []),
        "names_json": [serialize_name(name) for name in getattr(indi, "names", []) or []],
        "notes_json": list(getattr(indi, "notes", []) or []),
        "citations_json": [serialize_citation(citation) for citation in getattr(indi, "citations", []) or []],
        "media_refs_json": [serialize_media_ref(media_ref) for media_ref in getattr(indi, "media_refs", []) or []],
        "custom_tags_json": _normalize_raw_payload(getattr(indi, "custom_tags", {}) or {}),
        "source_file": source_file,
        "raw_record_key": getattr(getattr(indi, "raw_record", None), "record_key", None),
        "raw_record_json": serialize_record(indi.raw_record) if getattr(indi, "raw_record", None) else None,
        "record_hash": getattr(getattr(indi, "raw_record", None), "record_hash", None),
    }
    payload["payload_hash"] = canonical_payload_hash({k: v for k, v in payload.items() if k != "raw_record_json"})
    return payload


def _build_event_snapshot(
    event_key: str,
    gedcom_individual_id: str,
    event,
    event_type_override: str | None = None,
) -> dict[str, Any]:
    payload = {
        "event_key": event_key,
        "gedcom_individual_id": gedcom_individual_id,
        "event_type": event_type_override or getattr(event, "event_type", None),
        "date": (
            str(getattr(getattr(event, "date", None), "year", None))
            if getattr(getattr(event, "date", None), "year", None)
            else None
        ),
        "place": getattr(event, "place", None),
        "raw_date": getattr(event, "raw_date", ""),
        "value": getattr(event, "value", None),
        "type_label": getattr(event, "type_label", None),
        "notes_json": list(getattr(event, "notes", []) or []),
        "citations_json": [serialize_citation(citation) for citation in getattr(event, "citations", []) or []],
        "media_refs_json": [serialize_media_ref(media_ref) for media_ref in getattr(event, "media_refs", []) or []],
        "raw_tag": getattr(event, "raw_tag", None),
        "raw_node_json": _normalize_raw_payload(getattr(event, "raw_node", {}) or {}),
    }
    payload["payload_hash"] = canonical_payload_hash(payload)
    return payload


def _build_family_snapshot(xref_id: str, fam) -> dict[str, Any]:
    payload = {
        "family_gedcom_id": xref_id,
        "husband_xref": fam.husband_xref,
        "wife_xref": fam.wife_xref,
        "children_xrefs_json": list(fam.children_xrefs or []),
        "marriage_event_json": serialize_event(fam.marriage) if fam.marriage else None,
        "events_json": [serialize_event(event) for event in fam.events],
        "notes_json": list(fam.notes or []),
        "citations_json": [serialize_citation(citation) for citation in fam.citations],
        "media_refs_json": [serialize_media_ref(media_ref) for media_ref in fam.media_refs],
        "custom_tags_json": _normalize_raw_payload(fam.custom_tags or {}),
        "raw_record_key": fam.raw_record.record_key if fam.raw_record else None,
        "raw_record_json": serialize_record(fam.raw_record) if fam.raw_record else None,
        "record_hash": fam.raw_record.record_hash if fam.raw_record else None,
    }
    payload["payload_hash"] = canonical_payload_hash({k: v for k, v in payload.items() if k != "raw_record_json"})
    return payload


def _build_source_snapshot(xref_id: str, source) -> dict[str, Any]:
    payload = {
        "source_xref": xref_id,
        "title": source.title,
        "author": source.author,
        "publication": source.publication,
        "repository_xref": source.repository_xref,
        "notes_json": list(source.notes or []),
        "urls_json": list(source.urls or []),
        "raw_record_key": source.raw_record.record_key if source.raw_record else None,
        "raw_record_json": serialize_record(source.raw_record) if source.raw_record else None,
        "record_hash": source.raw_record.record_hash if source.raw_record else None,
    }
    payload["payload_hash"] = canonical_payload_hash({k: v for k, v in payload.items() if k != "raw_record_json"})
    return payload


def _build_media_snapshot(xref_id: str, media) -> dict[str, Any]:
    payload = {
        "media_xref": xref_id,
        "file": media.file,
        "form": media.form,
        "title": media.title,
        "media_type": media.media_type,
        "notes_json": list(media.notes or []),
        "urls_json": list(media.urls or []),
        "raw_record_key": media.raw_record.record_key if media.raw_record else None,
        "raw_record_json": serialize_record(media.raw_record) if media.raw_record else None,
        "record_hash": media.raw_record.record_hash if media.raw_record else None,
    }
    payload["payload_hash"] = canonical_payload_hash({k: v for k, v in payload.items() if k != "raw_record_json"})
    return payload


def _relationship_edge_key(individual_gedcom_id: str, related_gedcom_id: str, relationship_type: str, family_gedcom_id: str) -> str:
    return f"{relationship_type}|{family_gedcom_id}|{individual_gedcom_id}|{related_gedcom_id}"


def _build_relationship_snapshot(
    individual_gedcom_id: str,
    related_gedcom_id: str,
    relationship_type: str,
    family_gedcom_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "edge_key": _relationship_edge_key(individual_gedcom_id, related_gedcom_id, relationship_type, family_gedcom_id),
        "individual_gedcom_id": individual_gedcom_id,
        "related_gedcom_id": related_gedcom_id,
        "relationship_type": relationship_type,
        "family_gedcom_id": family_gedcom_id,
        "relationship_payload": payload or {},
    }
    row["payload_hash"] = canonical_payload_hash(row)
    return row


def build_snapshot_bundle(parsed, source_file: str | None = None) -> GedcomSnapshotBundle:
    bundle = GedcomSnapshotBundle()
    effective_source_file = source_file or getattr(parsed, "source_file", "") or ""

    for xref_id, indi in parsed.individuals.items():
        bundle.individuals[xref_id] = _build_individual_snapshot(xref_id, indi, effective_source_file)

        all_events = []
        if getattr(indi, "birth", None):
            all_events.append(("birth", 0, indi.birth))
        if getattr(indi, "death", None):
            all_events.append(("death", 0, indi.death))
        tag_counts: dict[str, int] = {}
        for event in getattr(indi, "events", []) or []:
            tag = getattr(event, "raw_tag", None) or getattr(event, "event_type", "event")
            event_index = tag_counts.get(tag, 0)
            tag_counts[tag] = event_index + 1
            all_events.append((tag, event_index, event))

        for tag, event_index, event in all_events:
            event_key = f"{xref_id}|{tag}|{event_index}"
            bundle.events[event_key] = _build_event_snapshot(event_key, xref_id, event, event_type_override=tag)

    for xref_id, fam in getattr(parsed, "families", {}).items():
        bundle.families[xref_id] = _build_family_snapshot(xref_id, fam)

        parents = [xref for xref in [fam.husband_xref, fam.wife_xref] if xref]
        for parent_xref in parents:
            for child_xref in fam.children_xrefs:
                row = _build_relationship_snapshot(
                    parent_xref,
                    child_xref,
                    "parent",
                    xref_id,
                    payload={"direction": "parent_to_child"},
                )
                bundle.relationships[row["edge_key"]] = row
                row = _build_relationship_snapshot(
                    child_xref,
                    parent_xref,
                    "child",
                    xref_id,
                    payload={"direction": "child_to_parent"},
                )
                bundle.relationships[row["edge_key"]] = row

        if fam.husband_xref and fam.wife_xref:
            for individual_gedcom_id, related_gedcom_id in (
                (fam.husband_xref, fam.wife_xref),
                (fam.wife_xref, fam.husband_xref),
            ):
                row = _build_relationship_snapshot(
                    individual_gedcom_id,
                    related_gedcom_id,
                    "spouse",
                    xref_id,
                )
                bundle.relationships[row["edge_key"]] = row

        for index, child_a in enumerate(fam.children_xrefs):
            for child_b in fam.children_xrefs[index + 1 :]:
                for individual_gedcom_id, related_gedcom_id in ((child_a, child_b), (child_b, child_a)):
                    row = _build_relationship_snapshot(
                        individual_gedcom_id,
                        related_gedcom_id,
                        "sibling",
                        xref_id,
                    )
                    bundle.relationships[row["edge_key"]] = row

    for xref_id, source in getattr(parsed, "sources", {}).items():
        bundle.sources[xref_id] = _build_source_snapshot(xref_id, source)

    for xref_id, media in getattr(parsed, "media_objects", {}).items():
        bundle.media_objects[xref_id] = _build_media_snapshot(xref_id, media)

    for record_key, record in getattr(parsed, "records", {}).items():
        row = serialize_record(record)
        row["payload_hash"] = canonical_payload_hash(row)
        bundle.records[record_key] = row

    return bundle


def _diff_lists(old: list[Any], new: list[Any], path: str) -> list[dict[str, Any]]:
    if old == new:
        return []
    max_len = max(len(old), len(new))
    changes: list[dict[str, Any]] = []
    if max_len > 20:
        return [{"path": path, "old_value": old, "new_value": new}]
    for index in range(max_len):
        child_path = f"{path}[{index}]"
        if index >= len(old):
            changes.append({"path": child_path, "old_value": None, "new_value": new[index]})
            continue
        if index >= len(new):
            changes.append({"path": child_path, "old_value": old[index], "new_value": None})
            continue
        changes.extend(diff_payloads(old[index], new[index], child_path))
    return changes


def diff_payloads(old: Any, new: Any, path: str = "") -> list[dict[str, Any]]:
    if old == new:
        return []

    current_path = path or "$"
    if isinstance(old, dict) and isinstance(new, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(set(old) | set(new)):
            child_path = f"{current_path}.{key}" if current_path != "$" else key
            if key not in old:
                changes.append({"path": child_path, "old_value": None, "new_value": new[key]})
            elif key not in new:
                changes.append({"path": child_path, "old_value": old[key], "new_value": None})
            else:
                changes.extend(diff_payloads(old[key], new[key], child_path))
        return changes

    if isinstance(old, list) and isinstance(new, list):
        return _diff_lists(old, new, current_path)

    return [{"path": current_path, "old_value": old, "new_value": new}]


def _legacy_payload_for_entity(entity_type: str, row: dict[str, Any]) -> dict[str, Any]:
    fields = LEGACY_COMPARE_FIELDS.get(entity_type)
    if not fields:
        return row
    return {field: row.get(field) for field in fields}


def diff_entity_maps(
    entity_type: str,
    old_map: dict[str, dict[str, Any]],
    new_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    unchanged: list[str] = []

    old_ids = set(old_map)
    new_ids = set(new_map)

    for entity_id in sorted(new_ids - old_ids):
        added.append({"entity_id": entity_id, "new_payload": new_map[entity_id]})

    for entity_id in sorted(old_ids - new_ids):
        removed.append({"entity_id": entity_id, "old_payload": old_map[entity_id]})

    for entity_id in sorted(old_ids & new_ids):
        old_payload = old_map[entity_id]
        new_payload = new_map[entity_id]

        old_hash = old_payload.get("payload_hash")
        new_hash = new_payload.get("payload_hash")
        if old_hash and new_hash and old_hash == new_hash:
            unchanged.append(entity_id)
            continue

        if old_hash:
            changes = diff_payloads(old_payload, new_payload)
        else:
            changes = diff_payloads(_legacy_payload_for_entity(entity_type, old_payload), _legacy_payload_for_entity(entity_type, new_payload))

        if changes:
            modified.append(
                {
                    "entity_id": entity_id,
                    "old_payload": old_payload,
                    "new_payload": new_payload,
                    "changes": changes,
                }
            )
        else:
            unchanged.append(entity_id)

    return {
        "entity_type": entity_type,
        "added": added,
        "removed": removed,
        "modified": modified,
        "unchanged": unchanged,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
            "unchanged": len(unchanged),
        },
    }


def inflate_parsed_date(data: dict[str, Any] | None) -> ParsedDate | None:
    if not data:
        return None
    return ParsedDate(
        year=data.get("year"),
        month=data.get("month"),
        day=data.get("day"),
        modifier=data.get("modifier"),
        confidence=data.get("confidence", "HIGH"),
        raw=data.get("raw", ""),
        year_end=data.get("year_end"),
    )


def inflate_citation(data: dict[str, Any] | None) -> GedcomCitation:
    data = data or {}
    return GedcomCitation(
        source_xref=data.get("source_xref"),
        page=data.get("page"),
        data_text=data.get("data_text"),
        data_date=data.get("data_date"),
        url=data.get("url"),
        apid=data.get("apid"),
        note=data.get("note"),
        raw_node=data.get("raw_node") or {},
    )


def inflate_media_ref(data: dict[str, Any] | None) -> GedcomMediaRef:
    data = data or {}
    return GedcomMediaRef(
        object_xref=data.get("object_xref"),
        title=data.get("title"),
        is_primary=bool(data.get("is_primary")),
        crop=data.get("crop") or {},
        raw_node=data.get("raw_node") or {},
    )


def inflate_name(data: dict[str, Any] | None) -> GedcomName:
    data = data or {}
    return GedcomName(
        full_name=data.get("full_name", ""),
        given_name=data.get("given_name", ""),
        surname=data.get("surname", ""),
        prefix=data.get("prefix"),
        suffix=data.get("suffix"),
        nickname=data.get("nickname"),
        is_primary=bool(data.get("is_primary")),
        notes=list(data.get("notes") or []),
        citations=[inflate_citation(citation) for citation in data.get("citations") or []],
        media_refs=[inflate_media_ref(media_ref) for media_ref in data.get("media_refs") or []],
        raw_value=data.get("raw_value", ""),
        raw_node=data.get("raw_node") or {},
    )


def inflate_event(data: dict[str, Any] | None) -> GedcomEvent | None:
    if not data:
        return None
    return GedcomEvent(
        event_type=data.get("event_type", ""),
        date=inflate_parsed_date(data.get("date")),
        place=data.get("place"),
        raw_date=data.get("raw_date", ""),
        value=data.get("value"),
        type_label=data.get("type_label"),
        notes=list(data.get("notes") or data.get("notes_json") or []),
        citations=[inflate_citation(citation) for citation in data.get("citations") or data.get("citations_json") or []],
        media_refs=[inflate_media_ref(media_ref) for media_ref in data.get("media_refs") or data.get("media_refs_json") or []],
        raw_tag=data.get("raw_tag"),
        raw_node=data.get("raw_node") or data.get("raw_node_json") or {},
    )
