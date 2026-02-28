# Session 76a: Auto-Clustering Pipeline + Discoveries UX + Face Card Redesign

Read CLAUDE.md. Read .claude/rules/spec-driven-development.md.
Read .claude/rules/verification-gate.md.
Read .claude/rules/feature-reality-contract.md.
Read .claude/rules/harness-decisions.md.
Read .claude/rules/phase-execution.md.
Read .claude/rules/prompt-decomposition.md.
Read CHANGELOG.md (first 15 lines for current version).
Read docs/ALGORITHMIC_DECISIONS.md (last 30 lines for recent ADs).
Read BACKLOG.md.
Read ROADMAP.md.
Read docs/session_context/session-76a-context.md.

## Session Identity
- **Session:** 76a
- **Goal:** Make the clustering pipeline actually work end-to-end,
  redesign Discoveries as the ML audit trail, fix face card sizing
- **Tracks:** 4 parallel tracks via worktrees
- **Time budget:** ~60 min
- **Priority:** CRITICAL — core product loop is broken

## ⚠️ CONTEXT MANAGEMENT — MANDATORY

1. Save this prompt to `docs/prompts/session-76a-prompt.md`
2. Parse into phases with a checklist in `docs/session_logs/session_76a_log.md`
3. Execute ONE phase at a time
4. Commit after each phase
5. `/clear` between EVERY track (not /compact — /compact is lossy)
6. Re-read `docs/prompts/session-76a-prompt.md` after each /clear
7. Re-read `docs/session_context/session-76a-context.md` after each /clear
8. At session end, re-read original prompt and verify EVERY phase

## ⚠️ DO NOT STOP UNTIL COMPLETE

If a phase fails, debug and fix it. Do not skip phases.
Do not declare success until the verification gate passes.
If context exceeds 60%, /clear and re-read from disk.
If a worktree merge conflicts, resolve manually — do not abandon the track.

---

## PHASE 0: Orient + Worktree Setup (~5 min)

### 0A: Verify Session 75 landed cleanly
```bash
# Check current version
head -5 CHANGELOG.md

# Check production is up
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/

# Check data integrity
python scripts/check_data_integrity.py 2>&1 | tail -5

# Check test suite
pytest tests/ -x -q --tb=no 2>&1 | tail -3
```

If any of these fail, FIX before proceeding. Session 75 must be clean.

### 0B: Investigate the specific examples from user feedback

```bash
# Find Unidentified Person 768 and 767 in identities.json
python3 -c "
import json
with open('data/identities.json') as f:
    data = json.load(f)

# Find 768 and 767
for identity in data.get('identities', data if isinstance(data, list) else []):
    name = identity.get('name', '')
    if '768' in name or '767' in name:
        print(f'=== {name} ===')
        print(f'  faces: {len(identity.get(\"faces\", []))}')
        print(f'  status: {identity.get(\"status\", \"unknown\")}')
        face_ids = [f.get('face_id', 'no-id') for f in identity.get('faces', [])]
        print(f'  face_ids: {face_ids}')
        print()

# Find Big Leon and Nace
for identity in data.get('identities', data if isinstance(data, list) else []):
    name = identity.get('name', '')
    if 'Big Leon' in name or 'Nace' in name:
        print(f'=== {name} ===')
        print(f'  faces: {len(identity.get(\"faces\", []))}')
        print(f'  status: {identity.get(\"status\", \"unknown\")}')
        print()
"
```

