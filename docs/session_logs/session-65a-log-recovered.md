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

## Phase 4: UX Quick Wins
- [x] 4A: Face overlay toggle — button on photo viewer + public photo page
  - Admin default: overlays ON ("Hide Faces" button)
  - Non-admin default: overlays OFF ("Show Faces" button)
  - Uses data-action event delegation (Lesson 39)
  - Legend also toggles with overlays
- [x] 4B: Share links — already exist on person pages (share_button with clipboard copy + toast)
- [x] 4C: Cross-page navigation audit — all critical paths bidirectional
  - Photo → Person (face overlay click), Person → Photo (gallery), Collection → Photo (grid cards)
  - Public photo page has collection links, prev/next carousel, share button
- [x] 4D: 5 new UX tests

## Phase 5: Docs Sync + Session Close
- [x] 5A: CHANGELOG.md — v0.68.0 entry with all session work
- [x] 5B: ROADMAP.md — version/test count updated, session 65a in Recently Completed
- [x] 5C: BACKLOG.md — version updated
- [x] 5D: ALGORITHMIC_DECISIONS.md — AD-159 verified with full provenance
- [x] 5E: SESSION_HISTORY.md — Session 65a entry + version table
- [x] 5F: Verification gate — all checks PASS

## Session 65a Complete
- Phases completed: 0, 1, 2, 3, 4, 5 (all 6)
- Commits: 6 (orient, upload fix, compare, prompt fidelity, UX, docs)
- Tests: 2956 app + 537 ML = ~3493 total
- Upload: FIXED (subprocess death detection + timeout)
- Compare: OVERHAULED (two-photo pair comparison)
- Prompt fidelity: VERIFIED (12.5% GEDCOM-enriched, ~106 tokens delta)
- UX: Face overlay toggle (admin ON, non-admin OFF)
- Deploy: Ready to push
