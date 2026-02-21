"""Tests for CalibrationModel architecture and forward pass."""

import torch
import pytest

from rhodesli_ml.calibration.model import CalibrationModel


class TestCalibrationModel:
    def test_output_shape_batch(self):
        model = CalibrationModel(embed_dim=512)
        emb_a = torch.randn(8, 512)
        emb_b = torch.randn(8, 512)
        out = model(emb_a, emb_b)
        assert out.shape == (8, 1)

    def test_output_shape_single(self):
        model = CalibrationModel(embed_dim=512)
        emb_a = torch.randn(1, 512)
        emb_b = torch.randn(1, 512)
        out = model(emb_a, emb_b)
        assert out.shape == (1, 1)

    def test_output_range(self):
        """Output should be in [0, 1] due to sigmoid."""
        model = CalibrationModel(embed_dim=512)
        emb_a = torch.randn(100, 512)
        emb_b = torch.randn(100, 512)
        out = model(emb_a, emb_b)
        assert (out >= 0).all()
        assert (out <= 1).all()

    def test_identical_embeddings_before_training(self):
        """Identical embeddings should get a score (may not be high before training)."""
        model = CalibrationModel(embed_dim=512)
        emb = torch.randn(1, 512)
        out = model(emb, emb)
        assert 0 <= out.item() <= 1

    def test_predict_returns_float(self):
        model = CalibrationModel(embed_dim=512)
        emb_a = torch.randn(512)
        emb_b = torch.randn(512)
        score = model.predict(emb_a, emb_b)
        assert isinstance(score, float)
        assert 0 <= score <= 1

    def test_predict_batched_input(self):
        model = CalibrationModel(embed_dim=512)
        emb_a = torch.randn(1, 512)
        emb_b = torch.randn(1, 512)
        score = model.predict(emb_a, emb_b)
        assert isinstance(score, float)

    def test_gradients_flow(self):
        """Ensure gradients flow through the model."""
        model = CalibrationModel(embed_dim=512)
        emb_a = torch.randn(4, 512, requires_grad=True)
        emb_b = torch.randn(4, 512, requires_grad=True)
        out = model(emb_a, emb_b)
        loss = out.sum()
        loss.backward()
        assert emb_a.grad is not None
        assert emb_b.grad is not None

    def test_parameter_count(self):
        model = CalibrationModel(embed_dim=512, hidden_dim=256)
        params = sum(p.numel() for p in model.parameters())
        # 2048*256 + 256 + 256*64 + 64 + 64*1 + 1 = ~540K
        assert 500_000 < params < 600_000

    def test_custom_embed_dim(self):
        model = CalibrationModel(embed_dim=128, hidden_dim=64)
        emb_a = torch.randn(4, 128)
        emb_b = torch.randn(4, 128)
        out = model(emb_a, emb_b)
        assert out.shape == (4, 1)

    def test_eval_mode_deterministic(self):
        """In eval mode, dropout is disabled so output is deterministic."""
        model = CalibrationModel(embed_dim=512)
        model.eval()
        emb_a = torch.randn(4, 512)
        emb_b = torch.randn(4, 512)
        out1 = model(emb_a, emb_b)
        out2 = model(emb_a, emb_b)
        assert torch.allclose(out1, out2)
