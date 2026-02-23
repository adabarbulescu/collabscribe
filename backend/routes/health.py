"""
Health check endpoint.
"""

import logging

from fastapi import APIRouter

from database import check_connection

logger = logging.getLogger("collab.routes.health")

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health endpoint that verifies database connectivity.

    Returns:
        Dictionary with status and database connection status.
    """
    db_ok = await check_connection()
    status = "healthy" if db_ok else "unhealthy"
    code = 200 if db_ok else 503

    if not db_ok:
        logger.warning("Database health check failed")

    return {
        "status": status,
        "database": "connected" if db_ok else "disconnected",
    }
