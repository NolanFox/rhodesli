# Session 76a Planning Context

## Session Identity
- **Session:** 76a
- **Previous:** 75 (Gemini eval, data integrity, tree upgrade, date parsing)
- **Previous:** 74 (Gemini/Antigravity UX overhaul — partially broken, data regressions)
- **Goal:** Fix auto-clustering pipeline + Discoveries UX redesign + Browse card face sizing
- **Version:** v0.77.1 (as shown in screenshots)

---

## 1. CORE PROBLEM STATEMENT

Faces are NEVER auto-clustered at upload time. Despite 75+ sessions of work,
every new face lands as an isolated "Unidentified Person N" card regardless
of how obvious the match is. The Gatekeeper pattern was designed but never
wired end-to-end into the upload pipeline.

**Evidence from production (Feb 28, 2026):**
- 405 New Matches, 202 Help Identify, 59 People, 272 Photos
- Unidentified Person 768 = clearly Big Leon Capeluto (Good match on Discoveries)
- Unidentified Person 767 = clearly Nace Capeluto (Possible match on Discoveries)
- Neither was auto-clustered. Both sit as isolated 1-face inbox entries.
- The Similar Identities panel shows matches with +31.7% gap (High) but
  these are suggestions, not actions.

**Root cause chain:**
1. `process_uploads.py` runs InsightFace → embeddings → stores face
2. `cluster_new_faces.py` groups inbox faces with threshold 0.95
3. But Step 2 only groups inbox-to-inbox, NOT inbox-to-confirmed
4. Proposals are generated but never auto-applied
5. No mechanism exists to auto-add high-confidence faces to existing clusters
6. The "Discoveries" page shows matches but requires manual confirm/reject
   with NO pre-clustering

---

## 2. DESIRED ARCHITECTURE: TWO-TIER DISCOVERY

### Tier 1 — Auto-clustered (High confidence, e.g. distance < 0.85)
At upload time, if a new face is close enough to a confirmed identity:
- System ADDS the face to the cluster automatically
- Discoveries surfaces: "We added this face to Big Leon — confirm or undo?"
- Face is already IN the cluster; user ratifies or corrects
- Correction = strong negative signal for ML (false positive caught by human)
- Confirmation = positive signal (reinforces cluster)

### Tier 2 — Strong suggestion (Medium confidence, e.g. 0.85-1.05)
For faces near the threshold boundary:
- System does NOT auto-cluster
- Discoveries surfaces: "This looks like Nace Capeluto — add them?"
- One-click merge or reject
- Both outcomes are training signals

### What this means for other sections:
- **New Matches (Inbox):** Faces with NO strong match to anyone confirmed.
  Genuinely need human identification work.
- **Help Identify:** Long tail of skipped/difficult faces.
- **Discoveries:** ML's actionable output. System did the work,
  human is the quality gate.

---

## 3. UX ISSUES FROM SCREENSHOTS (Feb 28, 2026)

### Browse View Cards (New Matches)
- Face crops are ~80-100px, buried under chrome
- Each card has: INBOX badge, Sort dropdown, View All Photos, Find Similar,
  quality label, View Photo, Share, Edit Details, Confirm, Skip, Reject
- Face occupies ~15% of card real estate — should be ~60-70%
- Session 18 flagged this. Session 74 made it WORSE.
- Cards should be face-dominant: 200-250px face, actions on hover/compact row

### Discoveries Page
- Shows side-by-side face circles with match badge (Good/Possible)
- "Also in photo" context is useful
- "Confirm as X" / "Not a match" buttons are correct
- BUT: faces should already be in clusters for Tier 1
- Missing: undo capability, ML signal logging, batch actions

### Similar Identities Panel
- Appears when you click "Find Similar" on a card
- Shows candidates with distance, confidence tier, gap%
- Face crops are tiny (~48px) — should be 64-80px minimum
- Technical metrics (dist, gap%) should be hidden by default
- Action buttons (Merge Selected / Not Same Selected) are good

---

## 4. ML IMPLICATIONS OF DISCOVERY FEEDBACK

Every user action in Discoveries generates training data:

