# SESSION 71D: DISCOVERIES FEATURE FIX + WORKTREE HARNESS HARDENING

Read CLAUDE.md first. Read ROADMAP.md. Read ALGORITHMIC_DECISIONS.md.
Then read `docs/session_context/session-71d-context.md` for full planning context, design intent research, and dogfooding findings.
Read `docs/design/UX_PRINCIPLES.md` before any UX work.

**IMPORTANT: This session runs IN PARALLEL with Session 71 (Tracks A/B/C). You MUST use git worktrees for ALL work. Do NOT commit to main directly.**

## ROLE
Lead Architect for Rhodesli heritage photo archive. The Discoveries feature is broken and confusing. This session fixes it based on the original design intent (Session 15 reclustering architecture) and current dogfooding findings.

## SESSION GOALS
1. Audit the Discoveries feature: understand what it does, why it's broken, and whether it should exist as a separate section
2. Fix or redesign the review section architecture (Discoveries vs New Matches vs Help Identify)
3. Fix all navigation dead-ends in the Discovery/Review flow
4. Fix the misleading percentage display
5. Ensure ALL high-confidence matches surface (not just one per photo)
6. Harden the git worktree harness with mechanical enforcement

## CONSTRAINTS
- **ALL work in worktrees. NEVER commit to main.** Verify with `git branch --show-current` before every commit. If it says `main`, STOP.
- Every AD entry needs: what was chosen, what was rejected, why, source material
- Deploy via `git push` only (never Railway dashboard)
- Use `/clear` (not `/compact`) between phases
- Test before every commit: `pytest tests/ -x -q`
- Session 71 Tracks A/B/C are running concurrently — do NOT touch files owned by those tracks:
  - Track A owns: templates/ (face card CSS, AI analysis sections), static/css/
  - Track B owns: app/routes/tree.py, app/gedcom.py, templates/person*.html
  - Track C owns: scripts/, .claude/skills/, docs/ (harness docs)
- This session owns: app/routes/discoveries.py (or wherever discoveries lives), the review section routing logic, the match percentage display logic, and the worktree enforcement script

---

## PHASE 0: ORIENT + WORKTREE SETUP (5 min)

### 0A: Set up worktrees
```bash
git checkout main
git pull origin main

# Create worktrees for this session's two tracks
git worktree add .claude/worktrees/discoveries session-71d/discoveries-fix -b session-71d/discoveries-fix
git worktree add .claude/worktrees/harness session-71d/harness-hardening -b session-71d/harness-hardening
```

### 0B: Verify you're NOT on main
```bash
# This should NOT say "main"
git branch --show-current
# Navigate to the discoveries worktree
cd .claude/worktrees/discoveries
git branch --show-current  # Should say "session-71d/discoveries-fix"
```

### 0C: Save prompt and create session log
```bash
cp <this-file> docs/prompts/session-71d-prompt.md

cat > docs/session_logs/SESSION_071D.md << 'EOF'
# Session 71D Log
Started: [timestamp]
Theme: Discoveries Fix + Worktree Harness Hardening
Prompt: docs/prompts/session-71d-prompt.md
Context: docs/session_context/session-71d-context.md
Parallel with: Session 71 (Tracks A/B/C)

## Phase Checklist
- [ ] Phase 0: Orient + worktree setup
- [ ] Phase 1: Discoveries audit (understand current state)
- [ ] Phase 2: Architecture decision (fix vs merge into New Matches)
- [ ] Phase 3: Implementation
- [ ] Phase 4: Worktree harness hardening
- [ ] Phase 5: Verify + prepare for merge

## Verification Gate
- [ ] All review sections make sense to a first-time user
- [ ] Every face/photo in review sections is clickable → navigates somewhere useful
- [ ] High-confidence matches surface ALL matches (not just first)
- [ ] Match display uses meaningful labels (not misleading percentages)
- [ ] Worktree enforcement script works mechanically
- [ ] ALGORITHMIC_DECISIONS.md updated
EOF
```

