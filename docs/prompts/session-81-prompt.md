# Session 81: Connected App — Tree, Map, Location Intelligence, Face Labels + Session 80 Deferred

## SESSION IDENTITY
- **Session**: 81
- **Predecessor**: Session 80 (Tree overhaul, Face Cards, Compare CPU fix)
- **Concurrent**: Session 80b may be running — use separate worktree branches prefixed `session-81/`
- **Goal**: Make every page in Rhodesli flow together. Photo → Tree → Map → Person = one-click navigation everywhere. Add Gemini location intelligence with GEDCOM-enriched prompts. Label faces in Face Analysis. Fix Session 80 deferred items.
- **Estimated time**: 120-150 minutes (parallelized across 7 tracks)
- **Context file**: `docs/session_context/session_81_context.md`
- **Assessment file**: `docs/assessments/session-81-assessment.md` (MANDATORY — hook-enforced)
- **Session log**: `docs/sessions/SESSION_081.md` (MANDATORY — hook-enforced)

---

## ⚠️ PHASE 0: INSTALL HOOKS + SKILLS FIRST (Before ANY other work)

### 0A: Install Context Enforcement Hooks

**This is the FIRST thing you do.** Without this, /clear will not be enforced
and the session will fail like Sessions 61, 62, 64 did.

Update `.claude/settings.json` to include these hooks. If the file exists,
MERGE — do not overwrite existing hooks.

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'ASSESS=\"docs/assessments/session-81-assessment.md\"; LOG=\"docs/sessions/SESSION_081.md\"; MISSING=0; if [ ! -f \"$ASSESS\" ]; then echo \"⛔ BLOCKED: Assessment file missing: $ASSESS\"; echo \"Run the session-review skill before stopping.\"; MISSING=1; fi; if [ ! -f \"$LOG\" ]; then echo \"⛔ BLOCKED: Session log missing: $LOG\"; echo \"Write the session log before stopping.\"; MISSING=1; fi; if [ \"$MISSING\" -eq 1 ]; then exit 1; fi; echo \"✓ Assessment and log files exist. Session may end.\"; exit 0'"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'INPUT=$(cat); CMD=$(echo \"$INPUT\" | jq -r \".tool_input.command // empty\" 2>/dev/null); if echo \"$CMD\" | grep -qE \"^git commit\"; then echo \"══════════════════════════════════════════════\"; echo \"🔴 SESSION 81: /clear GATE\"; echo \"══════════════════════════════════════════════\"; echo \"You just committed. You MUST now:\"; echo \"  1. Run /clear (NOT /compact)\"; echo \"  2. Re-read ONLY next act from docs/prompts/session-81-prompt.md\"; echo \"  3. Re-read context: head -40 docs/session_context/session_81_context.md\"; echo \"  4. Check progress: cat /tmp/session_81_checklist.md\"; echo \"══════════════════════════════════════════════\"; if [ -f /tmp/session_81_checklist.md ]; then cat /tmp/session_81_checklist.md; fi; fi; if echo \"$CMD\" | grep -qE \"rhodesli_ml/.*\\.py|core/.*\\.py\"; then echo \"⚠️  ML file touched. Update ALGORITHMIC_DECISIONS.md if design decision.\"; fi; exit 0'"
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c 'notify-send \"Claude Code\" \"Session 81: Awaiting input\" 2>/dev/null || osascript -e \"display notification \\\"Session 81: Awaiting input\\\" with title \\\"Claude Code\\\"\" 2>/dev/null; exit 0'"
          }
        ]
      }
    ]
  }
}
```

**What these hooks enforce:**
- **Stop hook**: BLOCKS session from ending unless `docs/assessments/session-81-assessment.md` AND `docs/sessions/SESSION_081.md` exist. This guarantees the assessment and log get written.
- **PostToolUse on git commit**: Prints a giant banner reminding to /clear after every commit, shows the checklist. Cannot be ignored.
- **PostToolUse on ML files**: Reminds to update ALGORITHMIC_DECISIONS.md.
- **Notification**: Pings when waiting for input (useful overnight).

### 0B: Verify Hooks Are Active

```bash
echo "=== VERIFYING HOOKS ==="
cat .claude/settings.json | jq '.hooks.Stop' && echo "✓ Stop hook" || echo "✗ MISSING Stop hook"
cat .claude/settings.json | jq '.hooks.PostToolUse' && echo "✓ PostToolUse hook" || echo "✗ MISSING PostToolUse hook"
# Test the stop hook by checking it would block:
test ! -f docs/assessments/session-81-assessment.md && echo "✓ Stop hook would correctly block (assessment missing)" || echo "Assessment already exists"
test ! -f docs/sessions/SESSION_081.md && echo "✓ Stop hook would correctly block (log missing)" || echo "Log already exists"
```

### 0C: Verify/Create Skills

```bash
echo "=== CHECKING SKILLS ==="
for skill in ux-review session-review overnight-session deploy-verify ml-pipeline; do
  if [ -f ".claude/skills/$skill/SKILL.md" ]; then
    echo "✓ $skill skill exists"
  else
    echo "✗ MISSING $skill — CREATING NOW"
  fi
