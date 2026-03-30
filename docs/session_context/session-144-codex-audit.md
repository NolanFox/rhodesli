# Session 144 Codex Audit Summary

**Auditor**: Codex CLI v0.117.0 (o4-mini)
**Agent type**: Independent (fresh context)
**Date**: 2026-03-29

## Audit 1: Phase 0 Code Changes
- **Scope**: GEDCOM import, face analysis, GEDCOM search display
- **Findings**: 4 P1, 1 P2, 1 P3 — ALL fixed
- **Value**: STRONG — caught cache key mismatch and datetime serialization

## Audit 2: Phase 4 Anchor Compare
- **Scope**: Anchor compare route, admin UI, tests
- **Findings**: 2 P1, 1 P2, 1 P3 — ALL fixed
- **Value**: STRONG — caught missing anchor date validation and malformed output handling

## Audit 3: Quality Comparison (Run A vs Run B)
- **Scope**: Gemini output quality with/without GEDCOM
- **Finding**: MODERATE improvement. Location inference is the big win. Date shift (1918→1915) is within noise.
- **Recommendation**: Record as "circa 1912-1918, probably mid-1910s, likely New York area"

## Audit 4: Identity Investigation (Persons 3481 + 3772)
- **Scope**: Identity of woman in penny arcade photo + Albert Fox recognition failure

### Person 3481
- 3 faces internally tight (0.72-0.79) — definitely one person
- Esther Burd ruled out: embedding distance 1.34, born ~1900 (too young)
- **Rachel Fox (born Oct 1891)**: strongest candidate
- Sadie Fox: runner-up

### Person 3772
- Embedding distance to Albert: 1.29 (best face-to-face)
- Confidence scorer gives 27%, calibrator gives 32% — NOT 0%
- **0% display is a UI bug** — stale or alternate display path
- 2579 and 3503 are from women-only group shots — false positives despite closer embedding distance
- **Root cause**: age/era/pose/domain shift pushes military uniform Albert outside cluster
- Fox family resemblance problem: all siblings equidistant (~1.0-1.3)

## Audit 5: 144b Prompt (pending — Codex still running)
