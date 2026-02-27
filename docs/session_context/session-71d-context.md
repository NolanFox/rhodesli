# Session 71D Planning Context: Discoveries Feature Fix
# Date: 2026-02-26
# Breadcrumbs: Session 15 (reclustering design) → Session 18c (focus mode) → Session 70 assessment → Dogfooding Feb 26

---

## 1. ORIGINAL DESIGN INTENT — THREE REVIEW SECTIONS

The three review sections were designed as a priority-tiered workflow, NOT three independent review areas. Here's what each was supposed to be:

### New Matches (405) — The Main Triage Inbox
- All faces where the AI found potential matches
- Admin reviews each: Confirm, Skip, or Reject
- Contains both high and low confidence proposals
- Has Focus mode (side-by-side comparison) and Browse mode (scroll through all)
- Triage bar shows "50 Ready to Confirm | 355 Unmatched"

### Discoveries (1) — Proactive High-Confidence Notifications
- **Purpose**: When the system discovers something the admin should act on IMMEDIATELY
- **Design intent (Session 15)**: Three promotion scenarios:
  1. `confirmed_match`: A previously skipped face now matches a CONFIRMED identity (most valuable — one-click merge)
  2. `new_face_match`: A newly uploaded photo matches a previously skipped face (new context available)
  3. `group_discovery`: Two skipped faces from different batches now cluster together (rediscovered)
- **Key UX principle**: These should be the HIGHEST-VALUE, LOWEST-EFFORT actions. One click to merge.
- **Current state**: Shows 1 discovery — "Unidentified Person 768" matches "Big Leon Capeluto" at 54%

### Help Identify (202) — Cold Cases for Community
- Faces the system couldn't match confidently
- "Your family knowledge could be the key" — designed for community members, not just admin
- Has Focus mode showing WHO IS THIS? / BEST MATCH side-by-side
- These are the hardest cases — low confidence or no matches at all

### The Information Architecture Problem
The INTENT was a funnel:
```
Discoveries (act NOW, one click) → New Matches (review, decide) → Help Identify (needs human knowledge)
```

But the EXECUTION created three confusing, overlapping sections with inconsistent UX, broken navigation, and unclear differentiation. A user seeing all three for the first time has no idea which to start with or how they're different.

---

## 2. DOGFOODING FINDINGS — DISCOVERIES IS BROKEN

### Bug: No Navigation from Discoveries (CRITICAL)
- Cannot click on either person photo to go to their face card
- Cannot navigate to the source photo
- Dead-end page — user can "Confirm as Big Leon Capeluto" or "Not a match" but can't investigate further
- Violates UX Principle #3: "Bidirectional navigation is mandatory. A→B means B→A must exist. No dead ends."

### Bug: 54% Match Seems Low for "High Confidence" (CONFUSING)
- Discovery page says "1 high-confidence match" but shows 54%
- 54% doesn't feel "high confidence" to a user
- What does 54% actually map to in terms of distance? The ML pipeline uses distance thresholds (0.91 = High, 1.09 = Moderate, etc.) — how was 54% calculated?
- Need to determine: Is this a percentage conversion of distance? A different metric? A bug in the display?
- The New Matches page shows "Dist: 0.91 +31.7% gap" for the same Big Leon match — that's the real metric, and 0.91 IS a strong match

### Bug: Only Leon, Not Nace (LOGIC ISSUE)
- The photo (Screenshot 4) clearly shows TWO Capeluto men: Leon and Nace
- Text in the photo literally says "LEON CAPELUTO" and "NACE CAPELUTO"
- Both should be Discoveries, but only Leon appears
- Questions: Did the system detect both faces? Is Nace confirmed in the system? If both are detected and both match confirmed identities, why is only one a Discovery?

### Bug: Unclear Relationship to Clustering
- If the system clustered these faces, shouldn't they already be grouped?
- The "Unidentified Person 768" label suggests the face IS detected but not clustered with an identity
- How does the clustering pipeline interact with Discoveries? Do discoveries bypass clustering?

### UX Confusion: Three Sections Look Too Similar
- New Matches shows face cards with Similar Identities expandable panel
- Discoveries shows a simpler side-by-side comparison card
- Help Identify shows yet another comparison layout
- All three are essentially "here's an unknown face and its potential matches" — the visual distinction between them is unclear
- User doesn't know where to start or why one face is in Discoveries vs New Matches

---

## 3. WHAT THE SCREENSHOTS REVEAL

### Screenshot 1 (Discoveries page):
- Clean layout but minimal information
- No photo context (collection, source, date)
- No navigation links on either face
- "54% match" badge is the ONLY information about match quality
- "Confirm as Big Leon Capeluto" and "Not a match" are the only actions

