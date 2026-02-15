# Cleanup Backlog

Tracks outstanding cleanup tasks, failed operations, and technical debt.
Updated after each session.

## Open Items

### ML Pipeline Cleanup
- [ ] 21 unlabeled photos (community batch-20260214) — retry with API, then manual fallback
- [ ] 2 small files (<50KB) — investigate if real photos or artifacts
- [ ] 4 photos with repeated 504 DEADLINE_EXCEEDED — analyze file sizes, try resize
- [ ] Failure pattern analysis — correlate file size/dimensions with API failures
- [ ] Retrain CORAL after new labels added
- [ ] Regenerate photo_search_index.json after new labels

### Data Quality
- [ ] Verify all 157 original labels have source_method="api" backfill
- [ ] Confirm AD-051 has full 2.5-vs-3.0 bias documentation
- [ ] Spot-check 5 random labels from community batch for quality

### API Key Hygiene
- [ ] Rotate Gemini API key (exposed in Session 26 logs)
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
