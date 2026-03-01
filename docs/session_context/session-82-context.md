# Session 82 Context: Multi-Tool Parallel Development

Save to: `docs/session_context/session-82-context.md`

## Session Overview

Session 82 runs THREE parallel tracks across THREE different tools:
- **82a** — Antigravity: UX Comprehensive Audit + Ideation
- **82b** — Codex: Face Cards Bug Fix + Sharing Consistency
- **82c** — Claude Code: Gemini Re-run with GEDCOM Enrichment

Claude Code handles merging all PRs after review.

---

## Tool Assignments & Rationale

| Track | Tool | Why This Tool |
|-------|------|---------------|
| 82a UX Audit | Antigravity | Browser agent can navigate live app, screenshot broken UX, visually verify. Nano Banana generates mockups of proposals before code. Planning Mode produces artifact deliverables. |
| 82b Face Cards | Codex | Parallel threads for isolated bug fixes. 30-min async sandbox grinding. Worktree-by-default. Good for mechanical multi-bug sessions. |
| 82c Gemini | Claude Code | Deep reasoning for ML pipeline work. Best for complex prompt engineering + GEDCOM integration + cost analysis. |

---

## Nano Banana Research Summary

**What it is:** Nano Banana Pro (Gemini 3 Pro Image) is Google's image generation model, natively integrated into Antigravity IDE. Agents can generate images on-demand during development workflows.

**Best use for Rhodesli 82a:**
- Generate high-fidelity UI mockups of proposed UX changes BEFORE writing code
- Create before/after comparison images for stakeholder review
- Produce device mockup screenshots (mobile, tablet, desktop) of proposed layouts
- Generate visual proposals for face card redesign, sharing UX, navigation improvements

**How to invoke in Antigravity:**
- In Planning Mode, ask the agent: "Generate a mockup image showing [proposed UI change]"
- The agent will call Nano Banana Pro and produce the image as an Artifact
- Iterate on the mockup with feedback comments before implementing
- Save approved mockups to `docs/session_context/82a-mockups/` for reference

**Limitations:**
- Service can be overloaded (agent falls back to HTML mockup — also useful)
- Free tier has daily generation limits (2-3 per day reported)
- Best for layout/composition mockups, not pixel-perfect designs

---

## Antigravity Research Methodology

**Antigravity's browser agent is the key differentiator for UX work:**

1. **Live App Navigation:** Agent can launch Chrome, navigate to `https://rhodesli.nolanandrewfox.com/`, click through every page, and screenshot what it sees
2. **Competitor Research:** Agent can browse competitor genealogy tools (MyHeritage, Ancestry, FamilySearch) and screenshot their UX patterns for comparison
3. **Visual Bug Detection:** Agent can load each page, screenshot, and identify visual issues that text-based tools miss
4. **Before/After Verification:** After making changes, agent re-screenshots to verify visual improvement

**Research workflow for 82a:**
- Phase 1: Agent browses live Rhodesli app → screenshots every page/flow → catalogs issues
- Phase 2: Agent browses 3-5 competitor sites → screenshots relevant UX patterns
- Phase 3: Agent generates Nano Banana mockups of Top 5 proposals
- Phase 4: All research compiled into Artifact deliverables for review

**Browser setup:** Install Antigravity Chrome extension. Agent can then interact with pages (click, scroll, fill forms). For admin pages, provide session cookie or have agent log in.

---

## Face Cards: Complete Bug Catalog

### Bug 1: Find Similar Is Broken
- **Where:** Face cards on People page, Identity cards in admin
- **Behavior:** Clicking "Find Similar" either does nothing, goes to a broken link, or only works for the first image
- **Expected:** In admin mode, Find Similar should open an inline animated panel that rearranges the other face cards around the similar results — NOT navigate to a new page
- **Public mode:** Fine to have its own dedicated page for Find Similar results

### Bug 2: Face Cards Went Large and Vertical (Regression)
- **Previous state:** Face cards were compact, horizontal, with sharing, find similar, and other actions accessible
- **Current state:** Face cards are oversized, vertical, with excessive whitespace and tiny cropped face photos
- **Lost functionality:** Sharing buttons, working Find Similar, quick actions
- **Required:** Return to the horizontal layout with larger face photos, less whitespace, and ALL previous functionality restored

### Bug 3: Sharing Inconsistency
- **People tab:** Sharing works ✓
- **Find Similar:** Sharing lost ✗
- **Face cards in other sections:** Inconsistent ✗
- **Required:** ALL face cards in admin mode should have identical functionality regardless of which section they appear in. Public-facing can be a simplified version.

