# Research Desk Meta-Log — what the harness did well/badly, every session

Append one entry per session. This is the learning loop the owner asked for ("we should be doing
the meta analysis on what worked and what didn't every time").

---

## 2026-07-13 — Session 170 (the replan itself)

**Shape:** Fable main loop (orchestrating + architect) · 3 parallel Claude research agents
(1 haiku web-research, 2 sonnet repo-mining) · gpt-5.6-sol ×3 rounds (xhigh ideation → xhigh
critique → high sign-off), all via `codex exec ... </dev/null`, zero stalls on CLI 0.144.3.

**What worked:**
- **Parallel independent drafting (Fable + Sol, same brief) → adjudication → critique → sign-off.**
  Convergence was heavy and instant credibility; each model filled the other's blind spots
  (Sol: Retrieval 2.0, event engine, FB author-export, found `identification_investigations`
  table + stale `gemini-2.0-flash`; Fable: institutional archives, HTR sweep, screenshot intake,
  sealed-verdict design). Second validation of the shared-memory pattern; promoted to VALIDATED.
- **"Do the arithmetic where possible" in the critic brief.** Sol's round-2 was the highest-value
  artifact of the session BECAUSE of the math: review-queue 10h vs 3.3h budget, $4-9/night,
  0.98^12 = 78.5% morning reliability, WIP arithmetic. Over-scoping died in this round, not in
  polite prose. Keep this clause in every future critic brief.
- **Sol runs its own web searches inside codex exec** — the rights table (per-source terms with
  live citations: Ancestry/USHMM/ANU/JDC/LoC) and Meta DYI research came from Sol directly, not
  from our web agent. Sol earned its "chance to shine": pass-1 was architect-grade.
- **Delegated repo-mining to sonnet agents** (211k + 181k tokens spent there, off the main
  context) — main-loop context stayed lean for synthesis; no /clear needed mid-session.
- **Haiku for web research** was fine at the task (found Sol GA date, effort guidance,
  Terra/Luna, Fable-vs-Opus economics) at low cost.
- Effort tiering demonstrated live: xhigh where it mattered, high for the sign-off — the
  sign-off was ~1/4 the tokens of a critique round and fully sufficient.

**What didn't / to fix next time:**
- **Skipped the Lesson-182 canary**: launched 3 Claude agents at once. Got away with it (no usage
  limit), but the rule exists for a reason — next multi-agent launch starts with one canary.
- Sol's pass-1 log is 1.1MB of search/reasoning trace for a 15KB deliverable — fine, but don't
  ever cat the log into context; read only the output file. (Applied here; codifying it.)
- `sol-pass1-brief.md` promised "another model adjudicates" — in practice Fable both drafted AND
  adjudicated round 1 (disclosed in the memo, and Sol got a rebuttal round, which is the real
  safeguard). For a cleaner design, a true third party (Opus) writes the adjudication.
- The three research agents + two model drafts produced ~80KB of artifacts; a future replan can
  cap pass-1 drafts at ~half this length without losing decisions.
- Model self-report is unreliable: Sol's probe replied "GPT-5 high" while the CLI banner said
  gpt-5.6-sol/xhigh — always trust the CLI header/config, never the model's self-description.

**Cost/budget:** Anthropic-side ≈ 500k subagent tokens (research fleet) + main loop; Codex-side
3 exec runs (subscription). No usage-limit events. Well inside "didn't do something wrong."

**Next session should verify first:** session-171 Rider R P0 (tree leak) before any Desk work.

### Rev 2 addendum (same day, owner feedback on the delivered plan)

Three corrections from the owner, applied immediately:
1. **The plan was too abstract** — he couldn't map "Research Desk / lanes" onto the actual
   rhodesli product. Fixed with a "What this actually is, in concrete rhodesli terms" section
   (corpus → case queue → matcher, all writing to existing app surfaces). META-LESSON: a strategy
   doc must open with the concrete product delta, not the operating model; name real routes,
   tables, and pages.
2. **Consent-first framing came back AGAIN despite repeated prior feedback.** All three models
   (Fable, Sol, and prior Codex evals) independently over-index on consent/rights ceremony —
   this is systematic model bias, not signal. Fixed structurally: durable memory
   `feedback_deprioritize_consent_fb_capture` + strike-on-sight rule in the plan.
   META-LESSON: when the owner repeats a correction across sessions, the fix is a feedback
   memory + an adjudication rule, not just editing the current doc.
3. **"Kill FB DOM extraction" over-rotated.** The owner wants human-in-the-loop capture (he
   clicks, Claude extracts everything incl. comments + commenter names) — the boundary is
   *unattended* automation, not capture itself. Both models read the TOS constraint as broader
   than the owner's actual risk tolerance. Restored FB as the PRIMARY supply line (FB capture
   v2, companion session 172).

---

