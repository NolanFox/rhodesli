# Rhodesli Session 47 Planning Context
## Iteration Record — February 18, 2026

This document captures ALL context from the Session 47 planning process,
including research, rejected ideas, and future considerations.

Claude Code should extract actionable items from this file into the 
appropriate harness files (BACKLOG, ALGORITHMIC_DECISIONS, ROADMAP) 
with breadcrumbs pointing back here.

---

## Problem Diagnosis

### Surface Symptoms
1. /estimate returns 404
2. Age estimation not visible in any UI (admin or public)
3. Admin view and public view are completely different apps
4. Version footer shows v0.8.0
5. Landing page doesn't showcase latest features

### Root Cause (Expert's Diagnosis — Adopted)
"You have a state + integration architecture problem. Your ML layer, app 
layer, and UX layer ship independently and there is no enforceable contract 
that guarantees a feature is 'real in production.'"

This manifests as the **Phantom Feature Pattern**: ML pipeline runs 
successfully, data is written to JSON, tests pass, but the app never loads 
the data and no route exposes it.

### Solution: Feature Reality Contract
Added as a rule to the SDD harness. A feature isn't "done" unless:
Data exists → App loads it → Route exposes → UI renders → Test verifies.

---

## Key Architectural Decision: Gatekeeper Pattern

### What It Is
ML outputs are treated as PROPOSALS, not facts. They go through an 
admin review step before entering the canonical identity data and 
becoming visible to the public.

### Why (from Assistant's review)
- Prevents AI hallucinations from going live to family members
- Maintains admin as quality gatekeeper
- Builds trust with community users
- Consistent with existing match proposal → confirm/reject workflow

### Implementation
- ML writes to staging files (e.g., birth_year_estimates.json)
- Admin sees "AI Suggestion" cards on person pages
- Accept → data enters identities.json → visible to public
- Edit & Accept → admin overrides ML with known value (HIGHEST VALUE DATA)
- Reject → recorded, suggestion removed
- Public ONLY sees confirmed/accepted data

### Applies To (Future)
- Birth year estimates (this session)
- Date corrections (future)
- Identity suggestions (future)
- Any other ML-generated metadata

---

## Key Architectural Decision: Confirmed Data → ML Feedback Loop

### The Novel Differentiator
When birth years are confirmed (from any source), they become ground truth 
anchor points that improve future ML estimates. No existing heritage/genealogy 
platform does this.

### How It Works
1. Admin confirms Big Leon's birth year as 1902 (from census records)
2. Big Leon appears in 18 photos with known dates
3. Each appearance becomes a labeled training sample:
   - (face_embedding_from_1935_photo, true_age=33)
   - (face_embedding_from_1950_photo, true_age=48)
4. One confirmed identity → 18 labeled data points
5. Admin corrections (ML said 1907, actual 1902) reveal model bias

### Academic Precedent
- **CACD (Cross-Age Celebrity Dataset)**: Uses celebrity birth years + photo 
  years to create age labels. 163,446 images from 2,000 celebrities.
  Birth year subtracted from photo year = age label.
- **FG-NET**: 1,002 images of 82 people across ages 0-69 with known identities.
  Uses the same person across decades to study aging.
- **Civil War Photo Sleuth** (Virginia Tech, Kurt Luther): Historical face 
  recognition with community contributions. Closest existing precedent to 
  Rhodesli's approach, but no feedback loop from confirmed data back into 
  model improvement.
- **Rhodesli's advantage**: Higher-quality ground truth from genealogical records 
  (Italian census, vital records, GEDCOM data) vs. web-scraped celebrity dates.
  Also: photos span 1900-1990 covering the FULL aging process, not just 10-year 
  windows. And: community-contributed corrections are a novel labeling mechanism.

### Semi-Supervised Learning Approach
- Small labeled set: confirmed identities with known birth years (~32 initially)
- Large unlabeled set: all 662 detected faces
- Anchor points ground the model's predictions (per SSL best practices)
- Active learning can prioritize which unconfirmed faces to present for review
  based on which confirmations would generate the most training data
- Confirmation bias risk: mitigated by human-in-the-loop review (Gatekeeper pattern)

