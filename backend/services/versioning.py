"""
Document versioning business logic service.
Handles version creation, retrieval, and lifecycle management.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid5, NAMESPACE_URL

import asyncpg

logger = logging.getLogger("collab.services.versioning")


class DocumentNotFoundError(Exception):
    """Raised when a document is not found."""

    pass


class VersioningService:
    """Service for managing document versions and snapshots."""

    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize versioning service.

        Args:
            pool: asyncpg connection pool instance.
        """
        self.pool = pool

    async def get_or_create_document(
        self,
        doc_id: str,
        title: str = "Untitled Document",
    ) -> UUID:
        """
        Get document by ID, creating it if it doesn't exist.

        Implements idempotent creation: if document already exists, returns its ID.
        Uses INSERT ... ON CONFLICT to handle race conditions atomically.

        Args:
            doc_id: Document identifier (usually 8-char hex from URL)
            title: Document title (default: "Untitled Document")

        Returns:
            UUID of the document (newly created or existing)

        Raises:
            asyncpg.PostgresError: If database operation fails
        """
        # Validate doc_id format
        if not doc_id or not isinstance(doc_id, str) or len(doc_id) < 4:
            raise ValueError(f"Invalid document ID format: {doc_id}")

        async with self.pool.acquire() as conn:
            try:
                # Create a deterministic UUID from doc_id string
                # uuid5 is deterministic across processes (unlike hash())
                doc_uuid = uuid5(NAMESPACE_URL, doc_id) if not self._is_valid_uuid(doc_id) else UUID(doc_id)

                # INSERT ... ON CONFLICT for idempotent creation
                result = await conn.fetchrow(
                    """
                    INSERT INTO documents (id, title, created_at, updated_at)
                    VALUES ($1, $2, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                      updated_at = NOW()
                    RETURNING id
                    """,
                    doc_uuid,
                    title,
                )
                logger.info(f"Document ensured: {doc_uuid} (title='{title}')")
                return result["id"]

            except asyncpg.PostgresError as exc:
                logger.error(f"Failed to get or create document {doc_id}: {exc}")
                raise

    async def create_version(
        self,
        doc_id: str | UUID,
        content: str,
    ) -> tuple[UUID, int]:
        """
        Create a new version for a document.

        Handles concurrent creates atomically:
        1. Get/create document (idempotent)
        2. Lock document row (SELECT FOR UPDATE)
        3. Get next version number
        4. Insert version
        5. Update document updated_at timestamp

        Args:
            doc_id: Document ID (string or UUID)
            content: Plain text content to save

        Returns:
            Tuple of (version_id: UUID, version_number: int) for the created version

        Raises:
            ValueError: If doc_id format is invalid
            asyncpg.PostgresError: If database operation fails
        """
        if isinstance(doc_id, str):
            document_id = await self.get_or_create_document(doc_id)
        else:
            document_id = doc_id

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # Lock document row to prevent concurrent version number races
                    await conn.fetchval(
                        "SELECT id FROM documents WHERE id = $1 FOR UPDATE",
                        document_id,
                    )

                    # Get next version number
                    max_version = await conn.fetchval(
                        "SELECT COALESCE(MAX(version_number), 0) FROM document_versions WHERE document_id = $1",
                        document_id,
                    )
                    next_version = max_version + 1

                    # Insert new version
                    result = await conn.fetchrow(
                        """
                        INSERT INTO document_versions (id, document_id, content, version_number, created_at)
                        VALUES (gen_random_uuid(), $1, $2, $3, NOW())
                        RETURNING id, version_number
                        """,
                        document_id,
                        content,
                        next_version,
                    )

                    # Update document timestamp
                    await conn.execute(
                        "UPDATE documents SET updated_at = NOW() WHERE id = $1",
                        document_id,
                    )

                    version_id = result["id"]
                    version_number = result["version_number"]

                    logger.info(
                        f"Version created: doc_id={document_id}, version={version_number}, "
                        f"content_length={len(content)}"
                    )

                    return version_id, version_number

                except asyncpg.PostgresError as exc:
                    logger.error(
                        f"Failed to create version for document {document_id}: {exc}"
                    )
                    raise

    async def get_version_history(
        self,
        doc_id: str | UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        """
        Get paginated version history for a document.

        Returns versions ordered by version_number descending (newest first).

        Args:
            doc_id: Document ID (string or UUID)
            page: Page number (1-based, default: 1)
            page_size: Results per page (max: 100, default: 20)

        Returns:
            Tuple of (versions_list, total_count)
            Each version dict contains: id, document_id, version_number, created_at, content_preview

        Raises:
            DocumentNotFoundError: If document doesn't exist
            ValueError: If pagination parameters invalid
        """
        if page < 1 or page_size < 1:
            raise ValueError("Page and page_size must be >= 1")
        if page_size > 100:
            page_size = 100

        if isinstance(doc_id, str):
            # Find document by ID
            document_id = await self._find_document_by_id(doc_id)
        else:
            document_id = doc_id

        async with self.pool.acquire() as conn:
            try:
                # Get total count
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM document_versions WHERE document_id = $1",
                    document_id,
                )

                if total == 0:
                    return [], 0

                # Get paginated results
                offset = (page - 1) * page_size
                rows = await conn.fetch(
                    """
                    SELECT id, document_id, version_number, created_at, 
                           LENGTH(content) as content_length,
                           SUBSTRING(content, 1, 100) as content_preview
                    FROM document_versions
                    WHERE document_id = $1
                    ORDER BY version_number DESC
                    LIMIT $2 OFFSET $3
                    """,
                    document_id,
                    page_size,
                    offset,
                )

                versions = [dict(row) for row in rows]
                logger.debug(
                    f"Retrieved version history: doc_id={document_id}, "
                    f"page={page}, count={len(versions)}, total={total}"
                )

                return versions, total

            except asyncpg.PostgresError as exc:
                logger.error(
                    f"Failed to retrieve version history for {document_id}: {exc}"
                )
                raise

    async def get_latest_version(self, doc_id: str | UUID) -> dict | None:
        """
        Get the latest version for a document.

        Args:
            doc_id: Document ID (string or UUID)

        Returns:
            Latest version dict or None if no versions exist

        Raises:
            DocumentNotFoundError: If document doesn't exist
        """
        if isinstance(doc_id, str):
            document_id = await self._find_document_by_id(doc_id)
        else:
            document_id = doc_id

        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    SELECT id, document_id, version_number, created_at, content
                    FROM document_versions
                    WHERE document_id = $1
                    ORDER BY version_number DESC
                    LIMIT 1
                    """,
                    document_id,
                )

                if row:
                    logger.debug(
                        f"Retrieved latest version: doc_id={document_id}, version={row['version_number']}"
                    )
                    return dict(row)
                return None

            except asyncpg.PostgresError as exc:
                logger.error(
                    f"Failed to retrieve latest version for {document_id}: {exc}"
                )
                raise

    async def get_version_by_number(
        self,
        doc_id: str | UUID,
        version_number: int,
    ) -> dict | None:
        """
        Get a specific version by version number.

        Args:
            doc_id: Document ID (string or UUID)
            version_number: Version number to retrieve

        Returns:
            Version dict or None if not found

        Raises:
            DocumentNotFoundError: If document doesn't exist
            ValueError: If version_number invalid
        """
        if version_number < 1:
            raise ValueError("version_number must be >= 1")

        if isinstance(doc_id, str):
            document_id = await self._find_document_by_id(doc_id)
        else:
            document_id = doc_id

        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    SELECT id, document_id, version_number, created_at, content
                    FROM document_versions
                    WHERE document_id = $1 AND version_number = $2
                    """,
                    document_id,
                    version_number,
                )

                if row:
                    logger.debug(
                        f"Retrieved version: doc_id={document_id}, version={version_number}"
                    )
                    return dict(row)
                return None

            except asyncpg.PostgresError as exc:
                logger.error(
                    f"Failed to retrieve version {version_number} for {document_id}: {exc}"
                )
                raise

    async def _find_document_by_id(self, doc_id: str) -> UUID:
        """
        Find a document's UUID by its ID string.

        Args:
            doc_id: Document identifier string

        Returns:
            UUID of the document

        Raises:
            DocumentNotFoundError: If document doesn't exist
        """
        async with self.pool.acquire() as conn:
            try:
                # Deterministic UUID lookup (matches ensure_document)
                doc_uuid = uuid5(NAMESPACE_URL, doc_id) if not self._is_valid_uuid(doc_id) else UUID(doc_id)

                result = await conn.fetchval(
                    "SELECT id FROM documents WHERE id = $1",
                    doc_uuid,
                )

                if result:
                    return result

                raise DocumentNotFoundError(f"Document not found: {doc_id}")

            except asyncpg.PostgresError as exc:
                logger.error(f"Database error looking up document {doc_id}: {exc}")
                raise

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """Check if a string is a valid UUID."""
        try:
            UUID(value)
            return True
        except ValueError:
            return False
