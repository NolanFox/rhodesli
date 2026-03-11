# PRD-038: Research Review & External References

**Parent**: [docs/prds/038_longitudinal_face_modeling.md](../038_longitudinal_face_modeling.md)
**Reviewed**: 2026-03-11

---

## Local Repo Findings That Change The Plan

- The repo now has **84 confirmed identities**, **28 multi-face confirmed identities**, and about **1,453 same-identity pairs** from current confirmed faces.
- The blocker for adapter work is no longer raw pair count. It is **representation skew**: current positive-pair Gini is about **0.788**.
- The repo has **271 / 271** photo date labels with year estimates and **331** same-identity pairs with photo-year coverage. **54** of those have year gaps >= 20.
- The current eval scripts are stale against the live embedding schema.
- A schema-aware local check on the current golden set shows **Euclidean AUC about 0.978** and **MLS about 0.953**, so the new plan must beat a strong frozen-embedding baseline.

---

## Academic And Product References

| Source | Key takeaway | Plan impact |
|---|---|---|
| CACon, arXiv 2024: https://arxiv.org/abs/2408.00797 | Cross-age FR still needs explicit age handling; identity-conditioned age adaptation is an active research direction. | Treat age-gap performance as a first-class slice, not a side metric. |
| CALFW benchmark: https://www.whdeng.cn/CALFW/index.html | Age gaps measurably hurt verification relative to standard LFW-style benchmarks. | Keep a dedicated age-gap challenge set for Rhodesli. |
| QMagFace, arXiv 2024: https://arxiv.org/abs/2408.07850 | Face-quality estimation can be learned from the embedding magnitude and improves quality-aware recognition. | Use quality-aware prototype weighting; do not treat all anchors equally. |
| PETALface, arXiv 2023: https://arxiv.org/abs/2312.11195 | Quality-adaptive LoRA can adapt low-quality faces while preserving high-quality performance. | If we fine-tune, prefer PEFT with quality conditioning over blunt LoRA on all samples. |
| Photo Sleuth paper page: https://photo-sleuth.com/ | Historical-photo identification benefits from human-in-the-loop evidence review, not silent automation. | Integrate active learning into review UX with provenance and explanations. |
| Google Photos face grouping / live albums: https://support.google.com/photos/answer/6128843?co=GENIE.Platform%3DAndroid&hl=en | Consumer expectation is that face groups power ongoing discovery and automatically updated people collections. | Additive retroactive discovery is a product win if review UX stays tight. |
| Reddit user thread on Google Photos grouping pain: https://www.reddit.com/r/googlephotos/comments/10nmhee/face_detectiongrouping_quality_on_google_photos/ | Users complain most about wrong merges, relatives being grouped together, and poor repair tools. | Optimize for kin false positives and one-click reject / detach, not just top-line accuracy. |
| Immich community request on birth-date-aware face sorting: https://github.com/immich-app/immich/issues/10583 | Power users explicitly want temporal metadata to constrain face clustering and browsing. | Birth-year and photo-year signals are product-relevant, not academic garnish. |

---

## Prompt, Agent, And Context Engineering References

| Source | Key takeaway | Plan impact |
|---|---|---|
| OpenAI GPT-5 prompting guide: https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide | Best results come from issue-style prompts, explicit success criteria, and persistent repo instructions such as `AGENTS.md`. | Session 97 prompt is written as a scoped implementation brief with concrete gates, not a loose brainstorming note. |
| Anthropic, Building Effective Agents: https://www.anthropic.com/engineering/building-effective-agents | Start with simple, composable patterns; use evaluator-optimizer loops and parallel workers only when boundaries are clear. | Session 97 uses phase gates plus optional worktree parallelism only for disjoint files. |
| Anthropic prompt engineering overview: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview | Give the model the right context, structure the task, and keep instructions explicit rather than implied. | The context file is phase-scoped so later implementation reads only the files needed for the current act. |

---

## Operational Scaling References

