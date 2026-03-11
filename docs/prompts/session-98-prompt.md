# Session 98 — GEDCOM Mirror And Non-Destructive Import Hardening

**Context:** `docs/session_context/session-98-context.md`
**Worktree:** `/private/tmp/rhodesli-session-98-gedcom`
**Primary constraint:** preserve everything, mutate nothing destructively

## Goal

Turn GEDCOM handling into a mirror-quality, audit-first pipeline:
- full record preservation
- version-to-version diffing
- reversible apply path
- richer app UX
- Session 97 lineage compatibility

## Non-Negotiables

1. Session 97 stays Session 97.
2. Session 96 work on `main` is off-limits.
3. No destructive GEDCOM import behavior.
4. Any apply flow must be backed by checked-in backup and diff artifacts.
5. Claude auditability is a first-class requirement.
6. Any touched AI/ML path must stay compatible with Session 97 prompt and
   state lineage requirements.

## Acts

### Act 0 — Orient And Breadcrumb
- create Session 98 artifacts
- record worktree, numbering decision, constraints

### Act 1 — Raw GEDCOM Audit
- inspect actual February and March GEDCOM exports
- enumerate record/tag coverage and parser drop zones
- produce a version diff inventory

### Act 2 — Parser And Schema Hardening
- preserve full raw record text and structured tree payloads
- extract richer names, facts, notes, citations, media refs, and family events
- design non-destructive versioned storage with redirect/rekey support

### Act 3 — Preview/Diff UX
- improve GEDCOM admin preview so changes are inspectable before apply
- surface rich person/family detail instead of only summary counts

### Act 4 — Lineage And Verification
- document how GEDCOM writes align with Session 97 lineage rules
- add tests for merge/rekey, relationship edits, preferred fact changes, and
  deleted facts
- write Session 98 assessment

## Deliverables

1. Parser/import code
2. Schema migration SQL
3. Tests
4. Session log
5. Assessment
6. Backup/diff artifacts or dry-run proof when no live mutation occurs
