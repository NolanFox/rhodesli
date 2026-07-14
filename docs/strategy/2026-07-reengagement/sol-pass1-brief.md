# Brief for GPT-5.6-Sol — Rhodesli Re-Engagement Deep Dive (Pass 1, independent)

You are Sol, running with xhigh reasoning inside the rhodesli repo (`/Users/nolanfox/rhodesli`).
You are one of two independent architects (the other is Claude Fable 5; you will not see its
draft and it will not see yours — a third model adjudicates). Do NOT play it safe. Do not
produce an audit. Produce the most ambitious, technically-grounded plan you can defend.

## The owner's situation (his words, distilled — treat as ground truth)

- "I've noticed I haven't been working on this project as much... because I haven't been making
  progress in the core things I'm interested in: **documenting the history of people from the
  Jewish community of Rhodes**, and **identifying family in photos**."
- Facebook groups hold the source material, but extracting it safely (without violating TOS and
  getting banned) has been hard — this stalled the rhodes-wiki pipeline.
- "We haven't been making a lot of progress in facial recognition, and scaling it out just
  hasn't been as exciting. We're not at the point where we can get a lot of users until we
  really build out that use case better."
- He LOVED the Fox/Heft research spinoffs — deep per-photo forensic investigations (multi-model
  date/location estimation with GEDCOM anchoring, identity hypotheses across photos, the 1946
  anniversary photo work, Harry Fox validation). That work felt like *discovery*.
- Dream: "a whole database of Rhodesli photos" — and eventually a way for other families to do
  this for their own people, but "we need to nail this use case first."
- Constraint change: this started when he was between jobs; now he has a job. The project must
  yield **substantive progress day-over-day as a side project** — sessions that run largely
  autonomously and end with something visibly better.
- Explicitly in scope: new data-science/facial-recognition work; refreshing the model/API
  integrations (they may be dated — frontier multimodal models have improved a lot); actually
  fixing desktop+mobile UX now that coding models are good at frontend.
- Explicitly NOT the answer: "a plan that is just tying up a couple of security loose ends."

## What exists (verify in-repo; read what you need)

- `ROADMAP.md` — current state, v0.99.90, ~5353 tests, 1127 photos, 1824 identities, live site.
- `docs/fable-eval/2026-07-05-security-growth/GROWTH_ROADMAP.md` — the previous plan (phases
  A-D: safety → trust loop → multi-tenant → polish). Competent but it's what failed to excite.
- `docs/fable-eval/GROWTH_10X.md`, `SITE_VISION_AUDIT.md` — earlier growth bets.
- `tasks/lessons.md` + `tasks/lessons/` — 200+ lessons; repeat-offender failure modes.
- `docs/ml/ALGORITHMIC_DECISIONS.md` — every ML decision (calibration AUC=0.9577, prototype-bank
  reranker shipped-but-neutral, Family Cluster Score, temporal co-occurrence, PRD-038 gates).
- `/Users/nolanfox/rhodes-wiki/` (read-only sibling) — FB post → markdown vault → rhodesli inbox
  pipeline. v0.2.0. Stalled on the FB extraction friction. `docs/ARCHITECTURE.md` there.
- ML stack: InsightFace (buffalo_l) embeddings, 512-dim, ~3000 faces; isotonic-calibrated
  similarity; Gemini 3.1 Pro for date/location estimation; two-tier auto-clustering.
- `scripts/multimodel_photo_estimate.py` — the Fox/Heft-style multi-model forensic workflow he
  loved (Gemini + Fable + Codex compared, best written to DB).

## What I want from you (write ALL of it to
`docs/strategy/2026-07-reengagement/sol-pass1.md` — create the file, overwrite if exists)

1. **Diagnosis (short):** why did engagement collapse? Read the evidence, don't flatter.
2. **The idea slate — 12+ concrete ideas**, each with: what it is, why it serves the two core
   loves (history documentation + photo identification), what makes it *newly* possible in 2026
   (model capabilities, tooling), effort shape (can it produce visible progress in 1-2h
   autonomous sessions?), and a 0-10 excitement score with one-line justification. Cover at
   least: (a) facial-recognition/data-science upgrades worth doing at 3K-face scale, (b) the
   photo-database/ingestion problem including TOS-safe Facebook strategies, (c) research/
   storytelling automation (the Fox/Heft magic, industrialized), (d) API/model refresh,
   (e) UX rebuild opportunities. Add categories I haven't thought of.
3. **Kill list:** what current roadmap items should be explicitly deprioritized and why.
4. **Your top-3 "start Monday" picks** with a concrete first-session definition of done.
5. **Where you disagree with the premise** — anything the owner believes that the evidence
   contradicts.

Rules: cite real files/line-level evidence when you make claims about the codebase. Prefer
ideas that compound (each session's output feeds the next). Assume a multi-model harness
(you for coding/research, Fable for architecture/judgment, Opus for orchestration) — design
ideas that exploit it. Do not write any code. Do not modify anything except creating your
output file.
