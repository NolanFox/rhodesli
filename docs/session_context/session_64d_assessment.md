# Session 64d Assessment
## "Batch Process Remaining 144 Photos"

- **Duration**: ~45 minutes (including 15-min batch wait + 20-min sync run)
- **Photos processed**: 142/144 (2 consistently fail)
- **Total aligned**: 269/271 (99.3%)
- **Total cost**: $1.19
- **Average cost/photo**: $0.0077
- **Model used**: gemini-3.1-pro-preview (verified — all 146 session calls)
- **Errors**: 2 (same 2 photos: Image 914 + Image 018)
- **Rate limits hit**: 0

## Shipped

- [x] Phase 1: Pre-flight checks — API accessible, 144 photos identified, Batch API available
- [x] Phase 2: Batch API submitted (144 requests), but took >15 min — fell back to synchronous
- [x] Phase 2-ALT: Synchronous pipeline processed all 136 remaining (after 8 from initial test run)
- [x] Phase 3: Results verified in Supabase — 269 alignments, $1.19 cost, 0 model drift
- [x] Phase 5: Session assessment (this document)

## Alignment Coverage

- Before 64d: 127/271 (47%)
- After 64d: 269/271 (99.3%)
- Remaining: 2 photos (Image 914_compress.jpg, Image 018_compress.jpg)

## Cost Analysis

| Metric | Estimated | Actual |
|--------|-----------|--------|
| Per-photo cost | $0.037 | $0.0077 |
| Total cost (144 photos) | $5.33 | $1.19 |
| Budget used | 107% | 24% |

The 5x cost difference is because the pricing estimate ($0.037/photo) assumed a higher token count per photo. Actual average: ~1,640 input tokens + ~475 output tokens per photo.

## GEDCOM Enrichment

- Photos with GEDCOM context: 18 (12.5% of batch)
- Photos without GEDCOM context: 124 (87.5%)
- Only photos with confirmed identities linked to GEDCOM records get enrichment
- Quality observation: GEDCOM-enriched photos tend to have slightly higher token counts (more context in prompt), but similar success rate

## Batch API Observations

- Gemini Batch API was accessible and accepted image+text InlinedRequests
- But processing was extremely slow — even a 1-request test batch didn't complete in 20+ minutes
- Synchronous pipeline completed all 136 photos in ~20 minutes with 3-second delay between calls
- Batch API would save 50% cost but the latency makes it impractical for interactive sessions
- Both test and main batch jobs were cancelled after sync completion

## 2 Failing Photos

| Photo ID | File | Faces | Issue |
|----------|------|-------|-------|
| 9411826ba358db3c | Image 914_compress.jpg | 1 | Gemini returns 200 but alignment parser fails |
| 81bf7f85ec9814bc | Image 018_compress.jpg | 1 | Gemini returns 200 but alignment parser fails |

Both are single-face legacy photos. The Gemini response might have malformed JSON or the response text is empty despite 200 status. Low priority — single-face photos don't benefit much from alignment.

## Red Flags

- **LOW**: Batch API latency was unexpectedly high (>20 min for 1 request). May have been a temporary Google infrastructure issue, or batch API is not optimized for vision tasks.
- **LOW**: 2 photos consistently fail alignment parsing. Should investigate the actual Gemini response content for these.
- **INFO**: The Batch API also submitted 144 duplicate requests that were later cancelled. No data loss since sync results were saved to Supabase first.

## Next Session Should Verify FIRST

1. Production photo pages show face descriptions for newly aligned photos
2. `face_gemini_alignments` table has 269 records
3. No duplicate alignment entries from batch + sync overlap
4. The 2 failing photos don't cause errors on their photo pages

---
*Predecessor: [Session 64b Assessment](docs/session_context/session_64b_assessment.md)*
*Prompt: [docs/prompts/session-64d-prompt.md](docs/prompts/session-64d-prompt.md)*
