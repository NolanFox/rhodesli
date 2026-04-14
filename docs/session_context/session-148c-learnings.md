# Session 148c — Identification Methodology Learnings

## Context
Systematic identification of Nellie Kubrin and Abraham "Al" Fader in the Sarah Fox Fader Collection (147 photos, 328 faces). Started with Sherry Ann Fader (CONFIRMED) and Ira Josowitz (CONFIRMED) as anchor identities.

## What Worked (strongest to weakest)

### 1. Event Context — STRONGEST signal
Corsage, boutonniere, aisle walk, father-daughter dance, mother-groom dance identified relationships definitively. This required no ML — just understanding wedding conventions.

### 2. Cross-Photo Person Tracking
Same outfit across photos = same person at same event. The glasses/brocade woman appeared in 5+ wedding photos. Intra-event distances: 0.58-0.76 (tight cluster).

### 3. Age + Genealogy Filtering
Knowing birth/death years eliminated 85% of candidates. Of 328 faces, only ~10 were age-appropriate for Nellie (born 1909).

### 4. Full-Collection Clustering
Searching ALL faces and clustering by person found recurring people the initial filtered search missed.

### 5. Kinship Embedding Distance — WEAK signal
- Nellie → Sherry (mother-daughter): 1.29
- Al → Sherry (father, no blood relation): 1.38
- Gap: 0.09 — measurable but small. Useful as tiebreaker only.

## What Didn't Work

### 1. Sherry-Distance Filtering
Initial approach ranked 20 photos by distance to Sherry. This biased toward young women similar to Sherry and missed the older women we were looking for.

### 2. Cross-Collection Fox Similarity
Al Fader → Fox family: min 1.30, mean 1.38. Zero signal. Expected — he's not a Fox by blood. Cross-collection similarity is NOT useful for in-laws.

### 3. Single-Threshold Clustering
Same person split across 3 clusters due to glasses on/off, angle, lighting. Intra-person distances: 0.58-1.40. Need visual confirmation across clusters.

### 4. Chrome Browser for Photo Analysis
Expensive in credits/context, not auditable by Codex. Local Read tool is far more efficient.

## Genealogical Pitfalls

1. **Name collisions are common** — "Abe Fader" (died 1958) was a DIFFERENT person from Abraham "Al" Fader (died 1984). Other Ancestry trees propagated the wrong link.
2. **Verify with primary sources** — death certificates, cemetery records, burial plot family groupings.
3. **Who was alive changes everything** — the false 1958 death date temporarily reversed our entire hypothesis.

## Quantitative Signal Rankings

| Signal | Strength | Notes |
|--------|----------|-------|
| Event context (corsage, aisle) | VERY STRONG | Definitively identifies roles |
| Same-outfit cross-photo | STRONG | 0.58-0.76 intra-person dist |
| Age + genealogy filter | STRONG | Eliminates 85% of candidates |
| Co-occurrence with known person | MODERATE | Mother near daughter at events |
| Kinship embedding distance | WEAK | 0.09 gap mother vs non-blood |
| Cross-collection similarity | NONE | Useless for in-laws |

## Feature Proposals

### F1: Gemini Event Context Analyzer
Automate the strongest signal. Input: photo + known people. Output: event type, role indicators, estimated era/ages.

### F2: Cross-Photo Person Tracker
Given a face, find same person across collection. Handle within-event (same outfit, low dist) AND cross-event (different clothing, higher dist).

### F3: Investigation Workflow UI
Structured accept/reject/possible workflow with evidence tracking. Mirror the investigation JSON format.

### F4: Genealogical Cross-Reference
Auto-generate "who could be in photos from year X" lists from GEDCOM data.

### F5: Name Collision Detector
Flag when multiple people share same name in same era/geography.

### F6: Kinship-Weighted Search
Combine embedding distance, co-occurrence, age consistency, and event context into a composite identification score.

## Reference Files
- Investigation data: `docs/session_context/session-148c-investigation.json`
- Detailed search log: `docs/session_context/session-148c-nellie-search.md`
- Feedback items: `docs/feedback/session-148c-feedback.md`
- Research (kinship verification): Both subagent reports in session log
