# Session 79: Fix Three Visible Failures + Session 78 Cleanup

Read CLAUDE.md. Read .claude/rules/*.md (all rules).
Read /mnt/skills/public/frontend-design/SKILL.md (design quality guide).
Read docs/ml/ALGORITHMIC_DECISIONS.md (last 20 lines).
Read docs/assessments/session-78-assessment.md.
Read docs/session_context/session-79-context.md (screenshot evidence + technical context).
Read ROADMAP.md. Read BACKLOG.md.

## SESSION IDENTITY

**This session fixes exactly three user-visible failures, plus unfinished
work from Session 78. Nothing else. No new features.**

**Nolan's exact words about the current state:**
- "the UI is genuinely bad"
- "genuinely poor design"
- "[the identity deletion] is a huge fail since we have spent multiple
  sessions trying to get it to work"
- "We have made way too little progress and done too much spinning our
  wheels. Let's prove we can solve 3 problems."

**WARNING: Session 78 self-assessment claimed "0 red flags" when my
independent review found 6+ red flags.** Self-assessments in Track 5
must be brutally honest. If something didn't work, say so.

Session 78 claimed "all 9 pages render correctly." The user then opened
the app and found:

1. **/tree is completely blank** — white rectangle, no people, no nodes.
   Session 78 synced 1,019 GEDCOM relationships to Supabase but the tree
   still shows nothing. The sync didn't work end-to-end.

2. **Face cards are badly designed** — each card is ~70% buttons/metadata
   and ~30% actual face. "View All Photos," "Find Similar," Sort dropdown,
   INBOX badge, quality label, Edit Details, Confirm/Skip/Reject all
   compete for attention. The face — the ONE thing the user needs to see —
   is a small thumbnail buried in the middle.

3. **Big Leon / Nace identity lost** — The St. Petersburg Times 1959 photo
   (faces 768/767) now shows "Unidentified" where there should be a named
   identity. An identity linked to this photo was deleted or corrupted
   across sessions 76a-78. This is a DATA LOSS incident.

Plus these unfinished items from my Session 78 evaluation:
4. Per-face dedup was IMPLEMENTED but never RUN — 57 duplicates still exist
5. Tier 2 threshold raise to 1.30 — analysis proved 1.10 too low, but
   change was not applied. Apply it now. Nolan approves.
6. Backfill was not re-run after threshold analysis
7. Compare upload E2E was deferred (again)
8. Mobile viewport never tested
9. 5 skipped tests undocumented

## CRITICAL RULES — READ THESE FIRST

**A. DO NOT STOP UNTIL THESE ARE FIXED.** Not "implemented." Not "code
written." FIXED — verified working in production with Claude Chrome
screenshots as evidence. If the first approach doesn't work, try another.
If that doesn't work, try another. Debug until it works.

**B. CLAUDE CHROME IS MANDATORY FOR VERIFICATION.** Every fix must be
verified by navigating to the production URL with Claude Chrome and
taking a screenshot. If Claude Chrome isn't working, spend up to 10
minutes getting it working. If it truly can't work, use Playwright
as a fallback — but try Claude Chrome first and hard.

**C. TESTS RUN AT THE END, NOT DURING.** Do not let test failures slow
down fixing the three visible problems. Fix the user-facing issues first.
Run the full test suite once at the end. Fix any test failures then.

**D. GIT WORKTREES + SUBAGENTS for parallelization.** Tracks that touch
different files run in parallel. /clear between tracks.

**E. SAVE BOTH FILES** at session start:
- This prompt → docs/prompts/session-79-prompt.md
- Context file → docs/session_context/session-79-context.md

**F. USE /clear BETWEEN TRACKS. NEVER USE /compact.** Re-read from disk.

**G. ALL HARNESS RULES APPLY:**
- Update ALGORITHMIC_DECISIONS.md for every non-trivial decision
- Commit after every logical unit of work
- No docs file > 300 lines. ROADMAP < 150 lines.
- Deploy via git push. Verify with Claude Chrome.
- Update CHANGELOG.md and SESSION_HISTORY.md
- Bump version (currently v0.80.0)
- Create session log: docs/session_logs/session-79-log.md

---

## TRACK 1: FIX THE TREE (CRITICAL — ~40 min)

