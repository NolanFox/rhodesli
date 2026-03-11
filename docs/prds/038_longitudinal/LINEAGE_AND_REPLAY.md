# PRD-038: ML Lineage And Replay Requirements

**Parent**: [docs/prds/038_longitudinal_face_modeling.md](../038_longitudinal_face_modeling.md)
**Reviewed**: 2026-03-11

**Detailed schema companion**:
[docs/prds/038_longitudinal/PROMPT_AND_STATE_LINEAGE.md](PROMPT_AND_STATE_LINEAGE.md)

---

## Why This Matters

PRD-038 is not just about improving matching quality. It is also about making
matcher evolution auditable.

The key question is not only:
- "Who is this face grouped with now?"

It is also:
- "Which scorer version grouped this face that way?"
- "What candidates did the model consider at the time?"
- "When did that proposal appear, change, or disappear?"
- "Can we reconstruct state before and after a scorer refresh?"

For a single static model, partial logging is tolerable. For an iterative ML
system with retroactive discovery and future cloud workers, it is not.

---

## Current State

### What we have

1. **Identity state**
   - Current identity membership lives in the registry / identities payload.
   - Manual identity mutations now have append-only registry history.

2. **Discovery log**
   - `core/auto_cluster.py` appends per-face suggestion records to
     `data/discovery_log.json`.
   - Entries include face, source identity, target identity, tier, distance,
     timestamp, and later user decision.

3. **Latest proposals snapshot**
   - `scripts/cluster_new_faces.py` writes the latest run to `data/proposals.json`.

### What we do not have

1. **No run-level manifest**
   - No stable `cluster_run_id` / `scoring_run_id`
   - No scorer artifact version pinned on each ML decision
   - No input snapshot hash for identities / embeddings / metadata at run time

2. **No durable proposal history**
   - `proposals.json` is overwritten by the next run
   - It is not a historical ledger

3. **No full replay path**
   - We can often tell that a face was suggested or auto-clustered
   - We cannot reliably reconstruct the complete grouping state for a given
     scorer version at a prior moment in time

4. **No universal prompt lineage for Gemini-driven decisions**
   - Some interactive Gemini calls store full prompt / response and prompt
     metadata
   - Other Gemini paths still log only model, status, and summary fields
   - This makes prompt-family A/B tests much harder than model A/B tests

5. **Auto-cluster path is not fully aligned with registry event history**
   - ML candidate additions are partly visible through discovery logging
   - They are not yet modeled as a scorer-versioned assignment history

---

## Assessment

The current data structure is good enough for:
- current UI behavior
- human review workflow
- basic ML signal collection

It is **not yet good enough** for:
- scorer-versioned replay
- high-confidence rollback analysis
- comparing proposal diffs across matcher versions
- future queued/cloud ML execution with durable lineage

So yes: your concern is real, and it is important.

---

## Minimum Requirements Before PRD-038 Rollout

1. **Run manifest**
   - record one durable row/artifact per scoring run with:
     - `run_id`
     - scorer family / artifact version
     - git commit or artifact hash
     - thresholds / policy config
     - timestamp
     - input snapshot hashes for identities / embeddings / metadata slices

2. **Prompt manifest for Gemini-backed analysis**
   - record one durable prompt artifact per callable prompt family with:
     - `prompt_family` (`date_estimation`, `face_alignment`, `combined_enrichment`)
     - `prompt_version`
     - `prompt_variant`
     - response schema / contract version
     - context recipe flags (`gedcom`, `face`, `geo`, `time`, `batch`, `interactive`)
     - git commit or prompt artifact hash
   - each Gemini API call should reference these fields explicitly
   - exact prompt text should still be logged for replay, but the manifest is
     what makes A/B testing and grouped analysis practical
   - the concrete manifest and state-event envelope are specified in
     `PROMPT_AND_STATE_LINEAGE.md`

3. **Assignment event log**
   - record per-face or per-source-identity events with:
     - `run_id`
     - face id
     - source identity id
     - target identity id
     - action (`suggested`, `candidate_added`, `dedup`, `rejected`, `confirmed`, `undone`, `superseded`)
     - score / rank / tier
     - minimal explanation payload

4. **Supersession tracking**
   - when a new run replaces prior proposals, mark prior ML proposals as
     superseded by `run_id`, rather than silently losing the old state

5. **Replayability**
   - it must be possible to answer:
     - current proposals for a face
     - prior proposals for a face
     - first run that suggested a target identity
     - scorer version responsible for a proposal
     - prompt family / version / variant responsible for a Gemini output

---

## Implementation Direction

This should enter PRD-038 as a Phase 0 requirement, not a later cleanup task.

The app does **not** need a heavyweight "cluster object" model. The real unit of
lineage is:
- scoring run
- assignment event
- human decision on that event
- prompt artifact version for any Gemini-backed stage

That is enough to reconstruct how the ML flow grouped people over time.
