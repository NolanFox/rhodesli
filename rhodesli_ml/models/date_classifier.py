"""Date/era estimation model using ordinal regression (CORAL loss).

Predicts the decade of a photo (1900s through 2000s) using transfer learning
from a pretrained EfficientNet-B0 backbone. Uses CORAL (Consistent Rank Logits)
ordinal regression because predicting 1940s when the answer is 1950s is less
wrong than predicting 2000s.

Architecture:
    - EfficientNet-B0 backbone (pretrained on ImageNet)
    - Freeze early layers, fine-tune last block + new head
    - Ordinal regression head with CORAL loss
    - Optional KL divergence auxiliary loss for soft label training

References:
    - Cao, Mirjalili, Raschka (2020): "Rank Consistent Ordinal Regression"
    - Hinton et al. (2015): Knowledge Distillation (soft label training)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import lightning as L
from torchvision import models

from rhodesli_ml.data.date_dataset import NUM_DECADES, index_to_decade


class CoralLoss(nn.Module):
    """CORAL (Consistent Rank Logits) loss for ordinal regression.

    Each output node k predicts P(class > k). The loss is the sum of
    binary cross-entropy losses across all ordinal thresholds.
    """

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Compute CORAL loss.

        Args:
            logits: Shape (batch, num_classes - 1). Raw logits for each ordinal threshold.
            targets: Shape (batch, num_classes - 1). Binary targets [1,1,...,1,0,...,0].

        Returns:
            Scalar loss value.
        """
        return F.binary_cross_entropy_with_logits(logits, targets, reduction="mean")


def ordinal_logits_to_probs(logits: torch.Tensor) -> torch.Tensor:
    """Convert CORAL ordinal logits to class probabilities.

    P(class = k) = P(class > k-1) - P(class > k)
    With P(class > -1) = 1 and P(class > K) = 0.

    Args:
        logits: Shape (batch, num_classes - 1).

    Returns:
        Shape (batch, num_classes) with class probabilities summing to 1.
    """
    cumprobs = torch.sigmoid(logits)  # P(class > k) for k = 0..K-2
    # Prepend P(class > -1) = 1, append P(class > K-1) = 0
    ones = torch.ones(cumprobs.shape[0], 1, device=cumprobs.device)
    zeros = torch.zeros(cumprobs.shape[0], 1, device=cumprobs.device)
    extended = torch.cat([ones, cumprobs, zeros], dim=1)
    # P(class = k) = P(class > k-1) - P(class > k)
    probs = extended[:, :-1] - extended[:, 1:]
    # Clamp to avoid negative probabilities from numerical issues
    probs = torch.clamp(probs, min=0.0)
    # Renormalize
    probs = probs / (probs.sum(dim=1, keepdim=True) + 1e-8)
    return probs


def probs_to_predicted_class(probs: torch.Tensor) -> torch.Tensor:
    """Get predicted class index from probability distribution."""
    return probs.argmax(dim=1)


