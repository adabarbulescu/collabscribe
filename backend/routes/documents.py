"""
Document routes: root redirect and document serving.
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

logger = logging.getLogger("collabscribe.routes.documents")

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REACT_FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend-app" / "dist"
REACT_FRONTEND_INDEX = REACT_FRONTEND_DIST_DIR / "index.html"


def _get_frontend_entrypoint() -> Path:
    """Return the built React app entrypoint."""
    return REACT_FRONTEND_INDEX


@router.get("/")
async def index_redirect() -> RedirectResponse:
    """
    Redirect root to a new document.

    Returns:
        Redirect response to a unique document URL.
    """
    doc_id = uuid.uuid4().hex[:8]
    logger.debug(f"Creating new document: {doc_id}")
    return RedirectResponse(url=f"/doc/{doc_id}")


@router.get("/doc/{doc_id}")
async def serve_doc(doc_id: str) -> FileResponse:
    """
    Serve the frontend HTML for a given document.

    Args:
        doc_id: Document identifier.

    Returns:
        Frontend HTML file.
    """
    logger.debug(f"Serving document: {doc_id}")
    return FileResponse(_get_frontend_entrypoint(), media_type="text/html")