Commit in worktree: `docs: session 71D phase 0 — orient and setup`

/clear

---

## PHASE 1: DISCOVERIES AUDIT (15 min)

Work in: `.claude/worktrees/discoveries`

Re-read `docs/session_context/session-71d-context.md` Section 1 (Original Design Intent) and Section 2 (Dogfooding Findings).

### 1A: Trace the Discoveries Code Path
Find where Discoveries are generated, stored, and displayed:
```bash
grep -rn "discover" app/ --include="*.py" | head -40
grep -rn "discover" templates/ --include="*.html" | head -20
```

Document:
1. What route serves /discoveries?
2. What query/logic determines which matches appear as "discoveries"?
3. Where does the 54% number come from? Trace the calculation.
4. What threshold determines "high confidence" for a discovery?
5. Why does only ONE match appear when there should be multiple?

### 1B: Trace the Three-Section Routing
Map the routing for all three review sections:
```bash
grep -rn "new_match\|to_review\|discoveries\|help_identify\|needs_help\|skipped" app/ --include="*.py" | head -50
```

Document:
1. How does a face end up in New Matches vs Discoveries vs Help Identify?
2. Is there overlap? Can the same face appear in multiple sections?
3. What's the actual decision tree?

### 1C: Check Clustering State
For the photo with Leon and Nace Capeluto:
```bash
# Find the photo and its detected faces
grep -rn "768\|767\|capeluto\|leon.*capeluto\|nace.*capeluto" app/ data/ --include="*.py" --include="*.json" | head -20
```

Determine:
1. Are both Leon and Nace faces detected in the photo?
2. Are both matched to confirmed identities?
3. Why did only Leon surface as a Discovery?
4. What would it take to surface both?

### 1D: Audit the Percentage Display
Find the code that converts distance (0.91) to percentage (54%):
```bash
grep -rn "percent\|54\|match.*score\|distance.*percent\|confidence.*display" app/ templates/ --include="*.py" --include="*.html" | head -20
```

