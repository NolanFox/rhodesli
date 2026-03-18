"""HTTP client for Rhodesli ML Service.

Wired in Session 116. This session creates the interface only.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


class MLServiceClient:
    """Client for communicating with the standalone ML service."""

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
        return bool(self.base_url)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=30.0,
            )
        return self._client

    async def health(self) -> dict:
        """Check ML service health."""
        client = await self._get_client()
        resp = await client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def detect_and_embed(self, image_path: str) -> dict:
        """Send image to ML service for face detection + embedding extraction."""
        client = await self._get_client()
        with open(image_path, "rb") as f:
            resp = await client.post(
                "/api/v1/detect-and-embed",
                files={"file": (os.path.basename(image_path), f, "image/jpeg")},
            )
        resp.raise_for_status()
        return resp.json()

    async def is_available(self) -> bool:
        """Check if ML service is reachable."""
        if not self.is_configured:
            return False
        try:
            await self.health()
            return True
        except Exception:
            return False

    async def close(self):
        """Clean up HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
