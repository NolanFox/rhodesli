# Session 69 Planning Context
# "Dogfooding Critical Fixes + Design Audit + Notification System + Parallelization Skill"

## Source: Dogfooding session Feb 25, 2026 + Claude research conversation
## Predecessor: Session 68 (v0.73.1 — hook hardening, LoRA audit, UX-103)
## Breadcrumbs: Session 68 assessment → dogfooding → this context → Session 69 prompt

---

## 1. DOGFOODING FINDINGS (2026-02-25)

Nolan spent 5 minutes using production (rhodesli.nolanandrewfox.com) and found
critical failures in the core user loop. The fundamental cycle of Rhodesli is:

```
AI proposes identity → Human reviews → Human corrects/confirms → 
Ground truth grows → ML improves → Better proposals
```

This cycle is currently broken at multiple points.

### BUG-1: "Create New Identity" Does Nothing [P0]

**Repro:** Photo Context modal → type name in search box → autocomplete works 
(found "Sol Sedikaro" as existing match) → click "+ Create Sol Menashe" → 
NOTHING HAPPENS. No error, no network request, no feedback.

**Context:** The photo was Rica Amato (1936) with caption identifying "grandson Sol, 
and his parents Natanel & Rachel Amato Menashe." From Nolan's Ancestry tree, this 
is Salomon Menashe (1936-2019), son of Netanel and Rachele. The user had the 
correct answer and could not enter it.

**Impact:** Cannot create new identities. Consensus feedback loop dead. LoRA 
training data ceiling locked at 221 pairs (from Session 68 audit).

**Diagnosis approach:** Check browser console for JS errors on click. Trace the 
click handler in the Photo Context modal code. Likely candidates:
- Dead event listener (handler attached to wrong element or not at all)
- Failed POST that silently swallows error (no .catch() or try/catch)
- Missing API route (route exists for search but not for create)
- The dropdown renders and autocomplete works, so data fetching is fine — 
  it's specifically the "Create" action that's broken

**Test gap:** No integration test covers "create new identity from photo context 
modal." The test suite has 3064 tests but missed this critical path.

### BUG-2: New Faces Are Not Clustering [P0]

**Repro:** New Matches → browse. Faces appear as "Unidentified Person 768" etc.
with no cluster assignment. The "Similar Identities" panel shows matches 
(Big Leon Capeluto at Dist: 0.91 "High", Nace Capeluto at Dist: 1.01 "High"),
so embeddings and matching pipeline work. But faces aren't auto-assigned.

**Key architectural question:** Is this the Gatekeeper pattern working as designed?

The Gatekeeper pattern (AD entries, multiple sessions) says: ML outputs are staged 
as proposals that require admin approval before going public. If clustering is 
intentionally not auto-assigning, then:
- The UX needs to make this clear (show "Proposed match: Big Leon Capeluto" 
  with a Confirm button, not just a generic "Similar Identities" section)
- The review flow should make confirmation ONE CLICK, not require navigating 
  to a different view

If clustering is supposed to auto-assign but isn't:
- The clustering job may have been lost during Supabase migration
- Or it was never connected to the post-upload pipeline for web uploads
  (it may only work for batch CLI processing)

**Related:** The Leon/Nace Capeluto newspaper photo (leon_and_nace_capeluto_kiddyland.jpeg)
shows 2 faces detected, both correctly matched to existing identities, but neither
auto-clustered. The newspaper literally says "LEON CAPELUTO" and "NACE CAPELUTO" 
under the photos, and the OCR/Gemini should have caught this.

### BUG-3: Collection Dropdown Missing Options [P1]

**Repro:** Photo detail page → Collection dropdown → only shows "Uncategorized."
The upload flow has a proper collection picker with all existing collections.
Same data, different UI, inconsistent behavior.

**Fix approach:** Find the collection dropdown component on the photo detail page.
Wire it to the same data source as the upload flow's collection picker. This is
likely a missing API call or a component that was built with a static list instead
of a dynamic query.

### DESIGN-1: Face Card Layout + Site-Wide Design Audit [P2 → NOW P1 VIA PARALLELIZATION]

**Observation:** Single-photo face cards waste enormous space. But this is 
symptomatic of broader design debt across the site.

