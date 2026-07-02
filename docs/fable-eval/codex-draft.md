# Codex Draft: Fable 5 Full-Evaluation

Date: 2026-07-02
Author: Codex gpt-5.5 xhigh
Scope: read-only research and prompt design for a future Fable evaluation.

## Codex research: what Fable 5 uniquely enables

Fable 5 should not be used as "a slightly stronger Opus" or as a faster Codex. Its best use in Rhodesli is a long, evidence-grounded evaluation that crosses product, code, live UX, repo history, and harness behavior in one continuous mental model. The advantage to exploit is not raw code generation. It is the ability to retain a large first brief, navigate ambiguous priorities, inspect dense visual UI state, and keep a multi-hour audit coherent without losing the constraints.

The highest-value Fable evaluation should therefore do five things that Opus/Sonnet/Codex are less reliable at doing in one pass:

1. Build a repo-history-aware risk model, not just a static code review. Rhodesli's biggest failures recur as patterns: split-brain data, silent Supabase writes, schema drift, upload pipeline regressions, and local-green versus CI-red gaps. Fable should connect `tasks/lessons.md`, `docs/BACKLOG.md`, session prompts, tests, and current code paths.
2. Use vision as a primary audit instrument. Fable's dense screenshot reading should be spent on production pages where DOM/code review misses reality: mobile overflow, face labels, compare/estimate upload affordances, photo overlays, public community pages, and first-run contribution paths.
3. Turn ambiguity into a ranked path, not a survey. The repo has many plausible futures: self-service archives, standalone tools, Detroit/Gemini quality, multi-community permissions, and data-integrity hardening. Fable should pick the few that compound and define acceptance criteria.
4. Extract reusable skills from scar tissue. The temporary Fable window is best used to distill Rhodesli's hard-won patterns into Opus-usable playbooks: split-brain audits, upload pipeline verification, FastHTML route safety, live UX vision audits, and multimodel sprint gates.
5. Dispatch or simulate independent specialist passes. If subagents are available, Fable should split bounded work by domain and append findings incrementally. If not, it should still separate the final report into fresh-pass style sections and explicitly mark which checks were independent versus self-reviewed.

What community advice gets wrong or oversells:

- "One big prompt" is good only if it contains hard exclusions, output contracts, and verification gates. A giant unbounded brief is how you get sprawling, untestable artifacts.
- "Autonomous" does not mean "mutate production" or "start refactoring." In this repo, the correct autonomous action is often to stop at a ranked finding with evidence because production data is the asset.
- "Have Fable write skills" is only valuable if the skills encode repo-specific incidents, trigger rules, required reads, and verification commands. Generic "be careful" skills are negative value.
- "Better vision" is not a replacement for browser evidence. Fable should save screenshots, cite routes, and connect visual findings back to code paths or tests.
- "Parallel subagents" still need bounded scopes, a canary, incremental file writes, and file-boundary discipline. Fable may be better at delegation, but it cannot repeal worktree and context physics.
- "Ask it to reason deeply" should not become "show your hidden reasoning." Ask for concise rationale, evidence, and tradeoffs. Do not ask for chain-of-thought.
- "xhigh solves correctness" is false. xhigh can make slop more elaborate. The prompt must require claim-by-claim verification against tool output before reporting.

## Highest-value evaluation targets in rhodesli

Ranked by expected impact if Fable performs the evaluation better than Opus/Codex would.

1. **Data-integrity and split-brain risk audit**
   Evidence paths: `tasks/lessons.md`, `tests/test_data_layer_invariants.py`, `docs/prompts/session-130-prompt.md`, `app/main.py`, `app/upload_routes.py`, `app/supabase_data.py`, `docs/prds/064_gedcom_history_storage_redesign.md`, `docs/architecture/DATA_MODEL.md`.
   Why Fable: this requires connecting old failure patterns to current code and stale docs. The live architecture says Postgres is source of truth, while older architecture docs still describe JSON as canonical. Fable should identify where that confusion can still leak into scripts, docs, prompts, tests, or operator behavior.

2. **Live-site product, UX, and vision audit**
   Evidence paths: `app/page_routes.py`, `app/browse_routes.py`, `app/photo_routes.py`, `app/compare_routes.py`, `app/estimate_routes.py`, `docs/user_feedback/FB-170_claude_benatar_compare_failure.md`, `docs/ux_audit/UX_ISSUE_TRACKER.md`, `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`.
   Why Fable: this is the most direct use of its vision edge. It should inspect production pages read-only at desktop and mobile widths, then map screenshots to UX failures and route files.

