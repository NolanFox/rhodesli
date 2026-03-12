#!/usr/bin/env python3
"""Audit differences between two GEDCOM exports using the rich snapshot model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rhodesli_ml.importers.gedcom_parser import parse_gedcom
from rhodesli_ml.importers.gedcom_matching import detect_individual_redirects
from rhodesli_ml.importers.gedcom_snapshot import build_snapshot_bundle, diff_entity_maps


ENTITY_TYPES = (
    "individuals",
    "events",
    "families",
    "sources",
    "media_objects",
    "relationships",
    "records",
)


def _top_change_paths(modified_items: list[dict], limit: int = 25) -> list[dict[str, int]]:
    counts: dict[str, int] = {}
    for item in modified_items:
        for change in item.get("changes", []):
            path = change.get("path") or ""
            counts[path] = counts.get(path, 0) + 1
    return [
        {"path": path, "count": count}
        for path, count in sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[:limit]
    ]


def _classify_individual_path(path: str) -> str:
    if path == "payload_hash":
        return "hash_bookkeeping"
    if path.startswith(("family_as_spouse_json", "family_as_child_json")):
        return "relationship_references"
    if path.startswith(("raw_record_json", "record_hash")):
        return "raw_record"
    if "citations_json" in path or "media_refs_json" in path or ".citations" in path or ".media_refs" in path:
        return "citation_or_media_refs"
    if path.startswith(("name", "given_name", "surname", "gender", "birth_", "death_", "events_json", "notes_json", "custom_tags_json")):
        return "person_facts"
    return "other"


def _individual_change_buckets(modified_items: list[dict]) -> dict[str, int]:
    buckets: dict[str, set[str]] = {}
    for item in modified_items:
        entity_id = item.get("entity_id", "")
        for change in item.get("changes", []):
            bucket = _classify_individual_path(change.get("path") or "")
            buckets.setdefault(bucket, set()).add(entity_id)
    return {bucket: len(entity_ids) for bucket, entity_ids in sorted(buckets.items())}


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit rich GEDCOM diffs between two exports")
    parser.add_argument("--old", required=True, help="Path to the older GEDCOM export")
    parser.add_argument("--new", required=True, help="Path to the newer GEDCOM export")
    parser.add_argument("--output", default="", help="Optional JSON output path")
    args = parser.parse_args()

    old_path = Path(args.old).expanduser()
    new_path = Path(args.new).expanduser()

    old_parsed = parse_gedcom(str(old_path))
    new_parsed = parse_gedcom(str(new_path))

    old_bundle = build_snapshot_bundle(old_parsed, source_file=old_path.name)
    new_bundle = build_snapshot_bundle(new_parsed, source_file=new_path.name)

    diff_by_entity = {}
    for entity_type in ENTITY_TYPES:
        diff = diff_entity_maps(entity_type, getattr(old_bundle, entity_type), getattr(new_bundle, entity_type))
        diff_by_entity[entity_type] = {
            "summary": diff["summary"],
            "top_change_paths": _top_change_paths(diff["modified"]),
            "sample_modified": [
                {
                    "entity_id": item["entity_id"],
                    "changes": item["changes"][:10],
                }
                for item in diff["modified"][:10]
            ],
            "sample_added": [item["entity_id"] for item in diff["added"][:10]],
            "sample_removed": [item["entity_id"] for item in diff["removed"][:10]],
        }

    individual_diff = diff_entity_maps("individuals", old_bundle.individuals, new_bundle.individuals)
    redirects = detect_individual_redirects(individual_diff["removed"], new_bundle.individuals, old_map=old_bundle.individuals)
    report = {
        "old_file": str(old_path),
        "new_file": str(new_path),
        "old_counts": old_bundle.counts,
        "new_counts": new_bundle.counts,
        "entity_diffs": diff_by_entity,
        "individual_change_buckets": _individual_change_buckets(individual_diff["modified"]),
        "detected_redirects": {
            "count": len(redirects),
            "sample": redirects[:10],
        },
    }

    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
