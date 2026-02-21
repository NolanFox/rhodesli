"""Export trained CalibrationModel to ONNX format for production serving.

The web app uses onnxruntime (15MB) instead of PyTorch (500MB+) for inference.
This script exports the trained .pt checkpoint to .onnx format and validates
that outputs match within numerical tolerance.

Usage:
    python -m rhodesli_ml.calibration.export_onnx
    python -m rhodesli_ml.calibration.export_onnx --model artifacts/calibration_v1.pt --output artifacts/calibration_v1.onnx

Decision provenance: AD-128 (ONNX for production serving).
"""

import argparse
from pathlib import Path

import numpy as np


def export_to_onnx(
    model_path: Path,
    output_path: Path,
    opset_version: int = 17,
) -> Path:
    """Export a trained CalibrationModel checkpoint to ONNX.

    Args:
        model_path: Path to .pt checkpoint
        output_path: Path for .onnx output
        opset_version: ONNX opset version

    Returns:
        Path to the exported .onnx file

    Raises:
        FileNotFoundError: If model_path doesn't exist
        RuntimeError: If export or validation fails
    """
    import torch

    from rhodesli_ml.calibration.model import CalibrationModel

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    # Load PyTorch model
    checkpoint = torch.load(model_path, weights_only=False, map_location="cpu")
    config = checkpoint.get("config", {})
    model = CalibrationModel(
        embed_dim=config.get("embed_dim", 512),
        hidden_dim=config.get("hidden_dim", 32),
        dropout=config.get("dropout", 0.5),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Create dummy inputs
    embed_dim = config.get("embed_dim", 512)
    emb_a = torch.randn(1, embed_dim)
    emb_b = torch.randn(1, embed_dim)

    # Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        (emb_a, emb_b),
        str(output_path),
        input_names=["embedding_a", "embedding_b"],
        output_names=["similarity_score"],
        dynamic_axes={
            "embedding_a": {0: "batch"},
            "embedding_b": {0: "batch"},
            "similarity_score": {0: "batch"},
        },
        opset_version=opset_version,
    )

    return output_path


def validate_onnx(
    model_path: Path,
    onnx_path: Path,
    tolerance: float = 1e-5,
    n_samples: int = 100,
) -> float:
    """Validate ONNX model outputs match PyTorch within tolerance.

    Returns the maximum absolute difference across all samples.
    Raises RuntimeError if difference exceeds tolerance.
    """
    import torch
    import onnxruntime as ort

    from rhodesli_ml.calibration.model import CalibrationModel

    # Load PyTorch model
    checkpoint = torch.load(model_path, weights_only=False, map_location="cpu")
    config = checkpoint.get("config", {})
    model = CalibrationModel(
        embed_dim=config.get("embed_dim", 512),
        hidden_dim=config.get("hidden_dim", 32),
        dropout=config.get("dropout", 0.5),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Load ONNX model
    session = ort.InferenceSession(str(onnx_path))

    embed_dim = config.get("embed_dim", 512)
    max_diff = 0.0

    for _ in range(n_samples):
        emb_a = np.random.randn(1, embed_dim).astype(np.float32)
        emb_b = np.random.randn(1, embed_dim).astype(np.float32)

        # PyTorch inference
        with torch.no_grad():
            pt_result = model(
                torch.tensor(emb_a), torch.tensor(emb_b)
            ).numpy()

        # ONNX inference
        ort_result = session.run(
            None,
            {"embedding_a": emb_a, "embedding_b": emb_b},
        )

        diff = np.max(np.abs(pt_result - ort_result[0]))
        max_diff = max(max_diff, diff)

    if max_diff > tolerance:
        raise RuntimeError(
            f"ONNX output mismatch: max diff {max_diff} > tolerance {tolerance}"
        )

    return max_diff


def main():
    parser = argparse.ArgumentParser(description="Export calibration model to ONNX")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("rhodesli_ml/artifacts/calibration_v1.pt"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("rhodesli_ml/artifacts/calibration_v1.onnx"),
    )
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--tolerance", type=float, default=1e-5)
    parser.add_argument("--validate-samples", type=int, default=100)
    args = parser.parse_args()

    print(f"Exporting {args.model} → {args.output}")
    export_to_onnx(args.model, args.output, opset_version=args.opset)
    size_kb = args.output.stat().st_size / 1024
    print(f"Exported: {args.output} ({size_kb:.1f} KB)")

    print(f"Validating against PyTorch ({args.validate_samples} samples)...")
    max_diff = validate_onnx(
        args.model, args.output,
        tolerance=args.tolerance,
        n_samples=args.validate_samples,
    )
    print(f"Max difference: {max_diff:.2e} (tolerance: {args.tolerance:.0e})")
    print("ONNX export validated — outputs match")


if __name__ == "__main__":
    main()
