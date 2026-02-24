# Session 64c: Concerns Resolution + Harness Validation
# Rhodesli Heritage Photo Archive
# Created: 2026-02-23
# Run in parallel with Session 64d (batch photos)

# ═══════════════════════════════════════════════════════
# GIT SETUP — DO THIS FIRST
# This session runs in parallel with Session 64d.
# Each session works on its own branch to avoid conflicts.
# ═══════════════════════════════════════════════════════

```bash
git checkout main
git pull origin main
git checkout -b session-64c
```

If `git pull` fails or there are uncommitted changes, resolve before proceeding.

# ═══════════════════════════════════════════════════════
# READ NEXT — MANDATORY
# ═══════════════════════════════════════════════════════

Read these files IN ORDER:
1. `CLAUDE.md`
2. `docs/session_context/session_64b_assessment.md`
3. `ALGORITHMIC_DECISIONS.md` (last 5 entries: AD-153 through AD-157)
4. `ROADMAP.md`
5. `BACKLOG.md`

Confirm you have read all five. Print: last AD number, ROADMAP line count, test count from last session.

# ═══════════════════════════════════════════════════════
# SESSION RULES (NON-NEGOTIABLE)
# ═══════════════════════════════════════════════════════

1. ONE deliverable per phase. Do not combine.
2. Commit after EVERY phase.
3. Print context % after EVERY phase.
4. If context < 40%: `/clear` and re-read CLAUDE.md + this prompt.
5. If context < 20%: STOP. Log progress.
6. NEVER use `/compact`. Always `/clear` + re-read from disk.
7. Every ROADMAP/BACKLOG edit → diff first, confirm no items silently dropped.

# ═══════════════════════════════════════════════════════
# PHASE 1: Harness Validation Report (~10 min)
# The skills, hooks, and rules from Session 64 need
# to be tested and validated. Report on what works.
# ═══════════════════════════════════════════════════════

## 1A: Test each hook

### Pre-commit test gate hook
Make a trivial change (add a comment to any test file), then attempt `git commit`. 
The hook should automatically run `pytest tests/ -x -q --ignore=tests/e2e/`.
Document: Did the hook fire? Did tests run? What was the output?

### ML file edit reminder hook  
Make a trivial change to any file in `rhodesli_ml/*.py` (add a comment, then revert).
The hook should print a reminder about updating ALGORITHMIC_DECISIONS.md.
Document: Did the hook fire? Was the reminder visible?

### Completion notification hook
This fires on session Stop — we can't test it mid-session. Note: will validate at end.

## 1B: Test each skill

For each skill file in `.claude/skills/`, read it and confirm:
- Does the file exist and is it well-formed markdown?
- Are the instructions clear and actionable?
- Does the `description` field in the frontmatter make sense?

```bash
echo "=== SKILL FILES ==="
ls -la .claude/skills/*.md 2>/dev/null
echo ""
for f in .claude/skills/*.md; do
    echo "--- $f ---"
    head -5 "$f"
    wc -l "$f"
    echo ""
done

echo "=== RULE FILES ==="
ls -la .claude/rules/*.md 2>/dev/null
for f in .claude/rules/*.md; do
    echo "--- $f ---"
    head -3 "$f"
    wc -l "$f"
    echo ""
done

echo "=== CLAUDE.md SIZE ==="
wc -c CLAUDE.md
```

## 1C: Test CLAUDE.md references

CLAUDE.md should reference the skills and rules directories. Verify:
```bash
grep -n "skills\|rules" CLAUDE.md
```

If CLAUDE.md doesn't point to `.claude/skills/` or `.claude/rules/`, add the references.

## 1D: Write harness validation report

Create `docs/session_context/harness_validation_64c.md` with:
```
# Harness Validation Report — Session 64c

## Hooks
| Hook | Event | Fires? | Notes |
|------|-------|--------|-------|
| Pre-commit test gate | PreToolUse (Bash git commit) | YES/NO | [details] |
| ML file edit reminder | PostToolUse (Edit rhodesli_ml/) | YES/NO | [details] |
| Completion notification | Stop | UNTESTED | Will fire at session end |

## Skills
| Skill | Exists? | Well-formed? | Notes |
|-------|---------|-------------|-------|
| session-run.md | YES/NO | YES/NO | [details] |
| deploy-verify.md | YES/NO | YES/NO | [details] |
| ml-pipeline.md | YES/NO | YES/NO | [details] |
| assess-session.md | YES/NO | YES/NO | [details] |
| build-prompt.md | YES/NO | YES/NO | [details] |

## Rules
| Rule | Exists? | Referenced? | Notes |
|------|---------|------------|-------|
| ml-development.md | YES/NO | YES/NO | [details] |
| data-layer.md | YES/NO | YES/NO | [details] |
| session-protocol.md | YES/NO | YES/NO | [details] |

## CLAUDE.md
- Size: XXXX chars (target: <2000)
- References skills directory: YES/NO
- References rules directory: YES/NO

## Recommendations
[Any fixes needed, improvements suggested]
```

