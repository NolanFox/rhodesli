# Session 154 Context — FULL state carry-over (post-/clear)

**Predecessor:** Session 153b (`docs/prompts/session-153b-prompt.md`, `docs/assessments/session-153b-assessment.md`)
**Predecessor-predecessor:** Session 153 (`docs/feedback/session-153-what-weve-done.md` is the honest narrative — the 14-doc trail is confusing; read that one).
**Written:** 2026-04-19 at end of 153b, before user /clear.
**Purpose:** Everything new-context Claude needs to resume 154 without losing prior work.

---

## TL;DR in 30 seconds

The Rhodesli Fox-family identification work had 3 big open threads at end of 153b:

1. **Shadow eval revealed the Gemini location prompt is unfair to candidate**: the 3-round scaffold EXPECTS GEDCOM context but `scripts/session153_shadow_eval.py` never passes any. So candidate's architectural-reasoning-only prompt hallucinated "New York Botanical Garden" for a 1917 Detroit photo. Production pipeline (`rhodesli_ml/gemini_extraction.py`) DOES accept `gedcom_context` — the plumbing exists; the shadow eval just doesn't use it.
2. **Harry Fox anchor repair is gated** on a face-ID discrepancy (`inbox_1fea75...` per Codex audit vs `inbox_2bc31a40c34a` per Session 153 breakthrough doc) and on strengthening the Bessie = 3009 hypothesis beyond POSSIBLE-trending-WEAK.
3. **Three outstanding Codex P0s from 153 Codex audit** never addressed: Belle Isle archival citation (Burton Historical Collection), Irving-anchor verification, and production `date_labels` Detroit correction (user explicitly skipped the last one).

Session 154 should tackle #1 and #2 in parallel tracks, with #3 as a lower-priority parallel tail.

---

## What was confirmed (honest, triangulated)

