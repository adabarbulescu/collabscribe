"""
Service for comparing document versions and computing diffs.
"""

from __future__ import annotations

import difflib
import logging
from typing import Optional
from uuid import UUID, uuid5, NAMESPACE_URL

from asyncpg import Pool

logger = logging.getLogger("collabscribe.services.diff")


class DiffService:
    """Service for version comparison and diff computation."""

    def __init__(self, pool: Pool):
        self.pool = pool

    async def get_version_content(self, doc_id: str, version_number: int) -> Optional[dict]:
        """
        Fetch content and metadata for a specific version.

        Args:
            doc_id: Document identifier
            version_number: Version number to retrieve

        Returns:
            Dictionary with version metadata and content, or None if not found
        """
        document_id = await self._resolve_document_id(doc_id)
        if document_id is None:
            return None

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT version_number, created_at, content
                FROM document_versions
                WHERE document_id = $1 AND version_number = $2
                """,
                document_id,
                version_number,
            )

        if not row:
            return None

        content = row["content"] or ""
        word_count = len(content.split())
        char_count = len(content)

        return {
            "version_number": row["version_number"],
            "created_at": row["created_at"],
            "content": content,
            "word_count": word_count,
            "char_count": char_count,
        }

    async def get_version_list(self, doc_id: str, limit: int = 50) -> list[dict]:
        """
        Get list of all versions for a document.

        Args:
            doc_id: Document identifier
            limit: Maximum number of versions to return

        Returns:
            List of version metadata dictionaries
        """
        document_id = await self._resolve_document_id(doc_id)
        if document_id is None:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT version_number, created_at, content
                FROM document_versions
                WHERE document_id = $1
                ORDER BY version_number DESC
                LIMIT $2
                """,
                document_id,
                limit,
            )

        versions = []
        for row in rows:
            content = row["content"] or ""
            versions.append({
                "version_number": row["version_number"],
                "created_at": row["created_at"],
                "word_count": len(content.split()),
                "char_count": len(content),
                "preview": content[:100] + "..." if len(content) > 100 else content,
            })

        return versions

    def compute_diff(self, text1: str, text2: str, context_lines: int = 3) -> list[dict]:
        """
        Compute word-level diff between two texts.

        Args:
            text1: Original text
            text2: Modified text
            context_lines: Number of context lines to include

        Returns:
            List of diff chunks with operations
        """
        # Split into words for word-level diff
        words1 = text1.split()
        words2 = text2.split()

        # Use SequenceMatcher for diff computation
        matcher = difflib.SequenceMatcher(None, words1, words2)
        chunks = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                text = ' '.join(words1[i1:i2])
                chunks.append({
                    "operation": "equal",
                    "text": text,
                })
            elif tag == 'delete':
                text = ' '.join(words1[i1:i2])
                chunks.append({
                    "operation": "delete",
                    "text": text,
                })
            elif tag == 'insert':
                text = ' '.join(words2[j1:j2])
                chunks.append({
                    "operation": "insert",
                    "text": text,
                })
            elif tag == 'replace':
                # Treat replace as delete + insert
                if i2 > i1:
                    text = ' '.join(words1[i1:i2])
                    chunks.append({
                        "operation": "delete",
                        "text": text,
                    })
                if j2 > j1:
                    text = ' '.join(words2[j1:j2])
                    chunks.append({
                        "operation": "insert",
                        "text": text,
                    })

        return chunks

    def compute_analytics_deltas(
        self,
        analytics1: Optional[dict],
        analytics2: Optional[dict]
    ) -> list[dict]:
        """
        Compare analytics between two versions and compute deltas.

        Args:
            analytics1: Analytics from version 1
            analytics2: Analytics from version 2

        Returns:
            List of analytics delta dictionaries
        """
        if not analytics1 or not analytics2:
            return []

        deltas = []

        # Compare readability
        if analytics1.get("readability") and analytics2.get("readability"):
            old_val = analytics1["readability"].get("flesch_reading_ease", 0)
            new_val = analytics2["readability"].get("flesch_reading_ease", 0)
            delta = new_val - old_val
            percent = (delta / old_val * 100) if old_val != 0 else 0

            deltas.append({
                "metric": "Readability Score",
                "old_value": round(old_val, 2),
                "new_value": round(new_val, 2),
                "delta": round(delta, 2),
                "percent_change": round(percent, 1) if old_val != 0 else None,
                "direction": "up" if delta > 0.5 else ("down" if delta < -0.5 else "neutral"),
            })

        # Compare sentiment
        if analytics1.get("sentiment") and analytics2.get("sentiment"):
            old_val = analytics1["sentiment"].get("polarity", 0)
            new_val = analytics2["sentiment"].get("polarity", 0)
            delta = new_val - old_val

            deltas.append({
                "metric": "Sentiment Polarity",
                "old_value": round(old_val, 3),
                "new_value": round(new_val, 3),
                "delta": round(delta, 3),
                "percent_change": None,
                "direction": "up" if delta > 0.05 else ("down" if delta < -0.05 else "neutral"),
            })

        # Compare word count
        old_words = analytics1.get("basic_metrics", {}).get("word_count", 0)
        new_words = analytics2.get("basic_metrics", {}).get("word_count", 0)
        delta = new_words - old_words
        percent = (delta / old_words * 100) if old_words != 0 else 0

        deltas.append({
            "metric": "Word Count",
            "old_value": old_words,
            "new_value": new_words,
            "delta": delta,
            "percent_change": round(percent, 1) if old_words != 0 else None,
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "neutral"),
        })

        # Compare unique vocabulary
        if analytics1.get("vocabulary") and analytics2.get("vocabulary"):
            old_val = analytics1["vocabulary"].get("unique_words", 0)
            new_val = analytics2["vocabulary"].get("unique_words", 0)
            delta = new_val - old_val

            deltas.append({
                "metric": "Unique Words",
                "old_value": old_val,
                "new_value": new_val,
                "delta": delta,
                "percent_change": None,
                "direction": "up" if delta > 0 else ("down" if delta < 0 else "neutral"),
            })

        return deltas

    async def _resolve_document_id(self, doc_id: str) -> Optional[UUID]:
        """Resolve document ID string to UUID."""
        if not doc_id:
            return None
        doc_uuid = uuid5(NAMESPACE_URL, doc_id) if not self._is_valid_uuid(doc_id) else UUID(doc_id)
        try:
            async with self.pool.acquire() as conn:
                return await conn.fetchval(
                    "SELECT id FROM documents WHERE id = $1",
                    doc_uuid,
                )
        except Exception as exc:
            logger.warning("Failed to resolve document id %s: %s", doc_id, exc)
            return None

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """Check if string is a valid UUID."""
        try:
            UUID(value)
            return True
        except ValueError:
            return False