### Screenshot 2 (New Matches - Browse):
- POSSIBLE MATCH banner: "Likely Betty Capeluto (45%)"
- Similar Identities panel with distance scores and confidence badges
- Multiple matches shown: Betty (1.09, Moderate), Unidentified 225 (1.13), Unidentified 245 (1.14)
- Compare/Merge/Not Same actions per match
- This is MORE useful than Discoveries — has context, multiple options, actionable

### Screenshot 3 (Help Identify - Focus):
- Side-by-side "WHO IS THIS?" / "BEST MATCH"
- Shows "Weak match" label
- MORE MATCHES section below with thumbnails
- PHOTO CONTEXT section at bottom
- This is ALSO more useful than Discoveries — has context, has alternatives

### Screenshot 4 (Photo view):
- Full photo showing Leon and Nace Capeluto with names printed
- Face detection boxes visible for both (Unidentified Person 768 x2)
- Text below says "LEON CAPELUTO" and "NACE CAPELUTO"
- Photo Detective Evidence would have caught these names — is that data being used?

### Screenshots 5-7 (New Matches - Browse detail):
- Unidentified Person 768 with INBOX badge
- Similar Identities: Big Leon Capeluto (High, Dist: 0.91, +31.7% gap) — strong match
- Victor Capelluto (Low, Dist: 1.20)
- Unidentified Person 767: Nace Capeluto (High, Dist: 1.01, +22.0% gap) — also strong
- Both Leon and Nace ARE in the system — but only Leon surfaced as a Discovery

---

## 4. ROOT CAUSE ANALYSIS

### Why only Leon as a Discovery?
Likely: The Discoveries feature has a threshold or limit. Possible causes:
1. Only surfaces the FIRST high-confidence match per photo (should surface ALL)
2. The 54% threshold cutoff excluded Nace (Nace has distance 1.01 vs Leon's 0.91)
3. A bug in the discovery generation logic that only processes one face per photo
4. Discovery was generated at a different time than the current match data

### Why 54% when the real distance is 0.91?
The 54% is likely a distance-to-percentage conversion: `(1 - distance/2) * 100` or similar. But this creates a confusing UX — users expect percentages to map to "how sure are we" where 90%+ = confident. 54% sounds uncertain. The raw distance of 0.91 with a 31.7% gap is actually a STRONG match. The percentage display is misleading.

### Why can't you click the photos?
Likely: The Discovery card was built as a standalone component without linking to the face card routes. The Confirm/Not a match buttons were implemented but navigation links were not added.

---

## 5. RECOMMENDED FIXES

### Option A: Fix Discoveries as a Distinct Section
- Add navigation links (click face → face card, click photo → photo view)
- Fix percentage display (use confidence labels like "Strong match" instead of misleading percentages)
- Surface ALL high-confidence matches per photo, not just one
- Add photo context (collection, source, date, co-occurring faces)
- Make it clear WHY this is in Discoveries vs New Matches

### Option B: Merge Discoveries into New Matches (RECOMMENDED)
- The current three-section split creates confusion without adding value
- Discoveries is essentially "high-confidence New Matches" — just surface them FIRST in New Matches
- Use the triage bar: "5 Ready to Confirm | 50 Review | 355 Unmatched"
- "Ready to Confirm" items get the one-click merge UX that Discoveries was supposed to provide
- Eliminate the separate Discoveries page entirely
- Keep Help Identify as separate (genuinely different — cold cases for community)

### Decision needed from Nolan:
Option A preserves the three-section architecture but requires significant UX work.
Option B simplifies to two sections (Review + Help Identify) and is closer to the original design intent of a priority-tiered funnel within a single review flow.

---

## 6. GIT WORKTREE HARNESS HARDENING

### Current problem
Claude Code runs Track A on main instead of a worktree (observed in Session 71). This creates merge risk when Track B and C complete.

### Required mechanical enforcement
Add to orchestration logic (NOT as a behavioral rule):
```bash
# At track start, verify we're NOT on main
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "main" ]; then
  echo "ERROR: Track must run in a worktree, not on main"
  echo "Run: git worktree add .claude/worktrees/<track-name> session-71/<track-name>"
  exit 1
fi
```

### Additional harness improvements
1. Pre-track: `git stash` any uncommitted work on main
2. Post-track: `git -C <worktree> status --porcelain` check (from session 70 assessment)
3. Merge gatekeeper: Script that merges tracks in correct order with test runs between each
4. Branch naming convention: `session-NN/track-X-description`

---

## 7. CROSS-REFERENCES
- Session 15: Global reclustering + Needs Help promotion design
- Session 18c: Focus mode, actionability scoring, triage bar
- UX_PRINCIPLES.md: Discovery-first, bidirectional navigation, context > crops
- ALGORITHMIC_DECISIONS.md: Distance thresholds, confidence tiers
- Session 71 (running): Tracks A/B/C handling other dogfooding issues
