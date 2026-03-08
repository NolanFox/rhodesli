"""
Compare V2 routes — Tier 2 Face Comparison API.

Stub implementation for PRD-031. Returns not_implemented until
ONNX export and real-time inference are available.

See: docs/prds/031_face_compare_tier2.md
See: docs/architecture/ML_SERVICE.md
"""

import logging

from fasthtml.common import *
from starlette.responses import JSONResponse

from app.main import rt

logger = logging.getLogger(__name__)


@rt("/api/v2/compare/status")
def get():
    """Health/status endpoint for Compare V2 API."""
    return JSONResponse(
        {"status": "not_implemented", "version": "v2"},
        status_code=501,
    )


@rt("/api/v2/compare/embed")
async def post():
    """Extract face embeddings from uploaded image (not yet implemented)."""
    return JSONResponse(
        {
            "status": "not_implemented",
            "message": "Real-time embedding requires ONNX export. See PRD-031.",
            "version": "v2",
        },
        status_code=501,
    )


@rt("/api/v2/compare")
async def post():  # noqa: F811 — FastHTML routes use function name for HTTP method
    """Compare two images or an image against the archive (not yet implemented)."""
    return JSONResponse(
        {
            "status": "not_implemented",
            "message": "Tier 2 comparison requires ML service. See PRD-031.",
            "version": "v2",
        },
        status_code=501,
    )
