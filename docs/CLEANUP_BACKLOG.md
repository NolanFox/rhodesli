# Cleanup Backlog

Tracks outstanding cleanup tasks, failed operations, and technical debt.
Updated after each session.

## Open Items

### ML Pipeline Cleanup
- [ ] Add `--fallback-model` flag to generate_date_labels.py for automatic 2.5-flash retry (labels will auto-set training_eligible=false)

### Data Quality
- [ ] Verify all 157 original labels have source_method="api" backfill
- [ ] Confirm AD-051 has full 2.5-vs-3.0 bias documentation
- [ ] Spot-check 5 random labels from community batch for quality
- [x] Re-label 9 gemini-2.5-flash photos with gemini-3-flash (or remove from training) — these hurt model accuracy by ~12% → Fixed via training_eligible=false flag (AD-061, 2026-02-15)

### API Key Hygiene
- [x] Rotate Gemini API key (rotated 2026-02-15)
- [ ] Add GEMINI_API_KEY to ~/.zshrc so Claude Code doesn't echo it
- [ ] Verify no API keys in git history

### Deployment Reliability
- [x] Production smoke tests (tests/smoke/test_production.py)
- [x] deploy_and_verify.sh script
- [ ] Document all data files that must be in deploy pipeline
- [ ] Audit: are there other data files not in sync lists?

### Deferred from Session 27 PRD
- [ ] Timeline visualization (needs 500+ photos)
- [ ] Map view (needs geocoding pipeline)
- [ ] Probability distribution rendering
- [ ] Confidence heatmap mode
- [ ] Generational spread view
- [ ] Decade auto-narrative
- [ ] Photo comparison tool
- [ ] Add location_structured to Gemini prompt (AD-057)

## Done
- [x] clean_labels.py created and verified
- [x] batch_label.sh created for future large runs
- [x] source_method field added to label schema
- [x] add_manual_label.py created for manual ingestion
- [x] process_uploads.sh verified
- [x] Date badges deployed to production (Session 27)
- [x] Deploy fix: date_labels.json + photo_search_index.json added to pipeline
- [x] AI Analysis panel wired into Photo Context modal (Session 28)
- [x] 271/271 photos labeled — 0 unlabeled remaining (Session 28)
- [x] 2 small files (<50KB) investigated — valid photos, not artifacts (Session 28)
- [x] Failure pattern analysis — 504 errors are infrastructure-side, NOT file-size related (Session 28)
- [x] gemini-2.5-flash fallback: 9/9 success on photos that 3-flash couldn't handle (Session 28)
- [x] CORAL model retrained with 271 labels (best val_accuracy=60.3%, val_MAE=0.534) (Session 28)
- [x] Diagnosed regression: old rng-based split had 19% val overlap between runs (Session 29)
- [x] Fixed: hash-based train/val split — stable across dataset size changes (Session 29)
- [x] Retrained 250 labels (hash split): acc=67.9%, MAE=0.358 (Session 29)
- [x] Retrained 271 labels (hash split): acc=55.4%, MAE=0.607 (Session 29)
- [x] Confirmed: 21 new labels (9 gemini-2.5-flash) genuinely hurt model — not just split noise
- [x] photo_search_index.json regenerated with 271 documents (Session 28)
- [x] Failure analysis saved to rhodesli_ml/data/model_comparisons/failure_analysis.md (Session 28)
