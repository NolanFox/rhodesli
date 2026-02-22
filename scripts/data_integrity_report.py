#!/usr/bin/env python3
"""Data Integrity Report — cross-checks Supabase and JSON data sources.

Usage:
    python scripts/data_integrity_report.py          # Full report
    python scripts/data_integrity_report.py --quick   # JSON-only (no Supabase)

Checks:
1. Record counts in Supabase tables vs JSON files
2. Cross-reference: confirmed identities in JSON ↔ Supabase
3. Gemini API log status
4. Upload record status
5. Dual-write consistency

Created: Session 61 (ACT 4: Data Storage Verification)
"""

import json
import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
ML_DATA_DIR = PROJECT_ROOT / "rhodesli_ml" / "data"


def count_json_entries():
    """Count entries in each JSON data file."""
    results = {}

    # identities.json
    idp = DATA_DIR / "identities.json"
    if idp.exists():
        data = json.loads(idp.read_text())
        identities = data.get("identities", {})
        results["identities.json"] = {
            "total": len(identities),
            "confirmed": sum(1 for v in identities.values() if v.get("state") == "CONFIRMED"),
            "proposed": sum(1 for v in identities.values() if v.get("state") == "PROPOSED"),
            "inbox": sum(1 for v in identities.values() if v.get("state") == "INBOX"),
            "merged": sum(1 for v in identities.values() if v.get("merged_into")),
        }
    else:
        results["identities.json"] = {"error": "FILE NOT FOUND"}

    # photo_index.json
    pip = DATA_DIR / "photo_index.json"
    if pip.exists():
        data = json.loads(pip.read_text())
        photos = data.get("photos", {})
        results["photo_index.json"] = {
            "total_photos": len(photos),
            "face_to_photo_entries": len(data.get("face_to_photo", {})),
        }
    else:
        results["photo_index.json"] = {"error": "FILE NOT FOUND"}

    # annotations.json
    anp = DATA_DIR / "annotations.json"
    if anp.exists():
        data = json.loads(anp.read_text())
        ann = data.get("annotations", [])
        results["annotations.json"] = {"total": len(ann)}
    else:
        results["annotations.json"] = {"total": 0, "note": "file not found"}

    # date_labels.json
    dlp = DATA_DIR / "date_labels.json"
    if dlp.exists():
        data = json.loads(dlp.read_text())
        results["date_labels.json"] = {"total": len(data)}
    else:
        results["date_labels.json"] = {"total": 0, "note": "file not found"}

    # relationships.json
    rp = DATA_DIR / "relationships.json"
    if rp.exists():
        data = json.loads(rp.read_text())
        rels = data if isinstance(data, list) else data.get("relationships", [])
        results["relationships.json"] = {"total": len(rels)}
    else:
        results["relationships.json"] = {"total": 0, "note": "file not found"}

    # gedcom_matches.csv
    gp = DATA_DIR / "gedcom_matches.csv"
    if gp.exists():
        lines = gp.read_text().strip().split("\n")
        results["gedcom_matches.csv"] = {"total": max(0, len(lines) - 1)}  # Minus header
    else:
        results["gedcom_matches.csv"] = {"total": 0, "note": "file not found"}

    # embeddings.npy
    ep = DATA_DIR / "embeddings.npy"
    if ep.exists():
        try:
            import numpy as np
            embs = np.load(str(ep), allow_pickle=True)
            results["embeddings.npy"] = {"total_entries": len(embs)}
        except Exception as e:
            results["embeddings.npy"] = {"error": str(e)}
    else:
        results["embeddings.npy"] = {"error": "FILE NOT FOUND"}

    return results


def count_supabase_tables():
    """Count records in each Supabase table."""
    try:
        from app.supabase_data import get_supabase_client
    except ImportError:
        return {"error": "Cannot import supabase_data module"}

    client = get_supabase_client()
    if not client:
        return {"error": "Supabase not configured (no SUPABASE_URL or key)"}

    results = {}
    tables = ["identity_overrides", "annotations", "relationships", "gedcom_matches"]

    for table in tables:
        try:
            resp = client.table(table).select("*", count="exact").limit(0).execute()
            results[table] = {"count": resp.count if hasattr(resp, "count") else "unknown"}
        except Exception as e:
            results[table] = {"error": str(e)}

    return results


