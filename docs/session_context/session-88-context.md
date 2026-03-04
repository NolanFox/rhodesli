# Session 88 Context

**Predecessor**: Session 87 (v0.91.0) — docs/session_context/session-87-context.md
**Prompt**: docs/prompts/session-88-prompt.md
**Log**: docs/session_logs/session-88-log.md

## Problem Statement
Session 87 claimed to unify confidence scoring (AD-200) and improve Compare/Discoveries UX but 5 failures remain:
1. Scoring still divergent (62% vs 43% for same distance)
2. Discovery cards missing features vs neighbor cards
3. Compare link from Discoveries broken
4. Accordion headers show no match preview
5. Admin badge noise on every card

## Key Decisions
- Calibrator everywhere, no dual display, no admin badges per card
- Unified match_card() additive from neighbor_card base
- Accordion: "Face N -- X matches (best: [Name] [Pct]%)"
- Admin badge -> subtle gear icon

## Deferred
(none planned)

## Post-Session Planning
(to be filled at session end)
