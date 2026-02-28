# Session 75: Post-Gemini Cleanup + Family Tree Upgrade

## Run with: `claude --dangerously-skip-permissions`

Read CLAUDE.md. Read docs/session_context/session-75-context.md.
Read docs/assessments/session-74-eval.md (full eval findings).

---

## SESSION RULES (ENFORCED — DO NOT SKIP ANY OF THESE)

1. **COMMIT AFTER EVERY PHASE.** No exceptions. If you crash mid-phase,
   previous phases are safe on main.
2. **USE /clear BETWEEN EVERY PHASE.** Not /compact. /compact is lossy.
   After /clear, re-read this prompt file + context file + checkpoint.
3. **UPDATE CHECKPOINT AFTER EVERY PHASE.** Write current status to
   `docs/session_context/session-75-checkpoint.md` so progress survives
   any crash, compaction, or context loss.
4. **TESTS BEFORE EVERY COMMIT.** Run `make test-fast` (or `pytest tests/
   -x -q`) and only commit if green.
5. **DO NOT STOP UNTIL ALL PHASES ARE COMPLETE.** If you hit a snag in
   one phase, document it in the checkpoint and move to the next phase.
   Come back to fix it after other phases complete. The session is not
   done until the final verification gate passes.
6. **KEEP PHASES SMALL.** Each phase is scoped to 5-15 minutes of work.
   If a phase is taking longer, checkpoint and split it.
7. **UPDATE ALGORITHMIC_DECISIONS.md** for every data or ML decision.

### Between EVERY phase (copy-paste this block):
```bash
# 1. Test
make test-fast || pytest tests/ -x -q

# 2. Commit
git add -A && git commit -m "session-75 phase N: [description]"

# 3. Update checkpoint
cat > docs/session_context/session-75-checkpoint.md << 'CHECKPOINT'
# Session 75 Checkpoint
Last completed: Phase N
Next: Phase N+1
Status: [what's done, what's pending]
Test count: [current count]
CHECKPOINT

# 4. Clear and reload
# /clear
# Then re-read:
# cat docs/session_context/session-75-context.md
# cat docs/session_context/session-75-checkpoint.md
# cat docs/prompts/session-75-prompt.md | sed -n '/^## PHASE N+1/,/^## PHASE N+2/p'
```

---

## PHASE 0: Orient + Create Checkpoint (~3 min)

```bash
git status
git log --oneline -15
cat docs/assessments/session-74-eval.md | head -80
cat rhodesli_ml/graph/relationship_graph.py | head -30
wc -l data/relationships.json
cat docs/ALGORITHMIC_DECISIONS.md | tail -20
cat docs/ROADMAP.md | head -30
```

Create the checkpoint file:
```bash
cat > docs/session_context/session-75-checkpoint.md << 'EOF'
# Session 75 Checkpoint — Post-Gemini Cleanup + Tree Upgrade
Started: $(date -Iseconds)
## Phase Status
- [ ] Phase 0: Orient
- [ ] Phase 1: Git state cleanup
- [ ] Phase 2: Relationship data merge
- [ ] Phase 3: GEDCOM date parser
- [ ] Phase 4: Junk cleanup
- [ ] Phase 5: Tree data (build_family_tree rewrite)
- [ ] Phase 6: Tree frontend (library + wrapper + page)
- [ ] Phase 7: Tree polish (nav, styling, loading)
- [ ] Phase 8: Tests for date parsing + tree data
- [ ] Phase 9: Fix xdist race condition
- [ ] Phase 10: Harness docs (AD, session log, ROADMAP)
- [ ] Phase 11: Integration + deploy verification
## Notes
EOF
```

Save this prompt to the repo:
```bash
cp <this-prompt-file> docs/prompts/session-75-prompt.md
cp <context-file> docs/session_context/session-75-context.md
```

Commit: `docs: session 75 prompt + context + checkpoint [session-75]`

---

## PHASE 1: Git State Cleanup (~5 min)

**Goal:** Clean git status — revert Gemini's key-reordering noise,
keep only real content changes.