def cross_check_identities():
    """Cross-reference confirmed identities between JSON and Supabase."""
    idp = DATA_DIR / "identities.json"
    if not idp.exists():
        return {"error": "identities.json not found"}

    data = json.loads(idp.read_text())
    identities = data.get("identities", {})

    # Get confirmed identity IDs from JSON
    confirmed_json = {
        iid for iid, v in identities.items()
        if v.get("state") == "CONFIRMED" and not v.get("merged_into")
    }

    # Get user-modified identity IDs from JSON (overrides = name, state, anchor changes)
    user_modified_json = set()
    for iid, v in identities.items():
        if v.get("state") == "CONFIRMED" or v.get("merged_into"):
            user_modified_json.add(iid)

    result = {
        "json_confirmed_count": len(confirmed_json),
        "json_user_modified_count": len(user_modified_json),
    }

    # Try Supabase cross-check
    try:
        from app.supabase_data import get_supabase_client
        client = get_supabase_client()
        if client:
            resp = client.table("identity_overrides").select("identity_id").execute()
            sb_ids = {r["identity_id"] for r in (resp.data or [])}
            result["supabase_override_count"] = len(sb_ids)

            missing_in_sb = user_modified_json - sb_ids
            extra_in_sb = sb_ids - user_modified_json
            result["missing_in_supabase"] = len(missing_in_sb)
            result["extra_in_supabase"] = len(extra_in_sb)

            if missing_in_sb:
                result["missing_ids_sample"] = sorted(missing_in_sb)[:5]
            if extra_in_sb:
                result["extra_ids_sample"] = sorted(extra_in_sb)[:5]

            result["in_sync"] = len(missing_in_sb) == 0
        else:
            result["supabase"] = "not configured"
    except Exception as e:
        result["supabase_error"] = str(e)

    return result


def check_gemini_logs():
    """Check Gemini API log directory status."""
    log_dir = ML_DATA_DIR / "api_logs"
    if not log_dir.exists():
        return {"status": "no logs yet", "count": 0}

    logs = list(log_dir.glob("*.json"))
    total_cost = 0
    models_used = set()
    for lf in logs[:100]:
        try:
            data = json.loads(lf.read_text())
            total_cost += data.get("estimated_cost_usd", 0)
            models_used.add(data.get("model", "unknown"))
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "count": len(logs),
        "total_cost_usd": round(total_cost, 4),
        "models_used": sorted(models_used),
    }


def check_upload_records():
    """Check pending uploads status."""
    up = DATA_DIR / "pending_uploads.json"
    if not up.exists():
        return {"status": "no pending uploads file", "count": 0}

    data = json.loads(up.read_text())
    uploads = data if isinstance(data, list) else data.get("uploads", [])
    return {
        "total": len(uploads),
        "pending": sum(1 for u in uploads if u.get("status") == "pending"),
        "processed": sum(1 for u in uploads if u.get("status") == "processed"),
    }


def print_report(quick=False):
    """Print the full data integrity report."""
    print("=" * 60)
    print("  RHODESLI DATA INTEGRITY REPORT")
    print("=" * 60)

    print("\n--- JSON FILE COUNTS ---")
    json_counts = count_json_entries()
    for fname, info in json_counts.items():
        if "error" in info:
            print(f"  {fname}: ERROR — {info['error']}")
        else:
            print(f"  {fname}: {info}")

    if not quick:
        print("\n--- SUPABASE TABLE COUNTS ---")
        sb_counts = count_supabase_tables()
        if "error" in sb_counts:
            print(f"  {sb_counts['error']}")
        else:
            for table, info in sb_counts.items():
                print(f"  {table}: {info}")

        print("\n--- CROSS-CHECK: JSON ↔ SUPABASE ---")
        xcheck = cross_check_identities()
        for k, v in xcheck.items():
            print(f"  {k}: {v}")
    else:
        print("\n  (Skipping Supabase checks — use without --quick for full report)")

    print("\n--- GEMINI API LOGS ---")
    gl = check_gemini_logs()
    for k, v in gl.items():
        print(f"  {k}: {v}")

    print("\n--- UPLOAD RECORDS ---")
    ul = check_upload_records()
    for k, v in ul.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("  Report complete.")
    print("=" * 60)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    print_report(quick=quick)
