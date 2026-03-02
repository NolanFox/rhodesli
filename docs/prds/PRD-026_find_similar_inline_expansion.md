# PRD-026: Find Similar Inline Expansion

## Problem Statement
Admin Find Similar currently breaks triage flow by navigating away or behaving inconsistently instead of expanding in-context beneath the initiating face card. Admin reviewers need to compare, merge, and reject candidate matches inline while preserving page context and velocity.

## Who This Is For
- Primary: admin reviewers triaging inbox/focus/browse identities
- Secondary: admin reviewers deduplicating confirmed identities
- Public users: separate shareable similar page behavior

## Requirements
1. Admin Find Similar expands inline beneath the originating face card without full-page navigation.
2. Multiple Find Similar panels may remain open simultaneously.
3. Expansion/collapse transitions are smooth and modern.
4. Expanded panel includes larger hero source face + identity context.
5. Similar faces render as horizontally scrollable tiles with compact actions.
6. Every similar tile exposes Compare, Merge, and Not Same actions.
7. Panel is collapsible via close affordance and toggle behavior.
8. Public mode preserves standalone shareable similar page route.
9. Vertical face card layout remains unchanged (horizontal regression is reverted).

## Success Criteria
- Admin can open 3 inline panels at once with no forced close.
- Inline panel displays similarity/confidence + action controls per tile.
- Merge and Not Same complete without page navigation.
- Grid reflow animates without flicker.
- Face cards remain vertical and consistent across admin surfaces.