3. **10x growth avenue: self-service archive and contribution loop**
   Evidence paths: `docs/prds/060_self_service_archive.md`, `app/onboarding_routes.py`, `docs/feedback/session-167-track-c-decisions.md`, `docs/session_context/session-168-path-forward.md`, `docs/prds/036_workspace_onboarding.md`, `docs/prds/035_multi_community/DATA_MODEL.md`, `docs/BACKLOG.md`.
   Why Fable: the core ambiguity is product-policy-technical. The feature exists behind a flag, but owner permissions and non-admin write semantics remain unresolved. Fable should recommend a launch sequence with risk gates, not just list tasks.

4. **Reusable skill extraction for Opus 4.8 inheritance**
   Evidence paths: `/Users/nolanfox/.claude/skills/multimodel-sprint/SKILL.md`, `docs/session_context/session-168-meta-lessons.md`, `docs/HARNESS_DECISIONS.md`, `tasks/lessons.md`, `scripts/simulate_ci_data.py`, `scripts/check_ml_suite_ci_safe.py`, `.github/workflows/test.yml`.
   Why Fable: this is the most time-sensitive leverage. Draft skills should teach Opus concrete workflows: split-brain audit, upload pipeline verification, live visual UX audit, FastHTML route safety, and Fable-style eval packaging.

5. **Code-quality and bug-recall sweep of route monoliths**
   Evidence paths: `app/main.py`, `app/page_routes.py`, `app/compare_routes.py`, `app/identity_routes.py`, `app/admin_routes.py`, `app/cluster_review_routes.py`, `tests/test_main_mod_references.py`.
   Why Fable: `app/main.py` is 8255 lines, but the real monolith has spread into `page_routes.py` at 13389 lines, `compare_routes.py` at 6171, `identity_routes.py` at 5294, and `admin_routes.py` at 5278. Fable should search for bug classes across route families: auth/CSRF inconsistencies, community-prefix leaks, stale `_main_mod` dependencies, public route surprises, and heavy request-path work.

6. **Upload, compare, and ingest pipeline end-to-end audit**
   Evidence paths: `app/upload_routes.py`, `app/compare_routes.py`, `core/ingest_inbox.py`, `scripts/process_uploads.py`, `tests/test_upload_*`, `tests/test_compare_*`, `docs/user_feedback/FB-170_claude_benatar_compare_failure.md`.
   Why Fable: upload regressions are a repeated user-trust killer. The pipeline crosses local staging, R2, Supabase, background ingest, community tagging, proposals, status polling, attribution, and cache invalidation.

7. **Gemini/estimate lineage and Detroit promotion readiness**
   Evidence paths: `rhodesli_ml/gemini_extraction.py`, `app/estimate_routes.py`, `scripts/session153_shadow_eval.py`, `docs/feedback/session-167-detroit-eval.md`, `docs/BACKLOG.md`, `tests/fixtures/session167_gedcom_context.json`.
   Why Fable: this is a prompt, data, and evaluation-design problem. It should not spend Gemini money unless gated. It should decide whether `DETROIT-PROMOTE-167` is implementation-ready, what mechanical validation is missing, and what a bounded eval must prove.

8. **Harness and CI-reality audit**
   Evidence paths: `docs/HARNESS_DECISIONS.md`, `tasks/lessons/harness-lessons.md`, `docs/session_context/session-168-meta-lessons.md`, `scripts/simulate_ci_data.py`, `scripts/check_ml_suite_ci_safe.py`, `.github/workflows/test.yml`, `scripts/harness-check.sh`.
   Why Fable: Session 168 proved the harness catches real regressions, but also exposed stalls and local-green/CI-red gaps. Fable should turn those into durable acceptance checks.

9. **Documentation and backlog truth audit**
   Evidence paths: `CLAUDE.md`, `ROADMAP.md`, `docs/BACKLOG.md`, `docs/architecture/OVERVIEW.md`, `docs/architecture/DATA_MODEL.md`, `docs/architecture/PERMISSIONS.md`, `docs/roadmap/SESSION_HISTORY.md`.
   Why Fable: stale docs can mislead every future agent. Some docs still describe pre-Postgres architecture or older counts. Fable should rank which drift matters operationally and which is harmless historical residue.

## Codex's draft Fable session prompt

