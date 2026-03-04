# Session 87 Planning Context

**Date**: 2026-03-04
**Predecessor**: [Session 86b context](docs/session_context/session-86b-context.md) (v0.90.0 — Route Extraction + Deferred UX Fixes)
**Trigger**: User feedback from real-world usage — sharing Purim 1922 photo identifications on Facebook
**Plan**: [Session 87 plan](../../.claude/plans/moonlit-discovering-key.md)
**Prompt**: `docs/prompts/session-87-prompt.md` (to be created in Act 1)
**Session log**: `docs/session_logs/session-87-log.md` (to be created in Act 1)
**Assessment**: `docs/assessments/session-87-assessment.md` (to be created in Act 7)

---

## User Scenario

Nolan uploaded `claude_benatar_purim_1922_646723611_10174283698525346_748045227922631717_n.jpg` via Claude Benatar on the Jews of Rhodes Facebook group (~2,000 members). Community members Susan Amira and Leo Di Leyo are commenting. Nolan is trying to identify people and share comparison results. The current UX required 10+ clicks to find and share the Netanel Menashe match.

## Research Findings

### A. Scoring Inconsistency (CRITICAL BUG)

**4+ different confidence calculation paths** produce different scores for the same Euclidean distance:

| Path | Location | Method | dist 1.13 → |
|------|----------|--------|-------------|
| A (archive) | core/neighbors.py:346-383 | `calibrated_similarity_batch()` or `_compute_confidence_pct()` CDF | **62%** |
| B (vs-person) | compare_routes.py:1748-1756 | `SimilarityCalibrator.predict()` or sigmoid `1/(1+exp(2*(d-1.1)))` | **48%** |
| C (vs-person dup) | compare_routes.py:2152-2159 | Same as B | **48%** |
| D (pair compare) | compare_routes.py:3439-3451 | Linear `(1-d/2)*100` then tries calibrator | **43%** or calibrated |
| E (entity) | compare_routes.py:3677-3686 | Same as B | **48%** |
| F (discoveries) | main.py:5065-5073 | Pure distance tiers, no percentage | tier only |

Additionally, 3 separate `_confidence_tier()` definitions in main.py with different thresholds.

**Confidence label thresholds** (consistent across paths):
- 85%+ = "Very likely same person" / STRONG MATCH
- 70-84% = "Strong match" / POSSIBLE MATCH
- 50-69% = "Possible match" / SIMILAR
- <50% = "Unlikely match" / WEAK

So 48% → "Unlikely" but 62% → "Possible match". Same distance, different user experience.

### B. Compare Page UX Issues

- **8 face accordions**: User must scroll through Face 1-8 to find one good match
- **80px circle face images**: Too small to judge similarity (result cards `w-20 h-20`)
- **No summary**: Best match buried under "Face 7" with no indication it's the most interesting
- **Flat sorting**: All matches sorted by distance within each face, not by importance across faces
- **"Unlikely" label at 48%/62%**: Discouraging for actually plausible matches

### C. Shareable Result Page Issues

- **Tiny face**: 48% face circle with "Unlikely match (dist: 1.13)"
- **"No strong matches found"**: Even when there IS a match
- **Sparse layout**: No source photo context, no compelling visual
- **OG tags generic**: Don't mention the matched person's name

### D. Discoveries Page Issues

- **184 entries, no filter/sort**: Netanel match buried
- **No inline comparison**: Can't see more detail without leaving page
- **Small face images**: Though larger than compare (96px), still `rounded-full`
- **No photo filter**: Can't narrow to "discoveries from Purim 1922 photo"

### E. Identity Card Navigation Issues

- **Detach/unmerge button hidden**: Only appears on hover of individual face cards within face gallery
- **"Photos" button misleading**: Opens photo lightbox, not face gallery
- **Face gallery hard to reach**: Accessed via sort dropdown, not obvious
- **Netanel Menashe (2 faces)**: Card shows "2" badge but no way to see both crops or detach
- **Key code**: Detach endpoint at main.py:21910, face gallery at main.py:20694, photos button at main.py:7187

