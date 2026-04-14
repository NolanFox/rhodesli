---
name: Memory files must never be deleted
description: 6 memory files were lost when a session deleted topic files instead of trimming the index. Memory must be backed up to git.
type: feedback
originSessionId: 27dd84b2-b7c4-4c48-8614-cb15d02f538c
---
NEVER delete memory topic files. When MEMORY.md exceeds 200 lines, trim INDEX ENTRIES (one-liners), not the underlying .md files.

**Why:** Session ~147 area: a previous session tried to slim MEMORY.md by deleting 6 topic files instead of shortening the index. The files lived outside git (at ~/.claude/projects/) with no version control, so they were unrecoverable. Had to reconstruct from partial context in the bloated MEMORY.md that was loaded into conversation. Hard-won feedback from Sessions 104-125 was at risk.

**How to apply:**
1. MEMORY.md is an INDEX — one line per entry, content in topic files
2. To slim the index: shorten descriptions, merge related entries — never delete topic files
3. Run `./scripts/backup-memory.sh` at session end — syncs to `.claude/memory_backup/` (in git)
4. If a file must truly be removed: rename with `_archived` suffix, and only with user approval
5. After any memory edit: verify all MEMORY.md links resolve (the backup script does this)
