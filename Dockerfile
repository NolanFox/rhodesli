# Dockerfile for Rhodesli web application
# Full image with ML processing (InsightFace face detection + comparison)

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# libgl1, libglib2.0-0 — OpenCV image format support
# libgomp1 — OpenMP threading for ONNX Runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download InsightFace buffalo_l model at build time (~300MB)
# This ensures face detection is available immediately on Railway
# The model is stored in /root/.insightface/models/buffalo_l/
RUN python -c "\
from insightface.app import FaceAnalysis; \
fa = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider']); \
fa.prepare(ctx_id=-1, det_size=(640, 640)); \
print('InsightFace buffalo_l model downloaded and verified')"

# Copy application code
COPY app/ app/
COPY core/ core/
COPY scripts/ scripts/

# Copy rhodesli_ml subpackages needed at runtime (graph + importers only)
# Full ML package has 3GB+ of .venv/checkpoints — only copy pure-Python modules
COPY rhodesli_ml/__init__.py rhodesli_ml/__init__.py
COPY rhodesli_ml/graph/ rhodesli_ml/graph/
COPY rhodesli_ml/importers/ rhodesli_ml/importers/

# Copy CHANGELOG.md for dynamic version display
COPY CHANGELOG.md .

# Bundle JSON data for first-run volume initialization
# This is copied TO the volume on first deploy, then the volume persists
# NOTE: Photos are NOT bundled - they're served from Cloudflare R2
COPY data/ /app/data_bundle/

# Create necessary directories
# /app/storage is for Railway single-volume mode (when STORAGE_DIR is set)
# /app/data is for local Docker testing
RUN mkdir -p /app/data /app/storage

# Port (Railway sets PORT env var automatically)
EXPOSE ${PORT:-5001}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-5001}/health')" || exit 1

# Default environment variables for production
ENV HOST=0.0.0.0
ENV PORT=5001
ENV DEBUG=false
ENV PROCESSING_ENABLED=true

# Storage configuration:
# - JSON data lives on Railway volume (STORAGE_DIR=/app/storage)
# - Photos served from Cloudflare R2 (STORAGE_MODE=r2, R2_PUBLIC_URL)
# - Local dev uses filesystem (STORAGE_MODE=local, default)
#
# Railway sets: STORAGE_DIR=/app/storage, STORAGE_MODE=r2, R2_PUBLIC_URL
# Local Docker: uses DATA_DIR=data, STORAGE_MODE=local (default)
ENV DATA_DIR=data
ENV STORAGE_MODE=local

# Start: init volume if needed, then run app
CMD python scripts/init_railway_volume.py && python app/main.py
