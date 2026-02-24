#!/usr/bin/env python3
"""
Process results from a Gemini Batch API job.

Retrieves batch results, parses alignment responses, saves to Supabase,
and logs API calls. Run after a batch job completes.

Usage:
    python scripts/process_batch_results.py --batch-name batches/xxx
    python scripts/process_batch_results.py --batch-name batches/xxx --check-only
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Process Gemini batch results")
    parser.add_argument('--batch-name', required=True, help='Batch job name (e.g., batches/xxx)')
    parser.add_argument('--check-only', action='store_true', help='Only check status, do not process')
    parser.add_argument('--wait', type=int, default=0, help='Wait up to N minutes for completion')
    args = parser.parse_args()

    from google import genai
    client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))

    # Check / wait for batch
    batch = client.batches.get(name=args.batch_name)
    print(f"Batch: {batch.name}")
    print(f"State: {batch.state}")
    print(f"Model: {batch.model}")

    if args.wait > 0 and 'RUNNING' in str(batch.state) or 'PENDING' in str(batch.state):
        start = time.time()
        max_wait = args.wait * 60
        while time.time() - start < max_wait:
            batch = client.batches.get(name=args.batch_name)
            print(f"[{int(time.time() - start)}s] {batch.state}")
            if 'SUCCEEDED' in str(batch.state) or 'FAILED' in str(batch.state) or 'CANCELLED' in str(batch.state):
                break
            time.sleep(60)

    if args.check_only:
        stats = getattr(batch, 'completion_stats', None)
        if stats:
            print(f"Stats: {stats}")
        return

    if 'SUCCEEDED' not in str(batch.state):
        print(f"Batch not yet complete: {batch.state}")
        print(f"Re-run with: python scripts/process_batch_results.py --batch-name {args.batch_name}")
        return

    # Process results
    print("\nProcessing results...")
    dest = batch.dest
    if not dest:
        print("No destination found on batch job")
        return

    # Load batch metadata
    meta_path = PROJECT_ROOT / 'results' / 'batch_64d_metadata.json'
    batch_meta = {}
    if meta_path.exists():
        with open(meta_path) as f:
            batch_meta = json.load(f)
    photo_ids = batch_meta.get('photo_ids', [])

    # Get results
    from app.face_alignment import (
        AlignmentResult,
        FaceDetection,
        build_alignment_prompt,
        parse_alignment_response,
        save_alignment,
    )
    from app.supabase_data import log_gemini_call
    from rhodesli_ml.gemini_config import get_model_pricing
    from scripts.run_combined_pipeline import build_faces_for_photo
    import numpy as np

    with open(PROJECT_ROOT / 'data' / 'photo_index.json') as f:
        photo_index = json.load(f)
    with open(PROJECT_ROOT / 'data' / 'identities.json') as f:
        identities = json.load(f)
    embeddings = np.load(str(PROJECT_ROOT / 'data' / 'embeddings.npy'), allow_pickle=True)

    photos = photo_index.get('photos', {})
    model = batch.model or 'gemini-3.1-pro-preview'
    pricing = get_model_pricing(model)
    batch_id = batch_meta.get('batch_display_name', f'batch-{args.batch_name}')

    # Read inline results from the batch
    results = []
    if hasattr(dest, 'inlined_responses') and dest.inlined_responses:
        results = dest.inlined_responses
    else:
        # Try to read from file output
        file_name = getattr(dest, 'file_name', None)
        if file_name:
            output_file = client.files.get(name=file_name)
            print(f"Output file: {output_file.name}")

    success_count = 0
    error_count = 0
    total_cost = 0.0

    for i, result in enumerate(results):
        photo_id = photo_ids[i] if i < len(photo_ids) else f"unknown_{i}"
        photo_data = photos.get(photo_id, {})
        faces = build_faces_for_photo(photo_data, identities, embeddings)

        if hasattr(result, 'response') and result.response:
            try:
                text = result.response.text
                parsed = json.loads(text)

                input_tokens = 0
                output_tokens = 0
                usage = getattr(result.response, 'usage_metadata', None)
                if usage:
                    input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                    output_tokens = getattr(usage, 'candidates_token_count', 0) or 0

                cost = (input_tokens * pricing["input"] / 1_000_000) + (output_tokens * pricing["output"] / 1_000_000)
                total_cost += cost

                alignment = parse_alignment_response(
                    parsed, faces, photo_id,
                    model_used=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                save_alignment(alignment, output_dir=PROJECT_ROOT / 'data')

                log_gemini_call(
                    photo_id=photo_id,
                    model_used=model,
                    call_type="batch_combined",
                    prompt_tokens=input_tokens,
                    completion_tokens=output_tokens,
                    cost_usd=cost,
                    latency_ms=0,
                    status="success",
                    batch_id=batch_id,
                )

                success_count += 1
                if (i + 1) % 20 == 0:
                    print(f"  [{i+1}/{len(results)}] Cost so far: ${total_cost:.4f}")

            except Exception as e:
                error_count += 1
                print(f"  ERROR processing {photo_id}: {e}")
                log_gemini_call(
                    photo_id=photo_id,
                    model_used=model,
                    call_type="batch_combined",
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0,
                    latency_ms=0,
                    status="error",
                    error_message=str(e),
                    batch_id=batch_id,
                )
        else:
            error_count += 1
            error_msg = getattr(result, 'error', 'No response')
            print(f"  FAILED {photo_id}: {error_msg}")

    print(f"\n{'='*60}")
    print(f"BATCH RESULTS PROCESSED")
    print(f"{'='*60}")
    print(f"Success: {success_count}/{len(results)}")
    print(f"Errors: {error_count}")
    print(f"Total cost: ${total_cost:.4f}")
    print(f"Average cost/photo: ${total_cost/max(success_count,1):.4f}")

    # Save summary
    summary = {
        "batch_name": args.batch_name,
        "batch_id": batch_id,
        "model": model,
        "total_requests": len(results),
        "success": success_count,
        "errors": error_count,
        "total_cost": round(total_cost, 4),
        "avg_cost_per_photo": round(total_cost / max(success_count, 1), 4),
        "processed_at": time.strftime('%Y-%m-%d %H:%M:%S'),
    }
    output_path = PROJECT_ROOT / 'results' / 'batch_64d_results.json'
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"Summary saved to {output_path}")


if __name__ == '__main__':
    main()
