# PRD-038: Prompt And State Lineage Schema

**Parent**: [docs/prds/038_longitudinal_face_modeling.md](../038_longitudinal_face_modeling.md)
**Reviewed**: 2026-03-11

---

## Purpose

PRD-038 will consume outputs from Gemini-backed analysis and repeated ML
rescoring. That only works safely if we can answer:

- which prompt family and variant produced a label
- which model or scorer used that label later
- which app action accepted, rejected, or reversed the result
- what the state was before and after the mutation

Raw prompt text alone is not enough. We need compact, queryable prompt and
state identities alongside full replay data.

---

## Design Principles

1. Every canonical mutation emits a durable event.
2. Every Gemini call stores both exact prompt text and a compact prompt-manifest identity.
3. Prompt versions track behavior, not only file hashes.
4. Undo and rollback are new events, never silent replacement.
5. Existing storage can remain if it carries the standard envelope.

---

## Scope

This schema applies to:

- Gemini-backed calls:
  - `date_estimation`
  - `re_analysis`
  - `face_alignment`
  - `combined_pipeline`
  - future review copilots or extraction helpers
- Canonical app mutations:
  - identity create / rename / confirm / reject / merge / undo / detach
  - annotation submit / approve / reject / skip / undo
  - discovery confirm / reject / supersede
  - GEDCOM link / unlink
  - relationship create / edit / delete
  - date-label or photo-location reanalysis writes
  - face-alignment refresh writes
  - active-learning label writes and reversals
- Offline ML jobs:
  - clustering / proposal runs
  - recalibration runs
  - longitudinal reranker training and shadow eval
  - adapter / LoRA experiments

---

## Object 1: `prompt_manifests`

One row or artifact per callable prompt definition.

### Required fields

- `prompt_manifest_id`
  - recommended shape:
    `date_estimation:v4:geo_time_face:contract2`
- `prompt_family`
  - examples: `date_estimation`, `face_alignment`, `combined_enrichment`
- `prompt_version`
  - main behavior version
- `prompt_variant`
  - branch within a version for A/B testing or specialized surfaces
- `prompt_contract_version`
  - output schema / parser contract version
- `channel`
  - `interactive`, `batch`, `admin_rerun`, `shadow_eval`
- `context_flags`
  - booleans such as `uses_gedcom`, `uses_face_coords`, `uses_geo`, `uses_time`
- `template_source`
  - file or function path
- `prompt_hash`
  - canonical rendered-template or template-definition hash
- `git_commit`
- `status`
  - `active`, `shadow`, `deprecated`
- `created_at`
- `notes`

### Versioning rules

- If instructions change in a way that may affect outputs, bump
  `prompt_version` or `prompt_variant`.
- If output structure or parser expectations change, bump
  `prompt_contract_version`.
- Hash changes are evidence, not the human-facing versioning strategy.
- Multiple routes may share one family but use different variants.

---

## Object 2: `gemini_api_calls`

Keep the current per-call logging table, but require prompt-manifest linkage.

### Existing must-keep fields

- `photo_id`
- `model_used`
- `call_type`
- `prompt_text`
- `full_response`
- `status`
- tokens / cost / latency
- `gemini_config`

### Required additions

- `prompt_manifest_id`
- `prompt_family`
- `prompt_version`
- `prompt_variant`
- `prompt_contract_version`
- `prompt_hash`
- `full_response_hash`
- `experiment_id`
  - for A/B or shadow prompt tests
- `shadow_run_id`
  - for non-user-facing experiments
- `request_surface`
  - route or job name
- `request_mode`
  - `interactive`, `batch`, `shadow`, `admin_tool`
- `related_state_event_id`
  - if this call directly triggered a canonical write
- `contract_valid`
  - parser/schema validation result

### Why this matters

These fields make it easy to ask:

- which prompt variant produced the labels that later fed Phase 2 features
- whether `face_alignment:v3:gedcom_curated` outperformed `face_alignment:v3:visual_only`
- whether a prompt regression came from instructions, model change, or parser change

---

## Object 3: Canonical State Event Envelope

Use a shared mutation envelope for every canonical write. Existing sinks such as
`audit_log`, registry history, or future dedicated tables may store it, but the
payload shape should be standardized.

### Required fields

- `event_id`
- `target_type`
  - `identity`, `annotation`, `relationship`, `gedcom_link`,
    `date_label`, `photo_location`, `face_alignment`, `active_learning_label`
- `target_id`
- `action`
- `actor_type`
  - `admin`, `community_user`, `system`, `model`
- `actor_id`
- `source_surface`
  - route, page, job, or script
- `community_id`
- `before_state`
- `after_state`
- `changed_fields`
- `reason_code`
- `request_id`
- `linked_event_id`
  - for undo / supersede / reversal chains
- `ml_run_id`
  - when a model run caused or proposed the change
- `prompt_manifest_id`
  - when a Gemini call is directly relevant
- `created_at`
- `reversed_by_event_id`

### Mutation rules

- Only canonical writes need this envelope.
- Read-only views and analytics events do not.
- Undo is represented as a new event linked to the prior event.
- Model proposals that are later accepted should keep the proposal and the
  acceptance as separate linked events.

---

## Object 4: `ml_run_manifests` And Assignment Events

This extends the replay model in
[LINEAGE_AND_REPLAY.md](LINEAGE_AND_REPLAY.md).

### `ml_run_manifests`

- `ml_run_id`
- `run_type`
  - `cluster`, `recalibration`, `reranker_train`, `reranker_shadow`, `adapter_experiment`
- scorer or artifact version
- git commit
- input snapshot hashes
- thresholds / policy config
- started / finished timestamps
- parent run id if derived from another run

### `ml_assignment_events`

- `ml_run_id`
- source identity / face id
- target identity id
- action
  - `suggested`, `candidate_added`, `dedup`, `rejected`, `confirmed`, `superseded`
- score / rank / tier
- explanation payload
- linked state event id if a human decision followed

---

## Coverage Matrix For Phase 0

Phase 0 should inventory every canonical mutation path and mark it:

- `covered`
- `partial`
- `missing`

Minimum expected coverage:

- identity workflow routes
- annotation moderation routes
- discoveries / cluster-review routes
- GEDCOM linking routes
- relationship editing routes
- date/location reanalysis routes
- face-alignment save / refresh routes
- active-learning label routes

The goal is not to replace every store immediately. The goal is to ensure no
canonical mutation is invisible.

---

## Safe Parallelization

Three tracks are reasonable if file overlap stays low:

1. Prompt manifests + `gemini_api_calls` schema / validation
2. State-event inventory + highest-risk route instrumentation
3. `ml_run_manifests` + assignment-event lineage for scorer jobs

If overlap becomes messy, collapse back to one track.

---

## Acceptance Gates

Before PRD-038 rollout:

1. Every app-facing Gemini path has a prompt manifest identity.
2. Every canonical mutation route is either instrumented or explicitly deferred in a written gap list.
3. At least one A/B-ready query is documented and runnable by manifest fields.
4. At least one full replay path is documented:
   `Gemini output -> canonical write -> downstream ML feature -> proposal event`.
5. No ML proposal history is lost purely because `proposals.json` was overwritten.
