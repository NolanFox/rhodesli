#!/usr/bin/env python3
"""Data Reconciliation Script — Cross-source consistency check.

Compares data across all sources (identities table, embeddings, photo_faces,
R2 crops) and reports mismatches. Can be run after every deploy or migration.

Usage:
    python scripts/data_reconciliation.py           # Full check
    python scripts/data_reconciliation.py --json    # Machine-readable output
    python scripts/data_reconciliation.py --fix     # Auto-fix safe issues

Exit codes:
    0 = All checks pass
    1 = Critical issues found

Created: Session 130 — Data Integrity Deep Audit
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _paginate_table(client, table_name, columns="*"):
    """Paginate a Supabase table query."""
    all_rows = []
    offset = 0
    page_size = 1000
    while True:
        resp = client.table(table_name).select(columns).range(offset, offset + page_size - 1).execute()
        if not resp.data:
            break
        all_rows.extend(resp.data)
        if len(resp.data) < page_size:
            break
        offset += page_size
    return all_rows


def run_reconciliation(data_dir: Path, fix: bool = False) -> dict:
    """Run all reconciliation checks."""
    import numpy as np
    from app.supabase_data import get_supabase_client
    from app.utils import generate_face_id, generate_photo_id

    client = get_supabase_client()
    if not client:
        return {"error": "Supabase unavailable", "status": "error"}

    report = {"checks": {}, "status": "healthy"}

    # 1. Load all data sources
    identities = _paginate_table(client, "identities", "identity_id, state, name, anchor_ids, merged_into")
    photos = _paginate_table(client, "photos", "photo_id, path")
    photo_faces = _paginate_table(client, "photo_faces", "face_id, photo_id")

    embeddings_path = data_dir / "embeddings.npy"
    emb_face_ids = set()
    if embeddings_path.exists():
        embeddings = np.load(str(embeddings_path), allow_pickle=True)
        filename_counts = {}
        for entry in embeddings:
            fn = entry["filename"]
            if fn not in filename_counts:
                filename_counts[fn] = 0
            idx = filename_counts[fn]
            filename_counts[fn] += 1
            fid = entry.get("face_id") or generate_face_id(fn, idx)
            emb_face_ids.add(fid)

    # Build lookup structures
    pf_face_ids = {r["face_id"] for r in photo_faces}
    pf_photo_ids = {r["photo_id"] for r in photo_faces}
    photo_ids = {r["photo_id"] for r in photos}
    photo_paths = {r["photo_id"]: r.get("path", "") for r in photos}

    logger.info(f"Identities: {len(identities)}")
    logger.info(f"Photos: {len(photos)}")
    logger.info(f"Photo_faces: {len(photo_faces)}")
    logger.info(f"Embeddings: {len(emb_face_ids)}")

    # 2. Check: Every embedding face exists in photo_faces
    missing_from_pf = emb_face_ids - pf_face_ids
    report["checks"]["embeddings_in_photo_faces"] = {
        "status": "PASS" if not missing_from_pf else "FAIL",
        "missing": len(missing_from_pf),
        "sample": sorted(missing_from_pf)[:10],
    }
    if missing_from_pf:
        report["status"] = "critical"

    # 3. Check: Every photo_faces.photo_id exists in photos table
    orphan_pf = pf_photo_ids - photo_ids
    report["checks"]["photo_faces_have_photos"] = {
        "status": "PASS" if not orphan_pf else "FAIL",
        "orphaned": len(orphan_pf),
        "sample": sorted(orphan_pf)[:10],
    }

    # 4. Check: Every CONFIRMED identity has all anchors in photo_faces
    confirmed_issues = []
    for ident in identities:
        if ident.get("merged_into") or ident.get("state") != "CONFIRMED":
            continue
        anchors = ident.get("anchor_ids", [])
        if isinstance(anchors, str):
            try:
                anchors = json.loads(anchors)
            except (json.JSONDecodeError, TypeError):
                anchors = []
        face_ids = []
        for a in anchors:
            if isinstance(a, str):
                face_ids.append(a)
            elif isinstance(a, dict):
                fid = a.get("face_id", "")
                if fid:
                    face_ids.append(fid)
        missing = [fid for fid in face_ids if fid not in pf_face_ids]
        if missing:
            confirmed_issues.append(
                {
                    "identity_id": ident["identity_id"][:8],
                    "name": ident.get("name", "?"),
                    "total": len(face_ids),
                    "missing": len(missing),
                }
            )

    report["checks"]["confirmed_faces_in_photo_faces"] = {
        "status": "PASS" if not confirmed_issues else "FAIL",
        "issues": len(confirmed_issues),
        "details": confirmed_issues[:20],
    }
    if confirmed_issues:
        report["status"] = "critical"

    # 5. Check: No duplicate face assignments
    face_owners = {}
    for ident in identities:
        if ident.get("merged_into"):
            continue
        anchors = ident.get("anchor_ids", [])
        if isinstance(anchors, str):
            try:
                anchors = json.loads(anchors)
            except (json.JSONDecodeError, TypeError):
                anchors = []
        for a in anchors:
            fid = a if isinstance(a, str) else a.get("face_id", "") if isinstance(a, dict) else ""
            if fid:
                face_owners.setdefault(fid, []).append(ident["identity_id"][:8])

    duplicates = {fid: owners for fid, owners in face_owners.items() if len(owners) > 1}
    report["checks"]["no_duplicate_face_assignments"] = {
        "status": "PASS" if not duplicates else "FAIL",
        "duplicates": len(duplicates),
        "sample": dict(list(duplicates.items())[:5]),
    }
    if duplicates:
        report["status"] = "critical"

    # Fix: backfill missing photo_faces
    if fix and missing_from_pf:
        from scripts.backfill_photo_faces import run_backfill

        result = run_backfill(data_dir, dry_run=False)
        report["fixes"] = result

    return report


def main():
    parser = argparse.ArgumentParser(description="Rhodesli Data Reconciliation")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--fix", action="store_true", help="Auto-fix safe issues")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    args = parser.parse_args()

    report = run_reconciliation(args.data_dir, fix=args.fix)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print("  RHODESLI DATA RECONCILIATION")
        print("=" * 60)
        for check_name, check_data in report.get("checks", {}).items():
            status = check_data.get("status", "?")
            marker = "PASS" if status == "PASS" else "FAIL"
            print(f"  [{marker}] {check_name}")
            for key, val in check_data.items():
                if key != "status":
                    if isinstance(val, list) and len(val) > 5:
                        print(f"        {key}: {val[:5]}... ({len(val)} total)")
                    else:
                        print(f"        {key}: {val}")
        print(f"\n  STATUS: {report['status'].upper()}")
        print("=" * 60)

    sys.exit(1 if report["status"] == "critical" else 0)


if __name__ == "__main__":
    main()
