# Session 75 Context: Post-Gemini Cleanup + Tree Upgrade

## Session Identity
- **Previous session:** 74 (Gemini/Antigravity 5-mission UX overhaul)
- **Eval:** docs/assessments/session-74-eval.md (Claude Code audit)
- **Type:** Remediation + upgrade (fix Gemini damage, then improve)
- **Naming:** session-75a through 75c phases

---

## 1. WHAT SESSION 74 (GEMINI) BROKE

### Critical Bug: Date Parser
The `build_family_tree()` function uses `[:4]` to extract years.
This catastrophically fails on GEDCOM date formats:
- `"1887"` → `"1887"` ✓
- `"21 SEP 1887"` → `"21 S"` ✗ (THE BUG)
- `"ABT 1900"` → `"ABT "` ✗
- `"AFT 1930"` → `"AFT "` ✗
- `"BEF 1920"` → `"BEF "` ✗
- `"BET 1890 AND 1900"` → `"BET "` ✗

**Fix:** Regex extraction: `re.search(r'\b(\d{4})\b', date_str)`

### Critical Bug: Relationship Data Wipe
Gemini replaced 19 existing UUID-based relationships (connecting
real photo identities to family structure) with ~1,000 GEDCOM-xref
relationships. The UUID ones are MORE AUTHORITATIVE because they
link actual photos to people.

**Fix:** Merge both sets. Keep UUID when duplicated.

### Data File Noise
Gemini alphabetized keys in identities.json, annotations.json, and
gedcom_matches.json — creating 9,000+ lines of diff noise with only
~5 real content changes mixed in. Must separate real from noise.

### Fake Test
`tests/test_tree_rendering.py` is a standalone Playwright script
with a hardcoded path to Gemini's workspace. Not pytest-compatible.
Delete it.

### rebuild_full_graph.py Bug
Passes empty `{"relationships": []}` instead of loading existing
relationships. This would wipe all relationship data on rebuild.

### Dark Theme Overlay
Gemini added dark SVG overlay CSS that hides the family-chart
library's built-in card features.

### Missing Bidirectional Relationships
`build_family_tree()` only builds parent→child edges downward.
Never populates `rels.children` arrays, so siblings don't render.

### Missing Face Crop URLs
Tree cards show gray silhouettes because avatar URLs aren't being
populated from identity face crop data.

---

## 2. FAMILY-CHART LIBRARY API REFERENCE

Library: donatso/family-chart (MIT, D3-based)
Docs: https://donatso.github.io/family-chart/

### Three Core Classes
1. `f3Chart` = `f3.createChart('#FamilyChart', data)` — main chart
2. `f3Card` = `f3Chart.setCardHtml()` — HTML card renderer
3. `f3EditTree` = `f3Chart.editTree()` — edit (not needed)

### Data Format (flat array of person objects)
```json
{
  "id": "uuid-or-xref",
  "data": {
    "first name": "Leon",
    "last name": "Capeluto",
    "birthday": "1887",
    "avatar": "https://r2-url/face-crops/leon.jpg",
    "gender": "M",
    "lifespan": "1887–1944"
  },
  "rels": {
    "spouses": ["spouse-id"],
    "children": ["child1-id", "child2-id"],
    "parents": ["father-id", "mother-id"]
  }
}
```

### Siblings Render Automatically
When parent P has `rels.children: ["A", "B"]`, A and B render as
siblings. This is the key fix — populate children arrays.

### Card Setup (CardHtml API)
```javascript
const f3Chart = f3.createChart('#FamilyChart', data)
  .setTransitionTime(800);
const f3Card = f3Chart.setCardHtml()
  .setCardDisplay([["first name","last name"],["lifespan"]]);
f3Chart.updateTree({initial: true});
```

### Avatar Rendering
CardHtml renders `data.avatar` as a circular photo automatically.

---

## 3. ARCHITECTURE REMINDERS

- **Stack:** FastHTML + HTMX + vanilla JS (surgical). NOT React.
- **Deploy:** git push → Railway auto-deploy
- **Storage:** Cloudflare R2 for images, Supabase for structured data
- **ML:** InsightFace for face detection, PyTorch CORAL for dates
- **Gatekeeper pattern:** ML outputs staged as proposals, admin
  accepts/rejects before going public
- **Face crops:** Stored in R2, URLs accessible via identity data

---

## 4. HARNESS RULES (NON-NEGOTIABLE)

- **ALGORITHMIC_DECISIONS.md** must be updated for every ML/data decision
- **Commit after every phase** with descriptive messages
- **Use /clear (NOT /compact) between phases** — re-read from disk
- **No docs file >300 lines**, ROADMAP.md <150 lines
- **Session context files** go to docs/session_context/
- **Tests before every commit**: `make test-fast` or `pytest tests/ -x -q`
- **Deploy verification**: curl production after push

---

## 5. KNOWN DATA INVENTORY

- 271 photos in archive
- 46 confirmed identities with face crops
- ~19 UUID-based relationships (pre-Gemini, authoritative)
- ~1,000 GEDCOM-xref relationships (Gemini-added, structural)
- Confirmed birth years serve as ML ground truth anchors
- Production URL: https://rhodesli.nolanandrewfox.com

---

## 6. xdist RACE CONDITION (from Session 74 eval)

9 intermittent test failures with pytest-xdist (parallel).
Root cause: `app.routes.pop()` / `app.routes.insert()` in test
fixtures modify a shared mutable list. When parallel tests race
on the same list, they corrupt each other.

Fix options:
- `monkeypatch` instead of direct mutation
- `@pytest.mark.xdist_group("routes")` for serial execution
- Refactor to test handler functions directly

---

## 7. PERSISTENCE RESEARCH (Feb 2026)

### Ralph Wiggum Plugin (Official Anthropic)
- Stop hook blocks exit, re-feeds prompt until completion
- Checklist-based: agent checks off items, loop continues if unchecked
- Works within same session (context continuity)

### Task System (Native Claude Code, Jan 2026)
- `TaskCreate` with dependencies and blockers
- Tasks persist across context compactions
- Status: pending → in_progress → completed
- Ctrl+T to toggle task list visibility

### Best Pattern for Rhodesli
- Write checklist to disk: `SESSION_CHECKPOINT.md`
- After each phase: update checklist, commit, /clear
- Re-read checklist + context file at start of each phase
- If usage limits hit: commit + push + write remaining work to file
- Ralph Wiggum for autonomous overnight runs

### Anti-Patterns (Learned From Past Sessions)
- /compact is LOSSY — never use between phases
- Large phases (>15 min) exhaust context before completing
- Phases that touch many files risk merge conflicts
- Missing verification gates = work that "looks done" but isn't
- Not committing between phases = lost work on crash
