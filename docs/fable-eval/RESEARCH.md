# Fable 5 Full-Evaluation — Research Log

**Date:** 2026-07-02 · **Author:** Opus 4.8 (1M) orchestrator + Codex gpt-5.5/xhigh (independent) · **Repo:** rhodesli

Purpose: capture everything known about Fable 5's edges + prompting so the synthesized
evaluation prompt exploits what Fable can do that Opus/Sonnet/Codex cannot. Feeds
`FABLE_EVAL_PROMPT.md`. Sources are primary (Anthropic docs) + community (X/Reddit, practitioner blogs).

---

## 1. Timing / why now (time-sensitive)

- Fable 5 returned to availability **2026-07-01**. Included in Pro/Max/Team subs for up to ~50%
  of weekly limits **only through ~July 7, 2026**, then moves to **pay-per-use**.
- **Implication (the highest-leverage community tip):** use Fable NOW — while it's effectively
  free — to **write reusable SKILLS that teach Opus 4.8 how to think**, so the "everyday" model
  inherits Fable's judgment before Fable gets expensive. (Sisinty/Reddit r/ClaudeAI oj93-rd.)

## 2. Fable 5 capability edges over Opus 4.8 (Anthropic docs, primary)

Source: platform.claude.com "Prompting Claude Fable 5".

1. **Long-horizon autonomy** — sustains productive output over extended periods; multi-day,
   goal-directed runs with strong instruction retention. *(This is THE edge to exploit — one
   long autonomous run, not many short ones.)*
2. **First-shot correctness on complex, well-specified problems** — single-pass implementations
   of systems that previously took days of iteration.
3. **Vision** — interprets dense technical images, web apps, detailed screenshots with
   substantially higher accuracy, often with fewer tokens; uses bash/crop tools on noisy images.
   *(→ Fable is the vision-QA authority for the live-site audit.)*
4. **Code review & debugging** — bug-finding recall noticeably higher than Opus, including search
   across codebases and repository history.
5. **Navigating ambiguity** — performs well on complex, multi-threaded requests where it must
   determine next steps.
6. **Delegation** — significantly more dependable at dispatching + sustaining parallel subagents;
   manages ongoing comms with long-running subagents. Prefer async over blocking.

Not for: offensive cybersecurity, bio/life-sciences (safety classifiers → `stop_reason: refusal`
→ fallback to Opus). Not relevant to rhodesli.

## 3. Fable-native prompting rules (primary + community, converged)

- **Goals, not checklists.** Micromanaging that helped older models *drags Fable down*. Give the
  objective + constraints; let it figure out the how.
- **One big brief beats twenty small ones.** Full context + full constraints in the FIRST message.
- **Effort = high by default; xhigh only for the hardest work.** Low/medium on Fable still beat
  xhigh on prior models. No temperature control; thinking can't be disabled.
- **Anti-overplanning:** "When you have enough information to act, act. …give a recommendation,
  not an exhaustive survey."
- **Anti-tidying at high effort:** "Don't add features, refactor, or introduce abstractions
  beyond what the task requires… do the simplest thing that works well."
- **Ground progress claims:** "Before reporting progress, audit each claim against a tool result
  from this session. Only report work you can point to evidence for." (Near-eliminates fabricated
  status.)
- **State boundaries:** when the user is asking/thinking-out-loud, the deliverable is the
  assessment — report and stop; don't apply a fix until asked. Check evidence supports a
  state-changing command before running it.
- **Memory system:** one lesson per file, one-line summary at top; record corrections +
  confirmed approaches + why; update don't duplicate; delete wrong notes. (Fable extracts ~3×
  the gain Opus does from file memory.)
- **Self-verification:** fresh-context verifier subagents beat self-critique. "Establish a method
  for checking your own work at an interval… verifying with subagents against the specification."