class DateEstimationModel(L.LightningModule):
    """PyTorch Lightning module for date estimation via CORAL ordinal regression.

    Training step uses CORAL loss as primary loss, with optional KL divergence
    auxiliary loss when soft labels (Gemini decade_probabilities) are available.
    """

    def __init__(
        self,
        num_classes: int = NUM_DECADES,
        backbone: str = "efficientnet_b0",
        pretrained: bool = True,
        freeze_layers: int = 6,
        learning_rate: float = 0.001,
        weight_decay: float = 0.01,
        soft_label_weight: float = 0.3,
    ):
        super().__init__()
        self.save_hyperparameters()

        self.num_classes = num_classes
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.soft_label_weight = soft_label_weight

        # Build backbone
        self.backbone = self._build_backbone(backbone, pretrained, freeze_layers)

        # Get feature dimension from backbone
        feature_dim = self._get_feature_dim(backbone)

        # Ordinal regression head: num_classes - 1 threshold logits
        self.ordinal_head = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(feature_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, num_classes - 1),
        )

        # Losses
        self.coral_loss = CoralLoss()

    def _build_backbone(self, backbone: str, pretrained: bool, freeze_layers: int) -> nn.Module:
        """Build and configure the backbone network."""
        if backbone == "efficientnet_b0":
            weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
            model = models.efficientnet_b0(weights=weights)
            # Remove the classifier head
            model.classifier = nn.Identity()
            # Freeze early layers
            if freeze_layers > 0:
                for i, (name, param) in enumerate(model.features.named_parameters()):
                    if i < freeze_layers * 10:  # Rough approximation of layer groups
                        param.requires_grad = False
        elif backbone == "resnet18":
            weights = models.ResNet18_Weights.DEFAULT if pretrained else None
            model = models.resnet18(weights=weights)
            model.fc = nn.Identity()
            if freeze_layers > 0:
                layers_to_freeze = [model.conv1, model.bn1, model.layer1, model.layer2]
                for layer in layers_to_freeze[:freeze_layers]:
                    for param in layer.parameters():
                        param.requires_grad = False
        else:
            raise ValueError(f"Unknown backbone: {backbone}")

        return model

    def _get_feature_dim(self, backbone: str) -> int:
        """Get the feature dimension of the backbone output."""
        if backbone == "efficientnet_b0":
            return 1280
        elif backbone == "resnet18":
            return 512
        else:
            raise ValueError(f"Unknown backbone: {backbone}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass. Returns ordinal logits of shape (batch, num_classes - 1)."""
        features = self.backbone(x)
        logits = self.ordinal_head(features)
        return logits

    def predict_probs(self, x: torch.Tensor) -> torch.Tensor:
        """Get class probabilities from input images."""
        logits = self.forward(x)
        return ordinal_logits_to_probs(logits)

    def predict_decade(self, x: torch.Tensor) -> list[int]:
        """Get predicted decades from input images."""
        probs = self.predict_probs(x)
        indices = probs_to_predicted_class(probs)
        return [index_to_decade(idx.item()) for idx in indices]

    def training_step(self, batch: dict, batch_idx: int) -> torch.Tensor:
        images = batch["image"]
        ordinal_targets = batch["ordinal_target"]
        soft_labels = batch["soft_labels"]
        has_soft = batch["has_soft_labels"]

        # Forward pass
        logits = self.forward(images)

        # Primary CORAL loss
        coral_loss = self.coral_loss(logits, ordinal_targets)

        # Optional KL divergence loss for soft labels
        total_loss = coral_loss
        if has_soft.any() and self.soft_label_weight > 0:
            probs = ordinal_logits_to_probs(logits)
            soft_mask = has_soft.bool()
            if soft_mask.sum() > 0:
                pred_log_probs = torch.log(probs[soft_mask] + 1e-8)
                target_probs = soft_labels[soft_mask]
                kl_loss = F.kl_div(pred_log_probs, target_probs, reduction="batchmean")
                total_loss = coral_loss + self.soft_label_weight * kl_loss
                self.log("train/kl_loss", kl_loss, prog_bar=False)

        # Metrics
        probs = ordinal_logits_to_probs(logits)
        predicted = probs_to_predicted_class(probs)
        true_classes = batch["class_index"]

        accuracy = (predicted == true_classes).float().mean()
        mae = (predicted - true_classes).float().abs().mean()
        adjacent = ((predicted - true_classes).abs() <= 1).float().mean()

        self.log("train/loss", total_loss, prog_bar=True)
        self.log("train/coral_loss", coral_loss, prog_bar=False)
        self.log("train/accuracy", accuracy, prog_bar=True)
        self.log("train/mae_decades", mae, prog_bar=True)
        self.log("train/adjacent_accuracy", adjacent, prog_bar=False)

        return total_loss

    def validation_step(self, batch: dict, batch_idx: int) -> dict:
        images = batch["image"]
        ordinal_targets = batch["ordinal_target"]
        true_classes = batch["class_index"]

        logits = self.forward(images)
        coral_loss = self.coral_loss(logits, ordinal_targets)

        probs = ordinal_logits_to_probs(logits)
        predicted = probs_to_predicted_class(probs)

        accuracy = (predicted == true_classes).float().mean()
        mae = (predicted - true_classes).float().abs().mean()
        adjacent = ((predicted - true_classes).abs() <= 1).float().mean()

        self.log("val/loss", coral_loss, prog_bar=True, sync_dist=True)
        self.log("val/accuracy", accuracy, prog_bar=True, sync_dist=True)
        self.log("val/mae_decades", mae, prog_bar=True, sync_dist=True)
        self.log("val/adjacent_accuracy", adjacent, prog_bar=False, sync_dist=True)

        return {"val_loss": coral_loss, "predicted": predicted, "true": true_classes}

    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(
            self.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=self.trainer.max_epochs if self.trainer else 100
        )
        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": scheduler,
                "interval": "epoch",
            },
        }
