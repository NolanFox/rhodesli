---
name: Always evaluate screenshots critically
description: Every screenshot from user must be critically evaluated for UX bugs, data issues, design problems — not just the issue user mentions
type: feedback
---

Every screenshot the user sends must be evaluated critically and comprehensively — not just for the issue they're calling out, but for EVERYTHING visible.

**Why:** Session 129 — user sent 9 screenshots focused on a data issue (duplicate Esther Burd). Claude initially only logged the specific issue the user mentioned, missing 10 additional UX/navigation/design issues visible in the screenshots (face crops not clickable, wrong community names in dropdown, 2-column grid wasting space, green button misleading state, etc.).

**How to apply:** For every screenshot received:
1. Evaluate the specific issue the user mentions
2. Scan the ENTIRE screenshot for: layout problems, incorrect states, misleading visual cues, missing interactions, navigation dead-ends, accessibility issues, mobile responsiveness, text readability, color/contrast, button states, data display issues
3. Log EVERY issue found as a separate FB-NNN entry
4. This is the DEFAULT behavior during interactive/triage sessions — user should never have to ask for it
