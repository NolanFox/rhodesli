# PRD-038: Research References & Industry Analysis

**Parent**: [docs/prds/038_longitudinal_face_modeling.md](../038_longitudinal_face_modeling.md)

---

## Academic Research on Age-Invariant Face Recognition

### Key Benchmarks
- **MORPH Album 2**: 55,000 face images of 13,000 subjects with age metadata. Standard benchmark for cross-age verification. Our archive is smaller but spans MORE years (100+ vs typical 20-30).
- **CACD (Cross-Age Celebrity Dataset)**: 160,000+ images of 2,000 celebrities. Good for training but celebrity photos are higher quality than heritage archive photos.
- **FG-NET**: 1,002 images of 82 subjects aged 0-69. Small but has extreme age ranges relevant to our use case (child → elderly).
- **AgeDB**: 16,488 images of 568 subjects. Annotated with exact ages. Useful for evaluating age-gap penalties.

### Relevant Techniques

**1. Age-Invariant Representation Learning**
- **Decorrelated Adversarial Learning (DAL)**: Train encoder to produce age-decorrelated embeddings. An adversary tries to predict age from the embedding; the encoder learns to fool it. Result: embeddings that capture identity but not age.
- **Applicability to Rhodesli**: Could be applied as a LoRA fine-tuning objective. Instead of just contrastive loss, add an adversarial age-prediction head. Requires age labels (we have 271 photo dates + 67 birth years).
- **Difficulty**: HARD — requires adversarial training infrastructure.

**2. Disentangled Representation**
- **Approach**: Separate embedding into identity-component and age-component. Only use identity-component for matching.
- **Methods**: Variational autoencoders (VAE) with age conditioning, or orthogonal projection to remove age subspace.
- **Applicability**: We could estimate the "age subspace" from our confirmed pairs that span multiple decades (e.g., young-Leon vs old-Leon). Project it out before distance computation.
- **Difficulty**: MEDIUM — orthogonal projection is straightforward if we have enough cross-age pairs.

**3. Multi-Prototype Learning**
- **Approach**: Instead of one prototype per identity, maintain multiple (e.g., one per age group). New face matches against closest prototype.
- **This is exactly our multi-anchor approach (AD-001)** — validates our architecture.
- **Enhancement**: Our WS-2 (longitudinal anchor stratification by decade) is the age-aware version of this. Literature confirms this is sound.

**4. Contrastive Learning with Age-Aware Sampling**
- **Approach**: During training, deliberately sample hard positives (same person, large age gap) and hard negatives (different person, similar age).
- **Applicability**: Directly applicable to our LoRA training (WS-4). Use confirmed cross-age pairs as hard positives.
- **Difficulty**: EASY — just a sampling strategy change.

### Key Papers (for implementer reference)
1. "OrthoFace: Orthogonal Age Disentanglement for Cross-Age Face Recognition" — orthogonal projection approach
2. "AIM: Age-Invariant Model for Cross-Age Face Recognition" — prototype + discriminative learning
3. "DAL: Decorrelated Adversarial Learning for Age-Invariant Face Recognition" — adversarial training
4. "When Age-Invariant Face Recognition Meets Face Age Synthesis" — unified framework
5. "Cross-Age Face Recognition: A Survey" — comprehensive overview of approaches

---

## How Google Photos Handles Face Clustering

### Known Architecture (from patents, blog posts, engineering talks)
1. **Hierarchical clustering**: Fast initial clustering using approximate nearest neighbors (ANN), then refinement with exemplar comparison.
2. **Multi-prototype per identity**: Google stores multiple "exemplar" embeddings per person — not centroids. Matches against closest exemplar. **Same as our multi-anchor approach.**
3. **Temporal signals**: Photos taken close in time at the same location are more likely the same person. Used as a soft prior.
4. **User feedback loop**: "Is this the same person?" prompts. Each answer becomes a training signal. **This is our WS-3 (active learning).**
5. **Continuous model updates**: Google periodically retrains their face model on accumulated user feedback. At our scale, this is WS-4 (LoRA) + recalibration.
6. **Face quality scoring**: Low-quality detections (blurry, occluded, extreme angle) are weighted less in matching. **This is our WS-1.**

### What Google Does That We Can't (yet)
- **Billion-scale ANN**: They use ScaNN/FAISS for sub-linear search. We don't need this at <10K faces.
- **Cross-user learning**: They train on data from billions of users. We have one archive.
- **GAN-based age progression**: Synthesize aged/de-aged faces for training data. Interesting but high effort.