Commit: `docs: harness validation report — hooks, skills, rules audit`

# ═══════════════════════════════════════════════════════
# PHASE 2: Narrow exception handling (~5 min)
# Broad except Exception silently swallowed bugs in 64b.
# ═══════════════════════════════════════════════════════

Find all broad exception handlers in GEDCOM loading paths:
```bash
grep -n "except Exception\|except:" rhodesli_ml/gedcom*.py app/supabase_data.py app/face_alignment.py 2>/dev/null | head -20
```

For each one found:
1. Determine what specific exceptions are expected (Supabase connection errors, network timeouts, JSON decode errors)
2. Narrow to those specific types
3. Let schema mismatches (KeyError, column name errors) bubble up as loud failures
4. Add logging for caught exceptions so they're visible even when handled

Pattern:
```python
# BEFORE (bad — swallows everything)
try:
    data = supabase.table('gedcom_face_links').select('*').execute()
except Exception:
    return None

# AFTER (good — catches expected errors, lets schema bugs crash)
try:
    data = supabase.table('gedcom_face_links').select('*').execute()
except (ConnectionError, TimeoutError, httpx.HTTPError) as e:
    logger.warning(f"Supabase query failed: {e}")
    return None
# KeyError, AttributeError, etc. will now crash loudly
```

Tests: existing tests should still pass. Run:
```bash
pytest tests/ -x -q --ignore=tests/e2e/
pytest rhodesli_ml/tests/ -v
```

Commit: `fix: narrow exception handling in GEDCOM/alignment loading paths`

# ═══════════════════════════════════════════════════════
# PHASE 3: Verify API cost tracking (~5 min)
# 64b logged 10 API calls. Check if cost_usd populated.
# ═══════════════════════════════════════════════════════

```bash
# Check what's in the API calls table
psql "$DATABASE_URL" -c "
SELECT 
    photo_id, 
    model_used, 
    call_type,
    prompt_tokens, 
    completion_tokens, 
    cost_usd, 
    status,
    latency_ms
FROM gemini_api_calls 
ORDER BY created_at DESC 
LIMIT 10;
" 2>&1
```

If psql not available, use Python:
```python
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
result = sb.table('gemini_api_calls').select('*').order('created_at', desc=True).limit(10).execute()
for r in result.data:
    print(f"photo={r['photo_id'][:12]}... model={r['model_used']} cost=${r.get('cost_usd', 'NULL')} tokens={r.get('total_tokens', 'NULL')} status={r['status']}")
```

**Evaluate the results:**
- If `cost_usd` is NULL or 0 for all rows: the cost calculation in `log_gemini_call()` isn't working. Fix it — it should compute cost from token counts × model pricing.
- If `total_tokens` is NULL: the Gemini API response isn't being parsed for token usage. Fix the parsing.
- If costs look reasonable (Flash ~$0.003/call): document that tracking works.

If fixes are needed, make them. If everything looks good, just document it.

Commit: `fix|docs(data): verify/fix API cost tracking in gemini_api_calls`

**Print context %. If < 40%, /clear and re-read CLAUDE.md + this prompt.**

# ═══════════════════════════════════════════════════════
# PHASE 4: Verify calibrated scores end-to-end (~5 min)
# Face cards show on photo pages (verified in 64b).
# But calibrated scores in compare flow are unverified.
# ═══════════════════════════════════════════════════════

1. Find the compare/match display code:
```bash
grep -rn "calibrat\|isotonic\|probability\|match.*score\|similarity.*display" --include="*.py" app/ | grep -v __pycache__ | grep -v test | head -20
```

2. Trace the data flow:
   - Where does the raw cosine similarity come from?
   - Where does it get transformed to a calibrated probability?
   - What does the user actually see in the UI?

3. Write a verification test:
```python
def test_compare_shows_calibrated_not_raw():
    """Verify the compare flow shows '85% match' not '0.73 similarity'"""
    # Get a known match pair
    # Call the compare endpoint
    # Check the response contains percentage format, not raw float
```

