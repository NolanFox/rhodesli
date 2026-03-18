FROM python:3.11-slim

# System dependencies for OpenCV and InsightFace
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download buffalo_l model at build time (~300MB)
RUN python -c "\
from insightface.app import FaceAnalysis; \
fa = FaceAnalysis(name='buffalo_l', allowed_modules=['detection', 'recognition'], providers=['CPUExecutionProvider']); \
fa.prepare(ctx_id=-1, det_size=(640, 640)); \
print('buffalo_l model downloaded successfully')"

# Copy application code
COPY . .

# Performance tuning for single-threaded inference
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV EXECUTION_ENVIRONMENT=railway_ml_service

EXPOSE 5002

CMD ["uvicorn", "ml_service.main:app", "--host", "0.0.0.0", "--port", "5002"]