1. Run `git status` and `git diff --stat` to see all unstaged changes
2. For data/annotations.json, data/gedcom_matches.json, data/identities.json:
   - Check if diff is ONLY key reordering (alphabetization noise)
   - If yes: `git checkout -- <file>` to revert
   - If real content changes mixed in: extract ONLY real changes,
     revert file, re-apply just the real changes
   - The eval found "5 real identity changes" in 9,000+ lines of noise
3. For docs/HARNESS_DECISIONS.md: keep HD-022 entry (legitimate
   FastHTML + surgical JS decision), revert any other noise
4. Delete any .bak files or Gemini workspace artifacts

Commit: `fix: revert data file key reordering noise, keep real changes [session-75]`

---

## PHASE 2: Relationship Data Merge (~10 min)

**Goal:** Restore 19 UUID relationships that Gemini wiped, merge with
1,000 GEDCOM-xref relationships.

**THIS IS THE MOST CRITICAL PHASE. Get this right.**

1. `git log --oneline -20` to find commit BEFORE Gemini's first commit
2. Extract old relationships:
   ```bash
   git show <pre-gemini-commit>:data/relationships.json > /tmp/old_relationships.json
   ```
3. Count and catalog old relationships (expect ~19 UUID-based)
4. Current relationships.json has ~1,000 GEDCOM-xref entries
5. MERGE:
   - Keep ALL old UUID-based relationships
   - Keep ALL new GEDCOM-xref relationships
   - Deduplicate: same two people connected by UUID AND xref → keep UUID
6. Write merged result to data/relationships.json
7. Print summary:
   ```
   Restored N UUID relationships
   Kept M GEDCOM relationships
   Removed K duplicates
   Total: X relationships
   ```

Commit: `fix: restore UUID relationships, merge with GEDCOM [session-75]`

---

## PHASE 3: GEDCOM Date Parser (~8 min)

**Goal:** Replace ALL `[:4]` date slicing with proper regex parser.

Create in `rhodesli_ml/graph/relationship_graph.py`:

```python
import re

def parse_gedcom_year(date_str: str | None) -> str | None:
    """Extract year from GEDCOM date string.
    Handles: "1887", "21 SEP 1887", "ABT 1900", "AFT 1930",
    "BEF 1920", "BET 1890 AND 1900", None, ""
    """
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    if not date_str:
        return None

    upper = date_str.upper()

    # BET...AND... → range
    bet_match = re.match(r'BET\w*\s+.*?(\d{4}).*AND.*?(\d{4})', upper)
    if bet_match:
        return f"{bet_match.group(1)}–{bet_match.group(2)}"

    # Find any 4-digit year
    year_match = re.search(r'\b(\d{4})\b', date_str)
    if not year_match:
        return None
    year = year_match.group(1)

    # Qualifiers
    if upper.startswith(('ABT', 'ABOUT')):
        return f"~{year}"
    if upper.startswith(('AFT', 'AFTER')):
        return f"aft. {year}"
    if upper.startswith(('BEF', 'BEFORE')):
        return f"bef. {year}"

    return year

def format_lifespan(birth_date: str | None, death_date: str | None) -> str:
    """Format birth/death into display string like '1887–1944'."""
    b = parse_gedcom_year(birth_date)
    d = parse_gedcom_year(death_date)
    if b and d:
        return f"{b}–{d}"
    if b:
        return f"{b}–"
    if d:
        return f"–{d}"
    return ""
```

Then find and replace ALL `[:4]` date slicing in:
- `rhodesli_ml/graph/relationship_graph.py` (build_family_tree)
- `app/main.py` (tree route, if any)
- Any other file: `grep -rn '\[:4\]' --include='*.py' .`

