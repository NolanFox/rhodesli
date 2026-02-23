"""Migrate face alignment data from JSON to Supabase.

One-time migration script for AD-152. Reads data/face_alignments.json
and upserts each entry into the face_gemini_alignments Supabase table.

Usage:
    python scripts/migrate_alignments_to_supabase.py --dry-run
    python scripts/migrate_alignments_to_supabase.py --execute
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Migrate face alignments JSON → Supabase")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview without writing (default)")
    parser.add_argument("--execute", action="store_true",
                        help="Actually write to Supabase")
    args = parser.parse_args()

    json_path = Path(__file__).resolve().parent.parent / "data" / "face_alignments.json"
    if not json_path.exists():
        print(f"No alignment file found at {json_path}")
        sys.exit(1)

    with open(json_path) as f:
        alignments = json.load(f)

    print(f"Found {len(alignments)} alignment records in JSON")

    if not args.execute:
        print("\n--- DRY RUN (use --execute to write) ---")
        for photo_id, data in list(alignments.items())[:3]:
            faces = data.get("faces_described", 0)
            model = data.get("model_used", "unknown")
            cost = data.get("cost", 0)
            print(f"  {photo_id}: {faces} faces, model={model}, cost=${cost:.4f}")
        if len(alignments) > 3:
            print(f"  ... and {len(alignments) - 3} more")
        return

    from app.supabase_data import save_face_alignment_to_supabase, get_supabase_client

    sb = get_supabase_client()
    if not sb:
        print("ERROR: Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    success = 0
    failed = 0
    for photo_id, data in alignments.items():
        tokens = None
        if data.get("input_tokens") and data.get("output_tokens"):
            tokens = data["input_tokens"] + data["output_tokens"]

        ok = save_face_alignment_to_supabase(
            photo_id=photo_id,
            alignment_data=data,
            model_used=data.get("model_used"),
            cost=data.get("cost"),
            tokens=tokens,
        )
        if ok:
            success += 1
        else:
            failed += 1
            print(f"  FAILED: {photo_id}")

        if success % 20 == 0 and success > 0:
            print(f"  Progress: {success}/{len(alignments)}")

    print(f"\nMigration complete: {success} success, {failed} failed out of {len(alignments)}")


if __name__ == "__main__":
    main()