| Action | Signal Type | ML Use |
|--------|-------------|--------|
| Confirm auto-cluster (Tier 1) | True positive | Reinforces threshold |
| Undo auto-cluster (Tier 1) | False positive | Critical — lowers threshold |
| Accept suggestion (Tier 2) | Positive pair | Anchor-positive for contrastive loss |
| Reject suggestion (Tier 2) | Hard negative | Anchor-negative (highest value) |
| "Not a match" on Discoveries | Hard negative | Model thought match, human disagreed |

This data feeds:
1. Threshold recalibration (running mean of TP/FP at each distance)
2. Active learning (faces with most uncertain matches → surface first)
3. Future LoRA fine-tuning (confirmed pairs + rejected pairs)

**IMPORTANT:** Log every Discovery action with timestamp, face IDs,
distance, confidence tier, and user decision. This is the golden
training dataset.

---

## 5. REVIEW SECTION WORKFLOW MAP

### New Matches (Inbox) — "Who is this?"
- Faces with NO confident match to confirmed identities
- Workflow: Browse cards → see face prominently → Find Similar →
  compare side-by-side → identify or skip
- Key UX: face-dominant cards, smart ordering by actionability

### Discoveries — "The AI found something"
- High-confidence matches to confirmed identities
- Workflow: See what AI did → confirm/undo (Tier 1) or accept/reject (Tier 2)
- Key UX: side-by-side with clear actions, undo capability, batch mode

### Help Identify — "These need human expertise"
- Skipped faces, low-confidence matches, genuinely unknown
- Workflow: Focus mode side-by-side → compare to suggestions →
  identify, merge with another unknown, or skip
- Key UX: large side-by-side, keyboard shortcuts, session tracking

---

## 6. EXISTING THRESHOLDS & DATA

From Session 14 clustering work:
- Same-person mean distance: 1.01 (std 0.19)
- Same-family mean distance: 1.34 (std 0.07)
- Different-person mean distance: 1.37 (std 0.06)
- Current grouping threshold: 0.95 (inbox-to-inbox only)
- Strong match threshold: < 1.16
- Possible match threshold: < 1.31

Proposed auto-cluster threshold (Tier 1): distance < 0.85
This is well within the same-person distribution and should have
very low false positive rate. Claude Code should VERIFY this by
checking the actual distance distribution of confirmed clusters.

Proposed suggestion threshold (Tier 2): 0.85 - 1.10
This covers the overlap zone where matches are likely but not certain.

---

## 7. TESTING STRATEGY

Testing has been a major time sink. Strategy for this session:

1. **Write tests LAST** — after all code works in production
2. **Use a test subagent** in a separate worktree that writes tests
   while the main agent moves on to next phase
3. **Focus on integration tests** — test the pipeline end-to-end,
   not unit tests for every helper function
4. **Key tests needed:**
   - Auto-clustering adds face to cluster when distance < threshold
   - Auto-clustering does NOT add face when distance > threshold
   - Discovery page shows Tier 1 (auto-clustered) items
   - Discovery page shows Tier 2 (suggestion) items
   - Undo action removes face from cluster
   - Accept action merges face into cluster
   - ML signal logged on every Discovery action

---

## 8. HARNESS REMINDERS

- Update ALGORITHMIC_DECISIONS.md with all threshold decisions
- Update ROADMAP.md and BACKLOG.md at session end
- Session log goes to docs/session_logs/session_76a_log.md
- PRD goes to docs/prds/ (number TBD based on existing)
- SDD goes to docs/sdds/ (if directory exists) or docs/design/
- No file > 300 lines. ROADMAP.md < 150 lines. CLAUDE.md < 80 lines.
- Deploy via git push (not Railway dashboard)
- Verify in browser after deploy (Claude Chrome or Playwright)
- Commit after every phase with descriptive messages

---

## 9. WORKTREE PLAN

| Worktree | Track | Files Touched | Dependencies |
|----------|-------|---------------|-------------|
| `main` | Orchestrator | docs/, ROADMAP, BACKLOG | None |
| `pipeline-fix` | Track A: Auto-clustering pipeline | process_uploads.py, cluster_new_faces.py, identities.json logic | None |
| `discoveries-ux` | Track B: Discoveries page redesign | app/main.py (Discoveries routes), templates | After Track A merges |
| `browse-cards` | Track C: Face card sizing | app/main.py (browse view), CSS | Independent |
| `test-suite` | Track D: Tests | tests/ only | After A, B, C merge |

Tracks A and C can run in parallel.
Track B depends on A (needs auto-clustering to exist).
Track D runs after all others merge.
