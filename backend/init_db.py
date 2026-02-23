"""
Database initialization script.
Creates all required tables and indexes if they do not exist.
Can be run standalone or called from the FastAPI startup event.
"""

from __future__ import annotations

import logging

import asyncpg

logger = logging.getLogger("collab.init_db")

# ---------------------------------------------------------------------------
# SQL Schema
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
-- Enable uuid-ossp extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title       VARCHAR(512) NOT NULL DEFAULT 'Untitled Document',
    owner_id    UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Document versions table
CREATE TABLE IF NOT EXISTS document_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content         TEXT NOT NULL DEFAULT '',
    version_number  INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_documents_owner_id
    ON documents (owner_id);

CREATE INDEX IF NOT EXISTS idx_documents_created_at
    ON documents (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_documents_updated_at
    ON documents (updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_document_versions_document_id
    ON document_versions (document_id);

CREATE INDEX IF NOT EXISTS idx_document_versions_created_at
    ON document_versions (created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_versions_doc_version
    ON document_versions (document_id, version_number);

-- Analytics cache table
CREATE TABLE IF NOT EXISTS document_analytics (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id     TEXT NOT NULL,
    content_hash    VARCHAR(64) NOT NULL,
    analytics_data  JSONB NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_analytics_hash
    ON document_analytics (content_hash);

CREATE INDEX IF NOT EXISTS idx_document_analytics_document_id
    ON document_analytics (document_id);
"""

# ---------------------------------------------------------------------------
# Trigger to auto-update `updated_at` on the documents table
# ---------------------------------------------------------------------------
TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_documents_updated_at'
    ) THEN
        CREATE TRIGGER trg_documents_updated_at
            BEFORE UPDATE ON documents
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END;
$$;
"""


async def create_tables(pool: asyncpg.Pool) -> None:
    """Execute the schema creation SQL against the given pool."""
    logger.info("Running database schema initialization...")
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
        await conn.execute(TRIGGER_SQL)
    logger.info("Database schema initialization complete")


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import os
    import sys

# Allow running from project root: python -m backend.init_db
    # or from backend/: python init_db.py
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from database import create_pool, close_pool  # type: ignore[import-untyped]

    async def main() -> None:
        logging.basicConfig(level=logging.INFO)
        pool = await create_pool()
        try:
            await create_tables(pool)
            print("✓ Database tables created successfully.")
        finally:
            await close_pool()

    asyncio.run(main())