done
```

**If `ux-review` skill is missing, CREATE IT:**

`.claude/skills/ux-review/SKILL.md`:
```yaml
---
name: ux-review
description: 'Spawn a UX review subagent that examines all screenshots taken by
  Claude Chrome or Playwright. Evaluates design quality, finds visual bugs, and
  resolves bugs via a separate git worktree and subagent. MUST run after any
  session that changes UI. Invoked automatically at session end.'
---
```
Content (write 40-50 lines covering):
1. Collect ALL screenshots from current session (Claude Chrome, Playwright, /tmp, screenshots/)
2. Spawn subagent in worktree `session-NN/ux-fixes`
3. Evaluate each screenshot against:
   - Touch targets ≥44px mobile
   - WCAG AA contrast
   - Layout consistency across pages
   - No broken images, cut-off text, missing icons
   - Navigation flows work (links lead to expected page)
   - Responsive at 375px, 768px, 1024px
   - Visual hierarchy clear
   - Empty states handled gracefully
4. For each bug found: fix in worktree, screenshot the fix, log finding
5. Merge worktree back to main
6. Append to session log: "UX Review: N bugs found, N fixed, N deferred (with reasons)"

**If `session-review` skill is missing, CREATE IT:**

`.claude/skills/session-review/SKILL.md`:
```yaml
---
name: session-review
description: 'At session end: critically assess all work against original prompt.
  Identify concerns, red flags, gaps, superficial work. Then automatically spawn
  an auto-fix subagent that resolves all fixable issues. Logs everything clearly
  so we know what slipped by. Writes the mandatory assessment file. MUST run
  every session.'