Verify:
```bash
python -c "
from rhodesli_ml.graph.relationship_graph import parse_gedcom_year
tests = [
    ('1887', '1887'), ('21 SEP 1887', '1887'),
    ('ABT 1900', '~1900'), ('AFT 1930', 'aft. 1930'),
    ('BEF 1920', 'bef. 1920'), ('BET 1890 AND 1900', '1890–1900'),
    (None, None), ('', None), ('Unknown', None)
]
for inp, exp in tests:
    result = parse_gedcom_year(inp)
    status = '✓' if result == exp else f'✗ got {result}'
    print(f'  {status} parse_gedcom_year({inp!r}) = {result!r}')
"
```

Commit: `fix: GEDCOM date parser — regex replaces broken [:4] slice [session-75]`

---

## PHASE 4: Junk Cleanup (~3 min)

**Goal:** Remove fake tests, fix broken scripts, delete security risks.

1. Delete `tests/test_tree_rendering.py` (fake Playwright test with
   hardcoded Gemini workspace path)
2. Fix `scripts/rebuild_full_graph.py`:
   - Must load EXISTING data/relationships.json as starting graph
   - Add new relationships ON TOP of existing ones
   - Never pass empty `{"relationships": []}`
3. Delete `check_supabase.py` if it exists (service role key risk)
4. Delete any remaining .bak files

Commit: `fix: remove fake test, fix rebuild script, cleanup [session-75]`

---

## PHASE 5: Rewrite build_family_tree() (~12 min)

**Goal:** Proper flat-array output with bidirectional rels, face crops,
and parsed dates.

Read these FIRST:
- `rhodesli_ml/graph/relationship_graph.py` (current build_family_tree)
- `data/identities.json` (to understand face crop URL field)
- `data/relationships.json` (merged result from Phase 2)

Rewrite `build_family_tree()` to:

1. Build person lookup from identities (UUID → name, dates, face_crop_url)
2. Process ALL relationships bidirectionally:
   - `parent_child` → parent.children includes child, child.parents includes parent
   - `spouse` → both spouses list each other
3. Build flat array in library format:
   ```python
   {
       "id": identity_uuid_or_xref,
       "data": {
           "first name": first,
           "last name": last,
           "gender": gender or "U",
           "birthday": parse_gedcom_year(birth_date) or "",
           "lifespan": format_lifespan(birth_date, death_date),
           "avatar": face_crop_url or ""
       },
       "rels": {
           "spouses": [list],
           "parents": [list, max 2],
           "children": [list]
       }
   }
   ```
4. **CRITICAL for siblings:** Build `parent_to_children` dict, then assign
5. Handle BOTH UUID and GEDCOM-xref identities
6. Use parse_gedcom_year() and format_lifespan() for ALL dates
7. IDs must be unique. All rels must reference existing IDs.

Verify:
```bash
python -c "
import json
from rhodesli_ml.graph.relationship_graph import build_family_tree
identities = json.load(open('data/identities.json'))
relationships = json.load(open('data/relationships.json'))
data = build_family_tree(identities, relationships)
print(f'{len(data)} people in tree')
photos = sum(1 for p in data if p['data'].get('avatar'))
children = sum(1 for p in data if p['rels'].get('children'))
spouses = sum(1 for p in data if p['rels'].get('spouses'))
print(f'{photos} with photos, {children} with children, {spouses} with spouses')
# Check no broken dates
broken = [p for p in data if '21 S' in p['data'].get('birthday','') or 'ABT ' in p['data'].get('birthday','')]
print(f'{len(broken)} broken dates (should be 0)')
# Check siblings
multi = [p for p in data if len(p['rels'].get('children',[])) >= 2]
print(f'{len(multi)} parents with 2+ children (siblings will render)')
"
```

Commit: `feat: build_family_tree rewrite — bidirectional rels, photos, dates [session-75]`

---

## PHASE 6: Tree Frontend (~12 min)

**Goal:** Update family-chart library to latest, clean JS wrapper,
proper page template.

### 6A: Update library
```bash
npm pack family-chart
tar xzf family-chart-*.tgz
# Copy dist file to app/static/js/family-chart.js
# Copy CSS to app/static/css/family-chart.css
```
If npm isn't available or the package doesn't have a dist build,
check the current vendored version — it may be sufficient. The key
is using the CardHtml API, not the old SVG API.