```bash
# Check embedding distances between 768 and Big Leon, 767 and Nace
python3 -c "
import numpy as np
import json

# Load embeddings
embs = np.load('data/embeddings.npy', allow_pickle=True)
if embs.ndim == 0:
    embs = embs.item()

with open('data/identities.json') as f:
    data = json.load(f)

identities = data.get('identities', data if isinstance(data, list) else [])

def get_face_ids(name_fragment):
    for identity in identities:
        if name_fragment in identity.get('name', ''):
            return [f.get('face_id') for f in identity.get('faces', [])]
    return []

def get_embedding(face_id):
    if isinstance(embs, dict):
        return embs.get(face_id)
    return None

from scipy.spatial.distance import cosine

# 768 vs Big Leon
ids_768 = get_face_ids('768')
ids_leon = get_face_ids('Big Leon')
print(f'Person 768 face_ids: {ids_768}')
print(f'Big Leon face_ids: {ids_leon}')

for fid_768 in ids_768:
    e768 = get_embedding(fid_768)
    if e768 is None:
        print(f'  No embedding for {fid_768}')
        continue
    for fid_leon in ids_leon:
        eleon = get_embedding(fid_leon)
        if eleon is None:
            print(f'  No embedding for {fid_leon}')
            continue
        dist = cosine(e768, eleon)
        print(f'  768 ({fid_768[:12]}) <-> Leon ({fid_leon[:12]}): dist={dist:.4f}')

print()

# 767 vs Nace
ids_767 = get_face_ids('767')
ids_nace = get_face_ids('Nace')
print(f'Person 767 face_ids: {ids_767}')
print(f'Nace face_ids: {ids_nace}')

for fid_767 in ids_767:
    e767 = get_embedding(fid_767)
    if e767 is None:
        print(f'  No embedding for {fid_767}')
        continue
    for fid_nace in ids_nace:
        enace = get_embedding(fid_nace)
        if enace is None:
            print(f'  No embedding for {fid_nace}')
            continue
        dist = cosine(e767, enace)
        print(f'  767 ({fid_767[:12]}) <-> Nace ({fid_nace[:12]}): dist={dist:.4f}')
"
```

**Record the actual distances.** These determine which tier each example falls into.
Write findings to session log.

### 0C: Create worktrees

```bash
git worktree add ../rhodesli-pipeline-fix pipeline-fix -b session-76a/pipeline-fix
git worktree add ../rhodesli-browse-cards browse-cards -b session-76a/browse-cards
```

Track B (Discoveries UX) runs on main AFTER Track A merges.
Track D (Tests) runs on main AFTER everything merges.

Commit: `docs: session 76a prompt, context, and log initialized`

---

## TRACK A: Auto-Clustering Pipeline Fix (worktree: pipeline-fix) (~15 min)

After Phase 0, switch to pipeline-fix worktree.
Read `docs/prompts/session-76a-prompt.md` and `docs/session_context/session-76a-context.md`.

### A1: Write PRD for Auto-Clustering

Create `docs/prds/NNN_auto_clustering_pipeline.md` (use next available number).

The PRD must define:
- **Tier 1 threshold:** Auto-add to cluster. Default: distance < 0.85.
  VERIFY against actual confirmed cluster distances first.
  If the mean same-person distance is 1.01 with std 0.19,
  then 0.85 is about 0.84 standard deviations below the mean.
  Adjust if the data suggests a different cutoff.
- **Tier 2 threshold:** Surface as suggestion. Default: 0.85 - 1.10.
- **Pipeline integration point:** Where in process_uploads.py does
  auto-clustering run? After embedding generation, before proposal generation.
- **Data model changes:** New fields on identity records to track
  auto-clustered faces vs manually confirmed faces.
- **Discovery log schema:** Every auto-cluster and suggestion is logged
  with face_id, target_identity, distance, tier, timestamp.

### A2: Write SDD for Auto-Clustering

Create `docs/design/sdd_auto_clustering.md` or equivalent.

The SDD specifies:
```python
def auto_cluster_face(face_id, embedding, confirmed_identities, embeddings_index):
    """
    Called during upload pipeline after face detection + embedding.
    
    Returns one of:
    - ("auto_clustered", identity_id, distance) — face added to cluster
    - ("suggested", identity_id, distance) — face flagged for Discovery
    - ("no_match", None, None) — face goes to Inbox as Unidentified
    
    Steps:
    1. Compute distance from face_id to ALL faces in confirmed identities
    2. Find minimum distance and which identity it belongs to
    3. If min_distance < TIER_1_THRESHOLD: auto-add to that identity's faces
    4. If TIER_1_THRESHOLD <= min_distance < TIER_2_THRESHOLD: create Discovery entry
    5. Else: no match, face stays in Inbox
    
    CRITICAL: Use the same distance metric as the existing clustering pipeline.
    """
```

### A3: Implement auto_cluster_face()

In the appropriate module (likely `app/clustering.py` or `rhodesli_ml/clustering.py`):

1. Implement the function from the SDD
2. Add Discovery log entries: `data/discovery_log.json`
   ```json
   {
     "entries": [
       {
         "face_id": "...",
         "target_identity": "Big Leon Capeluto",
         "target_identity_id": "...",
         "distance": 0.72,
         "tier": 1,
         "action": "auto_clustered",
         "timestamp": "2026-02-28T...",
         "user_decision": null,
         "user_decision_timestamp": null
       }
     ]
   }
   ```

