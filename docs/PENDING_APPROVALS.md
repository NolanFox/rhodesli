# Pending Cost Approvals

## Flash vs Pro Comparison (20 photos)
- **Estimated cost**: ~$0.62
- **Purpose**: Determine if Gemini 3.1 Pro is worth 10x premium over Flash for date estimation
- **Script**: `python rhodesli_ml/scripts/compare_models.py --photos 20`
- **Approved**: [ ] (Nolan must check this)
- **What it measures**: Decade agreement rate, evidence richness, cost per photo
- **Expected outcome**: Data to decide Flash vs Pro default for different use cases

## Full Library Re-Analysis (271 photos, unified extraction)
- **Estimated cost**: ~$0.30 (quick preset) to ~$11.00 (full preset with Pro)
- **Purpose**: Full re-analysis with unified extraction architecture
- **Script**: `python scripts/batch_analyze.py --preset full`
- **Approved**: [ ] (Nolan must check this)
- **What it measures**: Full metadata extraction for all archive photos
- **Batch API**: Available at 50% discount (~$5.50 for full preset)