### 6B: Rewrite family-tree.js
```javascript
// family-tree.js — Rhodesli family tree wrapper
document.addEventListener('DOMContentLoaded', async () => {
  const container = document.getElementById('FamilyChart');
  if (!container) return;

  const personId = new URLSearchParams(window.location.search).get('person');
  const url = personId ? `/api/tree-data?person=${personId}` : '/api/tree-data';

  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    if (!data.length) {
      container.innerHTML = '<p style="padding:2rem;text-align:center;">No family tree data available.</p>';
      return;
    }

    const f3Chart = f3.createChart('#FamilyChart', data)
      .setTransitionTime(800);
    const f3Card = f3Chart.setCardHtml()
      .setCardDisplay([["first name","last name"],["lifespan"]]);
    f3Chart.updateTree({initial: true});
  } catch (err) {
    console.error('Family tree error:', err);
    container.innerHTML = `<p style="padding:2rem;text-align:center;color:#c44;">Failed to load: ${err.message}</p>`;
  }
});
```

### 6C: Update /tree route in app/main.py
- Include family-chart.css
- Include D3.js from CDN
- Container: `<div class="f3" id="FamilyChart" style="width:100%;height:80vh;"></div>`
- Remove Gemini's dark-theme SVG overlay CSS
- Remove any inline `<script>` blocks that duplicate the JS wrapper
- Light background to match existing Rhodesli aesthetic

Verify: Start dev server and curl the /tree page, confirm no errors.

Commit: `feat: tree frontend upgrade — CardHtml, photos, clean wrapper [session-75]`

---

## PHASE 7: Tree Polish (~8 min)

**Goal:** Navigation, color coding, loading state.

1. **Person navigation:** If no `?person=` param, show a dropdown or
   default to a well-connected person. After clicking a tree card,
   the library re-centers automatically.
2. **Link to identity page:** Add small link on card → `/people/<uuid>`
3. **Color coding via CSS classes:**
   - Cards with face crops: warm amber/gold border
   - GEDCOM-only (no photos): gray border
4. **Loading state:** Show "Loading family tree..." while API fetches
5. **Breadcrumb:** Tree > [Person Name]
6. **Responsive:** Touch zoom/pan should work (library supports it)

Commit: `feat: tree polish — navigation, color coding, loading [session-75]`

---

## PHASE 8: Tests (~10 min)

**Goal:** Real pytest tests for all new code.

Use subagents if available. Write TWO test files:

### tests/test_gedcom_date_parser.py
- `TestParseGedcomYear`: simple year, day-month-year, month-year,
  ABT, AFT, BEF, BET...AND, None, empty, no year, the exact
  `[:4]` bug regression test ("21 SEP 1887" must NOT produce "21 S")
- `TestFormatLifespan`: both dates, birth only, death only, neither,
  GEDCOM format inputs (should show years only, not "SEP")

### tests/test_family_tree_data.py
- Load real data from data/ files
- `test_returns_list`: non-empty list
- `test_person_has_required_fields`: id, data, rels, first name
- `test_rels_has_valid_structure`: all rels values are lists
- `test_siblings_exist`: at least one parent with 2+ children
- `test_some_people_have_avatars`: at least some with face crop URLs
- `test_no_broken_dates`: no "21 S", "ABT ", "AFT ", "BEF " in any date
- `test_ids_are_unique`: no duplicate IDs
- `test_relationship_ids_reference_existing_people`: all rels point to
  real IDs in the tree

Run `make test-fast` — ALL tests pass including new ones.

Commit: `test: date parser + family tree data tests [session-75]`

---

## PHASE 9: Fix xdist Race Condition (~8 min)

**Goal:** Zero intermittent failures with pytest-xdist.

1. Search: `grep -rn 'routes.pop\|routes.insert' tests/`
2. The pattern: fixtures that temporarily swap routes, causing races
3. Fix with SIMPLEST approach:
   - Option A: `monkeypatch` (pytest manages cleanup)
   - Option B: `@pytest.mark.xdist_group("routes")` for serial group
   - Option C: Test handler functions directly, skip route swapping
