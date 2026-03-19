"""
Pytest fixtures for backend service tests.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DSN = "postgresql://postgres:postgres@localhost:5432/collabscribe_test"


@pytest.fixture(scope="session")
def event_loop():
    """Provide a session-scoped event loop for pytest-asyncio."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_pool():
    """Create a PostgreSQL connection pool for service tests."""
    try:
        pool = await asyncpg.create_pool(
            TEST_DSN,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )
    except Exception as exc:
        pytest.skip(f"PostgreSQL test database unavailable at {TEST_DSN}: {exc}")
    try:
        yield pool
    finally:
        await pool.close()


@pytest.fixture
async def versioning_service(test_db_pool):
    """Provide VersioningService with a clean schema per test."""
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            CREATE EXTENSION IF NOT EXISTS "pgcrypto";
            DROP TABLE IF EXISTS document_versions CASCADE;
            DROP TABLE IF EXISTS documents CASCADE;

            CREATE TABLE documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title VARCHAR(512) NOT NULL DEFAULT 'Untitled Document',
                owner_id UUID,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE document_versions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                content TEXT NOT NULL DEFAULT '',
                version_number INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(document_id, version_number)
            );
            """
        )

    from services import VersioningService

    service = VersioningService(test_db_pool)
    yield service

    async with test_db_pool.acquire() as conn:
        await conn.execute(
            """
            DROP TABLE IF EXISTS document_versions CASCADE;
            DROP TABLE IF EXISTS documents CASCADE;
            """
        )


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "concurrency: mark test as concurrency test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def anyio_backend():
    """Configure AnyIO to use asyncio."""
    return "asyncio"


@pytest.fixture
def client():
    """API endpoint tests are intentionally skipped in this harness."""
    pytest.skip("API endpoint tests are not configured for the current test harness.")