3. Wire into `process_uploads.py`:
   - After `generate_embeddings()` step
   - Before `generate_proposals()` step
   - Call `auto_cluster_face()` for each new face
   - If Tier 1: modify identities.json to add face to cluster
   - If Tier 2: add to discovery_log.json only
   - If no match: proceed as before (face goes to Inbox)

### A4: Backfill existing faces

Run auto-clustering on ALL current inbox faces (the 405 in New Matches):

```bash
python3 -c "
# Pseudo-code — adapt to actual data structures
from app.clustering import auto_cluster_face
import json, numpy as np

# Load data
with open('data/identities.json') as f:
    data = json.load(f)
embs = np.load('data/embeddings.npy', allow_pickle=True)

confirmed = [i for i in data['identities'] if i.get('status') == 'confirmed']
inbox = [i for i in data['identities'] if i.get('status') != 'confirmed']

results = {'tier_1': 0, 'tier_2': 0, 'no_match': 0}
for identity in inbox:
    for face in identity.get('faces', []):
        result = auto_cluster_face(face['face_id'], ...)
        results[result[0]] += 1

print(f'Results: {results}')
# Expected: some tier_1 (like 768/Big Leon), some tier_2 (like 767/Nace), most no_match
"
```

**Record actual counts in session log and AD entry.**

### A5: AD Entry

Add to ALGORITHMIC_DECISIONS.md:
```
## AD-NNN: Two-Tier Auto-Clustering at Upload Time

**Decision:** Auto-add faces to confirmed clusters when distance < X (Tier 1).
Surface as Discovery suggestion when X < distance < Y (Tier 2).
**Thresholds:** Tier 1 = [actual value from data], Tier 2 = [actual value from data]
**Evidence:** [paste actual distance distribution findings from Phase 0B]
**Rejected alternative:** All-suggestion model (current state) — produces
  405 manual review items when most could be auto-resolved.
**Rejected alternative:** Single threshold — doesn't capture the
  confidence gradient between "definitely the same" and "probably the same."
**ML signal:** Every Discovery action is logged for threshold recalibration
  and future LoRA training data.
**Session:** 76a
```

Commit: `feat(ml): two-tier auto-clustering pipeline with discovery log`
```bash
git add -A && git commit -m "feat(ml): two-tier auto-clustering pipeline with discovery log"
```

---

## TRACK C: Browse Card Face Sizing (worktree: browse-cards) (~10 min)

**Run in PARALLEL with Track A.** Switch to browse-cards worktree.
Read `docs/prompts/session-76a-prompt.md` and `docs/session_context/session-76a-context.md`.

### C1: Audit current card layout

```bash
# Find the browse view card template/rendering
grep -n "browse\|card\|face.*crop\|thumb\|identity.*card" app/main.py | head -30

# Find current face image sizing
grep -n "width.*px\|height.*px\|face.*size\|crop.*size\|img.*style" app/main.py | head -20

# Find the card components
grep -n "def.*card\|def.*browse\|def.*identity" app/main.py | head -15
```

### C2: Redesign card layout

The card must be FACE-DOMINANT. Current layout wastes space on chrome.

**New layout:**
```
┌─────────────────────────┐
│                         │
│     ┌─────────────┐     │
│     │             │     │
│     │   FACE      │     │  ← 200px minimum height
│     │   CROP      │     │
│     │             │     │
│     └─────────────┘     │
│                         │
│  Unidentified Person 768│
│  INBOX · 1 face · Good  │
│                         │
│  ┌────┐ ┌────┐ ┌─────┐  │
│  │ ✓  │ │ ⏸  │ │  ✗  │  │  ← compact action row
│  └────┘ └────┘ └─────┘  │
└─────────────────────────┘
```

Changes:
1. Face crop: **minimum 200px tall** on desktop, 150px on mobile
2. Remove from card surface: Sort dropdown, View All Photos button,
   Find Similar button, View Photo link, Share link, Edit Details link
3. Keep on card: Name, status badge, face count, quality label, 3 action buttons
4. Move removed items to: hover overlay OR click-to-expand detail panel
5. Similar Identities panel face crops: minimum 64px (currently ~48px)

### C3: Spawn UX Review Subagent

