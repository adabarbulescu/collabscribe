"""
Document versioning Pydantic models.
Defines request/response schemas and data validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    """Base document model with common fields."""

    title: str = Field(default="Untitled Document", max_length=512)


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""

    pass


class DocumentResponse(DocumentBase):
    """Schema for document responses."""

    id: UUID
    owner_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class DocumentVersionBase(BaseModel):
    """Base version model with common fields."""

    content: str = Field(default="", description="Plain text content of this version")


class DocumentVersionCreate(DocumentVersionBase):
    """Schema for creating a document version."""

    pass


class DocumentVersionResponse(DocumentVersionBase):
    """Schema for version responses."""

    id: UUID
    document_id: UUID
    version_number: int
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class VersionHistoryResponse(BaseModel):
    """Paginated version history response."""

    versions: list[DocumentVersionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1


class VersionSaveRequest(BaseModel):
    """Request body for manual version save."""

    content: str = Field(..., description="Document content to save as version")


class VersionSaveResponse(BaseModel):
    """Response for successful version save."""

    version_id: UUID
    document_id: UUID
    version_number: int
    created_at: datetime
    message: str = "Version saved successfully"
