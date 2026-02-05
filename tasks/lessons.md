# Lessons Learned

**READ THIS FILE AT THE START OF EVERY SESSION.**

## Session 2026-02-05: R2 Migration Failures

### Lesson 1: Test ALL code paths, not just the obvious one
- **Mistake**: Fixed image URLs for image_* identities but missed inbox_* identities
- **Rule**: When fixing URL generation, grep for ALL places that generate URLs and test each one
- **Prevention**: Before declaring done, list every code path and verify each

### Lesson 2: Regressions require before/after comparison
- **Mistake**: Face box overlays broke during dimension fix -- indentation error caused only 1 box instead of N
- **Rule**: Before committing, compare behavior for ALL affected features
- **Prevention**: Write down what worked before, verify it still works after

### Lesson 3: "It compiles" is not "it works"
- **Mistake**: Declared success when crops loaded, but didn't test Photo Context modal
- **Rule**: Test every UI state, not just the first one you see
- **Prevention**: Create explicit checklist of ALL UI states before starting

### Lesson 4: Staff engineer approval test
- **Question**: "Would a staff engineer at a top company approve this PR?"
- **If no**: Stop and fix before continuing
- **If unsure**: Probably no -- investigate further

### Lesson 5: 2026-02-05 - Indentation bugs when wrapping code in conditionals
- **Mistake**: When wrapping a `for` loop body inside `if has_dimensions:`, only the first few lines of the loop body were re-indented. The rest stayed at the outer level, causing them to run once after the loop instead of per-iteration.
- **Rule**: When adding a new conditional wrapper around existing code, verify EVERY line in the block got re-indented. Check the last line of the block specifically.
- **Prevention**: After any indentation change, read the full block end-to-end and confirm the closing lines are at the correct depth.
