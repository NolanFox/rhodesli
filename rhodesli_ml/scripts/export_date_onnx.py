"""Export trained DateEstimationModel to ONNX format for production serving.

The web app uses onnxruntime (15MB) instead of PyTorch (500MB+) for inference.
This script exports the trained Lightning checkpoint to .onnx format and validates
that outputs match within numerical tolerance.

Usage:
    python -m rhodesli_ml.scripts.export_date_onnx
    python -m rhodesli_ml.scripts.export_date_onnx --checkpoint rhodesli_ml/checkpoints/date-epoch=26-val/mae_decades=0.36.ckpt

Decision provenance: AD-129 (ONNX for date estimation production serving).
"""

import argparse
from pathlib import Path

import numpy as np


def _find_best_checkpoint() -> Path | None:
    """Find the best checkpoint by parsing MAE from filenames."""
    ckpt_dir = Path(__file__).resolve().parent.parent / "checkpoints"
    if not ckpt_dir.exists():
        return None

    best_mae = float("inf")
    best_path = None
    for epoch_dir in ckpt_dir.iterdir():
        if not epoch_dir.is_dir() or not epoch_dir.name.startswith("date-epoch="):
            continue
        for ckpt_file in epoch_dir.glob("*.ckpt"):
            # Parse MAE from filename like "mae_decades=0.36.ckpt"
            name = ckpt_file.stem
            if "mae_decades=" in name:
                try:
                    mae = float(name.split("mae_decades=")[1])
                    if mae < best_mae:
                        best_mae = mae
                        best_path = ckpt_file
                except (ValueError, IndexError):
                    continue

    return best_path


def export_to_onnx(
    checkpoint_path: Path,
    output_path: Path,
    opset_version: int = 17,
) -> Path:
    """Export a trained DateEstimationModel checkpoint to ONNX.

    Args:
        checkpoint_path: Path to .ckpt Lightning checkpoint
        output_path: Path for .onnx output
        opset_version: ONNX opset version

    Returns:
        Path to the exported .onnx file

    Raises:
        FileNotFoundError: If checkpoint_path doesn't exist
        RuntimeError: If export or validation fails
    """
    import torch

    from rhodesli_ml.models.date_classifier import DateEstimationModel

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    # Load PyTorch Lightning checkpoint
    model = DateEstimationModel.load_from_checkpoint(
        str(checkpoint_path), map_location="cpu"
    )
    model.eval()

    # Create dummy input: (batch=1, channels=3, height=224, width=224)
    dummy_input = torch.randn(1, 3, 224, 224)

    # Export
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        input_names=["image"],
        output_names=["ordinal_logits"],
        dynamic_axes={
            "image": {0: "batch"},
            "ordinal_logits": {0: "batch"},
        },
        opset_version=opset_version,
    )

    return output_path


def validate_onnx(
    checkpoint_path: Path,
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

    from rhodesli_ml.models.date_classifier import DateEstimationModel

    # Load PyTorch model
    model = DateEstimationModel.load_from_checkpoint(
        str(checkpoint_path), map_location="cpu"
    )
    model.eval()

    # Load ONNX model
    session = ort.InferenceSession(str(onnx_path))

    max_diff = 0.0

    for _ in range(n_samples):
        # Random input image tensor
        img = np.random.randn(1, 3, 224, 224).astype(np.float32)

        # PyTorch inference
        with torch.no_grad():
            pt_result = model(torch.tensor(img)).numpy()

        # ONNX inference
        ort_result = session.run(None, {"image": img})

        diff = np.max(np.abs(pt_result - ort_result[0]))
        max_diff = max(max_diff, diff)

    if max_diff > tolerance:
        raise RuntimeError(
            f"ONNX output mismatch: max diff {max_diff} > tolerance {tolerance}"
        )

    return max_diff


def main():
    parser = argparse.ArgumentParser(
        description="Export date estimation model to ONNX"
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Path to .ckpt checkpoint (auto-finds best if not specified)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("rhodesli_ml/artifacts/date_estimation_v1.onnx"),
    )
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--tolerance", type=float, default=0.05)
    parser.add_argument("--validate-samples", type=int, default=100)
    args = parser.parse_args()

    # Find checkpoint
    ckpt = args.checkpoint
    if ckpt is None:
        ckpt = _find_best_checkpoint()
        if ckpt is None:
            print("ERROR: No checkpoint found. Specify --checkpoint path.")
            return
        print(f"Auto-selected best checkpoint: {ckpt}")
    else:
        print(f"Using checkpoint: {ckpt}")

    print(f"Exporting → {args.output}")
    export_to_onnx(ckpt, args.output, opset_version=args.opset)
    size_kb = args.output.stat().st_size / 1024
    print(f"Exported: {args.output} ({size_kb:.1f} KB)")

    print(f"Validating against PyTorch ({args.validate_samples} samples)...")
    max_diff = validate_onnx(
        ckpt, args.output,
        tolerance=args.tolerance,
        n_samples=args.validate_samples,
    )
    print(f"Max difference: {max_diff:.2e} (tolerance: {args.tolerance:.0e})")
    print("ONNX export validated — outputs match PyTorch")


if __name__ == "__main__":
    main()