**Design direction for Rhodesli** (established in earlier sessions):
- "Editorial archival" aesthetic — warm, respectful of historical content
- Museum exhibition catalog feel, NOT dashboard/admin panel
- Serif display fonts for headings, refined body font
- Warm tones, parchment/cream accents, subtle shadows evoking physical photographs
- Confidence visualization as a differentiator (no other genealogy tool shows this)
- "Photo Detective" framing — AI analysis should feel like watching a detective work

**Approach:** This is a PARALLELIZABLE task. A dedicated subagent in its own 
worktree should:
1. Read /mnt/skills/public/frontend-design/SKILL.md for design principles
2. Audit the current site against those principles
3. Focus especially on: face cards, photo detail page, browse/review views
4. Propose concrete CSS/layout improvements with the archival aesthetic direction
5. Implement improvements that don't touch the same files as bug fix subagents

**Reference from past research (Session ~27 conversation):** The Anthropic frontend-design 
skill works best when loaded in a focused context with a clear aesthetic brief. 
NOT the "5 agent divergent design" pattern from the Goldbach Reel. One focused 
agent with clear direction produces better results than many unfocused ones.

---

## 2. NEW FEATURE: HIGH-CONFIDENCE MATCH NOTIFICATIONS

This emerged from dogfooding and connects to earlier community engagement research.

**Problem:** When a new face is uploaded and matches a confirmed, named, 
GEDCOM-linked identity at high confidence, NOBODY IS TOLD. The match silently 
appears in the Similar Identities panel and waits for someone to browse to it.

**For the core app goals:**
- "Usable by others" — community members need to know when their contributions 
  lead to discoveries
- "Community adoption" — people contribute more when they see results
- "Portfolio piece" — a notification system shows production-grade ML deployment

**Proposed implementation (scope for session 69 — minimal viable):**
1. When a face is processed and has a HIGH confidence match (Dist < 1.0) to a 
   CONFIRMED identity, flag it as a "discovery"
2. Show discoveries in a prominent location:
   - Badge on sidebar: "🔔 3 New Discoveries" (distinct from "New Matches")
   - A dedicated "Discoveries" view showing: the new face, the confirmed match, 
     the confidence score, and ONE-CLICK confirm/reject
3. Future (not session 69): Email notifications, activity feed for community

**This directly addresses the UX gap from BUG-2:** Instead of faces silently 
landing as "Unidentified Person 768," high-confidence matches are surfaced 
proactively. Lower-confidence matches stay in the existing review queue.

**Architectural note:** This is the Gatekeeper pattern done RIGHT — proposals 
are surfaced prominently with enough context for quick human verification, 
not buried in a generic list.

---

## 3. DESIGN DECISIONS FILE

The project has three decision logs:
- ALGORITHMIC_DECISIONS.md (AD-NNN) — ML and algorithm decisions
- HARNESS_DECISIONS.md (HD-NNN) — workflow, tooling, session engineering
- OPS_DECISIONS.md (OD-NNN) — deployment, infrastructure

Design decisions currently have NO dedicated log. They're scattered across PRDs, 
session logs, and conversation transcripts. Session 69 should create:

- `docs/DESIGN_DECISIONS.md` (DD-NNN) — UX, visual design, information architecture
- Same provenance pattern: what was decided, alternatives considered, why, breadcrumbs
- CLAUDE.md key docs table updated to include DD file
- First entries: DD-001 (archival aesthetic direction), DD-002 (face card layout), 
  DD-003 (discovery notification UX)

---

## 4. PARALLELIZATION ARCHITECTURE FOR SESSION 69

Session 68 successfully ran 3 parallel worktree subagents. Session 69 should do the same,
with this dependency map:

```
Phase 0: Orient (main) — sequential, sets up everything
Phase 1: Bug fixes (main) — sequential, touches app/main.py
  └── BUG-1: Create Identity fix
  └── BUG-2: Clustering pipeline diagnosis + fix
  └── BUG-3: Collection dropdown fix

PARALLEL after Phase 1 merges:
  ├── Subagent A (worktree: design-audit)
  │   Context: frontend-design SKILL.md + archival aesthetic brief
  │   Task: Face card redesign, site-wide CSS audit, DD entries
  │   Files: app/static/css/*, app/templates/* (no Python)
  │
  ├── Subagent B (worktree: notifications)
  │   Context: Gatekeeper pattern docs, community engagement research
  │   Task: Discovery notification system (badge + view + one-click confirm)
  │   Files: app/notifications.py (new), app/main.py routes (coordinate with main)
  │
  └── Subagent C (worktree: harness-improvements)
      Context: HARNESS_DECISIONS.md, session 68 assessment
      Task: Regression suite trimming, DESIGN_DECISIONS.md creation,
            Gemini content safety case study doc, parallelization skill draft
      Files: docs/*, .claude/* (no app code)

Phase N: Merge all worktrees → full test suite → deploy → verify
```

