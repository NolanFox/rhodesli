# Harness Validation Report — Session 64c

## Hooks

| Hook | Event | Matcher | Fires? | Notes |
|------|-------|---------|--------|-------|
| Pre-commit test gate | PreToolUse | Bash (`^git commit`) | UNCERTAIN | Hook exists and config is valid. Output not visible in tool results. **Bug**: regex `^git commit` doesn't match chained commands like `git add && git commit`. Only fires when `git commit` is the first/only command. |
| ML file edit reminder | PostToolUse | Edit\|Write (`rhodesli_ml\|core/*.py`) | UNCERTAIN | Hook exists, config valid. Tested by editing `rhodesli_ml/__init__.py`. Reminder writes to stderr — may not be visible in Claude Code tool results. Path regex looks correct. |
| Completion notification | Stop | (all) | UNTESTED | Will fire at session end. Uses macOS `osascript` for notification. |
| PreCompact recovery | PreCompact | auto | EXISTS | References `.claude/hooks/recovery-instructions.sh` (693 bytes, executable). Not tested — would need to trigger compaction. |

### Hook Issues Found

1. **Pre-commit hook regex too narrow**: `^git commit` fails on `git add -A && git commit -m "..."` which is the standard pattern. Should use `git commit` without `^` anchor, or check with `\bgit commit\b`.
2. **Hook output visibility unclear**: Neither the pre-commit test output nor the ML reminder was visible in tool results. Hooks may be running silently. Need to verify hook output mechanism.

## Skills (6 total — 5 expected + 1 bonus)

| Skill | Exists? | Well-formed? | Frontmatter? | Notes |
|-------|---------|-------------|--------------|-------|
| session-run.md | YES | YES | YES (`description` field) | Framework for autonomous sessions. Clear, actionable. |
| deploy-verify.md | YES | YES | YES (`description` field) | Deploy + production verification. Clear steps. |
| ml-pipeline.md | YES | YES | YES (`description` field) | ML code modification protocol. References AD docs. |
| assess-session.md | YES | YES | YES (`description` + `disable-model-invocation`) | Session assessment. Marked as human-invocable only. |
| build-prompt.md | YES | YES | YES (`description` + `disable-model-invocation`) | Session prompt builder. Marked as human-invocable only. |
| ingest.md | YES | YES | NO (no YAML frontmatter) | Ingestion pipeline. Older format — no `description` field in frontmatter. |

## Rules (39 total — 3 referenced in CLAUDE.md, 36 additional)

### Referenced in CLAUDE.md
| Rule | Exists? | Referenced? | Notes |
|------|---------|------------|-------|
| ml-development.md | YES | YES | ML code modification protocol |
| data-layer.md | YES | YES | Postgres-first data architecture |
| session-protocol.md | YES | YES | Session execution discipline |

### Also loaded via .claude/rules/ (auto-loaded by Claude Code)
| Category | Count | Examples |
|----------|-------|---------|
| Session/harness | 10 | verification-gate, self-assessment, phase-execution, prompt-decomposition, dual-test-suites, dual-update-rule, harness-decisions, session-context-integration, session-priorities, production-verification |
| ML/data | 6 | ml-pipeline, ml-decisions, ml-documentation, ml-ui-integration, data-files, data-safety |
| Development process | 7 | spec-driven-development, feature-reality-contract, feature-completeness, entry-point-testing, test-isolation, feedback-driven, decision-provenance |
| Domain/UX | 5 | ux-context, ux-evaluation, discovery-ux, about-docs, ui-scalability |
| Deployment/ops | 5 | deployment, data-sync, production-data-sync, post-pipeline-verification, photo-workflow |
| Auth/permissions | 2 | auth-permissions, upload-provenance |
| Planning | 1 | planning-awareness |

All 39 rule files exist and are valid markdown.

## CLAUDE.md

- **Size**: 1,952 chars (well under 2,000 target)
- **Line count**: 45 lines (well under 80 line limit)
- **References skills directory**: PARTIAL — references 2 specific skill files (`session-run.md`, `deploy-verify.md`), not the directory itself
- **References rules directory**: PARTIAL — references 3 specific rule files (`ml-development.md`, `data-layer.md`, `session-protocol.md`), not the directory itself
- **Note**: All 39 rules in `.claude/rules/` are auto-loaded by Claude Code regardless of CLAUDE.md references. CLAUDE.md references serve as "priority highlights" rather than exhaustive index.

## Recommendations

1. **Fix pre-commit hook regex**: Change `^git commit` to `git commit` (without anchor) so it catches chained commands. Or use `\bgit commit\b`.
2. **Add frontmatter to ingest.md**: Missing YAML frontmatter with `description` field — inconsistent with other skills.
3. **No action needed on CLAUDE.md**: The 39 rules auto-load from `.claude/rules/`. CLAUDE.md correctly highlights the 3 most important ones. Adding a directory reference would be informational but not functional.
4. **Verify hook output mechanism**: Test hooks from a fresh session to confirm they produce visible output. May need to write to stdout instead of stderr, or use a different output mechanism.