---
```
Content (write 50-60 lines covering):
1. Re-read the ORIGINAL prompt from `docs/prompts/session-NN-prompt.md`
2. For EVERY act/phase in the prompt:
   a. Verify artifacts exist on disk (grep, ls, curl)
   b. Verify tested (test output, screenshots, browser evidence)
   c. Flag ANY silent deferrals, shortcuts, or "claimed done but not verified"
3. Write `docs/assessments/session-NN-assessment.md`:
   - Per-act status: ✅ Complete / ⚠️ Partial / ❌ Missing
   - Concerns and red flags (be brutally honest — this replaces Nolan asking)
   - Things done superficially (tests that don't actually test, features that aren't wired up)
   - Specific evidence for each claim (file paths, test names, curl outputs)
4. **AUTO-FIX PHASE**: Spawn subagent in worktree `session-NN/auto-fix`
   - Fix EVERY concern that can be fixed right now
   - For each fix: log "AUTO-FIXED: [description] — was: [problem] now: [solution]"
   - For each deferral: log "DEFERRED: [description] — REASON: [why can't fix now]"
5. Merge auto-fix worktree
6. Update assessment with final counts: "N issues found, N auto-fixed, N deferred"
7. This file's existence is enforced by the Stop hook — session cannot end without it

Commit: `chore: session 81 phase 0 — hooks installed + skills verified`

---

## ⚠️ MANDATORY: LOG ALL FEEDBACK FIRST

Before writing ANY code, create `docs/session_context/session_81_nolan_feedback.md`:

1. **Asheville Photo Case Study** — Photo 746dd11e5b4d86a1. Manual Gemini chat identified 33 Elizabeth Street, Asheville, NC. Our automated prompt didn't. Benchmark for GEDCOM enrichment.
2. **Connected App Vision** — Photo → Tree → Map → Person, one-click everywhere, admin AND sharing pages.
3. **Face Analysis Labels** — Names not "Face N", clickable links to person pages.
4. **Location Intelligence** — Embedded maps, Gemini reasoning display, research Google/Apple/Mylio patterns.
5. **GEDCOM-Enriched Prompts** — Evaluate current prompt, enhance with biographical context, test against Asheville ground truth.
6. **Chatbot Interface** — Future vision, BACKLOG only.
7. **Session 80 Deferred** — Matilda GEDCOM fix, relationship viz, browser verification.

Commit: `docs: session 81 feedback log`

---

## ⚠️ CONTEXT MANAGEMENT — HOOK-ENFORCED

The PostToolUse hook prints a giant red banner after every `git commit` reminding
you to /clear. **You cannot miss it.** The sequence after every act:

1. `git add -A && git commit -m "session-81 act N: [description]"`
2. The hook fires: 🔴 /clear GATE banner appears
3. **Run /clear** (NOT /compact — the hook told you)
4. Re-read ONLY next act: `sed -n '/^## ACT [NEXT]/,/^## ACT/p' docs/prompts/session-81-prompt.md | head -100`
5. Re-read context: `head -40 docs/session_context/session_81_context.md`
6. Check progress: `cat /tmp/session_81_checklist.md`

### Initialize Checklist
```bash
cat > /tmp/session_81_checklist.md << 'EOF'
# Session 81 Phase Checklist
- [ ] PHASE 0: Hooks + skills installed and verified
- [ ] FEEDBACK: All Nolan feedback documented to disk
- [ ] ACT 1: Photo→Tree navigation (worktree: tree-nav)
- [ ] ACT 2: Face labels + Photo→Map navigation (worktree: face-map)
- [ ] ACT 3: Embedded location maps + Gemini location UX (worktree: location-ux)
- [ ] ACT 4: GEDCOM-enriched location prompts + Asheville test (main)
- [ ] ACT 5: Batch re-run if Act 4 succeeds (main)
- [ ] ACT D1: Matilda GEDCOM face link fix (worktree: deferred-matilda)
- [ ] ACT D2: Relationship viz enhancements (worktree: deferred-rel-viz)
- [ ] ACT D3: Browser verify Session 80 changes (worktree: deferred-verify)
- [ ] ACT 6: Merge all worktrees + integration test
- [ ] ACT 7: Verification gate + MANDATORY skills
- [ ] SKILL: UX Review subagent ran on ALL screenshots
- [ ] SKILL: Session Review + Auto-Fix wrote assessment file
EOF
```

---

## PARALLELIZATION PLAN

### Worktree Setup (7 parallel tracks)
```bash
git worktree add .claude/worktrees/tree-nav -b session-81/tree-nav
git worktree add .claude/worktrees/face-map -b session-81/face-map
git worktree add .claude/worktrees/location-ux -b session-81/location-ux
git worktree add .claude/worktrees/deferred-matilda -b session-81/deferred-matilda
git worktree add .claude/worktrees/deferred-rel-viz -b session-81/deferred-rel-viz
git worktree add .claude/worktrees/deferred-verify -b session-81/deferred-verify
```

### Track Assignment — ALL as subagents, ALL in parallel
- **Track A** `tree-nav`: ACT 1 — Photo→Tree smart navigation
- **Track B** `face-map`: ACT 2 — Face labels + Photo→Map links
- **Track C** `location-ux`: ACT 3 — Embedded maps + location UX
- **Track D1** `deferred-matilda`: Supabase GEDCOM face link fix
- **Track D2** `deferred-rel-viz`: Relationship viz (thicker lines, hover, generation bands)
- **Track D3** `deferred-verify`: Browser verification of Session 80 changes
- **Main**: ACTs 4-5 — GEDCOM prompt enhancement + batch re-run

**Each subagent should further break down into sub-subagents and sub-worktrees
as needed.** Give each track maximum bandwidth. Speed through parallelism.

### Merge Order
1. D1, D2, D3 first (deferred — smallest, least conflict)
2. Track B (face-map)
3. Track A (tree-nav)
4. Track C (location-ux)
5. Then ACTs 4-5 on main

---

## ACT 1: PHOTO → TREE SMART NAVIGATION
**Worktree**: `session-81/tree-nav` | **Subagent**: Yes — parallel
**Decompose further**: Sub-subagents for BFS logic vs UI vs tests

### Phase 1A: Tree Button on Photo Page (~10 min)
Add "🌳 Family Tree" button to photo page action bar (admin AND sharing).
→ `/tree?photo_id={id}&people={person_ids}`

### Phase 1B: Smart Subtree Logic (~15 min)
Read existing tree code + Session 80 docs FIRST to understand current architecture.

**Nuclear family** (Victoria + kids): Parents + children only. Don't expand grandparents.
**Unrelated**: Side-by-side immediate families.
**Distant relatives**: BFS shortest path through GEDCOM graph, show connecting nodes only.
Default tree pictures = cropped faces from THIS photo.

```python
def compute_subtree_for_photo(person_ids, gedcom):
    if len(person_ids) == 0: return None
    if len(person_ids) == 1: return immediate_family(person_ids[0])
    if is_nuclear_family(person_ids, gedcom):
        return nuclear_family_subtree(person_ids, gedcom)
    paths = []
    for i, p1 in enumerate(person_ids):
        for p2 in person_ids[i+1:]:
            path = bfs_shortest_path(p1, p2, gedcom)
            if path: paths.append(path)
    if paths: return union_paths(paths)
    return [immediate_family(pid) for pid in person_ids]