After implementing the card changes, spawn a subagent:

```yaml
---
name: ux-reviewer
description: Review browse card screenshots for design quality
isolation: worktree
---
```

The UX reviewer subagent should:
1. Take a screenshot of the browse view using Claude Chrome (or Playwright fallback):
   ```bash
   # Playwright fallback if Claude Chrome unavailable
   python3 -c "
   from playwright.sync_api import sync_playwright
   with sync_playwright() as p:
       browser = p.chromium.launch()
       page = browser.new_page(viewport={'width': 1280, 'height': 900})
       page.goto('http://localhost:5001/?section=to_review&view=browse')
       page.wait_for_timeout(2000)
       page.screenshot(path='screenshots/session_76a_browse_cards.png')
       browser.close()
   "
   ```
2. Evaluate against the frontend-design skill principles:
   - Is the face the dominant visual element?
   - Is the card layout clean and intentional?
   - Are action buttons discoverable but not dominating?
   - Does the color system (dark theme) support face visibility?
3. Write findings to `docs/session_logs/session_76a_ux_review.md`
4. If issues found, make CSS/layout fixes and re-screenshot

Commit: `feat(ux): face-dominant browse cards — 200px min face, compact actions`
```bash
git add -A && git commit -m "feat(ux): face-dominant browse cards — 200px min face, compact actions"
```

---

## /clear — Merge Tracks A and C, then continue

```bash
# Back on main branch
cd /path/to/rhodesli

# Merge pipeline fix
git merge session-76a/pipeline-fix --no-ff -m "merge: Track A — auto-clustering pipeline"

# Merge browse cards
git merge session-76a/browse-cards --no-ff -m "merge: Track C — face-dominant browse cards"

# Run tests to verify merge is clean
pytest tests/ -x -q --tb=short 2>&1 | tail -5

# Clean up worktrees
git worktree remove ../rhodesli-pipeline-fix
git worktree remove ../rhodesli-browse-cards
```

Re-read `docs/prompts/session-76a-prompt.md`.
Re-read `docs/session_context/session-76a-context.md`.

---

## TRACK B: Discoveries UX Redesign (on main, after merge) (~15 min)

### B1: Write PRD for Discoveries Redesign

Create `docs/prds/NNN_discoveries_redesign.md` (next available number).

**Discoveries is the ML audit trail.** It shows what the AI did or recommends,
and lets the human confirm, correct, or reject.

PRD must cover:
1. **Two sections on Discoveries page:**
   - "Recently Added" (Tier 1 auto-clusters) — cards showing face + cluster
     it was added to, with Confirm / Undo buttons
   - "Suggested Matches" (Tier 2) — cards showing face + suggested cluster,
     with Accept / Reject buttons
2. **Card layout for Discoveries:**
   ```
   ┌──────────────────────────────────────┐
   │  ┌──────────┐     ┌──────────┐      │
   │  │  NEW     │     │  MATCHED │      │
   │  │  FACE    │     │  PERSON  │      │
   │  │  (150px) │     │  (150px) │      │
   │  └──────────┘     └──────────┘      │
   │                                      │
   │  Unidentified    [Good match]        │
   │  Person 768      Big Leon Capeluto   │
   │                  Confirmed           │
   │                                      │
   │  Also in photo: Person 767           │
   │  Collection: [collection name]       │
   │                                      │
   │  [✓ Confirm]            [↩ Undo]     │  ← Tier 1
   │  -- OR --                            │
   │  [✓ Accept as Big Leon] [✗ Reject]   │  ← Tier 2
   └──────────────────────────────────────┘
   ```
3. **Batch actions:** "Confirm All High-Confidence" button for Tier 1
4. **ML signal display:** Show confidence badge (Good/Possible),
   hide distance by default, show on click/hover
5. **Counts:** Header shows "N auto-clustered, M suggestions"

### B2: Implement Discoveries page

