# Session 65a Log
## Plan: Upload fix → Compare overhaul → Prompt fidelity → UX polish → Docs
## Started: 2026-02-23

## Phase 0: Orient + Quick Fixes
- [x] 0A: Orient — read CLAUDE.md, ROADMAP, AD, session context, lessons
- [x] 0B: Pre-commit hook regex fix — `^git commit` → `\bgit commit\b`
- [x] 0C: Verify 64d production data:
  - Alignments: 269 ✓ (expected 269)
  - API calls: 156 ✓ (expected 156)
  - Duplicates: 0 ✓
  - Models: gemini-3.1-pro-preview + gemini-2.5-flash (flash from earlier Session 61C)
  - Failing photos (Image 914, Image 018): no alignment records (expected — they fail parsing)
- [x] 0D: AD-157 updated with actual 64d findings (batch API too slow, sync pipeline better)

## Phase 1: Fix Uploads (CRITICAL)
- [x] 1A: Diagnosis — root cause identified:
  - Subprocess spawns `python -m core.ingest_inbox` for face detection
  - InsightFace IS available on Railway (confirmed via /health)
  - If subprocess crashes (OOM during 300MB model load), status stays at "processing"
  - Status poller had timeout for "starting" state but NOT for "processing" state
  - UI polled forever showing "Processing 0/1 (0%): filename"
- [x] 1B: Fix implemented:
  - Store subprocess PID in status file
  - Check if PID still alive on each poll
  - Add 5-minute timeout for "processing" state
  - Show error with log excerpt when subprocess dies
  - Reassure user their photo was saved in staging
  - write_status_file() preserves started_at + pid across updates
- [x] 1C: Tests — 8 new tests covering death detection, timeout, alive-check, log display
- [x] Pushed to production

## Phase 2: Compare Face Overhaul
- [x] 2A: New route GET /compare/pair — two-panel layout with upload zones
- [x] 2B: POST /api/compare/pair/upload — face detection, crop generation, face selector UI
- [x] 2C: POST /api/compare/pair/match — cosine similarity with calibrated confidence tiers
- [x] 2D: Link from main /compare page to /compare/pair
- [x] 2E: 11 new tests covering page, uploads, math
- [x] Pushed to production

## Phase 3: Prompt Fidelity Investigation
- [x] 3A: Queried gemini_api_calls — 136 calls in 64d batch
- [x] 3B: Call type distribution: 119 alignment + 17 combined (GEDCOM-enriched)
- [x] 3C: Token analysis: GEDCOM adds ~106 tokens/call for 1-face photos
- [x] 3D: Token variation driven by face count (~25 tokens/face), not GEDCOM
- [x] 3E: gemini_config/response_summary NULL for all records — gap in logging
- [x] 3F: Findings written to docs/analysis/prompt_fidelity_64d.md
- [x] 3G: AD-159 created with findings and recommendations