Document:
1. The exact formula used
2. Why it produces misleading results (54% for what's actually a strong match)
3. What the correct display should be

Write all findings to a temporary audit file: `docs/session_logs/discoveries_audit.md`

Commit: `docs: session 71D phase 1 — discoveries feature audit`

/clear

---

## PHASE 2: ARCHITECTURE DECISION (10 min)

Work in: `.claude/worktrees/discoveries`

Re-read `docs/session_context/session-71d-context.md` Section 5 (Recommended Fixes) and your Phase 1 audit findings from `docs/session_logs/discoveries_audit.md`.

### 2A: Make the Architecture Decision

Based on the audit, decide between:

**Option A: Keep Discoveries as separate section, fix it**
- Pro: Preserves the "proactive notification" concept
- Pro: Clear separation of "system suggests" vs "admin reviews"
- Con: Three sections is confusing for first-time users
- Con: Requires significant UX work to differentiate properly

**Option B: Merge Discoveries into New Matches as a priority tier**
- Pro: Simpler mental model — two sections: "Review" and "Help Identify"
- Pro: Triage bar already supports "Ready to Confirm" as the first tier
- Pro: Consistent UX — all review uses the same components
- Con: Loses the "notification" feel of discoveries

**Option C: Keep Discoveries but redesign as a notification banner, not a page**
- Pro: Still surfaces high-confidence matches proactively
- Pro: Doesn't create a separate confusing page
- Con: Needs design for where the banner appears

Document your decision with full AD entry rationale.

### 2B: Create AD Entry
Create AD-XXX in ALGORITHMIC_DECISIONS.md:
- Title: "Review section architecture — Discoveries vs unified review"
- What was chosen (A, B, or C)
- What was rejected and why
- Impact on user workflow
- Match display strategy (labels vs percentages vs distances)

### 2C: Create AD Entry for Match Display
Create AD-XXX:
- Title: "Match confidence display — user-facing labels vs percentages"
- Document the current percentage formula and why it's misleading
- Decision: Use confidence labels (Strong/Good/Possible/Weak) mapping to distance thresholds
- OR: Use percentages but with a corrected formula that maps to user intuition
- Include the threshold→label mapping table

Commit: `docs: session 71D phase 2 — architecture decision and AD entries`

/clear

---

## PHASE 3: IMPLEMENTATION (30 min)

Work in: `.claude/worktrees/discoveries`

Re-read your architecture decision from Phase 2.

### If Option A (Fix Discoveries):

#### 3A-1: Fix Navigation Dead Ends
Every face photo on the Discoveries page must be clickable:
- Click unidentified face → goes to their face card in New Matches
- Click confirmed face → goes to their face card in People
- Add "View Photo" link → goes to the source photo with face overlays
- Add photo context: collection name, source, date estimate, other faces in photo

#### 3A-2: Fix "Surface All" Logic
- Modify the discovery generation to surface ALL high-confidence matches, not just one
- If a photo has 2 faces that match confirmed identities, show 2 discoveries
- Add proper pagination or "show all" if there are many

#### 3A-3: Fix Match Display
- Replace "54% match" with meaningful label based on distance thresholds
- Use the same vocabulary as New Matches: Strong (< 0.95), Good (0.95-1.05), Possible (1.05-1.15), Weak (> 1.15)
- OR if using percentages, fix the formula so 0.91 distance → ~90% (not 54%)

#### 3A-4: Add Context and Differentiation
- Add a clear explanation at the top: "These are faces the AI is confident about — review and confirm with one click"
- Show WHY this is a discovery (new photo matched confirmed identity, previously skipped face now matches, etc.)
- Make the UX distinct from New Matches — this should feel like a notification, not another inbox

### If Option B (Merge into New Matches):

#### 3B-1: Remove Discoveries as a Separate Page
- Remove /discoveries route
- Remove "Discoveries" from sidebar navigation

#### 3B-2: Add "Ready to Confirm" Tier to New Matches
- In the triage bar, add "Ready to Confirm" as the first section
- "Ready to Confirm" = faces where the top match is a confirmed identity with High confidence
- These get the one-click merge UX: side-by-side faces with "Confirm as [Name]" button
- Show count in sidebar badge alongside New Matches count

#### 3B-3: Update Sidebar
- Remove Discoveries sidebar item
- Update New Matches to show triage breakdown: "5 Ready | 400 Review"
- OR keep it simple: New Matches (405) with the triage bar visible on the page

#### 3B-4: Fix Match Display Throughout
- Apply the confidence label fix across all of New Matches, not just former Discoveries
- The "POSSIBLE MATCH — Likely Betty Capeluto (45%)" banner should use labels too

### If Option C (Notification Banner):

#### 3C-1: Create Discovery Banner Component
- A banner that appears at the top of the New Matches page (and/or Dashboard)
- "🎯 We found a match! Unidentified Person 768 looks like Big Leon Capeluto (Strong match)"
- Click banner → expands to show the comparison with Confirm/Reject
- Or click banner → scrolls to that face in New Matches with it highlighted

#### 3C-2: Remove Discoveries Page
- Same as 3B-1 and 3B-3

### Regardless of Option: Fix the Leon/Nace Problem

#### 3X-1: Ensure All Strong Matches Surface
- Investigate why Nace didn't surface as a discovery
- Fix the logic so ALL faces in a photo with high-confidence matches to confirmed identities are surfaced
- Test with the Leon/Nace photo specifically

#### 3X-2: Fix Clustering Visibility
- If faces are clustered, the cluster should be visible in the UX
- When reviewing a face, show "This face was found in a photo with [other faces]"
- Co-occurrence = signal. Two Capelutos in one photo is strong contextual evidence.

### Write Tests for All Changes
- Test that high-confidence matches surface (ALL of them, not just first)
- Test navigation: every clickable element goes somewhere
- Test match display: distance thresholds map to correct labels
- Test triage bar counts match actual data

Commit: `feat(review): session 71D phase 3 — [describe actual implementation]`

/clear

---

## PHASE 4: WORKTREE HARNESS HARDENING (15 min)

Switch to: `.claude/worktrees/harness`

### 4A: Create Worktree Enforcement Script
Create `scripts/enforce_worktree.sh`:

```bash
#!/bin/bash
# Verifies that the current session is NOT running on main
# Called at the start of each track in a parallelized session

CURRENT_BRANCH=$(git branch --show-current)

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  ERROR: Track is running on main branch!                    ║"
  echo "║  All tracks MUST run in a worktree.                         ║"
  echo "║                                                             ║"
  echo "║  Fix: git worktree add .claude/worktrees/<name> <branch>   ║"
  echo "║  Then: cd .claude/worktrees/<name>                          ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  exit 1
fi

echo "✓ Running on branch: $CURRENT_BRANCH (not main — safe to proceed)"
```

### 4B: Create Merge Gatekeeper Script
Create `scripts/merge_tracks.sh`:

```bash
#!/bin/bash
# Safely merges multiple worktree branches into main
# Usage: ./scripts/merge_tracks.sh track-c track-a track-b
# (order matters — merge docs-first, then independent features, then shared-dependency tracks last)

set -e

echo "=== Merge Gatekeeper ==="
git checkout main
git pull origin main

for TRACK in "$@"; do
  BRANCH="session-*/${TRACK}*"
  ACTUAL_BRANCH=$(git branch --list "$BRANCH" | head -1 | tr -d ' *')

  if [ -z "$ACTUAL_BRANCH" ]; then
    echo "WARNING: No branch matching pattern '$BRANCH' found. Skipping."
    continue
  fi

  echo ""
  echo "--- Merging: $ACTUAL_BRANCH ---"

  # Check for uncommitted work in worktree
  WORKTREE_PATH=$(git worktree list | grep "$ACTUAL_BRANCH" | awk '{print $1}')
  if [ -n "$WORKTREE_PATH" ]; then
    UNCOMMITTED=$(git -C "$WORKTREE_PATH" status --porcelain)
    if [ -n "$UNCOMMITTED" ]; then
      echo "WARNING: Uncommitted files in $WORKTREE_PATH:"
      echo "$UNCOMMITTED"
      echo "Auto-committing..."
      git -C "$WORKTREE_PATH" add -A
      git -C "$WORKTREE_PATH" commit -m "fix: auto-commit uncommitted files (merge gatekeeper)"
    fi
  fi

  # Merge
  git merge "$ACTUAL_BRANCH" --no-ff -m "merge: $ACTUAL_BRANCH into main"

  # Test
  echo "Running tests after merge..."
  pytest tests/ -x -q
  if [ $? -ne 0 ]; then
    echo "TESTS FAILED after merging $ACTUAL_BRANCH. Fix before continuing."
    exit 1
  fi

  echo "✓ $ACTUAL_BRANCH merged and tests pass"
done

echo ""
echo "=== All tracks merged. Run final verification: ==="
echo "  pytest tests/ -x -q"
echo "  git push origin main"
```

### 4C: Create Pre-Track Hook
Add to `.claude/rules/worktree-enforcement.md`:

```markdown
# Worktree Enforcement

Triggers: At the start of any parallelized session track.

## Rule:
Before any code changes in a parallel track, run:
```bash
source scripts/enforce_worktree.sh
```

If this fails, DO NOT PROCEED. Set up the worktree first.

## For merging:
After all tracks complete, use the merge gatekeeper:
```bash
./scripts/merge_tracks.sh <track-names-in-merge-order>
```

This handles: uncommitted file detection, auto-commit, ordered merging, test gates.

## Why this exists:
Session 71 observed Track A running directly on main instead of a worktree.
Behavioral instructions ("use worktrees") are routinely ignored.
Mechanical enforcement (scripts that check and fail) is the only reliable pattern.
See: AD-XXX (subagent commit enforcement)
```

### 4D: Create AD Entry
AD-XXX: "Worktree enforcement — mechanical script replacing behavioral rules"
- What: Scripts that verify branch and enforce merge ceremony
- Rejected: Adding another line to CLAUDE.md or LESSONS_LEARNED (proven to fail)
- Why: 4+ instances of tracks running on main despite instructions

### 4E: Tests
- Test `enforce_worktree.sh` exits non-zero when on main
- Test `merge_tracks.sh` handles missing branches gracefully
- Verify scripts are executable

Commit: `feat(harness): session 71D phase 4 — worktree enforcement scripts`

/clear

---

## PHASE 5: VERIFY + PREPARE FOR MERGE (10 min)

### 5A: Verify Discoveries Fix
In the discoveries worktree, verify:
- [ ] Navigation works: every face/photo is clickable
- [ ] Match display uses meaningful labels (not misleading percentages)
- [ ] Multiple matches surface (Leon AND Nace, not just Leon)
- [ ] First-time user can understand the review workflow
- [ ] Help Identify still makes sense as a separate section
- [ ] All tests pass: `pytest tests/ -x -q`

### 5B: Verify Harness Scripts
In the harness worktree, verify:
- [ ] `enforce_worktree.sh` exits 1 on main, exits 0 on a branch
- [ ] `merge_tracks.sh` runs without errors in dry-run
- [ ] AD entry created
- [ ] Rule file created

### 5C: Update Session Log
Update `docs/session_logs/SESSION_071D.md`:
- Mark all phase checkboxes
- Record all commits
- Record architecture decision made
- Note any items deferred to session 72

### 5D: Push Branches (but do NOT merge yet)
```bash
# Push discoveries branch
cd .claude/worktrees/discoveries
git push origin session-71d/discoveries-fix

# Push harness branch
cd .claude/worktrees/harness
git push origin session-71d/harness-hardening
```

**Do NOT merge to main.** Session 71 Tracks A/B/C are still running. All merges happen in a single merge ceremony after ALL tracks from ALL parallel sessions are complete.

Merge order when ready:
1. Session 71 Track C (harness docs) + Session 71D harness-hardening
2. Session 71 Track A (UX fixes)
3. Session 71D discoveries-fix
4. Session 71 Track B (GEDCOM integration) — last, most likely to conflict

### 5E: Clean Up (after merge is complete)
```bash
git worktree remove .claude/worktrees/discoveries
git worktree remove .claude/worktrees/harness
git branch -d session-71d/discoveries-fix session-71d/harness-hardening
```

---

## CRITICAL REMINDERS
- **ALL work in worktrees. Check `git branch --show-current` before EVERY commit.**
- Use `/clear` between phases. Not `/compact`.
- Every AD entry needs: what was chosen, what was rejected, why, source material.
- Test before every commit: `pytest tests/ -x -q`
- Do NOT merge to main — Session 71 is running in parallel.
- The Discoveries fix is about USER COMPREHENSION, not just code fixes. A first-time user must understand the workflow.
- The 54% number is actively misleading. Whatever you ship must make match confidence intuitive.
- Both Leon AND Nace must surface. If only one does, the logic is wrong.

## ITEMS CHECKLIST
- [x] Discoveries audit (code path, routing, percentage formula) → Phase 1
- [x] Architecture decision (fix vs merge vs banner) → Phase 2
- [x] Navigation dead ends → Phase 3
- [x] Misleading percentage display → Phase 3
- [x] Only Leon, not Nace → Phase 3 (3X-1)
- [x] Clustering visibility → Phase 3 (3X-2)
- [x] Three confusing sections → Phase 2 decision
- [x] Worktree enforcement script → Phase 4A
- [x] Merge gatekeeper script → Phase 4B
- [x] Pre-track hook/rule → Phase 4C
- [x] AD entries for decisions → Phases 2B, 2C, 4D
