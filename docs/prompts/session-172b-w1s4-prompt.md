# Session (W1-S4) — Freeze the candidate slate + exhaustive local retrieval + constraint assertions

**Plan:** `docs/strategy/2026-07-reengagement/RESEARCH_DESK_PLAN.md` (the constitution). This is
**W1-S4** of its two-week sequence. Predecessors: W1-S1+S2 (Session 171 — first Morning Mystery,
"worth-opening" rubric, `investigation_runs` contract, R1 tree-leak fix) and **W1-S3 (assembler,
shipped 2026-07-14)** — `rhodesli_ml/research_desk/packet_assembler.py::assemble_evidence_packet`,
live-validated on the Belle Isle case. Read the Belle Isle case
(`docs/strategy/2026-07-reengagement/morning-mystery-belle-isle/`) and AD-252 first.

## Why this session (the plan's Lane-3 discovery bet)
The old ML program "changed 0 of 470 predictions" because the reranker could only reorder the
baseline top-5 — it could not PROPOSE outside the shortlist. W1-S4 builds the opposite: an
**exhaustive, constraint-aware local retrieval** over ALL ~3,285 faces for one case, so the Desk can
find a match the old system never surfaced — or defensibly conclude none exists (abstention).

## Multi-model operating instructions (unchanged from Session 171 — worked well)
- **Opus = orchestrator**: dispatch, verify artifacts, keep the ledger, commit. Never trust "done".
- **Sol = coder (medium) + independent auditor (xhigh)** via `codex exec "<spec>" </dev/null`.
  Dispatch-shaped specs: exact files, acceptance criteria, forbidden surfaces, a BOUNDED verify
  (targeted pytest, never `make test-fast`). NOTE: `codex exec` at xhigh has stalled on long final
  reports (Session 171) — if the tee log freezes with procs alive for >~5 min, kill it and fall back
  to a fresh-context Claude subagent auditor (`.claude/rules/ai-tool-audit.md`).
- **Fable = architect/judge, ≤2 dispatches** (Agent `model:"fable"`, bounded ≤3 file reads): use it
  to judge the retrieval OUTPUT quality (does the constraint-ranked slate read as "worth
  investigating"?), not to write code. Load the `fable-usage` skill first.
- Budget: any single dispatch >150k tokens or a wrong-feeling spend → STOP and post-mortem.

## Scope (WIP: 1 enabling task — the retrieval engine; do NOT also generate new cases)
1. **Freeze the candidate slate** for a case: given a subject identity, define the closed set of
   plausible identities to rank (all non-self identities, OR a constrained subset). Store it so a run
   is reproducible (the slate is part of the immutable input manifest — extend the assembler or add a
   companion `freeze_candidate_slate(case_ref)`).
2. **Exhaustive local retrieval** over all ~3K faces (build on the assembler's embedding map +
   `_rank_external_matches`): reciprocal-neighbor check, multi-crop/quality-weighted aggregation per
   identity (not just per-face min), and an identity-level ranking (aggregate a person's faces, don't
   let one lucky crop dominate). Explicitly ALLOWED to rank the full corpus, not a top-5 shortlist.
3. **Constraint assertions** per candidate: age-feasibility (subject's estimated photo-date vs the
   candidate's GEDCOM birth/death — a candidate born 1881 fails a "young man in 1917" case, cf. the
   Harry Isaackovitz drop), and co-occurrence/kinship plausibility. Emit each as a structured,
   evidence-cited assertion (PASS/FAIL + why) — these become the packet's `constraints` block.
4. Wire the frozen slate + ranked candidates + constraint assertions into the evidence packet
   (extend `assemble_evidence_packet` or a new `assemble_with_retrieval`), and record a run via the
   `investigation_runs` contract (status pending→assembling→...; do NOT seal verdicts here — that's
   W1-S5). **Read-only against confirmed data.**
5. **Validate live on Belle Isle**: the exhaustive retrieval must still yield `no_confident_match`
   (nearest ~1.209) AND the constraint block must FAIL the Harry Isaackovitz (b.1881) candidate on
   age — reproducing, mechanically, the two models' hand-reasoned conclusion.

## Anti-goals
No nightly scheduler (W1-S8). No sealed verdicts / investigator calls (W1-S5). No embedding-model
swap (that's the champion/challenger bake-off, later + eval-gated). No new UI. No new cases beyond
Belle Isle as the validation fixture. No writes to confirmed identity data. No multi-tenant/consent
work (owner directive). First resolve **PACKET-DECOUPLE-171** (BACKLOG) if the retrieval will run
offline — decouple the GEDCOM read from `app.main`.

## Close-out (mandatory)
Independent audit (Sol xhigh or Claude-subagent fallback) on the diff; fix P0/P1. Assessment,
CHANGELOG (v0.99.93), ROADMAP/BACKLOG dual-update, session log, AD entry for the retrieval/aggregation
+ constraint thresholds. Append a meta-lesson to `docs/strategy/2026-07-reengagement/meta-log.md`.
Deploy only if app code changed; CI green; `git log origin/main..HEAD` empty.

## Outstanding from Session 171 (verify/carry)
- **R2 — rotate `ML_SERVICE_TOKEN`** on Railway (never done; owner action). Verify before any ML-service work.
- **R1 UX**: confirm with Nolan whether the Fox tree should also appear at the root (currently only `/c/fox-family/tree`).
- BACKLOG: TREE-AUTH-171 (fox-family tree public — owner decision), RUN-KEY-171 (idempotency delimiter), PACKET-DECOUPLE-171.
