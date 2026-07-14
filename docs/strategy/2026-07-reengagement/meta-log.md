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
