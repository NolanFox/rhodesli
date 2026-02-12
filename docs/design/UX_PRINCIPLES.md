# UX Principles — Rhodesli

**Last updated:** 2026-02-11

Rhodesli is not a photo management app. It is a consensus engine where ML proposes hypotheses and humans adjudicate historical truth. The UX must serve that mission.

---

## Core Metaphor

**Sitting with grandma and a box of photos.**

The experience should feel like discovery, not triage. Every interaction should build understanding of who these people are, how they're connected, and what their stories are.

---

## Principles

### 1. Context > Crops

People identify faces by who else is in the photo, the setting, the era, the collection — not by looking at a 64px crop in isolation. Photo context must be ONE CLICK from anywhere a face appears.

### 2. Bidirectional Navigation

A→B means B→A must exist. No dead ends. Every screen has a way back, a way forward, and a way to the thing you're looking at in its full context.

### 3. Surface Easy Wins First

High-confidence matches before cold cases. The admin's time is best spent on items where one click resolves an identification, not on ambiguous 0.9-distance pairs.

### 4. Merge != Confirm

Encourage merging same-person faces even without a name. "I don't know who this is, but these three crops are definitely the same person" is valuable signal. Celebrate grouping.

### 5. Show Provenance

"AI grouped" vs "Merged by admin on Feb 10" vs "Confirmed by family member." Trust comes from transparency about how each decision was made.

### 6. Consistent Visual Language

Same component should look and behave the same across Inbox, Needs Help, People, and Focus mode. A face card is a face card everywhere.

### 7. Co-occurrence is Signal

Two unidentified people in multiple photos together are likely related. Surface this: "These two appear in N photos together."

### 8. Quality Scores are for Engineers

Translate ML metrics to human language for non-admin users:
- VERY HIGH → "Strong match"
- HIGH → "Good match"
- MODERATE → "Possible match"
- LOW → "Weak match"

Never show raw distances, sigma values, or embedding dimensions.

### 9. Mobile is Primary

Older community members browse on phones. Minimum 16px text, 44px touch targets, no horizontal scroll.

### 10. Gender as Soft Signal

Subtle visual indicator, never a hard filter. Cross-gender high similarity → "Possible family resemblance" rather than hiding the match.

---

## Anti-Patterns

- Raw ML metrics shown to users
- 200+ item scroll with no prioritization
- Dead-end navigation (no way back, no way forward)
- Inconsistent behavior by entry point
- Modals too small for content
- Actions requiring full page refresh
- Confirmation dialogs for non-destructive actions
- Hiding merged-but-unnamed identities

---

## Learnings

_(Updated as we discover what works and what doesn't)_

- Event delegation is mandatory for HTMX apps — DOM nodes get swapped
- Filter context must propagate through the entire action chain
- Post-merge UI should show what happened and suggest next actions
- Focus mode works best when sorted by actionability, not chronology
