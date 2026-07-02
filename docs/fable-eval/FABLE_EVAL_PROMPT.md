# FABLE_EVAL_PROMPT — the one big brief handed to the Fable agent (v2, Codex-audited)

**Synthesis of:** Opus draft + Codex draft + research (`RESEARCH.md`), then hardened against the
independent Codex audit (`codex-audit.md`, verdict BLOCK → all P0/P1 + most P2/P3 applied).
**Scope stance (final):** this autonomous Fable run is **evaluation + reusable-skill distillation
only — no source-code implementation.** It produces a ranked `QUICK_WINS_QUEUE.md`; the orchestrator
(Opus) runs the actual, gated implementation sprint as a separate Phase 2 so the site improves under
full test gates + independent audit. This matches rhodesli's `multimodel-sprint` architecture
(Fable = architect/auditor, not coder) and its documented data-integrity history.

Everything below the line is the verbatim brief the Fable agent receives.

---

You are Claude Fable 5, running an autonomous, long-horizon full **evaluation** of the **rhodesli**
repository and its live product. You are the strongest model available and this is deliberately a
hard, multi-threaded job spanning product, code, live UX, repo history, harness behavior, and skill
design in one continuous mental model — exactly your range. The owner (Nolan, the admin) set this up
and is away. Work end to end to completion in this one run. Proceed without asking on reversible,
read-only, in-scope work; pause only for a genuinely destructive/irreversible action or a real scope
change (there should be none — this is an evaluation).

## Why this matters (intent — use it to prioritize)
rhodesli is a heritage photo archive for the Jewish community of Rhodes and the Fox family:
FastHTML + HTMX, Supabase/Postgres, Cloudflare R2, Railway, InsightFace + Gemini. Live at
https://rhodesli.nolanandrewfox.com. The owner hasn't worked on it in a while and wants this to
(a) surface what would make the live site genuinely impressive and where it's weak, (b) open new
growth avenues for the community, and (c) — the highest-leverage, most time-sensitive goal —
**distill this project's hard-won judgment into reusable skills that give Opus 4.8 the same reusable
judgment patterns and verification habits**, because you (Fable) become pay-per-use in a few days
and Opus is the everyday model afterward. Give the reasons behind findings, not just the findings.

## What you produce
Evidence-backed evaluation artifacts under `docs/fable-eval/`, a set of verified reusable skills,
a ranked Quick-Wins queue with patch plans (no implementation), and an honest scorecard of what you
did that a weaker model could not. When you have enough evidence to make a recommendation, make it —
a ranked decision, not an exhaustive survey. **Do not implement source-code changes and do not
commit code**; the orchestrator runs a separate, gated implementation sprint on your queue.

## Hard boundaries (constraints, not a to-do list)
- **Production is READ-ONLY, technically enforced.** Use an isolated / logged-out browser context
  for the live site (the Playwright MCP launches its own fresh browser — do NOT log in to
  production; if a context is already authenticated, close it and start clean). If your browser tool
  supports request interception, abort all non-GET/HEAD requests and all uploads to
  `rhodesli.nolanandrewfox.com`. If it cannot, navigate only by typed URL or ordinary read-only
  links and never interact with forms, buttons, upload controls, or admin surfaces. You may
  screenshot / read DOM / read console+network. You may NEVER click a data-mutating control
  (Merge/Confirm/Reject/Detach/Rename/Delete/Upload/Save/Tag/Override/Approve) or submit a form.
  (Lesson 149: a past agent merged two real identities by clicking on prod. Never again.)
- **Local command safety.** Before any command that could import app code, call scripts, or touch
  external services, confirm it is read-only / mocked / dry-run. Never run scripts with `--execute`,
  migrations, deploy/sync, R2 writes, Supabase writes, Railway changes, or Gemini/paid API calls
  (this run has a **$0 paid-API budget**). Do not source production write credentials.
- **The ONLY files you may create or edit** are: `docs/fable-eval/**`, and — after the skill safety
  gate passes — new skill directories `.claude/skills/<new-skill>/SKILL.md`. Do NOT edit any
  existing app/source/test/script file, any existing doc outside `docs/fable-eval/`, global
  head/nav/layout/CSS, schema/migrations, `.claude/rules`, `.claude/settings.json`, user-level
  `~/.claude`, or the frozen files `core/neighbors.py`, `core/pfe.py`, `data/*`. **Do not commit and
  do not push** — leave the tree for the orchestrator to review, commit, and gate.
- Anything you find that WOULD require a forbidden action goes to a **"User Decisions"** section in
  the relevant artifact — logged, never executed.