### Acceptance Criteria (write to /tmp/track_1_acceptance.md first)
- PASS: /tree shows 100+ people with family connections in production
- PASS: "Focus on" dropdown lists real family names
- PASS: Clicking a person shows their family connections
- FAIL: Blank white rectangle (current state)
- FAIL: Tree renders locally but not in production

### 1A: Diagnose WHY the tree is blank

The tree uses the `family-chart` library with CardHtml format (Session 75).
Something in the pipeline from Supabase → build_family_tree() → 
family-chart JS is broken.

Debug this step by step:

```bash
# 1. Does Supabase actually HAVE the relationships now?
python3 -c "
from supabase import create_client
import os
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
# Check relationships
rels = sb.table('relationships').select('*', count='exact').execute()
print(f'Supabase relationships: {rels.count}')
# Check if pagination is working
if rels.count and rels.count > 0:
    print(f'First rel: {rels.data[0]}')
"

# 2. Does build_family_tree() return data?
python3 -c "
from core.family_tree import build_family_tree
tree_data = build_family_tree()
print(f'Tree nodes: {len(tree_data) if tree_data else 0}')
if tree_data:
    print(f'First 3 nodes: {tree_data[:3]}')
"

# 3. Does the /tree route return the data to the frontend?
curl -s https://rhodesli.nolanandrewfox.com/api/tree 2>&1 | head -50
# or whatever the tree data endpoint is

# 4. Check the family-chart JS initialization
grep -n "family-chart\|FamilyTree\|CardHtml\|f3" app/main.py | head -20
cat static/js/family-tree.js | head -50
```

