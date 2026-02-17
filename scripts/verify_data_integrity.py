#!/usr/bin/env python3
"""
Data integrity verifier for Rhodesli.

Checks that all JSON data files parse correctly, expected collections exist,
photo counts are stable, relationships.json is valid, and identities.json
has the required "history" key.

Run: python scripts/verify_data_integrity.py
Exit code 0 = all checks passed, 1 = one or more checks failed.
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
data_dir = project_root / "data"

passed = []
failed = []


def check(name: str, condition: bool, detail: str = ""):
    """Record a pass or fail for a named check."""
    if condition:
        passed.append(name)
    else:
        failed.append(f"{name}: {detail}" if detail else name)


# ---------------------------------------------------------------------------
# 1. All JSON files in data/ parse correctly
# ---------------------------------------------------------------------------
def check_json_parse():
    """Every .json file in data/ must parse without errors."""
    json_files = sorted(data_dir.glob("*.json"))
    if not json_files:
        check("json_files_exist", False, "no .json files found in data/")
        return

    all_ok = True
    bad_files = []
    for jf in json_files:
        try:
            json.loads(jf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            all_ok = False
            bad_files.append(f"{jf.name}: {exc}")

    check(
        "all_json_files_parse",
        all_ok,
        "; ".join(bad_files) if bad_files else "",
    )


# ---------------------------------------------------------------------------
# 2. Expected collections exist in photo_index.json
# ---------------------------------------------------------------------------
def check_collections():
    """photo_index.json should contain known collections."""
    pi_path = data_dir / "photo_index.json"
    if not pi_path.exists():
        check("photo_index_exists", False, "data/photo_index.json not found")
        return

    pi = json.loads(pi_path.read_text(encoding="utf-8"))
    photos = pi.get("photos", {})
    collections = set()
    for photo in photos.values():
        if isinstance(photo, dict):
            col = photo.get("collection", "")
            if col:
                collections.add(col)

    check(
        "collections_found",
        len(collections) > 0,
        f"found {len(collections)} collections" if collections else "no collections in photo_index",
    )

    # Verify at least the well-known collections are present
    expected = [
        "Vida Capeluto NYC Collection",
        "Betty Capeluto Miami Collection",
        "Nace Capeluto Tampa Collection",
    ]
    for col_name in expected:
        check(
            f"collection_exists:{col_name}",
            col_name in collections,
            f"'{col_name}' not found in collections: {sorted(collections)}",
        )


# ---------------------------------------------------------------------------
# 3. Photo counts haven't changed unexpectedly
# ---------------------------------------------------------------------------
def check_photo_counts():
    """Photo count should be within a reasonable range (not 0, not wildly different)."""
    pi_path = data_dir / "photo_index.json"
    if not pi_path.exists():
        check("photo_index_for_counts", False, "data/photo_index.json not found")
        return

    pi = json.loads(pi_path.read_text(encoding="utf-8"))
    photos = pi.get("photos", {})
    count = len([p for p in photos.values() if isinstance(p, dict)])

    check("photo_count_nonzero", count > 0, f"photo count is {count}")
    check(
        "photo_count_reasonable",
        count >= 100,
        f"photo count is {count}, expected >= 100 (current archive has ~271)",
    )

    # Also check face_to_photo mapping exists and is populated
    f2p = pi.get("face_to_photo", {})
    check(
        "face_to_photo_populated",
        len(f2p) > 0,
        f"face_to_photo has {len(f2p)} entries",
    )


# ---------------------------------------------------------------------------
# 4. relationships.json parses correctly
# ---------------------------------------------------------------------------
def check_relationships():
    """relationships.json must parse and have expected structure."""
    rel_path = data_dir / "relationships.json"
    if not rel_path.exists():
        check("relationships_exists", False, "data/relationships.json not found")
        return

    try:
        data = json.loads(rel_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        check("relationships_parse", False, str(exc))
        return

    check("relationships_parse", True)
    check(
        "relationships_has_schema_version",
        "schema_version" in data,
        "missing 'schema_version' key",
    )
    check(
        "relationships_has_relationships_key",
        "relationships" in data,
        "missing 'relationships' key",
    )

    rels = data.get("relationships", [])
    check(
        "relationships_is_list",
        isinstance(rels, list),
        f"'relationships' is {type(rels).__name__}, expected list",
    )

    # Validate each relationship has required fields
    valid_types = {"parent_child", "spouse", "sibling", "fan_friend", "fan_associate", "fan_neighbor"}
    bad_entries = []
    for i, rel in enumerate(rels):
        if not isinstance(rel, dict):
            bad_entries.append(f"index {i}: not a dict")
            continue
        for field in ("person_a", "person_b", "type"):
            if field not in rel:
                bad_entries.append(f"index {i}: missing '{field}'")
        rel_type = rel.get("type", "")
        if rel_type and rel_type not in valid_types:
            bad_entries.append(f"index {i}: unknown type '{rel_type}'")

    check(
        "relationships_entries_valid",
        len(bad_entries) == 0,
        "; ".join(bad_entries[:5]) + (f" (+{len(bad_entries)-5} more)" if len(bad_entries) > 5 else ""),
    )


# ---------------------------------------------------------------------------
# 5. identities.json has "history" key
# ---------------------------------------------------------------------------
def check_identities_history():
    """identities.json must have the 'history' key (required by IdentityRegistry.load())."""
    id_path = data_dir / "identities.json"
    if not id_path.exists():
        check("identities_exists", False, "data/identities.json not found")
        return

    try:
        data = json.loads(id_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        check("identities_parse", False, str(exc))
        return

    check("identities_parse", True)
    check(
        "identities_has_history_key",
        "history" in data,
        "CRITICAL: 'history' key missing — IdentityRegistry.load() will throw ValueError",
    )
    check(
        "identities_has_identities_key",
        "identities" in data,
        "missing 'identities' key",
    )

    identities = data.get("identities", {})
    check(
        "identities_count_nonzero",
        len(identities) > 0,
        f"identities count is {len(identities)}",
    )

    # Validate identity states
    valid_states = {"CONFIRMED", "PROPOSED", "INBOX", "SKIPPED", "CONTESTED"}
    bad_states = []
    for iid, ident in identities.items():
        if not isinstance(ident, dict):
            continue
        state = ident.get("state", "")
        if state not in valid_states:
            bad_states.append(f"{iid}: state='{state}'")

    check(
        "identities_states_valid",
        len(bad_states) == 0,
        "; ".join(bad_states[:5]) + (f" (+{len(bad_states)-5} more)" if len(bad_states) > 5 else ""),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Rhodesli Data Integrity Verification")
    print("=" * 45)

    check_json_parse()
    check_collections()
    check_photo_counts()
    check_relationships()
    check_identities_history()

    print()
    print(f"PASSED: {len(passed)}")
    for name in passed:
        print(f"  [PASS] {name}")

    if failed:
        print(f"\nFAILED: {len(failed)}")
        for detail in failed:
            print(f"  [FAIL] {detail}")

    print()
    total = len(passed) + len(failed)
    if failed:
        print(f"RESULT: {len(failed)}/{total} checks FAILED")
        sys.exit(1)
    else:
        print(f"RESULT: {total}/{total} checks PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
