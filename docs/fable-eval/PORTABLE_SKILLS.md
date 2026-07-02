# W7 — Skill Portability: which skills should live at user level

Rhodesli already promotes genuinely-portable skills to user level (`~/.claude/skills/`, HD-002
pattern — e.g. `photo-context`, all the `source-*` skills, `multimodel-sprint`, `fable-usage`).
The three skills installed this run are **project-scoped for now** but two have a portable core.

## Recommendation per skill

| Skill | Keep project-level? | Promote to `~/.claude`? | Rationale |
|-------|--------------------|------------------------|-----------|
| `split-brain-data-audit` | **Yes (now)** | Later, as a generalized `single-source-of-truth-audit` | The *principle* (write-path must reach the read store; remove legacy layers in the same commit; fail-closed scoping; round-trip + prod-page verify) is fully portable. But the current draft is dense with rhodesli specifics (`save_registry`, `DATA_SOURCE=postgres`, `_ensure_list`, exact lesson numbers, `tests/test_data_layer_invariants.py`). fox-genealogy is a markdown-vault repo (different failure surface). Promote only after extracting a repo-agnostic core + a rhodesli-specifics appendix. |
| `supabase-migration-safety` | **Yes (now)** | Only if a sibling repo adopts Supabase | Tightly bound to rhodesli's Supabase/pooler/R2/GEDCOM stack. fox-genealogy has no Postgres. Not worth generalizing until a second repo shares the stack. |
| `route-safety-audit` | **Yes (keep project-level)** | No | FastHTML/HTMX + CommunityMiddleware + the exact guard helpers are rhodesli-specific. fox-genealogy has no web route surface. A generalized "web route auth/CSRF checklist" already exists in the wider ecosystem; this one earns its place by encoding *rhodesli's* incidents. |

## Repo-specific paths that MUST be adapted before any promotion
If `split-brain-data-audit` is later generalized, these rhodesli-only anchors become placeholders:
- Data stores: Supabase Postgres (source of truth) + Railway volume JSON + local JSON → in
  fox-genealogy this maps to "the vault markdown + any derived index/cache".
- Files: `app/main.py` save/load, `app/supabase_data.py`, `core/registry.py`, `app/upload_routes.py`.
- Tests: `tests/test_data_layer_invariants.py`, `tests/test_merge_*`.
- Lesson index: `tasks/lessons.md` + `tasks/lessons/data-lessons.md` (fox-genealogy has its own
  `tasks/lessons.md`).
- Env: `DATA_SOURCE=postgres` flag has no fox-genealogy analog.

## Suggested promotion path (future session, not this run)
1. Split each skill into a portable `SKILL.md` (principles + generic gates) + a
   `rhodesli-specifics.md` child (exact files/tests/lessons).
2. Symlink or copy the portable core to `~/.claude/skills/` per the HD-002 promotion convention
   used for `photo-context` and the `source-*` family.
3. Register a repo-detection note at the top so the skill loads the right specifics file.

**This run does NOT promote anything to user level** — that touches `~/.claude` (excluded). Logged
here as a User Decision for a later, gated session.