- **Center man is NOT Harshel Fox** (the registry's "Harry Fox" identity). 4 independent sources agree: local ML (d=1.36-1.43 vs 5 Harshel anchors), Gemini 3.1 Pro (blond/blue vs dark/dark + ear morphology), Codex (0.88 confidence), Codex 4th independent audit.
- **Two Belle Isle Conservatory frames (02068 + 01659) are the SAME event**. Gemini 3.1 Pro said 100% confidence in Session 153. Cross-face d=0.629 (same person, across frames). Photo 91b6f6b296e93a60 from Session 143 may be a third frame — not in Supabase under that exact string, needs investigation.
- **Albert Fox IS seated-right in 02068**. Distance to Albert's cluster = 0.876 (strong). Independently Gemini-confirmed.
- **Person 3010 is a background passerby**. SKIPPED (reversible snapshot).
- **The photo date window is 1917-mid-1918** (corrected from Session 153's initial "1918 New York"). Albert's GEDCOM: RESI Detroit 1917; RESI Detroit 1917-1918 single; EVEN 7 Jun 1918 (draft induction); EVEN 5 Jul 1918 NY (Camp Devens). Before June 1918 induction is most likely.

## What was over-claimed and retracted in 153b

- **"Center man IS Harry Isaackovitz"** — retracted. Ancestry proves Harry Isaackovitz existed (b.1881, Bessie Fox's husband per tree 162873127 person 132506612777) but NO reference photo exists. No model can positively identify him. Only "NOT Harshel" is triangulated.
- The file `docs/feedback/session-153-harry-isaackovitz-breakthrough.md` has a retraction banner added in 153b pointing to the honest corrective docs.

## What is genuinely uncertain (honest confidence)

### 3009 (back-right standing woman in 02068) = Bessie Fox?
**POSSIBLE trending WEAK (~40%)**. 4 signals:
- Local ML (d=1.28 beach anchor, d=1.36 FB anchor) — rank **#46** in full similarity list. Bessie is the best Fox candidate but not a strong candidate in absolute terms. **WEAK.**
- Claude multimodal subagent (fresh context, independent): broad-based nose + face-width support; mouth + eye-spacing against. **POSSIBLE ~55%.**
- Claude direct visual (153b main thread): face feels narrower vs Bessie's fuller face; age gap obscures. **WEAK.**
- Opus independent audit: beach anchor at rank 51/2,868 = top 1.7% (real signal) but FB anchor rank 715 (~25th pct, noise). **POSSIBLE.**

**Synthesis doc:** `docs/feedback/session-153b-bessie-validation.md`.

### 3007 (back-left standing woman in 02068)
**UNKNOWN, likely non-Fox.** Zero confirmed Fox in top-10 nearest. Closest CONFIRMED is Rachel Alhadeff Capeluto (Rhodes Sephardic, unrelated) at d=1.239 — cross-family baseline. Strongest alternative by biography: Rose Scheckzner (Harshel's wife, age 33 in 1917, Dayton OH) but no anchor.

### Center man identity
**NOT Harshel (STRONG, 4 sources).** IS someone compatible with Harry Isaackovitz (age/biography) — but also compatible with other candidates:
- Unrelated Detroit friend (Opus audit's strongest alternative)
- Unrelated Fox-side social connection
- Unrelated Detroit Jewish community acquaintance

**Recommended if repaired:** label as "Belle Isle Conservatory Young Man c.1917-1918" (conservative), NOT "Harry Isaackovitz" (unconfirmed).

## Outstanding work inventory

### P0 — Gemini prompt validation
1. **Shadow eval design bug**: `scripts/session153_shadow_eval.py:278 build_prompt()` only passes `collection`, `source`, `filename` as metadata. Never passes `gedcom_context`. Yet the candidate prompt's 3-round scaffold references "biographical context" / "subject's RESIDENCE" 15+ times — it expects data it never gets. This invalidates the partial shadow eval results from 153b (`docs/feedback/session-153b-shadow-eval-results.md`).
2. **Schema drift**: `gemini_api_calls` table is missing an `experiment_id` column. Every Supabase log write in the 153b shadow eval run failed with `PGRST204`. Trivial fix: `ALTER TABLE gemini_api_calls ADD COLUMN experiment_id TEXT;`
3. **API stability**: Gemini 3.1 Pro returned 503/504 intermittently during the 153b run. The script has no retry-with-backoff.

### P0 — Harry anchor repair blockers
1. **Face-ID discrepancy**: `inbox_1fea75...` (Codex audit) vs `inbox_2bc31a40c34a` (Session 153 breakthrough doc). One of these is wrong. Resolve by grepping embeddings.npy + Supabase photo_faces + `identities.anchor_ids` JSONB.
2. **Bessie hypothesis strengthening**: need either (a) a 1910s Bessie Ancestry photo to ML-test directly, (b) multi-frame triangulation in other Belle Isle frames, or (c) kinship proximity test against her confirmed daughter Leona (ranked #15 at d=1.24 for 3009).
3. **Replacement identity label**: user decision — "Harry Isaackovich" (risky) vs "Belle Isle Conservatory Young Man c.1917-1918" (conservative — Opus audit recommendation).

### P1 — From Session 153 Codex audit
1. Belle Isle archival citation (Burton Historical Collection) — NOT DONE
2. Irving-anchor verification (seated-left man in 02068) — no Irving anchor in local cache per Codex; should check against his 8 known anchors
3. (declined by user: production `date_labels` Detroit correction)

### P2
1. Full embedding baselines run (`scripts/compute_embedding_baselines.py` still times out on Supabase `photo_faces` fetch; script committed but not run)
2. Codex CLI `--full-auto` stdin hang (same issue in Sessions 152, 153, 153b — blocks using Codex for audits)
3. Claude Chrome MCP upload_image cross-tab limitation (architectural; escalated to user in 153b — fundamental, not fixable from our side)

## Key identity IDs (verified as of 153b)

| Person | Identity ID | State |
|---|---|---|
| Albert Fox | `85546ebf-75b9-4971-a9d4-b2ce2271bc19` | CONFIRMED |
| Bessie Fox | `b4a43575-9312-40ec-a574-85bf4294d0af` | CONFIRMED |
| Harry Fox (contains 2 wrong anchors — repair gated) | `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` | CONFIRMED |
| Irving Israel Fox | `7e6aae2b-2b70-4a8a-9ee5-46e2b2c16c41` | CONFIRMED |
| Person 3007 (Detroit back-left F) | `121c9aa7-ed47-4adc-97a0-46588d5c24de` | INBOX |
| Person 3009 (Detroit back-right F — HYPOTHESIS = Bessie, POSSIBLE-trending-WEAK) | `63a1c0c1-aed2-4429-9e54-9dfae1b099d4` | INBOX |
| Person 3010 (Detroit partial bg — SKIPPED with snapshot) | `ee0f3026-1459-4cf1-b184-538acf11131d` | SKIPPED |
| Person 2510 (restored after accidental skip) | `c39e8284-871d-4a1d-88ae-888793f4b151` | INBOX |

## Key face IDs

| Face ID | Belongs to | Notes |
|---|---|---|
| `inbox_ed3f214545b9` | 3009 back-right Detroit | Target of Bessie hypothesis |
| `inbox_fad6b0654cc7` | Bessie Fox | FB photo, age ~70s — weaker anchor |
| `inbox_0ae416754174` | Bessie Fox | 02136 beach, age ~60 — stronger anchor |
| `inbox_1fea75...` vs `inbox_2bc31a40c34a` | Center man in 02068 | **DISCREPANCY unresolved.** These should be the same face (face F in the 2-face cluster F+G that is NOT Harshel) but two different face IDs were cited. |

## Key GEDCOM facts

| Person | Ancestry ID | Key facts for location/identity work |
|---|---|---|
| Albert Fox | (confirmed subject) | b.1892 Minsk; RESI Detroit 1917 + 1917-1918 single; EVEN 7 Jun 1918 draft; EVEN 5 Jul 1918 NY (Camp Devens); arrival back 28 Apr 1919; m. Esther Burd 6 May 1920 |
| Bessie Fox | — | b. abt 1884; RESI Dayton OH 1910; m. (1) had child Elizabeth Asnes ~1905; m. (2) Harry Isaackovitz 3 Jan 1911; daughter Frances b. Jan 1918 Dayton |
| Harry Isaackovitz | `@I132506612777@` in tree 162873127 | b.1881, m. Bessie 1911. **NO PHOTO in system or Ancestry tree per user.** |
| Harshel Iosha Fox (registry "Harry Fox") | — | Blond + blue eyes per naturalization record; dark-and-dark mystery man in 02068 is visibly NOT him |
| Rose Scheckzner | — | Harshel's wife, b.1884, age 33 in 1917; Dayton OH; daughter Frances b. Jan 1918; no anchor in system |

## Artifacts from 153b (full list)

| File | Purpose |
|---|---|
| `docs/prompts/session-153b-prompt.md` | Original 153b prompt |
| `docs/assessments/session-153-assessment.md` | Retroactive stub for 153 |
| `docs/assessments/session-153b-assessment.md` | Full 153b assessment |
| `docs/feedback/session-153b-bessie-validation.md` | Phase 1F synthesis |
| `docs/feedback/session-153b-bessie-ml-output.json` | Phase 1A raw output |
| `docs/feedback/session-153b-claude-multimodal-bessie.md` | Phase 1D independent agent |
| `docs/feedback/session-153b-opus-audit.md` | Phase 3 Opus audit (2961 words) |
| `docs/feedback/session-153b-coverage-audit.md` | Phase 4 — 50 user requests enumerated |
| `docs/feedback/session-153b-center-man-honest.md` | Phase 2 honest hypothesis table |
| `docs/feedback/session-153b-harry-repair-decision.md` | Phase 7 DO-NOT-EXECUTE decision |
| `docs/feedback/session-153b-shadow-eval-results.md` | Phase 5 partial — candidate FAILS Detroit gate |
| `docs/feedback/session-153b-harness-compliance-audit.md` | Audit of sessions 152+153 closeout drift |
| `docs/prds/061_event_clustering.md` | Phase 6 PRD |
| `docs/prds/062_anchor_inspector_and_repair_ux.md` | Phase 6 PRD |
| `scripts/session153b_bessie_neighbors.py` | Phase 1A neighbors script |

## Related ADs

- AD-139 (Gemini 3.1 Pro wired to Estimate)
- AD-152 (gemini_api_calls logging)
- AD-159 (gemini_config + response_summary fix)
- AD-160 (GEDCOM linking in-app)
- AD-210, AD-211 (business-name → GEDCOM owner lookup for Leon's Restaurant)
- AD-228 (ml_runs provenance schema)
- AD-229 (ML proposals / ML service defer decision)

Session 154 should create:
- **AD-241**: subject-GEDCOM-context injection in location prompts (if we add it to shadow eval)
- **AD-242**: iterative refinement with prior-prediction retry block (if we add it to the candidate prompt)

## Parallelization constraints

Files that should NOT be touched in parallel (single-agent only):
- `rhodesli_ml/gemini_extraction.py` — production pipeline, sequential changes only
- `scripts/session153_shadow_eval.py` — one agent owns at a time
- Supabase schema migrations — one agent at a time

Files that CAN be edited in parallel (different agents, different files):
- New scripts in `scripts/` (e.g., face-ID resolution script, Irving verification script)
- Docs in `docs/feedback/session-154-*`
- `docs/ml/ALGORITHMIC_DECISIONS.md` (appends-only, rare conflicts)

## Known limitations / DO NOT repeat

- **Gemini via Claude Chrome MCP is architecturally blocked** — don't retry unless MCP upload_image changes. Either user uploads manually and pastes transcript, or we use Gemini API.
- **Codex CLI `--full-auto` hangs on stdin** — don't rely on it for audits this session. Either use interactive Codex or substitute with Claude subagents.
- **Shadow eval should NOT be piped through `tail` when running — it buffers output.** Use `> /tmp/file.log 2>&1 &` to a real file.
- **Gemini API had 503/504 during 153b run** — may still be degraded. Build retry-with-backoff into the script before rerunning.

## Workflow preferences (user)

- Every session must follow the harness Session End checklist (9 steps, see `.claude/rules/session-defaults.md`).
- Sessions 152 and 153 had closeout drift — backfilled in 153b. DO NOT repeat.
- Parallelize via worktree subagents for independent work. Opus 4.7 needs explicit instruction to parallelize (it spawns fewer subagents by default than 4.6).
- Commit after every phase. /clear between phases at 300+ transcript lines.
- Never click action buttons on production (browser READ-ONLY per Lesson 149).