### Bug 4: Find Similar Animation (Admin Mode)
- **Expected behavior:** Clicking Find Similar on a face card should:
  1. Animate/expand an inline panel
  2. Rearrange surrounding face cards to make room
  3. Show similar faces with confidence scores
  4. Allow merge/dismiss actions from the inline view
  5. NOT navigate to a new URL
- **Public sharing site:** OK to have a separate page with its own URL for sharing Find Similar results

### Bug 5: Photos/Faces Toggle Performance
- **Where:** Public person page (e.g., `/person/{id}`)
- **Behavior:** Switching between Photos and Faces tabs is extremely slow
- **Required:** Investigate and fix — likely needs lazy loading, pagination, or pre-rendering

### Historical Reference
Look at git history for the face card implementation BEFORE the vertical redesign. Identify the commit that changed them and understand what functionality was present. Command: `git log --oneline --all -- app/main.py | head -50` and diff the relevant commits.

---

## Gemini Re-run: Asheville Litmus Test

### The Problem
Photo of Victoria Capuano Capeluto with 3 of her 4 children — taken in Asheville, NC — is currently showing as Brooklyn on the map. This is because:
1. Victoria lived in Brooklyn for most of her life (GEDCOM data)
2. Without contextual clues, Gemini defaults to the most common location
3. With GEDCOM enrichment + photo analysis, Gemini should be able to infer Asheville

### The Experiment (3 variants)
1. **No GEDCOM context** — Send photo to Gemini with no family data. Expected: generic guess (Brooklyn or unknown)
2. **Full GEDCOM context** — Send photo + all GEDCOM events for Victoria and her children (births, residences, marriages). Expected: may pick up Asheville connection
3. **Curated GEDCOM context** — Pre-process to only include location/time events within ±15 years of estimated photo date. Filter to first-order connections. Expected: best signal-to-noise ratio

### Previous Gemini Conversation Reference
Nolan previously had success with a similar workflow for his great-grandfather Albert Fox — feeding in all known residences (Minsk, New York, Detroit, Ohio) with birthdates, and Gemini identified a specific building. This is the quality bar we're trying to approximate.

### Budget Gates
- $3 checkpoint after Asheville experiment
- $10 hard cap for full session
- Use sync pipeline (NOT Batch API — too slow based on 64d findings)
- Track cost per photo after each API call

### Gatekeeper Pattern
All Gemini outputs are PROPOSALS. Admin reviews and accepts/rejects/corrects before public display. Confirmed corrections feed back as ML ground truth anchors.

---

## ML Pipeline Next Steps (Post-82)

**Priority order (confirmed):**
1. ✅ Date estimation (CORAL) — Done
2. **Similarity calibration** — Next. 60 confirmed identities + ~775 total. Learn actual same-person vs different-person distance distributions. Set thresholds that maximize precision at desired recall.
3. **Active learning on review queue** — Rank 398 items by expected information value, not arbitrary order.
4. **CORAL date correction layer** — Use confirmed birth years as ground truth anchors to adjust estimates.
5. **LoRA fine-tuning** — Long-term. Need ~200+ confirmed identity pairs. Historical B&W photos of closely-related ethnic community ≠ modern training data.

---

## Harness Rules (Apply to ALL tracks)

- Read `CLAUDE.md` first, then ALL files in `.claude/rules/`
- `pytest tests/ -x -q` before EVERY commit
- Update `ALGORITHMIC_DECISIONS.md` for any design decision
- Update `SESSION_HISTORY.md` when trimming ROADMAP
- Deploy via git push (not Railway dashboard)
- Use `/clear` (not `/compact`) between phases
- Commit after EVERY completed item
- ALL tests must be non-destructive (see `.claude/rules/data-safety.md`)
- NO data mutations without backup-before-write
- Validate UUIDs before any database operation

---

## Architecture Reminders

- **Frontend:** FastHTML (Python, server-rendered) + HTMX
- **Backend:** FastHTML + Starlette
- **ML:** InsightFace (face detection/embeddings), PyTorch (CORAL date estimation)
- **Database:** Supabase (user data, identities) + JSON files (ML-generated data)
- **Storage:** Cloudflare R2
- **Hosting:** Railway
- **Auth:** Supabase auth
- **Gatekeeper Pattern:** ML outputs staged as proposals → admin accepts/rejects → confirmed data = ground truth