```

### Phase 1C: Face Thumbnails on Tree Nodes (~10 min)
### Phase 1D: One-Click Tree from Person Page (~5 min) — admin AND sharing
### Phase 1E: Tests — nuclear, unrelated, distant, single, no GEDCOM

Commit: `feat(tree): photo→tree smart navigation with relationship-aware subtrees`
**🔴 /clear gate fires. Follow the protocol.**

---

## ACT 2: FACE ANALYSIS LABELS + PHOTO → MAP
**Worktree**: `session-81/face-map` | **Subagent**: Yes — parallel

### Phase 2A: Face Identity Labels (~10 min)
Replace "Face N" with person name if identified. Clickable link to `/person/{id}`.
Unidentified: "Face N (Unidentified)".

### Phase 2B: Map Button on Photo Page (~10 min)
"🗺️ See on Map" → `/map?people={ids}`. Filters to photos of those people.

### Phase 2C: Map Link on Person Page (~5 min) — admin AND sharing
### Phase 2D: Tests

Commit: `feat(ux): face analysis labels + photo/person→map navigation`
**🔴 /clear gate fires.**

---

## ACT 3: EMBEDDED LOCATION MAPS + GEMINI LOCATION UX
**Worktree**: `session-81/location-ux` | **Subagent**: Yes — parallel
**Decompose**: Sub-subagent for research, sub-subagent for Leaflet, sub-subagent for data model

### Phase 3A: Research Photo Location UX (~10 min)
Google Photos, Apple Photos, Mylio patterns. Write to `docs/session_context/session_81_location_ux_research.md`.

### Phase 3B: Gemini Location Estimation Display (~15 min)
New section matching Date Estimate pattern: location label, confidence badge, evidence cards, admin correct button.

### Phase 3C: Location Data Model (~10 min)
`location_estimate` + `location_confirmed` fields.

### Phase 3D: Embedded Leaflet Map (~10 min)
Leaflet.js + OpenStreetMap (free, no API key). 300px. Admin: draggable pin.

### Phase 3E: Tests

Commit: `feat(location): embedded maps + Gemini location UX`
**🔴 /clear gate fires.**

---

## ACT D1: SUPABASE GEDCOM FACE LINK FIX FOR MATILDA
**Worktree**: `session-81/deferred-matilda` | **Subagent**: Yes — parallel
**Source**: Session 80 assessment

**FIRST**: Read `docs/assessments/session-80-assessment.md` and any related docs/prds
to understand the full context. Don't guess — the docs explain what's broken.

1. Investigate: What's wrong with Matilda's GEDCOM face link?
2. Identify correct Supabase API call
3. Fix
4. Add regression test
5. Verify in browser

Commit: `fix(data): Matilda GEDCOM face link — session 80 deferred`

---

## ACT D2: RELATIONSHIP VISUALIZATION ENHANCEMENTS
**Worktree**: `session-81/deferred-rel-viz` | **Subagent**: Yes — parallel
**Decompose into 3 sub-subagents**: one per enhancement
**Source**: Session 80 assessment

**FIRST**: Read Session 80 assessment + existing tree/relationship code.

1. **Thicker lines** — more shared photos = thicker connection line
2. **Hover labels** — relationship type + strength on hover
3. **Generation bands** — horizontal visual bands grouping by generation

Each independently testable. Screenshot each. Run UX review on screenshots.

Commit: `feat(tree): relationship viz — thicker lines, hover labels, generation bands`

---

## ACT D3: BROWSER VERIFICATION OF SESSION 80 CONTINUATION CHANGES
**Worktree**: `session-81/deferred-verify` | **Subagent**: Yes — parallel
**Source**: Session 80 assessment — "not yet deployed"

**FIRST**: Read Session 80 assessment to identify exactly which changes need verification.

1. Deploy current main: `git push`
2. Wait for Railway deploy
3. Open production URL in Claude Chrome
4. Verify EVERY Session 80 change noted as "not browser verified"
5. Screenshot each
6. Fix any issues
7. Log all results

Commit: `verify: session 80 continuation — browser verified`

---

## ACT 4: GEDCOM-ENRICHED LOCATION PROMPTS + ASHEVILLE TEST
**Branch**: main | **THE ML/AI LEARNING — DOCUMENT EVERYTHING**

### Phase 4A: Audit Current Prompt (~10 min)
```bash
grep -rn "location\|where.*taken\|geographic\|city\|address" rhodesli_ml/gemini*.py | grep -v __pycache__
grep -rn "gedcom\|family.*tree\|birth.*year\|residence" rhodesli_ml/gemini*.py | grep -v __pycache__
```
What GEDCOM context is passed? What's missing?

### Phase 4B: Design Enhanced Prompt (~10 min)
Inject: birth/death places, known addresses, children's birth dates, spouse, family migration patterns. See context file for what data cracked the Asheville case.

### Phase 4C: Implement Context Injection (~15 min)

### Phase 4D: Test Against Asheville Ground Truth (~10 min)
Photo 746dd11e5b4d86a1. Expected: "Asheville" or "North Carolina".
**Dry run first** — log prompt without calling API.
Then run with gemini-3-flash.
Log EVERYTHING: full prompt, full response, match analysis, decisive info, gaps vs manual conversation.
Write AD-XXX: GEDCOM-enriched location prompting strategy.

Commit: `feat(ml): GEDCOM-enriched location prompt + Asheville ground truth test`
**🔴 /clear gate fires.**

---

## ACT 5: BATCH RE-RUN + IMPACT ANALYSIS
**Branch**: main | **ONLY if ACT 4 identified Asheville**

### Phase 5A: Batch 1 — 5 photos (most identified faces), old vs new comparison
### Phase 5B: Impact analysis — quantitative, qualitative, cost, recommendations
### Phase 5C: Log chatbot idea to BACKLOG

Commit: `feat(ml): batch location re-run + impact analysis`
**🔴 /clear gate fires.**

---

## ACT 6: MERGE ALL WORKTREES + INTEGRATION
**Branch**: main

### Phase 6A: Merge (order: D1→D2→D3→B→A→C)
```bash
git merge session-81/deferred-matilda --no-ff -m "merge: Matilda GEDCOM fix"
git merge session-81/deferred-rel-viz --no-ff -m "merge: relationship viz"
git merge session-81/deferred-verify --no-ff -m "merge: browser verification"
git merge session-81/face-map --no-ff -m "merge: face labels + map nav"
git merge session-81/tree-nav --no-ff -m "merge: tree navigation"
git merge session-81/location-ux --no-ff -m "merge: location maps + UX"
```

### Phase 6B: Integration Test
Full test suite + curl all new features:
```bash
# Start app
python app/main.py &

