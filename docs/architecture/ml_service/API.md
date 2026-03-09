# ML Service API Specification

**Parent:** [ML_SERVICE.md](../ML_SERVICE.md)

## Endpoints

| Method | Path | Description | Input | Output |
|--------|------|-------------|-------|--------|
| `GET` | `/health` | Health check + model status | — | `{"status": "ok", "models_loaded": true}` |
| `POST` | `/api/v1/detect` | Detect faces in image | Image file | Face bounding boxes + scores |
| `POST` | `/api/v1/embed` | Extract face embeddings | Image file | 512-dim embedding vectors |
| `POST` | `/api/v1/detect-and-embed` | Combined detection + embedding | Image file | Faces with bboxes + embeddings |
| `POST` | `/api/v1/compare` | Compare two face sets | Two image files | Similarity matrix |
| `POST` | `/api/v1/align` | Face alignment coordinates | Image file + face index | Alignment landmarks |
| `POST` | `/api/v1/cluster` | Run clustering on new faces | — | Cluster assignments |
| `GET` | `/api/v1/pipeline/status` | Pipeline run status | — | Last run, next scheduled, queue depth |

## Request/Response Format

```python
# POST /api/v1/detect-and-embed
# Request: multipart/form-data with image file

# Response:
{
  "faces": [
    {
      "bbox": [x1, y1, x2, y2],
      "det_score": 0.95,
      "quality": 0.82,
      "embedding": [0.123, -0.456, ...],  # 512-dim
      "landmarks": [[x, y], ...]  # 5-point
    }
  ],
  "image_size": [width, height],
  "processing_time_ms": 1234
}
```

## Authentication

Service-to-service auth via shared secret:
```
Authorization: Bearer {ML_SERVICE_TOKEN}
```

No user-level auth — the web service handles all user authentication.
