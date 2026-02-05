# Dockerfile for Rhodesli web application
# Lightweight image - only web dependencies, no ML processing

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install minimal system dependencies
# libgl1 and libglib2.0-0 are needed by Pillow for some image formats
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY core/ core/
COPY scripts/ scripts/

# Bundle data for first-run volume initialization
# These are copied TO the volume on first deploy, then the volume persists
COPY data/ /app/data_bundle/
COPY raw_photos/ /app/photos_bundle/

# Create necessary directories
# /app/storage is for Railway single-volume mode (when STORAGE_DIR is set)
# /app/data and /app/raw_photos are for local Docker testing
RUN mkdir -p /app/data /app/raw_photos /app/storage

# Port (Railway sets PORT env var automatically)
EXPOSE ${PORT:-5001}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-5001}/health')" || exit 1

# Default environment variables for production
ENV HOST=0.0.0.0
ENV PORT=5001
ENV DEBUG=false
ENV PROCESSING_ENABLED=false

# Storage configuration:
# - STORAGE_DIR is set only on Railway (single-volume mode)
# - When STORAGE_DIR is set, DATA_DIR and PHOTOS_DIR are derived from it
# - When STORAGE_DIR is not set (local Docker), use DATA_DIR and PHOTOS_DIR directly
# Railway sets: STORAGE_DIR=/app/storage (via environment variables)
# Local Docker: uses DATA_DIR=data and PHOTOS_DIR=raw_photos
ENV DATA_DIR=data
ENV PHOTOS_DIR=raw_photos

# Start: init volume if needed, then run app
CMD python scripts/init_railway_volume.py && python app/main.py
