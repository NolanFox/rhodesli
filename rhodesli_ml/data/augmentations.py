"""Heritage-specific image augmentations for date estimation training.

These augmentations simulate common artifacts in scanned heritage photos:
sepia toning, scanning artifacts, fading, film grain, resolution degradation,
geometric distortion (photos-of-photos), and JPEG compression artifacts.

Uses torchvision.transforms for standard augmentations plus custom transforms
for heritage-specific degradation patterns.
"""

import random

import numpy as np
import torch
from PIL import Image, ImageFilter
from torchvision import transforms


class SepiaTransform:
    """Simulate sepia-toned photograph effect."""

    def __call__(self, img: Image.Image) -> Image.Image:
        img_array = np.array(img, dtype=np.float32)
        # Sepia matrix
        sepia_matrix = np.array([
            [0.393, 0.769, 0.189],
            [0.349, 0.686, 0.168],
            [0.272, 0.534, 0.131],
        ])
        sepia = img_array @ sepia_matrix.T
        sepia = np.clip(sepia, 0, 255).astype(np.uint8)
        return Image.fromarray(sepia)


class FilmGrainTransform:
    """Simulate film grain noise."""

    def __init__(self, intensity: float = 0.05):
        self.intensity = intensity

    def __call__(self, img: Image.Image) -> Image.Image:
        img_array = np.array(img, dtype=np.float32)
        noise = np.random.normal(0, self.intensity * 255, img_array.shape)
        noisy = np.clip(img_array + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(noisy)


class ResolutionDegradationTransform:
    """Simulate low-resolution scanning by downscaling then upscaling."""

    def __init__(self, min_scale: float = 0.25, max_scale: float = 0.5):
        self.min_scale = min_scale
        self.max_scale = max_scale

    def __call__(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        scale = random.uniform(self.min_scale, self.max_scale)
        small = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
        return small.resize((w, h), Image.BILINEAR)


class JPEGCompressionTransform:
    """Simulate JPEG compression artifacts."""

    def __init__(self, min_quality: int = 10, max_quality: int = 30):
        self.min_quality = min_quality
        self.max_quality = max_quality

    def __call__(self, img: Image.Image) -> Image.Image:
        import io
        quality = random.randint(self.min_quality, self.max_quality)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        return Image.open(buffer).convert("RGB")


class ScanningArtifactTransform:
    """Simulate subtle horizontal line artifacts from scanning."""

    def __init__(self, num_lines: int = 5, alpha: float = 0.1):
        self.num_lines = num_lines
        self.alpha = alpha

    def __call__(self, img: Image.Image) -> Image.Image:
        img_array = np.array(img, dtype=np.float32)
        h, w = img_array.shape[:2]
        for _ in range(self.num_lines):
            y = random.randint(0, h - 1)
            thickness = random.randint(1, 3)
            brightness_shift = random.uniform(-30, 30)
            y_end = min(y + thickness, h)
            img_array[y:y_end, :, :] += brightness_shift * self.alpha
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        return Image.fromarray(img_array)


class GeometricDistortionTransform:
    """Simulate photos-of-photos taken at slight angles (projective transform)."""

    def __init__(self, max_shift: float = 0.05):
        self.max_shift = max_shift

    def __call__(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        shift = self.max_shift
        # Random projective distortion via perspective transform coefficients
        coeffs = self._find_coeffs(
            [(0, 0), (w, 0), (w, h), (0, h)],
            [
                (random.uniform(-w * shift, w * shift),
                 random.uniform(-h * shift, h * shift)),
                (w + random.uniform(-w * shift, w * shift),
                 random.uniform(-h * shift, h * shift)),
                (w + random.uniform(-w * shift, w * shift),
                 h + random.uniform(-h * shift, h * shift)),
                (random.uniform(-w * shift, w * shift),
                 h + random.uniform(-h * shift, h * shift)),
            ]
        )
        return img.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)

    @staticmethod
    def _find_coeffs(source_coords, target_coords):
        """Find perspective transform coefficients."""
        matrix = []
        for s, t in zip(source_coords, target_coords):
            matrix.append([t[0], t[1], 1, 0, 0, 0, -s[0]*t[0], -s[0]*t[1]])
            matrix.append([0, 0, 0, t[0], t[1], 1, -s[1]*t[0], -s[1]*t[1]])
        A = np.matrix(matrix, dtype=np.float64)
        B = np.array([s for pair in source_coords for s in pair]).reshape(8)
        try:
            res = np.dot(np.linalg.inv(A.T * A) * A.T, B)
            return np.array(res).reshape(8).tolist()
        except np.linalg.LinAlgError:
            return [1, 0, 0, 0, 1, 0, 0, 0]  # Identity transform on failure


class FadingTransform:
    """Simulate photo fading (contrast reduction + slight warm color shift)."""

    def __init__(self, max_fade: float = 0.3):
        self.max_fade = max_fade

    def __call__(self, img: Image.Image) -> Image.Image:
        img_array = np.array(img, dtype=np.float32)
        fade = random.uniform(0.1, self.max_fade)
        # Reduce contrast
        mean = img_array.mean()
        img_array = img_array * (1 - fade) + mean * fade
        # Slight warm shift (yellowing)
        img_array[:, :, 0] += random.uniform(0, 10)  # R
        img_array[:, :, 1] += random.uniform(0, 5)    # G
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        return Image.fromarray(img_array)


class RandomApply:
    """Apply a transform with a given probability."""

    def __init__(self, transform, p: float = 0.5):
        self.transform = transform
        self.p = p

    def __call__(self, img):
        if random.random() < self.p:
            return self.transform(img)
        return img


def get_train_transforms(image_size: int = 224, config: dict | None = None) -> transforms.Compose:
    """Get training augmentation pipeline with heritage-specific transforms.

    Args:
        image_size: Target image size (square).
        config: Optional augmentation config dict with probability overrides.
    """
    cfg = config or {}
    heritage_prob = cfg.get("heritage_augmentation_prob", 0.3)
    sepia_prob = cfg.get("sepia_prob", 0.15)
    noise_prob = cfg.get("noise_prob", 0.2)
    resolution_prob = cfg.get("resolution_degradation_prob", 0.15)
    geometric_prob = cfg.get("geometric_distortion_prob", 0.1)

    return transforms.Compose([
        transforms.Resize(int(image_size * 1.15)),
        transforms.RandomCrop(image_size),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05),
        # Heritage-specific augmentations (applied as PIL transforms before ToTensor)
        RandomApply(SepiaTransform(), p=sepia_prob),
        RandomApply(FilmGrainTransform(intensity=0.05), p=noise_prob),
        RandomApply(ResolutionDegradationTransform(), p=resolution_prob),
        RandomApply(JPEGCompressionTransform(), p=heritage_prob * 0.5),
        RandomApply(ScanningArtifactTransform(), p=heritage_prob * 0.3),
        RandomApply(GeometricDistortionTransform(max_shift=0.03), p=geometric_prob),
        RandomApply(FadingTransform(max_fade=0.25), p=heritage_prob * 0.4),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def get_val_transforms(image_size: int = 224) -> transforms.Compose:
    """Get validation/test augmentation pipeline (resize + center crop only)."""
    return transforms.Compose([
        transforms.Resize(int(image_size * 1.15)),
        transforms.CenterCrop(image_size),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
