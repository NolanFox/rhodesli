# The Rhodesli Research Desk — Re-Engagement Plan (2026-07-13)

**Status:** CONVERGED + CO-SIGNED. Sol final verdict: CO-SIGN-WITH-NITS (`sol-signoff.md`; all
three nits folded in below). Sol's residual risk, kept front-of-mind: *"the single biggest
remaining risk is a trust-breaking first artifact"* — hence W1-S1 hand-builds the first Morning
Mystery before any automation exists.
**Provenance:** Fable 5 draft (`fable-pass1.md`) × GPT-5.6-Sol draft (`sol-pass1.md`, independent,
same brief) → adjudication (`adjudication-round1.md`) → Sol adversarial critique with arithmetic
(`sol-critique.md`, AGREE-WITH-CHANGES) → this synthesis. Evidence base: `engagement-evidence.md`,
`tech-state.md`, `model-settings-research.md`.

---

## Why the project went quiet (converged diagnosis)

Both models, independently: the roadmap drifted from **discovery** to **platform**. Sessions
158–164 were Supabase firefighting; 168–170 were security/growth/multi-tenant phases. Every
session Nolan actually loved (145, 148c, 152, 153, 166) was an investigation — a mystery, evidence
from many sources, a verdict, something newly *known*. Three structural causes:

1. **Discovery was manual** — it only happened when Nolan drove, and he now has a day job.
2. **Evidence intake was built around its highest-friction step** — ~2h of supervised Chrome-MCP
   wrangling per FB post; exactly one post captured in three months.
3. **The ML program optimized scores inside a shortlist instead of finding anything new** — the
   reranker changed 0 of 470 predictions because it *couldn't* propose outside the baseline top-5.

**The product prototype was the Fox/Heft work all along.** The plan below industrializes it.

## The core product: the Morning Mystery (sealed verdicts)

Overnight, the Desk prepares **one** case: selects it, assembles an immutable evidence packet
(photo + crops + GEDCOM + dates + co-occurrence + retrieval candidates + testimony + source
excerpts), runs a bounded multi-model investigation, runs a Skeptical Historian pass — and then
**seals the conclusions**.

In the morning (≤15 min, mobile-first), Nolan opens the case, reviews the evidence, and **makes
his own call first**. Then he reveals the sealed verdicts — what Gemini, Sol, and Fable each
concluded and why — and adjudicates. His call + the reveal comparison are recorded as ground
truth and as model-league scores.

Why sealed verdicts (Sol's round-2 catch, Fable's design answer): the engagement record shows
Nolan's joy is *conducting* investigations and *adjudicating bake-offs* — not processing model
output. A completed dossier risks turning pleasure into editorial homework. Sealing preserves the
detective moment; the reveal preserves the bake-off moment; the label lands either way. Both
modes ship (reveal-immediately vs. play-first); the first six cases A/B which one he actually
opens. **If play-first wins, the autonomy boundary is evidence preparation, not conclusion
generation — and that's fine; the Desk is still doing its job.**