# Test all new navigation
curl -s localhost:8000/photo/746dd11e5b4d86a1 | grep -q "Family Tree" && echo "✓ Tree button" || echo "✗ MISSING tree button"
curl -s localhost:8000/photo/746dd11e5b4d86a1 | grep -q "See on Map" && echo "✓ Map button" || echo "✗ MISSING map button"
curl -s localhost:8000/photo/746dd11e5b4d86a1 | grep -q "leaflet" && echo "✓ Embedded map" || echo "✗ MISSING embedded map"
curl -s localhost:8000/photo/746dd11e5b4d86a1 | grep -q "Victoria" && echo "✓ Face label" || echo "✗ MISSING face label"

# Person page links
curl -s localhost:8000/person/victoria-capuano-capeluto | grep -q "Family Tree" && echo "✓ Person→Tree" || echo "✗ MISSING"
curl -s localhost:8000/person/victoria-capuano-capeluto | grep -q "See on Map" && echo "✓ Person→Map" || echo "✗ MISSING"

# Full test suite
pytest tests/ -x -q --tb=short 2>&1 | tail -10
```
Deploy: `git push`

---

## ACT 7: VERIFICATION GATE + MANDATORY SKILLS

### ⛔ NOTHING IS DONE UNTIL ALL THREE PASS: Chrome verify + UX skill + Session review skill

### 7A: Visual Verification in Claude Chrome

Screenshot and verify each:

**Photo page (746dd11e5b4d86a1)**:
- [ ] Tree button in action bar
- [ ] Map button in action bar
- [ ] Embedded Leaflet map (if location exists)
- [ ] Location estimate with evidence cards
- [ ] Face Analysis shows "Victoria Capuano Capeluto" not "Face 2"
- [ ] Face names are clickable links
- [ ] Relationship lines show thickness variation

**Tree page (from photo link)**:
- [ ] Victoria + Leon as parents, children expanded
- [ ] Does NOT show Victoria's parents/siblings
- [ ] Face thumbnails from THIS photo
- [ ] Generation bands visible
- [ ] Hover labels on connections

**Map page (from photo link)**:
- [ ] Filtered to people in photo
- [ ] Current photo highlighted

**Person page (admin AND sharing)**:
- [ ] Tree link works
- [ ] Map link works
- [ ] No admin elements on sharing page

**Matilda page**:
- [ ] GEDCOM face link works

### 7B: Fix failures immediately. Do NOT proceed until all pass.

### 7C: RUN UX REVIEW SKILL (MANDATORY — NOT OPTIONAL)

**Invoke `.claude/skills/ux-review/SKILL.md` NOW.**

The UX review subagent:
1. Collects ALL screenshots from this session
2. Spawns in worktree `session-81/ux-fixes`
3. Evaluates against UX criteria (see skill)
4. Fixes bugs in worktree
5. Merges back
6. Logs: "UX Review: N bugs found, N fixed, N deferred"

### 7D: RUN SESSION REVIEW + AUTO-FIX SKILL (MANDATORY — ENFORCED BY STOP HOOK)

**Invoke `.claude/skills/session-review/SKILL.md` NOW.**

This replaces Nolan asking "Evaluate critically. Concerns? Red flags? Next steps?"
and then automatically does what would be "Session 81b" — fixing all gaps.

The skill:
1. Re-reads THIS prompt
2. Compares every act against what was actually built
3. Writes `docs/assessments/session-81-assessment.md` (REQUIRED by Stop hook)
4. Spawns auto-fix subagent in `session-81/auto-fix`
5. Fixes everything fixable, logs everything deferred
6. Updates assessment: "N issues found, N auto-fixed, N deferred"

**The Stop hook will BLOCK session completion if this file doesn't exist.**

### 7E: Write Session Log (ENFORCED BY STOP HOOK)

Create `docs/sessions/SESSION_081.md`:
```markdown
# Session 81 Log
Started: [timestamp] | Completed: [timestamp]

