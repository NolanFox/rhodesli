#!/usr/bin/env python3
"""Backfill 80+ Gemini API call audit logs from Session 142 batch run.

The batch script (batch_gemini_for_person.py) processed photos successfully
but Supabase logging failed because prompt manifest columns (contract_valid,
full_response_hash) don't exist in gemini_api_calls table.

Results are saved in rhodesli_ml/data/date_labels.json with full provenance.
This script reads those entries and inserts audit rows directly into Supabase,
using only columns that exist in the actual table.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Load .env BEFORE any app imports
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_data import get_supabase_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Columns that actually exist in gemini_api_calls table
VALID_COLUMNS = {
    "id",
    "photo_id",
    "model_used",
    "call_type",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "cost_usd",
    "latency_ms",
    "status",
    "error_message",
    "rate_limit_type",
    "response_summary",
    "gemini_config",
    "created_at",
    "batch_id",
    "prompt_text",
    "full_response",
    "gedcom_context",
}


def load_batch_entries():
    """Load batch entries from date_labels.json."""
    labels_path = Path(__file__).resolve().parent.parent / "rhodesli_ml" / "data" / "date_labels.json"
    with open(labels_path) as f:
        data = json.load(f)

    labels = data.get("labels", [])
    batch = [l for l in labels if l.get("source_method") in ("gemini_batch_full", "gemini_batch_person")]
    return batch


def build_row(entry):
    """Build a gemini_api_calls row from a date_labels entry."""
    # Estimate tokens from response size (rough: ~4 chars per token)
    response_summary = json.dumps(
        {
            "estimated_decade": entry.get("estimated_decade"),
            "best_year_estimate": entry.get("best_year_estimate"),
            "confidence": entry.get("confidence"),
            "probable_range": entry.get("probable_range"),
            "location_estimate": entry.get("location_estimate", {}).get("place"),
            "people_count": entry.get("group_composition", {}).get("people_count"),
            "photo_type": entry.get("photo_type"),
        }
    )

    # Full response is the entire entry minus internal tracking fields
    full_response_data = {
        k: v
        for k, v in entry.items()
        if k
        not in (
            "photo_id",
            "filename",
            "source_method",
            "batch_context",
            "preset",
            "prompt_version",
            "created_at",
            "face_coordinates_sent",
            "gedcom_context_sent",
        )
    }
    full_response = json.dumps(full_response_data)

    # Estimate tokens
    est_prompt_tokens = 2000  # typical for full extraction prompt + image
    est_completion_tokens = len(full_response) // 4

    # Build gemini_config with manifest metadata
    gemini_config = {
        "prompt_version": entry.get("prompt_version"),
        "preset": entry.get("preset"),
        "source_method": entry.get("source_method"),
        "face_coordinates_sent": entry.get("face_coordinates_sent", False),
        "gedcom_context_sent": entry.get("gedcom_context_sent", False),
        "trigger": "batch_person_analysis_backfill",
        "original_batch_context": entry.get("batch_context"),
    }

    row = {
        "photo_id": entry["photo_id"],
        "model_used": "gemini-2.5-pro-preview-05-06",
        "call_type": "batch_full_extraction",
        "status": "success",
        "prompt_tokens": est_prompt_tokens,
        "completion_tokens": est_completion_tokens,
        "total_tokens": est_prompt_tokens + est_completion_tokens,
        "response_summary": response_summary,
        "gemini_config": gemini_config,
        "full_response": full_response,
        "batch_id": "session_142_esther_albert_backfill",
    }

    # Use original created_at if available
    if entry.get("created_at"):
        row["created_at"] = entry["created_at"]

    # Add GEDCOM context if it was sent
    if entry.get("gedcom_context_sent"):
        batch_ctx = entry.get("batch_context", {})
        if batch_ctx:
            row["gedcom_context"] = json.dumps(batch_ctx)

    return row


def main():
    sb = get_supabase_client()
    if not sb:
        logger.error("Supabase client not available. Check .env credentials.")
        sys.exit(1)

    entries = load_batch_entries()
    logger.info(f"Found {len(entries)} batch entries to backfill")

    if not entries:
        logger.info("No entries to backfill.")
        return

    # Check for existing backfill rows to avoid duplicates
    existing = (
        sb.table("gemini_api_calls").select("photo_id").eq("batch_id", "session_142_esther_albert_backfill").execute()
    )
    existing_photo_ids = {r["photo_id"] for r in existing.data}
    logger.info(f"Already backfilled: {len(existing_photo_ids)} rows")

    # Filter out already-backfilled
    new_entries = [e for e in entries if e["photo_id"] not in existing_photo_ids]
    logger.info(f"New entries to insert: {len(new_entries)}")

    if not new_entries:
        logger.info("All entries already backfilled. Nothing to do.")
        return

    # Build rows
    rows = [build_row(e) for e in new_entries]

    # Insert in batches of 20
    success = 0
    failed = 0
    batch_size = 20
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            sb.table("gemini_api_calls").insert(batch).execute()
            success += len(batch)
            logger.info(f"  Inserted batch {i // batch_size + 1}: {len(batch)} rows")
        except Exception as e:
            logger.error(f"  Batch {i // batch_size + 1} failed: {e}")
            # Fall back to individual inserts
            for row in batch:
                try:
                    sb.table("gemini_api_calls").insert(row).execute()
                    success += 1
                except Exception as e2:
                    failed += 1
                    logger.error(f"    Failed for {row['photo_id']}: {e2}")

    logger.info(f"\nBackfill complete: {success} inserted, {failed} failed")

    # Verify
    total = (
        sb.table("gemini_api_calls")
        .select("photo_id", count="exact")
        .eq("batch_id", "session_142_esther_albert_backfill")
        .execute()
    )
    logger.info(f"Total backfill rows in table: {total.count}")


if __name__ == "__main__":
    main()