Hard caps (Sol's arithmetic, adopted): **1 case per morning, ≤3 requested decisions, $2/night
default model budget** (cheap scout + one principal investigator; the expensive challenger runs
only on disagreement, high-value cases, or audit samples). Notification fires only after the
stored artifact re-reads and validates — a model's "done" is not a checkpoint.

## Four lanes, one critical path (WIP limit: 1 live case + 1 enabling task)

Lanes are a map, not four parallel programs. Lane 1 owns the critical path; 2 and 4 contribute
only what the live case needs; Lane 3 gets one bounded session, then waits until the case loop
survives human review twice.

**Lane 1 — The Desk (engine).** Case/run contract on the existing
`identification_investigations` schema (immutable inputs, cited atomic claims, contradictions,
alternatives, cost/model/version, idempotency keys); the nightly runner with checkpoint/resume;
sealed-verdict protocol; Skeptical Historian pass; research-value scheduler (later); model/
provider registry with per-run budgets (engine concern, per Sol). Kill switch + partial-artifact
degradation.

**Lane 2 — Evidence supply (consent-first, rights-aware).**
- *Research Drop*: contributor bundles (photo front/back, context, permalink, consent) — and
  **screenshot leads**: Nolan's own 15-second phone screenshots of FB posts enter as
  `capture_method=screenshot, rights_state=unknown, audience=private_research` — lead quality,
  never archive-ready, author consent required before any public use. This replaces the DOM
  pipeline as the day-over-day capture path (unit cost: ~2h → ~1min).
- *FB author-export importer*: parse a consenting member's official "Download Your Information"
  archive offline. Zero automated Facebook access anywhere in the system.
- *HTR/verso extraction*: exempt from the hypothesis gate as pure evidence extraction, with Sol's
  conditions — inventory first, 50-image stratified pilot (incl. Solitreo), Gemini Flash Batch
  (~$7–20 corpus-wide), transcription-only output to an extraction ledger **idempotent on
  (asset hash, model, prompt) with a hard $20 corpus cap before scaling past the pilot**, and a
  promotion threshold so review hours stay bounded.
- *Source discovery, not bulk connectors* (Sol's rights table stands): a **rights registry**
  with per-source, per-operation permissions (retain / model-process / face-embed / quote /
  **derivative-crop** / republish, each with **grantor + grant timestamp** — permission for one
  is not permission for the others; **unknown-rights screenshot leads default to NO model
  processing and NO face embedding until expressly authorized**); first adapters = Chronicling
  America (real API, PD-leaning) and UW Stroum metadata; **Rhodes Jewish Museum as a partnership
  target, not a scraper**; Yad Vashem/USHMM/JDC/ANU/JewishGen/FindAGrave = manual lead sources.
- *One-Question Witness Packets*: end each case with one targeted, human-approved question to
  the one person likely to know. Never auto-sent.
- *Session-doc lead mining*: recover cases, sources, and contradictions from the Fox/Heft corpus
  as *leads to re-verify* — not day-one publishable content.

**Lane 3 — Recognition science (discovery-oriented, eval-gated).**
Sequence: (1) frozen eval harness from confirmed anchors — hard slices: decade-gap, family-held-
out, children, occlusion, plus a **sealed case set** never used in prompt development; (2)
**Retrieval 2.0** — exhaustive age-conditioned search over all ~3K faces (age-bin prototypes,
reciprocal neighbors, multi-crop quality ensembles) — explicitly allowed to find what the old
system never proposed; (3) champion/challenger embedding bake-off vs. buffalo_l (2021-era),
switch only on hard-slice wins; (4) calibrated evidence fusion (face + age feasibility + kinship
+ co-occurrence + geography + testimony) as a transparent posterior; (5) active learning ranked
by *historical unlock*, feeding the Morning Mystery queue. PRD-038 Phase 5 ("more labels, same
reranker") is closed — labels reuse here.

**Lane 4 — The stage (human surfaces).**
The case review page (mobile-first, evidence beside claim, disagreement visible, ≤3 decisions);
publishable casefiles + open-mystery cards (private→public gate, living-person protections);
biography compiler (later — every sentence cited, private by default); journey-based UX repairs
(one journey, two viewports, before/after screenshots per session — starting with the journeys
the Desk lands on, which is how mobile gets fixed without a rewrite).

## Operating rules (the contract that keeps this honest)

1. No frontier pass without a named hypothesis + evidence packet + ledger destination (HTR
   extraction exempt, conditions above).
2. Multidimensional permissions enforced in code; `rights_state` is never a prose note.
3. External evidence is hostile input: data-delimited source text, read-only tools during
   research, model-authored URLs/IDs validated before storage (prompt-injection defense).
4. **Abstention counts as value**: "no defensible identification; here's the decisive missing
   evidence" is a good morning. Record calibrated abstentions + the named missing evidence in
   the ledger; when no claim is accepted, score the run on cost-per-reviewed-case so valid
   caution is never scored as failure. Track unsupported-claim rate and overturned conclusions,
   not just discoveries.
5. Citation durability: retrieval time, item ID, exact excerpt, checksum; private snapshot only
   when rights allow.
6. No model grades its own work; nothing auto-confirms; humans gate identity + publication.
7. Security is an **interrupt lane**, not a phase: P0 privacy/consent/data-loss preempts
   everything; routine hardening gets a bounded maintenance budget. (Immediate riders: scope
   `/api/tree/data` to community — the live cross-community GEDCOM leak; rotate
   `ML_SERVICE_TOKEN`; make anonymous compare ephemeral. All small; ride along with W1 sessions.)
8. Every session ends with the six-counter ledger delta: cases advanced · accepted claims ·
   identities confirmed/corrected · photos linked · witness answers · $/accepted claim.

## 30-day pilot bar (Sol's revision, adopted — replaces the 20-casefile fantasy)

Six reviewed dossiers · ≥3 rated "worth opening" (binary rubric written in W1-S1) · median
review <15 min · ≥1 accepted historical delta per 3 cases · 2 consecutive clean unattended runs
· cost under cap. Hit that, then raise throughput. Miss it: inspect the failed cases, fix the
evidence/retrieval loop, run it again — do not add tenants, tools, or traffic.

## First two weeks (Sol's sequence, adopted; ~8 sessions + 2 stretch)

W1-S1 hand-build the ideal morning artifact for one real case + "worth opening" rubric →
W1-S2 case/run contract + schema validation → W1-S3 evidence-packet assembler (rights-known
material only) → W1-S4 freeze candidate slate, exhaustive local retrieval + constraint
assertions → W1-S5 one investigator vs. static packet, score every claim → W2-S6 second
investigator + conditional skeptic + $2 cap + failure degradation → W2-S7 minimal mobile review
page → W2-S8 checkpoints/resume/idempotency + dress rehearsal + schedule ONE unattended case →
W2-S9 review the first real Morning Mystery, measure everything → W2-S10 one supply pilot (HTR
triage or screenshot Research Drop). Full session specs in `sol-critique.md` §4.

First case candidates (seeded from open mysteries): Belle Isle Conservatory young man ·
Bessie/3009 · person 3299 (Elizabeth Tischler?) · Nellie Kubrin confirmation.

## Kill list (both models, converged)

Multi-tenant enablement & self-service archives (until 3 non-Fox families complete 10
investigations through a concierge version) · growth-phase analytics/SEO/funnel polish ·
FB DOM-extraction sophistication (frozen; consent paths only) · PRD-038 Phase 5 as-specified ·
pgvector & scale infra · generic chatbot/NL-explorer · framework-wide frontend rewrite ·
indiscriminate batch re-analysis.

## Model orchestration (from `model-settings-research.md` + this session's own evidence)

| Role | Model | Effort | Notes |
|---|---|---|---|
| Orchestrator (interactive sessions) | Opus 4.8 | default | Cheap, fast; dispatches everything below |
| Coder (bounded, spec'd work) | Sol via `codex exec` | **medium** | Sol docs: start lower; xhigh reserved |
| Independent research / ideation | Sol | **xhigh** | This session's pass-1 quality justifies it |
| Adversarial audit / critique | Sol | **xhigh** | The round-2 critique caught 5 real failure modes |
| Bulk mechanical (formatting, boilerplate) | Terra/Luna (Codex) or Haiku | low | 5× cheaper than Sol |
| Architecture, judgment, synthesis, narrative | Fable 5 | high (max for final adjudications) | ~6% of calls, most of the value |
| Case investigators (nightly) | Gemini 3.1 Pro (batch where possible) + one of Sol/Fable | med-high | Challenger only on disagreement |

Budget discipline: hard per-run caps; running out of tokens = a design error to post-mortem, not
a reason to buy more. Every session logs model/effort/cost per `ai-tool-audit.md` and appends
one meta-lesson about what the harness did well/badly.

## What both models missed until round 2 (logged for the meta-record)

The autonomy-boundary question (solved by sealed verdicts + the A/B) · multidimensional
permissions · prompt injection via archival evidence · abstention-as-value · citation
durability · sealed eval cases to prevent golden-case overfitting.
