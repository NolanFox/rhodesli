# Session 97 Post-Gemini Assessment

**Date:** 2026-03-11
**Author:** Codex
**Reviewed Gemini commits:**
- `9907989` — `[gemini] docs(ml): review PRD-038 session 97 package`
- `da4f288` — `[gemini] docs(ml): wire review feedback into session 97 prompt and context`

---

## Verdict

Gemini's work was strong and worth keeping.

The review was high-signal, technically aligned with the direction of the SDD,
and it surfaced three meaningful risks that the original package had not made
explicit enough:
- active-learning label toxicity and undoability
- prototype-bank temporal collapse toward one era
- reranker overfitting to dominant families

The weakest part of Gemini's work was source hygiene. Several "research
additions" were directionally useful but not cited precisely enough to meet the
repo's normal breadcrumb standard. I kept the substance where it held up, but I
added exact supporting sources in the research doc rather than treating
Gemini's prose as sufficient evidence by itself.

---

## What Gemini Got Right

1. **Active-learning undoability is a real gap.**
   - I agree that review-time labels should remain reversible until they are
     consumed by recalibration.

2. **Temporal diversity must outrank raw face quality in prototype selection.**
   - I agree with the core point. A prototype bank that collapses onto one era
     defeats the purpose of longitudinal modeling.

3. **Dominant-family bias needs an explicit evaluation check.**
   - I agree that overall lift can be misleading if gains come only from the
     most overrepresented families.

4. **`core/auto_cluster.py` should be the offline source of truth.**
   - I already leaned this way in the SDD and Gemini correctly sharpened it.

5. **The local-to-cloud migration order is sensible.**
   - Gemini's endorsement of queued offline workers before online inference is
     consistent with the repo constraints and with the scaling research.

---

## Where I Modified Gemini's Recommendations

### 1. "Implement the 4 recommended changes"

I did **not** keep this as a blanket instruction in the Session 97 prompt.
That wording was too rigid for a review artifact.

**What I changed instead**
- The prompt now says future implementation must evaluate Gemini's
  recommendations one by one and either adopt them or document a reasoned
  rejection before proceeding.

**Why**
- Review feedback should constrain implementation, but not become an
  unquestioned source of truth.

### 2. "Log the Gini coefficient of the newly rebuilt golden set"

I **modified** this recommendation.

**What I changed instead**
- The prompt/SDD now require logging skew and concentration metrics for the
  rebuilt training and evaluation assets, not only the golden set.

**Why**
- The main skew risk is in the pair/training distribution, not just the eval
  asset. Logging only golden-set Gini would create false comfort.

### 3. "Add a boolean `has_kinship_risk` feature"

I **partially adopted** this recommendation.

**What I changed instead**
- The plan now requires at least one explicit kinship-risk feature and leaves
  the exact representation open to testing.

**Why**
- The idea is good, but a single hardcoded boolean may be too blunt. The scorer
  may benefit from a small kinship-risk feature family instead.

### 4. "Actionable audit log UI"

I **adopted the requirement** but softened the implementation form.

**What I changed instead**
- The plan now requires an actionable audit/revert path before recalibration,
  without prematurely forcing a specific UI implementation.

**Why**
- The reversibility guarantee matters more than whether the first version is a
  full dedicated UI page.

---

## What I Adopted Directly

These points are now reflected in the planning package:

1. `core/auto_cluster.py` as the batch-matching source of truth
2. temporal-diversity override in prototype-bank selection
3. dominant-identity bias checks in evaluation gates
4. active-learning label audit/revert requirement

Files updated to reflect this:
- `docs/prds/SDD-038_longitudinal_face_modeling.md`
- `docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md`
- `docs/prompts/session-97-prompt.md`

---

## Source Quality Assessment

Gemini's review cited good themes but weakly attributed them:

1. **CACon / CALFW**
   - Valid, but not net-new. These were already in the package.

2. **Dual-encoder vs cross-encoder / retrieve-rerank**
   - Good conceptual support.
   - Gemini did not provide an exact source link, so I added Sentence
     Transformers references to the research doc.

3. **Active learning in low-volume medical imaging**
   - Directionally useful analogy.
   - Gemini did not provide a precise paper link, so I added exact references
     for an active-learning survey and a diversity-aware selection paper.

4. **Google Photos kin false merges**
   - Valid and consistent with the earlier Reddit / product evidence already in
     the package.

Overall source assessment:
- **Reasoning quality:** high
- **Citation quality:** medium
- **Net-new evidence quality after validation:** medium-high

---

## Net Assessment Of Gemini's Work

Gemini improved the package. The work was especially good at:
- spotting practical failure modes
- preserving the core architecture while tightening guardrails
- reinforcing the local-first, cloud-ready design

The work was weaker at:
- precise source attribution
- distinguishing "must adopt" from "good candidate to evaluate"

That is why I kept the review artifact intact, incorporated the strong parts,
and documented the modified parts rather than reverting them silently.

---

## Follow-Up Gap

If we ask Gemini one more question, the highest-value follow-up would be:
- give exact citations for each "Research Additions" claim
- propose concrete metrics / fixture designs for dominant-identity bias and
  active-learning label-toxicity tests

That would turn Gemini's strongest qualitative feedback into directly
implementable evaluation requirements.
