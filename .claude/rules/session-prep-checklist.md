# Session Prep Checklist — Mandatory Before Writing a Prompt

Triggers: When creating a new session prompt file (docs/prompts/session-*-prompt.md).

## Before writing ANY session prompt, ALL of these must exist:

### 1. Context File (MANDATORY)
- Location: `docs/session_context/session-{N}-context.md`
- Must include:
  - Predecessor link (verified to exist)
  - All research findings from planning discussion
  - Cross-community / cross-feature implications
  - Known gaps and weaknesses to watch for
  - Pipeline analysis (what's automated vs manual)
  - Breadcrumbs to all related docs (PRDs, ADs, BACKLOG items)

### 2. Algorithmic Decision Entries
- If the session involves ML, data pipelines, or architectural decisions:
  - Add AD-NNN entries to `docs/ml/ALGORITHMIC_DECISIONS.md`
  - Each AD must have: Date, Session, Context, Decision, Rationale, Gap/Risk
  - Link back to context file

### 3. ROADMAP Work Items
- Every deliverable in the prompt must have a corresponding ROADMAP line item
- Use task IDs (PRD037-001, COMMUNITY-003, etc.) for traceability

### 4. BACKLOG Updates
- New work items discovered during planning → BACKLOG with source breadcrumb
- Existing items affected → update status and add session reference

### 5. PRD (if applicable)
- Features >30 min need a PRD in `docs/prds/`
- PRD must exist BEFORE the prompt references it

## Why This Exists
Session 96: Prompt was written without context file, without AD entries, and without
ROADMAP items. User had to ask 3 times for proper documentation. Research from
planning discussion (cross-community matching mechanics, pipeline analysis, GEDCOM-first
workflow rationale) was only in conversation context, not persisted.

The prompt is the last artifact, not the first. Research → decisions → context → prompt.
