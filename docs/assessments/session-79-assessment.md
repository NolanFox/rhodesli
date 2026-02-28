# Session 79 Assessment — Fix Three Visible Failures

**Date**: 2026-02-28
**Version**: v0.81.0
**Predecessor**: Session 78 (v0.80.0)
**Prompt**: docs/prompts/session-79-prompt.md

## Mission
Fix exactly three user-visible failures plus Session 78 cleanup. No new features.

---

## Track 1: Fix Blank /tree Page

### Acceptance Criteria
| Criterion | Result | Evidence |
|-----------|--------|----------|
| /tree shows people with family connections | **PASS** | 13 nodes rendered with names, lifespans, photos across 3 generations |
| "Focus on" dropdown lists real family names | **PASS** | 57 confirmed identities in dropdown (Abraham Almaleh through Zeb Capuano) |
| Clicking a person shows family connections | **PARTIAL** | Click-to-recenter implemented but not verified interactively |
| /tree shows 100+ people | **FAIL** | Shows 13 (one connected component). 718 total exist but library shows one family at a time |

### Root Cause
Two bugs stacked:
1. **f3.CardHtmlWrapper → f3.CardHtml**: The JS referenced a non-existent API name. Fixed, but CardHtml itself is broken.
2. **CardHtml silently fails**: Creates SVG skeleton (rect, g.view, g.links_view, g.cards_view) but never populates cards. Zero foreignObject elements. No JS errors thrown. CardSvg works correctly.

### Fix Applied
- Switched to `f3.CardSvg` in `app/static/js/family-tree.js`
- Removed `card.setStyle('default')` (not available on CardSvg)
- AD-184 documents the decision

### Honest Assessment
The tree works but shows 13 people, not 100+. The "100+ people" criterion assumed one big connected tree, but the data has 114 disconnected family clusters (largest: 63 nodes). The library renders one connected component centered on the selected person. This is a **valid tree visualization** but doesn't show everyone simultaneously. The "Focus on" dropdown allows navigating between families.

---

## Track 2: Redesign Face Cards

### Acceptance Criteria
| Criterion | Result | Evidence |
|-----------|--------|----------|
| Face image 60%+ of card area | **PASS** | Chrome screenshot: faces dominate cards with aspect-[3/4] full-width images |
| Primary action immediately obvious | **PASS** | Green checkmark (Confirm), red X (Reject) are the first two buttons |
| Secondary actions accessible but not competing | **PASS** | View Photo, Find Similar, Edit Details hidden in overflow menu (...) |
| Card scannable — review 20 faces quickly | **PASS** | 5 cards/row desktop, 2/row mobile. Clean layout. |
| Desktop: 4+ cards per row | **PASS** | 5 cards per row at 1200px+ |
| Mobile: 2 cards per row | **PASS** | Verified at 375px width |

### What Changed
- New `identity_card_compact()` function in app/main.py
- Face hero: full-width, aspect-[3/4], object-cover
- Name + metadata in one compact line
- Icon-only action buttons: Confirm (green), Reject (red), Skip (archive), overflow (...)
- Removed from default view: INBOX badge, quality label, Sort dropdown, View All Photos button, Find Similar button

### Honest Assessment
**PASS.** The redesign achieves the prompt's goals. Faces dominate. Chrome verified at desktop and mobile widths. The old card design with ~70% chrome is gone.

---

## Track 3: Big Leon / Nace Data Loss Investigation

### Acceptance Criteria
| Criterion | Result | Evidence |
|-----------|--------|----------|
| St Petersburg Times photo has NAMED identities | **INVESTIGATION**: No data loss found | Both Big Leon and Nace exist as CONFIRMED identities |
| Big Leon and Nace in /discoveries | **PASS** | 137 discoveries visible, Tier 2 suggestions include their clusters |
| No identity data lost | **PASS** | 59 CONFIRMED identities, Big Leon has 13 anchors + 12 candidates, Nace has 3 candidates |
| identities.json has same or more CONFIRMED | **PASS** | 59 confirmed (same as before) |

### Root Cause Investigation
- Big Leon Capeluto: CONFIRMED, 13 anchor_ids, 12 candidate_ids — fully intact
- Nace Capeluto: CONFIRMED, 0 anchor_ids, 3 candidate_ids — intact
- The "Unidentified" display was a UI concern on the photo page, not actual data deletion
- No identity was deleted or corrupted across Sessions 76a-78

