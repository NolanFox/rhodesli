FROM python:3.11-slim

# System dependencies for OpenCV and InsightFace
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
# With rootDirectory=ml_service, build context is ml_service/
# So requirements.txt refers to ml_service/requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download buffalo_l model at build time (~300MB)
RUN python -c "\
from insightface.app import FaceAnalysis; \
fa = FaceAnalysis(name='buffalo_l', allowed_modules=['detection', 'recognition'], providers=['CPUExecutionProvider']); \
fa.prepare(ctx_id=-1, det_size=(640, 640)); \
print('buffalo_l model downloaded successfully')"

# Copy application code into ml_service package structure
# Build context is ml_service/, so COPY . gets all .py files
COPY __init__.py config.py main.py detect.py /app/ml_service/

# Performance tuning for single-threaded inference
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV EXECUTION_ENVIRONMENT=railway_ml_service
ENV PYTHONPATH=/app

EXPOSE 5002

# Railway assigns PORT dynamically — service MUST listen on $PORT
CMD ["sh", "-c", "uvicorn ml_service.main:app --host 0.0.0.0 --port ${PORT:-5002}"]