**Coordination rule:** Subagent B touches app/main.py for routes. BUG fixes in 
Phase 1 also touch app/main.py. Therefore Phase 1 MUST complete and merge before 
Subagent B starts. Subagents A and C can start immediately after Phase 0 if their 
work is truly independent of app/main.py.

Actually, safer: run all bug fixes first (they're the P0s), THEN parallelize 
the enhancement work. This avoids merge conflicts on app/main.py.

---

## 5. PROMPT PARALLELIZATION SKILL

From past conversations (Session 48 research, HD-001), we identified that no 
existing tool auto-decomposes a prompt into parallel vs sequential phases. 
The concept:

**What it does:**
1. Receives a multi-phase prompt
2. Analyzes which phases are independent (no shared file dependencies)
3. Groups into: sequential (must run in order) vs parallel (can use worktrees)
4. Outputs a parallelization plan with dependency graph
5. Optionally: auto-generates subagent context files for each parallel track

**Implementation approach:**
- A Claude Code skill at `.claude/skills/prompt-parallelizer/SKILL.md`
- Triggered by: prompts with 3+ phases, or explicit "parallelize" request
- Could also be a hook (UserPromptSubmit) that analyzes incoming prompts
- For session 69: CREATE the skill draft + test with the session 69 prompt itself
- Full integration with hooks: future session

**This is a portfolio piece:** "I built an auto-parallelization system for 
multi-phase development sessions" is a strong interview talking point.

---

## 6. CARRYOVER FROM SESSION 68 ASSESSMENT

### Must verify:
- Railway deploy status (webhook may not have fired for session 68 commits)
- UX-103 changes from session 68 visible in production
- LoRA readiness after Nolan reviews 3 candidate identities (Vida, Big Leon, Victor)

### Must address:
- run_session.sh manual test (deferred since Session 67 — Nolan does pre-session)
- Gemini content safety filter documentation (2 photos permanently blocked)
- Regression suite: trim from 15-item checklist to 5-item smoke test

### ML roadmap position:
- Date estimation: COMPLETE
- Similarity calibration: NEXT (after UX bugs are resolved and LoRA data is assessed)
- LoRA fine-tuning: AFTER similarity calibration
- Confirmed birth years = ground truth anchors
- Active learning + regression gate = core architecture

---

## 7. FUNDAMENTAL GOALS REMINDER

### App Goals (from Nolan, carried across all sessions)
1. **Usable by others** — not just Nolan, real community members
2. **Expandable** — beyond Rhodes, platform for heritage archives
3. **Community adoption** — people actually contribute and return
4. **Portfolio piece** — demonstrates ML/MLOps maturity for job search

### Current state vs goals:
- Goal 1 FAILING: Core user loop is broken (BUG-1, BUG-2)
- Goal 2 OK: Architecture is generalizable
- Goal 3 BLOCKED: Can't adopt what doesn't work; no notifications for discoveries
- Goal 4 STRONG: Test suite, harness, decision logs, parallelization all demonstrate maturity

Session 69's primary purpose is to unblock Goals 1 and 3.

---

## 8. TECHNICAL REFERENCES

- Frontend design skill: /mnt/skills/public/frontend-design/SKILL.md
- Skill creator: /mnt/skills/examples/skill-creator/SKILL.md
- 7 subagents confirmed in .claude/agents/: ux-reviewer, session-evaluator, 
  fix-prompt-writer, design-check, parallel-optimizer, merge-resolver, enrichment-worker
- parallel-optimizer subagent: review its current capabilities vs what we need
- Health endpoint: /health (not /api/health)
- Deploy: via git push (not Railway dashboard) — but verify webhook is working first
