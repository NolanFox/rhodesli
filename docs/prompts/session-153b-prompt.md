# Session 153b — Fresh-Context Continuation: Honest Validation + Gap Closure

**Mode:** Interactive identification + research (fresh context required)
**Predecessor:** Session 153 (14 commits, ending at `4cb2ed98` or later)
**Why 153b not 154:** User judgment — Session 153 accumulated too much context for honest re-validation. Treat this as a continuation of 153, not a new session.

## Orientation

**MANDATORY first read (in order):**

1. `docs/feedback/session-153-what-weve-done.md` — single plain-English summary of Session 153. This replaces the 14-file trail as your primary reference.
2. `docs/prompts/session-153-prompt.md` — original Session 153 prompt (the continuation of Session 152's Fox family work)
3. `docs/feedback/session-153-harry-isaackovitz-breakthrough.md` — **READ WITH SKEPTICISM**. Claude 153 over-claimed: the document says "user-confirmed via Ancestry" but the Ancestry lookup only proves Harry Isaackovitz EXISTS. It does NOT confirm the center man IS Harry Isaackovitz. No reference photo exists. Multi-model agreement was on "NOT Harry Fox," NOT on "IS Harry Isaackovitz."
4. `docs/feedback/session-153-corrective-analysis.md` — honest 3007/3009 re-analysis
5. `docs/feedback/session-153-codex-harry-audit.md` — 4th independent "NOT Harshel" confirmation
6. `docs/feedback/session-153-gemini-harry-validation.md` — Gemini 3.1 Pro API validation (note: Chrome fallback was WRONG — see below)
7. `tasks/lessons.md` — Lessons 171-172 + any new lessons from session 153
8. `docs/feedback/session-153-feedback.md` — FB-001 through FB-005

Session setup:
```bash
echo "153b" > .claude/current_session.txt
echo "interactive" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh
```

## Non-negotiable operating rules for this session

1. **Do NOT conflate "not-Harshel" with "is-Harry-Isaackovitz".** No model has a reference photo of Harry Isaackovitz. The positive identification is NOT triangulated.
2. **Use Claude Chrome (NOT Playwright) for Gemini multimodal.** User explicitly insisted; they are logged in. If Chrome MCP tool errors: RETRY (see `.claude/memory_backup/feedback_retry_tools.md` — "Never give up on tools after first failure"). Re-fetch `mcp__claude-in-chrome__tabs_context_mcp` with `createIfEmpty`. Wait 5s and retry. Do NOT fall back to Gemini API or Playwright.
3. **Browser READ-ONLY on production** (`.claude/rules/browser-read-only.md`). Never click action buttons.
4. **Do NOT execute the Harry Fox anchor repair** until you have resolved:
   - The face-ID discrepancy (Codex found `1fea75...`, Session 153 breakthrough doc said `2bc31a40c34a`)
   - Whether 3009 is actually Bessie (ungates the repair narrative)
   - Positive identification of the replacement identity (Harry Isaackovitz vs "unknown young man")
5. **Honest confidence language.** "STRONG / GOOD / POSSIBLE / WEAK / UNKNOWN" — not "confirmed" unless triangulated. Track sources explicitly.

---

## Phase 1 — Bessie Fox systematic validation (THE CRITICAL GAP)

Session 153 did Harry Fox validation in 3 models but SKIPPED the equivalent for 3009 = Bessie Fox. User flagged this. Do it now.

### Phase 1A — Local ML similarity
Run `scripts/compute_embedding_baselines.py` if it hasn't succeeded yet (Session 153 attempt failed on Supabase statement timeout; add smaller page size flag or filter). Then:

For face `inbox_ed3f214545b9` (Person 3009 back-right woman):
- Compute top-20 neighbors across ALL identities (not just Fox)
- Rank by distance + report source (CONFIRMED vs INBOX, community)
- Separately compute distance to Bessie's 2 anchors individually:
  - `inbox_fad6b0654cc7` (FB photo, age ~70s)
  - `inbox_0ae416754174` (02136 beach, age ~60)
- Check Bessie internal self-consistency (d ≈ 1.08 per prior work)
- Caveat cross-age explicitly

### Phase 1B — Gemini 3.1 Pro via **Claude Chrome** (not Playwright, not API fallback)
Attach both photos to a Gemini chat:
- Photo containing 3009 face bbox (crop `/Users/nolanfox/rhodesli/raw_photos/02068_p_13akf5twbc3600.jpg` — 3009 is back-right standing woman; see `docs/feedback/session-153-corrective-analysis.md` for bbox coordinates)
- Both known Bessie anchor photos (`raw_photos/15036201_1414627595229094_2569001315822491926_n.jpg` — elderly Bessie; `raw_photos/02136_p_13akf5twbc1202.jpg` — 2-women beach)

Ask Gemini to compare the 3009 face (identify it by position in the group) to the Bessie reference photos. Specifically:
- Is this the same person, just younger?
- What facial features support or reject the match (bone structure, nose, eyes, ear shape, jawline)?
- What confidence does Gemini assign?
- What would convince it either way?

If Chrome MCP fails: RETRY 3+ times per `feedback_retry_tools.md`. Only escalate to user if 3+ retries fail.

### Phase 1C — Codex CLI independent audit
Run Codex with the 3009 face + Bessie anchor context. Ask:
- Is 3009 = Bessie Fox? Confidence?
- What's the strongest alternative hypothesis?
- What's needed to increase confidence?

### Phase 1D — Claude Chrome multimodal subagent (**MISSING in Session 153 — DO THIS**)
User's Session 153 request included THREE validation paths, not two: Codex + Gemini-via-Chrome + "another subagent investigate it in claude chrome and figure out how to use the new multimodal skills of the recent model." The third path was never launched. Do it now.

Launch a subagent that:
- Uses Claude Chrome tools to open both Bessie anchor photos AND the 3009 face crop in Chrome tabs
- Uses Claude's own multimodal vision (pass images via Read tool, or via the agent inheriting multimodal capability) to produce an independent visual assessment — NOT via Gemini
- Compares bone structure, eye shape, ear shape, jawline across the 3 images
- Produces its own confidence rating independent of ML embedding numbers

### Phase 1E — Claude (this session) visual comparison
Use Read tool to view the photos directly. Write an honest visual assessment — is 3009 visibly the same bone structure as Bessie's anchors, given 35-year age gap?

### Phase 1F — Synthesis
Write `docs/feedback/session-153b-bessie-validation.md` with:
- Per-source verdict (Local ML / Gemini-via-Chrome / Codex / Claude)
- Honest confidence level (WEAK / POSSIBLE / GOOD / STRONG)
- Contradictions between sources (there will be some — be honest)
- What would settle it (e.g., a 1910s Bessie photo from Ancestry)

---

## Phase 2 — Center man: honest hypothesis table

With the over-claim corrected, re-frame the center man options:

| Candidate | Age in 1917 | Biography fits? | Reference photo available? | Can any model confirm positively? |
|---|---|---|---|---|
| Harry Fox (Harshel) | 35-36 | Brother of Albert | YES (Harshel ID card) | Triangulated: NOT him |
| Harry Isaackovitz | 36 | Bessie Fox's husband, Ancestry record exists | NO (per user) | NO — can only confirm "not-Harshel" |
| An unrelated Fox-side relative or friend | ~30s | Possibly | NO | NO |
| An unrelated Detroit Jewish community member | ~30s | Possibly | NO | NO |

**Deliverable:** `docs/feedback/session-153b-center-man-honest.md` — clearly stating what we actually know vs what's speculation.

---

## Phase 3 — Independent audit by a different model (Opus 4.6/4.7 1M context)

User asked for this explicitly. Launch:

```
Agent(
  subagent_type="general-purpose",
  model="opus",   # the Agent tool enum only supports sonnet/opus/haiku
  description="Opus independent audit",
  prompt="Fresh-context audit of session-153's identification work. ..."
)
```

**Important note for this audit:** the Agent tool's `model` enum only accepts `sonnet|opus|haiku` — we cannot guarantee Opus 4.6 vs 4.7. Document which model actually ran. If the user strictly requires 4.6, fall back to calling the Anthropic API directly via Bash with the specific model ID.

The audit should:
- Read `docs/feedback/session-153-what-weve-done.md`
- Read the 4 Harry verification files and independently assess the "not-Harshel" conclusion
- Review Claude's reasoning for over-claiming Harry Isaackovitz
- Run the Bessie validation independently
- Flag other cognitive errors: premature closure, confirmation bias, etc.
- Output: `docs/feedback/session-153b-opus-audit.md`

---

## Phase 4 — Coverage audit of ALL original prompts

User feels Session 153 didn't cover everything in their original requests. Launch a dedicated agent to read EVERY message in this session's transcript equivalent (the user prompts stored in the prompt file + any subsequent messages) and produce:

- Bullet list of every specific user request
- Status per request: DONE (with artifact link) / PARTIAL (what's missing) / NOT DONE (why)
- Gap inventory ranked by user-stated priority

Written to `docs/feedback/session-153b-coverage-audit.md`.

**Specific items to verify coverage on (from Session 153 transcript):**
- [ ] 3007 investigation — visual comparison against 3103 / Bessie / Sadie
- [ ] 3101/3103 beach photos co-occurrence
- [ ] Person 2516 investigation (1:1 with Esther, always in beach photos)
- [ ] Children in beach photos — who are they?
- [ ] Person 2510 vs Person 3079 merge hypothesis
- [ ] UX fix for accidental-skip (DONE, committed, needs deploy verification)
- [ ] Belle Isle archival citation (Burton Historical Collection)
- [ ] Gemini prompt shadow-eval run
- [ ] Embedding baselines run (failed on timeout — needs retry)
- [ ] Event-clustering PRD (research done, PRD not written)
- [ ] Anchor-vs-candidate repair UX PRD (FB-001, not written)
- [ ] Production `date_labels` correction — user said skip this
- [ ] All research/agent outputs documented

---

## Phase 5 — Run the rate-limit-blocked work + explicit Detroit regression gate

1. `scripts/compute_embedding_baselines.py` — failed with Supabase statement timeout. Fix: reduce SUPABASE_PAGE_SIZE, add WHERE clauses to limit scope, or fetch per-family instead of global.

2. `scripts/session153_shadow_eval.py` — rate-limit blocked. Can now run.

   **Explicit Detroit regression gate (the user called this out — don't soften it):**
   - The test set MUST include BOTH known-Detroit conservatory photos as positive controls:
     - Photo `02068_p_13akf5twbc3600.jpg` (`b39d6cbe7fe63fca` in URL form)
     - Photo `91b6f6b296e93a60` (Session 143 reference, second conservatory frame)
     - Optionally also `01659_p_13akf5twbc5249.jpg` as the third frame
   - The candidate prompt (3-round scaffold) MUST predict Detroit / Belle Isle for ALL Detroit photos at ≥medium confidence
   - The baseline prompt will almost certainly say NYC for at least 2 of them (that's the bug we're fixing)
   - Additionally test ≥7 other known-location photos (Rhodes, Tampa, Dayton, Miami, Newspapers) to catch regressions on non-Detroit photos
   - PASS criterion: candidate prompt ≥20% better Top-1 accuracy than baseline AND zero regressions (no photo where candidate is wrong and baseline was right)
   - If candidate prompt fails any Detroit photo: do NOT recommend deployment; investigate which signal is missing
   - Log ALL runs to `gemini_api_calls` with `experiment_id=session153b_shadow_eval_<ts>` (never to `date_labels`)

3. **After shadow-eval passes on Detroit:** propose permanent deployment as a separate PR with reviewer checkoff, NOT as part of 153b. Deployment is a separate decision from validation.

---

## Phase 6 — Write two PRDs (research already complete — just codify)

Both PRDs have underlying research already committed. This phase is codification + implementation plan, not fresh research.

1. **`docs/prds/061_event_clustering.md`** — "Photos taken at the same time" auto-grouping
   - Foundation: `docs/feedback/session-153-event-clustering-research.md` (agent `af0449b5` output, 191 lines)
   - Key findings from the research:
     - Apple Photos' two-pass architecture (clothing within event + face across events) is the direct existence proof
     - `core/temporal.py` already vendors CLIP — no new dependencies needed for Tier 2
     - Existing `scripts/event_grouping.py` + `rhodesli_ml/data/event_groups.json` already implements Tier-1 for Esther/Albert only (18 groups, 246/554 dated photos) — generalizing community-wide is ~1 session
     - Recommended: Tier 1 rule-based (shared identities + clothing + location + filename), Tier 2 CLIP scene embedding after Tier 1 validates
   - The PRD must include the Belle Isle case as a hand-verified positive: 02068 + 91b6f6b296e93a60 + 01659 should cluster as one event
   - Validation gate: 30-pair labeled set, ≥85% precision before shipping
   - Note honest prioritization: this is #2 behind PRD-059 Phase 4 closure per the research agent

2. **`docs/prds/062_anchor_inspector_and_repair_ux.md`** — Product-level misassignment repair
   - Foundation: `docs/feedback/session-153-feedback.md` FB-001
   - Capabilities: identity health score, anchor inspector grid, one-click split, Ancestry link repair in same flow, visual side-by-side anchor comparison
   - Tie-in: the Harry Fox misassignment we found in Session 153 is the canonical test case — would admin-surface tools have let you catch and fix it without a Claude Code session?

Write BOTH PRDs even if they land behind other priority work. This PRD writing is the deliverable, not the implementation.

---

## Phase 7 — Harry Fox anchor repair (ONLY if Phase 1-4 clear it)

All must be true before mutation:
- [ ] 3009 = Bessie Fox validated at POSSIBLE+ confidence across 3 sources
- [ ] Face IDs F + G verified (resolve the 1fea75 vs 2bc31 discrepancy)
- [ ] Replacement identity label decided (user choice: "Harry Isaackovich" explicit, or "Unknown Young Man — Belle Isle c.1917" conservative)
- [ ] Backup snapshot saved
- [ ] Audit_log metadata drafted
- [ ] Structural tests pass

If any fail: do NOT execute. Document the blocker.

---

## Data safety reminders

- Snapshots before every mutation: `backups/session-153b/{identity-id}-before-{UTC-ts}.json`
- `make test-fast` before every commit
- Browser READ-ONLY on production
- `/clear` after every commit (Opus 4.7 recall cliff at 300 transcript lines)
- NEVER use `--no-verify`
- Write to `gemini_api_calls` for experiments (experiment_id=`session153b_*`); never `date_labels` without human review

## Success criteria

By end of Session 153b:
1. Honest multi-source Bessie = 3009 validation posted
2. Either repair executed OR repair-blockers clearly documented
3. Coverage audit shows 0 user requests marked "NOT DONE" without justification
4. Opus independent audit posted
5. Both PRDs (061 event clustering, 062 anchor UX) written or explicitly declined

## Key identity IDs (verified as of 2026-04-18)

| Person | Identity ID | State |
|--------|-------------|-------|
| Albert Fox | `85546ebf-75b9-4971-a9d4-b2ce2271bc19` | CONFIRMED |
| Bessie Fox | `b4a43575-9312-40ec-a574-85bf4294d0af` | CONFIRMED |
| Harry Fox (contains 2 wrong anchors) | `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` | CONFIRMED |
| Irving Israel Fox | `7e6aae2b-2b70-4a8a-9ee5-46e2b2c16c41` | CONFIRMED |
| Person 3007 (Detroit back-left F) | `121c9aa7-ed47-4adc-97a0-46588d5c24de` | INBOX |
| Person 3009 (Detroit back-right F) — HYPOTHESIS = Bessie | `63a1c0c1-aed2-4429-9e54-9dfae1b099d4` | INBOX |
| Person 3010 (Detroit partial bg) | `ee0f3026-1459-4cf1-b184-538acf11131d` | SKIPPED |
| Person 2510 (restored after accidental skip) | `c39e8284-871d-4a1d-88ae-888793f4b151` | INBOX |

| GEDCOM reference | Ancestry ID | Note |
|---|---|---|
| Harry Isaackovich (Isaackovitz) | `@I132506612777@` | tree 162873127, b.1881, Bessie's husband m.1911. **NO PHOTO EXISTS.** |
| Harshel Iosha Fox (real Harry) | — | blond/blue per naturalization record |

## Anti-pattern Claude must avoid in 153b

From Session 153 post-mortem:
- ❌ Treating "multi-source agreement on X is NOT Y" as "multi-source agreement on X IS Z"
- ❌ Running Harry validation but skipping Bessie validation
- ❌ Falling back to Playwright/API when Claude Chrome fails once
- ❌ Proactively declaring session done without coverage verification
- ❌ Generating 14 doc files without a single plain-English summary
- ❌ Launching 2 validation agents when user asked for 3 (Codex + Gemini + **Claude Chrome multimodal** — the last one was missed)
- ❌ Writing PRDs without explicit reference to the underlying research docs
- ❌ Shadow-eval criteria that don't require both known-Detroit photos to pass

Session 153b MUST NOT repeat these.

## Explicit success gates (binary checks — either met or not)

| Gate | Met by |
|---|---|
| Bessie Fox 3-model + multimodal validation complete | Phase 1F synthesis with 4 independent source verdicts |
| Center-man hypothesis table honest | Phase 2 doc distinguishes confirmed-NOT-Harshel from unconfirmed-IS-Harry-Isaackovitz |
| Opus 4.6/4.7 independent audit | Phase 3 doc exists with fresh-context Opus output |
| Coverage audit: 0 NOT-DONE without justification | Phase 4 doc lists every user-prompt item from Sessions 152+153 |
| Gemini shadow-eval passes on both Belle Isle photos | Phase 5 results show candidate prompt identifies Detroit for 02068 AND 91b6f6b296e93a60 |
| PRD-061 + PRD-062 exist | Phase 6 files committed |
| Harry repair executed OR blockers documented | Phase 7 decision recorded |
