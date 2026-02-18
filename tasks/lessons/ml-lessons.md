# ML & Algorithm Lessons

Lessons about ML decisions, clustering, embeddings, and decision provenance.
See also: `docs/ml/ALGORITHMIC_DECISIONS.md`, `.claude/rules/ml-pipeline.md`

---

### Lesson 27: Algorithmic decisions need a structured decision log
- **Mistake**: Proposed centroid averaging when multi-anchor was the correct approach. No record existed of past algorithmic decisions or why alternatives were rejected.
- **Rule**: All ML/algorithmic decisions must be recorded in `docs/ml/ALGORITHMIC_DECISIONS.md` with AD-XXX format: context, decision, rejected alternative, why rejected, affected files.
- **Prevention**: Path-scoped rules (`.claude/rules/ml-pipeline.md`) auto-load this requirement when touching ML files.

### Lesson 28: Use path-scoped rules for domain-specific context
- **Observation**: ML rules should load when touching `core/neighbors.py`, but not when working on auth or landing page. Path-scoped rules in `.claude/rules/` achieve this with zero token cost for unrelated work.
- **Rule**: When a set of rules only applies to specific files/directories, use `.claude/rules/` with YAML frontmatter `paths:` instead of adding to CLAUDE.md.
- **Prevention**: Before adding rules to CLAUDE.md, ask: "Does this apply to ALL files, or just a subset?" If subset, use path-scoped rules.

### Lesson 30: Path-scoped rules can include future planning awareness
- **Observation**: `.claude/rules/planning-awareness.md` triggers when touching `app/main.py` or `core/*.py`, reminding about upcoming Postgres migration and contributor roles.
- **Rule**: Path-scoped rules aren't just for restrictions — they can include "this code will be affected by X planned change" so Claude considers upcoming work without reading full design docs.
- **Prevention**: When adding a planned feature that will affect existing code, add a planning-awareness rule so the context loads automatically.

### Lesson 33: Not every decision needs a formal AD entry
- **Observation**: Some undocumented behaviors (temporal prior penalty values, detection thresholds) exist in code but were never formally decided.
- **Rule**: Use TODO markers for undocumented code behavior and "Known Unknowns" for things not yet discussed (cluster size limits). Formalize only when modifying.
- **Prevention**: `docs/ml/ALGORITHMIC_DECISIONS.md` has a "TODO" section for decisions that need code review before formalizing.

### Lesson 41: Confidence gap > absolute distance for human decision-making
- **Observation**: Showing "15% closer than next-best" is more useful for humans than showing "distance: 0.82". Relative comparisons help adjudicate truth better than absolute scores.
- **Rule**: When displaying ML results to non-technical users, prefer comparative metrics over absolute ones.
- **Prevention**: The confidence_gap pattern can be reused for any ranked list.

### Lesson 61: SKIPPED faces must participate in clustering, not just proposals
- **Mistake**: `group_inbox_identities()` only included INBOX faces (line 139). The 196 SKIPPED faces were excluded from peer-to-peer grouping forever. But `cluster_new_faces.py` already included them for proposal generation against confirmed identities.
- **Rule**: Status boundaries (INBOX vs SKIPPED) should not be clustering boundaries. "Skip" means "I can't identify this right now," not "exclude from ML forever." Every major photo system (Apple, Google, Immich) continuously re-evaluates all unresolved faces.
- **Prevention**: `group_all_unresolved()` now includes both INBOX and SKIPPED. Use `--inbox-only` flag only for legacy behavior. Added `.claude/rules/ml-ui-integration.md` section documenting this.
