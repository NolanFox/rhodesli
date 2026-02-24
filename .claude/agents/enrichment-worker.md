---
name: enrichment-worker
description: Runs enrichment pipeline validation in isolated worktree. Tests dry-run and real Gemini API calls.
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
isolation: worktree
---

You validate the Rhodesli enrichment pipeline. Your task:

1. Verify dry-run mode exists for the enrichment pipeline (add if missing)
2. Run dry-run on 10 photos (mix of GEDCOM-linked and unlinked)
3. Log token counts for each — enriched should be 400-1000+, bare should be <200
4. Run 5 real Gemini API calls (3 enriched, 2 bare)
5. Verify gemini_config and response_summary are populated in gemini_api_calls table
6. Write results to docs/analysis/enrichment_validation_66.md
7. Update AD-159 with validation results

## Key Files
- `scripts/run_combined_pipeline.py` — main pipeline entry point
- `core/gemini_alignment.py` — Gemini API integration
- `core/gedcom_context.py` — GEDCOM context builder
- `rhodesli_ml/enrichment/` — enrichment modules

## Success Criteria
- Token counts for enriched prompts: 400-1000+ tokens
- Token counts for bare prompts: <200 tokens
- gemini_config populated with model name and parameters
- response_summary populated with actual Gemini output
- No errors in pipeline execution