4. If calibration ISN'T wired into the compare flow:
   - Find the compare endpoint
   - Find where similarity scores display
   - Add calibration transformation before display
   - The isotonic regression model should already exist from Session 63

5. Document exactly what the user sees, with code line references.

Commit: `test|fix: verify calibrated scores display as probabilities in compare flow`

# ═══════════════════════════════════════════════════════
# PHASE 5: Update roadmap with upcoming session plan (~5 min)
# Make sure nothing gets lost in the planning.
# ═══════════════════════════════════════════════════════

Read current ROADMAP.md and BACKLOG.md. Print both.

Update ROADMAP.md to reflect this plan (DIFF first, confirm no items dropped):

```
## Upcoming Sessions

### Session 65: UX Walkthrough + Help Identify
- Nolan conducts end-to-end product walkthrough, documents findings
- FE-041: Help Identify mode for non-admin users
- Address UX issues from walkthrough
- Prerequisite for LoRA: community identifications generate training data

### Session 66: Portfolio Documentation + LoRA Prep
- Technical writeup of ML pipeline for interview portfolio
- Document: InsightFace → CORAL → isotonic calibration → Gemini alignment → GEDCOM enrichment
- LoRA training data audit: count confirmed pairs, assess readiness
- LoRA implementation plan: contrastive loss, layer selection, ONNX export

### Session 67+: LoRA Fine-Tuning
- Fine-tune InsightFace final layers on confirmed identity pairs
- Active learning + regression gate architecture
- Recalibrate isotonic regression on new embedding space
- A/B comparison: pre-LoRA vs post-LoRA similarity scores
```

Update BACKLOG.md: ensure FE-041, portfolio documentation, and LoRA items are all present.

AD entry: `AD-XXX: Session roadmap — UX → Portfolio → LoRA sequence rationale`
- Why UX first: community identifications generate LoRA training data
- Why portfolio before LoRA: job search is active, ML pipeline is already interview-worthy
- Why LoRA after: needs 50-100+ confirmed pairs minimum

Commit: `docs: update roadmap with Sessions 65-67 plan, AD entry for sequencing rationale`

# ═══════════════════════════════════════════════════════
# PHASE 6: Merge to main (~2 min)
# ═══════════════════════════════════════════════════════

```bash
git checkout main
git pull origin main
git merge session-64c --no-edit
```

If merge conflicts (because 64d pushed first):
- Resolve conflicts — 64c owns: app code, tests, harness files, ROADMAP, BACKLOG
- 64d owns: gemini_api_calls inserts, face_gemini_alignments inserts, results/ logs
- If conflict is in ROADMAP.md or SESSION_HISTORY.md: keep both sessions' additions

```bash
git push origin main
```

If push fails (64d pushed while we were merging): `git pull --rebase origin main && git push origin main`

Clean up:
```bash
git branch -d session-64c
```

# ═══════════════════════════════════════════════════════
# PHASE 7: Session assessment (~3 min)
# ═══════════════════════════════════════════════════════

Print structured assessment:

```
## Session 64c Assessment
- Duration: X minutes
- Phases: N/7 completed
- Tests: +N new, NNNN total

## Concerns Resolved
1. Broad exception handling → [RESOLVED/PARTIAL]
2. API cost tracking verification → [RESOLVED/PARTIAL]
3. Calibrated scores in compare flow → [RESOLVED/PARTIAL]
4. Harness validation → [RESOLVED/PARTIAL]
5. Roadmap updated with upcoming plan → [RESOLVED/PARTIAL]

## Harness Report Summary
- Hooks working: N/3
- Skills present: N/5
- Rules present: N/3
- Issues found: [list]

## Completion notification test
[The Stop hook should fire after this session ends.
Did you see the macOS notification? Y/N]
```

Commit: `docs: Session 64c assessment`

# ═══════════════════════════════════════════════════════
# WHAT THIS SESSION DELIVERS
# ═══════════════════════════════════════════════════════
#
# 1. Harness validation report (hooks, skills, rules)
# 2. Narrowed exception handling (no more silent failures)
# 3. API cost tracking verified or fixed
# 4. Calibrated scores verified end-to-end
# 5. Roadmap updated with 65-67 plan (UX → Portfolio → LoRA)
# 6. Self-assessment with harness metrics
#
# This runs in PARALLEL with 64d (batch photos).
# Neither session touches the other's files.
# ═══════════════════════════════════════════════════════