4. Verify: `make test` (with xdist) — 0 failures
5. Verify: `make test-fast` (serial) — 0 failures

Commit: `fix: xdist race condition in route-swapping tests [session-75]`

---

## PHASE 10: Harness Documentation (~5 min)

### ALGORITHMIC_DECISIONS.md — Add entries:
- AD-XXX: GEDCOM date parsing — regex vs [:4] slice.
  Accepted: regex. Rejected: slice (breaks day-first formats).
  Source: Session 74 eval.
- AD-XXX: Relationship data merge — UUID + GEDCOM coexistence.
  Accepted: merge both. Rejected: replace (loses identity links).
  Source: Session 74 eval.
- AD-XXX: family-chart CardHtml vs SVG cards.
  Accepted: CardHtml. Rejected: SVG (no photos, harder to style).
  Source: Session 75 implementation.

### docs/session_logs/session-75-log.md
- Phase A: Data integrity (what was restored, counts)
- Phase B: Tree upgrade (what changed, API migration)
- Phase C: Tests + polish
- Final test count
- Lessons learned (reference eval findings)

### docs/ROADMAP.md — Update:
- Mark tree visualization as "done"
- Mark data integrity fix as "done"
- Keep under 150 lines

### SESSION_HISTORY.md — Add session 75 entry

Commit: `docs: session 75 harness docs — AD entries, log, ROADMAP [session-75]`

---

## PHASE 11: Integration + Deploy Verification (~5 min)

### Final local verification:
```bash
# All tests pass
make test-fast
make test  # with xdist — 0 intermittent failures

# Print total count
pytest tests/ --co -q 2>/dev/null | tail -1
```

### Push + deploy:
```bash
git push origin main
sleep 60  # Wait for Railway deploy
```

### Production verification:
```bash
# Tree page loads
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/tree

# API returns valid data
curl -s https://rhodesli.nolanandrewfox.com/api/tree-data | python3 -c "
import sys,json
data=json.load(sys.stdin)
print(f'Production tree: {len(data)} people')
photos = sum(1 for p in data if p['data'].get('avatar'))
siblings = sum(1 for p in data if len(p['rels'].get('children',[])) >= 2)
broken = sum(1 for p in data if '21 S' in p['data'].get('birthday',''))
print(f'{photos} with photos, {siblings} parents with 2+ children, {broken} broken dates')
assert broken == 0, 'BROKEN DATES IN PRODUCTION'
assert photos > 0, 'NO PHOTOS IN PRODUCTION'
"
```

### If Playwright available, screenshot the tree page and verify:
- No "21 S" or broken dates visible
- At least some cards show photos
- Light background (not dark)

### Update checkpoint to COMPLETE:
```bash
cat > docs/session_context/session-75-checkpoint.md << 'EOF'
# Session 75 Checkpoint — COMPLETE
All phases done. Production verified.
EOF
git add -A && git commit -m "docs: session 75 complete [session-75]"
git push origin main
```

### Print final summary:
```
=== Session 75 Complete ===
Phase 1-4: Data integrity restored, junk cleaned
Phase 5-7: Tree upgraded (CardHtml, photos, siblings, modern cards)
Phase 8-9: Tests written, xdist fixed
Phase 10-11: Harness updated, production verified
Total tests: XXXX
Production: https://rhodesli.nolanandrewfox.com/tree
===
```

---

## DO NOT:
- Use /compact between phases (use /clear)
- Skip the checkpoint update between phases
- Skip test runs before commits
- Skip production verification
- Print API keys or secrets
- Add features beyond what's specified
- Touch files unrelated to the tree + data integrity work
- Give up before all phases complete — if stuck, checkpoint and continue

## IF USAGE LIMITS HIT:
1. Immediately commit all current work
2. Push to main
3. Update checkpoint with exactly what's done and what remains
4. Write remaining work to docs/session_context/session-75-remaining.md
5. The next `claude --continue` or `claude -c` picks up from checkpoint