## Planned vs Actual
| Act | Planned | Status | Notes |
|-----|---------|--------|-------|
| 0   | Hooks + skills | ✅/⚠️/❌ | |
| 1   | Tree navigation | | |
| 2   | Face labels + map | | |
| 3   | Location UX | | |
| 4   | GEDCOM prompts | | |
| 5   | Batch re-run | | |
| D1  | Matilda fix | | |
| D2  | Relationship viz | | |
| D3  | Browser verify | | |

## Commits
[list all]

## Test Count
Before: NNN → After: NNN

## UX Review Findings
N bugs found, N fixed, N deferred

## Auto-Fix Log
N issues found, N auto-fixed, N deferred
[List each: what was found, what was done]

## Deferred to Session 82
[Everything not completed with clear reasons]
```

**The Stop hook will BLOCK session completion if this file doesn't exist.**

Also update: ALGORITHMIC_DECISIONS.md, ROADMAP.md (<150 lines), BACKLOG.md, SESSION_HISTORY.md

Final commit: `docs: session 81 complete`
`git push`

---

## SESSION RULES

1. **Phase 0 runs FIRST** — hooks + skills before any other work
2. **/clear between EVERY act** — PostToolUse hook prints 🔴 banner on every commit
3. Re-read from disk after /clear — only next act's section
4. **7 parallel subagents** for tracks A, B, C, D1, D2, D3 + main
5. Each subagent further decomposes into sub-subagents where beneficial
6. All tracks use git worktrees
7. Verify EVERY change in browser/curl
8. Run tests after every act
9. NOTHING done until Claude Chrome verification
10. Handle missing API keys gracefully
11. DO NOT modify confirmed identity data
12. DO NOT batch Gemini calls without dry-run first
13. Log ALL Gemini prompts and responses
14. Update ALGORITHMIC_DECISIONS.md for every algorithmic decision
15. Keep docs under 300 lines, ROADMAP under 150 lines
16. **UX Review skill MUST run** — catches what tests don't
17. **Session Review skill MUST run** — writes assessment + auto-fixes gaps
18. **Stop hook BLOCKS completion** without assessment + log files
19. All navigation links work on BOTH admin AND sharing pages
20. Read existing docs for deferred item context BEFORE building
