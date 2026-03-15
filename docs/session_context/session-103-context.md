# Session 103 Context — ML Pipeline Execution + Triage Feedback

**Predecessor:** `docs/session_context/session-102-context.md`
**Date:** 2026-03-15
**Current:** v0.99.5, ~4296 tests, 941 photos, 1922 active identities, 91 confirmed

---

## Why This Session Exists

Session 102 Phase 7 was supposed to **run the ML pipeline end-to-end** — evaluate whether confirmed labels improve clustering, compare reranker vs baseline, and give a real answer on whether constrained clustering works. Instead, it wrote two PRDs (045, 046) and a research doc. No pipeline was run. No comparison was made. No tables were created.

This session executes the work that should have been done.

Additionally, Session 102's triage sprint (Phase 8) produced UX feedback that needs to be addressed.

---

## Part 1: ML Pipeline — What Exists

### PRD-038 Infrastructure (Session 97, all shipped but gated)

| Module | Path | Status |
|--------|------|--------|
| Longitudinal reranker | `rhodesli_ml/longitudinal_reranker.py` | Shadow mode, gates closed |
| Active learning | `rhodesli_ml/active_learning.py` | Offline queue, label persistence |
| Embedding adapter | `rhodesli_ml/embedding_adapter_experiment.py` | Experiment harness, frozen |
| Calibration lineage | `rhodesli_ml/calibration_lineage.py` | Append-only audit trail |

### Clustering Pipeline (`scripts/cluster_new_faces.py`)

- Loads confirmed identities (CONFIRMED state, no merged_into)
- For each unresolved face (INBOX/PROPOSED): find closest confirmed match via `cdist`
- Filters by threshold (MATCH_THRESHOLD_HIGH = 1.05)
- Writes to `data/proposals.json` (17 proposals, last run 2026-03-10)
- **Can load reranker** with `--scorer longitudinal-shadow` flag but defaults to `baseline`
- **No run tracking** — proposals.json overwritten each time
- **No constraints** from confirmed pairs (no must-link/cannot-link)
- Rejects pairs in `negative_ids` only

### Label Inventory

- 91 confirmed identities, 382 total confirmed faces (anchor + candidate)
- Sufficient for constrained clustering evaluation per PRD-045

### PRD-046 Tables

- **Not created.** `ml_runs` and `ml_proposals` Supabase tables don't exist.
- `compare_ml_runs.py` script doesn't exist.
- No run history, no A/B testing capability.

---

## Part 2: Triage Feedback (Session 102 Phase 8)

### FB-147: Big Leon Capeluto keeps appearing as suggested match
- Person 3048 (8 faces) is clearly Albert Fox, but suggestions show Big Leon Capeluto (25 faces, Rhodes)
- Root cause: nearest-neighbor search is cross-community, doesn't penalize cross-community matches
- Related: PERF-007 (similar panel not community-scoped)
- Fix: rank Fox Family confirmed identities first; only show cross-community if genuinely strong match

### FB-148: Cross-community badge too verbose
- Badge says "From Jewish Community of Rhodes" — the "From" is redundant
- Should just be community name badge (e.g., "Jewish Community of Rhodes" or "Rhodes")
- The badge placement already implies provenance

### FB-149: Post-merge enrichment flow too slow — auto-advance needed
- After merging into a named, tree-linked person (e.g., Albert Fox), the panel still shows suggested matches, name input, GEDCOM link, and "Done — Next Cluster" at the bottom requiring a scroll
- If merged into someone who already has a name + GEDCOM link, should auto-advance to next cluster
- If name/tree missing, show compact inline prompt then advance
- Post-merge, the suggested matches section is irrelevant — decision is already made

### FB-150: Speed Loop lost face card navigation (REGRESSION)
- Suggestion thumbnails in Speed Loop (e.g., "Roland F...") are not clickable
- Previously you could click through to inspect all faces of a suggested match before deciding
- Now you can only confirm/reject blind — no way to verify a match
- This is a regression from Session 102 Track C navigation changes

### FB-151: Suggestion name truncated in Speed Loop
- "Roland F..." not enough info to make a decision — should show full name

### FB-152: No way to inspect suggested match from Speed Loop
- Should be able to click suggestion thumbnail to open person's face card (new tab or panel)
- Currently only actions are confirm/reject — no "let me look first" flow

### FB-153: /identify/ page shows wrong community for Fox Family identity
- Person 4066 is in Fox Family but /identify/ page says "appears in photos from Jewish Community of Rhodes"
- Another manifestation of DATA-019 incomplete fix — identity community membership not updated

### FB-154: Finding a specific identity by number is too hard
- Had to switch communities, sidebar search, browse results — 7 steps
- Need direct URL or admin search (e.g., `/admin/identity/4066` or global search)

### FB-155: "View in Admin Queue" link missing community prefix (COMMUNITY-015)
- URL is `/?section=to_review&view=browse#identity-{id}` — should be `/c/fox-family/...`
- Third instance of COMMUNITY-015 found in this triage
- Systemic issue: need a sweep of ALL internal links, not one-at-a-time fixes

---

## Part 3: Session 102 Gaps (from audit)

| ID | Gap | Priority |
|----|-----|----------|
| PERF-007 | Similar panel results not filtered by community | P2 |
| TEST-003 | DATA-019 script lacks automated test | P2 |
| TEST-004 | DATA-020 name guard lacks unit test | P2 |
| OBS-003 | Keyboard vs button input_method not logged | P3 |

---

## Part 4: Cross-References

- PRD-038: `docs/prds/038_longitudinal_face_modeling/` (Session 97)
- PRD-045: `docs/prds/045_active_learning_feedback_loop.md` (Session 102, draft)
- PRD-046: `docs/prds/046_ml_run_provenance.md` (Session 102, draft)
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md` (AD-001 through AD-223)
- Active learning research: `docs/ml/ACTIVE_LEARNING_RESEARCH.md`
- Proposals: `data/proposals.json` (17 proposals from 2026-03-10, baseline scorer)
- Clustering: `scripts/cluster_new_faces.py`

---

## Deferred from this context

- TOOLS-002 (ML service extraction) — separate concern
- Phase 5 longitudinal adapter graduation — needs more labels first
- Multi-GEDCOM support — separate feature track