### Research Sources
- Lilian Weng (2021): "Learning with not Enough Data Part 1: Semi-Supervised Learning"
  https://lilianweng.github.io/posts/2021-12-05-semi-supervised/
- Arazo et al. (2019): "Pseudo-Labeling and Confirmation Bias in Deep SSL"
- Practical age estimation using deep label distribution learning (Springer, 2020)
- FamilySearch Compare-a-Face: genealogy + face recognition but NO feedback loop
- RootsTech 2025: Ancestry and FamilySearch AI showcases — all treat AI suggestions
  as "starting points" requiring traditional research verification (same philosophy
  as our Gatekeeper pattern)
- "Guess the Age of Photos" (2025): gamified historical photo age estimation platform,
  interesting UX precedent for community engagement

---

## User Input Taxonomy

### The Framework

| Input Type | Who Can Submit | Approval Required? | Goes Live When? | ML Value |
|-----------|---------------|-------------------|----------------|----------|
| Identity confirmation | Admin only | No | Immediately | High |
| ML suggestion acceptance | Admin only | No | Immediately | High |
| ML suggestion correction | Admin only | No | Immediately | HIGHEST |
| GEDCOM import | Admin only | Per-record review | After review | High |
| Photo upload | Admin (now) | Review for others | After approval | Medium |
| Community annotation | Any user (future) | Admin review | After approval | Medium |
| Community birth date | Any user (future) | Admin review | After approval | High |
| Community story/context | Any user (future) | Admin review | After approval | Low |

### Key Principles
1. Admin actions are immediate — curator's edits are canonical
2. Community contributions persist immediately as "pending" — contributor sees 
   their submission with "Pending review" badge, knows it hasn't been lost
3. All inputs have provenance — who submitted, when, what source
4. Confirmed inputs feed ML — every confirmation generates ground truth
5. The UX funnel: Browse → Identify → Share story → Upload → Import GEDCOM

### Big Leon Test Case
- ML estimate: ~1907 (or whatever pipeline computed)
- Known from records: Born June 28, 1902 in Milas, Mugla, Turkey
- Sources: Italian census of Rhodes (~1903), family records
- The ML-to-actual gap (1907 vs 1902) is a 5-year bias signal

---

## Harness Context Integration Protocol (NEW)

### The Problem
Planning context was being lost in chat windows across Claude, Gemini, 
and ChatGPT. One-off markdown files with no breadcrumbs are not useful.

### The Solution
1. For each session with planning research, create session_NN_planning_context.md
2. Download to ~/Downloads
3. Claude Code moves it to docs/session_context/ in the repo
4. Claude Code extracts actionable items to destination files with breadcrumbs:
   - BACKLOG.md items → "See docs/session_context/..." references
   - ALGORITHMIC_DECISIONS.md → Context: field in each AD entry
   - ROADMAP.md → session status updates
5. The session context file is canonical for "what we researched and why"
6. New .claude/rules/session-context-integration.md codifies this protocol

### Why This Works
- Planning context preserved in codebase (not lost in chat)
- Other harness files stay lean (pointers, not full context)
- Claude Code can trace any BACKLOG item back to full research
- "Rejected alternatives" section prevents re-exploring dead ends

---

## Admin/Public UX — Ideas Explored (Deferred)

### Solutions Considered (most to least invasive)
A. WordPress-Style Admin Bar — familiar but consumes vertical space
B. Unified Layout with Role-Based Rendering — cleanest but biggest effort
C. Contextual Admin Panel (Drawer) — less invasive but admin becomes secondary
D. "View As" Toggle — simplest but still context switching
E. Progressive Admin Enhancement — public view canonical, layer admin on top
F. Curator Mode FAB (Assistant) — clean mode shift but expensive HTMX swap
G. Three-Mode System (Expert) — Explore/Curate/Analyze, most sophisticated

### Decision
- NOT building any UX unification this session
- Design philosophy: Expert's three-mode framing (Explore/Curate/Analyze)
- Implementation: Progressive Enhancement (E) first, evolve to (G)
- Recorded in BACKLOG

---

## ML Roadmap Context

### Established Sequence
1. Date estimation (PyTorch Lightning + MLflow) — DONE
2. Similarity calibration on frozen embeddings — NEXT
3. LoRA fine-tuning (important for portfolio)
4. Active learning and regression gate as core architecture

