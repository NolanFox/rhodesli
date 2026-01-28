"""
Temporal Priors for Era-Constrained Face Matching.

Implements CLIP-based era classification and Bayesian temporal penalties
for historical photograph matching. See docs/adr_002_temporal_priors.md.

Key concepts:
- Era bins: 1890-1910, 1910-1930, 1930-1950
- Temporal penalty: Log-space additive penalty to MLS
- Uncertainty-aware: Low confidence eras → smoothed penalties
"""

from dataclasses import dataclass

import numpy as np

from core.pfe import mutual_likelihood_score


# Era definitions
ERAS = ["1890-1910", "1910-1930", "1930-1950"]

# Penalty matrix (log-space): penalty[era1][era2]
# Same era: 0.0, Adjacent: -2.0, Non-adjacent: -10.0
PENALTY_MATRIX = {
    "1890-1910": {"1890-1910": 0.0, "1910-1930": -2.0, "1930-1950": -10.0},
    "1910-1930": {"1890-1910": -2.0, "1910-1930": 0.0, "1930-1950": -2.0},
    "1930-1950": {"1890-1910": -10.0, "1910-1930": -2.0, "1930-1950": 0.0},
}

# Text prompts for CLIP era classification
ERA_PROMPTS = {
    "1890-1910": [
        "a Victorian era photograph from the 1890s",
        "an Edwardian era photograph from the 1900s",
        "a sepia toned formal portrait from the late 1800s",
        "a carte de visite photograph",
    ],
    "1910-1930": [
        "a photograph from the 1910s or 1920s",
        "a World War I era photograph",
        "a 1920s flapper era photograph",
        "a black and white photograph from the interwar period",
    ],
    "1930-1950": [
        "a photograph from the 1930s or 1940s",
        "a World War II era photograph",
        "a 1940s photograph",
        "a Great Depression era photograph",
    ],
}


@dataclass
class EraEstimate:
    """
    Era classification result with uncertainty.

    Attributes:
        era: Most likely era ("1890-1910", "1910-1930", or "1930-1950")
        probabilities: P(era) for each bin, sums to 1.0
        confidence: max(probabilities) - second highest (higher = more certain)
    """
    era: str
    probabilities: dict[str, float]
    confidence: float


def compute_temporal_penalty(era1: EraEstimate, era2: EraEstimate) -> float:
    """
    Compute Bayesian temporal penalty for cross-era matching.

    Uses marginalization over era probabilities to handle uncertainty:
    penalty = Σ_e1 Σ_e2 P(e1) * P(e2) * PENALTY_MATRIX[e1][e2]

    Args:
        era1: Era estimate for first face
        era2: Era estimate for second face

    Returns:
        Temporal penalty (log-space, negative or zero)
    """
    penalty = 0.0
    for e1, p1 in era1.probabilities.items():
        for e2, p2 in era2.probabilities.items():
            penalty += p1 * p2 * PENALTY_MATRIX[e1][e2]
    return penalty


def mls_with_temporal(
    mu1: np.ndarray,
    sigma_sq1: np.ndarray,
    era1: EraEstimate,
    mu2: np.ndarray,
    sigma_sq2: np.ndarray,
    era2: EraEstimate,
) -> float:
    """
    Compute MLS with temporal prior penalty.

    MLS_temporal = MLS(f1, f2) + log(P(same_person | era1, era2))

    Args:
        mu1, mu2: Mean embeddings, shape (512,)
        sigma_sq1, sigma_sq2: Variance vectors, shape (512,)
        era1, era2: Era estimates for each face

    Returns:
        Temporal-aware MLS score (higher = more likely match)
    """
    base_mls = mutual_likelihood_score(mu1, sigma_sq1, mu2, sigma_sq2)
    temporal_penalty = compute_temporal_penalty(era1, era2)
    return base_mls + temporal_penalty


# CLIP model cache (lazy loaded)
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None


def _load_clip_model():
    """Lazy load CLIP model. Deferred to avoid import at module level."""
    global _clip_model, _clip_preprocess, _clip_tokenizer

    if _clip_model is not None:
        return _clip_model, _clip_preprocess, _clip_tokenizer

    import torch
    import open_clip

    # Use ViT-B/32 for balance of speed and accuracy
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="laion2b_s34b_b79k"
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")

    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()

    _clip_model = model
    _clip_preprocess = preprocess
    _clip_tokenizer = tokenizer

    return model, preprocess, tokenizer


def _prepare_image(image: np.ndarray) -> "torch.Tensor":
    """Convert numpy image to CLIP input tensor."""
    import torch
    from PIL import Image

    _, preprocess, _ = _load_clip_model()

    # Handle grayscale
    if len(image.shape) == 2:
        image = np.stack([image, image, image], axis=-1)

    # Convert to PIL Image
    pil_image = Image.fromarray(image)

    # Apply CLIP preprocessing
    tensor = preprocess(pil_image).unsqueeze(0)

    if torch.cuda.is_available():
        tensor = tensor.cuda()

    return tensor


def classify_era(image: np.ndarray) -> EraEstimate:
    """
    Classify image into era using CLIP zero-shot classification.

    Uses text prompts describing each era and computes similarity scores.

    Args:
        image: Image array (H, W, 3) RGB or (H, W) grayscale

    Returns:
        EraEstimate with era, probabilities, and confidence
    """
    import torch

    model, _, tokenizer = _load_clip_model()

    # Prepare image
    image_tensor = _prepare_image(image)

    # Prepare text prompts for all eras
    all_prompts = []
    era_indices = []  # Maps prompt index to era
    for era, prompts in ERA_PROMPTS.items():
        for prompt in prompts:
            all_prompts.append(prompt)
            era_indices.append(era)

    text_tokens = tokenizer(all_prompts)
    if torch.cuda.is_available():
        text_tokens = text_tokens.cuda()

    # Compute similarities
    with torch.no_grad():
        image_features = model.encode_image(image_tensor)
        text_features = model.encode_text(text_tokens)

        # Normalize
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        # Cosine similarity
        similarities = (image_features @ text_features.T).squeeze(0)

    # Aggregate similarities by era (take max per era)
    era_scores = {}
    for i, era in enumerate(era_indices):
        score = similarities[i].item()
        if era not in era_scores:
            era_scores[era] = []
        era_scores[era].append(score)

    # Take mean of top-2 prompts per era for robustness
    era_means = {}
    for era, scores in era_scores.items():
        sorted_scores = sorted(scores, reverse=True)
        era_means[era] = np.mean(sorted_scores[:2])

    # Convert to probabilities via softmax
    scores_array = np.array([era_means[era] for era in ERAS])
    # Temperature scaling for sharper distributions
    temperature = 0.1
    exp_scores = np.exp((scores_array - scores_array.max()) / temperature)
    probabilities = exp_scores / exp_scores.sum()

    # Build probability dict
    prob_dict = {era: float(prob) for era, prob in zip(ERAS, probabilities)}

    # Determine most likely era
    best_era = max(prob_dict, key=prob_dict.get)

    # Compute confidence as gap between top-1 and top-2
    sorted_probs = sorted(probabilities, reverse=True)
    confidence = float(sorted_probs[0] - sorted_probs[1])

    return EraEstimate(era=best_era, probabilities=prob_dict, confidence=confidence)
