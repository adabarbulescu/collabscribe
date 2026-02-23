"""Analytics API routes for NLP-powered document analysis."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from database import get_pool
from models.analytics import AnalyticsRequest, AnalyticsResponse, InsightsResponse
from models.topic import TopicModelingResponse
from services.analytics import AnalyticsService
from services.topic_modeling import TopicModelingService

logger = logging.getLogger("collab.routes.analytics")

router = APIRouter(prefix="/api/documents", tags=["analytics"])


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService(get_pool())


@router.post(
    "/{doc_id}/analytics",
    response_model=AnalyticsResponse,
)
async def get_document_analytics(
    doc_id: str,
    request: AnalyticsRequest,
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> AnalyticsResponse:
    """Compute or retrieve cached analytics for document content."""
    try:
        result = await service.get_analytics(doc_id, request.content)
        return AnalyticsResponse(**result)
    except Exception as exc:
        logger.error("Analytics computation failed for %s: %s", doc_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics computation failed",
        )


@router.get(
    "/{doc_id}/insights",
    response_model=InsightsResponse,
)
async def get_document_insights(
    doc_id: str,
    limit: int = Query(60, ge=1, le=200),
    service: Annotated[AnalyticsService, Depends(get_analytics_service)] = None,
) -> InsightsResponse:
    """Return temporal insights derived from document versions."""
    try:
        result = await service.get_insights(doc_id, limit=limit)
        return InsightsResponse(**result)
    except Exception as exc:
        logger.error("Insights retrieval failed for %s: %s", doc_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Insights retrieval failed",
        )


@router.post(
    "/{doc_id}/topics",
    response_model=TopicModelingResponse,
)
async def get_document_topics(
    doc_id: str,
    request: AnalyticsRequest,
    n_topics: int = Query(5, ge=2, le=10, description="Number of topics to extract"),
    method: str = Query("nmf", regex="^(nmf|lda)$", description="Topic modeling method"),
) -> TopicModelingResponse:
    """
    Extract topics from document content using NMF or LDA.

    Args:
        doc_id: Document identifier
        request: Request with document content
        n_topics: Number of topics to extract (2-10, default: 5)
        method: Topic modeling method - "nmf" (default) or "lda"

    Returns:
        TopicModelingResponse with extracted topics and keywords

    Raises:
        HTTPException: If topic extraction fails or document is too short
    """
    try:
        service = TopicModelingService()
        result = service.extract_topics(
            content=request.content,
            n_topics=n_topics,
            method=method.lower(),
            n_keywords=8
        )

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document too short for topic modeling (minimum 100 words required)",
            )

        return TopicModelingResponse(
            document_id=doc_id,
            **result
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Topic modeling failed for %s: %s", doc_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Topic modeling failed",
        )

