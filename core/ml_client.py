"""HTTP client for Rhodesli ML Service.

Created Session 115. Wired to upload pipeline in Session 116.

Usage:
    client = MLServiceClient()  # reads ML_SERVICE_URL from env
    if client.is_configured:
        result = await client.detect_and_embed("/path/to/photo.jpg")
        faces = result["faces"]
    else:
        # Fall back to local InsightFace
        faces = extract_faces("/path/to/photo.jpg")
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Singleton client instance — reused across requests
_ml_client: "MLServiceClient | None" = None


def get_ml_client() -> "MLServiceClient":
    """Get or create the singleton ML service client."""
    global _ml_client
    if _ml_client is None:
        _ml_client = MLServiceClient()
    return _ml_client


class MLServiceClient:
    """Client for communicating with the standalone ML service.

    Feature flag: if ML_SERVICE_URL is not set, is_configured returns False
    and callers should fall back to local InsightFace.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("ML_SERVICE_URL", "")).rstrip("/")
        self.token = token or os.getenv("ML_SERVICE_TOKEN", "dev-token")
        self._client = None

    @property
    def is_configured(self) -> bool:
        """True if ML_SERVICE_URL is set and non-empty."""
        return bool(self.base_url)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=60.0,  # Face detection can take 10-30s for large images
            )
        return self._client

    async def health(self) -> dict:
        """Check ML service health. Returns response JSON."""
        client = await self._get_client()
        resp = await client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def detect_and_embed(self, image_path: str) -> dict:
        """Send image to ML service for face detection + embedding extraction.

        Returns dict with:
            - faces: list of {bbox, det_score, quality, embedding, landmarks}
            - image_size: [width, height]
            - processing_time_ms: int
            - model_info: {insightface_version, detection_model, embedding_dim}
        """
        client = await self._get_client()
        with open(image_path, "rb") as f:
            resp = await client.post(
                "/api/v1/detect-and-embed",
                files={"file": (os.path.basename(image_path), f, "image/jpeg")},
            )
        resp.raise_for_status()
        return resp.json()

    async def is_available(self) -> bool:
        """Check if ML service is reachable and healthy."""
        if not self.is_configured:
            return False
        try:
            result = await self.health()
            return result.get("status") == "healthy"
        except Exception as e:
            logger.debug("ML service unavailable: %s", e)
            return False

    async def close(self):
        """Clean up HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
