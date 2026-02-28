# Session 79 Log — Fix Three Visible Failures
## Mission: Fix tree, face cards, Big Leon/Nace + Session 78 cleanup
## Started: 2026-02-28
## Version: v0.80.0 → v0.81.0
## Context: docs/session_context/session-79-context.md
## Predecessor: Session 78 (v0.80.0)

### Track 1: Fix Blank /tree Page
- [x] Diagnosed CardHtmlWrapper → CardHtml name mismatch
- [x] Discovered CardHtml silently fails (zero cards rendered)
- [x] Switched to CardSvg — 13-node family tree renders correctly
- [x] Chrome verified: names, lifespans, photos across 3 generations
- [x] Focus dropdown: 57 confirmed identities
- [x] AD-184: CardSvg replaces CardHtml

### Track 2: Redesign Face Cards
- [x] New identity_card_compact() — face hero 60%+ of card
- [x] Icon-only actions: confirm/reject/skip/overflow
- [x] 5 cards/row desktop, 2/row mobile
- [x] Chrome verified at desktop + 375px mobile

### Track 3: Big Leon/Nace + Threshold
- [x] Investigation: NO data loss — both CONFIRMED with full faces
- [x] TIER_2_THRESHOLD: 1.10 → 1.30 (AD-183, Nolan approved)
- [x] DISCOVERY_DISTANCE_THRESHOLD: 1.05 → 1.30
- [x] Backfill: 617 Tier 2 suggestions, 137 discoveries in UI
- [x] Chrome verified: discoveries page populated

### Track 4: Session 78 Cleanup
- [x] Compare: page renders, upload blocked (InsightFace not on Railway)
- [x] Skipped tests: 8 e2e (expected), 1 pre-existing e2e failure
- [x] Mobile: 3 pages at 375px — all PASS

### Track 5: Deploy + Docs
- [x] All pushed to main, deployed
- [x] Tests: 3246 app + 538 ML = 3784 passing
- [x] Assessment: docs/assessments/session-79-assessment.md
- [x] AD-183, AD-184 written
- [x] CHANGELOG v0.81.0, SESSION_HISTORY, ROADMAP updated
