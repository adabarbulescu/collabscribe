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

# Path to the frontend HTML file
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


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
    return FileResponse(FRONTEND_DIR / "index.html", media_type="text/html")
