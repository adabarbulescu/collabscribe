"""
Routes for version comparison and diff operations.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from database import get_pool
from services.diff_service import DiffService
from services.analytics import AnalyticsService
from models.diff import (
    VersionMetadata,
    DiffChunk,
    AnalyticsDelta,
    VersionComparisonResponse,
)

logger = logging.getLogger("collabscribe.routes.diff")

router = APIRouter(prefix="/api/diff", tags=["diff"])


@router.get("/{doc_id}/versions")
async def get_versions(doc_id: str, limit: int = Query(50, ge=1, le=200)):
    """
    Get list of all versions for a document.

    Args:
        doc_id: Document identifier
        limit: Maximum number of versions to return

    Returns:
        List of version metadata
    """
    pool = get_pool()
    diff_service = DiffService(pool)

    versions = await diff_service.get_version_list(doc_id, limit)

    return {
        "document_id": doc_id,
        "versions": versions,
        "count": len(versions),
    }


@router.get("/{doc_id}/compare")
async def compare_versions(
    doc_id: str,
    v1: int = Query(..., description="First version number", ge=1),
    v2: int = Query(..., description="Second version number", ge=1),
    include_analytics: bool = Query(True, description="Include analytics comparison"),
):
    """
    Compare two versions of a document.

    Args:
        doc_id: Document identifier
        v1: First version number
        v2: Second version number
        include_analytics: Whether to include analytics comparison

    Returns:
        Version comparison with diff chunks and analytics deltas
    """
    if v1 == v2:
        raise HTTPException(status_code=400, detail="Cannot compare a version with itself")

    pool = get_pool()
    diff_service = DiffService(pool)

    # Fetch both versions
    version1_data = await diff_service.get_version_content(doc_id, v1)
    version2_data = await diff_service.get_version_content(doc_id, v2)

    if not version1_data:
        raise HTTPException(status_code=404, detail=f"Version {v1} not found")
    if not version2_data:
        raise HTTPException(status_code=404, detail=f"Version {v2} not found")

    # Compute diff
    diff_chunks = diff_service.compute_diff(
        version1_data["content"],
        version2_data["content"],
    )

    # Compute analytics deltas if requested
    analytics_deltas = []
    if include_analytics:
        analytics_service = AnalyticsService(pool)

        # Compute analytics for both versions
        analytics1 = analytics_service._compute_all(
            doc_id,
            version1_data["content"],
            f"v{v1}",
        )
        analytics2 = analytics_service._compute_all(
            doc_id,
            version2_data["content"],
            f"v{v2}",
        )

        analytics_deltas = diff_service.compute_analytics_deltas(analytics1, analytics2)

    # Build response
    version1_meta = VersionMetadata(
        version_number=version1_data["version_number"],
        created_at=version1_data["created_at"],
        word_count=version1_data["word_count"],
        char_count=version1_data["char_count"],
    )

    version2_meta = VersionMetadata(
        version_number=version2_data["version_number"],
        created_at=version2_data["created_at"],
        word_count=version2_data["word_count"],
        char_count=version2_data["char_count"],
    )

    diff_chunks_models = [DiffChunk(**chunk) for chunk in diff_chunks]
    analytics_deltas_models = [AnalyticsDelta(**delta) for delta in analytics_deltas]

    # Compute summary statistics
    insertions = sum(1 for c in diff_chunks if c["operation"] == "insert")
    deletions = sum(1 for c in diff_chunks if c["operation"] == "delete")
    total_changes = insertions + deletions

    summary = {
        "total_changes": total_changes,
        "insertions": insertions,
        "deletions": deletions,
        "word_delta": version2_data["word_count"] - version1_data["word_count"],
    }

    return VersionComparisonResponse(
        document_id=doc_id,
        version1=version1_meta,
        version2=version2_meta,
        diff_chunks=diff_chunks_models,
        analytics_deltas=analytics_deltas_models,
        summary=summary,
    )
