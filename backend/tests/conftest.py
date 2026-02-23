"""
Pytest configuration and fixtures for versioning tests.
Provides database setup, async test support, and service/client fixtures.
"""

import pytest
import asyncio
import asyncpg
from fastapi.testclient import TestClient
from sqlalchemy import text

# Note: These imports assume the package structure from main.py
# In actual implementation, adjust paths based on PYTHONPATH configuration


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_pool():
    """
    Create a PostgreSQL connection pool for testing.
    Uses a test database; creates and cleans up schema.
    """
    # Connection string - use test database
    # In real implementation, read from TEST_DATABASE_URL environment variable
    dsn = "postgresql://postgres:postgres@localhost:5432/collaborative_editor_test"
    
    try:
        pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=5,
            command_timeout=60,
        )
        yield pool
    finally:
        if pool:
            await pool.close()


@pytest.fixture
async def versioning_service(test_db_pool):
    """
    Provide VersioningService instance with fresh database schema.
    Schema is created before each test and dropped after.
    """
    # Setup: Create schema
    async with test_db_pool.acquire() as conn:
        await conn.execute("""
            DROP TABLE IF EXISTS document_versions CASCADE;
            DROP TABLE IF EXISTS documents CASCADE;
        """)
        
        # Create documents table
        await conn.execute("""
            CREATE TABLE documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id VARCHAR(255) UNIQUE NOT NULL,
                title VARCHAR(512),
                owner_id VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create document_versions table
        await conn.execute("""
            CREATE TABLE document_versions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, version_number)
            );
        """)
        
        # Create index for efficient version number lookups
        await conn.execute("""
            CREATE INDEX idx_document_versions_document_version 
            ON document_versions(document_id, version_number);
        """)
    
    # Import here to avoid circular imports
    from services import VersioningService
    
    service = VersioningService(test_db_pool)
    yield service
    
    # Cleanup: Drop schema
    async with test_db_pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS document_versions CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS documents CASCADE;")


@pytest.fixture
def client(test_db_pool):
    """
    Provide FastAPI TestClient with versioning service injected.
    """
    from main import app, get_db_pool
    from services import VersioningService
    
    # Override the get_db_pool dependency to use test pool
    def override_get_db_pool():
        return test_db_pool
    
    app.dependency_overrides[get_db_pool] = override_get_db_pool
    
    client = TestClient(app)
    yield client
    
    # Cleanup
    app.dependency_overrides.clear()


# Markers for categorizing tests
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (requires pytest-asyncio)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "concurrency: mark test as concurrency/race condition test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Async test marker configuration
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"
