"""
Document versioning API routes.
Endpoints for creating, retrieving, and managing document versions.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from database import get_pool
from models import (
    VersionHistoryResponse,
    VersionSaveRequest,
    VersionSaveResponse,
    DocumentVersionResponse,
)
from services import VersioningService, DocumentNotFoundError

logger = logging.getLogger("collab.routes.versions")

router = APIRouter(prefix="/api/documents", tags=["versions"])


def get_versioning_service() -> VersioningService:
    """
    Dependency injection for VersioningService.

    Returns:
        VersioningService instance with database pool.
    """
    pool = get_pool()
    return VersioningService(pool)


@router.post(
    "/{doc_id}/versions",
    response_model=VersionSaveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def save_version(
    doc_id: str,
    request: VersionSaveRequest,
    service: Annotated[VersioningService, Depends(get_versioning_service)],
) -> VersionSaveResponse:
    """
    Save a new version of a document.

    Creates a document record if it doesn't exist. Content is stored as plain text.
    Version numbers are assigned sequentially starting from 1.

    Args:
        doc_id: Document identifier from URL path
        request: Request body containing content to save
        service: VersioningService injected dependency

    Returns:
        VersionSaveResponse with version metadata

    Raises:
        HTTPException: If save fails (DB error, validation error, etc.)

    Example:
        POST /api/documents/abc123/versions
        {
            "content": "# Hello World\n\nThis is my document."
        }

        200 OK
        {
            "version_id": "550e8400-e29b-41d4-a716-446655440000",
            "document_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "version_number": 1,
            "created_at": "2026-02-18T20:15:30.123Z",
            "message": "Version saved successfully"
        }
    """
    try:
        logger.info(
            f"Saving version for document: {doc_id}, content_length={len(request.content)}"
        )

        # Create/get document and save version
        version_id, version_number = await service.create_version(
            doc_id=doc_id,
            content=request.content,
        )

        # Fetch created version to get created_at
        version = await service.get_version_by_number(doc_id, version_number)
        if not version:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Version created but could not be retrieved",
            )

        logger.info(
            f"Version saved successfully: doc_id={doc_id}, version={version_number}"
        )

        return VersionSaveResponse(
            version_id=version_id,
            document_id=version["document_id"],
            version_number=version_number,
            created_at=version["created_at"],
            message="Version saved successfully",
        )

    except ValueError as exc:
        logger.warning(f"Validation error saving version: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except DocumentNotFoundError as exc:
        logger.warning(f"Document not found: {exc}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error saving version: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save version",
        )


@router.get(
    "/{doc_id}/versions",
    response_model=VersionHistoryResponse,
)
async def get_version_history(
    doc_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    service: Annotated[VersioningService, Depends(get_versioning_service)] = None,
) -> VersionHistoryResponse:
    """
    Get paginated version history for a document.

    Returns versions ordered by version_number descending (newest first).
    Each page contains up to 100 versions.

    Args:
        doc_id: Document identifier
        page: Page number (1-based, default: 1)
        page_size: Results per page (1-100, default: 20)
        service: VersioningService injected dependency

    Returns:
        VersionHistoryResponse with paginated version list

    Raises:
        HTTPException: If document not found or query fails

    Example:
        GET /api/documents/abc123/versions?page=1&page_size=20

        200 OK
        {
            "versions": [
                {
                    "id": "...",
                    "document_id": "...",
                    "version_number": 5,
                    "created_at": "2026-02-18T20:15:30.123Z"
                },
                ...
            ],
            "total": 45,
            "page": 1,
            "page_size": 20,
            "total_pages": 3
        }
    """
    try:
        logger.debug(f"Retrieving version history: doc_id={doc_id}, page={page}")

        versions, total = await service.get_version_history(
            doc_id=doc_id,
            page=page,
            page_size=page_size,
        )

        total_pages = (total + page_size - 1) // page_size

        logger.debug(
            f"Version history retrieved: doc_id={doc_id}, versions={len(versions)}, total={total}"
        )

        return VersionHistoryResponse(
            versions=[
                DocumentVersionResponse(
                    id=v["id"],
                    document_id=v["document_id"],
                    version_number=v["version_number"],
                    created_at=v["created_at"],
                    content="",  # Don't return content in list view
                )
                for v in versions
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except DocumentNotFoundError as exc:
        logger.warning(f"Document not found: {exc}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        logger.warning(f"Invalid query parameters: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error retrieving version history: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve version history",
        )


@router.get("/{doc_id}/versions/latest")
async def get_latest_version(
    doc_id: str,
    service: Annotated[VersioningService, Depends(get_versioning_service)] = None,
) -> DocumentVersionResponse:
    """
    Get the latest version of a document.

    Returns the most recent version with full content for document restoration.

    Args:
        doc_id: Document identifier
        service: VersioningService injected dependency

    Returns:
        Latest DocumentVersionResponse with full content

    Raises:
        HTTPException: If document not found or no versions exist

    Example:
        GET /api/documents/abc123/versions/latest

        200 OK
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "document_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "version_number": 5,
            "created_at": "2026-02-18T20:15:30.123Z",
            "content": "# Document content..."
        }
    """
    try:
        logger.debug(f"Retrieving latest version: doc_id={doc_id}")

        version = await service.get_latest_version(doc_id)

        if not version:
            logger.warning(f"No versions found for document: {doc_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No versions found for this document",
            )

        logger.debug(
            f"Latest version retrieved: doc_id={doc_id}, version={version['version_number']}"
        )

        return DocumentVersionResponse(**version)

    except DocumentNotFoundError as exc:
        logger.warning(f"Document not found: {exc}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error retrieving latest version: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve latest version",
        )


@router.get("/{doc_id}/versions/{version_number}")
async def get_version_by_number(
    doc_id: str,
    version_number: Annotated[int, Path(ge=1)],
    service: Annotated[VersioningService, Depends(get_versioning_service)] = None,
) -> DocumentVersionResponse:
    """
    Get a specific version by version number.

    Returns the content and metadata for a specific version number.

    Args:
        doc_id: Document identifier
        version_number: Version number to retrieve (must be >= 1)
        service: VersioningService injected dependency

    Returns:
        DocumentVersionResponse with requested version

    Raises:
        HTTPException: If document/version not found or invalid parameters

    Example:
        GET /api/documents/abc123/versions/3

        200 OK
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "document_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "version_number": 3,
            "created_at": "2026-02-18T20:10:15.123Z",
            "content": "# Document version 3 content..."
        }
    """
    try:
        logger.debug(
            f"Retrieving specific version: doc_id={doc_id}, version={version_number}"
        )

        version = await service.get_version_by_number(doc_id, version_number)

        if not version:
            logger.warning(
                f"Version not found: doc_id={doc_id}, version={version_number}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_number} not found",
            )

        logger.debug(
            f"Version retrieved: doc_id={doc_id}, version={version_number}"
        )

        return DocumentVersionResponse(**version)

    except DocumentNotFoundError as exc:
        logger.warning(f"Document not found: {exc}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        logger.warning(f"Invalid parameters: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(f"Error retrieving version: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve version",
        )