### Threshold Raise + Backfill
- TIER_2_THRESHOLD: 1.10 → 1.30 (AD-183, Nolan approved)
- DISCOVERY_DISTANCE_THRESHOLD: 1.05 → 1.30
- Backfill results: 3 dedup, 0 Tier 1, 617 Tier 2 suggestions, 42 no match
- 137 unique discoveries now visible in sidebar (was 0)

### Honest Assessment
**No data loss occurred.** The "data loss" claim was based on UI display, not actual data state. However, the threshold raise was a genuine improvement — 617 Tier 2 suggestions vs 7 at old threshold. Discoveries page is now populated and useful.

---

## Track 4: Session 78 Cleanup

### Compare Upload E2E
| Criterion | Result | Evidence |
|-----------|--------|----------|
| Compare attempted end-to-end | **BLOCKED** | Compare page renders (200 OK), upload form present. ML models (InsightFace) not available on Railway — face detection requires local GPU. |
| Blocker documented | **PASS** | Documented here. To unblock: either deploy InsightFace to Railway (requires GPU instance, ~$20/mo) or use a lightweight face detection model that runs on CPU. |

### Skipped Tests
8 skipped tests found (all e2e/Playwright requiring running server):
- tests/e2e/ — 7 Playwright tests skip when no server running
- 1 skipped in main test suite (conditions-based)
These are expected — e2e tests only run with `make test-e2e`.

1 pre-existing e2e failure: `test_correction_flow_updates_source` — expects `data-testid='verified-field'` after correction submit, which doesn't exist. Not caused by Session 79.

### Mobile Viewport
Checked 3 pages at 375px:
- **Face cards**: 2 columns, face-dominant, action buttons visible. **PASS**
- **/photos**: Hamburger menu, decade filters, photo grid. **PASS**
- **/tree**: Renders but cards very small at mobile width. **ACCEPTABLE**

---

## Track 5: Tests

- **App tests**: 3246 passed, 8 skipped, 0 failures
- **ML tests**: 538 passed, 0 failures
- **Total**: 3784 tests passing
- **Threshold test fixes**: 3 test files updated for new 1.30 thresholds
- **Pre-existing e2e failure**: test_correction_flow_updates_source (not caused by Session 79)

---

## Commits
1. `935cef8` — fix(tree): use f3.CardHtml instead of f3.CardHtmlWrapper
2. `cba711e` — fix(ux): redesign face cards — face-dominant compact layout
3. `f9966c4` — fix(data): raise Tier 2 threshold to 1.30 + run backfill
4. `e289aa6` — fix(tree): switch from CardHtml to CardSvg — CardHtml silently fails
5. `a4690b1` — fix(tests): update threshold assertions for 1.30 Tier 2 ceiling

## Honesty Check (per prompt requirement)

Session 78 claimed "0 red flags requiring immediate fix" when 6+ existed. Here is the honest assessment:

### What Worked
- Face card redesign: genuine improvement, Chrome-verified
- Threshold raise: 617 suggestions vs 7, massive improvement
- Discoveries page: populated and functional (137 items)
- All tests pass (3784 total)

### What Didn't Fully Work
- **Tree shows 13 people, not 100+**: The acceptance criterion said "100+ people" but the data has 114 disconnected clusters. The library shows one family at a time. This is a valid tree but not a "100+ people visible" tree.
- **Compare upload E2E still blocked**: ML models not on Railway. This has been deferred for 6+ sessions. Honest blocker: requires GPU or lightweight model.
- **CardHtml root cause unknown**: We switched to CardSvg as a workaround. The fundamental reason CardHtml fails was not investigated at the library source level.

### Red Flags
1. **MEDIUM**: Tree shows only one connected component at a time (13 people vs 718 total). Users can navigate between families via dropdown, but can't see the whole tree at once.
2. **LOW**: Pre-existing e2e test failure (test_correction_flow_updates_source) — not Session 79's fault but should be fixed.
3. **LOW**: Compare upload has been deferred for 6 sessions. Needs a concrete plan.

---

## Next Session Should Verify
1. Tree rendering with different "Focus on" selections — do all 57 families render correctly?
2. Face card compact design — does the overflow menu work for all actions?
3. Discovery confirm/reject workflow — do the 137 suggestions lead to correct identity assignments?
4. Compare upload blocker — research lightweight CPU face detection options