| Source | Key takeaway | Plan impact |
|---|---|---|
| SageMaker async inference: https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html | Queue-first async inference is built for long-running jobs, large payloads, and scale-to-zero operation. | If Rhodesli outgrows local runs, the first cloud move should be queued offline scoring and retraining, not synchronous web inference. |
| SageMaker autoscaling for async endpoints: https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html | Async endpoints can scale to zero and back up on demand. | Future cloud extraction should keep idle cost near zero between ingest or retraining bursts. |
| Modal job queues: https://modal.com/docs/guide/job-queue | Web app to job queue to poll/result is a clean pattern for long-running Python tasks. | The offline scorer interface should be artifact-based and job-oriented so it can move off the laptop without changing the app contract. |
| Ray Serve dynamic batching: https://docs.ray.io/en/latest/serve/advanced-guides/dyn-req-batch.html | Batching improves throughput once online serving becomes worthwhile. | Real-time batching is a later concern for compare/live tools, not a reason to change the PRD-038 offline-first plan now. |

---

## What The Research Supports

### 1. Quality-aware matching is low-risk and high-value

- The external literature and current repo baseline both support anchor quality as a real signal.
- The repo already stores useful proxies: `det_score`, `quality`, and `sigma_sq`.
- This supports a near-term move from "closest anchor wins" to "closest trustworthy prototype wins."

### 2. Cross-age performance needs explicit slice tracking

- Benchmarks like CALFW show age-gap degradation is real.
- The Rhodesli archive now has enough dated same-identity pairs to track this locally.
- That supports a frozen-embedding longitudinal reranker before any base-model adaptation.

### 3. Heritage archives need assisted review, not opaque automation

- Photo Sleuth is the clearest analogous product in this space.
- Community and Reddit signals point in the same direction:
  - false merges are expensive
  - users want clear provenance
  - repair tooling matters as much as raw matching quality

### 4. Adapter training is viable, but only if we guard against skew

- PETALface makes PEFT more credible than it was when the original PRD was written.
- The current Rhodesli data snapshot now supports experiments.
- The remaining risk is not "too few pairs"; it is "too many pairs from too few people."

### 5. The implementation prompt itself needs engineering discipline

- OpenAI and Anthropic guidance converges on the same pattern:
  - small scoped tasks
  - explicit outputs
  - evaluation loops
  - minimal but sufficient context
- That is why the Session 97 package includes a dedicated prompt and context file instead of relying on chat history.

### 6. Cloud migration should begin with queued offline work, not online inference

- The scaling literature and current Rhodesli constraints both point to the same migration order:
  - keep web requests light
  - move offline scoring / retraining into queued workers first
  - add batching only when live inference volume justifies it
- This matches AD-110 and the existing ML service architecture draft.

---

## Research-Driven Recommendations

1. Do not make "best face per decade" the main abstraction. Use a small quality-aware prototype bank per identity.
2. Do not push metadata into the legacy isotonic module. Use a multifeature reranker with optional post-hoc calibration.
3. Do not greenlight adapter work off global AUC alone. Require wins on:
   - year-gap >= 20 recall
   - same-family false positive rate
   - community-safe proposal diffs
4. Do not hide active learning in a disconnected widget. Put it where review already happens.
5. Do not let research or user feedback live only in chat state. Every new source or requirement should land in a harness artifact before it shapes implementation.
6. Do not couple the future cloud migration to PRD-038 launch. Keep the scorer interface job-oriented now so queued cloud execution is an extraction, not a rewrite.

---

## Sources For Future Prompt Prep

These sources should be copied into the later implementation context file because they directly shaped the architecture choice:

1. CACon
2. CALFW
3. QMagFace
4. PETALface
5. Photo Sleuth
6. Google Photos grouping / live albums
7. Community complaints about grouping repair
8. OpenAI GPT-5 prompting guide
9. Anthropic agent / prompt engineering guides
10. Async queue / batch serving references for future cloud extraction
