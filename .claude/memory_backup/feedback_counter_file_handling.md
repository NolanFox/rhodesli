---
name: Counter file handling
description: Never commit commits_since_clear.txt — use git checkout to restore it when stop hook complains about dirty state
type: feedback
---

When the stop hook blocks because `.claude/commits_since_clear.txt` is modified, NEVER commit it. That creates a loop (commit increments counter → file dirty again). Instead: `git checkout -- .claude/commits_since_clear.txt` immediately.

**Why:** Session 105b-cont wasted 3 unnecessary commits trying to commit the counter file, eroding user trust. Basic competence failure.

**How to apply:** At session end, if stop hook complains about this file being dirty, restore it with git checkout. One command, done.