### What We Have That Google Doesn't
- **GEDCOM genealogy data**: Family relationships as a matching signal. Google has no genealogy.
- **Date estimates from Gemini**: AI-estimated photo dates for 271 photos. Google has EXIF dates but not for heritage photos.
- **Community knowledge**: Admin is a domain expert who knows the people. Google relies on crowd wisdom.
- **100+ year span**: Most Google Photos users have 10-20 years of photos. We have 100+ years across generations.

---

## LoRA Best Practices for Small Datasets

### Key Findings
1. **Minimum viable dataset**: Literature suggests 200-500 positive pairs for LoRA on a pre-trained face model. We have 221 (MARGINAL) and growing.
2. **Regularization is critical**: At small scale, LoRA can overfit in 5-10 epochs. Use:
   - Low rank (r=4 or r=8, not r=64)
   - High dropout (0.1-0.3)
   - Early stopping on validation AUC
   - Weight decay (1e-4 to 1e-3)
3. **Layer selection**: For ResNet backbones, fine-tune only the last 2-3 blocks. Earlier layers capture low-level features that generalize well.
4. **Data augmentation for heritage photos**:
   - Gaussian noise (simulates film grain)
   - Contrast/brightness jitter (simulates fading)
   - Random crop with slight rotation (simulates scanning artifacts)
   - Sepia/grayscale conversion (most heritage photos are B&W)
   - NOT: aggressive color jitter, large rotations, or cutout (destroy face structure)
5. **Inverse-frequency sampling**: Essential for class balance. Without it, the model overfits to the most-photographed people (Capeluto family).
6. **PFE-aware loss**: Since we use PFE embeddings with uncertainty (sigma_sq), the contrastive loss should weight by inverse uncertainty: pairs where the model is confident should contribute more to the loss.

### Training Recipe (recommended)
```python
# Hyperparameters for Rhodesli LoRA
lora_config = {
    'rank': 8,                    # Low rank for small dataset
    'alpha': 16,                  # alpha/rank = 2 (standard)
    'dropout': 0.15,              # Moderate dropout
    'target_modules': ['conv2', 'conv3'],  # Last 2 ResNet blocks
    'learning_rate': 1e-4,        # Conservative
    'weight_decay': 5e-4,
    'epochs': 20,                 # With early stopping patience=5
    'batch_size': 32,             # Small batches for small dataset
    'pair_sampling': 'inverse_frequency',
    'augmentation': 'heritage_photo_aug',
    'loss': 'pfe_contrastive',    # sigma_sq weighted
    'validation_split': 0.2,      # Stratified by identity
}
```

---

## Active Learning for Face Clustering

### Uncertainty Sampling Strategy
- **Most effective queries**: Pairs near the decision boundary (distance ~0.4-0.6 in our calibrated space)
- **Information gain ranking**: Prefer pairs from under-represented identities (balances the training set)
- **Batch diversity**: Don't show 10 pairs from the same identity — diversify across identities
- **Expected label efficiency**: Each human label worth ~5-10 unlabeled pairs for calibration model improvement

### Implementation Pattern (from literature)
1. Run clustering → identify uncertain pairs
2. Present to human (batch of 10-20)
3. Human labels → insert into `calibration_pairs`
4. Recalibrate → re-cluster → identify new uncertain pairs
5. Repeat until convergence (uncertainty plateau)

---

## Heritage-Specific Challenges

### Unique to Our Domain
1. **Extreme age spans**: Same person photographed as infant (1890) and elderly (1980). Standard face models trained on 0-30 year age gaps.
2. **Photo degradation**: Fading, staining, damage, low resolution. Affects embedding quality.
3. **Formal poses**: Pre-1960s photos typically formal/stiff. Different expression distribution than modern training data.
4. **Family resemblance**: Sephardic Jewish families from Rhodes have strong family resemblance across generations. Father-son pairs may look more similar than the same person at different ages.
5. **Limited ground truth**: Only 69 confirmed identities. Need to grow this via active learning + admin confirmation sprints.

### Mitigation Strategies
- WS-1 (quality weighting) addresses #2
- WS-2 (age-aware) addresses #1
- WS-4 (LoRA) addresses #3 if trained on heritage photos
- WS-3 (active learning) addresses #5
- GEDCOM data helps distinguish family members (#4) — WS-5
