# Session 79 Log — Fix Three Visible Failures
## Mission: Fix tree, face cards, Big Leon/Nace + Session 78 cleanup
## Started: 2026-02-28
## Context: docs/session_context/session-79-context.md
## Predecessor: Session 78 (v0.80.0)

### Track 1: Fix Blank /tree Page
- [x] Diagnosed: f3.CardHtmlWrapper undefined → f3.CardHtml
- [x] Discovered: CardHtml silently fails (zero cards rendered)
- [x] Fixed: Switched to f3.CardSvg — cards render correctly
- [x] Chrome verified: 13-node family tree with names/photos/lifespans
- [x] Focus dropdown: 57 confirmed identities listed
- [ ] 100+ people visible simultaneously (not achievable with disconnected graph)

### Track 2: Redesign Face Cards
- [x] New identity_card_compact() function
- [x] Face hero: full-width, aspect-[3/4], object-cover
- [x] Icon-only action buttons (confirm/reject/skip/overflow)
- [x] 5 cards/row desktop, 2/row mobile
- [x] Chrome verified at desktop and 375px mobile widths

### Track 3: Big Leon/Nace + Threshold
- [x] Investigation: NO data loss — both identities CONFIRMED with full faces
- [x] TIER_2_THRESHOLD: 1.10 → 1.30 (AD-183)
- [x] DISCOVERY_DISTANCE_THRESHOLD: 1.05 → 1.30
- [x] Backfill: 617 Tier 2 suggestions, 137 unique discoveries
- [x] Chrome verified: Discoveries page shows 137 items

### Track 4: Session 78 Cleanup
- [x] Compare page renders (200 OK)
- [x] Compare upload blocked: InsightFace not on Railway (documented)
- [x] Skipped tests: 8 skipped (all e2e Playwright, expected)
- [x] Mobile viewport: 3 pages checked at 375px (all PASS)

### Track 5: Deploy + Verify + Docs
- [x] All commits pushed to main
- [x] Chrome verification: tree, face cards, discoveries
- [x] Tests: 3246 app + 538 ML = 3784 passing
- [x] Assessment: docs/assessments/session-79-assessment.md
- [x] AD-183 (threshold raise), AD-184 (CardSvg)
- [x] CHANGELOG v0.81.0
- [x] Session log written

### Version
v0.80.0 → v0.81.0