- **Autonomous-run reminder:** "You are operating autonomously. The user is not watching… For
  reversible actions that follow from the original request, proceed without asking… Before ending
  your turn, check your last paragraph. If it is a plan, a question, or a promise ('I'll…'), do
  that work now with tool calls."
- **DO NOT ask it to echo/transcribe/explain its reasoning as response text** — triggers the
  `reasoning_extraction` refusal category → elevated fallbacks to Opus. Audit skills/prompts for
  "show your thinking" language before running Fable.
- **"You have ample context remaining. Do not stop, summarize, or suggest a new session."** —
  prevents mid-run context-budget anxiety on long runs.
- **Give the reason, not only the request** — intent context improves output.
- **Refactor old prompts/skills** — over-prescriptive scaffolding degrades Fable. Three buckets:
  constraints (keep), calibration (refresh), scaffolding (likely delete).

## 4. Community "do this now with Fable 5" tasks (the four tweets)

- **Vox (@Voxyz_ai):** don't jump into code — run a **read-only full health check** first:
  disk eaters, folder mess, bloated CLAUDE.md tokens, installed-but-unused skills/MCP servers,
  over-wide permissions. Rank every issue by impact×effort with the exact action. Staged cleanup
  plan; flag moves/deletes for one-by-one approval. **Save the flow as a reusable skill; rerun
  quarterly.**
- **Fishbein (@mfishbein):** 5 prompts — (1) review ROADMAP.md → detailed dev task list + tests
  that prove it works → `/goal` build overnight; (2) "here's the tool: [idea]" → full spec + test
  suite + build + browser-control every user flow + loop until pass + suggest improvements;
  (3) browser every page of a SaaS you pay for → write a PRD to build your own; (4) rebuild the
  codebase from scratch, old version = spec, 10x better, tests capture everything, loop until
  pass; (5) review codebase → what features make it 10x more valuable → roadmap with acceptance
  criteria.
- **Sisinty (@VaibhavSisinty):** give it your HARDEST problem; one big brief; effort high (xhigh
  for complex); give it a memory file; tell it to VERIFY its own work before reporting progress;
  delete old Opus prompts (too prescriptive); **use Fable now to write skills for Opus 4.8.**
- **Reddit (r/ClaudeAI, oj93-rd):** friendly reminder to have Fable write skills NOW to tell Opus
  4.8 how to behave/think once Fable is pay-per-use. Caveat: author couldn't prove the skills
  helped or share them (project-specific) — so we build our own + measure.

## 5. How this maps to a rhodesli full-evaluation (synthesis thesis)

The evaluation is ONE long autonomous Fable run organized as GOALS across six workstreams, each
chosen to exploit a specific Fable edge:

| Workstream | Fable edge exploited | Deliverable |
|---|---|---|
| W1 Repo/harness/machine health audit (read-only) | ambiguity + bug-recall + repo-history search | `HEALTH_AUDIT.md` |
| W2 Live-site product+UX+VISION audit (read-only prod) | **vision** | `SITE_AUDIT.md` + screenshots |
| W3 10x growth-avenue discovery w/ acceptance criteria | ambiguity + product judgment | `GROWTH_10X.md` |
| W4 **Reusable-SKILL extraction for Opus 4.8** (highest leverage) | judgment distillation | new skills + `SKILLS_WRITTEN.md` |
| W5 Code-quality + bug-recall sweep (write paths, split-brain) | **bug-finding recall** | `CODE_FINDINGS.md` |
| W6 Package reusable + self-improving (loop engineering) | long-horizon meta-work | the skill + `META_LESSONS.md` |
| Cross-cutting | measure Fable-unique value | `EVALS.md` scorecard |

Plus: implement the **LOW-RISK** subset of findings with tests + commits (make the site
impressive) while respecting the multimodel-sprint EXCLUSION list.

## 6. Guardrails (from docs + rhodesli harness)

- **Read-only on production** (absolute — Lesson 149 / browser-read-only.md). No clicking
  data-mutating buttons on the live site.
- **EXCLUSION list** (multimodel-sprint): no prod-data mutation, no schema/migration, no
  paid-Gemini spend over a stated cap, no global head/nav/layout changes, frozen files
  (`core/neighbors.py`, `core/pfe.py`, `data/*`) untouched. These go to "user decisions."
- **No reasoning-extraction language** in the prompt (avoid Fable refusal→fallback).
- **Independent-audit gate** before any push (multimodel ML-1): Fable does NOT push; the
  orchestrator runs an independent audit, then gates.
- **Local gate mirrors CI** (Lesson 209): ruff + targeted tests; simulate CI's missing deps/data
  (Lessons 210/211).

## Sources
- [Anthropic — Prompting Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5) (primary)
- [ProductCompass — Fable 5 guide](https://www.productcompass.pm/p/claude-fable-5-guide)
- [DigitalApplied — 10 Fable 5 prompts](https://www.digitalapplied.com/blog/fable-5-prompts-upgrade-ai-agent-setup-2026)
- [Vox @Voxyz_ai](https://x.com/Voxyz_ai/status/2072604608669593830) — read-only health check + reusable skill
- [Mike Fishbein @mfishbein](https://x.com/mfishbein/status/2072438234504646852) — 5 prompts
- [Vaibhav Sisinty @VaibhavSisinty](https://x.com/VaibhavSisinty/status/2072613763979915620) — operational tips + write-skills-for-Opus
- r/ClaudeAI (oj93-rd) — write skills for Opus 4.8 now