```text
You are Claude Fable 5 acting as an autonomous evaluator, product architect, visual QA reviewer, and skill distiller for Rhodesli.

You are running inside /Users/nolanfox/rhodesli. Rhodesli is a FastHTML + HTMX heritage photo archive backed by Supabase/Postgres, Cloudflare R2, Railway, InsightFace, and Gemini. Live site: https://rhodesli.nolanandrewfox.com. Current rough scale: v0.99.89, about 5353 tests, 1127 photos, 1824 identities, CI green as of Session 168. app/main.py is still large, but much of the effective monolith now lives in route modules such as app/page_routes.py, app/compare_routes.py, app/identity_routes.py, app/admin_routes.py, and app/cluster_review_routes.py.

Your mission is a full evaluation, not an implementation sprint. Produce durable, evidence-backed artifacts under docs/fable-eval/ that tell us where Fable created value beyond Opus/Codex. You are autonomous: do the work now, verify it against tool results, and do not end on a promise or a plan for later. When you have enough evidence to make a recommendation, make it.

Hard guardrails:
- Do not mutate production data. Production browser work is READ-ONLY. Do not click admin action buttons, submit forms, approve/reject/merge/detach/rename, POST to data-modifying routes, or run scripts that write to Supabase/R2/Railway.
- Do not make Supabase schema changes, migrations, destructive ops, deploys, pushes, feature-flag flips, or Railway env changes.
- Do not spend real Gemini or paid API calls unless the prompt explicitly gives a dollar cap and user approval. This evaluation has no paid-call approval. Use existing eval artifacts and fixtures.
- Do not edit source code, tests, scripts, app files, rhodesli_ml files, global nav/head/layout, frozen files, or data files. Frozen/excluded: core/neighbors.py, core/pfe.py, data/*.
- You may write evaluation artifacts only under docs/fable-eval/. If you draft reusable skills, put them under docs/fable-eval/skill-drafts/ rather than installing them.
- Do not run the full test suite. Targeted read-only commands, grep, file reads, route extraction, and small static checks are fine.
- Do not reveal hidden chain-of-thought. Provide concise rationale, evidence, tradeoffs, and confidence.

Memory:
- Create or update docs/fable-eval/FABLE_MEMORY.md.
- Keep it as a short indexed memory file: one lesson per bullet, each with source evidence.
- Record only corrections, reusable patterns, and high-confidence observations. Do not duplicate large report content.

Required orientation:
- Read CLAUDE.md, ROADMAP.md, docs/BACKLOG.md, docs/AGENT_HARNESS.md, tasks/lessons.md, docs/session_context/session-168-meta-lessons.md, docs/session_context/session-168-path-forward.md, and /Users/nolanfox/.claude/skills/multimodel-sprint/SKILL.md if readable.
- Skim app/ structure with line counts and route registration patterns.
- Skim docs/ structure enough to detect stale architecture, backlog, harness, ML, and product material.
- Treat docs that conflict with current code as drift to be classified, not as truth.

Primary goals:

1. Build a ranked Fable health audit of the repo and harness.
   Focus on issues that recurring agents miss: stale docs that mislead future sessions, local-green versus CI-red risks, route monolith risk, circular import and _main_mod coupling, hook/harness gaps, oversized or stale docs, and unused or outdated process rules. Output docs/fable-eval/HEALTH_AUDIT.md.

2. Run a live-site product and UX vision audit, read-only.
   Use browser screenshots at desktop and mobile widths. Inspect at least: root, /people, /photos, a public photo page, a public person page, /tools/compare, /compare/pair, /tools/estimate, /help, and one /c/<slug>/ community page if safely discoverable without writing. Save screenshots under docs/fable-eval/screenshots/. For each finding, cite route URL, screenshot path, viewport, user impact, likely file path, and whether the finding depends on vision. Output docs/fable-eval/SITE_VISION_AUDIT.md.

3. Audit data-integrity and split-brain risk.
   Connect lessons and current code. Read tests/test_data_layer_invariants.py, docs/prompts/session-130-prompt.md, app/main.py load/save paths, app/upload_routes.py, app/supabase_data.py, docs/prds/064_gedcom_history_storage_redesign.md, and relevant tests. Produce a risk table that distinguishes active risk, mitigated risk, stale doc risk, and user-gated production risk. Output docs/fable-eval/DATA_INTEGRITY_AUDIT.md.

4. Identify the highest-leverage 10x growth avenues.
   Start from self-service archives and contribution loops, but do not assume they win. Read docs/prds/060_self_service_archive.md, app/onboarding_routes.py, docs/feedback/session-167-track-c-decisions.md, docs/prds/036_workspace_onboarding.md, docs/prds/035_multi_community/, and relevant feedback. Recommend 3 growth bets with acceptance criteria, risk gates, kill criteria, metrics, and first shippable slices. Output docs/fable-eval/GROWTH_10X.md.

5. Perform a code bug-recall sweep without editing code.
   Focus on P0/P1 classes across app/main.py and route modules: auth/CSRF, community scoping, upload/compare status state, public write surfaces, stale JSON reads in Postgres mode, cache failure states, request-path heavy ML, and live route/link inconsistencies. Every finding needs evidence: file:line, route, why existing tests may miss it, and a targeted test that would catch it. Output docs/fable-eval/CODE_FINDINGS.md.

6. Evaluate Gemini/estimate and Detroit readiness without spending API money.
   Read rhodesli_ml/gemini_extraction.py, app/estimate_routes.py, scripts/session153_shadow_eval.py, docs/feedback/session-167-detroit-eval.md, and docs/BACKLOG.md Detroit items. Decide if DETROIT-PROMOTE-167 is ready for implementation, what validation fields/tests are missing, and what bounded paid eval would be required later. Output docs/fable-eval/GEMINI_ESTIMATE_READINESS.md.

7. Extract reusable skills for Opus 4.8.
   Draft 3 to 5 skill files under docs/fable-eval/skill-drafts/. Each draft skill must have: trigger rules, required files to read, step-by-step workflow, exact verification gates, anti-patterns, and a "past incident this prevents" section. Candidate skills: split-brain data audit, upload pipeline verifier, FastHTML route safety audit, live UX vision audit, and Fable evaluation packaging. Output docs/fable-eval/SKILLS_WRITTEN.md summarizing them.

8. Produce an eval scorecard proving Fable-specific value.
   Output docs/fable-eval/EVALS.md. Include:
   - Vision delta: at least 8 screenshot-grounded findings, with at least 3 that would likely be missed by code-only review.
   - History delta: at least 6 findings that cite recurring lessons/session history and current code together.
   - Ambiguity delta: a ranked recommendation where multiple plausible product paths were considered and one was chosen.
   - Skill delta: at least 3 skill drafts that are specific enough for Opus 4.8 to reuse without Fable.
   - Verification delta: every top-level factual claim in final summary maps to file evidence, command output, screenshot, or explicitly marked "unverified."
   - Novel bug delta: at least 3 plausible P1/P2 findings not already verbatim in BACKLOG, or a clear statement that no novel findings survived verification.

Self-verification before final:
- Re-open each artifact you wrote.
- Check that every ranked finding has evidence.
- Check that no claim says "verified" unless you have a tool result, screenshot, file read, or command output from this run.
- Check that no production write, schema change, full test run, data edit, or forbidden file edit happened.
- Write docs/fable-eval/FINAL_SUMMARY.md with the top 10 recommendations, the artifacts produced, and any unverified assumptions.

Operating style:
- Prefer goals over checklists, but use the output contracts above.
- Be concrete and opinionated. Rank by impact and risk.
- If a source contradicts another source, classify the contradiction and decide which source is operationally authoritative.
- If you stall or hit a tool/budget limit, preserve partial findings in the appropriate artifact before continuing with a smaller scope.
- Do not end with "I will". Finish the artifacts and final summary.
```

