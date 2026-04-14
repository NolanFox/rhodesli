# Memory Protection — Never Delete, Always Back Up

Triggers: Before any Write or Edit to MEMORY.md, or any deletion of files in the memory directory.

## ABSOLUTE RULES

### 1. Never delete a memory file
- Memory files represent hard-won lessons from real user feedback and production incidents
- To "clean up" memory: UPDATE the file content or MERGE two files — never delete
- If a memory is truly obsolete, rename it with `_archived` suffix, don't remove it
- **Only the user can authorize deletion** — ask first, always

### 2. MEMORY.md is an INDEX, not storage
- Each entry must be ONE line, under 150 characters
- Detailed content goes in topic files, not the index
- When MEMORY.md exceeds 200 lines, trim INDEX ENTRIES (the one-liners), not topic files
- Before removing an index entry: verify the topic file still exists and is self-contained

### 3. Back up memory to git
- Memory is backed up to `.claude/memory_backup/` (in the repo, version-controlled)
- Run `scripts/backup-memory.sh` at session end to sync
- This ensures git history protects against accidental deletions

### 4. Integrity check
- After any memory write: verify every MEMORY.md link resolves to an existing file
- After any memory read: if a referenced file is missing, flag it immediately — don't silently skip

## Why This Exists
Session 148 (2026-04-13): 6 memory files were deleted by a previous session that was
trying to trim MEMORY.md under the 200-line limit. It deleted the topic FILES instead of
trimming the index entries. The inline content from the old bloated MEMORY.md was also lost.
These represented critical feedback from Sessions 104-125 that had to be reconstructed from
partial context. Memory outside git had no recovery path.
