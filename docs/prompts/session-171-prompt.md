# Session 171 — Research Desk W1-S1+S2: The First Morning Mystery, Hand-Built

**Plan:** `docs/strategy/2026-07-reengagement/RESEARCH_DESK_PLAN.md` (read it first — it is the
constitution for the next 30 days). This session is W1-S1 + W1-S2 of its two-week sequence,
plus the security interrupt-lane riders.
**Supersedes:** `session-170-prompt.md` (growth Phase A) — its P0 items survive as Rider R below;
the rest of Phase A moves to the maintenance budget.
**Context:** `docs/strategy/2026-07-reengagement/` (all files). Session mode: implementation.

## Multi-model operating instructions (follow exactly; log per ai-tool-audit.md)

- **Orchestrator = Opus (this session's main loop).** Dispatches, verifies artifacts exist
  (never trusts "done" messages), keeps the token ledger, commits.
- **Sol = coder + independent auditor** via `codex exec "<prompt>" </dev/null`
  (pin: gpt-5.6-sol). Effort discipline: `-c model_reasoning_effort="medium"` for bounded
  coding; **xhigh only** for the end-of-session adversarial audit. Give Sol dispatch-shaped
  specs: exact files, acceptance criteria, forbidden surfaces, and a bounded verify command
  (targeted pytest, never `make test-fast` — Lesson 213).
- **Fable = architect/judgment, invoked at most twice** (Agent tool, `model: "fable"`):
  once to review the hand-built morning artifact against the "worth opening" rubric (it designed
  the sealed-verdict protocol), once only if a design decision genuinely forks. Bounded briefs:
  ≤3 file reads + inline context (shared-memory rule).
- **Budget:** if any single dispatch exceeds ~150k tokens or the session's subagent spend feels
  wrong, STOP and post-mortem — running out of tokens is a design error (owner directive).
- **Canary rule (Lesson 182):** first parallel-agent launch of the session is a single canary;
  verify real work before launching siblings.

## Phase 0 — Init + interrupt-lane riders (Rider R, ≤45 min total, Sol codes)

0a. Standard init (current_session 171, mode implementation, venv, `make test-fast` baseline,
    harness-check).
0b. **R1 — Tree scoping P0:** `/api/tree/data` (`app/page_routes.py:~10950`) scopes GEDCOM by
    community; non-Rhodes/Fox communities get honest empty state. Regression test: requesting
    `/c/rhodes/tree` data does NOT contain Fox GEDCOM individuals. (Live cross-community leak,
    Lesson-151 class, found by Fable eval 2026-07-05.)
0c. **R2 — Rotate `ML_SERVICE_TOKEN`** on Railway (value committed in session-116 log). Verify
    ML service health after rotation.
0d. **R3 — Ephemeral anonymous compare:** anonymous `/api/compare/upload` creates no
    `pending_uploads` row / R2 object (GROWTH_ROADMAP A1; update the stale test at
    `tests/test_community_routing_safety.py:384`).
Commit each rider separately. These are the ONLY platform items this session.

## Phase 1 — W1-S1: Hand-build the ideal Morning Mystery (the product-defining phase)

Pick the case: **Belle Isle Conservatory young man** (identity `ef39908e-...`, 2 anchors,
INBOX, GEDCOM candidate Harry Isaackovitz @I132506612777@ at confidence 0.3 — Sessions 154/156
left it genuinely unresolved with real evidence on file).

1. Assemble the evidence packet BY HAND (scripts fine, no new infra): photo(s) + face crops,
   provenance, GEDCOM context for all linked/candidate individuals, date/location estimates,
   co-occurrence neighbors, top-20 embedding candidates with calibrated distances, prior session
   findings (as leads-to-reverify, cited), the Library of Congress Belle Isle citation.
2. Write the morning artifact as it should feel: evidence first, then **sealed verdicts** —
   run Gemini 3.1 Pro and Sol (medium) independently on the packet with a structured
   investigator prompt (claims must cite evidence IDs; abstention is a valid verdict); seal
   both. Fable reviews artifact structure (dispatch 1).
3. Write the binary **"worth opening" rubric** (one page, `docs/strategy/2026-07-reengagement/
   worth-opening-rubric.md`) — the acceptance test every future nightly artifact must pass.
4. **Deliver the artifact to Nolan** (repo file + SendUserFile): his review IS the A/B's first
   data point — record whether he plays-first or reveals-first, review minutes, and his call.

DoD: a real, complete, reviewable Morning Mystery artifact for a real case; rubric written;
model calls logged to `gemini_api_calls`/cost ledger; zero writes to confirmed data.

## Phase 2 — W1-S2: The case/run contract

On the existing `identification_investigations` schema (extend, don't replace): immutable input
manifest (hashes), atomic cited claims, candidates, contradictions, requested decisions (≤3),
sealed-verdict envelope, model/version/tokens/cost, status transitions, idempotency key,
`rights_state` enum stub (multidimensional permissions land with Research Drop). Schema
validation + structural tests: (a) a run with a failed write leaves ZERO rows (Lesson 199
class), (b) no path writes confirmed identity data, (c) idempotent re-run creates no duplicates.
Sol codes from a dispatch-shaped spec; targeted tests only.

## Phase 3 — Close-out (mandatory)

Sol adversarial audit (xhigh) on the diff; fix P0/P1. Session artifacts: assessment, CHANGELOG
(v0.99.91), ROADMAP/BACKLOG dual-update, session log. Meta-analysis appended to
`docs/strategy/2026-07-reengagement/meta-log.md`: what each model did, effort levels used,
token/cost per dispatch, what worked/failed, one lesson. Deploy riders (`git push`), verify
health 200 + browser-verify tree scoping on production (READ-ONLY). CI green.

## Anti-goals
No nightly scheduler yet. No new UI surfaces. No embedding changes. No Research Drop. No
public-archive adapters. No biography compiler. The WIP limit is real: one live case (Belle
Isle) + one enabling task (the contract). Everything else waits for W1-S3+.
