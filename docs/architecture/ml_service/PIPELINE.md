# ML Service Automated Pipeline

**Parent:** [ML_SERVICE.md](../ML_SERVICE.md)

The ML service runs the full pipeline automatically, not just inference.
This eliminates the laptop dependency entirely.

## Trigger: Upload Webhook

```
User uploads photo → Web app saves to R2 staging
                   → Web app POSTs to ML service /api/v1/pipeline/trigger
                   → ML service:
                       1. Downloads photo from R2
                       2. Runs face detection + embedding
                       3. Writes embeddings to Supabase (not .npy file)
                       4. Runs clustering against existing embeddings
                       5. Creates proposals (Tier 1 auto-add, Tier 2 suggestions)
                       6. Uploads crops to R2
                       7. Notifies web app via callback
```

## Trigger: Scheduled Batch

```
Cron (nightly or weekly) → ML service:
    1. Recalibrate isotonic model (if new confirmed pairs exist)
    2. Re-cluster INBOX faces against updated embeddings
    3. Run Gemini batch reanalysis on flagged photos
    4. Generate pipeline health report
```

## Data Flow Change

**Before:** Embeddings in `data/embeddings.npy` (file on Railway volume, synced via git)
**After:** Embeddings in Supabase `face_embeddings` table (already partially migrated
per DATA-007). The ML service reads/writes Supabase directly.

This eliminates the entire `sync_from_production.py` → local processing →
`push_to_production.py` cycle that has caused Lesson 78 (production-local
divergence, the #1 recurring deployment failure).

## Web App Integration

### Before (current)
```python
# app/upload_routes.py
from core.processing import process_directory
result = process_directory(photo_path)  # Local InsightFace
```

### After (with ML service)
```python
# app/upload_routes.py
from core.ml_client import MLServiceClient
client = MLServiceClient(os.environ.get("ML_SERVICE_URL"))
result = await client.detect_and_embed(photo_path)
```

### Fallback
```python
# core/ml_client.py
class MLServiceClient:
    async def detect_and_embed(self, image_path):
        if self.service_url:
            return await self._call_service(image_path)
        else:
            # Fallback to local (development)
            from core.processing import process_directory
            return process_directory(image_path)
```
