"""Siamese MLP for similarity calibration on frozen embeddings.

Takes a pair of 512-dim face embeddings and outputs P(same_person).
Architecture: concat(a, b, |a-b|, a*b) -> FC layers -> sigmoid.

Decision provenance: AD-123 (Siamese MLP over metric learning).
"""

import torch
import torch.nn as nn


class CalibrationModel(nn.Module):
    """Siamese MLP that predicts P(same_person) from embedding pairs.

    Input: Two 512-dim face embeddings.
    Output: Scalar probability in [0, 1].
    """

    def __init__(self, embed_dim: int = 512, hidden_dim: int = 256, dropout: float = 0.3):
        super().__init__()
        input_dim = embed_dim * 4  # concat(a, b, |a-b|, a*b)
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Dropout(dropout * 0.67),  # Lighter dropout in later layers
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, emb_a: torch.Tensor, emb_b: torch.Tensor) -> torch.Tensor:
        """Predict P(same_person) for embedding pairs.

        Args:
            emb_a: (batch, 512) tensor
            emb_b: (batch, 512) tensor

        Returns:
            (batch, 1) tensor of probabilities
        """
        diff = torch.abs(emb_a - emb_b)
        prod = emb_a * emb_b
        x = torch.cat([emb_a, emb_b, diff, prod], dim=-1)
        return self.net(x)

    def predict(self, emb_a: torch.Tensor, emb_b: torch.Tensor) -> float:
        """Single-pair prediction (no grad, returns Python float)."""
        self.eval()
        with torch.no_grad():
            if emb_a.dim() == 1:
                emb_a = emb_a.unsqueeze(0)
            if emb_b.dim() == 1:
                emb_b = emb_b.unsqueeze(0)
            prob = self.forward(emb_a, emb_b)
            return prob.item()