Modify the `/discoveries` route (or create if it doesn't exist).

Key implementation details:
1. Read from `data/discovery_log.json` for entries
2. Tier 1 entries: show face + cluster it was added to + Confirm/Undo
3. Tier 2 entries: show face + suggested cluster + Accept/Reject
4. On Confirm (Tier 1): update discovery_log entry with user_decision="confirmed"
5. On Undo (Tier 1): REMOVE face from cluster, move back to Inbox,
   update discovery_log with user_decision="undone"
6. On Accept (Tier 2): ADD face to cluster, update discovery_log
   with user_decision="accepted"
7. On Reject (Tier 2): update discovery_log with user_decision="rejected",
   face stays in Inbox
8. ALL actions use HTMX for instant UI update without page reload

### B3: Wire Discovery counts into sidebar

Update sidebar to show:
- Discoveries badge count = (pending Tier 1 items) + (pending Tier 2 items)
- After user acts on a Discovery, count decreases
- Tier 1 items that are confirmed disappear from Discoveries
- Tier 2 items that are accepted/rejected disappear from Discoveries

### B4: Spawn UX Review Subagent for Discoveries

Same pattern as Track C — take screenshot, evaluate against frontend-design
skill, write findings, fix issues.

Screenshot the Discoveries page after backfill data populates it.
Verify:
- Faces are large enough to identify (150px minimum)
- Two sections are visually distinct (Tier 1 vs Tier 2)
- Actions are clear and prominent
- Match confidence badges are readable

Commit: `feat(ux): discoveries redesign — two-tier ML audit trail`
```bash
git add -A && git commit -m "feat(ux): discoveries redesign — two-tier ML audit trail with confirm/undo/accept/reject"
```

---

## TRACK D: Testing + Deploy + Verify (~10 min)

### D1: Write key tests

Spawn a test subagent that writes tests in parallel:

```yaml
---
name: test-writer
description: Write integration tests for session 76a features
isolation: worktree
---
```

Tests to write:
```python
# Auto-clustering pipeline
def test_auto_cluster_tier1_adds_to_identity():
    """Face with distance < TIER_1_THRESHOLD is added to confirmed cluster."""

def test_auto_cluster_tier2_creates_discovery():
    """Face with distance in Tier 2 range creates discovery_log entry."""

def test_auto_cluster_no_match_stays_inbox():
    """Face with distance > TIER_2_THRESHOLD stays as Unidentified in Inbox."""

def test_auto_cluster_logs_entry():
    """Every auto-cluster action creates a discovery_log.json entry."""

# Discoveries UX
def test_discoveries_page_shows_tier1_items():
    """Tier 1 auto-clustered items appear with Confirm/Undo buttons."""

def test_discoveries_page_shows_tier2_items():
    """Tier 2 suggestions appear with Accept/Reject buttons."""

def test_discovery_confirm_marks_confirmed():
    """Confirming a Tier 1 item updates discovery_log."""

def test_discovery_undo_removes_from_cluster():
    """Undoing a Tier 1 item removes face from cluster and returns to Inbox."""

def test_discovery_accept_adds_to_cluster():
    """Accepting a Tier 2 suggestion adds face to cluster."""

def test_discovery_reject_keeps_in_inbox():
    """Rejecting a Tier 2 suggestion keeps face in Inbox."""

# Browse card sizing
def test_browse_card_face_minimum_size():
    """Face crop in browse cards has minimum 200px height."""

def test_browse_card_compact_actions():
    """Browse card has only 3 action buttons visible, rest on hover."""
```

### D2: Run full test suite

```bash
pytest tests/ -x -q --tb=short
```

If failures: fix them. Do not skip.

### D3: Deploy

```bash
git add -A
git commit -m "test: session 76a integration tests for auto-clustering and discoveries"
git push origin main
sleep 120  # Wait for Railway deploy
```

### D4: Production verification with Claude Chrome

Use Claude Chrome (or Playwright fallback) to verify production:

```bash
# 1. Check Discoveries page has entries
curl -s "https://rhodesli.nolanandrewfox.com/discoveries" | grep -o "auto-clustered\|Confirm\|Undo\|Accept\|Reject\|Big Leon\|Nace" | head -10

# 2. Check browse cards have larger faces
curl -s "https://rhodesli.nolanandrewfox.com/?section=to_review&view=browse" | grep -o "200px\|min-height\|face.*large\|face-dominant" | head -5

# 3. Check sidebar counts updated
curl -s "https://rhodesli.nolanandrewfox.com/" | grep -o "[0-9]* New Matches\|[0-9]* Discoveries\|[0-9]* Help Identify"

# 4. Take production screenshots
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    
    # Discoveries page
    page.goto('https://rhodesli.nolanandrewfox.com/discoveries')
    page.wait_for_timeout(3000)
    page.screenshot(path='screenshots/session_76a_discoveries_prod.png')
    
    # Browse view
    page.goto('https://rhodesli.nolanandrewfox.com/?section=to_review&view=browse')
    page.wait_for_timeout(3000)
    page.screenshot(path='screenshots/session_76a_browse_prod.png')
    
    browser.close()
"
```

### D5: UX Review Subagent on Production

Spawn final UX review subagent on production screenshots:
1. Compare before (user's uploaded screenshots) vs after
2. Verify face sizes are genuinely larger
3. Verify Discoveries page is functional and clear
4. Write final UX assessment to session log

---

## PHASE FINAL: Documentation + Session Close (~5 min)

### F1: Update ROADMAP.md
- Add Session 76a to Recently Completed
- Update version number
- Update test count
- Update feature status for auto-clustering, Discoveries

### F2: Update BACKLOG.md
- Mark auto-clustering as DONE
- Mark Discoveries redesign as DONE
- Mark face card sizing as DONE
- Add any new items discovered during session

### F3: Update SESSION_HISTORY.md
- Add session 76a entry with outcomes

### F4: Session Log completion

Write final session log to `docs/session_logs/session_76a_log.md`:
```markdown
# Session 76a Log

## Planned vs Actual
| Phase | Planned | Actual | Notes |
|-------|---------|--------|-------|

## Key Decisions
- AD-NNN: Two-tier auto-clustering thresholds
- PRD-NNN: Auto-clustering pipeline
- PRD-NNN: Discoveries redesign

## Metrics
- Inbox before: 405
- Inbox after: [actual]
- Discoveries Tier 1: [count]
- Discoveries Tier 2: [count]
- Tests added: [count]
- Total tests: [count]

## 768/767 Investigation Results
- Person 768 <-> Big Leon distance: [actual]
- Person 767 <-> Nace distance: [actual]
- 768 tier: [1 or 2]
- 767 tier: [1 or 2]
```

### F5: Verification Gate

Re-read `docs/prompts/session-76a-prompt.md`.

Check EVERY item:

```bash
echo "=== SESSION 76a VERIFICATION GATE ==="

# Track A: Auto-clustering exists
grep -c "auto_cluster\|auto-cluster" app/*.py rhodesli_ml/*.py 2>/dev/null

# Track A: Discovery log exists
ls data/discovery_log.json

# Track A: AD entry written
grep "auto-cluster\|Two-Tier\|Tier 1\|Tier 2" docs/ALGORITHMIC_DECISIONS.md | head -3

# Track A: PRD written
ls docs/prds/*auto_cluster* docs/prds/*clustering* 2>/dev/null

# Track B: Discoveries page shows two tiers
curl -s "https://rhodesli.nolanandrewfox.com/discoveries" | grep -c "Confirm\|Accept"

# Track C: Face crops are larger
curl -s "https://rhodesli.nolanandrewfox.com/?section=to_review&view=browse" | grep -o "min-height:[^;]*" | head -3

# Track D: Tests pass
pytest tests/ -x -q --tb=no 2>&1 | tail -1

# Docs: Session log exists
ls docs/session_logs/session_76a_log.md

# Docs: ROADMAP updated
grep "76a" ROADMAP.md

echo "=== GATE COMPLETE ==="
```

If ANY check fails: fix it before declaring session done.

Commit: `docs: session 76a complete — auto-clustering, discoveries, face cards`
```bash
git add -A && git commit -m "docs: session 76a complete — auto-clustering, discoveries redesign, face-dominant cards"
git push origin main
```

---

## SESSION RULES REMINDER

- Start app and verify EVERY change in browser/curl
- Run tests after EVERY merge (not every phase — batched at end per testing strategy)
- Check requirements.txt for any new dependencies
- Handle missing dependencies gracefully (degrade, don't crash)
- Commit after every phase with descriptive messages
- Deploy via git push (not Railway dashboard)
- Use Claude Chrome for screenshots; Playwright as fallback
- Every AD entry must have: decision, rejected alternatives, source session, rationale
- Keep docs under 300 lines each
- ROADMAP.md under 150 lines
- CLAUDE.md under 80 lines
- If context exceeds 60%, /clear and re-read context file
- Update ALGORITHMIC_DECISIONS.md after EVERY algorithmic decision
- DO NOT modify confirmed identity data EXCEPT through auto_cluster_face()
- DO NOT use /compact — use /clear + re-read from disk