The blank white rectangle means one of these is failing:
- Supabase has no data (sync didn't persist)
- build_family_tree() returns empty array
- The API endpoint returns empty JSON
- The JS library fails to initialize (check browser console errors)
- The JS library initializes but gets empty data

**Find which step breaks and fix it. Then fix the next break. Keep going
until the tree renders with actual people.**

### 1B: Verify the Supabase pagination fix

Session 78 fixed a pagination bug (only fetching first 1000 rows). 
Verify this fix is actually deployed:
```bash
grep -n "paginate\|range\|offset\|limit\|1000" app/supabase_data.py
```

If the pagination fix only exists in the sync script but NOT in the
startup data loader, that's the bug — data gets synced TO Supabase
but never loaded FROM Supabase correctly.

### 1C: Fix and verify

Fix whatever is broken. Deploy. Open /tree with Claude Chrome.
Screenshot must show family tree nodes with names and connections.

If the family-chart library itself is the problem (JS errors, bad data
format), consider whether a simpler visualization (even just a nested
HTML list of families) would be better than a blank page.

Commit: `fix(tree): [description of what was actually broken]`

---

## TRACK 2: REDESIGN FACE CARDS (CRITICAL — ~30 min)

### Acceptance Criteria (write to /tmp/track_2_acceptance.md first)
- PASS: Face image is 60%+ of card area (currently ~30%)
- PASS: Primary action (Confirm/Reject) is immediately obvious
- PASS: Secondary actions are accessible but not competing visually
- PASS: Card is scannable — user can review 20 faces quickly
- FAIL: Buttons/metadata dominate the card over the face
- FAIL: Card requires scrolling to see the face AND take action

### Current Card Anatomy (BROKEN — too much chrome)

From the screenshots, each card currently shows:
```
┌─────────────────────────────┐
│ Unidentified Person 762  Edit│  ← Title + Edit link
│ [INBOX] 1 face · Good        │  ← Badge + metadata
│ [Sort by Date        ▼]      │  ← Dropdown (WHY?)
│ [🖼 View All Photos]          │  ← Button
│ [🔍 Find Similar]             │  ← Button
│                               │
│   ┌───────────┐              │
│   │           │              │  ← FACE (~100x130px)
│   │   face    │              │
│   │           │              │
│   └───────────┘              │
│ Good quality                  │  ← Quality label
│ Edit Details                  │  ← Link
│ [✔ Confirm] [⏸ Skip]         │  ← Primary actions
│ [✖ Reject]                    │  ← Destructive action
└─────────────────────────────┘
```

### Target Card Design

The face should dominate. Everything else is secondary.

```
┌─────────────────────────────┐
│ ┌─────────────────────────┐ │
│ │                         │ │
│ │                         │ │
│ │      FACE (large)       │ │  ← 60%+ of card
│ │      200px+ tall        │ │
│ │                         │ │
│ │                         │ │
│ └─────────────────────────┘ │
│ Person 762 · 1 match    [⋯] │  ← Name + overflow menu
│ [✔ Confirm]  [✖]  [⏭]      │  ← Compact action row
└─────────────────────────────┘
```

Design principles:
- **Face image: object-cover, min-height 200px, full card width**
- **Name: one line, truncated if long, with match count inline**
- **Actions: icon buttons with tooltips, not text buttons**
  - ✔ (green) = Confirm — tooltip "Confirm identity"
  - ✖ (red) = Reject — tooltip "Wrong person"  
  - ⏭ (gray) = Skip — tooltip "Review later"
- **Overflow menu (⋯):** View Photos, Find Similar, Edit Details,
  Sort by Date — these are secondary actions, hidden behind a menu
- **Remove from default view:** INBOX badge (they're ALL inbox on this
  page), quality label (not actionable), Sort dropdown (per-card sort
  makes no sense)
- **Keep visible only on hover/focus:** Edit link

Read `.claude/rules/ux-evaluation.md` and the frontend-design skill
at `/mnt/skills/public/frontend-design/SKILL.md` before implementing.

### Implementation

Find the face_card() function (likely in app/main.py or a component file).
Rewrite the HTML/CSS. This is FastHTML + HTMX + Tailwind, not React.

Test at three viewport widths:
- Desktop (1200px): 4 cards per row
- Tablet (768px): 3 cards per row
- Mobile (375px): 2 cards per row

### Verify with Claude Chrome

Navigate to /?section=to_review&view=browse
Screenshot at desktop width. The faces should dominate the cards.
Screenshot at mobile width. Cards should still be usable.

Commit: `fix(ux): redesign face cards — face-dominant layout`

---

## TRACK 3: INVESTIGATE + FIX BIG LEON / NACE DATA LOSS (CRITICAL — ~30 min)

### Acceptance Criteria (write to /tmp/track_3_acceptance.md first)
- PASS: The St. Petersburg Times 1959 photo has NAMED identities on
  both faces (not "Unidentified")
- PASS: Big Leon and Nace appear in /discoveries as suggested matches
  (Tier 2) or are auto-added to their clusters (Tier 1 if threshold raised)
- PASS: No identity data was lost — all previously confirmed identities
  still exist
- FAIL: Either face shows "Unidentified" in the photo view
- FAIL: identities.json has fewer CONFIRMED entries than before Session 76a

### 3A: Diagnose the data loss

```bash
# How many confirmed identities exist now?
python3 -c "
import json
idents = json.load(open('data/identities.json'))
confirmed = [i for i in idents if i.get('state') == 'CONFIRMED']
print(f'Total identities: {len(idents)}')
print(f'Confirmed: {len(confirmed)}')
# List confirmed names
for c in sorted(confirmed, key=lambda x: x.get('name', '')):
    print(f'  {c.get(\"name\", \"??\")} — {len(c.get(\"faces\", []))} faces')
"

# Check git blame — when did the identity for 768/767's photo change?
git log --oneline --all -- data/identities.json | head -20

# Find the specific photo with these faces
python3 -c "
import json
annots = json.load(open('data/annotations.json'))
# Find annotations for the St Petersburg Times photo
for photo_id, faces in annots.items():
    for face in faces:
        if face.get('face_id') in ['768', '767', 768, 767]:
            print(f'Photo: {photo_id}')
            print(f'Face: {json.dumps(face, indent=2)}')
"

# What identity are faces 768/767 currently assigned to?
python3 -c "
import json
idents = json.load(open('data/identities.json'))
for i in idents:
    faces = i.get('faces', [])
    face_ids = [str(f.get('face_id', f)) if isinstance(f, dict) else str(f) for f in faces]
    if '768' in face_ids or '767' in face_ids:
        print(f'Identity: {i.get(\"name\", \"??\")} (state: {i.get(\"state\")})')
        print(f'  Faces: {face_ids}')
"
```

### 3B: Identify what session caused the data loss

```bash
# Check each session's commits for identity changes
git log --oneline --diff-filter=M -- data/identities.json | head -10
# For the suspicious commit:
git show <commit>:data/identities.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
confirmed = [i for i in data if i.get('state') == 'CONFIRMED']
print(f'Confirmed at this commit: {len(confirmed)}')
"
```

Was it Session 76a's dedup? Session 78's per-face dedup? The merge?
Find the exact commit that removed or altered the identity.

### 3C: Restore the identity

If the identity was deleted:
- Find it in git history
- Restore it to data/identities.json
- Verify it appears in the photo view

If the identity exists but faces 768/767 were unlinked:
- Re-link them to the correct identity
- Verify the annotation shows the name

### 3D: Apply threshold raise + run backfill

**Nolan has approved raising Tier 2 ceiling from 1.10 to 1.30.**

```bash
# Find the threshold constant
grep -rn "1\.10\|TIER_2\|tier_2" core/auto_cluster.py

# Change it to 1.30
# Update AD-179 with the change and Nolan's approval
```

Then run the dedup + backfill:
```bash
python scripts/backfill_auto_cluster.py --dry-run
# Review output, then:
python scripts/backfill_auto_cluster.py
```

Expected results after threshold raise:
- Big Leon (768) at distance 1.13 should now be Tier 2 (suggest)
- Nace (767) at distance 1.18 should now be Tier 2 (suggest)
- Both should appear in /discoveries

### 3E: Run the per-face dedup

Session 78 implemented this but never ran it.
```bash
python scripts/backfill_auto_cluster.py --dedup-only
# or whatever the dedup invocation is
```

Report: how many of the 57 duplicates were resolved?

### 3F: Verify with Claude Chrome

1. Navigate to the St. Petersburg Times 1959 photo — both faces
   should show names, not "Unidentified"
2. Navigate to /discoveries — Big Leon and Nace should appear as
   Tier 2 suggestions
3. Discoveries count in sidebar should be > 0 (currently shows 0)

Commit: `fix(data): restore Big Leon/Nace identity + threshold 1.30 + backfill`

---

## TRACK 4: SESSION 78 CLEANUP (worktree: cleanup-78, ~20 min)

### Acceptance Criteria (write to /tmp/track_4_acceptance.md first)
- PASS: Compare upload attempted end-to-end, outcome documented with evidence
- PASS: 5 skipped tests identified, documented, and justified
- PASS: Mobile viewport screenshots captured for 3+ pages
- FAIL: Compare deferred again without concrete blocker documentation
- FAIL: Skipped tests undocumented

These are items from my Session 78 evaluation that were left unfinished.

### 4A: Compare upload E2E

This has been deferred for 5+ sessions. Today it gets attempted.

Using Claude Chrome or Playwright:
1. Navigate to /compare
2. Upload a test photo
3. Watch what happens
4. If it errors: read the error, fix the code, redeploy, retry
5. If it works: screenshot as evidence

If ML models aren't on Railway and uploads genuinely can't process,
document EXACTLY what's missing and what it would take to fix — not
"deferred" but "blocked on X, estimated Y effort to unblock."

### 4B: Document the 5 skipped tests

```bash
python -m pytest tests/ -v 2>&1 | grep -i "skip\|SKIP"
python -m pytest rhodesli_ml/tests/ -v 2>&1 | grep -i "skip\|SKIP"
```

For each skipped test: what is it, why is it skipped, should it be
enabled? Document in the session assessment.

### 4C: Mobile viewport check

Using Claude Chrome or Playwright, check these pages at 375px width:
- /photos
- /?section=to_review&view=browse (the new face cards)
- /tree (after it's fixed)

Screenshot each. Note any issues.

Commit: `fix: session 78 cleanup — compare test, skip docs, mobile check`

---

## TRACK 5: DEPLOY + DOUBLE-CHECK + ASSESSMENT (on main, LAST)

### 5A: Merge all tracks, deploy

```bash
git checkout main
# Merge each track, running a quick sanity check between each
git merge <track-1-branch> --no-ff -m "merge: Track 1 tree fix"
git merge <track-2-branch> --no-ff -m "merge: Track 2 face card redesign"  
git merge <track-3-branch> --no-ff -m "merge: Track 3 Big Leon + threshold"
git merge <track-4-branch> --no-ff -m "merge: Track 4 session 78 cleanup"
git push origin main
```

### 5B: Run full test suite

```bash
python -m pytest tests/ -x -q --timeout=60 2>&1 | tail -10
python -m pytest rhodesli_ml/tests/ -v 2>&1 | tail -20
```

Fix any failures. This is the ONLY time tests run in this session.
If a test fails because of the face card redesign (checking old HTML
structure), update the test to match the new design.

### 5C: DOUBLE-CHECK — Claude Chrome verification of ALL THREE fixes

This is the verification that Session 78 should have done. Open each
URL with Claude Chrome and take a screenshot.

**Check 1: Tree**
- URL: https://rhodesli.nolanandrewfox.com/tree
- Expected: Family tree with 100+ people, connections visible
- If still blank: DO NOT PROCEED. Go back to Track 1. Debug more.

**Check 2: Face Cards**
- URL: https://rhodesli.nolanandrewfox.com/?section=to_review&view=browse
- Expected: Face-dominant cards. Face = 60%+ of card area.
- If still button-heavy: DO NOT PROCEED. Go back to Track 2.

**Check 3: Big Leon / Nace**
- Navigate to the St. Petersburg Times 1959 photo
- Expected: Both faces show names, not "Unidentified"
- Navigate to /discoveries
- Expected: Tier 2 suggestions visible (count > 0 in sidebar)
- If "Unidentified" still shows: DO NOT PROCEED. Go back to Track 3.

**Check 4: Compare upload (best effort)**
- URL: https://rhodesli.nolanandrewfox.com/compare
- Upload a photo, document what happens

**Check 5: Mobile**
- Resize to 375px width, screenshot /photos and face cards

### 5D: If ANY check fails

Go back to the relevant track. Debug. Fix. Redeploy. Re-check.
Loop until the check passes. This is not optional.

### 5E: Write assessment

Create `docs/assessments/session-79-assessment.md`:
- Screenshot evidence for each of the three fixes
- What was broken and what the root cause was
- What the fix was
- Remaining issues (honest, not "everything looks great")
- Session 78 cleanup items: completed or truly blocked
- **HONESTY CHECK:** Session 78's self-assessment claimed "0 red flags
  requiring immediate fix" when 6+ existed. For each acceptance criterion
  in each track, state PASS or FAIL with evidence. Do not rationalize
  failures as "deferred." If something didn't work, say FAIL.

Create `docs/session_context/session_79_ux_evaluation.md`:
- Face card before/after comparison
- Mobile viewport findings
- Any other UX issues noticed during Chrome verification

### 5F: Prepare for Session 80 Interactive

Session 80 will be an interactive walkthrough with Nolan where Claude
Code uses Claude Chrome to navigate every page of the app together.

To prepare:
- Verify Claude Chrome is working (can navigate, screenshot, click)
- Create `docs/session_context/session_80_interactive_plan.md`:
  - List every page/route in the app
  - For each: what it should do, known issues, what to test
  - Order: start with the strongest pages, save weakest for last
  - Note which pages need auth vs. work for anonymous users

Commit: `docs: session 79 assessment + session 80 interactive plan`

---

## RULES REMINDER

1. **THREE FIXES MUST SHIP.** Tree, face cards, Big Leon. Non-negotiable.
2. **Claude Chrome verification or it didn't happen.**
3. **Tests run at the END, not during.** Fix user-facing issues first.
4. **If a fix doesn't work, keep debugging.** Don't defer. Don't skip.
5. **Update ALGORITHMIC_DECISIONS.md** — especially for the threshold
   raise (AD-179 update with Nolan's approval).
6. **Commit after every logical fix.** Small, atomic.
7. **/clear between tracks. NEVER /compact.** Re-read from disk.
8. **No new features.** Fix only.
9. **Save prompt AND context file** to docs/prompts/ and docs/session_context/.
10. **Stop hook must pass** — assessment file must exist before session ends.
11. **Session log** — create docs/session_logs/session-79-log.md.
12. **CHANGELOG + SESSION_HISTORY** — update both. Bump version.
13. **Self-assessment must be honest.** Session 78 claimed "0 red flags"
    when 6+ existed. If Track 5 finds issues, report them. Don't minimize.