### F. Netanel Menashe Auto-Clustering

- **Identity UUID**: 64096284-ace8-4790-aebb-a82ff1f288a5 (CONFIRMED)
- **Distance to UP 531**: 1.225 → correctly Tier 2 (suggested, not auto-added)
- **Distance to UP 851**: 1.13 → also Tier 2
- **In discovery_log.json**: Logged as Tier 2 suggestion on 2026-02-28
- **Shows in Discoveries page**: As "Possible match" — system working as designed
- **Thresholds**: Tier 1 < 0.85 (auto-add), Tier 2 0.85-1.30 (suggest). AD-179, AD-183.

## Key Files

| File | Lines | What to Change |
|------|-------|---------------|
| `core/confidence.py` (NEW) | ~80 | Unified scoring function |
| `core/neighbors.py` | 416 | Refactor tier assignment to use unified scoring |
| `app/compare_routes.py` | 4,642 | Replace 4 scoring paths, summary view, shareable page |
| `app/main.py` | ~23,000 | Replace `_confidence_tier()` defs, discoveries sort/filter, face card nav |
| `tests/test_confidence.py` (NEW) | ~60 | Score consistency tests |
| `tests/test_compare.py` | ~650 | Summary view tests, shareable page tests |
| `tests/test_discoveries.py` | ~200 | Sort/filter tests |

## User Feedback (Direct Quotes, paraphrased)

1. "Each piece of the UX was missing something vital"
2. "The compare site still feels brittle and not interactive"
3. "Pictures are too small to see"
4. "The scores are hard to parse"
5. "The matches are not organized in a reasonable way that surfaces comparisons first"
6. "This whole flow was very manual in a way that it should have been automatic"
7. "The Discoveries section seems to be completely broken"
8. "You can't even compare the matches [in Discoveries]"
9. "I don't have a way to unmerge for Netanel Menashe"
10. "There is no way to actually see the multiple faces associated with Netanel"

## Decisions Made During Planning

| ID | Decision | Rationale | See Also |
|----|----------|-----------|----------|
| AD-200 (planned) | Unified Confidence Scoring | 4+ divergent scoring paths cause same match to show 62% or 48%. Single `core/confidence.py` module. | `core/confidence.py`, `docs/ml/ALGORITHMIC_DECISIONS.md` |
| DD-007 (planned) | Compare "Best Matches" summary | Users shouldn't dig through 8 accordions. Surface best matches first, collapse detail. | `app/compare_routes.py` |
| DD-008 (planned) | Shareable page positive framing | "Could this be [Name]?" instead of "Unlikely match". Optimized for Facebook sharing. | `app/compare_routes.py` |
| UX-110 (planned) | Identity card faces button + visible detach | Detach/unmerge hidden behind hover + obscure navigation. Make always visible for admin. | `app/main.py` |

## Work Deferred to Future Sessions

- **Photo Page ML Suggestions** — show per-face ML match suggestions on the photo detail page. Needs stable scoring first. Complex overlay system. → Session 88. BACKLOG: ML-110.

## Post-Session Planning

**Candidate Session 88**: Photo Page Intelligence
- Per-face ML suggestion tooltips on photo detail page
- "This could be [Name] (62%)" badge on each face overlay
- One-click compare from photo page
- Prerequisite: Session 87 scoring unification must be stable

**Candidate Session 89**: Navigation & Information Architecture
- Unify the sidebar sections (New Matches vs Discoveries vs Help Identify)
- Consider merging into a single "Review" workflow with filters
- Address the 477 New Matches backlog

## Screenshots Provided

10 screenshots showing:
1. Facebook post (Purim 1922 photo, community discussion)
2. Facebook comments (identification attempts)
3-5. Compare page (8-face accordion, buried matches, Netanel at 62%)
6. Browse page with Similar sidebar (Netanel at 1.13)
7. Person-to-person compare (same match shows 48% not 62%)
8. Shareable result page (tiny face, "Unlikely match")
9-10. Discoveries page (184 entries, Netanel buried)
