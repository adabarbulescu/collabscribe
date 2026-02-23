"""
Database connection pool and helper utilities using asyncpg.
"""

from __future__ import annotations

import logging
from typing import Optional

import asyncpg

from config import settings

logger = logging.getLogger("collab.database")

# ---------------------------------------------------------------------------
# Global connection pool (created at startup, closed at shutdown)
# ---------------------------------------------------------------------------
_pool: Optional[asyncpg.Pool] = None


def _get_dsn() -> str:
    """
    Build a PostgreSQL DSN from settings.

    Returns:
        PostgreSQL connection string.
    """
    return (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


async def create_pool() -> asyncpg.Pool:
    """
    Create and return the global connection pool.

    Returns:
        asyncpg connection pool instance.

    Raises:
        Exception: If connection pool creation fails.
    """
    global _pool
    if _pool is not None:
        return _pool

    dsn = _get_dsn()
    logger.info(
        "Creating database connection pool (min=%d, max=%d)",
        settings.db_pool_min_size,
        settings.db_pool_max_size,
    )

    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=60,
    )
    logger.info("Database connection pool created successfully")
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool is not None:
        logger.info("Closing database connection pool")
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")


def get_pool() -> asyncpg.Pool:
    """
    Return the current connection pool.

    Returns:
        asyncpg connection pool instance.

    Raises:
        RuntimeError: If pool is not initialized.
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool is not initialized. "
            "Call create_pool() during application startup."
        )
    return _pool


async def check_connection() -> bool:
    """
    Test database connectivity.

    Returns:
        True if database is reachable, False otherwise.
    """
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False