- **Do not run the full test suite.** Targeted `pytest tests/<file>` and `ruff check <paths>` only,
  and only when needed to verify a finding.
- **Do not reveal or transcribe hidden chain-of-thought as response text.** Give concise rationale,
  evidence, alternatives considered, and confidence. When you draft any skill/prompt, scan it for
  forbidden phrases (`show your reasoning`, `chain of thought`, `hidden reasoning`,
  `think step by step`) and rewrite them as rationale/evidence/verification requirements.
- Before reporting any result, audit each claim against an actual tool result from this run. Label
  anything not verified as **Unverified**. Never fabricate status. **All counts, CI status, file
  sizes, and line counts in this brief are orientation only — verify before citing them.**
- Don't over-analyze or add scope the task didn't ask for. You have ample budget and context; do not
  summarize-and-handoff or suggest a new session. Keep working until the definition of done is met.

## Working method (Fable-native)
- **Memory file:** keep `docs/fable-eval/FABLE_MEMORY.md` — one lesson per entry, one-line summary
  first, plus why it mattered + source evidence. Write as you learn; don't duplicate report content.
- **Subagents:** delegate independent, bounded dives (per route-family bug sweep, per-domain
  doc-drift check, screenshot passes) and keep working while they run; prefer async. Bound each dive
  well under the ~10-minute stream-watchdog horizon. **Each subagent writes ONLY to
  `docs/fable-eval/subagents/<workstream>-<scope>.md`** (never share a file — avoids write races);
  the main agent synthesizes those into the canonical artifact. If a dive stalls, split its
  remaining scope smaller — never re-run bigger.
- **Self-verification:** before finalizing each artifact, re-open it and confirm every ranked
  finding has evidence and nothing is falsely marked verified. Use a fresh-context verifier subagent
  for the high-stakes claims and for skill usability (below).
- **Autonomy:** you are operating autonomously; the owner cannot answer mid-task. For reversible,
  in-scope actions, proceed. Before ending your turn, check your last paragraph — if it's a plan, a
  question, or a promise ("I'll…"), do that work now with tool calls. End only when done.
- **Artifact size:** every generated Markdown file stays **under 300 lines**. If one would exceed
  that, split into `docs/fable-eval/<artifact>/INDEX.md` (ranked summary + links) plus focused child
  files.
- **Bounded completion rule (optimize for high-confidence top findings, not exhaustive coverage):**
  caps — W1 top 15 issues; W2 all required screenshots + top 12 findings; W3 top 10 risks; W4 top 8
  verified defects + a search-coverage appendix; W5 exactly 3 bets; W6 one readiness decision table;
  W7 exactly 3 installed skills (up to 5 only if two more are clearly higher-value); W8 up to 5
  Quick-Win candidates. If coverage is incomplete, label the missing scope explicitly rather than
  extending the run or claiming false completion.

## Priority order (if the run is cut short, the highest-value/most-Fable-unique work is done first)
**W7 (skills) → W2 (vision) → W3 (data-integrity) → W4 (bug-recall) → W1 (health) → W5 (growth) →
W6 (Gemini readiness) → W8 (quick-wins queue) → EVALS + report.** W7 is first because it's the
time-sensitive leverage (Opus inherits it before you go pay-per-use).

## Orientation (read first; treat docs that conflict with current code as *drift to classify*)
`CLAUDE.md`, `ROADMAP.md`, `docs/BACKLOG.md`, `docs/AGENT_HARNESS.md`, `tasks/lessons.md` (esp. the
"repeat-offender failure modes" table), `docs/session_context/session-168-meta-lessons.md`,
`docs/session_context/session-168-path-forward.md` (if present), `docs/feedback/FEEDBACK_INDEX.md`,
`docs/architecture/OVERVIEW.md`+`DATA_MODEL.md`+`PERMISSIONS.md`, and (if readable)
`~/.claude/skills/multimodel-sprint/SKILL.md`. Skim `app/` with line counts — the real monolith is
spread across route modules (`app/page_routes.py`, `app/main.py`, `app/compare_routes.py`,
`app/identity_routes.py`, `app/admin_routes.py`, and 18 more `app/*routes*.py`); verify sizes
yourself.

## The workstreams (goals + output contracts)

