# Temporal Co-Occurrence Research for PRD-059

**Date:** 2026-03-27
**Purpose:** Research summary for temporal co-occurrence analysis in family photo archives
**Scope:** Academic papers, industry practice (Google/Apple Photos), and genealogy-specific tools

---

## 1. Temporal Event Clustering

### Core Technique: Time-Gap Segmentation
The foundational work (Loui & Savakis, 2003) proposes partitioning photo collections into events based on temporal gaps between adjacent photos. The simplest approach uses a fixed threshold (e.g., 1 hour between photos = new event), but adaptive thresholds that respond to local photo density perform better.

**Relevance to Rhodesli:** Our photos span 1920s-1960s and lack EXIF timestamps. However, Gemini-estimated dates (AD-139) provide approximate year ranges. We can cluster photos into "eras" (5-10 year windows) rather than events, and use co-occurrence within an era as a weaker but still useful signal.

**Key algorithm:** Multi-scale temporal similarity -- compute inter-photo time gaps at multiple granularities (year, decade) to identify natural clusters. For undated photos, use visual similarity of backgrounds, clothing styles, and paper/print quality as proxy temporal signals.

**Source:** [Temporal Event Clustering for Digital Photo Collections](https://dl.acm.org/doi/10.1145/1083314.1083317) (ACM TOMM, 2003)

---

## 2. Apple Photos: Two-Pass Clustering with Temporal Constraints

### Architecture
Apple's on-device face recognition uses a two-pass agglomerative clustering approach:

1. **Pass 1 (Conservative):** Clusters faces using combined face + upper body embeddings, restricted to the same "moment" (photos taken close in time/location). Within a moment, a person wears the same clothing, so upper body similarity is a reliable signal. Distance formula: `D_ij = min(F_ij, alpha*F_ij + beta*T_ij)` where F = face distance, T = upper body distance.

2. **Pass 2 (Cross-temporal):** Uses hierarchical agglomerative clustering (HAC) with median-linkage across all moments, using face embeddings only (since clothing changes over time). Recursively merges cluster pairs that minimally increase linkage distance.

**Key insight:** Temporal proximity makes non-face signals (clothing, body shape) reliable. Cross-temporal matching must rely on face-only features.

**Relevance to Rhodesli:** We already have face embeddings (InsightFace 512-dim). We could adopt the two-pass pattern: (1) within estimated-same-era, use both face similarity AND co-occurrence as signals; (2) across eras, rely on face similarity alone but with age-adjusted thresholds. Our Gemini date estimates map to Apple's "moments" at a coarser granularity.

**Source:** [Recognizing People in Photos Through Private On-Device Machine Learning](https://machinelearning.apple.com/research/recognizing-people-photos) (Apple ML Research, 2021)

---

## 3. Google Photos: Face Grouping with Temporal + Clothing Signals

Google Photos groups faces using embedding similarity, but augments this with:
- **Temporal proximity:** Photos taken close together are more likely to contain the same people
- **Clothing consistency:** Same clothing across nearby photos helps link faces even when face quality is poor
- **Torso features:** Used as auxiliary signal within same-event windows
- **User feedback loop:** Confirmed/corrected identifications improve clustering over time

**Relevance to Rhodesli:** Our Gatekeeper pattern (proposals -> admin review -> confirmed) is structurally similar to Google's feedback loop. Confirmed identities should feed back as hard constraints for re-clustering, which we already do via anchor_ids. The clothing signal is less useful for our archive (black-and-white, formal wear), but co-occurrence in the same physical photograph is a very strong signal.

**Source:** [Google Patent US8189880B2](https://patents.google.com/patent/US8189880B2/en); [Google Photos Face Grouping Help](https://support.google.com/photos/answer/6128838)

---

## 4. Family Member Identification from Photo Collections

### Dai et al. (WACV 2015) -- Probabilistic Framework
This paper directly addresses our use case: identifying family members across a photo collection. Key contributions:

- **Family structure as constraint:** A family has at most one father, one mother, one grandfather, one grandmother, but multiple children. This structural prior dramatically reduces the search space.
- **Co-occurrence as evidence:** Family members appear together across multiple photos. The frequency and pattern of co-occurrence provides probabilistic evidence for relationships.
- **Temporal validity:** Parent-child relationships must respect biological age constraints (parents older than children).
- **Probabilistic graphical model:** Combines individual face identification scores, relationship constraints, temporal validity, and co-appearance frequency into a unified framework.

**Relevance to Rhodesli:** This is highly relevant. We have GEDCOM data that provides exactly these family structure constraints. We know who is married to whom, who are siblings, parent-child relationships, and birth/death years. Combining GEDCOM structure + face embeddings + co-occurrence in photos could dramatically improve identification accuracy.

**Specific adoption:** Build a scoring function: `S(identity, face) = w1*embedding_similarity + w2*co_occurrence_score + w3*temporal_plausibility + w4*gedcom_prior`. The GEDCOM prior would encode: "if Person A is already identified in this photo and Person B is their spouse, the probability that an unidentified face in the same photo is Person B increases."

**Source:** [Family Member Identification from Photo Collections](http://dhoiem.cs.illinois.edu/publications/dai_disney_wacv2015.pdf) (WACV 2015)

---

## 5. Constrained Clustering: Must-Link / Cannot-Link

### Pairwise Constraints from Photo Context
The face clustering literature (Zhu et al., 2017; Wu et al., CVPR 2013) introduces constraint-based clustering:

- **Must-link constraints:** "These two faces belong to the same person" (from admin confirmation)
- **Cannot-link constraints:** "These two faces are NOT the same person" (from rejection, or from co-occurrence -- two different faces in the same photo cannot be the same person)
- **Propagation:** If A must-link B and B must-link C, then A must-link C (transitivity). Similarly for cannot-link under certain conditions.

**Key insight for Rhodesli:** Co-occurrence in the SAME photo generates automatic cannot-link constraints. If Face X and Face Y are both detected in Photo P, they are definitionally different people. This is free, automatic, and 100% reliable. We should exploit this systematically.

**Algorithm:** Conditional Pairwise Clustering (ConPaC) directly estimates an adjacency matrix using both similarity and constraints, allowing dynamic cluster count selection.

**Relevance to Rhodesli:** We already have cannot-link data (faces in same photo) and must-link data (admin-confirmed anchor_ids). We also have negative_ids (explicit rejections). These should be formalized as hard constraints in our clustering pipeline.

**Source:** [Face Clustering: Representation and Pairwise Constraints](https://arxiv.org/abs/1706.05067) (IEEE TIFS, 2017); [Constrained Clustering in Videos](https://openaccess.thecvf.com/content_cvpr_2013/papers/Wu_Constrained_Clustering_and_2013_CVPR_paper.pdf) (CVPR 2013)

---

## 6. Cross-Age Face Recognition

### The Age Problem
Faces change significantly over decades. For our 1920s-1960s archive, the same person may appear as a child, young adult, and middle-aged. Key techniques:

- **Age-Invariant Feature Extraction:** Decompose facial features into identity features (stable across age) and age features (variable). AT-GAN achieves 97.53% on AgeDB-30 by disentangling these. However, this requires training data with known age progression -- which we have via GEDCOM birth years + estimated photo dates.
- **Young Parent Bridging:** Use younger photos of parents as intermediary to bridge the appearance gap between children and elderly parents.
- **Cross-generation GANs:** De-age older faces to reduce appearance gap before comparison. Computationally expensive and currently beyond our scope.

**Practical approach for Rhodesli:** Rather than age-invariant features (which require retraining our embedding model), use age-aware distance thresholds. If Gemini estimates Photo A at ~1925 and Photo B at ~1955, and Person X was born in 1910, they would be ~15 in Photo A and ~45 in Photo B. Apply a looser matching threshold for this 30-year gap compared to faces from the same decade.

**Threshold scaling formula (proposed):**
```
adjusted_threshold = base_threshold + alpha * age_gap_years
```
Where `age_gap_years = abs(estimated_age_in_photo_A - estimated_age_in_photo_B)` and alpha is calibrated from confirmed cross-age matches.

**Source:** [Cross-Age Facial Recognition with AT-GAN](https://pmc.ncbi.nlm.nih.gov/articles/PMC12063864/) (PLOS ONE, 2025); [Face Age Synthesis Survey](https://www.sciencedirect.com/science/article/abs/pii/S0031320323004892) (Pattern Recognition, 2024); [Age Invariant Face Recognition Survey](https://dl.acm.org/doi/abs/10.1007/s10462-018-9661-z) (AI Review, 2019)

---

## 7. Photo Sleuth: Historical Portrait Identification

### Human-AI Workflow for Historical Photos
Photo Sleuth (Virginia Tech, 2018) identifies unknown Civil War soldiers using a three-stage pipeline:

1. **Build the haystack:** Crowdsource a database of identified portraits with metadata (rank, unit, dates)
2. **Narrow the haystack:** User tags visual clues (uniform color -> Union/Confederate, insignia -> rank). System maps these to search filters against military records.
3. **Find the needle:** Face recognition on the narrowed candidate pool, sorted by similarity.

**Key insight:** Face recognition alone produces too many false positives for historical photos. Contextual filtering (who COULD this person be, given the metadata?) dramatically improves precision by reducing the candidate pool before face matching.

**Relevance to Rhodesli:** We already have this structure. GEDCOM provides the "military records" equivalent -- we know who was alive when, who lived where, who was in which family. Gemini's date/location estimates narrow the candidate pool. Face matching is the final discriminator, not the first filter.

**Proposed pipeline:**
1. Estimate photo date + location (Gemini, already built)
2. Filter GEDCOM: who was alive, plausible age, lived in relevant location?
3. Check co-occurrence: who else is identified in this photo? Who are their relatives?
4. Face match against filtered candidates only
5. Present top candidates to admin with supporting evidence

**Source:** [Photo Sleuth: Identifying Historical Portraits](https://dl.acm.org/doi/10.1145/3365842) (ACM TiiS, 2020); [Virginia Tech News](https://news.vt.edu/articles/2019/03/computer-science-civil-war-photo-sleuth.html); [Smithsonian Coverage](https://www.smithsonianmag.com/smart-news/facial-recognition-software-helping-identify-unknown-figures-civil-war-photographs-180970863/)

---

## 8. Enriching Image Archives via Facial Recognition

### Milleville et al. (ACM JOCCH, 2023)
Applied facial recognition to cultural heritage archives (150K+ images, 6K+ known persons):

- **Precision 0.936** at similarity threshold 0.5 on face embeddings
- **62,000+ persons identified** from archive images
- **Interactive labeling tool** for efficient validation of predictions
- **Key finding:** Post-identification, additional contextual clues (inscriptions, captions, co-appearing known individuals) were critical for human validators

**Relevance to Rhodesli:** Our archive is smaller (971 photos, ~3000 faces) but has richer metadata (GEDCOM, community knowledge). Their 0.936 precision at 0.5 threshold aligns with our calibrated similarity scoring (AD-149/152, AUC=0.9577). Their interactive labeling tool maps to our Speed-Run and Focus Mode UX.

**Source:** [Enriching Image Archives via Facial Recognition](https://dl.acm.org/doi/10.1145/3606704) (ACM JOCCH, 2023); [Ghent University Publication](https://biblio.ugent.be/publication/01HQ0FY86C6EHE0PTKE1S2C049)

---

## 9. Graph-Based Kinship Recognition

### Family Structure as Graph
Van der Maaten (2014) and subsequent work model families as graphs:
- **Vertices:** Detected faces
- **Edges:** Kinship relationships (parent-child, sibling, spouse)
- **Kinship rules** constrain valid graph configurations
- **Joint inference:** Recognizing one relationship provides evidence for others

**Multi-person kinship (Liang et al., 2020):** Deep Kinship Matching and Recognition (DKMR) generates a nuclear family tree end-to-end from a single family photo.

**Facial Kinship Verification challenges:**
- Same-gender pairs show stronger resemblance than cross-gender
- Age variance is the #1 confound
- Human accuracy: 57.5%-86.6% depending on relationship type
- Small inter-class separation: kin similarity overlaps with non-kin

**Relevance to Rhodesli:** We have the graph (GEDCOM). The research suggests we should use family structure as a Bayesian prior, not just for kinship verification but for identity resolution. If we identify one sibling, the probability of other faces in the same photo being other siblings increases proportionally to face similarity.

**Source:** [Graph-based Kinship Recognition](https://lvdmaaten.github.io/publications/papers/ICPR_2014c.pdf) (ICPR 2014); [Facial Kinship Verification Survey](https://pmc.ncbi.nlm.nih.gov/articles/PMC9016696/) (IJCV 2022); [Families in the Wild Dataset](https://medium.com/voxel51/visual-kinship-recognition-with-the-families-in-the-wild-computer-vision-dataset-b37d8ddbcf14)

---

## 10. Genealogy-Specific Tools and Workflows

### Practitioner Approaches
The genealogy community has developed practical workflows that combine:

1. **Photo dating by fashion/format:** Clothing styles, hairstyles, print format (daguerreotype vs carte de visite vs snapshot) narrow the date range
2. **Process of elimination via family tree:** Cross-reference estimated date + location with GEDCOM to identify who COULD be in the photo
3. **Known-to-unknown chaining:** Start from confidently identified individuals, then identify co-occurring unknowns through relationship reasoning
4. **Compare-a-Face (FamilySearch):** Simple face comparison tool for genealogists
5. **Related Faces:** AI service for matching unknown faces against a personal collection

**Key genealogist insight (from multiple sources):** "By combining historical documents with the clues in the photos -- clothing (to place the style in an era), dates, studio stamps (to identify the location), and your family tree (to see who was alive at the time) -- it's possible to eventually figure out who is in photos."

**Relevance to Rhodesli:** This is exactly what our Estimate tool + GEDCOM linking already does, but manually. PRD-059 should automate this reasoning chain.

**Source:** [Legacy Tree: Date Old Family Photos](https://www.legacytree.com/blog/date-old-family-photos); [Family Locket: Match Individuals Using Related Faces](https://familylocket.com/how-to-match-individuals-in-old-photos-using-related-faces/); [MyHeritage: Analyze Old Family Photos](https://www.myheritage.com/wiki/How_to_analyze_old_family_photos_for_finding_context); [Hawk Hill: Google Photos for Old Family Photos](https://www.hawk-hill.com/old-photos-facial-recognition/)

---

## Synthesis: Recommended Approach for PRD-059

### Techniques to Adopt

1. **Two-pass clustering (Apple pattern)**
   - Pass 1: Within same estimated era, use face similarity + co-occurrence + GEDCOM prior
   - Pass 2: Cross-era matching with face embeddings only, age-adjusted thresholds

2. **Automatic constraint generation**
   - Cannot-link: All face pairs within the same photo (free, 100% reliable)
   - Must-link: Admin-confirmed anchor_ids (existing)
   - Soft must-link: GEDCOM-predicted co-occurrence (spouse pairs, parent-child pairs likely in same photos)

3. **GEDCOM-filtered candidate scoring (Photo Sleuth pattern)**
   - For each unidentified face: estimate photo date -> filter GEDCOM by alive + plausible age -> score filtered candidates by face similarity
   - Dramatically reduces false positive rate by shrinking candidate pool

4. **Co-occurrence graph analysis**
   - Build a face co-occurrence graph (who appears with whom across photos)
   - Identify "social clusters" -- groups of faces that frequently co-occur
   - Map social clusters to GEDCOM family units
   - Use cluster membership as evidence for identity

5. **Age-aware distance thresholds**
   - Calibrate from confirmed cross-age matches (we have some: Fox family across decades)
   - Apply looser thresholds for larger estimated age gaps
   - Formula: `adjusted_threshold = base_threshold + alpha * abs(age_gap)`

6. **Probabilistic scoring function**
   ```
   S(identity, face) = w1 * embedding_sim
                      + w2 * cooccurrence_score
                      + w3 * temporal_plausibility
                      + w4 * gedcom_prior
                      + w5 * kinship_boost
   ```
   Where:
   - `embedding_sim`: Calibrated face distance (existing, AD-149/152)
   - `cooccurrence_score`: How often this face appears with known associates of the candidate identity
   - `temporal_plausibility`: P(person alive and plausible age at estimated photo date)
   - `gedcom_prior`: P(person in this photo given GEDCOM relationships to other identified people in the photo)
   - `kinship_boost`: Face similarity to confirmed relatives (parents, siblings)

### Techniques to Defer

- **Age progression/regression GANs:** Computationally expensive, requires training data we don't have, marginal benefit given our age-aware threshold approach
- **Kinship verification models:** Our GEDCOM already provides kinship ground truth; we don't need to infer kinship from faces
- **Full re-training of face embeddings:** InsightFace embeddings are good enough; the gains come from context, not better embeddings

### Specific Algorithms

| Technique | Algorithm | Complexity | Priority |
|-----------|-----------|-----------|----------|
| Co-occurrence constraints | Cannot-link from same-photo faces | O(photos * faces^2) | P0 -- free data |
| GEDCOM candidate filtering | Date range + alive filter on GEDCOM | O(identities * photos) | P0 -- highest ROI |
| Co-occurrence graph | Build adjacency matrix, community detection | O(faces^2) | P1 -- moderate effort |
| Age-adjusted thresholds | Linear scaling from confirmed pairs | O(confirmed_pairs) | P1 -- calibration needed |
| Probabilistic scoring | Weighted sum with learned weights | O(candidates * features) | P2 -- needs evaluation framework |
| Two-pass clustering | HAC with constraints | O(n^2 log n) | P2 -- architectural change |

---

## References

### Academic Papers
- Loui & Savakis. [Temporal Event Clustering for Digital Photo Collections](https://dl.acm.org/doi/10.1145/1083314.1083317). ACM TOMM, 2003.
- Dai et al. [Family Member Identification from Photo Collections](http://dhoiem.cs.illinois.edu/publications/dai_disney_wacv2015.pdf). WACV 2015.
- Zhu et al. [Face Clustering: Representation and Pairwise Constraints](https://arxiv.org/abs/1706.05067). IEEE TIFS, 2017.
- Wu et al. [Constrained Clustering and Its Application to Face Clustering in Videos](https://openaccess.thecvf.com/content_cvpr_2013/papers/Wu_Constrained_Clustering_and_2013_CVPR_paper.pdf). CVPR 2013.
- Mohanty et al. [Photo Sleuth: Identifying Historical Portraits](https://dl.acm.org/doi/10.1145/3365842). ACM TiiS, 2020.
- Milleville et al. [Enriching Image Archives via Facial Recognition](https://dl.acm.org/doi/10.1145/3606704). ACM JOCCH, 2023.
- Robinson et al. [Automatic Face Understanding: Recognizing Families in Photos](https://arxiv.org/abs/2102.08941). arXiv, 2021.
- Van der Maaten. [Graph-based Kinship Recognition](https://lvdmaaten.github.io/publications/papers/ICPR_2014c.pdf). ICPR 2014.
- Wang et al. [Facial Kinship Verification: A Comprehensive Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC9016696/). IJCV, 2022.
- [Cross-Age Facial Recognition with AT-GAN](https://pmc.ncbi.nlm.nih.gov/articles/PMC12063864/). PLOS ONE, 2025.

### Industry
- Apple. [Recognizing People in Photos Through Private On-Device Machine Learning](https://machinelearning.apple.com/research/recognizing-people-photos). 2021.
- Google. [Patent US8189880B2: Interactive Photo Annotation Based on Face Clustering](https://patents.google.com/patent/US8189880B2/en).
- Google. [Set up & Manage Face Groups](https://support.google.com/photos/answer/6128838).

### Genealogy Practice
- [Legacy Tree: How to Date Old Family Photos](https://www.legacytree.com/blog/date-old-family-photos)
- [Family Locket: Match Individuals Using Related Faces](https://familylocket.com/how-to-match-individuals-in-old-photos-using-related-faces/)
- [MyHeritage: How to Analyze Old Family Photos](https://www.myheritage.com/wiki/How_to_analyze_old_family_photos_for_finding_context)
- [Hawk Hill: Using Google Photos for Old Family Photos](https://www.hawk-hill.com/old-photos-facial-recognition/)
- [FamilySearch Compare-a-Face](https://familytreemagazine.com/websites/familysearch/familysearch-compare-a-face/)
- [Programming Historian: Facial Recognition in Historical Photographs](https://programminghistorian.org/en/lessons/facial-recognition-ai-python)
