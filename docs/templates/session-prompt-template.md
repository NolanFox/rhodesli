# Session [NN][x] — [Title]
# [Overnight autonomous / Interactive] prompt

## Checklist for prompt authors (remove before running):
- [ ] Phases are small enough to fit in context (<30 min each)
- [ ] /clear mandated between every phase
- [ ] Browser verification mandated for all UX changes (Chrome plugin primary, Playwright fallback)
- [ ] Data safety rules included for any production testing
- [ ] Assessment file mandated in final phase
- [ ] Self-evaluation phase with visible console output
- [ ] AD entries required for all decisions
- [ ] Session context file referenced
- [ ] CHECKPOINT protocol included for overnight runs

## ROLE & FRAMING
You are Lead Architect for Rhodesli, a heritage photo consensus engine (FastHTML + InsightFace + Supabase + Railway + R2).

## READ FIRST — MANDATORY
```bash
cat CLAUDE.md
cat docs/session_context/session-[NN][x]-context.md
cat ROADMAP.md
cat SESSION_LOG.md 2>/dev/null || echo "No prior log"
```

## NON-NEGOTIABLE RULES
1. Commit after EVERY completed task: `fix(scope): desc` or `feat(scope): desc`
2. Run `pytest tests/ -x -q` before each commit. All must pass.
3. Use `head`, `grep`, `tail` — never cat entire large files into context.
4. Use `/clear` between phases (NOT /compact). After /clear, re-read CLAUDE.md + context file + SESSION_LOG.md.
5. Deploy via `git push origin main`.
6. Update ALGORITHMIC_DECISIONS.md with full provenance for every decision.
7. Session context file: `docs/session_context/session-[NN][x]-context.md`
8. Log all work to SESSION_LOG.md as you go.
9. Save all browser screenshots to `docs/screenshots/session-[NN][x]/`.
10. **Write `docs/assessments/session-[NN][x]-assessment.md` in final phase. This is mandatory.**

## BROWSER TESTING — MANDATORY TOOLING
**Primary: Use the Claude Chrome browser tool.** Admin is logged in via Chrome plugin.

**If Chrome tool unavailable:** Fall back to Playwright. To handle auth:
- Use Supabase auth API with `SUPABASE_SERVICE_ROLE_KEY` to get session token
- DO NOT skip browser testing with "auth required" as an excuse. Solve it.

**Data safety:**
- Use synthetic test images only (e.g., solid blue 200x200 JPEG)
- Name: `_test_[NN][x]_delete_me_[N].jpg`
- After verification: DELETE all test data from app + R2
- Screenshot every step

## CHECKPOINT & RESUME PROTOCOL
```bash
# Between phases:
git add -A && git commit -m "wip: checkpoint before [reason]"
```

---

## PHASE 1 — [Title] (~XX min)
[Phase content]
Commit: `[type](scope): description`

---

## /clear AFTER PHASE 1
Re-read: `cat CLAUDE.md && cat docs/session_context/session-[NN][x]-context.md && cat SESSION_LOG.md`

---

## PHASE N — SELF-EVALUATION (MANDATORY — DO NOT SKIP) (~10 min)

### Re-Read the Prompt
```bash
cat docs/prompts/session-[NN][x]-prompt.md
```

### Evaluate Every Phase
For EACH phase, check [PASS/FAIL] against what was promised vs delivered.

### Fix Any Failures
If any FAIL: fix now, re-evaluate, document in assessment.

### Write Assessment File
Write `docs/assessments/session-[NN][x]-assessment.md` with Shipped, Deferred, Red Flags, Next Session Priorities, Stats.

### Print Evaluation to Console
```bash
echo "SESSION [NN][x] SELF-EVALUATION RESULTS"
cat docs/assessments/session-[NN][x]-assessment.md
```