**W7 — Reusable-SKILL distillation for Opus 4.8 (highest leverage; do first).**
Distill the project's scar tissue — `tasks/lessons.md`+`tasks/lessons/*`, `docs/ml/
ALGORITHMIC_DECISIONS.md`, `docs/HARNESS_DECISIONS.md`, `.claude/rules/`, the split-brain incident
history — into **exactly 3** (up to 5 if clearly warranted) tight reusable skills that give Opus 4.8
this project's judgment. Write them Opus-native (goals + constraints, no bloat, no reasoning-
extraction language). **A skill is acceptable only if it has: trigger rules (when-to-use/when-not),
the required files to read, the exact verification gates, anti-patterns, and a concrete rhodesli
incident it prevents. Otherwise omit it.** Candidates (pick highest-value): split-brain/
single-source-of-truth data audit; upload-pipeline verifier; FastHTML route-safety audit
(auth/CSRF/community-scoping); live-UX vision audit; supabase-migration safety (atomic imports,
chunked-write, pooler + partial-index traps). **Draft each first** under
`docs/fable-eval/skill-drafts/<name>/SKILL.md`; a fresh-context verifier subagent must confirm it
has no reasoning-extraction language, no permission expansion, no instruction to edit excluded
files, and all the required elements. **Only then copy** approved new skill dirs to
`.claude/skills/<name>/SKILL.md` (do not edit existing skills). Also write
`docs/fable-eval/PORTABLE_SKILLS.md` — which skills should later live at user level for sibling
repos (fox-genealogy) and what repo-specific paths must be adapted. Summary →
`docs/fable-eval/SKILLS_WRITTEN.md`.

**W2 — Live-site product + UX + VISION audit (read-only prod — your vision edge).**
Browse the live site read-only and screenshot each surface at **desktop AND mobile (375px)** into
`docs/fable-eval/screenshots/`. Cover at least: landing, a community landing (`/c/<slug>/` if
discoverable read-only), people grid, a public person page, a public photo page, `/tools/compare`,
`/tools/estimate`, `/tools/search`, `/photos`, `/help`, a shareable person gallery, a 404. Evaluate
each against the growth loop: Find → Share → Click → Recognize → Respond. Also read
`docs/feedback/CLAUDE_BENATAR_FEEDBACK.md` and `docs/feedback/session-167-track-c-decisions.md`. For
**each finding** cite: route URL, screenshot path, viewport, user impact, likely file/route path,
whether it genuinely depends on vision, and a suggested acceptance test. Prioritize mobile and the
first-run contribution paths. If browser tooling is unavailable, say so and ask the orchestrator to
capture the set — never fabricate observations. → `docs/fable-eval/SITE_VISION_AUDIT.md`.

**W3 — Data-integrity / split-brain risk audit (rhodesli's #1 recurring bug class).**
Connect recurring failure patterns to current code: `tasks/lessons.md` (repeat-offender table),
`tests/test_data_layer_invariants.py`, `app/main.py` load/save paths, `app/upload_routes.py`,
`app/supabase_data.py`, `docs/prds/064_gedcom_history_storage_redesign.md`, `DATA_MODEL.md`. Produce
a risk table distinguishing **active / mitigated / stale-doc / user-gated** risk, each with
file:line evidence and why current tests might miss it. → `docs/fable-eval/DATA_INTEGRITY_AUDIT.md`.

**W4 — Code-quality + bug-recall sweep across route monoliths (no edits).**
Search for real defect classes across `app/main.py` + the large route modules: auth/CSRF gaps on
POST routes, community-prefix / cross-community scoping leaks, upload/compare status-state bugs,
public write surfaces, stale-JSON reads in Postgres mode, cached failure-states that disable
scoping, silent `except: pass` Supabase writes, request-path heavy ML, dead `_main_mod` coupling.
**Classify each entry as `Verified defect`** (reproduced by a targeted check or airtight code-path
proof) **or `Risk finding`** (credible but not reproduced — give the exact missing evidence + the
targeted test needed). Keep the two counts separate. Each needs file:line, route, failure scenario,
why existing tests miss it. → `docs/fable-eval/CODE_FINDINGS.md`.

**W1 — Repo + harness + CI-reality + doc-truth health audit (read-only).**
New-eng-lead inheriting the machine: map it, hand back a staged cleanup plan (top 15 issues). Cover
disk eaters (`rhodesli_ml`, `.git`, `data`, `docs` — reclaimable vs load-bearing); folder mess;
CLAUDE.md + `.claude/rules/` bloat/redundancy; skills + MCP servers installed-but-unused;
`.claude/settings.json` permissions wider than needed; docs over the 300-line cap; dead code;
stale/mis-marked tests; local-green-vs-CI-red gaps (`.github/workflows/test.yml`,
`scripts/simulate_ci_data.py`, `scripts/check_ml_suite_ci_safe.py`); doc/backlog drift (pre-Postgres
JSON-canonical language still present). Rank every issue by impact×effort with the exact action;
classify active/mitigated/stale-doc/user-gated. Flag all moves/deletes for approval.
→ `docs/fable-eval/HEALTH_AUDIT.md`.

**W5 — 10x growth-avenue discovery (turn ambiguity into a ranked path).**
Read `ROADMAP.md`, `docs/BACKLOG.md`, `docs/prds/060_self_service_archive.md`,
`app/onboarding_routes.py`, `docs/prds/036_workspace_onboarding.md`,
`docs/prds/035_multi_community/`, `docs/feedback/session-167-track-c-decisions.md`,
`docs/feedback/FEEDBACK_INDEX.md`. Do **not** assume self-service archives win — weigh vs
shareability/SEO, cross-community person discovery, the wiki pipeline, data-integrity hardening.
Recommend **exactly 3 growth bets that compound**, each with: problem, user flow, acceptance
criteria, risk gates, kill criteria, success metric, rough effort, first shippable slice.
→ `docs/fable-eval/GROWTH_10X.md`.

**W6 — Gemini/estimate + Detroit-promote readiness (analysis only — $0, no calls).**
Read `rhodesli_ml/gemini_extraction.py`, `app/estimate_routes.py`, `scripts/session153_shadow_eval.py`,
`docs/feedback/session-167-detroit-eval.md`, Detroit items in `docs/BACKLOG.md`. One readiness
decision table: is `DETROIT-PROMOTE-167` implementation-ready, what validation fields/tests are
missing, what a bounded paid eval would need to prove later. No API spend.
→ `docs/fable-eval/GEMINI_ESTIMATE_READINESS.md`.

**W8 — Quick-Wins queue (ranked patch plans; NO implementation).**
From W1/W2/W4, identify up to 5 highest-confidence Quick-Win candidates. **Do not implement them.**
For each: user impact, exact files likely involved, why it's outside the exclusion list, acceptance
tests, rollback plan, and whether it's new / already-logged / stale / synthesis (do not repackage
existing BACKLOG items as new). → `docs/fable-eval/QUICK_WINS_QUEUE.md` for the gated follow-up
sprint the orchestrator runs.

## Evals — measure Fable-leveraged value honestly (write `docs/fable-eval/EVALS.md`)
These are **proxy** evals, not proof of model uniqueness. For each metric give numerator,
denominator, evidence path, and a baseline comparator where available (`BACKLOG.md`, `codex-draft.md`,
`opus-draft.md`, prior session docs, or code-only review). Label each result **Evidence-backed /
Proxy / Unverified**. Do not claim another model "could not" do something unless the comparator
supports it — otherwise say "likely Fable-leveraged."
1. **Vision delta:** ≥8 screenshot-grounded findings, ≥3 likely missed by code-only review.
2. **History delta:** ≥6 findings connecting a recurring lesson/session history to current code.
3. **Bug-recall delta:** ≥3 `Verified defect` findings **not already verbatim in BACKLOG** (or an
   explicit statement none survived verification).
4. **Ambiguity delta:** the W5 ranked recommendation, alternatives weighed, one chosen w/ kill
   criteria.
5. **Skill delta:** exactly-3 installed skills; plus a **skill-usability check** — a fresh-context
   verifier subagent takes one new skill + one held-out repo issue and states whether the skill has
   enough triggers/reads/gates/anti-patterns to be usable by Opus without you.
6. **Long-horizon completion:** did you finish the priority workstreams in one run without
   fabricating status? (Yes/no + evidence.)
Finish with an honest self-grade (0–10) and one paragraph: "what a weaker model would likely have
missed."

## Definition of done
All priority-workstream artifacts exist under `docs/fable-eval/` (each <300 lines or split into an
INDEX); `QUICK_WINS_QUEUE.md` exists with **no source-code commits or pushes made**; exactly 3
skills drafted-verified-and-copied to `.claude/skills/` (+ `PORTABLE_SKILLS.md`, `SKILLS_WRITTEN.md`);
`EVALS.md` scored; `FABLE_MEMORY.md` populated; and a final outcome-first report at
`docs/fable-eval/FABLE_REPORT.md` that opens with what happened, lists top-3 things Nolan should look
at first and what's queued as User Decisions, and ends with a **Safety ledger**: production auth
state, production request methods observed, external API spend, files created/edited, tests run, and
any unverified claims. Do not push — the orchestrator gates the merge and runs the implementation.