## Risks & anti-patterns

1. **Fable over-refactors instead of evaluates**
   Guardrail language: "This is an evaluation. Do not edit source code, tests, scripts, app files, rhodesli_ml files, or existing docs outside docs/fable-eval/. Produce findings, specs, and skill drafts only."

2. **Hallucinated status or unverifiable claims**
   Guardrail language: "Before reporting progress or final status, audit each claim against tool output from this run. If you cannot point to file evidence, command output, screenshot, or live read-only observation, mark it Unverified."

3. **Scope creep into production or schema**
   Guardrail language: "Production browser work is READ-ONLY. No POST/PUT/DELETE, no admin action buttons, no Supabase writes, no schema migrations, no Railway env changes, no deploys, no feature-flag flips."

4. **Paid Gemini or API spend without approval**
   Guardrail language: "This evaluation has no paid-call approval. Do not call Gemini or other paid APIs. Use existing eval artifacts, fixtures, logs, and code."

5. **Reasoning-extraction refusal or fallback**
   Guardrail language: "Do not reveal hidden chain-of-thought. Provide concise rationale, evidence, alternatives considered, and confidence."

6. **Subagent stalls lose all work**
   Guardrail language: "Bound every specialist pass below the stream-watchdog horizon. Append findings to files incrementally. If a pass stalls, split the remaining scope smaller instead of rerunning larger."

7. **Generic skill slop**
   Guardrail language: "A skill draft is acceptable only if it has trigger rules, required reads, exact gates, anti-patterns, and a concrete Rhodesli incident it prevents. Otherwise, omit it."

8. **Vision audit without actionable linkage**
   Guardrail language: "Every visual finding must cite screenshot path, viewport, route URL, user impact, likely code path, and a suggested acceptance test or browser check."

9. **Backlog laundering**
   Guardrail language: "Do not repackage BACKLOG as new findings. Mark whether each finding is new, already logged, stale/resolved, or a higher-level synthesis. Novel bug delta requires non-verbatim findings that survive verification."

10. **Autonomy ending as a promise**
    Guardrail language: "Before final, inspect the last paragraph. If it is a plan, question, or promise, do the work now or explicitly mark the blocker. Do not end with 'I'll do X next.'"