### NEW: Ground Truth Feedback Loop
Sits alongside step 2. Confirmed birth years become ground truth for:
- Age estimation calibration
- Similarity calibration (confirmed same-person pairs across decades)
- Future LoRA fine-tuning data

### Future Session Ideas (all in BACKLOG)
- Identity Resolution Unlock Metric: "Confirming X resolves N faces"
- Cluster-Level Curation: review clusters not individual faces
- Temporal Consistency Validation: timeline contradictions flag bad merges
- Relationship-Aware Matching: GEDCOM graph boosts match ranking
- Temporal Context Cards: age + Gemini historical context on timeline

---

## Testing & Deployment Context
- App runs on Railway (production)
- Local is for directed testing only when specifically needed
- All verification against production URL
- ML pipeline runs locally on MacBook, syncs via git push

---

## ROADMAP.md Size Fix (Context Window Protection)

### Problem
ROADMAP.md grew to ~40.5k chars, triggering Claude Code's performance 
warning: "⚠ Large ROADMAP.md will impact performance (40.5k chars > 40.0k)"

This is the EXACT same problem we had with SYSTEM_DESIGN_WEB.md (47.6k 
chars, 1373 lines) back in early February. That was split into focused 
sub-files under docs/architecture/ and docs/design/.

### Existing Rule Being Violated
"No file in docs/ should exceed 300 lines — split if growing" (CLAUDE.md)

### Solution (same pattern as before)
Split ROADMAP.md into:
- ROADMAP.md (lean, ~150 lines): current status, active session, next 
  priorities, pointers to detail files
- docs/roadmap/SESSION_HISTORY.md: all completed session logs (1-46)
- docs/roadmap/FEATURE_STATUS.md: detailed feature completion matrix
- docs/roadmap/ML_ROADMAP.md: ML pipeline status and plans

### Why ROADMAP.md Specifically
Claude Code reads ROADMAP.md at session start. A 40k char file means 
~10k tokens consumed before any work begins. The lean version (~6k chars) 
saves ~8k tokens per session while still giving Claude the navigation 
it needs. Details are available on-demand via the sub-files.

### Precedent
SYSTEM_DESIGN_WEB.md split (Feb 2026): 47.6k → deleted monolith, 
created docs/architecture/OVERVIEW.md, DATA_MODEL.md, PERMISSIONS.md, 
PHOTO_STORAGE.md + docs/design/FUTURE_COMMUNITY.md. All under 300 lines.

---

## What Was Rejected and Why

| Idea | Source | Why Rejected |
|------|--------|-------------|
| YAML feature registry | Expert | Too heavy; concept adopted as lighter SDD rule |
| File locking/checksums | Assistant | Solving wrong problem (git push, not races) |
| Standalone /estimate route | Original | Age data integrated into existing views |
| FAB for curator mode | Assistant | Full-page swap expensive; doesn't handle inbox |
| Live archive landing page | Expert | Premature without stable features |
| Three-mode toggle NOW | Expert | Ambitious; adopt as philosophy, build later |
| Direct ML → UI pipe | Original | Gatekeeper pattern is safer |
| Admin bar NOW | Original | Defer to UX unification session |
| LoRA deprioritized | Expert | Important for portfolio; keep in sequence |

---

## Critical Review of External Advisors

### Assistant: Strengths & Weaknesses
+ Gatekeeper/Staging pattern (adopted as core architecture)
+ Temporal Context Cards (deferred, high value)
+ Data safety emphasis
- JSON concurrency critique misdiagnosed risk (it's git push, not races)
- FAB implementation too thin
- Prompt didn't follow SDD methodology

### Expert: Strengths & Weaknesses
+ Executive diagnosis (state + integration architecture problem)
+ Feature Reality Contract (adopted as SDD rule)
+ Three-mode cognitive framing (adopted as design philosophy)
+ Identity Unlock Metric (high value, recorded for future)
- Over-indexes on architecture, under-delivers on execution
- YAML registry adds maintenance burden vs. lighter SDD rule
- Three-mode system too ambitious for immediate build
- Dismissed LoRA too aggressively (important for portfolio)
- Live archive landing page premature