## Session 171 (2026-07-13/14) — Research Desk W1-S1+S2, first execution session

**What each model did (role · effort · tokens/cost · verdict):**
- **Opus 4.8 (orchestrator):** dispatched everything, assembled the Belle Isle evidence packet by
  hand (embeddings top-20 + co-occurrence + GEDCOM + dates via scripts), authored the artifact +
  rubric, de-slopped Fable's fixes, applied the migration, ran closeout. Never trusted a "done"
  message without checking the artifact.
- **Sol / gpt-5.6-sol (coder, medium):** R1 tree scoping (47k tok, 4 tests) · Phase 2 run contract
  (40k tok, 5 tests). Both implemented to the dispatch-shaped spec on the FIRST pass, only touched
  allowed files, ran only the bounded pytest. STRONG.
- **Sol (sealed investigator, medium):** blind verdict on the packet+images (12k tok) → ABSTAIN + DROP.
- **Sol (adversarial auditor, xhigh):** independent fresh-context audit of the code diff (Phase 3).
- **Gemini 3.1 Pro (sealed investigator):** blind multimodal verdict (~$0.09, logged) → ABSTAIN + DROP.
- **Fable 5 (architect, 1 dispatch, 135k tok):** artifact-vs-rubric review. Caught three real
  self-scoring over-claims + a rubric-degeneracy gap. STRONG — the single highest-value dispatch.

**Cost/budget:** every dispatch well under the 150k-token ceiling (Fable 135k was the max, a single
bounded review). Case prep ≈ $0.14 of the $2/night cap. No usage-limit events on Sol; one Anthropic
limit pause between Phase 2 and closeout (resumed cleanly). Inside "didn't do something wrong."

**What worked:** (1) Dispatch-shaped specs with a bounded verify command (targeted pytest, never
make test-fast — Lesson 213) got first-pass-correct code from Sol twice. (2) Running the REAL path on
ONE production item (the live `create_run` + idempotent re-run) validated the whole Phase-2 contract
against live Supabase — Lesson 208 in action. (3) Fable as artifact JUDGE (not author) is where it
earns its cost: it found that the artifact self-scored gate-13 ("one-tap write-back") YES on a static
file that has no write-back, and that gate-10 rewards boilerplate abstention levers — both trust-surface
defects on the product-defining artifact.

**What failed / friction:** (1) The sealed-verdict Gemini call logged with cost/tokens NULL —
usage_metadata capture is a runner TODO; recording an *estimated* cost in-artifact was the honest
patch. (2) R1 is a genuine design fork (the Fox GEDCOM is linked to identities across rhodes-53 and
fox-family-9) that the prompt's acceptance criterion resolved — but the fix changes how the flagship
root `/tree` behaves; flagged for owner confirmation rather than assumed.

**One lesson:** *For a product-defining artifact, use the strong model as an adversarial JUDGE of the
artifact's own honesty, not as its author.* Fable's most valuable finding was not a design idea — it
was catching the artifact grading itself dishonestly (a "one tap" that doesn't exist, an unrecorded
cost, a misdescribed model divergence). On a plan whose named #1 risk is "a trust-breaking first
artifact," self-scoring honesty IS the trust surface, and only an independent judge reliably audits it.

### Session 171 overnight addendum — W1-S3 assembler (autonomous, owner asleep)

Owner asked to "keep going while I sleep." Continued into **W1-S3** (evidence-packet assembler) —
the read-only enabling task, NOT more cases (the plan says don't generate cases until the review loop
is validated). Built `rhodesli_ml/research_desk/packet_assembler.py` (Sol medium),
**live-validated against the Belle Isle case** (reproduced the hand-built evidence + the abstention
signal exactly), independently audited (fresh-context Claude subagent — codex xhigh stalled again),
fixed 2 P1s + P2/P3, re-validated (sha256 seal now stable across runs), pushed, CI green. AD-252 +
W1-S4 prompt (`docs/prompts/session-172b-w1s4-prompt.md`) written.

**Two meta-lessons reinforced:** (1) *Running the real path on ONE production item catches what mocks
can't* — the assembler's unit tests passed but the FIRST live run hit `identities.community_id does
not exist` (schema drift, Lesson 152) and a standalone circular import; both invisible to mocks
(Lesson 208 again). (2) *The independent audit gate keeps earning its cost even on read-only tooling*
— it caught that the manifest sha256 was NOT reproducible (no ORDER BY → un-ordered derived lists),
which silently defeats the immutable-seal contract the entire run pipeline is built on. Neither the
coder nor the orchestrator's review caught it; only the adversarial pass did. **Codex xhigh stalled on
its final report a 2nd time (Session 171) — the Claude-subagent fallback is now the reliable auditor
for xhigh-class reviews; treat codex-xhigh audits as best-effort with a mandatory fallback.**
