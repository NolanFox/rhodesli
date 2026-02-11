#!/usr/bin/env python3
"""
Data integrity checker for Rhodesli.

Detects test contamination, orphaned references, and data inconsistencies.
Run: python scripts/check_data_integrity.py
Exit code 0 = clean, 1 = issues found.

Fast (~1 second). Safe to run as pre-commit hook.
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
data_dir = project_root / "data"

errors = []
warnings = []


def check_no_test_contamination():
    """No photos should have test-related collection or source names."""
    pi_path = data_dir / "photo_index.json"
    if not pi_path.exists():
        return

    pi = json.loads(pi_path.read_text())
    photos = pi.get("photos", pi)

    test_patterns = ["test collection", "test ", "fixture", "mock"]
    for pid, p in photos.items():
        if not isinstance(p, dict):
            continue
        for field in ("collection", "source"):
            val = p.get(field, "")
            if any(pat in val.lower() for pat in test_patterns):
                errors.append(
                    f"TEST CONTAMINATION: photo {pid} has {field}='{val}'"
                )


def check_identity_integrity():
    """Identities should have valid states and no test artifacts."""
    id_path = data_dir / "identities.json"
    if not id_path.exists():
        return

    ids = json.loads(id_path.read_text())
    identities = ids.get("identities", ids)

    valid_states = {"CONFIRMED", "PROPOSED", "INBOX", "SKIPPED", "CONTESTED"}
    test_names = ["test person", "test identity", "fixture"]

    for iid, identity in identities.items():
        if not isinstance(identity, dict):
            continue

        state = identity.get("state", "")
        if state not in valid_states:
            errors.append(f"INVALID STATE: identity {iid} has state='{state}'")

        name = identity.get("name", "").lower()
        for pat in test_names:
            if pat in name:
                errors.append(
                    f"TEST CONTAMINATION: identity {iid} has name='{identity.get('name')}'"
                )


def check_photo_count_consistency():
    """Photo count in index should be reasonable."""
    pi_path = data_dir / "photo_index.json"
    if not pi_path.exists():
        return

    pi = json.loads(pi_path.read_text())
    photos = pi.get("photos", pi)
    count = len([p for p in photos.values() if isinstance(p, dict)])

    if count == 0:
        errors.append("EMPTY: photo_index.json has 0 photos")
    elif count < 10:
        warnings.append(f"LOW COUNT: photo_index.json has only {count} photos")


def check_face_to_photo_consistency():
    """Face-to-photo mapping should reference existing photos."""
    pi_path = data_dir / "photo_index.json"
    if not pi_path.exists():
        return

    pi = json.loads(pi_path.read_text())
    photos = pi.get("photos", pi)
    f2p = pi.get("face_to_photo", {})

    photo_ids = set(photos.keys())
    orphaned = 0
    for face_id, photo_id in f2p.items():
        if photo_id not in photo_ids:
            orphaned += 1
            if orphaned <= 5:
                warnings.append(
                    f"ORPHAN: face {face_id} -> photo {photo_id} (not in index)"
                )
    if orphaned > 5:
        warnings.append(f"  ... and {orphaned - 5} more orphaned face references")


def check_photo_entry_completeness():
    """Every photo entry must have all required fields."""
    # Mirror REQUIRED_PHOTO_FIELDS from core/photo_registry.py
    required = ["path", "width", "height", "collection"]

    pi_path = data_dir / "photo_index.json"
    if not pi_path.exists():
        return

    pi = json.loads(pi_path.read_text())
    photos = pi.get("photos", pi)

    for pid, p in photos.items():
        if not isinstance(p, dict):
            continue
        missing = [f for f in required if not p.get(f)]
        if missing:
            errors.append(
                f"INCOMPLETE PHOTO: {pid} missing required fields: {missing}"
            )


def check_deployment_readiness():
    """Verify all required data files are tracked by git and will deploy."""
    import subprocess

    # Must match REQUIRED_DATA_FILES in scripts/init_railway_volume.py
    required_files = ["identities.json", "photo_index.json", "embeddings.npy"]

    for filename in required_files:
        filepath = data_dir / filename

        # Check exists
        if not filepath.exists():
            errors.append(f"DEPLOY: required file missing: data/{filename}")
            continue

        # Check not empty
        if filepath.stat().st_size == 0:
            errors.append(f"DEPLOY: required file is empty: data/{filename}")
            continue

        # Check tracked by git (not gitignored)
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(filepath)],
            capture_output=True,
            cwd=project_root,
        )
        if result.returncode == 0:
            # Exit 0 means the file IS ignored
            errors.append(
                f"DEPLOY: data/{filename} is gitignored — add '!data/{filename}' to .gitignore"
            )


def main():
    print("Rhodesli Data Integrity Check")
    print("=" * 40)

    check_no_test_contamination()
    check_identity_integrity()
    check_photo_count_consistency()
    check_face_to_photo_consistency()
    check_photo_entry_completeness()
    check_deployment_readiness()

    if errors:
        print(f"\nERRORS ({len(errors)}):")
        for e in errors:
            print(f"  {e}")

    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  {w}")

    if not errors and not warnings:
        print("All checks passed.")

    if errors:
        print(f"\nFAILED — {len(errors)} error(s) found")
        sys.exit(1)
    else:
        print(f"\nPASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
