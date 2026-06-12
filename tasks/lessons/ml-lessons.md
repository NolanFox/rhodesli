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

### Lesson 115: Single-linkage union-find creates transitive snowball clusters
- **Mistake**: `group_inbox_identities()` used union-find with single-linkage: if A↔B < 0.95 AND B↔C < 0.95, A and C merged even when A↔C = 1.4. Created 252-face garbage clusters mixing many different people.
- **Rule**: Face grouping MUST use complete-linkage: only merge two groups if ALL inter-group pairwise distances are below threshold. This prevents transitive chain merging.
- **Prevention**: Replaced union-find with complete-linkage agglomerative clustering in all 3 grouping functions (`group_faces`, `group_inbox_identities`, `group_all_unresolved`). Verify largest cluster size after any grouping run — should never exceed ~50 at threshold 0.95.

### Lesson 61: SKIPPED faces must participate in clustering, not just proposals
- **Mistake**: `group_inbox_identities()` only included INBOX faces (line 139). The 196 SKIPPED faces were excluded from peer-to-peer grouping forever. But `cluster_new_faces.py` already included them for proposal generation against confirmed identities.
- **Rule**: Status boundaries (INBOX vs SKIPPED) should not be clustering boundaries. "Skip" means "I can't identify this right now," not "exclude from ML forever." Every major photo system (Apple, Google, Immich) continuously re-evaluates all unresolved faces.
- **Prevention**: `group_all_unresolved()` now includes both INBOX and SKIPPED. Use `--inbox-only` flag only for legacy behavior. Added `.claude/rules/ml-ui-integration.md` section documenting this.

### Lesson 207: With rich GEDCOM context, multi-model photo dating is won by biographical-age anchoring, not material-format breadth
- **Context (Session 166):** Ran one fully-GEDCOM-enriched prompt (date + location) against Gemini 3.1 Pro, Fable 5.0, and Codex gpt-5.5-xhigh on a portrait of Meyer Fox (b.~1853) + Reva Heft (b.~1865), both later in Brooklyn, Reva d.1926. All three converged on **decade 1910 / New York City / medium confidence** with a hard 1926 ceiling (Reva's death) — strong agreement.
- **Finding:** The differentiator was reasoning quality on the GEDCOM age signal. **Fable 5.0** explicitly anchored the lower bound on the sitters' apparent ages vs their birth years ("not earlier, since the sitters' apparent ages anchor the lower bound"), ran the missing-child test correctly, and gave the sharpest distribution. **Codex gpt-5.5** was solid but put ~0.42 probability on the 1900s because it leaned on the broad print-format/enlargement range (~1895–1920) instead of letting apparent-age evidence pull the lower bound up. **Gemini 3.1 Pro** was a near-tie with Fable and is the platform-native path (auto cost/lineage logging).
- **Rule:** When a photo has GEDCOM-linked subjects, the best estimate privileges biographical age-anchoring (apparent age vs birth year) and hard date ceilings (a spouse's death) over broad material-format ranges. Material format (cabinet card, oval crayon enlargement, gelatin print) sets a wide prior; biography sharpens it. Prefer the model whose reasoning does the latter.
- **Prevention / use:** Multi-model comparison is a manual admin workflow (`scripts/multimodel_photo_estimate.py`); only the chosen estimate goes to `date_labels`, all candidates + the decision are repo artifacts under `docs/experiments/photo-estimates/`. See `.claude/rules/multimodel-photo-estimate.md`, AD-251.
