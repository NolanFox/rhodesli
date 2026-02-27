# Session 72 Planning Context
# Date: 2026-02-27
# Breadcrumbs: Session 71D (discoveries fix) → ML Roadmap (date estimation done → similarity calibration next)

## IMPORTANT: CONCURRENT SESSION

Another Claude Code session is running on main, merging branches from Session 71D.
This session works on worktree branch `session-72/harness-ml` and merges at the very end.
By then, the other session should be long done.

---

## 1. HARNESS PROBLEMS TO FIX

### Tests too slow
Full suite: 3146 tests, 3-5 minutes. Per-commit testing eats 30-50% of session time.
Fix: pytest-xdist + markers. `make test-fast` <30s, `make test-full` parallel.

### Worktree enforcement fails
Claude Code ignores behavioral rules. Scripts exist but aren't called.
Fix: PreToolUse hook fires automatically on every git commit. Checks for
`.claude/parallel_session_active` flag + main branch → blocks with exit 2.

### Merge ceremonies too slow
Session 71D merge: 23+ minutes for 2 branches.
Fix: `scripts/merge.sh branch1 branch2` — merge all, test once.

---

## 2. ML CONTEXT — SIMILARITY CALIBRATION

### ML roadmap position
1. ✅ Date estimation (CORAL — done, deployed)
2. → **Similarity calibration** (THIS SESSION)
3. LoRA fine-tuning (future, only if calibration plateaus)

### What it does
Currently: cosine distance → hard thresholds → confidence tiers.
Problem: ignores metadata (collection, era, quality).
Solution: MLP that takes distance + metadata → match probability (0-1).
Sits on frozen InsightFace embeddings. No backbone changes.

### Training data
- Positive pairs: faces merged into same identity (confirmed same person)
- Negative pairs: "Not Same" marks + random cross-identity pairs
- Sources: Supabase tables, identity data in app

### Portfolio value
Clean ML engineering story: problem framing, feature engineering, PyTorch training,
regression gate, shadow scoring, active learning potential.

---

## 3. WHAT NOT TO DO

- No new harness documentation beyond what's specified
- No Discoveries redesign
- No GEDCOM work
- No landing page
- No prompt decomposition improvements
- Phase 1 hard cap: 30 minutes
