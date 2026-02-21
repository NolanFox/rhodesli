# RHODESLI — Session 55: Similarity Calibration + Backlog Audit

## ROLE
You are Lead Engineer for Rhodesli, a heritage photo archive with ML-powered face recognition for the Jewish community of Rhodes. Stack: FastHTML + HTMX + InsightFace + Supabase + Cloudflare R2 + Railway.

## SESSION GOALS (in priority order)
1. Backlog/Roadmap audit — ensure ALL discussed items are tracked (nothing lost)
2. Write PRD + SDD for Similarity Calibration
3. Implement similarity calibration training pipeline (PyTorch Lightning + MLflow)
4. Evaluate calibration against raw cosine similarity baseline
5. Integrate calibrated model into compare pipeline
6. Session documentation + verification gate

**This is the #1 portfolio piece for the job search.** The interview sentence: "I trained a learned calibration layer on frozen InsightFace embeddings using 54 confirmed identities as ground truth, tracked with MLflow — improving precision by X% without retraining the base model."

---

## NON-NEGOTIABLE RULES

### Execution Rules
1. **Commit after EVERY completed phase**
2. **Run `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q` before each commit.** Both suites. Every time.
3. **Deploy via `git push` (Railway auto-deploys).** NEVER use Railway dashboard.
4. **After every deploy, verify with Railway CLI:** `railway logs --tail 50`
5. **Use Claude in Chrome extension for browser verification.**
6. **Do NOT declare any feature "done" without production browser verification.**

### Documentation Rules
7. **Update `docs/session_context/session_55_checkpoint.md` after EVERY phase.**
8. **Update ALGORITHMIC_DECISIONS.md** for any ML/architectural decisions.
9. **No doc over 300 lines.** CLAUDE.md under 80 lines.
10. **Save the original prompt to disk immediately.**

### ML-Specific Rules
11. **Serving Path Contract (AD-110):** Training runs LOCAL. Model artifact deployable to Railway.
12. **Ground truth is sacred.** Never modify ground truth data programmatically.
13. **MLflow tracks everything.** Every training run logged.

---

## PHASES

### Phase 0: Orient + Install Checkpoint System
Read project state, save prompt, create checkpoint, set up compact hooks.

### Phase 1: Backlog/Roadmap Audit
Verify 20 items from planning context are tracked. Fix session numbering.

### Phase 2: PRD + SDD for Similarity Calibration
Investigate ground truth data. Write PRD-023, SDD-023. Record AD entries.

### Phase 3: Implement Training Pipeline
- data.py: pair generation from ground truth
- model.py: CalibrationModel (Siamese MLP)
- train.py: PyTorch Lightning training loop + MLflow
- evaluate.py: precision/recall vs baseline
- export.py: model artifact export
- Full test coverage for each module

### Phase 4: Evaluate Against Baseline
Compute baseline, run training, compare results, hyperparameter sweep.

### Phase 5: Integrate into Compare Pipeline
Model loading, updated compare endpoint, config flag, deploy+verify.

### Phase 6: Session Documentation + Verification Gate
Re-read prompt, check all phases, update CHANGELOG/ROADMAP/BACKLOG/session log.

---

## CRITICAL REMINDERS (for post-compaction)

1. **Session 55.** Read `docs/prompts/session_55_prompt.md`, checkpoint, planning context.
2. **#1 portfolio piece.** Similarity calibration on frozen InsightFace embeddings.
3. **Two test suites:** `pytest tests/` AND `pytest rhodesli_ml/tests/`. Run BOTH.
4. **Serving Path Contract:** Training LOCAL. Model artifact deployable to Railway.
5. **MLflow tracks everything.**
6. **Deploy via git push.** Verify with `railway logs --tail 50`.
7. **Update checkpoint after every phase.**
8. **PRD + SDD before code.**
9. **Commit after every phase.**
10. **No doc over 300 lines. CLAUDE.md under 80.**
